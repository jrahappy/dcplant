# Fix for the generate_s3_presigned_url function
# Replace the metadata section with this code:

import urllib.parse

# Around line 1500-1530, update the metadata handling:

# Encode non-ASCII characters in filename for S3 metadata
encoded_filename = urllib.parse.quote(file_name, safe='')

# For multipart upload (if file_size > 100MB):
if file_size > 100 * 1024 * 1024:
    multipart_upload = s3_client.create_multipart_upload(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=s3_key,
        ContentType=file_type,
        Metadata={
            'original-name': encoded_filename,  # Use encoded filename
            'case-id': str(case.id),
            'user-id': str(request.user.id)
        }
    )
    # ... rest of multipart code

# For regular upload:
presigned_post = s3_client.generate_presigned_post(
    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
    Key=s3_key,
    Fields={
        "Content-Type": file_type,
        "x-amz-meta-original-name": encoded_filename,  # Use encoded filename
        "x-amz-meta-case-id": str(case.id),
        "x-amz-meta-user-id": str(request.user.id),
    },
    Conditions=[
        {"Content-Type": file_type},
        ["content-length-range", 0, 1073741824],
    ],
    ExpiresIn=3600
)