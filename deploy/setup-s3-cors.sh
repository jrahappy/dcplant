#!/bin/bash

# Setup S3 CORS Configuration
# Usage: ./setup-s3-cors.sh

echo "Setting up S3 CORS configuration..."

# Read bucket name from environment or prompt
if [ -z "$AWS_STORAGE_BUCKET_NAME" ]; then
    read -p "Enter your S3 bucket name: " BUCKET_NAME
else
    BUCKET_NAME=$AWS_STORAGE_BUCKET_NAME
fi

# Apply CORS configuration
aws s3api put-bucket-cors \
    --bucket $BUCKET_NAME \
    --cors-configuration file://s3-cors-config.json

if [ $? -eq 0 ]; then
    echo "✓ CORS configuration applied successfully to bucket: $BUCKET_NAME"

    # Verify the configuration
    echo ""
    echo "Current CORS configuration:"
    aws s3api get-bucket-cors --bucket $BUCKET_NAME
else
    echo "✗ Failed to apply CORS configuration"
    exit 1
fi

echo ""
echo "You can also apply this configuration through the AWS Console:"
echo "1. Go to S3 > Your Bucket > Permissions > CORS"
echo "2. Paste the contents of s3-cors-config.json"
echo ""