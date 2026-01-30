import os, io, uuid, base64
import qrcode
from flask import (
    Flask, request, jsonify, session, send_file,
    render_template, redirect, url_for, make_response
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps

from config import Config
from models import db, User, Document, Share
from utils import (
    encrypt_bytes, decrypt_bytes,
    save_file_bytes, read_file_bytes_as_b64,
    audit, send_email
)
# ==========================================================
# ⚙️ APP SETUP
# ==========================================================
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

print("📧 Loaded email config:")
print("SMTP_HOST =", os.getenv("SMTP_HOST"))
print("SMTP_USER =", os.getenv("SMTP_USER"))
print("FROM_EMAIL =", os.getenv("FROM_EMAIL"))

with app.app_context():
    db.create_all()

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.start()


# ==========================================================
# 🔒 HELPER FUNCTIONS
# ==========================================================
def allowed(filename):
    """Checks if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXT"]

def login_required(func):
    """Ensures routes require login."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        user = User.query.get(session["user_id"])
        if not user:
            return redirect(url_for("login_page"))
        return func(user, *args, **kwargs)
    return wrapper


# ==========================================================
# 🚪 AUTHENTICATION ROUTES
# ==========================================================
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or request.form
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already exists"}), 400

    user = User(email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "registered"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.form
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401

    session["user_id"] = user.id
    # ✅ Redirect user directly to /home after login
    return redirect(url_for("home_page"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login_page"))


# ==========================================================
# 📁 DOCUMENT MANAGEMENT ROUTES
# ==========================================================
@app.route("/upload", methods=["POST"])
@login_required
def upload(user):
    if "file" not in request.files:
        return jsonify({"error": "no file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "empty filename"}), 400

    if not allowed(file.filename):
        return jsonify({"error": "invalid file type"}), 400

    category = request.form.get("category", "General")
    expiry_str = request.form.get("expiry_date")
    reminder_str = request.form.get("reminder_at")

    reminder_at = None
    if reminder_str:
        try:
            local_time = datetime.fromisoformat(reminder_str)
            reminder_at = local_time.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception as e:
            print("⚠️ Could not parse reminder time:", e)

    raw = file.read()
    nonce_b64, cipher_b64 = encrypt_bytes(raw)
    stored_name = str(uuid.uuid4()) + ".bin"
    stored_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
    save_file_bytes(stored_path, cipher_b64)

    doc = Document(
        owner_id=user.id,
        filename=secure_filename(file.filename),
        stored_name=stored_name,
        category=category,
        expiry_date=datetime.fromisoformat(expiry_str).date() if expiry_str else None,
        reminder_at=reminder_at,
        nonce_b64=nonce_b64,
    )
    db.session.add(doc)
    db.session.commit()
    audit(user.id, "upload", f"Uploaded {doc.filename}")
    return redirect(url_for("documents_page"))


@app.route("/download/<int:doc_id>")
@login_required
def download(user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return "File not found", 404
    stored_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.stored_name)
    cipher_b64 = read_file_bytes_as_b64(stored_path)
    plaintext = decrypt_bytes(doc.nonce_b64, cipher_b64)
    return send_file(io.BytesIO(plaintext), as_attachment=True, download_name=doc.filename)


@app.route("/delete/<int:doc_id>")
@login_required
def delete_doc(user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc or doc.owner_id != user.id:
        return "Unauthorized or not found", 403
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for("documents_page"))


@app.route("/mydocs")
@login_required
def mydocs(user):
    docs = Document.query.filter_by(owner_id=user.id).all()
    return render_template("dashboard.html", docs=docs, user=user)


# ==========================================================
# ⏰ REMINDER FUNCTIONALITY
# ==========================================================
sent_reminders = set()

def check_reminders():
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=1)
    window_end = now + timedelta(minutes=1)
    due_docs = Document.query.filter(Document.reminder_at != None).all()

    for doc in due_docs:
        if doc.reminder_at and window_start <= doc.reminder_at <= window_end:
            unique_key = f"{doc.id}-{doc.reminder_at}"
            if unique_key in sent_reminders:
                continue
            owner = User.query.get(doc.owner_id)
            if owner:
                subject = f"Reminder: {doc.filename}"
                body = (
                    f"Hi {owner.email},\n\n"
                    f"Your document '{doc.filename}' is due soon.\n"
                    f"Expiry Date: {doc.expiry_date}\n\n"
                    f"Regards,\nFlyvia Docs"
                )
                success = send_email(owner.email, subject, body)
                if success:
                    sent_reminders.add(unique_key)
                    audit(owner.id, "reminder_sent", f"Reminder for {doc.filename}")

def run_reminder_job():
    with app.app_context():
        check_reminders()

if not scheduler.get_job("reminder_job"):
    scheduler.add_job(run_reminder_job, "interval", minutes=1, id="reminder_job", replace_existing=True)


# ==========================================================
# 🆕 MOBILE COMPANION + EXPORT SUMMARY ROUTES
# ==========================================================
@app.route("/generate_qr")
@login_required
def generate_qr(user):
    link = url_for("export_summary", _external=True)
    qr = qrcode.make(link)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return jsonify({"qr_image": f"data:image/png;base64,{qr_b64}", "link": link})


@app.route("/export_summary")
@login_required
def export_summary(user):
    docs = Document.query.filter_by(owner_id=user.id).all()
    if not docs:
        return "No documents to summarize.", 404

    summary = [
        f"Flyvia Docs — File Summary for {user.email}",
        f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]
    for doc in docs:
        summary.append(f"📄 {doc.filename}")
        summary.append(f"   • Category: {doc.category}")
        summary.append(f"   • Expiry: {doc.expiry_date or 'N/A'}")
        summary.append(f"   • Reminder: {doc.reminder_at or 'N/A'}")
        summary.append("")

    output = "\n".join(summary)
    response = make_response(output)
    response.headers["Content-Disposition"] = "attachment; filename=file_summary.txt"
    response.mimetype = "text/plain"
    return response


# ==========================================================
# 🖥 FRONTEND ROUTES
# ==========================================================
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("home_page"))
    return render_template("index.html")

@app.route("/login-page")
def login_page():
    return render_template("login.html")

@app.route("/signup-page")
def signup_page():
    return render_template("signup.html")

# 🏠 Home → Upload only
@app.route("/home")
@login_required
def home_page(user):
    return render_template("dashboard.html", docs=None, user=user)

# 📄 My Documents
@app.route("/documents")
@login_required
def documents_page(user):
    docs = Document.query.filter_by(owner_id=user.id).all()
    return render_template("dashboard.html", docs=docs, user=user)

# ⏰ Expiring Soon
@app.route("/expiring")
@login_required
def expiring_page(user):
    today = datetime.utcnow().date()
    docs = Document.query.filter(
        Document.owner_id == user.id,
        Document.expiry_date != None,
        Document.expiry_date <= today + timedelta(days=7)
    ).all()
    return render_template("dashboard.html", docs=docs, user=user)

# ⚙️ Settings
@app.route("/settings")
@login_required
def settings_page(user):
    return render_template("settings.html", user=user)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
