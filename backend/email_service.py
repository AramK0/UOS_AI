import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

def send_feedback_email(name: str, email: str, category: str, subject: str, message: str):
    """
    Send feedback email to hawaall.assistant@gmail.com
    """
    try:
        # Email configuration
        sender_email = os.getenv("SENDER_EMAIL", "hawaall.assistant@gmail.com")
        sender_password = os.getenv("SENDER_PASSWORD")
        recipient_email = "hawaall.assistant@gmail.com"
        
        if not sender_password:
            raise Exception("Email password not configured")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Haawall Feedback - {category.title()}: {subject}"
        
        # Email body
        body = f"""
New feedback received from Haawall contact form:

Name: {name}
Email: {email}
Category: {category.title()}
Subject: {subject}

Message:
{message}

---
Submitted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source: Haawall Contact Form
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Gmail SMTP configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logging.info(f"Feedback email sent successfully from {email}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send feedback email: {str(e)}")
        raise e