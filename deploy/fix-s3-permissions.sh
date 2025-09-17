#!/bin/bash

echo "==================================="
echo "S3 Permission Fix Script"
echo "==================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get AWS account ID
echo "Getting AWS Account Information..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not get AWS account ID. Check your AWS CLI configuration.${NC}"
    exit 1
fi

echo -e "${GREEN}AWS Account ID: $ACCOUNT_ID${NC}"
echo ""

# Set bucket name
BUCKET_NAME="dcdentals"
echo "Bucket: $BUCKET_NAME"
echo ""

# Step 1: Update CORS configuration
echo "Step 1: Applying CORS Configuration..."
echo "---------------------------------------"

cat > /tmp/cors.json << 'EOF'
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
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
            "x-amz-id-2",
            "x-amz-meta-original-name"
        ],
        "MaxAgeSeconds": 3000
    }
]
EOF

aws s3api put-bucket-cors --bucket $BUCKET_NAME --cors-configuration file:///tmp/cors.json

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CORS configuration applied${NC}"
else
    echo -e "${RED}✗ Failed to apply CORS configuration${NC}"
fi

# Step 2: Update bucket policy
echo ""
echo "Step 2: Updating Bucket Policy..."
echo "----------------------------------"

# Get current IAM user ARN
IAM_USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
echo "IAM User ARN: $IAM_USER_ARN"

cat > /tmp/bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowPresignedUploads",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::$BUCKET_NAME/cases/*",
            "Condition": {
                "StringEquals": {
                    "s3:x-amz-acl": "private"
                }
            }
        },
        {
            "Sid": "AllowAppAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "$IAM_USER_ARN"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:PutObjectAcl",
                "s3:GetObjectAcl"
            ],
            "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file:///tmp/bucket-policy.json

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Bucket policy updated${NC}"
else
    echo -e "${YELLOW}⚠ Could not update bucket policy (may already exist)${NC}"
fi

# Step 3: Disable "Block all public access" for presigned URLs
echo ""
echo "Step 3: Configuring Public Access Settings..."
echo "----------------------------------------------"

aws s3api put-public-access-block \
    --bucket $BUCKET_NAME \
    --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Public access settings configured${NC}"
else
    echo -e "${YELLOW}⚠ Could not update public access settings${NC}"
fi

# Step 4: Verify IAM permissions
echo ""
echo "Step 4: Verifying IAM Permissions..."
echo "-------------------------------------"

# Test S3 access
aws s3 ls s3://$BUCKET_NAME/ --max-items 1 > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ IAM user can list bucket${NC}"
else
    echo -e "${RED}✗ IAM user cannot list bucket${NC}"
    echo "  Please ensure your IAM user has the following policy attached:"
    echo ""
    cat << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetBucketCORS",
                "s3:PutBucketCORS"
            ],
            "Resource": "arn:aws:s3:::dcdentals"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:GetObjectAcl",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::dcdentals/*"
        }
    ]
}
EOF
fi

# Step 5: Test presigned URL generation
echo ""
echo "Step 5: Testing Presigned URL Generation..."
echo "--------------------------------------------"

# Create a test file
echo "test" > /tmp/test.txt

# Generate presigned URL for upload
PRESIGNED_URL=$(aws s3 presign s3://$BUCKET_NAME/test/test.txt --expires-in 300)

if [ ! -z "$PRESIGNED_URL" ]; then
    echo -e "${GREEN}✓ Presigned URL generated successfully${NC}"
    echo "  URL (first 100 chars): ${PRESIGNED_URL:0:100}..."
else
    echo -e "${RED}✗ Failed to generate presigned URL${NC}"
fi

# Cleanup
rm -f /tmp/cors.json /tmp/bucket-policy.json /tmp/test.txt

echo ""
echo "==================================="
echo "Configuration Summary:"
echo "==================================="
echo ""
echo "1. CORS is configured for uploads from dcdentals.com"
echo "2. Bucket policy allows presigned URL uploads"
echo "3. Public access settings configured for presigned URLs"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update your .env file with correct AWS credentials:"
echo "   AWS_ACCESS_KEY_ID=your-key-id"
echo "   AWS_SECRET_ACCESS_KEY=your-secret-key"
echo "   AWS_STORAGE_BUCKET_NAME=$BUCKET_NAME"
echo "   AWS_S3_REGION_NAME=us-east-1"
echo ""
echo "2. Restart your Django application"
echo ""
echo "3. Test upload with a small file first"
echo ""

# Additional debugging info
echo "==================================="
echo "Debugging Information:"
echo "==================================="
echo ""
echo "If you still get 403 errors, check:"
echo ""
echo "1. AWS CLI configured user:"
aws sts get-caller-identity

echo ""
echo "2. Current CORS configuration:"
aws s3api get-bucket-cors --bucket $BUCKET_NAME 2>/dev/null || echo "No CORS configuration found"

echo ""
echo "3. Current bucket policy:"
aws s3api get-bucket-policy --bucket $BUCKET_NAME 2>/dev/null || echo "No bucket policy found"

echo ""
echo "Done!"