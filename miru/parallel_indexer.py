import os
import boto3
import numpy as np
from datetime import datetime
from tqdm import tqdm
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from .storage import Database
from .fingerprint import generate_fingerprints_adaptive

# Configuration
FINGERPRINT_DIR = "data/fingerprints"
os.makedirs(FINGERPRINT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ParallelIndexer:
    """並列処理対応のIndexer"""
    
    def __init__(self, 
                 access_key: str, 
                 secret_key: str, 
                 bucket_name: str,
                 endpoint_url: str,
                 region: str = "us-east-1",
                 db_path: str = "miru.db"):
        
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.db_path = db_path
        
        # メインプロセス用のS3クライアント
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.db = Database(db_path)

    def scan_bucket(self):
        """Scans the S3 bucket and updates the inventory in DB."""
        logger.info("Starting bucket scan...")
        
        paginator = self.s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=self.bucket_name)

        count = 0
        for page in page_iterator:
            if 'Contents' not in page:
                continue
                
            for item in page['Contents']:
                key = item['Key']
                if not key.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
                    continue
                    
                self.db.add_or_update_video(
                    key=key, 
                    size=item['Size'], 
                    last_modified=item['LastModified']
                )
                count += 1
                if count % 1000 == 0:
                    logger.info(f"Scanned {count} videos...")
        
        logger.info(f"Bucket scan complete. Total videos found: {count}")

    def process_unprocessed(self, limit: int = None, workers: int = None):
        """
        並列処理で未処理動画を処理
        
        Args:
            limit: 処理する動画数の上限 (Noneで全件)
            workers: ワーカー数 (NoneでCPUコア数)
        """
        if workers is None:
            workers = multiprocessing.cpu_count()
        
        videos = self.db.get_unprocessed_videos(limit=limit)
        
        if not videos:
            logger.info("No unprocessed videos found.")
            return

        logger.info(f"Processing {len(videos)} videos with {workers} workers...")
        
        # ProcessPoolExecutor で並列処理
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # 各動画の処理タスクをサブミット
            futures = {
                executor.submit(
                    _process_video_worker,
                    video,
                    self.bucket_name,
                    self.endpoint_url,
                    self.access_key,
                    self.secret_key,
                    self.region,
                    self.db_path
                ): video
                for video in videos
            }
            
            # 進捗バー付きで結果を回収
            success_count = 0
            error_count = 0
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
                video = futures[future]
                try:
                    future.result()
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to process {video['s3_key']}: {e}")
                    error_count += 1
            
            logger.info(f"Processing complete. Success: {success_count}, Errors: {error_count}")


def _process_video_worker(video, bucket_name, endpoint_url, access_key, secret_key, region, db_path):
    """
    ワーカープロセスで実行される処理関数
    
    Note: ProcessPoolExecutor では各ワーカーが独立したプロセスなので、
          S3クライアントとDBコネクションを個別に作成する必要がある
    """
    # ワーカープロセス用のS3クライアント
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    # ワーカープロセス用のDBコネクション
    db = Database(db_path)
    
    key = video['s3_key']
    logger.info(f"[Worker {os.getpid()}] Processing: {key}")
    
    # 1. Download to temporary file
    temp_dir = "data/temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    safe_filename = f"{video['id']}.mp4"
    local_path = os.path.join(temp_dir, safe_filename)
    
    try:
        # ダウンロード
        s3.download_file(bucket_name, key, local_path)
        logger.debug(f"[Worker {os.getpid()}] Downloaded: {local_path}")
        
        # フィンガープリント生成 (適応的サンプリング)
        timestamps, hashes = generate_fingerprints_adaptive(
            local_path,
            target_frames=150  # 約150フレームを目標
        )
        
        if len(hashes) == 0:
            logger.warning(f"[Worker {os.getpid()}] No hashes generated for {key}")
            return
        
        logger.info(f"[Worker {os.getpid()}] Generated {len(hashes)} hashes for {key}")
        
        # 保存
        filename = f"{video['id']}_fingerprint.npz"
        filepath = os.path.join(FINGERPRINT_DIR, filename)
        np.savez_compressed(filepath, timestamps=timestamps, hashes=hashes)
        
        # DBを更新
        duration = float(timestamps[-1]) if len(timestamps) > 0 else 0.0
        db.mark_processed(video['id'], duration, filepath)
        
        logger.debug(f"[Worker {os.getpid()}] Completed: {key}")
        
    finally:
        # 一時ファイル削除
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except:
                pass
