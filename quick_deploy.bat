@echo off
echo Deploying S3 fixes to server...

REM Copy updated files to server
echo Copying views.py...
scp cases/views.py ubuntu@dc:/home/ubuntu/projects/dcdentals/cases/

echo Copying urls.py...
scp cases/urls.py ubuntu@dc:/home/ubuntu/projects/dcdentals/cases/

echo Copying image_upload_brite.html...
scp templates/cases/image_upload_brite.html ubuntu@dc:/home/ubuntu/projects/dcdentals/templates/cases/

echo Restarting Gunicorn on server...
ssh ubuntu@dc "sudo systemctl restart gunicorn && sudo systemctl status gunicorn --no-pager | head -10"

echo.
echo Deployment complete!
echo.
echo Test the following:
echo 1. Upload the Korean filename file (임대석.zip)
echo 2. Upload a large file (200MB+)
echo.
pause