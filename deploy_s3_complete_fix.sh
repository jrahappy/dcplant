#!/bin/bash

# Deploy S3 upload fixes to production server
# Fixes:
# 1. Non-ASCII characters in filenames (Korean, etc.)
# 2. Removed ACL fields causing 403 errors
# 3. Added multipart upload for large files

echo "=========================================="
echo "Deploying S3 Upload Complete Fix"
echo "=========================================="

# Server details
SERVER="ubuntu@dc"
REMOTE_PATH="/home/ubuntu/projects/dcdentals"

# Copy updated files
echo "📦 Copying updated files to server..."
scp cases/views.py $SERVER:$REMOTE_PATH/cases/
scp cases/urls.py $SERVER:$REMOTE_PATH/cases/
scp templates/cases/image_upload_brite.html $SERVER:$REMOTE_PATH/templates/cases/

# Apply changes on server
echo "🔧 Applying changes on server..."
ssh $SERVER << 'EOF'
cd /home/ubuntu/projects/dcdentals

echo "✅ Activating virtual environment..."
source /home/ubuntu/venvs/dcdentals/bin/activate

echo "🔍 Checking Python syntax..."
python -m py_compile cases/views.py
if [ $? -ne 0 ]; then
    echo "❌ Syntax error in views.py!"
    exit 1
fi

python -m py_compile cases/urls.py
if [ $? -ne 0 ]; then
    echo "❌ Syntax error in urls.py!"
    exit 1
fi

echo "✅ Syntax check passed!"

echo "🔄 Restarting Gunicorn..."
sudo systemctl restart gunicorn

# Wait for service to start
sleep 3

echo "📊 Checking Gunicorn status..."
sudo systemctl status gunicorn --no-pager | head -20

if systemctl is-active --quiet gunicorn; then
    echo "✅ Gunicorn is running successfully!"
else
    echo "❌ Gunicorn failed to start! Check logs with:"
    echo "   sudo journalctl -u gunicorn -n 50"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
EOF

echo ""
echo "📋 Summary of changes:"
echo "  1. ✅ Added urllib.parse import for encoding"
echo "  2. ✅ Non-ASCII filenames are now URL-encoded for S3 metadata"
echo "  3. ✅ Removed ACL fields that caused 403 errors"
echo "  4. ✅ Added multipart upload for files > 100MB"
echo ""
echo "🧪 Test the fix:"
echo "  1. Try uploading the file: 임대석.zip (Korean filename)"
echo "  2. Try uploading a large file (200MB+)"
echo ""
echo "📝 If you still see errors, check logs with:"
echo "  ssh $SERVER 'sudo journalctl -u gunicorn -f'"