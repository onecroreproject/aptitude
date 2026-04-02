import qrcode
import os
from django.core.mail import send_mail
from django.conf import settings
from io import BytesIO
from django.core.files.base import ContentFile
from .models import OTP

def send_otp_email(email, otp_code):
    subject = 'Your AptiPro Verification Code'
    message = f'Hi there! Your 6-digit verification code is: {otp_code}\n\nThis code will expire in 10 minutes.'
    email_from = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'webmaster@localhost'
    send_mail(subject, message, email_from, [email])

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue())
