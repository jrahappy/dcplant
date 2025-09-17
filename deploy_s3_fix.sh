#!/bin/bash

# Deploy S3 upload fixes to production server
# This script fixes the 403 error for large file uploads

echo "Deploying S3 upload fixes..."

# Server details
SERVER="ubuntu@dc"
REMOTE_PATH="/home/ubuntu/projects/dcdentals"

# Copy updated files
echo "Copying updated files to server..."
scp cases/views.py $SERVER:$REMOTE_PATH/cases/
scp cases/urls.py $SERVER:$REMOTE_PATH/cases/
scp templates/cases/image_upload_brite.html $SERVER:$REMOTE_PATH/templates/cases/

# Apply changes on server
echo "Applying changes on server..."
ssh $SERVER << 'EOF'
cd /home/ubuntu/projects/dcdentals

# Activate virtual environment
source /home/ubuntu/venvs/dcdentals/bin/activate

# Check syntax
python -m py_compile cases/views.py
python -m py_compile cases/urls.py

# Restart Gunicorn
sudo systemctl restart gunicorn

# Check status
sleep 2
sudo systemctl status gunicorn --no-pager | head -20

echo "Deployment complete!"
EOF

echo "S3 upload fixes deployed successfully!"
echo ""
echo "Changes made:"
echo "1. Removed ACL field that was causing 403 errors"
echo "2. Added multipart upload support for files > 100MB"
echo "3. Updated frontend to handle chunked uploads"
echo ""
echo "Test with a large file (200MB+) to verify the fix works."