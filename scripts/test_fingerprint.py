
import os
import sys
import boto3
from dotenv import load_dotenv
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miru.fingerprint import generate_fingerprints

load_dotenv()

WASABI_ACCESS_KEY = os.environ.get("WASABI_ACCESS_KEY")
WASABI_SECRET_KEY = os.environ.get("WASABI_SECRET_KEY")
WASABI_REGION = os.environ.get("WASABI_REGION", "ap-northeast-1")
WASABI_ENDPOINT = f"https://s3.{WASABI_REGION}.wasabisys.com"
BUCKET_NAME = os.environ.get("WASABI_BUCKET_NAME")

def test_s3_fingerprint():
    s3 = boto3.client(
        's3',
        endpoint_url=WASABI_ENDPOINT,
        aws_access_key_id=WASABI_ACCESS_KEY,
        aws_secret_access_key=WASABI_SECRET_KEY,
        region_name=WASABI_REGION
    )

    print("Fetching first video from bucket...")
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, MaxKeys=5)
        if 'Contents' not in response:
            print("No files found.")
            return

        # Find first mp4
        video_key = None
        for item in response['Contents']:
            if item['Key'].lower().endswith('.mp4'):
                video_key = item['Key']
                break
        
        if not video_key:
            print("No MP4 files found in the first 5 objects.")
            return

        print(f"Testing with: {video_key}")
        
        # Generate Presigned URL
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': video_key},
            ExpiresIn=3600
        )
        print(f"Generated URL (truncated): {url[:50]}...")

        print("Generating fingerprints (First 20 seconds)...")
        # Sample just a bit to be fast
        timestamps, hashes = generate_fingerprints(url, fps=1.0, max_duration=20.0)
        
        print("\n=== Results ===")
        print(f"Total Frames: {len(hashes)}")
        print(f"Hashes (first 5): {[hex(h) for h in hashes[:5]]}")
        print(f"Timestamps (first 5): {timestamps[:5]}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_s3_fingerprint()
