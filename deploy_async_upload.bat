@echo off
echo ==========================================
echo Deploying Async Upload with Celery
echo ==========================================
echo.

REM Copy updated files
echo Copying updated files...
scp templates/cases/image_upload_brite.html ubuntu@dc:/home/ubuntu/projects/dcdentals/templates/cases/
scp cases/views.py ubuntu@dc:/home/ubuntu/projects/dcdentals/cases/
scp cases/tasks.py ubuntu@dc:/home/ubuntu/projects/dcdentals/cases/
scp core/celery.py ubuntu@dc:/home/ubuntu/projects/dcdentals/core/

echo.
echo Setting up Celery on server...
scp setup_celery_server.sh ubuntu@dc:/tmp/
ssh ubuntu@dc "chmod +x /tmp/setup_celery_server.sh && /tmp/setup_celery_server.sh"

echo.
echo Restarting services...
ssh ubuntu@dc "sudo systemctl restart gunicorn && sudo systemctl restart celery && sudo systemctl status celery --no-pager | head -10"

echo.
echo ==========================================
echo Deployment Complete!
echo ==========================================
echo.
echo The system will now:
echo - Use async upload for 100+ files automatically
echo - Process uploads in background with Celery
echo - Show real-time progress
echo - Prevent 502 timeouts
echo.
echo Test with your 700 files upload!
pause