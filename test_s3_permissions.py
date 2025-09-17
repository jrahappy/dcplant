#!/usr/bin/env python
"""
Test and fix S3 permissions for DCPlant uploads
Run this script to diagnose and fix S3 403 errors
"""

import os
import sys
import json
import boto3
from botocore.exceptions import ClientError

# Add Django project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.conf import settings


def test_s3_connection():
    """Test basic S3 connection"""
    print("Testing S3 Connection...")
    print("-" * 40)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        )

        # Test bucket access
        response = s3_client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        print(f"✓ Connected to bucket: {settings.AWS_STORAGE_BUCKET_NAME}")

        # Get bucket location
        location = s3_client.get_bucket_location(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        print(f"✓ Bucket region: {location.get('LocationConstraint', 'us-east-1')}")

        return s3_client

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"✗ Bucket not found: {settings.AWS_STORAGE_BUCKET_NAME}")
        elif error_code == '403':
            print(f"✗ Access denied to bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
            print("  Check your AWS credentials and IAM permissions")
        else:
            print(f"✗ Error: {e}")
        return None


def check_cors_configuration(s3_client):
    """Check and fix CORS configuration"""
    print("\nChecking CORS Configuration...")
    print("-" * 40)

    try:
        cors = s3_client.get_bucket_cors(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        print("✓ CORS configuration found:")
        print(json.dumps(cors['CORSRules'], indent=2))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchCORSConfiguration':
            print("✗ No CORS configuration found")
            print("  Applying CORS configuration...")

            cors_config = {
                'CORSRules': [
                    {
                        'AllowedHeaders': ['*'],
                        'AllowedMethods': ['GET', 'HEAD', 'PUT', 'POST', 'DELETE'],
                        'AllowedOrigins': [
                            'https://dcdentals.com',
                            'https://www.dcdentals.com',
                            'http://localhost:8000',
                            'http://127.0.0.1:8000'
                        ],
                        'ExposeHeaders': [
                            'ETag',
                            'x-amz-server-side-encryption',
                            'x-amz-request-id',
                            'x-amz-id-2'
                        ],
                        'MaxAgeSeconds': 3000
                    }
                ]
            }

            try:
                s3_client.put_bucket_cors(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    CORSConfiguration=cors_config
                )
                print("  ✓ CORS configuration applied successfully")
            except Exception as e:
                print(f"  ✗ Failed to apply CORS: {e}")
        else:
            print(f"✗ Error checking CORS: {e}")


def test_presigned_post(s3_client):
    """Test generating presigned POST URL"""
    print("\nTesting Presigned POST URL Generation...")
    print("-" * 40)

    try:
        import uuid

        test_key = f"test/test-{uuid.uuid4()}.txt"

        # Generate presigned POST
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=test_key,
            Fields={
                "acl": "private",
                "Content-Type": "text/plain",
            },
            Conditions=[
                {"acl": "private"},
                {"Content-Type": "text/plain"},
                ["content-length-range", 0, 1048576],  # Max 1MB
            ],
            ExpiresIn=3600
        )

        print("✓ Presigned POST URL generated successfully")
        print(f"  URL: {presigned_post['url']}")
        print(f"  Key: {test_key}")
        print(f"  Fields: {list(presigned_post['fields'].keys())}")

        return presigned_post

    except Exception as e:
        print(f"✗ Failed to generate presigned POST: {e}")
        return None


def test_file_upload(s3_client, presigned_post):
    """Test actual file upload using presigned POST"""
    print("\nTesting File Upload...")
    print("-" * 40)

    if not presigned_post:
        print("✗ Skipping upload test (no presigned URL)")
        return

    try:
        import requests

        # Create test file content
        test_content = b"Test upload from DCPlant"

        # Prepare multipart upload
        files = {'file': ('test.txt', test_content)}

        # Upload to S3
        response = requests.post(
            presigned_post['url'],
            data=presigned_post['fields'],
            files=files
        )

        if response.status_code == 204:
            print("✓ Test file uploaded successfully")

            # Try to read it back
            test_key = presigned_post['fields']['key']
            try:
                obj = s3_client.get_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=test_key
                )
                print(f"  ✓ File verified: {test_key}")

                # Clean up
                s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=test_key
                )
                print("  ✓ Test file cleaned up")
            except Exception as e:
                print(f"  ⚠ Could not verify file: {e}")
        else:
            print(f"✗ Upload failed with status {response.status_code}")
            print(f"  Response: {response.text}")

    except Exception as e:
        print(f"✗ Upload test failed: {e}")


def check_iam_permissions():
    """Check IAM user permissions"""
    print("\nChecking IAM Permissions...")
    print("-" * 40)

    try:
        sts_client = boto3.client(
            'sts',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        )

        identity = sts_client.get_caller_identity()
        print(f"✓ AWS Account: {identity['Account']}")
        print(f"✓ User ARN: {identity['Arn']}")
        print(f"✓ User ID: {identity['UserId']}")

    except Exception as e:
        print(f"✗ Could not get IAM identity: {e}")


def main():
    print("=" * 50)
    print("S3 Upload Permission Tester for DCPlant")
    print("=" * 50)

    # Check if S3 is enabled
    if not getattr(settings, 'USE_S3', False):
        print("✗ S3 is not enabled in settings (USE_S3=False)")
        print("  Set USE_S3=True in your .env file")
        return

    print(f"✓ S3 is enabled")
    print(f"  Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"  Region: {getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')}")

    # Test connection
    s3_client = test_s3_connection()
    if not s3_client:
        print("\n✗ Cannot proceed without S3 connection")
        return

    # Check IAM
    check_iam_permissions()

    # Check CORS
    check_cors_configuration(s3_client)

    # Test presigned POST
    presigned_post = test_presigned_post(s3_client)

    # Test upload
    test_file_upload(s3_client, presigned_post)

    print("\n" + "=" * 50)
    print("Summary:")
    print("=" * 50)

    if presigned_post:
        print("✓ S3 configuration appears to be working")
        print("\nIf you still get 403 errors in the browser:")
        print("1. Clear browser cache and cookies")
        print("2. Check browser console for CORS errors")
        print("3. Ensure your domain is in the CORS AllowedOrigins")
        print("4. Check that the bucket policy allows uploads")
    else:
        print("✗ S3 configuration needs attention")
        print("\nRecommended fixes:")
        print("1. Run: bash deploy/fix-s3-permissions.sh")
        print("2. Check IAM user has s3:PutObject permission")
        print("3. Ensure bucket exists and is in the correct region")


if __name__ == '__main__':
    main()