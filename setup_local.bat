@echo off
echo Setting up local development environment...

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements-dev.txt

echo.
echo Setup complete! 
echo To activate the environment, run: activate.bat
echo Then navigate to backend folder: cd backend
echo Run migrations: python manage.py migrate
echo Create superuser: python manage.py createsuperuser
echo Start server: python manage.py runserver