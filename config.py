import os

MAIL_USER = os.environ.get("MAIL_USER")        # your Gmail address (or SendGrid username)
MAIL_PASS = os.environ.get("MAIL_PASS")        # Gmail App Password or SendGrid API key
FLASK_SECRET = os.environ.get("FLASK_SECRET", "dev-secret-change-me")

OTP_LENGTH = int(os.environ.get("OTP_LENGTH", 6))
OTP_EXPIRY_SECONDS = int(os.environ.get("OTP_EXPIRY_SECONDS", 300))   # 5 minutes
OTP_RESEND_COOLDOWN = int(os.environ.get("OTP_RESEND_COOLDOWN", 30))  # seconds between resends
OTP_PEPPER = os.environ.get("OTP_PEPPER", "change_this_pepper")       # extra secret for hashing
