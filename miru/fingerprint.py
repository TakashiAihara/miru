import ffmpeg
import numpy as np
import imagehash
from PIL import Image
import io
import sys
import logging
from typing import Tuple, Generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_video_duration(file_path: str) -> float:
    """Gets the duration of a video file using ffprobe."""
    try:
        probe = ffmpeg.probe(file_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        # Try to get duration from stream info, fallback to format info
        if 'duration' in video_info:
            return float(video_info['duration'])
        if 'duration' in probe['format']:
            return float(probe['format']['duration'])
        return 0.0
    except Exception as e:
        logger.error(f"Error probing video {file_path}: {e}")
        return 0.0

def generate_fingerprints(
    file_path: str, # Can be a local path or a presigned URL
    fps: float = 1.0, 
    hash_size: int = 8,
    max_duration: float = None # Optional: stop after this many seconds
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates time-series perceptual hashes for a video.
    
    Args:
        file_path: Path to video file or URL.
        fps: Frames per second to sample.
        hash_size: Size of the hash (8 -> 64-bit hash).
        max_duration: If set, stop processing after this many video seconds.
        
    Returns:
        Tuple of (timestamps, hashes)
    """
    
    # 1. Get dimensions/duration to ensure valid video
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if not video_stream:
            logger.warning(f"No video stream found in {file_path}")
            return np.array([]), np.array([])
            
        width = int(video_stream['width'])
        height = int(video_stream['height'])
    except ffmpeg.Error as e:
        logger.error(f"ffprobe error: {e.stderr.decode() if e.stderr else str(e)}")
        return np.array([]), np.array([])

    # 2. Setup ffmpeg process to output raw video frames to stdout
    # We resize to a small size (e.g. 144p or small enough for hash) to speed up transfer
    # pHash resizes to 32x32 (or hash_size*4) internally anyway, so we can resize early.
    target_w, target_h = 144, 144 
    
    # Build ffmpeg command with duration limit if specified
    input_stream = ffmpeg.input(file_path)
    if max_duration:
        input_stream = ffmpeg.input(file_path, t=max_duration)
    
    process = (
        input_stream
        .filter('fps', fps=fps)
        .filter('scale', target_w, target_h)
        .output('pipe:', format='rawvideo', pix_fmt='rgb24')
        .run_async(pipe_stdout=True, pipe_stderr=True, quiet=False)
    )
    
    logger.info(f"FFmpeg process started for {file_path}")

    hashes = []
    timestamps = []
    frame_idx = 0
    frame_size = target_w * target_h * 3
    
    while True:
        in_bytes = process.stdout.read(frame_size)
        if not in_bytes:
            break
            
        if len(in_bytes) != frame_size:
            logger.warning("Incomplete frame read")
            break
            
        # Create image from raw bytes
        image = Image.frombytes('RGB', (target_w, target_h), in_bytes)
        
        # Calculate pHash
        # imagehash.phash returns an ImageHash object. 
        # We convert it to numpy array of booleans then pack to uint64 for efficiency
        h = imagehash.phash(image, hash_size=hash_size)
        
        # Access the internal boolean array (hash.hash) and pack bits to uint64
        # Note: imagehash stores hash as a boolean 2D array.
        # flatten -> packbits gives uint8 array -> combined to uint64
        # However, imagehash objects can be converted to distinct integers directly.
        # But for 'hex' consistency or Hamming distance, we need a consistent int representation.
        # A simple way involves converting hex string to int, but that's slow.
        # Faster: construct int from boolean array.
        
        # Provide a 64-bit integer representation
        hash_int = 0
        flat_hash = h.hash.flatten()
        
        # Pack bits manually or use numpy (if size fits)
        # For 8x8 hash (64 bits), it fits in one uint64.
        if len(flat_hash) == 64:
             # Most efficient packing for 64 bits
             hash_val = np.packbits(flat_hash.astype(int)).view(np.uint64)[0]
             # Note: packbits output is big-endian by default for bits, but let's be consistent.
             # Actually packbits packs high-to-low bit index per byte.
             # We just need CONSISTENCY.
             hash_val = int(str(h), 16) # Fallback to hex parsing for absolute correctness with library assumptions
             hashes.append(hash_val)
        else:
            # If larger hash, we might need multiple ints or big int. 
            # For this MVP we assume 64-bit pHash.
            hash_val = int(str(h), 16)
            hashes.append(hash_val)

        if max_duration and (frame_idx / fps) > max_duration:
            break

        timestamps.append(frame_idx / fps)
        frame_idx += 1

    process.wait()
    logger.info(f"FFmpeg processing complete. Generated {len(hashes)} frames.")
    
    return np.array(timestamps, dtype=np.float32), np.array(hashes, dtype=np.uint64)


def generate_fingerprints_adaptive(
    file_path: str,
    target_frames: int = 150,
    min_fps: float = 0.05,
    max_fps: float = 1.0,
    hash_size: int = 8
) -> Tuple[np.ndarray, np.ndarray]:
    """
    動画の長さに応じて適応的にサンプリング
    
    短い動画: 高密度サンプリング (1fps)
    長い動画: 低密度サンプリング (0.05fps = 20秒に1回)
    
    Args:
        file_path: 動画ファイルパス
        target_frames: 目標フレーム数 (デフォルト: 150)
        min_fps: 最小サンプリングレート (デフォルト: 0.05 = 20秒に1回)
        max_fps: 最大サンプリングレート (デフォルト: 1.0 = 1秒に1回)
        hash_size: ハッシュサイズ
    
    Returns:
        Tuple of (timestamps, hashes)
    
    Examples:
        1分動画 (60秒): fps=1.0 → 60フレーム
        10分動画 (600秒): fps=0.25 → 150フレーム
        30分動画 (1800秒): fps=0.083 → 150フレーム
    """
    # 動画の長さを取得
    duration = get_video_duration(file_path)
    
    if duration <= 0:
        logger.warning(f"Could not determine duration for {file_path}, using max_fps")
        fps = max_fps
    else:
        # fpsを計算: target_frames / duration
        # ただし min_fps と max_fps の範囲内に制限
        fps = min(max_fps, max(min_fps, target_frames / duration))
    
    logger.info(f"Adaptive sampling: duration={duration:.1f}s, fps={fps:.3f}, expected_frames={int(duration * fps)}")
    
    # max_duration は使わず、全体を処理
    return generate_fingerprints(file_path, fps=fps, max_duration=None, hash_size=hash_size)
