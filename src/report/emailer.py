"""Sends the report via SMTP with the PDF attached."""
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src import config


def send_report_email(subject: str, body_text: str, pdf_path: Path) -> None:
    host = config.require(config.SMTP_HOST, "SMTP_HOST")
    user = config.require(config.SMTP_USER, "SMTP_USER")
    password = config.require(config.SMTP_PASS, "SMTP_PASS")
    sender = config.require(config.EMAIL_FROM, "EMAIL_FROM")
    recipient = config.require(config.EMAIL_TO, "EMAIL_TO")

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body_text, "plain"))

    with open(pdf_path, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="pdf")
        attachment.add_header(
            "Content-Disposition", "attachment", filename=pdf_path.name
        )
        msg.attach(attachment)

    with smtplib.SMTP(host, config.SMTP_PORT) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(sender, [recipient], msg.as_string())
