
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miru.indexer import Indexer

load_dotenv()

S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

def main():
    if not all([S3_ACCESS_KEY, S3_SECRET_KEY, BUCKET_NAME, S3_ENDPOINT_URL]):
        print("Error: Missing environment variables.")
        print("Required: S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME, S3_ENDPOINT_URL")
        return

    indexer = Indexer(
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        bucket_name=BUCKET_NAME,
        endpoint_url=S3_ENDPOINT_URL,
        region=S3_REGION
    )

    print("Step 1: Scanning Bucket Inventory...")
    indexer.scan_bucket()
    
    print("\nStep 2: Processing Unprocessed Videos (Limit 5)...")
    indexer.process_unprocessed(limit=5)
    
    print("\nDone.")

if __name__ == "__main__":
    main()
