@echo off
echo Fixing progress bar updates...

REM Copy updated files
scp cases/views.py ubuntu@dc:/home/ubuntu/projects/dcdentals/cases/
scp templates/cases/image_upload_brite.html ubuntu@dc:/home/ubuntu/projects/dcdentals/templates/cases/

REM Restart services
ssh ubuntu@dc "sudo systemctl restart gunicorn && sudo systemctl restart celery"

echo.
echo Fixed! Progress bar should now update properly.
echo.
echo Make sure Redis and Celery are running:
ssh ubuntu@dc "sudo systemctl status redis --no-pager | head -5 && echo '' && sudo systemctl status celery --no-pager | head -10"

pause