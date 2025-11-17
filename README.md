# Appraisal AutoPull

Flask backend for sending PVA and Zoning requests via email using SMTP, with email capture and verification feature.

## Environment Variables

Create a `.env` file to define email variables:

```bash
# SMTP / email settings for Hostinger (Titan)
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=

# Mail sender info used by the Flask app
SENDER_EMAIL=
SENDER_NAME=

# Optional: address to receive test emails from smtp_test.py
TEST_TO=

# Required for email verification feature
SMTP_USE_TLS=true
APP_BASE_URL=http://localhost:5000
```

## Email Verification Feature

This application includes a simple email capture and verification feature that:
- Collects user emails with a child-friendly UI
- Sends verification emails using centralized SMTP credentials
- Stores verified emails in a SQLite database
- Uses secure token generation for verification links

### Setup
1. Set the required environment variables (listed above)
2. Run the Flask app: `python app.py`
3. The email database (`emails.db`) will be created automatically

### Security Notes
- The app uses centralized SMTP credentials (not per-user credentials)
- Rate limiting should be added in production (see comments in `app.py`)
- CAPTCHA recommended for production deployment
- All verification tokens are generated using `secrets.token_urlsafe()`

### Phase 2 Enhancements (Future)
- OAuth-based email verification
- Per-user SMTP credentials (advanced users)
- Rate limiting integration
- CAPTCHA integration

