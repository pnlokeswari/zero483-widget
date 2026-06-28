import os
import re
import imaplib
import smtplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# Credentials
IMAP_HOST = os.getenv("IMAP_HOST", "imap.secureserver.net")
SMTP_HOST = os.getenv("SMTP_HOST", "smtpout.secureserver.net")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
USER_EMAIL = os.getenv("SMTP_USER")
USER_PASS = os.getenv("SMTP_PASS")

SUBSCRIBERS_FILE = "subscribers.txt"

WELCOME_SUBJECT = "Welcome to the Zero483 Regulatory Digest!"
WELCOME_HTML = """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #2563eb;">Welcome to Zero483!</h2>
    <p>Thank you for subscribing to the Zero483 Regulatory Digest.</p>
    <p>Every week, you'll receive a curated summary of the most important FDA regulatory alerts, warning letters, and drug shortages, written specifically for healthcare and pharma professionals.</p>
    <p>Our goal is to keep you inspection-ready and informed.</p>
    <p>Stay tuned for your first digest arriving this Friday!</p>
    <br>
    <p>Best regards,<br>The Zero483 Team</p>
</body>
</html>
"""

def get_current_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if "@" in line)

def append_subscriber(new_email):
    with open(SUBSCRIBERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{new_email}")
    print(f"Added {new_email} to {SUBSCRIBERS_FILE}")

def send_email(to_email, subject, html_content):
    if not USER_EMAIL or not USER_PASS:
        return
        
    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = f"Zero483 <{USER_EMAIL}>"
    msg['To'] = to_email
    
    part = MIMEText(html_content, "html")
    msg.attach(part)
    
    try:
        server = smtplib.SMTP(SMTP_HOST, 587)
        server.starttls()
        server.login(USER_EMAIL, USER_PASS)
        server.sendmail(USER_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"Sent welcome email to {to_email}")
    except Exception as e:
        print(f"Failed to send welcome email to {to_email}: {e}")

def send_welcome_email(recipient_email):
    send_email(recipient_email, WELCOME_SUBJECT, WELCOME_HTML)

def check_for_new_subscribers():
    if not USER_EMAIL or not USER_PASS:
        print("Skipping IMAP sync: Credentials not set.")
        return
        
    print(f"Connecting to IMAP at {IMAP_HOST}...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(USER_EMAIL, USER_PASS)
        mail.select("inbox")
        
        # Search for unread emails from formspree
        status, messages = mail.search(None, 'UNSEEN', 'FROM', '"noreply@formspree.io"')
        
        if status != "OK":
            print("Failed to search inbox.")
            return
            
        email_ids = messages[0].split()
        if not email_ids:
            print("No new Formspree submissions found.")
            mail.logout()
            return
            
        print(f"Found {len(email_ids)} new submission(s). Processing...")
        
        current_subscribers = get_current_subscribers()
        
        for e_id in email_ids:
            status, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extract body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                try:
                                    body += part.get_payload(decode=True).decode()
                                except:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode()
                        except:
                            pass
                            
                    # Find email address in body. Formspree format usually "email: user@domain.com"
                    # We'll use a regex to grab the email
                    match = re.search(r"email:\s*([\w\.-]+@[\w\.-]+\.\w+)", body, re.IGNORECASE)
                    if not match:
                        # Fallback: just find any email that isn't the sender or user
                        emails_found = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", body)
                        for em in emails_found:
                            em_lower = em.lower()
                            if "formspree" not in em_lower and em_lower != USER_EMAIL.lower():
                                match_email = em_lower
                                break
                        else:
                            match_email = None
                    else:
                        match_email = match.group(1).lower()
                        
                    if match_email:
                        print(f"Extracted email: {match_email}")
                        if match_email not in current_subscribers:
                            append_subscriber(match_email)
                            current_subscribers.add(match_email)
                            send_welcome_email(match_email)
                        else:
                            print(f"{match_email} is already subscribed. Skipping welcome email.")
                    else:
                        print("Could not extract subscriber email from this message.")
                        
            # The email is automatically marked as SEEN when fetched via RFC822
            # but we can explicitly set it just in case
            mail.store(e_id, '+FLAGS', '\\Seen')
            
        mail.logout()
        print("IMAP Sync Complete.")
        
    except Exception as e:
        print(f"IMAP Error: {e}")

if __name__ == "__main__":
    check_for_new_subscribers()
