#!/bin/bash
# Fix static files on AWS Ubuntu server

echo "=== Fixing DCPlant Static Files on AWS ==="

# Navigate to project directory
cd /home/ubuntu/dcplant || exit

# Pull latest changes from git
echo "1. Pulling latest changes..."
git pull origin master

# Activate virtual environment
echo "2. Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "3. Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "4. Collecting static files..."
python manage.py collectstatic --noinput --clear

# Fix permissions for static files
echo "5. Setting correct permissions..."
sudo chown -R www-data:www-data staticfiles/
sudo chmod -R 755 staticfiles/

# Fix permissions for media files
echo "6. Setting media file permissions..."
sudo chown -R www-data:www-data media/
sudo chmod -R 755 media/

# Check if nginx is configured correctly
echo "7. Checking nginx configuration..."
if [ -f /etc/nginx/sites-available/dcplant ]; then
    echo "Nginx configuration found. Updating..."
    
    # Create proper nginx config
    sudo tee /etc/nginx/sites-available/dcplant > /dev/null <<EOF
server {
    listen 80;
    server_name 3.234.238.120;
    
    client_max_body_size 100M;
    
    # Static files
    location /static/ {
        alias /home/ubuntu/dcplant/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        
        # Ensure proper permissions
        location ~* \.(css|js|jpg|jpeg|gif|png|ico|svg|woff|woff2|ttf|eot)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # Media files
    location /media/ {
        alias /home/ubuntu/dcplant/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Test nginx configuration
    sudo nginx -t
    
    # Reload nginx
    sudo systemctl reload nginx
else
    echo "Warning: Nginx configuration not found. Please configure manually."
fi

# Restart Gunicorn if it's running
echo "8. Restarting Gunicorn..."
if systemctl is-active --quiet gunicorn; then
    sudo systemctl restart gunicorn
    echo "Gunicorn restarted."
else
    echo "Starting Gunicorn..."
    # Create systemd service if not exists
    sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<EOF
[Unit]
Description=gunicorn daemon for DCPlant
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/dcplant
ExecStart=/home/ubuntu/dcplant/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/home/ubuntu/dcplant/dcplant.sock \
          core.wsgi:application

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl start gunicorn
    sudo systemctl enable gunicorn
fi

# Update settings for production
echo "9. Checking production settings..."
cat > /home/ubuntu/dcplant/.env <<EOF
DEBUG=False
SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
ALLOWED_HOSTS=3.234.238.120,localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
STATIC_ROOT=/home/ubuntu/dcplant/staticfiles
MEDIA_ROOT=/home/ubuntu/dcplant/media
EOF

# Run migrations
echo "10. Running migrations..."
python manage.py migrate

# Check status
echo ""
echo "=== Status Check ==="
echo "Static files directory:"
ls -la staticfiles/ | head -5

echo ""
echo "Nginx status:"
sudo systemctl status nginx --no-pager | head -5

echo ""
echo "Gunicorn status:"
sudo systemctl status gunicorn --no-pager | head -5

echo ""
echo "=== Fix Complete ==="
echo "Your site should now be accessible at: http://3.234.238.120"
echo ""
echo "If you still see issues:"
echo "1. Check nginx error logs: sudo tail -f /var/log/nginx/error.log"
echo "2. Check gunicorn logs: sudo journalctl -u gunicorn -f"
echo "3. Ensure firewall allows port 80: sudo ufw allow 80"