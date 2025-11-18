#!/usr/bin/env python3
"""
Flask backend for sending PVA and Zoning requests via email using SMTP.

Changes:
- Adds a small contacts/email-save + verification flow (SQLite-backed) with:
  - POST /save_email  -> create pending email + send verification
  - GET  /confirm_email?token=... -> confirm the pending email
- Keeps existing /api/send-requests behavior.
- send_email_via_smtp now supports setting Reply-To.
"""
from flask import Flask, request, jsonify, redirect, make_response
import os
import logging
import json
import csv
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Dict
from jinja2 import Environment, FileSystemLoader
import sqlite3
from datetime import datetime
import secrets
import re

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
DB_PATH = os.path.join(BASE_DIR, "emails.db")

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


# -----------------------------------------------------------------------------
# Simple SQLite-backed emails/contacts helpers (minimal and local)
# -----------------------------------------------------------------------------
EMAILS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT NOT NULL UNIQUE,
    token TEXT,
    confirmed INTEGER DEFAULT 0,
    opt_in INTEGER DEFAULT 1,
    created_at TEXT,
    confirmed_at TEXT
);
"""

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def init_contacts_db(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(EMAILS_TABLE_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def add_pending_email(email: str, name: Optional[str], token: str, opt_in: bool = True, db_path: str = DB_PATH) -> bool:
    """Insert or update a pending email with token. Return True on insert/update."""
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # If email already exists and is confirmed, return False to indicate already confirmed
        cur.execute("SELECT confirmed FROM emails WHERE email = ?", (email,))
        row = cur.fetchone()
        if row:
            if row[0] == 1:
                return False  # already confirmed
            # update token and timestamp for unconfirmed
            cur.execute("UPDATE emails SET token = ?, name = ?, opt_in = ?, created_at = ? WHERE email = ?",
                        (token, name, 1 if opt_in else 0, now, email))
        else:
            cur.execute("INSERT INTO emails (name, email, token, confirmed, opt_in, created_at) VALUES (?, ?, ?, 0, ?, ?)",
                        (name, email, token, 1 if opt_in else 0, now))
        conn.commit()
        return True
    finally:
        conn.close()


def confirm_email(token: str, db_path: str = DB_PATH) -> Optional[Dict]:
    """Mark token as confirmed. Return the row dict when confirmed, else None."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, confirmed FROM emails WHERE token = ? LIMIT 1", (token,))
        row = cur.fetchone()
        if not row:
            return None
        if row[3] == 1:
            # already confirmed
            return {"id": row[0], "name": row[1], "email": row[2], "confirmed": True}
        now = datetime.utcnow().isoformat()
        cur.execute("UPDATE emails SET confirmed = 1, confirmed_at = ? WHERE id = ?", (now, row[0]))
        conn.commit()
        return {"id": row[0], "name": row[1], "email": row[2], "confirmed": True}
    finally:
        conn.close()


def email_exists(email: str, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM emails WHERE email = ? LIMIT 1", (email,))
        return cur.fetchone() is not None
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Email sending (SMTP) helper - extended to support Reply-To
# -----------------------------------------------------------------------------
def send_email_via_smtp(to_email: str, subject: str, body_text: str, reply_to: Optional[str] = None, html_body: Optional[str] = None) -> dict:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    from_addr = os.environ.get("SENDER_EMAIL")
    from_name = os.environ.get("SENDER_NAME")

    if not smtp_host or not smtp_user or not smtp_pass or not from_addr:
        logger.info("SMTP not fully configured; simulating send to %s", to_email)
        # In simulated mode include reply-to in headers for debugging
        headers = {}
        if reply_to:
            headers["Reply-To"] = reply_to
        return {"status_code": 250, "body": f"Simulated send to {to_email}", "headers": headers}

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject
    msg.set_content(body_text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

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


def build_verification_email(user_email: str, token: str) -> (str, str): # type: ignore
    app_base = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")
    confirm_url = f"{app_base}/confirm_email?token={token}"
    subject = "Confirm your email for Appraisal AutoPull"
    plain = (
        f"Hi,\n\n"
        f"Thanks for saving your contact info with Whenever Home. Click the link below to confirm your email address:\n\n"
        f"{confirm_url}\n\n"
        f"If the link doesn't work, copy and paste it into your browser.\n\n"
        f"Sent by {os.getenv('SENDER_NAME','Whenever Home')} on behalf of {user_email}\n"
    )
    html = f"""
    <html>
      <body>
        <p>Hi,</p>
        <p>Thanks for saving your contact info with Whenever Home. Click the button below to confirm your email address:</p>
        <p><a href="{confirm_url}" style="display:inline-block;padding:12px 20px;background:#1a73e8;color:#fff;border-radius:6px;text-decoration:none;">Yes — confirm my email</a></p>
        <p>If the button doesn't work, use this link:<br/><a href="{confirm_url}">{confirm_url}</a></p>
        <hr/>
        <small>Sent by {os.getenv('SENDER_NAME','Whenever Home')} on behalf of {user_email}. Reply-To is set to {user_email}.</small>
      </body>
    </html>
    """
    return subject, plain, html


# -----------------------------------------------------------------------------
# Routes: contact save + verify
# -----------------------------------------------------------------------------
@app.route("/save_email", methods=["POST"])
def save_email():
    """
    Accept JSON or form data with fields:
      - email (required)
      - name (optional)
      - opt_in (optional; true/false)
    Creates a token, stores pending record, sends verification email to the provided address.
    """
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip()
    name = (data.get("name") or "").strip() or None
    opt_in_raw = data.get("opt_in")
    opt_in = True
    if isinstance(opt_in_raw, str):
        opt_in = opt_in_raw.lower() in ("1", "true", "yes", "on")
    elif isinstance(opt_in_raw, bool):
        opt_in = opt_in_raw

    if not email:
        return jsonify({"success": False, "error": "Email is required."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"success": False, "error": "Invalid email format."}), 400

    # Generate a token and add a pending db record
    token = secrets.token_urlsafe(16)
    try:
        added = add_pending_email(email=email, name=name, token=token, opt_in=opt_in)
        if added is False:
            # Already confirmed
            return jsonify({"success": True, "message": "Email already confirmed."}), 200
    except Exception as e:
        logger.exception("Failed to save pending email: %s", e)
        return jsonify({"success": False, "error": "Server error saving email."}), 500

    # Build and send verification email
    try:
        subject, plain, html = build_verification_email(email, token)
        # Send verification to the user's email; Reply-To set to the user's email too (makes replies go back to them)
        send_result = send_email_via_smtp(to_email=email, subject=subject, body_text=plain, reply_to=email, html_body=html)
        logger.info("Verification send result: %s", send_result)
    except Exception as e:
        logger.exception("Failed to send verification email: %s", e)
        return jsonify({"success": False, "error": "Failed to send verification email."}), 500

    return jsonify({"success": True, "message": "Verification email sent. Check your inbox."}), 200


@app.route("/confirm_email", methods=["GET"])
def confirm_email_route():
    token = request.args.get("token", "").strip()
    if not token:
        return make_response("<h3>Invalid verification link</h3>", 400)

    try:
        row = confirm_email(token)
        if not row:
            return make_response("<h3>Invalid or expired token</h3>", 400)
    except Exception as e:
        logger.exception("Failed to confirm email: %s", e)
        return make_response("<h3>Server error while confirming</h3>", 500)

    # Friendly HTML response (simple)
    html = f"""
    <html>
      <head><title>Email confirmed</title></head>
      <body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
        <h2>Thanks — your email is confirmed</h2>
        <p>The address <strong>{row['email']}</strong> has been confirmed and saved. You can now use this contact when sending requests.</p>
        <p><a href="/">Return to the app</a></p>
      </body>
    </html>
    """
    return make_response(html, 200)


# -----------------------------------------------------------------------------
# Existing send-requests route (unchanged apart from using send_email_via_smtp signature)
# -----------------------------------------------------------------------------
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
                # When sending official requests, set Reply-To to the saved user (if provided in payload)
                reply_to = None
                if data.get("user_email"):
                    reply_to = data.get("user_email")
                results["pva"] = send_email_via_smtp(
                    to_email=pva_email,
                    subject=f"PVA request for {address}",
                    body_text=pva_body,
                    reply_to=reply_to
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
                reply_to = None
                if data.get("user_email"):
                    reply_to = data.get("user_email")
                results["zoning"] = send_email_via_smtp(
                    to_email=zoning_email,
                    subject=f"Zoning request for {address}",
                    body_text=zoning_body,
                    reply_to=reply_to
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


if __name__ == "__main__":
    csv_path = os.path.join(BASE_DIR, "mappings.csv")
    load_email_mappings_from_csv(csv_path)
    # Initialize contacts DB for /save_email
    init_contacts_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))