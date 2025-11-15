#!/usr/bin/env python3
"""
Verbose SMTP test for Titan/Hostinger.
- Loads .env if present.
- Shows which env vars are set (masked password).
- Attempts SMTP_SSL using SMTP_HOST/SMTP_PORT.
- If that fails, will optionally try STARTTLS on port 587 and print full exceptions.
"""
import os
import ssl
import smtplib
import traceback
from email.message import EmailMessage

# Try to load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env via python-dotenv (if present).")
except Exception:
    print("python-dotenv not installed or load failed (this is okay if you set env vars another way).")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.titan.email")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
FROM = os.environ.get("SENDER_EMAIL", SMTP_USER)
TO = os.environ.get("TEST_TO", SMTP_USER)

def is_test_domain(email):
    # Checks if the email is an example/test domain
    test_domains = {"example.com", "example.org", "example.net"}
    if not email or "@" not in email:
        return True
    domain = email.lower().split("@")[-1]
    return domain in test_domains

# Safety check
if is_test_domain(TO):
    print("ERROR: The recipient email (TO) cannot be a test or documentation domain like example.com, example.net, or example.org.")
    print("Please set the TEST_TO environment variable or .env entry to a real, valid email address.")
    raise SystemExit(1)

def mask(s):
    if not s:
        return None
    if len(s) <= 4:
        return "****"
    return s[:1] + "****" + s[-1:]

print(f"SMTP_HOST = {SMTP_HOST}")
print(f"SMTP_PORT = {SMTP_PORT}")
print(f"SMTP_USER = {SMTP_USER}")
print(f"SMTP_PASS set = {bool(SMTP_PASS)} (masked: {mask(SMTP_PASS)})")
print(f"FROM = {FROM}")
print(f"TO = {TO}")
print("")

if not SMTP_USER or not SMTP_PASS:
    print("ERROR: SMTP_USER and/or SMTP_PASS are not set. Set them in your .env or in the shell, then re-run.")
    raise SystemExit(1)

msg = EmailMessage()
msg["From"] = FROM
msg["To"] = TO
msg["Subject"] = "SMTP verbose test"
msg.set_content("This is a verbose SMTP test message.")

def try_ssl(host, port, user, passwd):
    print(f"Trying SMTP_SSL to {host}:{port} ...")
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as s:
            s.login(user, passwd)
            s.send_message(msg)
        print("SUCCESS: Sent message using SMTP_SSL.")
        return True
    except Exception as e:
        print("SMTP_SSL attempt failed. Exception:")
        traceback.print_exc()
        return False

def try_starttls(host, port, user, passwd):
    print(f"Trying STARTTLS to {host}:{port} ...")
    try:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            s.login(user, passwd)
            s.send_message(msg)
        print("SUCCESS: Sent message using STARTTLS.")
        return True
    except Exception as e:
        print("STARTTLS attempt failed. Exception:")
        traceback.print_exc()
        return False

# First try the configured port (likely 465)
ok = try_ssl(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)

# If that failed and port is not 587, try STARTTLS on 587 (common fallback)
if not ok and SMTP_PORT != 587:
    print("\nAttempting STARTTLS on port 587 as a fallback...")
    ok = try_starttls(SMTP_HOST, 587, SMTP_USER, SMTP_PASS)

if not ok:
    print("\nFinal status: FAILED to send via SMTP.")
    print("Common causes:")
    print("- Wrong username/password (verify by logging into Titan/Hostinger webmail).")
    print("- Outbound SMTP port blocked on your network (try another network or server).")
    print("- Account not active or needs additional setup in Hostinger hPanel.")
    print("- Host/port mismatch (confirm with Hostinger Email Client configuration page).")
    print("\nPlease copy & paste the full traceback above here and I will help diagnose further.")
else:
    print("\nTest completed successfully. Check the recipient inbox and Sent folder in Titan webmail.")