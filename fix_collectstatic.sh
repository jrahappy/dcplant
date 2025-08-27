#!/bin/bash
# Fix collectstatic issues on AWS Ubuntu

echo "=== Fixing Django Static Files Collection ==="

# Ensure we're in the right directory
cd /home/ubuntu/projects/dcplant

# Create staticfiles directory with proper permissions
echo "1. Creating staticfiles directory..."
mkdir -p staticfiles
chmod 755 staticfiles

# Clear old static files
echo "2. Clearing old static files..."
rm -rf staticfiles/*

# Temporarily disable WhiteNoise compression for collectstatic
echo "3. Running collectstatic without compression..."
python manage.py collectstatic --noinput --clear

# Fix permissions after collection
echo "4. Fixing permissions..."
find staticfiles -type f -exec chmod 644 {} \;
find staticfiles -type d -exec chmod 755 {} \;

# If running with sudo is needed
if [ "$EUID" -eq 0 ]; then
    chown -R ubuntu:ubuntu staticfiles
fi

echo "=== Static files collected successfully ==="
echo ""
echo "Files in staticfiles directory:"
ls -la staticfiles/ | head -10
echo ""
echo "Total static files:"
find staticfiles -type f | wc -l