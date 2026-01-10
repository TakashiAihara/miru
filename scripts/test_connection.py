
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# S3-Compatible Storage Configuration
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

def test_connection():
    print(f"Connecting to S3-compatible storage ({S3_ENDPOINT_URL})...")
    s3 = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION
    )

    try:
        if not BUCKET_NAME:
            print("Error: WASABI_BUCKET_NAME is not set in .env")
            return

        response = s3.list_objects_v2(Bucket=BUCKET_NAME, MaxKeys=5)
        print(f"Successfully connected to bucket: {BUCKET_NAME}")
        if 'Contents' in response:
            for item in response['Contents']:
                print(f" - {item['Key']} (Size: {item['Size']})")
        else:
            print("Bucket is empty or no objects found.")
    except Exception as e:
        print(f"Error connecting to S3: {e}")

if __name__ == "__main__":
    test_connection()
