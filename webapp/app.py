"""
LinkedIn Auto-Apply SaaS – Flask web application
Multi-user platform: users register, upload CV, fill profile,
then the bot applies to LinkedIn jobs automatically every day.
"""
from __future__ import annotations

import io
import os
import uuid
import json
import re
import hashlib
import secrets
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

from sqlalchemy import text, inspect, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import MultipleResultsFound
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort, send_from_directory, send_file
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
app.config["TEMPLATES_AUTO_RELOAD"] = True
PROCESS_START_UTC = datetime.utcnow()

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
    api_token = db.Column(db.String(64), unique=True, nullable=True)

    def get_or_create_token(self) -> str:
        if not self.api_token:
            self.api_token = secrets.token_urlsafe(32)
        return self.api_token

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

    # Extended profile — screening questions
    nationality = db.Column(db.String(64), default="")
    is_eu_citizen = db.Column(db.Boolean, default=False)
    willing_to_relocate = db.Column(db.Boolean, default=False)
    willing_to_work_onsite = db.Column(db.Boolean, default=False)
    willing_to_work_remote = db.Column(db.Boolean, default=True)
    current_job_title = db.Column(db.String(128), default="")
    years_management_experience = db.Column(db.String(8), default="0")
    highest_education = db.Column(db.String(128), default="")
    field_of_study = db.Column(db.String(128), default="")
    english_proficiency = db.Column(db.String(64), default="Professional")
    languages_spoken = db.Column(db.Text, default="")
    has_drivers_license = db.Column(db.Boolean, default=False)
    drivers_license_category = db.Column(db.String(16), default="")
    linkedin_url = db.Column(db.String(256), default="")
    github_url = db.Column(db.String(256), default="")
    portfolio_url = db.Column(db.String(256), default="")
    gender = db.Column(db.String(32), default="")
    has_disability = db.Column(db.Boolean, default=False)
    veteran_status = db.Column(db.String(32), default="No")

    # Job search settings
    keywords = db.Column(db.Text, default="Software Developer")  # newline-separated
    search_locations = db.Column(db.Text, default="Hungary")     # comma/newline-separated
    workplace_type = db.Column(db.String(16), default="all")      # all/remote/hybrid/on_site
    max_applications = db.Column(db.Integer, default=25)
    posted_days_ago = db.Column(db.Integer, default=7)

    # Application type filter
    apply_type = db.Column(db.String(16), default="easy_apply")  # easy_apply / all / external_only

    # Bot schedule – 0/1 flag
    auto_apply_enabled = db.Column(db.Boolean, default=False)

    # LinkedIn credentials (encrypted at rest)
    linkedin_email = db.Column(db.String(256), default="")
    linkedin_password_enc = db.Column(db.Text, default="")  # Fernet-encrypted

    # CV file (path relative to UPLOAD_FOLDER)
    cv_filename = db.Column(db.String(256), default="")

    # Render-compatible scheduling (per-user)
    scheduled_run_hour = db.Column(db.Integer, default=8)      # Hour (0-23) to run daily
    scheduled_run_minute = db.Column(db.Integer, default=30)   # Minute (0-59)
    last_scheduled_run = db.Column(db.DateTime, nullable=True)  # Last time the scheduled bot ran
    send_missing_skills = db.Column(db.Boolean, default=True)  # Send missing skills report after run

    user = db.relationship("User", back_populates="profile")
    missing_skills_reports = db.relationship("MissingSkillsReport", back_populates="user_profile", cascade="all, delete-orphan")

    def set_linkedin_password(self, pw: str) -> None:
        self.linkedin_password_enc = encrypt(pw) if pw else ""

    def get_linkedin_password(self) -> str:
        return decrypt(self.linkedin_password_enc) if self.linkedin_password_enc else ""

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip() for k in self.keywords.splitlines() if k.strip()]

    @property
    def locations_list(self) -> list[str]:
        chunks = [c.strip() for c in re.split(r"[\n,;|]+", self.search_locations or "") if c.strip()]
        # Keep order while removing duplicates to avoid repeated searches.
        return list(dict.fromkeys(chunks))

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


class MissingSkillsReport(db.Model):
    """Tracks missing skills identified from job postings for a user."""
    __tablename__ = "missing_skills_reports"
    id = db.Column(db.Integer, primary_key=True)
    user_profile_id = db.Column(db.Integer, db.ForeignKey("user_profiles.id"), nullable=False)
    job_id = db.Column(db.String(256), default="")  # LinkedIn job ID
    job_title = db.Column(db.String(256), default="")
    company = db.Column(db.String(256), default="")
    job_url = db.Column(db.Text, default="")
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    missing_skills = db.Column(db.Text, default="")  # JSON list of skill strings
    confidence = db.Column(db.Float, default=0.0)  # 0.0-1.0, how confident the extraction is
    
    user_profile = db.relationship("UserProfile", back_populates="missing_skills_reports")

    def get_missing_skills(self) -> list[str]:
        """Parse JSON-encoded missing skills list."""
        if not self.missing_skills:
            return []
        try:
            return json.loads(self.missing_skills)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_missing_skills(self, skills: list[str]) -> None:
        """Store skills as JSON."""
        self.missing_skills = json.dumps([s.strip() for s in skills if s.strip()])


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if not get_current_user():
            session.clear()
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user() -> User | None:
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def ensure_user_profile(user: User) -> UserProfile:
    """Return existing profile or create one for legacy users."""
    if user is None:
        raise ValueError("User is required")
    try:
        profile = user.profile
    except MultipleResultsFound:
        profiles = UserProfile.query.filter_by(user_id=user.id).order_by(UserProfile.id.asc()).all()
        profile = profiles[0] if profiles else None
        for extra in profiles[1:]:
            db.session.delete(extra)
        db.session.commit()
    if profile is None:
        profile = UserProfile(user_id=user.id, linkedin_email=user.email)
        db.session.add(profile)
        db.session.commit()
    return profile


def ensure_api_token(user: User) -> str:
    """Return existing token or safely create one with retry on rare collisions/locks."""
    if user.api_token:
        return user.api_token

    for _ in range(3):
        user.api_token = secrets.token_urlsafe(32)
        try:
            db.session.commit()
            return user.api_token
        except IntegrityError:
            db.session.rollback()

    raise RuntimeError("Could not generate API token")


def _load_recent_job_events(user_id: int, limit: int = 100) -> tuple[list[dict], list[dict]]:
    """Load recent submitted/failed job events from the per-user job log."""
    jobs_file = USER_DATA_FOLDER / str(user_id) / "applied_jobs.json"
    archive_file = USER_DATA_FOLDER / str(user_id) / "failed_jobs_archive.json"

    raw: list[dict] = []

    if jobs_file.exists():
        try:
            current_raw = json.loads(jobs_file.read_text(encoding="utf-8"))
            if isinstance(current_raw, list):
                raw.extend(current_raw)
        except (json.JSONDecodeError, OSError):
            pass

    if archive_file.exists():
        try:
            archive_raw = json.loads(archive_file.read_text(encoding="utf-8"))
            if isinstance(archive_raw, list):
                raw.extend(archive_raw)
        except (json.JSONDecodeError, OSError):
            pass

    if not raw:
        return [], []

    submitted_jobs: list[dict] = []
    failed_jobs: list[dict] = []

    for entry in reversed(raw):
        if not isinstance(entry, dict):
            continue

        status = (entry.get("status") or "").strip().lower()
        if status not in {"submitted", "failed", "manual_required"}:
            continue

        ts = (entry.get("timestamp") or "").strip()
        time_display = ts
        if ts:
            try:
                parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_display = parsed.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        raw_report = entry.get("report") or {}
        record = {
            "time": time_display,
            "title": (entry.get("title") or "").strip() or f"Job {entry.get('job_id') or ''}".strip(),
            "company": (entry.get("company") or "").strip() or "-",
            "note": (entry.get("note") or "").strip() or "-",
            "job_url": (entry.get("job_url") or "").strip(),
            "job_id": (entry.get("job_id") or "").strip(),
            "status": status,
            "report": raw_report,
        }

        # Extract dedicated HR messaging status from the combined note field.
        note_text = record["note"]
        hr_sep = " | HR: "
        if hr_sep in note_text:
            details, hr_status = note_text.split(hr_sep, 1)
            record["note"] = details.strip() or "-"
            record["hr_message_status"] = hr_status.strip() or "-"
        else:
            record["hr_message_status"] = "-"

        if status == "submitted":
            submitted_jobs.append(record)
        else:
            failed_jobs.append(record)

        if len(submitted_jobs) >= limit and len(failed_jobs) >= limit:
            break

    return submitted_jobs[:limit], failed_jobs[:limit]


def _load_generated_letters(user_id: int, limit: int = 40) -> list[dict[str, str]]:
    """Load generated motivation/cover-letter files for dashboard download cards."""
    letters_dir = USER_DATA_FOLDER / str(user_id) / "generated_letters"
    if not letters_dir.exists():
        return []

    files: list[dict[str, str]] = []
    try:
        for p in sorted(letters_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_file():
                continue
            # Skip legacy plain-text files and placeholders
            if p.suffix.lower() == ".txt":
                try:
                    p.unlink()
                except Exception:
                    pass
                continue
            if p.stem.endswith("company__role") or p.name in ("company__role.pdf", "company__role.docx"):
                continue
            files.append(
                {
                    "name": p.name,
                    "size_kb": f"{max(1, int(round(p.stat().st_size / 1024)))} KB",
                    "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
            if len(files) >= limit:
                break
    except OSError:
        return []

    return files


def _derive_counts_from_log(log_text: str) -> tuple[int, int, int]:
    """Derive submitted/skipped/failed counters from run log lines."""
    if not log_text:
        return 0, 0, 0
    submitted = len(re.findall(r"\[SUBMITTED\]", log_text))
    skipped = len(re.findall(r"\[SKIPPED\]", log_text))
    failed = len(re.findall(r"\[FAILED\]", log_text))
    return submitted, skipped, failed


def token_required(f):
    """Decorator for extension API endpoints — authenticates via Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing token"}), 401
        token = auth[7:]
        user = User.query.filter_by(api_token=token).first()
        if not user:
            return jsonify({"error": "Invalid token"}), 401
        return f(user, *args, **kwargs)
    return decorated


# ─── Extension API ────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    """Extension login — returns an API token."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    token = ensure_api_token(user)
    return jsonify({"token": token, "user_id": user.id})


@app.route("/api/ext/status")
@token_required
def api_ext_status(user):
    """Return today's stats and schedule info for the extension popup."""
    from datetime import date
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_runs = BotRun.query.filter(
        BotRun.user_id == user.id,
        BotRun.started_at >= today_start
    ).all()
    today_submitted = sum(r.submitted for r in today_runs)
    total_runs = BotRun.query.filter_by(user_id=user.id).all()
    total_submitted = sum(r.submitted for r in total_runs)
    profile = ensure_user_profile(user)
    return jsonify({
        "today": today_submitted,
        "total": total_submitted,
        "auto_apply_enabled": profile.auto_apply_enabled if profile else False,
        "next_run": None
    })


@app.route("/api/ext/config")
@token_required
def api_ext_config(user):
    """Return user config for the extension to run the bot."""
    profile = ensure_user_profile(user)
    return jsonify({
        "full_name": profile.full_name,
        "phone": profile.phone,
        "location": profile.location,
        "graduation_year": profile.graduation_year,
        "experience_years": profile.experience_years,
        "salary_answer": profile.salary_answer,
        "work_auth_answer": profile.work_auth_answer,
        "keywords": profile.keywords_list,
        "locations": profile.locations_list,
        "workplace_type": profile.workplace_type or "all",
        "max_applications": profile.max_applications,
        "posted_days_ago": profile.posted_days_ago,
    })


@app.route("/api/ext/set_auto", methods=["POST"])
@token_required
def api_ext_set_auto(user):
    """Enable or disable daily auto-apply schedule."""
    data = request.get_json(silent=True) or {}
    profile = ensure_user_profile(user)
    profile.auto_apply_enabled = bool(data.get("enabled", False))
    db.session.commit()
    return jsonify({"ok": True, "auto_apply_enabled": profile.auto_apply_enabled})


@app.route("/api/ext/report_job", methods=["POST"])
@token_required
def api_ext_report_job(user):
    """Record a single job application from the extension."""
    data = request.get_json(silent=True) or {}
    # Find or create today's BotRun for this user
    from datetime import date
    today_start = datetime.combine(date.today(), datetime.min.time())
    run = BotRun.query.filter(
        BotRun.user_id == user.id,
        BotRun.started_at >= today_start,
        BotRun.status == "running"
    ).first()
    if not run:
        run = BotRun(user_id=user.id, status="running")
        db.session.add(run)
    if data.get("status") == "submitted":
        run.submitted += 1
    elif data.get("status") == "failed":
        run.failures += 1
    else:
        run.skipped += 1
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/ext/report_run", methods=["POST"])
@token_required
def api_ext_report_run(user):
    """Mark today's bot run as complete with final stats."""
    data = request.get_json(silent=True) or {}
    from datetime import date
    today_start = datetime.combine(date.today(), datetime.min.time())
    run = BotRun.query.filter(
        BotRun.user_id == user.id,
        BotRun.started_at >= today_start,
        BotRun.status == "running"
    ).first()
    if not run:
        run = BotRun(user_id=user.id)
        db.session.add(run)
    run.status = "done"
    run.finished_at = datetime.utcnow()
    run.submitted = data.get("submitted", run.submitted)
    run.skipped = data.get("skipped", run.skipped)
    run.failures = data.get("failures", run.failures)
    db.session.commit()
    return jsonify({"ok": True})


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


# ─── Routes: Bot app download ───────────────────────────────────────────────

@app.route("/download/bot")
@login_required
def download_bot():
    """Serve the packaged Windows bot executable as a ZIP."""
    zip_path = BASE_DIR.parent / "dist" / "LinkedInAutoApply.zip"
    if zip_path.exists():
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name="LinkedInAutoApply.zip",
        )
    abort(404)


# ─── Routes: Extension download ──────────────────────────────────────────────

@app.route("/download/extension")
@login_required
def download_extension():
    """Serve the packaged .crx extension for direct install."""
    crx_file = BASE_DIR / "static" / "linkedin_autoapply.crx"
    if crx_file.exists():
        return send_file(
            crx_file,
            mimetype="application/x-crx",
            as_attachment=True,
            download_name="linkedin_autoapply.crx",
        )
    
    # Fallback: serve as ZIP if .crx doesn't exist
    ext_dir = BASE_DIR.parent / "chrome_extension"
    if not ext_dir.exists():
        abort(404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in ext_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(ext_dir.parent))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="linkedin_autoapply_extension.zip",
    )


# ─── Routes: Dashboard ────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    try:
        p = ensure_user_profile(user)
        
        # Check if profile has minimum required data
        if not p.cv_filename:
            flash("Please upload your CV in Profile first.", "warning")
            return redirect(url_for("profile"))
        
        if not p.linkedin_email or not p.linkedin_password_enc:
            flash("Please add your LinkedIn credentials in Profile first.", "warning")
            return redirect(url_for("profile"))
        
        runs = BotRun.query.filter_by(user_id=user.id).order_by(BotRun.started_at.desc()).limit(20).all()
        try:
            from bot_runner import get_active_run_ids
            active_run_ids = get_active_run_ids()
        except Exception:
            active_run_ids = set()
        failed_runs = (
            BotRun.query
            .filter(BotRun.user_id == user.id, BotRun.failures > 0)
            .order_by(BotRun.started_at.desc())
            .limit(15)
            .all()
        )
        total_submitted = db.session.query(db.func.sum(BotRun.submitted)).filter_by(user_id=user.id).scalar() or 0
        total_failed = db.session.query(db.func.sum(BotRun.failures)).filter_by(user_id=user.id).scalar() or 0
        total_attempted = int(total_submitted) + int(total_failed)
        success_probability = round((float(total_submitted) / float(total_attempted)) * 100.0, 1) if total_attempted else 0.0
        failure_probability = round(100.0 - success_probability, 1) if total_attempted else 0.0

        recent_for_chart = list(reversed(runs[:10]))
        analytics_labels = [f"Run {r.id}" for r in recent_for_chart]
        analytics_submitted = [int(r.submitted or 0) for r in recent_for_chart]
        analytics_failed = [int(r.failures or 0) for r in recent_for_chart]

        application_stats = {
            "attempted": total_attempted,
            "submitted": int(total_submitted),
            "failed": int(total_failed),
            "success_probability": success_probability,
            "failure_probability": failure_probability,
            "labels": analytics_labels,
            "submitted_series": analytics_submitted,
            "failed_series": analytics_failed,
        }
        api_token = ensure_api_token(user)
        submitted_jobs, failed_jobs = _load_recent_job_events(user.id, limit=25)
        generated_letters = _load_generated_letters(user.id, limit=40)

        try:
            from bot_runner import get_network_follow_summary, get_networking_status
            network_follow = get_network_follow_summary(user.id, limit=200)
            networking_status = get_networking_status(user.id)
        except Exception:
            network_follow = {"total": 0, "items": []}
            networking_status = {"running": False, "action": "", "started_at": ""}
        
        # Load missing skills reports (top 20 most recent)
        try:
            missing_skills_reports = (
                MissingSkillsReport.query
                .filter_by(user_profile_id=p.id)
                .order_by(MissingSkillsReport.applied_at.desc())
                .limit(20)
                .all()
            )
        except:
            missing_skills_reports = []
        
        return render_template(
            "dashboard.html",
            user=user,
            p=p,
            runs=runs,
            active_run_ids=active_run_ids,
            total_submitted=total_submitted,
            api_token=api_token,
            submitted_jobs=submitted_jobs,
            failed_jobs=failed_jobs,
            failed_runs=failed_runs,
            generated_letters=generated_letters,
            missing_skills_reports=missing_skills_reports,
            network_follow=network_follow,
            networking_status=networking_status,
            application_stats=application_stats,
            is_render=bool(os.environ.get("RENDER")),
        )
    except Exception as e:
        app.logger.exception("Dashboard render failed for user_id=%s: %s", session.get("user_id"), str(e))
        flash(f"Dashboard error: {str(e)[:100]}. Please check your profile and try again.", "danger")
        return redirect(url_for("profile"))


# ─── Routes: Profile / Settings ───────────────────────────────────────────────

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    p = ensure_user_profile(user)

    if request.method == "POST":
        p.full_name = request.form.get("full_name", "").strip()
        p.phone = request.form.get("phone", "").strip()
        p.location = request.form.get("location", "").strip()
        p.graduation_year = request.form.get("graduation_year", "").strip()
        p.experience_years = request.form.get("experience_years", "").strip()
        p.work_auth_answer = request.form.get("work_auth_answer", "").strip()
        p.salary_answer = request.form.get("salary_answer", "").strip()

        # Extended profile fields
        p.nationality = request.form.get("nationality", "").strip()
        p.is_eu_citizen = bool(request.form.get("is_eu_citizen"))
        p.willing_to_relocate = bool(request.form.get("willing_to_relocate"))
        p.willing_to_work_onsite = bool(request.form.get("willing_to_work_onsite"))
        p.willing_to_work_remote = bool(request.form.get("willing_to_work_remote"))
        p.current_job_title = request.form.get("current_job_title", "").strip()
        p.years_management_experience = request.form.get("years_management_experience", "0").strip()
        p.highest_education = request.form.get("highest_education", "").strip()
        p.field_of_study = request.form.get("field_of_study", "").strip()
        p.english_proficiency = request.form.get("english_proficiency", "Professional").strip()
        p.languages_spoken = request.form.get("languages_spoken", "").strip()
        p.has_drivers_license = bool(request.form.get("has_drivers_license"))
        p.drivers_license_category = request.form.get("drivers_license_category", "").strip()
        p.linkedin_url = request.form.get("linkedin_url", "").strip()
        p.github_url = request.form.get("github_url", "").strip()
        p.portfolio_url = request.form.get("portfolio_url", "").strip()
        p.gender = request.form.get("gender", "").strip()
        p.has_disability = bool(request.form.get("has_disability"))
        p.veteran_status = request.form.get("veteran_status", "No").strip()
        p.keywords = request.form.get("keywords", "").strip()
        p.search_locations = request.form.get("search_locations", "").strip()
        workplace_type = (request.form.get("workplace_type", "all") or "all").strip().lower()
        p.workplace_type = workplace_type if workplace_type in {"all", "remote", "hybrid", "on_site"} else "all"
        apply_type = (request.form.get("apply_type", "easy_apply") or "easy_apply").strip().lower()
        p.apply_type = apply_type if apply_type in {"easy_apply", "all", "external_only"} else "easy_apply"
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
    p = ensure_user_profile(user)
    if not p.cv_filename:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, p.cv_filename, as_attachment=True, download_name="cv.pdf")


@app.get("/letters/download/<path:filename>")
@login_required
def download_generated_letter(filename: str):
    """Download a generated motivation/cover-letter file for the logged-in user."""
    if not filename or "/" in filename or "\\" in filename:
        abort(400)

    user = get_current_user()
    letters_dir = USER_DATA_FOLDER / str(user.id) / "generated_letters"
    if not letters_dir.exists():
        abort(404)

    return send_from_directory(letters_dir, filename, as_attachment=True, download_name=filename)


# ─── Routes: Manual run ───────────────────────────────────────────────────────

@app.get("/run")
@login_required
def run_now_info():
    flash("Use the Run Now button from Dashboard to start a run.", "info")
    return redirect(url_for("dashboard"))


@app.post("/run")
@login_required
def run_now():
    try:
        user = get_current_user()
        p = ensure_user_profile(user)
        watch_browser = (
            (request.form.get("watch_browser") or "").strip().lower() in {"1", "true", "yes", "on"}
            or (request.form.get("run_mode") or "").strip().lower() == "watch"
        )

        if not p.linkedin_email or not p.linkedin_password_enc:
            flash("Please set your LinkedIn credentials first.", "warning")
            return redirect(url_for("profile"))
        if not p.cv_filename:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("profile"))

        from bot_runner import run_for_user_async
        run_for_user_async(user.id, watch_browser=watch_browser)
        if watch_browser:
            if os.environ.get("RENDER"):
                flash("Run and Watch started in cloud mode. Live progress appears in the dashboard log (no desktop browser window on Render).", "info")
            else:
                flash("Bot run started in visible mode. A Chrome window should open on this machine.", "info")
        else:
            flash("Bot run started in background mode. Check the dashboard for progress.", "info")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        uid = session.get("user_id")
        app.logger.exception("Failed to start bot run for user_id=%s", uid)
        flash(f"Could not start bot run: {exc}", "danger")
        return redirect(url_for("dashboard"))


@app.post("/run_external_watch")
@login_required
def run_external_watch():
    try:
        user = get_current_user()
        p = ensure_user_profile(user)

        if not p.cv_filename:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("profile"))

        from bot_runner import run_direct_external_for_user_async
        ok, msg = run_direct_external_for_user_async(user.id, watch_browser=not bool(os.environ.get("RENDER")))
        if ok:
            if os.environ.get("RENDER"):
                flash("External job search started in cloud mode. The bot will browse WeWorkRemotely, RemoteOK, EuropeRemoteJobs, and Jobicy with live dashboard logs.", "info")
            else:
                flash("External job search started. A browser window will open and browse WeWorkRemotely, RemoteOK, EuropeRemoteJobs, and Jobicy.", "info")
        else:
            flash(f"Could not start external job search: {msg}", "warning")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        uid = session.get("user_id")
        app.logger.exception("Failed to start external watch run for user_id=%s", uid)
        flash(f"Could not start external websites watch run: {exc}", "danger")
        return redirect(url_for("dashboard"))


@app.post("/network_now")
@login_required
def network_now():
    """Follow top international companies on LinkedIn to grow connections."""
    try:
        user = get_current_user()
        p = ensure_user_profile(user)

        if not p.linkedin_email or not p.linkedin_password_enc:
            flash("Please set your LinkedIn credentials first.", "warning")
            return redirect(url_for("profile"))

        from bot_runner import run_networking_for_user_async
        started, message = run_networking_for_user_async(user.id, watch_browser=True)
        flash(message, "info" if started else "warning")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        app.logger.exception("Failed to start networking run for user_id=%s", session.get("user_id"))
        flash(f"Could not start networking campaign: {exc}", "danger")
        return redirect(url_for("dashboard"))


@app.post("/network_unfollow")
@login_required
def network_unfollow():
    """Start unfollow run for one tracked company or for all tracked companies."""
    try:
        user = get_current_user()
        p = ensure_user_profile(user)

        if not p.linkedin_email or not p.linkedin_password_enc:
            flash("Please set your LinkedIn credentials first.", "warning")
            return redirect(url_for("profile"))

        company = (request.form.get("company") or "").strip()

        from bot_runner import run_network_unfollow_for_user_async
        started, message = run_network_unfollow_for_user_async(
            user.id,
            company=company if company else None,
            watch_browser=True,
        )
        flash(message, "info" if started else "warning")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        app.logger.exception("Failed to start unfollow run for user_id=%s", session.get("user_id"))
        flash(f"Could not start unfollow: {exc}", "danger")
        return redirect(url_for("dashboard"))


@app.post("/retry_failures")
@login_required
def retry_failures():
    try:
        user = get_current_user()
        p = ensure_user_profile(user)

        if not p.linkedin_email or not p.linkedin_password_enc:
            flash("Please set your LinkedIn credentials first.", "warning")
            return redirect(url_for("profile"))
        if not p.cv_filename:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("profile"))

        from bot_runner import run_for_user_async_retry_failed
        run_for_user_async_retry_failed(user.id)
        flash("Retrying failed jobs — check the dashboard for progress.", "info")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        uid = session.get("user_id")
        app.logger.exception("Failed to start retry run for user_id=%s", uid)
        flash(f"Could not start retry run: {exc}", "danger")
        return redirect(url_for("dashboard"))


@app.post("/stop_run")
@login_required
def stop_run():
    """Signal the currently running bot to stop gracefully after the current job."""
    try:
        user = get_current_user()
        run = (
            BotRun.query
            .filter_by(user_id=user.id, status="running")
            .order_by(BotRun.started_at.desc())
            .first()
        )
        if not run:
            try:
                from bot_runner import is_run_active
                recent_runs = (
                    BotRun.query
                    .filter_by(user_id=user.id)
                    .order_by(BotRun.started_at.desc())
                    .limit(20)
                    .all()
                )
                run = next((r for r in recent_runs if is_run_active(r.id)), None)
            except Exception:
                run = None
        if run:
            from bot_runner import request_stop
            request_stop(run.id)
            # Only append the note once to avoid duplicates on repeated clicks
            note = "[User requested stop — will halt after current job]"
            if note not in (run.log_snippet or ""):
                run.log_snippet = ((run.log_snippet or "") + "\n" + note).strip()
                db.session.commit()
            flash("Stop signal sent — the bot will finish the current job and then halt.", "info")
        else:
            flash("No active run found.", "warning")
    except Exception as exc:
        app.logger.exception("Failed to stop run")
        flash(f"Could not stop run: {exc}", "danger")
    return redirect(url_for("dashboard"))


@app.post("/stop_run_now")
@login_required
def stop_run_now():
    """Force stop the currently running bot immediately (best effort)."""
    try:
        user = get_current_user()
        run = (
            BotRun.query
            .filter_by(user_id=user.id, status="running")
            .order_by(BotRun.started_at.desc())
            .first()
        )
        if not run:
            try:
                from bot_runner import is_run_active
                recent_runs = (
                    BotRun.query
                    .filter_by(user_id=user.id)
                    .order_by(BotRun.started_at.desc())
                    .limit(20)
                    .all()
                )
                run = next((r for r in recent_runs if is_run_active(r.id)), None)
            except Exception:
                run = None
        if run:
            from bot_runner import request_stop_now
            request_stop_now(run.id)
            run.status = "stopped"
            run.finished_at = datetime.utcnow()
            note = "[User requested FORCE STOP — immediate abort requested]"
            run.log_snippet = ((run.log_snippet or "") + "\n" + note).strip()
            db.session.commit()
            flash("Force stop sent — browser/context close requested immediately.", "warning")
        else:
            flash("No active run found.", "warning")
    except Exception as exc:
        app.logger.exception("Failed to force stop run")
        flash(f"Could not force stop run: {exc}", "danger")
    return redirect(url_for("dashboard"))


@app.route("/api/run_status/<int:run_id>")
@login_required
def run_status(run_id: int):
    user = get_current_user()
    run = db.session.get(BotRun, run_id)
    if not run or run.user_id != user.id:
        abort(404)

    # Self-heal stale "running" rows even if the app process was interrupted.
    # This keeps the dashboard from showing "Running..." forever.
    if run.status == "running" and run.started_at:
        # If this run started before the current Flask process, the worker thread
        # does not exist anymore (threads do not survive process restarts).
        if run.started_at < PROCESS_START_UTC - timedelta(seconds=5):
            run.status = "error"
            run.finished_at = datetime.utcnow()
            note = "Run interrupted by server restart; marked stale during status check."
            run.log_snippet = (run.log_snippet + "\n" + note).strip() if run.log_snippet else note
            db.session.commit()
        elif datetime.utcnow() - run.started_at > timedelta(hours=8):
            run.status = "error"
            run.finished_at = datetime.utcnow()
            note = "Run marked stale during status check (timeout exceeded)."
            run.log_snippet = (run.log_snippet + "\n" + note).strip() if run.log_snippet else note
            db.session.commit()

    # Backfill counters from log for older runs that were left at 0/0/0.
    if run.log_snippet:
        sub_cnt, skip_cnt, fail_cnt = _derive_counts_from_log(run.log_snippet)
        changed = False
        if sub_cnt > (run.submitted or 0):
            run.submitted = sub_cnt
            changed = True
        if skip_cnt > (run.skipped or 0):
            run.skipped = skip_cnt
            changed = True
        if fail_cnt > (run.failures or 0):
            run.failures = fail_cnt
            changed = True
        if changed:
            db.session.commit()

    submitted_jobs, _failed_jobs = _load_recent_job_events(user.id, limit=10)

    return jsonify({
        "status": run.status,
        "submitted": run.submitted,
        "skipped": run.skipped,
        "failures": run.failures,
        "log": run.log_snippet[-2000:] if run.log_snippet else "",
        "submitted_jobs": submitted_jobs,
    })


@app.route("/api/cron/check_scheduled_jobs", methods=["GET", "POST"])
def cron_check_scheduled_jobs():
    """
    Render-compatible cron endpoint: checks all users' scheduled run times and triggers bot runs.
    
    Can be called by:
    - Render Cron Job: https://your-render-url/api/cron/check_scheduled_jobs
    - External cron service: EasyCron, UpTimeRobot, etc.
    
    Secure with an API key in Authorization header:
    Authorization: Bearer YOUR_CRON_SECRET_KEY
    """
    # Simple auth: check for cron token in env or header
    cron_token = os.environ.get("CRON_SECRET_KEY", "default-insecure-key-change-me")
    auth_header = request.headers.get("Authorization", "")
    expected_auth = f"Bearer {cron_token}"
    
    if auth_header != expected_auth:
        return jsonify({"error": "Unauthorized"}), 401
    
    now = datetime.utcnow()
    current_hour = now.hour
    current_minute = now.minute
    
    # Find all users whose scheduled run time is now (within the minute)
    triggered_count = 0
    try:
        profiles = UserProfile.query.filter_by(auto_apply_enabled=True).all()
        for profile in profiles:
            # Check if scheduled time matches current time
            if (profile.scheduled_run_hour == current_hour and 
                profile.scheduled_run_minute == current_minute):
                # Check if we haven't already run in the last hour (to avoid duplicate runs)
                if profile.last_scheduled_run:
                    time_since_last = now - profile.last_scheduled_run
                    if time_since_last < timedelta(hours=1):
                        continue
                
                # Trigger bot run for this user
                try:
                    from bot_runner import run_for_user_async
                    run_id = run_for_user_async(profile.user_id)
                    profile.last_scheduled_run = now
                    db.session.commit()
                    triggered_count += 1
                    app.logger.info(f"Cron: Triggered bot run for user_id={profile.user_id}, run_id={run_id}")
                except Exception as e:
                    app.logger.warning(f"Cron: Failed to trigger bot for user_id={profile.user_id}: {e}")
    except Exception as e:
        app.logger.exception("Cron job failed")
        return jsonify({"error": str(e), "triggered": triggered_count}), 500
    
    return jsonify({"status": "ok", "triggered_runs": triggered_count}), 200


# ─── Entry point ──────────────────────────────────────────────────────────────

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


def create_tables() -> None:
    with app.app_context():
        db.create_all()


def ensure_schema_updates() -> None:
    """Apply tiny schema updates for existing installations."""
    with app.app_context():
        try:
            dialect = db.engine.dialect.name
            inspector = inspect(db.engine)
            if "users" not in inspector.get_table_names():
                return

            table_names = set(inspector.get_table_names())

            col_names = {c["name"] for c in inspector.get_columns("users")}

            if "api_token" not in col_names:
                if dialect == "sqlite":
                    db.session.execute(text("ALTER TABLE users ADD COLUMN api_token VARCHAR(64)"))
                elif dialect == "postgresql":
                    db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS api_token VARCHAR(64)"))
                else:
                    return
                db.session.commit()

            if dialect == "sqlite":
                db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_api_token ON users(api_token)"))
                db.session.commit()
            elif dialect == "postgresql":
                db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_api_token ON users(api_token)"))
                db.session.commit()

            if "user_profiles" in table_names:
                profile_cols = {c["name"] for c in inspector.get_columns("user_profiles")}
                if "workplace_type" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN workplace_type VARCHAR(16) DEFAULT 'all'"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS workplace_type VARCHAR(16) DEFAULT 'all'"))
                    db.session.commit()

                db.session.execute(text("UPDATE user_profiles SET workplace_type='all' WHERE workplace_type IS NULL OR workplace_type=''"))
                db.session.commit()

                # Add scheduler fields for Render-compatible scheduling
                if "scheduled_run_hour" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN scheduled_run_hour INTEGER DEFAULT 8"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS scheduled_run_hour INTEGER DEFAULT 8"))
                    db.session.commit()

                if "scheduled_run_minute" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN scheduled_run_minute INTEGER DEFAULT 30"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS scheduled_run_minute INTEGER DEFAULT 30"))
                    db.session.commit()

                if "last_scheduled_run" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN last_scheduled_run DATETIME"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS last_scheduled_run DATETIME"))
                    db.session.commit()

                if "send_missing_skills" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN send_missing_skills BOOLEAN DEFAULT 1"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS send_missing_skills BOOLEAN DEFAULT TRUE"))
                    db.session.commit()

                if "apply_type" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN apply_type VARCHAR(16) DEFAULT 'easy_apply'"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS apply_type VARCHAR(16) DEFAULT 'easy_apply'"))
                    db.session.commit()

            # Ensure MissingSkillsReport table exists (created by create_all if missing)
            if "missing_skills_reports" not in table_names:
                db.create_all()

        except Exception as e:
            app.logger.warning(f"Schema migration failed (may already exist): {e}")


def cleanup_stale_runs() -> None:
    """Mark interrupted running rows as error after server restarts/crashes."""
    with app.app_context():
        try:
            # Any running row started before this process boot is stale because
            # worker threads from previous process instances are gone.
            restart_cutoff = PROCESS_START_UTC - timedelta(seconds=5)
            timeout_cutoff = datetime.utcnow() - timedelta(hours=8)
            stale = BotRun.query.filter(
                BotRun.status == "running",
                or_(BotRun.started_at < restart_cutoff, BotRun.started_at < timeout_cutoff),
            ).all()
            if not stale:
                return
            for run in stale:
                if run.log_snippet:
                    sub_cnt, skip_cnt, fail_cnt = _derive_counts_from_log(run.log_snippet)
                    run.submitted = max(run.submitted or 0, sub_cnt)
                    run.skipped = max(run.skipped or 0, skip_cnt)
                    run.failures = max(run.failures or 0, fail_cnt)
                run.status = "error"
                run.finished_at = datetime.utcnow()
                note = "Run marked stale after process restart/interruption."
                run.log_snippet = (run.log_snippet + "\n" + note).strip() if run.log_snippet else note
            db.session.commit()
        except Exception as exc:
            app.logger.warning("Stale run cleanup skipped: %s", exc)


# Always initialise DB tables (works under gunicorn --preload and direct run)
create_tables()
ensure_schema_updates()
cleanup_stale_runs()

# Start the daily scheduler (gunicorn or direct run)
from scheduler import start_scheduler as _start_scheduler
_start_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
