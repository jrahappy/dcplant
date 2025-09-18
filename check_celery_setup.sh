#!/bin/bash

echo "Checking Celery and Redis setup..."
echo "===================================="

# 1. Check Redis is running
echo "1. Redis Status:"
if systemctl is-active --quiet redis; then
    echo "✅ Redis is running"
    redis-cli ping
else
    echo "❌ Redis is NOT running!"
    echo "Starting Redis..."
    sudo systemctl start redis
    sudo systemctl enable redis
fi

# 2. Check if Celery is installed
echo ""
echo "2. Celery Installation:"
cd /home/ubuntu/projects/dcdentals
source /home/ubuntu/venvs/dcdentals/bin/activate
if pip show celery > /dev/null 2>&1; then
    echo "✅ Celery is installed"
    pip show celery | grep Version
else
    echo "❌ Celery not installed!"
    echo "Installing Celery..."
    pip install celery redis celery-progress
fi

# 3. Check if celery-progress is installed
echo ""
echo "3. Celery Progress:"
if pip show celery-progress > /dev/null 2>&1; then
    echo "✅ celery-progress is installed"
    pip show celery-progress | grep Version
else
    echo "❌ celery-progress not installed!"
    echo "Installing celery-progress..."
    pip install celery-progress
fi

# 4. Test Celery connection
echo ""
echo "4. Testing Celery Worker:"
# Start a test worker in background
celery -A core worker --loglevel=info --detach --pidfile=/tmp/celery_test.pid

sleep 3

# Check if worker started
if [ -f /tmp/celery_test.pid ]; then
    PID=$(cat /tmp/celery_test.pid)
    if ps -p $PID > /dev/null; then
        echo "✅ Celery worker started (PID: $PID)"

        # Test sending a task
        echo ""
        echo "5. Testing Task Execution:"
        python -c "
from core.celery import app
result = app.send_task('core.celery.debug_task')
print('Task sent:', result.id)
import time
time.sleep(2)
print('Task state:', result.state)
print('Task result:', result.get(timeout=5))
"

        # Stop test worker
        kill $PID
        rm /tmp/celery_test.pid
    else
        echo "❌ Celery worker failed to start"
    fi
else
    echo "❌ Could not start Celery worker"
fi

echo ""
echo "6. Current Celery Workers:"
celery -A core inspect active

echo ""
echo "===================================="
echo "Setup Check Complete!"
echo ""
echo "To start Celery permanently:"
echo "  sudo systemctl start celery"
echo "  sudo systemctl enable celery"
echo ""
echo "To monitor Celery:"
echo "  celery -A core events"
echo "  celery -A core flower  # Web UI (if flower is installed)"