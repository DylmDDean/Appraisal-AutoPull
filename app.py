#!/usr/bin/env python3
"""
Flask backend for sending PVA and Zoning requests via email using SMTP.

Changes in this version:
- Supports Grant County district-level zoning by city.
- Replaced SendGrid usage with an SMTP sender (smtplib).
- send_email_via_smtp reads SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS and SENDER_EMAIL/SENDER_NAME from env.
- If SMTP is not configured, the send is simulated (useful for local testing).
- Added email capture and verification feature with /save_email and /confirm_email endpoints.
"""
from flask import Flask, request, jsonify, redirect, send_from_directory
import os
import logging
import json
import csv
import smtplib
import ssl
import secrets
import re
from email.message import EmailMessage
from typing import Optional, Dict
from jinja2 import Environment, FileSystemLoader

# Import email verification modules
import emails_db
import email_sender

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# Jinja environment for plain text templates (no autoescape for plain text)
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=False
)

CITY_EMAIL_MAP: Dict[str, Dict[str, str]] = {
    "Springfield": {"pva": "pva@springfield.gov", "zoning": "zoning@springfield.gov"},
    "Metropolis": {"pva": "pva@metropolis.gov", "zoning": "zoning@metropolis.gov"},
}

# Grant County Zoning per City
GRANT_CITY_ZONING_MAP: Dict[str, str] = {
    "corinth": "", # TODO: insert real email if/when available
    "crittenden": "dmartin@cityofcrittendenky.gov",
    "dry ridge": "", # TODO: insert real email if/when available
    "williamstown": "cityofwtown@wtownky.org"
}

# Hard-locked county mapping
COUNTY_EMAIL_MAP: Dict[str, Dict[str, str]] = {
    "anderson": {
        "pva": "BStivers41@gmail.com",
        "zoning": "rachelle.lile@roadrunner.com"
    },
    "boone": {
        "pva": "pva@boonecountyky.org",
        "zoning": "plancom@boonecountyky.org"
    },
    "carroll": {
        "pva": "bethany.petry@ky.gov",
        "zoning": "brianmumphrey@carrolltonky.net"
    },
    "franklin": {
        "pva": "Angie.obanion@ky.gov",
        "zoning": "autumn.goderwis@franklincounty.ky.gov"
    },
    "gallatin": {
        "pva": "Sheryl.jones@ky.gov",
        "zoning": "jhansen@gallatinky.org"
    },
    "grant": {
        "pva": "Elliott.Anderson@ky.gov",
        # zoning falls to GRANT_CITY_ZONING_MAP
    },
    "kenton": {
        "pva": "info.kentonpva@kentoncounty.org",
        "zoning": "webmaster01@pdskc.org"   
    },
    "owen": {
        "pva": "blake.robertson@ky.gov",
        "zoning": ""   # TODO: insert real email if/when available
    },
    "scott": {
        "pva": "Tony.McDonald@ky.gov",
        "zoning": "rshirley@gscplanning.com"   
    },
    "trimble": {
        "pva": "JillM.Mahoney@ky.gov",
        "zoning": ""   # TODO: insert real email if/when available
    },
}

DEFAULT_EMAILS: Dict[str, str] = {
    "pva": os.environ.get("DEFAULT_PVA_EMAIL", "pva@example.com"),
    "zoning": os.environ.get("DEFAULT_ZONING_EMAIL", "zoning@example.com"),
}


def normalize_key(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return " ".join(s.strip().split()).lower()


def load_email_mappings_from_csv(csv_path: str) -> None:
    if not os.path.exists(csv_path):
        logger.info("CSV mapping file not found: %s", csv_path)
        return
    try:
        with open(csv_path, newline='', encoding='utf-8') as fh:
            reader = csv.reader(fh)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                typ = row[0].strip().lower()
                key = row[1].strip()
                pva = row[2].strip() if len(row) > 2 and row[2].strip() else None
                zoning = row[3].strip() if len(row) > 3 and row[3].strip() else None
                entry: Dict[str, str] = {}
                if pva:
                    entry["pva"] = pva
                if zoning:
                    entry["zoning"] = zoning
                if not entry:
                    continue
                if typ == "city":
                    CITY_EMAIL_MAP[key] = entry
                elif typ == "county":
                    COUNTY_EMAIL_MAP[key] = entry
    except Exception as e:
        logger.exception("Failed to load CSV mappings: %s", e)


def extract_city_from_address(address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-2]
    return None


def get_emails_for_location(city: Optional[str], county: Optional[str]) -> Dict[str, str]:
    """
    Lookup priority:
      - if Grant county: override zoning with city-specific zoning if possible
      - fallback to county
      - fallback to city
      - fallback to default
    """
    city_n = normalize_key(city)
    county_n = normalize_key(county)

    # 1. Special handling for Grant county zoning by city
    if county_n == "grant":
        emails = COUNTY_EMAIL_MAP.get("grant", {}).copy()
        if city_n and city_n in GRANT_CITY_ZONING_MAP and GRANT_CITY_ZONING_MAP[city_n]:
            emails["zoning"] = GRANT_CITY_ZONING_MAP[city_n]
        emails = {**DEFAULT_EMAILS, **emails}
        logger.info("(Grant) Zoning for city '%s': %s", city_n, emails.get("zoning"))
        return emails

    # 2) County lookup (hard-locked, precedence)
    if county_n:
        for k, v in COUNTY_EMAIL_MAP.items():
            if normalize_key(k) == county_n:
                logger.info("Using county-level mapping for '%s' -> %s", k, v)
                merged = {**DEFAULT_EMAILS, **v}
                return merged

    # 3) City lookup (only when no county mapping)
    if city_n:
        for k, v in CITY_EMAIL_MAP.items():
            if normalize_key(k) == city_n:
                logger.info("Using city-level mapping for '%s' -> %s", k, v)
                merged = {**DEFAULT_EMAILS, **v}
                return merged

    # 4) Fallback default
    logger.info("No mapping found for city=%s county=%s; using defaults", city, county)
    return DEFAULT_EMAILS.copy()


def render_template_file(filename: str, context: dict) -> str:
    tpl = env.get_template(filename)
    return tpl.render(**context)


def send_email_via_smtp(to_email: str, subject: str, body_text: str) -> dict:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    from_addr = os.environ.get("SENDER_EMAIL")
    from_name = os.environ.get("SENDER_NAME")

    if not smtp_host or not smtp_user or not smtp_pass or not from_addr:
        logger.info("SMTP not fully configured; simulating send to %s", to_email)
        return {"status_code": 250, "body": f"Simulated send to {to_email}", "headers": {}}

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    try:
        if smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
                smtp.login(smtp_user, smtp_pass)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(smtp_user, smtp_pass)
                smtp.send_message(msg)
        return {"status_code": 250, "body": "OK", "headers": {}}
    except Exception as e:
        logger.exception("SMTP send failed: %s", e)
        return {"error": str(e)}


@app.route("/api/send-requests", methods=["POST"])
def send_requests():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"success": False, "error": "Invalid JSON", "details": str(e)}), 400

    address = data.get("address")
    if not address:
        return jsonify({"success": False, "error": "Missing required field: address"}), 400

    city = data.get("city") or extract_city_from_address(address)
    county = data.get("county")  # optional; when present it will take precedence

    logger.info("Received send-requests for address=%s city=%s county=%s", address, city, county)

    emails = get_emails_for_location(city, county)
    pva_email = emails.get("pva")
    zoning_email = emails.get("zoning")

    send_to_pva = data.get("send_to_pva", True)
    send_to_zoning = data.get("send_to_zoning", True)

    template_context = {
        "address": address,
        "city": city,
        "county": county,
        "payload": data,
        "payload_json": json.dumps(data, indent=2)
    }

    try:
        pva_body = render_template_file("pva_email.txt", template_context)
        zoning_body = render_template_file("zoning_email.txt", template_context)
    except FileNotFoundError as e:
        logger.exception("Template missing")
        return jsonify({"success": False, "error": "Template missing", "details": str(e)}), 500
    except Exception as e:
        logger.exception("Template rendering error")
        return jsonify({"success": False, "error": "Template rendering error", "details": str(e)}), 500

    results = {}

    if send_to_pva:
        if not pva_email:
            results["pva"] = {"error": "No PVA recipient configured"}
        else:
            try:
                results["pva"] = send_email_via_smtp(
                    to_email=pva_email,
                    subject=f"PVA request for {address}",
                    body_text=pva_body
                )
            except Exception as e:
                logger.exception("Failed to send PVA email")
                results["pva"] = {"error": str(e)}
    else:
        results["pva"] = {"skipped": True}

    if send_to_zoning:
        if not zoning_email:
            results["zoning"] = {"error": "No Zoning recipient configured"}
        else:
            try:
                results["zoning"] = send_email_via_smtp(
                    to_email=zoning_email,
                    subject=f"Zoning request for {address}",
                    body_text=zoning_body
                )
            except Exception as e:
                logger.exception("Failed to send Zoning email")
                results["zoning"] = {"error": str(e)}
    else:
        results["zoning"] = {"skipped": True}

    success = (
        ("error" not in results.get("pva", {}) if send_to_pva else True) and
        ("error" not in results.get("zoning", {}) if send_to_zoning else True)
    )
    status_code = 200 if success else 500

    return jsonify({
        "success": success,
        "city": city,
        "county": county,
        "address": address,
        "emails_used": {"pva": pva_email, "zoning": zoning_email},
        "results": results
    }), status_code


# Simple email validation regex
EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def is_valid_email(email: str) -> bool:
    """Validate email format using a simple regex."""
    return EMAIL_REGEX.match(email) is not None


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files (JS, CSS, etc.)"""
    return send_from_directory('static', filename)


@app.route("/save_email", methods=["POST"])
def save_email():
    """
    Accept email from user, validate, generate verification token, and send verification email.
    
    Security notes:
    - TODO: Add rate limiting in production to prevent abuse (e.g., Flask-Limiter)
    - TODO: Add CAPTCHA for additional protection against bots
    - Uses centralized app SMTP credentials (no per-user SMTP storage in this phase)
    """
    # Accept both JSON and form data
    if request.is_json:
        data = request.get_json()
        email = data.get("email", "").strip()
    else:
        email = request.form.get("email", "").strip()
    
    # Validate email
    if not email:
        return jsonify({"success": False, "message": "Email address is required"}), 400
    
    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Invalid email format"}), 400
    
    # Check if email already exists
    if emails_db.email_exists(email):
        return jsonify({
            "success": False, 
            "message": "This email is already registered. Please check your inbox for the verification email."
        }), 400
    
    # Generate secure verification token
    token = secrets.token_urlsafe(32)
    
    # Add pending email to database
    if not emails_db.add_pending_email(email, token):
        return jsonify({
            "success": False,
            "message": "Unable to save email. Please try again."
        }), 500
    
    # Send verification email
    try:
        email_sender.send_verification(email, token)
        logger.info("Verification email sent to: %s", email)
        return jsonify({
            "success": True,
            "message": "Verification email sent! Please check your inbox."
        }), 200
    except ValueError as e:
        # SMTP not configured
        logger.error("SMTP configuration error: %s", e)
        return jsonify({
            "success": False,
            "message": "Email service is not configured. Please contact support."
        }), 500
    except Exception as e:
        # Other send failures
        logger.exception("Failed to send verification email: %s", e)
        return jsonify({
            "success": False,
            "message": "Failed to send verification email. Please try again later."
        }), 500


@app.route("/confirm_email", methods=["GET"])
def confirm_email():
    """
    Verify email using the token from the verification link.
    Marks the email as confirmed and shows a friendly success page.
    """
    token = request.args.get("token", "").strip()
    
    if not token:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Invalid Link</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #dc2626;">Invalid Verification Link</h1>
            <p>The verification link is missing required information.</p>
        </body>
        </html>
        """, 400
    
    # Attempt to confirm the email
    if emails_db.confirm_email(token):
        email_data = emails_db.get_email_by_token(token)
        email_address = email_data.get("email", "your email") if email_data else "your email"
        
        logger.info("Email confirmed: %s", email_address)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Email Verified!</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f9fafb;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #059669; }}
                .checkmark {{
                    font-size: 64px;
                    color: #059669;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="checkmark">✓</div>
                <h1>Email Verified!</h1>
                <p>Thank you for verifying your email address: <strong>{email_address}</strong></p>
                <p>You're all set!</p>
            </div>
        </body>
        </html>
        """, 200
    else:
        # Token not found or already confirmed
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Verification Failed</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f9fafb;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h1 { color: #dc2626; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Verification Failed</h1>
                <p>This verification link is invalid or has already been used.</p>
                <p>If you need a new verification email, please submit your email again.</p>
            </div>
        </body>
        </html>
        """, 400


if __name__ == "__main__":
    # Initialize email verification database
    emails_db.init_db()
    logger.info("Email verification database initialized")
    
    csv_path = os.path.join(BASE_DIR, "mappings.csv")
    load_email_mappings_from_csv(csv_path)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))