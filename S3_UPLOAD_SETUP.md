# S3 Direct Upload Setup Guide

## Overview
This guide explains how to configure AWS S3 for direct file uploads from the browser, bypassing Django server memory for large files.

## 1. S3 Bucket Configuration

### Create S3 Bucket (if not exists)
```bash
aws s3api create-bucket --bucket your-bucket-name --region us-east-1
```

### Apply CORS Configuration

**Option 1: Using AWS CLI**
```bash
cd deploy
aws s3api put-bucket-cors --bucket your-bucket-name --cors-configuration file://s3-cors-config.json
```

**Option 2: Using AWS Console**
1. Go to AWS S3 Console
2. Select your bucket
3. Go to "Permissions" tab
4. Scroll to "Cross-origin resource sharing (CORS)"
5. Click "Edit" and paste this configuration:

```json
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "GET",
            "HEAD",
            "PUT",
            "POST",
            "DELETE"
        ],
        "AllowedOrigins": [
            "https://dcdentals.com",
            "https://www.dcdentals.com",
            "http://localhost:8000",
            "http://127.0.0.1:8000"
        ],
        "ExposeHeaders": [
            "ETag",
            "x-amz-server-side-encryption",
            "x-amz-request-id",
            "x-amz-id-2"
        ],
        "MaxAgeSeconds": 3000
    }
]
```

**Important:** Replace the `AllowedOrigins` with your actual domain names.

## 2. IAM User Configuration

Create an IAM user with the following policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:GetObjectVersion"
            ],
            "Resource": "arn:aws:s3:::your-bucket-name/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": "arn:aws:s3:::your-bucket-name"
        }
    ]
}
```

## 3. Django Environment Configuration

Add these to your `.env` file:

```bash
# Enable S3 storage
USE_S3=True

# AWS Credentials
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key

# S3 Configuration
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1

# Optional: Custom domain if using CloudFront
# AWS_S3_CUSTOM_DOMAIN=cdn.yourdomain.com
```

## 4. How It Works

### Upload Flow
1. **Small files (< 50MB)**: Upload through Django server
2. **Large files (> 50MB)**: Direct upload to S3

### For Large Files:
1. Browser requests pre-signed URL from Django
2. Browser uploads directly to S3 (no Django memory used)
3. Real-time progress tracking during upload
4. After S3 upload, Django processes the file asynchronously
5. File is downloaded from S3, processed, and saved to database

## 5. Troubleshooting

### CORS Error
If you see CORS errors in the browser console:
1. Verify CORS configuration is applied to the bucket
2. Check that your domain is in the `AllowedOrigins` list
3. Clear browser cache

### Permission Denied
If uploads fail with permission errors:
1. Check IAM user has proper S3 permissions
2. Verify AWS credentials in `.env` file
3. Check bucket policy allows uploads

### S3 Not Available
If the system doesn't detect S3:
1. Verify `USE_S3=True` in `.env`
2. Check AWS credentials are correct
3. Ensure bucket exists and is accessible

## 6. Testing

Test S3 configuration:
```python
python manage.py shell

from django.conf import settings
import boto3

# Test connection
s3 = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME
)

# List buckets
print(s3.list_buckets())

# Test upload
s3.put_object(
    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
    Key='test.txt',
    Body=b'Hello World'
)
```

## 7. Performance Benefits

- **No Django memory usage** for large uploads
- **Faster uploads** directly to S3
- **Better scalability** for multiple concurrent uploads
- **Reduced server load**
- **Progress tracking** in real-time

## 8. Security Notes

- Pre-signed URLs expire after 1 hour
- File size limited to 1GB per upload
- Files are scanned for DICOM metadata server-side
- Original filenames are preserved in metadata
- User and case IDs are tracked for audit

## 9. Monitoring

Monitor S3 usage:
```bash
# Check bucket size
aws s3 ls s3://your-bucket-name --recursive --human-readable --summarize

# View recent uploads
aws s3api list-objects-v2 --bucket your-bucket-name --max-items 10
```

## 10. Cleanup

To remove old uploads from S3 (optional):
```bash
# Delete files older than 30 days
aws s3 rm s3://your-bucket-name/cases/ --recursive --exclude "*" --include "*/uploads/*" --older-than 30
```

---

For issues or questions, check the application logs and AWS CloudWatch for detailed error messages.