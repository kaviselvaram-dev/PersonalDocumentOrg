import os
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import datetime
from config import Config
from models import db, AuditLog


# --- Encryption setup ---
if not Config.ENCRYPTION_KEY_B64:
    raise RuntimeError("ENCRYPTION_KEY not set in .env — generate one using base64 key generator")

ENCRYPTION_KEY = base64.b64decode(Config.ENCRYPTION_KEY_B64)


# ==========================================================
# 🔐 ENCRYPTION / DECRYPTION
# ==========================================================
def encrypt_bytes(data: bytes):
    """Encrypt file bytes using AES-GCM (256-bit)."""
    aesgcm = AESGCM(ENCRYPTION_KEY)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return base64.b64encode(nonce).decode(), base64.b64encode(ciphertext).decode()


def decrypt_bytes(nonce_b64: str, cipher_b64: str) -> bytes:
    """Decrypt file bytes using AES-GCM."""
    aesgcm = AESGCM(ENCRYPTION_KEY)
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(cipher_b64)
    return aesgcm.decrypt(nonce, ciphertext, None)


# ==========================================================
# 💾 FILE OPERATIONS
# ==========================================================
def save_file_bytes(stored_path: str, cipher_b64: str):
    """Save encrypted base64 data to disk."""
    with open(stored_path, "wb") as f:
        f.write(base64.b64decode(cipher_b64))


def read_file_bytes_as_b64(stored_path: str) -> str:
    """Read file as base64 string."""
    with open(stored_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ==========================================================
# 🧾 AUDIT LOGGING
# ==========================================================
def audit(user_id: int, action: str, detail: str = ""):
    """Log user actions (uploads, downloads, reminders, etc)."""
    entry = AuditLog(user_id=user_id, action=action, detail=detail, timestamp=datetime.utcnow())
    db.session.add(entry)
    db.session.commit()


# ==========================================================
# 📧 EMAIL SENDING (UTF-8 SAFE)
# ==========================================================
def send_email(to_email, subject, body):
    """
    Sends an email using Gmail SMTP with UTF-8 support.
    Requires .env setup with SMTP credentials.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    print(f"📨 Attempting SMTP => host={smtp_host} user={smtp_user} port={smtp_port}")

    try:
        # Create UTF-8 safe message
        msg = MIMEMultipart()
        msg["From"] = formataddr(("Flyvia Docs", from_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect and send
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f"✅ Email successfully sent to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Email send failed to {to_email}: {e}")
        return False
