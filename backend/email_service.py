import smtplib #Its a Library for sending emails through email servers
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

def send_feedback_email(name: str, email: str, category: str, subject: str, message: str):

    """
    Send feedback email to hawaall.assistant@gmail.com AND send auto-reply to user

    """
    try:
        #Email configuration
        sender_email = os.getenv("SENDER_EMAIL", "hawaall.assistant@gmail.com")
        sender_password = os.getenv("SENDER_PASSWORD")
        recipient_email = "hawaall.assistant@gmail.com"
        
        if not sender_password:
            error_msg = "Email password not configured - SENDER_PASSWORD environment variable is missing"
            logging.error(error_msg)
            raise Exception(error_msg) # stops the function and reports the error
        
        #Connect to Gmail SMTP server once
        logging.info("Connecting to Gmail SMTP server...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password) #signs into the email account
        
        # 1.Send feedback to team
        team_msg = create_team_notification(sender_email, recipient_email, name, email, category, subject, message)
        server.sendmail(sender_email, recipient_email, team_msg.as_string()) #sends the emai
        logging.info(f"Team notification sent for feedback from {email}")
        
        #Small delay to avoid rate limiting
        time.sleep(1)
        
        #2. Send auto-reply to user
        user_msg = create_user_auto_reply(sender_email, email, name, category, subject)
        server.sendmail(sender_email, email, user_msg.as_string())
        logging.info(f"Auto-reply sent to {email}")
        
        #Close connection
        server.quit()
        
        logging.info(f"Both emails sent successfully for feedback from {email}")
        return True
        
    except Exception as e:
        error_details = str(e)
        logging.error(f"Failed to send feedback emails: {error_details}")
        
        # Log specific error types
        if "Authentication failed" in error_details:
            logging.error("Gmail authentication failed - check SENDER_PASSWORD is correct app password")
        elif "SENDER_PASSWORD" in error_details:
            logging.error("Environment variable SENDER_PASSWORD is not set")
        
        raise e

def create_team_notification(sender_email: str, recipient_email: str, name: str, user_email: str, category: str, subject: str, message: str):
    """Create the notification email for the team"""
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"Haawall Feedback - {category.title()}: {subject}"
    
    body = f"""
New feedback received from Haawall contact form:

Name: {name}
Email: {user_email}
Category: {category.title()}
Subject: {subject}

Message:
{message}

---
Submitted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source: Haawall Contact Form
Auto-reply sent: Yes
    """
    
    msg.attach(MIMEText(body, 'plain'))
    return msg

def create_user_auto_reply(sender_email: str, user_email: str, name: str, category: str, subject: str):
    """Create the auto-reply email for the user"""
    msg = MIMEMultipart()
    msg['From'] = f"Haawall Assistant <{sender_email}>"
    msg['To'] = user_email
    msg['Subject'] = f"✅ Thank you for your feedback - {subject}"
    msg['Reply-To'] = sender_email
    
    #headers to prevent it from being marked as spam
    msg['X-Mailer'] = "Haawall University Assistant"
    msg['X-Priority'] = "3"
    
    #both English and Kurdish versions
    body = f"""
Dear {name},

✅ CONFIRMATION: Your message has been received successfully!

Thank you for contacting Haawall University Assistant! We have received your {category.lower()} regarding "{subject}".

Your feedback is valuable to us, and our development team will review it carefully. We appreciate you taking the time to help us improve Haawall.


---

 {name}بەڕێز ،
پشتڕاستکردنەوە: پەیامەکەتان بە سەرکەوتووی گەیەندرا 

سوپاس بۆ پەیوەندیکردنتان لەگەڵ یارمەتیدەری زانکۆ  { category.lower() }ەکەتانمان وەرگرتووە سەبارەت بە  "{subject}"

فیدباکەکەتان بۆ ئێمە بەنرخە، و تیمی گەشەپێدانمان بە وردی پێداچوونەوەی بۆ دەکات. پێزانینمان لەوەی کاتتان تەرخان کردووە بۆ یارمەتیدانمان لە باشترکردنی هاوەڵ.



---

Best regards,
Haawall Development Team
College of Engineering, University of Sulaimani
📧 {sender_email}

,بە ڕێزەوە
تیمی گەشەپێدانی هاواڵ
کۆلێژی ئەندازیاری، زانکۆی سلێمانی
📧 {sender_email}

---
⚠️  ALERT: This is an automated response. Please do not reply to this email.
⚠️  ئاگاداری: ئەمە وەڵامێکی خۆکارە. تکایە وەڵامی ئەم ئیمەیلە مەدەنەوە

🕒 Sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    msg.attach(MIMEText(body, 'plain'))
    return msg