import os, smtplib
from email.message import EmailMessage

def send_message_via_smtp(to_addr, user_email, subject, plain_body, html_body=None):
    msg = EmailMessage()
    msg["From"] = f"{os.getenv('SENDER_NAME','Whenever Home')} <{os.getenv('SENDER_EMAIL')}>"
    msg["To"] = to_addr
    msg["Reply-To"] = user_email
    msg["Subject"] = subject
    msg.set_content(plain_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1","true","yes")

    if use_tls:
        server = smtplib.SMTP(host, port, timeout=20)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(host, port, timeout=20)

    server.login(user, password)
    server.send_message(msg)
    server.quit()