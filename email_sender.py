#!/usr/bin/env python3
"""
Email sender module for sending verification emails via SMTP.
Uses centralized SMTP credentials from environment variables.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional


def send_verification(email: str, token: str) -> None:
    """
    Send a verification email with a confirmation link.
    
    Args:
        email: Recipient email address
        token: Verification token to include in the link
        
    Raises:
        ValueError: If required environment variables are missing
        Exception: If SMTP send fails
    """
    # Read SMTP configuration from environment
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    sender_email = os.environ.get("SENDER_EMAIL")
    app_base_url = os.environ.get("APP_BASE_URL", "http://localhost:5000")
    
    # Validate required configuration
    if not smtp_host or not smtp_user or not smtp_pass or not sender_email:
        raise ValueError(
            "Missing required SMTP configuration. Please set SMTP_HOST, SMTP_USER, "
            "SMTP_PASS, and SENDER_EMAIL environment variables."
        )
    
    # Build verification link
    verification_link = f"{app_base_url.rstrip('/')}/confirm_email?token={token}"
    
    # Create email message
    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = email
    msg["Subject"] = "Verify Your Email Address"
    
    # Plain text version
    text_body = f"""
Hello!

Thank you for sharing your email address with us!

To complete your email verification, please click the link below:

{verification_link}

If you didn't request this verification, you can safely ignore this email.

Best regards,
The Team
    """.strip()
    
    # HTML version with a nice button
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #2563eb;">Verify Your Email Address</h2>
    
    <p>Hello!</p>
    
    <p>Thank you for sharing your email address with us!</p>
    
    <p>To complete your email verification, please click the button below:</p>
    
    <p style="text-align: center; margin: 30px 0;">
        <a href="{verification_link}" 
           style="background-color: #2563eb; color: white; padding: 12px 24px; 
                  text-decoration: none; border-radius: 6px; display: inline-block;
                  font-weight: bold;">
            Verify My Email
        </a>
    </p>
    
    <p style="color: #666; font-size: 14px;">
        Or copy and paste this link into your browser:<br>
        <a href="{verification_link}" style="color: #2563eb; word-break: break-all;">{verification_link}</a>
    </p>
    
    <p style="color: #999; font-size: 12px; margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;">
        If you didn't request this verification, you can safely ignore this email.
    </p>
</body>
</html>
    """.strip()
    
    # Set both plain text and HTML content
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype='html')
    
    # Send the email via SMTP
    try:
        if smtp_port == 465 or smtp_use_tls:
            # Use SMTP_SSL for port 465
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=20) as smtp:
                smtp.login(smtp_user, smtp_pass)
                smtp.send_message(msg)
        else:
            # Use STARTTLS for other ports
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(smtp_user, smtp_pass)
                smtp.send_message(msg)
    except smtplib.SMTPException as e:
        raise Exception(f"Failed to send verification email via SMTP: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error sending verification email: {str(e)}")
