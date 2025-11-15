#!/usr/bin/env python3
"""
Flask backend for sending PVA and Zoning requests via email using SMTP.

Changes in this version:
- Replaced SendGrid usage with an SMTP sender (smtplib).
- send_email_via_smtp reads SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS and SENDER_EMAIL/SENDER_NAME from env.
- If SMTP is not configured, the send is simulated (useful for local testing).
- County-level mapping remains hard-locked (Carroll -> bethany.petry@ky.gov / brianmumphrey@carrolltonky.net).
"""
from flask import Flask, request, jsonify
import os
import logging
import json
import csv
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Dict
from jinja2 import Environment, FileSystemLoader

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

# In-memory default mappings (can be loaded/overridden with CSV)
CITY_EMAIL_MAP: Dict[str, Dict[str, str]] = {
    "Springfield": {"pva": "pva@springfield.gov", "zoning": "zoning@springfield.gov"},
    "Metropolis": {"pva": "pva@metropolis.gov", "zoning": "zoning@metropolis.gov"},
}

# Hard-locked county mapping: Carroll county -> fixed PVA and Zoning addresses
COUNTY_EMAIL_MAP: Dict[str, Dict[str, str]] = {
    "Carroll": {
        "pva": "bethany.petry@ky.gov",
        "zoning": "brianmumphrey@carrolltonky.net"
    },
}

DEFAULT_EMAILS: Dict[str, str] = {
    "pva": os.environ.get("DEFAULT_PVA_EMAIL", "pva@example.com"),
    "zoning": os.environ.get("DEFAULT_ZONING_EMAIL", "zoning@example.com"),
}


def normalize_key(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    # collapse whitespace and lowercase for stable comparisons
    return " ".join(s.strip().split()).lower()


def load_email_mappings_from_csv(csv_path: str) -> None:
    """
    Load mappings from a CSV file with columns:
      type,key,pva_email,zoning_email
    type: city or county
    This will merge into CITY_EMAIL_MAP and COUNTY_EMAIL_MAP.
    """
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
    """
    Heuristic: split on commas and assume the city is the second-to-last component
    in a typical "street, city, state zip" format.
    """
    if not address:
        return None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-2]
    return None


def get_emails_for_location(city: Optional[str], county: Optional[str]) -> Dict[str, str]:
    """
    Lookup priority: county -> city -> DEFAULT_EMAILS.
    County mappings are hard-locked: if a county entry exists it will always be used.
    """
    city_n = normalize_key(city)
    county_n = normalize_key(county)

    # 1) County lookup (hard-locked, precedence)
    if county_n:
        for k, v in COUNTY_EMAIL_MAP.items():
            if normalize_key(k) == county_n:
                logger.info("Using county-level mapping for '%s' -> %s", k, v)
                # merge with defaults so missing roles fall back
                merged = {**DEFAULT_EMAILS, **v}
                return merged

    # 2) City lookup (only when no county mapping)
    if city_n:
        for k, v in CITY_EMAIL_MAP.items():
            if normalize_key(k) == city_n:
                logger.info("Using city-level mapping for '%s' -> %s", k, v)
                merged = {**DEFAULT_EMAILS, **v}
                return merged

    # 3) Fallback default
    logger.info("No mapping found for city=%s county=%s; using defaults", city, county)
    return DEFAULT_EMAILS.copy()


def render_template_file(filename: str, context: dict) -> str:
    tpl = env.get_template(filename)
    return tpl.render(**context)


def send_email_via_smtp(to_email: str, subject: str, body_text: str) -> dict:
    """
    Send email via SMTP using environment variables:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SENDER_EMAIL, SENDER_NAME

    If SMTP is not configured, a simulated success response is returned for local testing.
    """
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
    """
    Expected JSON:
    {
      "address": "123 Main St, Springfield, IL 62701",
      "city": "Springfield",   # optional; if not provided we try to parse from address
      "county": "Sangamon",    # optional; used as hard-locked override if present
      "property_id": "ABC123", # optional
      ...
    }
    """
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

    # Build template context
    template_context = {
        "address": address,
        "city": city,
        "county": county,
        "payload": data,
        "payload_json": json.dumps(data, indent=2)
    }

    # Render templates
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
    # Send to PVA
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

    # Send to Zoning
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

    success = ("error" not in results.get("pva", {})) and ("error" not in results.get("zoning", {}))
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
    # Optional: load CSV mappings if you keep a mappings.csv in the project root
    csv_path = os.path.join(BASE_DIR, "mappings.csv")
    load_email_mappings_from_csv(csv_path)
    # For local dev only. Use a proper WSGI server (gunicorn/uvicorn) in production.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))