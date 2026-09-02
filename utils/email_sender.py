import smtplib
import csv
import os
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from utils.logger import log_info, log_success, log_error, log_warning

RECIPIENTS_FILE = Path(__file__).resolve().parent.parent / "helper_files" / "recipients.csv"

def send_email(doc_path):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_APP_PASSWORD")
    
    if not sender or not password:
        log_error("Email credentials not found in environment variables.")
        return
        
    recipients = []
    with RECIPIENTS_FILE.open('r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            recipients.append(row['Email'])
            
    if not recipients:
        log_warning("No recipients found in recipients.csv")
        return

    msg = EmailMessage()
    msg['Subject'] = f"UTSA Digital Tools Release Notes - {datetime.now().strftime('%B %d, %Y')}"
    msg['From'] = sender
    msg['To'] = ", ".join(recipients)
    
    if doc_path:
        msg.set_content("Hello,\n\nPlease find attached the latest release notes for our digital tools.\n\nBest regards,\nAutomated System")
        with open(doc_path, 'rb') as f:
            file_data = f.read()
            file_name = os.path.basename(doc_path)
        msg.add_attachment(file_data, maintype='application', subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename=file_name)
    else:
        msg.set_content("Hello,\n\nThere were no new release notes for the digital tools this week.\n\nBest regards,\nAutomated System")

    try:
        log_info("Connecting to SMTP server...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        log_success(f"Email sent successfully to {len(recipients)} recipient(s).")
    except Exception as e:
        log_error(f"Failed to send email: {e}")