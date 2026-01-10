import os
import boto3
import numpy as np
from datetime import datetime
from tqdm import tqdm
import logging
from .storage import Database
from .fingerprint import generate_fingerprints

# Configuration
FINGERPRINT_DIR = "data/fingerprints"
os.makedirs(FINGERPRINT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Indexer:
    def __init__(self, 
                 access_key: str, 
                 secret_key: str, 
                 bucket_name: str,
                 endpoint_url: str,
                 region: str = "us-east-1",
                 db_path: str = "miru.db"):
        
        self.bucket_name = bucket_name
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
        
        # Using paginator for large buckets
        paginator = self.s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=self.bucket_name)

        count = 0
        for page in page_iterator:
            if 'Contents' not in page:
                continue
                
            for item in page['Contents']:
                key = item['Key']
                # Simplistic filter for video files
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

    def process_unprocessed(self, limit: int = 100):
        """Processes videos that haven't been fingerprinted yet."""
        videos = self.db.get_unprocessed_videos(limit=limit)
        
        if not videos:
            logger.info("No unprocessed videos found.")
            return

        logger.info(f"Processing {len(videos)} videos...")
        
        for video in tqdm(videos):
            try:
                self._process_single_video(video)
            except Exception as e:
                logger.error(f"Failed to process {video['s3_key']}: {e}")

    def _process_single_video(self, video: dict):
        key = video['s3_key']
        logger.info(f"Processing: {key}")
        
        # 1. Download to temporary file
        import tempfile
        temp_dir = "data/temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create safe filename
        safe_filename = f"{video['id']}.mp4"
        local_path = os.path.join(temp_dir, safe_filename)
        
        logger.info(f"Downloading {key} to {local_path}...")
        try:
            self.s3.download_file(self.bucket_name, key, local_path)
            logger.info(f"Download complete: {local_path}")
        except Exception as e:
            logger.error(f"Failed to download {key}: {e}")
            return
        
        # 2. Generate Fingerprints from local file
        # Use defaults: fps=1.0, hash_size=8
        # For testing, limit to first 30 seconds
        logger.info(f"Generating fingerprints for {key}...")
        timestamps, hashes = generate_fingerprints(local_path, fps=1.0, max_duration=30.0)
        logger.info(f"Generated {len(hashes)} hashes for {key}")
        
        # Clean up temp file
        try:
            os.remove(local_path)
        except:
            pass
        
        if len(hashes) == 0:
            logger.warning(f"No hashes generated for {key}. Maybe file is corrupt or not a video.")
            return

        # 3. Save to disk
        # Create a safe filename from ID or Key
        # Using ID is safer to avoid directory depth issues or special chars
        filename = f"{video['id']}_fingerprint.npz"
        filepath = os.path.join(FINGERPRINT_DIR, filename)
        
        np.savez_compressed(filepath, timestamps=timestamps, hashes=hashes)
        
        # 4. Mark as processed
        duration = float(timestamps[-1]) if len(timestamps) > 0 else 0.0
        self.db.mark_processed(video['id'], duration, filepath)
