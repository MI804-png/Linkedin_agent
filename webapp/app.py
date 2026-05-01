"""
LinkedIn Auto-Apply SaaS – Flask web application
Multi-user platform: users register, upload CV, fill profile,
then the bot applies to LinkedIn jobs automatically every day.
"""
from __future__ import annotations

import os
import uuid
import json
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet

# ─── App setup ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
USER_DATA_FOLDER = BASE_DIR / "user_data"
UPLOAD_FOLDER.mkdir(exist_ok=True)
USER_DATA_FOLDER.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

# Use PostgreSQL on Render (DATABASE_URL set automatically), else SQLite locally
_db_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
# Render sets postgres:// but SQLAlchemy needs postgresql://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB CV upload limit

db = SQLAlchemy(app)

# Fernet key for encrypting LinkedIn passwords at rest
_RAW_FERNET_KEY = os.environ.get("FERNET_KEY", "")
if _RAW_FERNET_KEY:
    _FERNET = Fernet(_RAW_FERNET_KEY.encode())
else:
    # Generate a new key on first start and persist it
    _KEY_FILE = BASE_DIR / ".fernet_key"
    if _KEY_FILE.exists():
        _FERNET = Fernet(_KEY_FILE.read_bytes().strip())
    else:
        _new_key = Fernet.generate_key()
        _KEY_FILE.write_bytes(_new_key)
        _KEY_FILE.chmod(0o600)
        _FERNET = Fernet(_new_key)


def encrypt(plaintext: str) -> str:
    return _FERNET.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _FERNET.decrypt(ciphertext.encode()).decode()


ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    profile = db.relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    runs = db.relationship("BotRun", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, pw: str) -> None:
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)


class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Personal info
    full_name = db.Column(db.String(256), default="")
    phone = db.Column(db.String(64), default="")
    location = db.Column(db.String(128), default="")
    graduation_year = db.Column(db.String(8), default="")
    experience_years = db.Column(db.String(8), default="")
    work_auth_answer = db.Column(db.Text, default="")
    salary_answer = db.Column(db.Text, default="")

    # Job search settings
    keywords = db.Column(db.Text, default="Software Developer")  # newline-separated
    search_locations = db.Column(db.Text, default="Hungary")     # newline-separated
    max_applications = db.Column(db.Integer, default=25)
    posted_days_ago = db.Column(db.Integer, default=7)

    # Bot schedule – 0/1 flag
    auto_apply_enabled = db.Column(db.Boolean, default=False)

    # LinkedIn credentials (encrypted at rest)
    linkedin_email = db.Column(db.String(256), default="")
    linkedin_password_enc = db.Column(db.Text, default="")  # Fernet-encrypted

    # CV file (path relative to UPLOAD_FOLDER)
    cv_filename = db.Column(db.String(256), default="")

    user = db.relationship("User", back_populates="profile")

    def set_linkedin_password(self, pw: str) -> None:
        self.linkedin_password_enc = encrypt(pw) if pw else ""

    def get_linkedin_password(self) -> str:
        return decrypt(self.linkedin_password_enc) if self.linkedin_password_enc else ""

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip() for k in self.keywords.splitlines() if k.strip()]

    @property
    def locations_list(self) -> list[str]:
        return [l.strip() for l in self.search_locations.splitlines() if l.strip()]

    @property
    def cv_path(self) -> Path | None:
        if self.cv_filename:
            return UPLOAD_FOLDER / self.cv_filename
        return None


class BotRun(db.Model):
    __tablename__ = "bot_runs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default="running")  # running/done/error
    submitted = db.Column(db.Integer, default=0)
    skipped = db.Column(db.Integer, default=0)
    failures = db.Column(db.Integer, default=0)
    log_snippet = db.Column(db.Text, default="")

    user = db.relationship("User", back_populates="runs")


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user() -> User | None:
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


# ─── Routes: Auth ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        pw2 = request.form.get("password2", "")

        if not email or not pw:
            flash("Email and password are required.", "danger")
            return render_template("register.html")
        if pw != pw2:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if len(pw) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        user = User(email=email)
        user.set_password(pw)
        db.session.add(user)
        db.session.flush()  # get user.id

        profile = UserProfile(user_id=user.id, linkedin_email=email)
        db.session.add(profile)
        db.session.commit()

        session["user_id"] = user.id
        flash("Account created! Now complete your profile.", "success")
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(pw):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ─── Routes: Dashboard ────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    runs = BotRun.query.filter_by(user_id=user.id).order_by(BotRun.started_at.desc()).limit(20).all()
    total_submitted = db.session.query(db.func.sum(BotRun.submitted)).filter_by(user_id=user.id).scalar() or 0
    return render_template("dashboard.html", user=user, runs=runs, total_submitted=total_submitted)


# ─── Routes: Profile / Settings ───────────────────────────────────────────────

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    p = user.profile

    if request.method == "POST":
        p.full_name = request.form.get("full_name", "").strip()
        p.phone = request.form.get("phone", "").strip()
        p.location = request.form.get("location", "").strip()
        p.graduation_year = request.form.get("graduation_year", "").strip()
        p.experience_years = request.form.get("experience_years", "").strip()
        p.work_auth_answer = request.form.get("work_auth_answer", "").strip()
        p.salary_answer = request.form.get("salary_answer", "").strip()
        p.keywords = request.form.get("keywords", "").strip()
        p.search_locations = request.form.get("search_locations", "").strip()
        try:
            p.max_applications = int(request.form.get("max_applications", 25))
        except ValueError:
            p.max_applications = 25
        try:
            p.posted_days_ago = int(request.form.get("posted_days_ago", 7))
        except ValueError:
            p.posted_days_ago = 7

        # LinkedIn credentials
        li_email = request.form.get("linkedin_email", "").strip()
        li_pw = request.form.get("linkedin_password", "")
        if li_email:
            p.linkedin_email = li_email
        if li_pw:
            p.set_linkedin_password(li_pw)

        p.auto_apply_enabled = bool(request.form.get("auto_apply_enabled"))

        # CV upload
        cv_file = request.files.get("cv_file")
        if cv_file and cv_file.filename and allowed_file(cv_file.filename):
            # Delete old file
            if p.cv_filename:
                old = UPLOAD_FOLDER / p.cv_filename
                if old.exists():
                    old.unlink()
            ext = secure_filename(cv_file.filename).rsplit(".", 1)[-1]
            new_name = f"{user.id}_{uuid.uuid4().hex}.{ext}"
            cv_file.save(UPLOAD_FOLDER / new_name)
            p.cv_filename = new_name

        db.session.commit()
        flash("Profile saved!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user, p=p)


@app.route("/cv/download")
@login_required
def cv_download():
    user = get_current_user()
    p = user.profile
    if not p.cv_filename:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, p.cv_filename, as_attachment=True, download_name="cv.pdf")


# ─── Routes: Manual run ───────────────────────────────────────────────────────

@app.route("/run", methods=["POST"])
@login_required
def run_now():
    user = get_current_user()
    p = user.profile

    if not p.linkedin_email or not p.linkedin_password_enc:
        flash("Please set your LinkedIn credentials first.", "warning")
        return redirect(url_for("profile"))
    if not p.cv_filename:
        flash("Please upload your CV first.", "warning")
        return redirect(url_for("profile"))

    # Enqueue / trigger bot run in background thread
    from bot_runner import run_for_user_async
    run_for_user_async(user.id)

    flash("Bot run started! Check the dashboard for progress.", "info")
    return redirect(url_for("dashboard"))


@app.route("/api/run_status/<int:run_id>")
@login_required
def run_status(run_id: int):
    user = get_current_user()
    run = db.session.get(BotRun, run_id)
    if not run or run.user_id != user.id:
        abort(404)
    return jsonify({
        "status": run.status,
        "submitted": run.submitted,
        "skipped": run.skipped,
        "failures": run.failures,
        "log": run.log_snippet[-2000:] if run.log_snippet else "",
    })


# ─── Entry point ──────────────────────────────────────────────────────────────

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


def create_tables() -> None:
    with app.app_context():
        db.create_all()


# Always initialise DB tables (works under gunicorn --preload and direct run)
create_tables()

# Start the daily scheduler (gunicorn or direct run)
from scheduler import start_scheduler as _start_scheduler
_start_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
