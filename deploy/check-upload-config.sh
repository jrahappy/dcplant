#!/bin/bash

echo "Checking Upload Configuration..."
echo "================================="

# Check Nginx configuration
echo ""
echo "1. Nginx Configuration:"
echo "-----------------------"
if [ -f /etc/nginx/nginx.conf ]; then
    echo "✓ Nginx config found"

    # Check client_max_body_size
    max_size=$(grep -r "client_max_body_size" /etc/nginx/ 2>/dev/null | head -1)
    if [ ! -z "$max_size" ]; then
        echo "  Current setting: $max_size"
    else
        echo "  ⚠ client_max_body_size not set (default is 1M)"
        echo "  → Add 'client_max_body_size 1024M;' to nginx config"
    fi

    # Check timeout settings
    timeout=$(grep -r "proxy_read_timeout" /etc/nginx/ 2>/dev/null | head -1)
    if [ ! -z "$timeout" ]; then
        echo "  Timeout setting: $timeout"
    else
        echo "  ⚠ proxy_read_timeout not set (default is 60s)"
        echo "  → Add timeout settings to nginx config"
    fi
else
    echo "✗ Nginx config not found"
fi

# Check Gunicorn configuration
echo ""
echo "2. Gunicorn Configuration:"
echo "--------------------------"
if pgrep -f gunicorn > /dev/null; then
    echo "✓ Gunicorn is running"

    # Get gunicorn process info
    ps aux | grep gunicorn | head -2
else
    echo "⚠ Gunicorn is not running"
fi

# Check Django settings
echo ""
echo "3. Django Settings:"
echo "-------------------"
python manage.py shell << EOF
from django.conf import settings
print(f"FILE_UPLOAD_MAX_MEMORY_SIZE: {settings.FILE_UPLOAD_MAX_MEMORY_SIZE / 1024 / 1024}MB")
print(f"DATA_UPLOAD_MAX_MEMORY_SIZE: {settings.DATA_UPLOAD_MAX_MEMORY_SIZE / 1024 / 1024}MB")
print(f"DATA_UPLOAD_MAX_NUMBER_FILES: {settings.DATA_UPLOAD_MAX_NUMBER_FILES}")
EOF

# Check S3 configuration
echo ""
echo "4. S3 Configuration:"
echo "--------------------"
python manage.py shell << EOF
from django.conf import settings
if hasattr(settings, 'USE_S3') and settings.USE_S3:
    print("✓ S3 is enabled")
    print(f"  Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"  Region: {settings.AWS_S3_REGION_NAME}")

    # Test S3 connection
    try:
        import boto3
        s3 = boto3.client('s3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        s3.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        print("  ✓ S3 connection successful")
    except Exception as e:
        print(f"  ✗ S3 connection failed: {e}")
else:
    print("⚠ S3 is not enabled")
    print("  To enable, set USE_S3=True in .env")
EOF

# Check system limits
echo ""
echo "5. System Limits:"
echo "-----------------"
echo "  Open files limit: $(ulimit -n)"
echo "  Process limit: $(ulimit -u)"

# Recommendations
echo ""
echo "Recommendations:"
echo "----------------"
echo "1. For large file uploads (>100MB), ensure:"
echo "   - Nginx: client_max_body_size 1024M;"
echo "   - Nginx: proxy timeouts >= 3600s"
echo "   - Gunicorn: timeout >= 3600"
echo "   - S3 enabled for direct uploads"
echo ""
echo "2. Apply recommended Nginx config:"
echo "   sudo cp nginx-large-upload.conf /etc/nginx/sites-available/dcplant"
echo "   sudo ln -s /etc/nginx/sites-available/dcplant /etc/nginx/sites-enabled/"
echo "   sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "3. Restart Gunicorn with new config:"
echo "   sudo systemctl restart dcplant"
echo ""