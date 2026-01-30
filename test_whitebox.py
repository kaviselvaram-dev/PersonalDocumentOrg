import pytest
from app import app
from utils import encrypt_bytes, decrypt_bytes, audit
from models import db, AuditLog

# ----------------------------------------------------------
# ✅ Flask app fixture for testing database and context
# ----------------------------------------------------------
@pytest.fixture
def test_app():
    """Creates a temporary Flask app context for white box testing."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"  # in-memory DB
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ==========================================================
# ✅ TEST 1 – ENCRYPTION / DECRYPTION ROUNDTRIP
# ==========================================================
def test_encrypt_decrypt_roundtrip():
    data = b"Confidential Data"
    nonce_b64, cipher_b64 = encrypt_bytes(data)
    decrypted = decrypt_bytes(nonce_b64, cipher_b64)
    assert decrypted == data, "Decrypted data does not match original input"


# ==========================================================
# ✅ TEST 2 – FILE TYPE VALIDATION
# ==========================================================
def test_allowed_file_types():
    from app import allowed
    assert allowed("test.pdf") is True
    assert allowed("image.png") is True
    assert allowed("malware.exe") is False


# ==========================================================
# ✅ TEST 3 – AUDIT LOG ENTRY CREATION
# ==========================================================
def test_audit_log(test_app):
    """Verifies that audit() correctly creates an entry in the database."""
    with test_app.app_context():
        user_id = 1
        audit(user_id, "upload", "test file upload")
        log = AuditLog.query.filter_by(user_id=user_id).first()
        assert log is not None
        assert log.action == "upload"
        assert log.detail == "test file upload"


# ==========================================================
# ✅ TEST 4 – ENCRYPTION RANDOMNESS CHECK
# ==========================================================
def test_unique_ciphertexts():
    data = b"same message"
    nonce1, cipher1 = encrypt_bytes(data)
    nonce2, cipher2 = encrypt_bytes(data)
    assert nonce1 != nonce2 or cipher1 != cipher2, \
        "Encryption must produce unique outputs for identical input data"
