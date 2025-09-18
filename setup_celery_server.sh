#!/bin/bash

# Setup Celery and Redis on Ubuntu server for async file processing
echo "=========================================="
echo "Setting up Celery & Redis for Async Upload"
echo "=========================================="

# 1. Install Redis if not already installed
echo "📦 Installing Redis..."
sudo apt update
sudo apt install redis-server -y

# 2. Configure Redis
echo "⚙️ Configuring Redis..."
sudo sed -i 's/supervised no/supervised systemd/' /etc/redis/redis.conf
sudo systemctl restart redis
sudo systemctl enable redis
sudo systemctl status redis --no-pager | head -10

# 3. Test Redis connection
echo "🔍 Testing Redis connection..."
redis-cli ping
if [ $? -eq 0 ]; then
    echo "✅ Redis is running!"
else
    echo "❌ Redis connection failed!"
    exit 1
fi

# 4. Create Celery service file
echo "📝 Creating Celery service..."
sudo tee /etc/systemd/system/celery.service > /dev/null << 'EOF'
[Unit]
Description=Celery Service for DCDentals
After=network.target redis.service

[Service]
Type=forking
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/projects/dcdentals
EnvironmentFile=/home/ubuntu/venvs/dcdentals.env
Environment="DJANGO_SETTINGS_MODULE=core.settings"

# Celery configuration
ExecStart=/home/ubuntu/venvs/dcdentals/bin/celery \
    -A core multi start worker1 \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/log/celery/%n%I.log \
    --loglevel=info \
    --time-limit=3600 \
    --concurrency=4

ExecStop=/home/ubuntu/venvs/dcdentals/bin/celery \
    multi stopwait worker1 \
    --pidfile=/var/run/celery/%n.pid

ExecReload=/home/ubuntu/venvs/dcdentals/bin/celery \
    multi restart worker1 \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/log/celery/%n%I.log

# Create run and log directories
RuntimeDirectory=celery
RuntimeDirectoryMode=0755
LogsDirectory=celery
LogsDirectoryMode=0755

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 5. Create Celery Beat service (for scheduled tasks)
echo "📝 Creating Celery Beat service..."
sudo tee /etc/systemd/system/celerybeat.service > /dev/null << 'EOF'
[Unit]
Description=Celery Beat Service for DCDentals
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/projects/dcdentals
EnvironmentFile=/home/ubuntu/venvs/dcdentals.env
Environment="DJANGO_SETTINGS_MODULE=core.settings"

ExecStart=/home/ubuntu/venvs/dcdentals/bin/celery \
    -A core beat \
    --loglevel=info \
    --pidfile=/var/run/celery/celerybeat.pid \
    --schedule=/var/run/celery/celerybeat-schedule

RuntimeDirectory=celery
RuntimeDirectoryMode=0755

Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 6. Create directories for Celery
echo "📁 Creating Celery directories..."
sudo mkdir -p /var/log/celery
sudo mkdir -p /var/run/celery
sudo chown -R ubuntu:www-data /var/log/celery
sudo chown -R ubuntu:www-data /var/run/celery

# 7. Reload systemd and start services
echo "🚀 Starting Celery services..."
sudo systemctl daemon-reload
sudo systemctl enable celery
sudo systemctl enable celerybeat
sudo systemctl start celery
sudo systemctl start celerybeat

# 8. Check status
sleep 3
echo "📊 Service Status:"
echo "=================="
echo "Redis:"
sudo systemctl is-active redis
echo ""
echo "Celery:"
sudo systemctl status celery --no-pager | head -15
echo ""
echo "Celery Beat:"
sudo systemctl status celerybeat --no-pager | head -10

# 9. Test Celery
echo ""
echo "🧪 Testing Celery..."
cd /home/ubuntu/projects/dcdentals
source /home/ubuntu/venvs/dcdentals/bin/activate
python -c "from core.celery import app; result = app.send_task('core.celery.debug_task'); print('Task sent:', result.id)"

echo ""
echo "=========================================="
echo "✅ Celery Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Commands to manage services:"
echo "  sudo systemctl status celery"
echo "  sudo systemctl restart celery"
echo "  sudo journalctl -u celery -f"
echo ""
echo "📝 Log files:"
echo "  /var/log/celery/worker1.log"
echo ""
echo "🔍 Monitor Celery tasks:"
echo "  celery -A core inspect active"
echo "  celery -A core inspect stats"