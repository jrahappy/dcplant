#!/usr/bin/env python
"""
Test email script for DCPlant
Sends a test email to verify email configuration
"""

import os
import sys
import django
from datetime import datetime

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def send_test_email():
    """Send a test email to william@integdental.com"""
    
    recipient = 'william@integdental.com'
    subject = f'DCPlant Test Email - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    
    message = f"""
Hello William,

This is a test email from the DCPlant system to verify that email configuration is working correctly.

Test Details:
- Date/Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- Email Backend: {settings.EMAIL_BACKEND}
- Email Host: {settings.EMAIL_HOST}
- Email Port: {settings.EMAIL_PORT}
- Use TLS: {settings.EMAIL_USE_TLS}
- From Email: {settings.DEFAULT_FROM_EMAIL}

If you receive this email, your email configuration is working properly!

Best regards,
DCPlant System
    """
    
    html_message = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #a2e436;">DCPlant Test Email</h2>
    <p>Hello William,</p>
    <p>This is a test email from the <strong>DCPlant system</strong> to verify that email configuration is working correctly.</p>
    
    <h3>Test Details:</h3>
    <ul>
        <li><strong>Date/Time:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</li>
        <li><strong>Email Backend:</strong> {settings.EMAIL_BACKEND}</li>
        <li><strong>Email Host:</strong> {settings.EMAIL_HOST}</li>
        <li><strong>Email Port:</strong> {settings.EMAIL_PORT}</li>
        <li><strong>Use TLS:</strong> {settings.EMAIL_USE_TLS}</li>
        <li><strong>From Email:</strong> {settings.DEFAULT_FROM_EMAIL}</li>
    </ul>
    
    <p style="color: green; font-weight: bold;">✓ If you receive this email, your email configuration is working properly!</p>
    
    <hr style="border: 1px solid #a2e436;">
    <p style="color: #666; font-size: 12px;">
        Best regards,<br>
        DCPlant System<br>
        <em>Dental Case & Patient Management Platform</em>
    </p>
</body>
</html>
    """
    
    try:
        print(f"Attempting to send test email to {recipient}...")
        print(f"Using email backend: {settings.EMAIL_BACKEND}")
        print(f"From: {settings.DEFAULT_FROM_EMAIL}")
        print(f"Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
        
        if result:
            print(f"\nSUCCESS: Test email sent successfully to {recipient}")
            print(f"Email sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"\nFAILED: Email was not sent")
            
    except Exception as e:
        print(f"\nERROR: Failed to send email")
        print(f"Error details: {str(e)}")
        print("\nPlease check your .env file has the following settings:")
        print("- EMAIL_BACKEND (e.g., 'django.core.mail.backends.smtp.EmailBackend')")
        print("- EMAIL_HOST (e.g., 'smtp.gmail.com')")
        print("- EMAIL_PORT (e.g., 587)")
        print("- EMAIL_USE_TLS (e.g., True)")
        print("- EMAIL_HOST_USER (your email address)")
        print("- EMAIL_HOST_PASSWORD (your email password or app password)")
        print("- DEFAULT_FROM_EMAIL (sender email address)")

if __name__ == '__main__':
    send_test_email()