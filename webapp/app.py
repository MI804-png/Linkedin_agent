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
from types import SimpleNamespace
from urllib.parse import urlparse

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
STUDY_GUIDES_FOLDER = BASE_DIR.parent / "linkedin_bot" / "study_guides"
SHARED_APPLIED_LOG = BASE_DIR.parent / "linkedin_bot" / "applied_jobs.json"
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

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+()0-9\s-]{7,32}$")
LANGUAGE_ENTRY_RE = re.compile(
    r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' /-]*(?:\s*(?:\([^)]+\)|[:\-]\s*[^,;\n]+))?$"
)
COMPANY_INPUT_RE = re.compile(r"^[A-Za-z0-9À-ÿ&.,'()\-+/ ]{1,120}$")

PROFILE_ALLOWED_SENIORITY = {"", "junior", "senior", "other"}
PROFILE_ALLOWED_EDUCATION = {
    "",
    "High School",
    "Associate's Degree",
    "Bachelor's Degree",
    "Master's Degree",
    "PhD",
}
PROFILE_ALLOWED_ENGLISH_PROFICIENCY = {"Professional", "Conversational", "Basic", "Native"}
PROFILE_ALLOWED_GENDER = {"", "Male", "Female", "Non-binary"}
PROFILE_ALLOWED_VETERAN_STATUS = {"No", "Yes", "Prefer not to say"}
PROFILE_ALLOWED_WORKPLACE_TYPES = {"all", "remote", "hybrid", "on_site"}
PROFILE_ALLOWED_APPLY_TYPES = {"easy_apply", "all", "external_only"}

# Blank saves should restore safe profile defaults for configurable fields.
# Personal identity/contact fields still require explicit user input.
PROFILE_BLANK_TEXT_DEFAULTS = {
    "experience_years": "5",
    "years_management_experience": "0",
    "keywords": "Software Developer\nFull Stack Developer\nPython Developer",
    "search_locations": "Hungary, Budapest, Remote",
}
PROFILE_BLANK_INTEGER_DEFAULTS = {
    "max_applications": 25,
    "max_network_companies_per_run": 20,
    "posted_days_ago": 7,
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _clean_single_line(value: str, *, max_length: int, label: str, errors: list[str], required: bool = False) -> str:
    cleaned = _collapse_spaces(value)
    if required and not cleaned:
        errors.append(f"{label} is required.")
    if cleaned and len(cleaned) > max_length:
        errors.append(f"{label} must be {max_length} characters or fewer.")
    return cleaned


def _clean_multiline_text(value: str, *, max_length: int, label: str, errors: list[str], required: bool = False) -> str:
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [_collapse_spaces(line) for line in raw.split("\n")]
    cleaned = "\n".join(line for line in lines if line)
    if required and not cleaned:
        errors.append(f"{label} is required.")
    if cleaned and len(cleaned) > max_length:
        errors.append(f"{label} must be {max_length} characters or fewer.")
    return cleaned


def _validate_email(value: str, *, label: str, errors: list[str], required: bool = False) -> str:
    cleaned = _clean_single_line(value, max_length=256, label=label, errors=errors, required=required).lower()
    if cleaned and not EMAIL_RE.fullmatch(cleaned):
        errors.append(f"{label} must be a valid email address.")
    return cleaned


def _validate_url(value: str, *, label: str, errors: list[str], allowed_hosts: tuple[str, ...] = ()) -> str:
    cleaned = _clean_single_line(value, max_length=256, label=label, errors=errors)
    if not cleaned:
        return ""

    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        errors.append(f"{label} must be a valid http:// or https:// URL.")
        return cleaned
    if allowed_hosts and not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
        errors.append(f"{label} must point to {allowed_hosts[0]}.")
    return cleaned


def _validate_choice(value: str, *, label: str, allowed: set[str], errors: list[str]) -> str:
    cleaned = _collapse_spaces(value)
    if cleaned not in allowed:
        errors.append(f"{label} contains an unsupported value.")
        return ""
    return cleaned


def _validate_integer(
    value: str,
    *,
    label: str,
    minimum: int,
    maximum: int,
    errors: list[str],
    default: int | None = None,
) -> int:
    cleaned = _collapse_spaces(value)
    if not cleaned:
        if default is not None:
            return default
        errors.append(f"{label} is required.")
        return minimum
    try:
        parsed = int(cleaned)
    except ValueError:
        errors.append(f"{label} must be a whole number between {minimum} and {maximum}.")
        return minimum
    if parsed < minimum or parsed > maximum:
        errors.append(f"{label} must be between {minimum} and {maximum}.")
    return max(minimum, min(maximum, parsed))


def _validate_optional_number_text(
    value: str,
    *,
    label: str,
    maximum: float,
    errors: list[str],
    default: str = "",
) -> str:
    cleaned = _clean_single_line(value, max_length=8, label=label, errors=errors)
    if not cleaned:
        return default
    if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        errors.append(f"{label} must be a number between 0 and {int(maximum)}.")
        return cleaned
    parsed = float(cleaned)
    if parsed < 0 or parsed > maximum:
        errors.append(f"{label} must be between 0 and {int(maximum)}.")
    return str(int(parsed)) if parsed.is_integer() else cleaned.rstrip("0").rstrip(".")


def _validate_graduation_year(value: str, *, errors: list[str]) -> str:
    cleaned = _clean_single_line(value, max_length=4, label="Graduation Year", errors=errors)
    if not cleaned:
        return ""
    if not re.fullmatch(r"\d{4}", cleaned):
        errors.append("Graduation Year must be a 4-digit year.")
        return cleaned
    year = int(cleaned)
    if year < 1900 or year > 2100:
        errors.append("Graduation Year must be between 1900 and 2100.")
    return cleaned


def _validate_phone(value: str, *, errors: list[str]) -> str:
    cleaned = _clean_single_line(value, max_length=32, label="Phone Number", errors=errors, required=True)
    digits = re.sub(r"\D", "", cleaned)
    if cleaned and (not PHONE_RE.fullmatch(cleaned) or len(digits) < 7 or len(digits) > 15):
        errors.append("Phone Number must contain a valid international phone format.")
    return cleaned


def _validate_languages_spoken(value: str, *, errors: list[str]) -> str:
    cleaned = _clean_single_line(value, max_length=1000, label="Languages Spoken", errors=errors)
    if not cleaned:
        return ""

    entries = [_collapse_spaces(part) for part in re.split(r"[,;\n]+", cleaned) if _collapse_spaces(part)]
    invalid = [entry for entry in entries if not LANGUAGE_ENTRY_RE.fullmatch(entry)]
    if invalid:
        errors.append(
            "Languages Spoken must use entries like 'English (Professional)' or 'Hungarian: Basic'."
        )
    return ", ".join(entries)


def _build_profile_form_state(profile: "UserProfile", overrides: dict[str, object]) -> SimpleNamespace:
    state = {column.name: getattr(profile, column.name) for column in profile.__table__.columns}
    state.update({key: value for key, value in overrides.items() if key not in {"linkedin_password", "cv_file"}})
    return SimpleNamespace(**state)


def _validate_profile_submission(profile: "UserProfile", form, files) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    cleaned: dict[str, object] = {}

    cleaned["full_name"] = _clean_single_line(
        form.get("full_name", ""), max_length=256, label="Full Name", errors=errors, required=True
    )
    cleaned["phone"] = _validate_phone(form.get("phone", ""), errors=errors)
    cleaned["location"] = _clean_single_line(
        form.get("location", ""), max_length=128, label="Current Location", errors=errors, required=True
    )
    cleaned["graduation_year"] = _validate_graduation_year(form.get("graduation_year", ""), errors=errors)
    cleaned["experience_years"] = _validate_optional_number_text(
        form.get("experience_years", ""),
        label="Years of Experience",
        maximum=80,
        errors=errors,
        default=PROFILE_BLANK_TEXT_DEFAULTS["experience_years"],
    )
    cleaned["work_auth_answer"] = _clean_single_line(
        form.get("work_auth_answer", ""), max_length=500, label="Work Authorization Answer", errors=errors
    )
    cleaned["salary_answer"] = _clean_single_line(
        form.get("salary_answer", ""), max_length=500, label="Salary / Compensation Answer", errors=errors
    )

    cleaned["nationality"] = _clean_single_line(
        form.get("nationality", ""), max_length=64, label="Nationality", errors=errors
    )
    cleaned["is_eu_citizen"] = bool(form.get("is_eu_citizen"))
    cleaned["willing_to_relocate"] = bool(form.get("willing_to_relocate"))
    cleaned["willing_to_work_onsite"] = bool(form.get("willing_to_work_onsite"))
    cleaned["willing_to_work_remote"] = bool(form.get("willing_to_work_remote"))
    cleaned["current_job_title"] = _clean_single_line(
        form.get("current_job_title", ""), max_length=128, label="Current Job Title", errors=errors
    )

    seniority = _validate_choice(
        form.get("job_seniority", ""), label="Preferred Seniority", allowed=PROFILE_ALLOWED_SENIORITY, errors=errors
    )
    cleaned["job_seniority"] = seniority
    cleaned["job_seniority_custom"] = _clean_single_line(
        form.get("job_seniority_custom", ""), max_length=128, label="Custom Seniority Label", errors=errors
    )
    if seniority == "other" and not cleaned["job_seniority_custom"]:
        errors.append("Custom Seniority Label is required when Preferred Seniority is Other.")
    if seniority != "other":
        cleaned["job_seniority_custom"] = ""

    cleaned["networking_title"] = _clean_single_line(
        form.get("networking_title", ""), max_length=128, label="Networking Title", errors=errors
    )
    cleaned["years_management_experience"] = _validate_optional_number_text(
        form.get("years_management_experience", "0"),
        label="Years of Management Experience",
        maximum=80,
        errors=errors,
        default=PROFILE_BLANK_TEXT_DEFAULTS["years_management_experience"],
    )
    cleaned["highest_education"] = _validate_choice(
        form.get("highest_education", ""),
        label="Highest Education Level",
        allowed=PROFILE_ALLOWED_EDUCATION,
        errors=errors,
    )
    cleaned["field_of_study"] = _clean_single_line(
        form.get("field_of_study", ""), max_length=128, label="Field of Study", errors=errors
    )
    cleaned["english_proficiency"] = _validate_choice(
        form.get("english_proficiency", "Professional"),
        label="English Proficiency",
        allowed=PROFILE_ALLOWED_ENGLISH_PROFICIENCY,
        errors=errors,
    ) or "Professional"
    cleaned["languages_spoken"] = _validate_languages_spoken(form.get("languages_spoken", ""), errors=errors)
    cleaned["has_drivers_license"] = bool(form.get("has_drivers_license"))
    cleaned["drivers_license_category"] = _clean_single_line(
        form.get("drivers_license_category", ""), max_length=16, label="License Category", errors=errors
    )
    if cleaned["has_drivers_license"] and not cleaned["drivers_license_category"]:
        errors.append("License Category is required when Driver's License is enabled.")
    if not cleaned["has_drivers_license"]:
        cleaned["drivers_license_category"] = ""

    cleaned["linkedin_url"] = _validate_url(
        form.get("linkedin_url", ""), label="LinkedIn Profile URL", errors=errors, allowed_hosts=("linkedin.com",)
    )
    cleaned["github_url"] = _validate_url(
        form.get("github_url", ""), label="GitHub URL", errors=errors, allowed_hosts=("github.com",)
    )
    cleaned["portfolio_url"] = _validate_url(form.get("portfolio_url", ""), label="Portfolio URL", errors=errors)
    cleaned["gender"] = _validate_choice(
        form.get("gender", ""), label="Gender", allowed=PROFILE_ALLOWED_GENDER, errors=errors
    )
    cleaned["has_disability"] = bool(form.get("has_disability"))
    cleaned["veteran_status"] = _validate_choice(
        form.get("veteran_status", "No"),
        label="Veteran Status",
        allowed=PROFILE_ALLOWED_VETERAN_STATUS,
        errors=errors,
    ) or "No"

    cleaned["keywords"] = _clean_multiline_text(
        form.get("keywords", ""), max_length=1500, label="Job Keywords", errors=errors
    ) or PROFILE_BLANK_TEXT_DEFAULTS["keywords"]
    cleaned["search_locations"] = _clean_multiline_text(
        form.get("search_locations", ""), max_length=1000, label="Search Locations", errors=errors
    ) or PROFILE_BLANK_TEXT_DEFAULTS["search_locations"]
    cleaned["workplace_type"] = _validate_choice(
        form.get("workplace_type", "all"),
        label="Workplace Type",
        allowed=PROFILE_ALLOWED_WORKPLACE_TYPES,
        errors=errors,
    ) or "all"
    cleaned["apply_type"] = _validate_choice(
        form.get("apply_type", "easy_apply"),
        label="Application Type",
        allowed=PROFILE_ALLOWED_APPLY_TYPES,
        errors=errors,
    ) or "easy_apply"
    cleaned["max_applications"] = _validate_integer(
        form.get("max_applications", "25"),
        label="Max Applications Per Day",
        minimum=1,
        maximum=50,
        errors=errors,
        default=PROFILE_BLANK_INTEGER_DEFAULTS["max_applications"],
    )
    cleaned["max_network_companies_per_run"] = _validate_integer(
        form.get("max_network_companies_per_run", "20"),
        label="Max Companies to Follow (Per Run)",
        minimum=1,
        maximum=100,
        errors=errors,
        default=PROFILE_BLANK_INTEGER_DEFAULTS["max_network_companies_per_run"],
    )
    cleaned["posted_days_ago"] = _validate_integer(
        form.get("posted_days_ago", "7"),
        label="Posted Within (days)",
        minimum=1,
        maximum=30,
        errors=errors,
        default=PROFILE_BLANK_INTEGER_DEFAULTS["posted_days_ago"],
    )
    cleaned["auto_apply_enabled"] = bool(form.get("auto_apply_enabled"))

    cleaned["linkedin_email"] = _validate_email(
        form.get("linkedin_email", ""), label="LinkedIn Email", errors=errors, required=True
    )
    cleaned["linkedin_password"] = form.get("linkedin_password", "")
    if cleaned["linkedin_password"] and len(str(cleaned["linkedin_password"])) < 8:
        errors.append("LinkedIn Password must be at least 8 characters.")
    if not cleaned["linkedin_password"] and not profile.linkedin_password_enc:
        errors.append("LinkedIn Password is required.")

    cv_file = files.get("cv_file")
    cleaned["cv_file"] = cv_file
    if cv_file and cv_file.filename:
        if not allowed_file(cv_file.filename):
            errors.append("CV file must be a PDF.")
    elif not profile.cv_filename:
        errors.append("CV file is required.")

    return cleaned, errors


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
    experience_years = db.Column(db.String(8), default="5")
    work_auth_answer = db.Column(db.Text, default="")
    salary_answer = db.Column(db.Text, default="")

    # Extended profile — screening questions
    nationality = db.Column(db.String(64), default="")
    is_eu_citizen = db.Column(db.Boolean, default=False)
    willing_to_relocate = db.Column(db.Boolean, default=False)
    willing_to_work_onsite = db.Column(db.Boolean, default=False)
    willing_to_work_remote = db.Column(db.Boolean, default=True)
    current_job_title = db.Column(db.String(128), default="")
    job_seniority = db.Column(db.String(16), default="")
    job_seniority_custom = db.Column(db.String(128), default="")
    networking_title = db.Column(db.String(128), default="")
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
    max_network_companies_per_run = db.Column(db.Integer, default=20)
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
    def seniority_label(self) -> str:
        seniority = (self.job_seniority or "").strip().lower()
        if seniority == "junior":
            return "Junior"
        if seniority == "senior":
            return "Senior"
        if seniority == "other":
            return re.sub(r"\s+", " ", (self.job_seniority_custom or "").strip())
        return ""

    def _apply_seniority_to_keyword(self, keyword: str) -> str:
        cleaned = re.sub(r"\s+", " ", (keyword or "").strip())
        seniority = self.seniority_label
        if not cleaned or not seniority:
            return cleaned

        prefix_pattern = (
            r"^(?:junior|jr\.?|senior|sr\.?|mid(?:-level)?|middle|lead|principal|staff|"
            r"entry[- ]level|intern(?:ship)?|graduate)\s+"
        )
        base_keyword = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE).strip()
        return f"{seniority} {base_keyword or cleaned}".strip()

    @property
    def search_job_title(self) -> str:
        return self._apply_seniority_to_keyword(self.current_job_title)

    @property
    def search_keywords_list(self) -> list[str]:
        base_keywords = self.keywords_list
        if not base_keywords:
            return []

        ordered_keywords: list[str] = []
        seen: set[str] = set()

        def _add(keyword: str) -> None:
            cleaned = re.sub(r"\s+", " ", (keyword or "").strip())
            if not cleaned:
                return
            key = cleaned.lower()
            if key in seen:
                return
            seen.add(key)
            ordered_keywords.append(cleaned)

        seniority = self.seniority_label
        if seniority:
            for keyword in base_keywords:
                _add(self._apply_seniority_to_keyword(keyword))

        for keyword in base_keywords:
            _add(keyword)

        return ordered_keywords

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


def _coerce_string_list(values: object) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []

    items: list[str] = []
    for value in values:
        text_value = str(value).strip()
        if text_value:
            items.append(text_value)
    return items


def _coerce_limited_string_list(values: object, *, max_items: int, max_length: int) -> list[str]:
    if values is None:
        return []

    raw_values: list[object]
    if isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = re.split(r"[\n,;|]+", str(values))

    cleaned_items: list[str] = []
    seen: set[str] = set()

    for value in raw_values:
        text_value = _collapse_spaces(value)
        if not text_value or len(text_value) > max_length:
            continue
        lowered = text_value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned_items.append(text_value)
        if len(cleaned_items) >= max_items:
            break

    return cleaned_items


def _shorten_text(value: str, limit: int = 320) -> str:
    text_value = re.sub(r"\s+", " ", (value or "").strip())
    if len(text_value) <= limit:
        return text_value

    shortened = text_value[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{shortened or text_value[: limit - 3]}..."


def _load_requirements_summary(job_id: str) -> str:
    if not job_id or not STUDY_GUIDES_FOLDER.exists():
        return ""

    try:
        candidates = sorted(STUDY_GUIDES_FOLDER.glob(f"{job_id}_*_requirements.txt"), reverse=True)
    except OSError:
        return ""

    for candidate in candidates:
        try:
            raw_text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue

        content_lines = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("Title:", "Company:", "URL:")):
                continue
            content_lines.append(stripped)

        summary = _shorten_text(" ".join(content_lines), limit=420)
        if summary:
            return summary

    return ""


def _load_requirements_metadata(job_id: str) -> dict[str, str]:
    if not job_id or not STUDY_GUIDES_FOLDER.exists():
        return {}

    try:
        candidates = sorted(STUDY_GUIDES_FOLDER.glob(f"{job_id}_*_requirements.txt"), reverse=True)
    except OSError:
        return {}

    for candidate in candidates:
        try:
            raw_text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue

        title = ""
        company = ""
        url = ""
        for line in raw_text.splitlines()[:6]:
            stripped = line.strip()
            if stripped.lower().startswith("title:"):
                title = stripped.partition(":")[2].strip()
            elif stripped.lower().startswith("company:"):
                company = stripped.partition(":")[2].strip()
            elif stripped.lower().startswith("url:"):
                url = stripped.partition(":")[2].strip()

        if title or company or url:
            return {"title": title, "company": company, "job_url": url}

    return {}


def _load_shared_job_index() -> dict[str, dict]:
    if not SHARED_APPLIED_LOG.exists():
        return {}

    try:
        raw_entries = json.loads(SHARED_APPLIED_LOG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(raw_entries, list):
        return {}

    shared_index: dict[str, dict] = {}
    for entry in reversed(raw_entries):
        if not isinstance(entry, dict):
            continue
        job_id = str(entry.get("job_id") or "").strip()
        if not job_id or job_id in shared_index:
            continue
        if entry.get("report") or entry.get("missing_skills"):
            shared_index[job_id] = entry
    return shared_index


def _load_shared_job_entries_for_user(user_id: int) -> list[dict]:
    if not SHARED_APPLIED_LOG.exists():
        return []

    user = db.session.get(User, user_id)
    profile = UserProfile.query.filter_by(user_id=user_id).first()

    candidate_emails = {
        str(getattr(user, "email", "") or "").strip().lower(),
        str(getattr(profile, "linkedin_email", "") or "").strip().lower(),
    }
    candidate_emails.discard("")

    candidate_names = {
        str(getattr(profile, "full_name", "") or "").strip().lower(),
    }
    candidate_names.discard("")

    if not candidate_emails and not candidate_names:
        return []

    try:
        raw_entries = json.loads(SHARED_APPLIED_LOG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(raw_entries, list):
        return []

    matches: list[dict] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue

        snapshot = entry.get("profile_snapshot")
        if not isinstance(snapshot, dict):
            continue

        snapshot_email = str(snapshot.get("email") or "").strip().lower()
        snapshot_name = str(snapshot.get("full_name") or "").strip().lower()

        email_match = bool(snapshot_email and snapshot_email in candidate_emails)
        name_match = bool(
            snapshot_name and any(
                snapshot_name in candidate_name or candidate_name in snapshot_name
                for candidate_name in candidate_names
            )
        )

        if email_match or name_match:
            matches.append(entry)

    return matches


def _normalize_skills_analysis(entry: dict, report: dict) -> dict:
    raw_analysis = report.get("skills_analysis")
    if not isinstance(raw_analysis, dict):
        raw_analysis = entry.get("missing_skills")
    if not isinstance(raw_analysis, dict):
        return {}

    missing_skills = _coerce_string_list(raw_analysis.get("missing_skills", raw_analysis.get("missing", [])))
    matched_skills = _coerce_string_list(raw_analysis.get("matched_skills", raw_analysis.get("matched", [])))
    job_skills = _coerce_string_list(raw_analysis.get("job_skills", []))

    try:
        match_percentage = float(raw_analysis.get("match_percentage", 0) or 0)
    except (TypeError, ValueError):
        match_percentage = 0.0

    normalized = {
        "missing_skills": missing_skills,
        "matched_skills": matched_skills,
        "job_skills": job_skills,
        "match_percentage": max(0.0, min(1.0, match_percentage)),
    }

    if any(normalized[key] for key in ("missing_skills", "matched_skills", "job_skills")) or normalized["match_percentage"]:
        return normalized
    return {}


def _normalize_job_report(entry: dict, fallback_entry: dict | None = None) -> dict:
    raw_report = entry.get("report")
    if not isinstance(raw_report, dict) and isinstance(fallback_entry, dict):
        raw_report = fallback_entry.get("report")
    report = dict(raw_report) if isinstance(raw_report, dict) else {}

    merged_entry = dict(fallback_entry) if isinstance(fallback_entry, dict) else {}
    merged_entry.update(entry)

    skills_analysis = _normalize_skills_analysis(merged_entry, report)
    if skills_analysis:
        report["skills_analysis"] = skills_analysis

    requirements_summary = str(report.get("requirements_summary") or "").strip()
    if not requirements_summary:
        requirements_summary = _load_requirements_summary(str(entry.get("job_id") or "").strip())
    if requirements_summary:
        report["requirements_summary"] = requirements_summary

    qa_pairs = report.get("qa_pairs")
    if isinstance(qa_pairs, list):
        report["qa_pairs"] = [pair for pair in qa_pairs if isinstance(pair, dict)]
    else:
        report["qa_pairs"] = []

    uploaded_files = _coerce_string_list(report.get("uploaded_files", []))
    if uploaded_files:
        report["uploaded_files"] = uploaded_files
    elif "uploaded_files" in report:
        report["uploaded_files"] = []

    if not isinstance(report.get("external_ats"), dict):
        report["external_ats"] = {}

    return report


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

    existing_event_keys = {
        (
            str(entry.get("job_id") or "").strip(),
            str(entry.get("timestamp") or "").strip(),
            str(entry.get("status") or "").strip().lower(),
        )
        for entry in raw
        if isinstance(entry, dict)
    }
    for shared_entry in _load_shared_job_entries_for_user(user_id):
        event_key = (
            str(shared_entry.get("job_id") or "").strip(),
            str(shared_entry.get("timestamp") or "").strip(),
            str(shared_entry.get("status") or "").strip().lower(),
        )
        if event_key in existing_event_keys:
            continue
        raw.append(shared_entry)
        existing_event_keys.add(event_key)

    if not raw:
        return [], []

    shared_job_index = _load_shared_job_index()

    submitted_jobs: list[dict] = []
    failed_jobs: list[dict] = []
    seen_job_ids: set[str] = set()

    for entry in reversed(raw):
        if not isinstance(entry, dict):
            continue

        job_id = str(entry.get("job_id") or "").strip()
        if job_id and job_id in seen_job_ids:
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

        fallback_entry = shared_job_index.get(str(entry.get("job_id") or "").strip())
        file_metadata = _load_requirements_metadata(job_id)
        raw_report = _normalize_job_report(entry, fallback_entry=fallback_entry)
        record = {
            "time": time_display,
            "title": (
                (entry.get("title") or "").strip()
                or str((fallback_entry or {}).get("title") or "").strip()
                or file_metadata.get("title", "")
                or f"Job {entry.get('job_id') or ''}".strip()
            ),
            "company": (
                (entry.get("company") or "").strip()
                or str((fallback_entry or {}).get("company") or "").strip()
                or file_metadata.get("company", "")
                or "-"
            ),
            "note": (entry.get("note") or "").strip() or "-",
            "job_url": (
                (entry.get("job_url") or "").strip()
                or str((fallback_entry or {}).get("job_url") or "").strip()
                or file_metadata.get("job_url", "")
            ),
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

        if job_id:
            seen_job_ids.add(job_id)

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
        "job_seniority": profile.job_seniority or "",
        "job_seniority_custom": profile.job_seniority_custom or "",
        "search_job_title": profile.search_job_title or profile.current_job_title,
        "keywords": profile.search_keywords_list or profile.keywords_list,
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


@app.route("/api/ext/apify_influencers", methods=["POST"])
@token_required
def api_ext_apify_influencers(user):
    """Recommend and optionally run an Apify actor for public LinkedIn networking research."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    profile = ensure_user_profile(user)
    errors: list[str] = []
    goal = _clean_single_line(data.get("goal", ""), max_length=320, label="Goal", errors=errors)
    max_profiles = _validate_integer(
        str(data.get("max_profiles", 25)),
        label="Max Profiles",
        minimum=1,
        maximum=100,
        errors=errors,
        default=25,
    )
    actor_limit = _validate_integer(
        str(data.get("actor_limit", 8)),
        label="Actor Limit",
        minimum=3,
        maximum=15,
        errors=errors,
        default=8,
    )

    companies = [
        company
        for company in _coerce_limited_string_list(data.get("companies"), max_items=20, max_length=120)
        if COMPANY_INPUT_RE.fullmatch(company)
    ]
    keywords = _coerce_limited_string_list(data.get("keywords"), max_items=12, max_length=80)
    locations = _coerce_limited_string_list(data.get("locations"), max_items=8, max_length=80)
    run_actor = bool(data.get("run_actor", False))

    actor_input = data.get("actor_input")
    if actor_input is not None and not isinstance(actor_input, dict):
        errors.append("actor_input must be a JSON object when provided.")

    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400

    if not goal:
        role_label = _collapse_spaces(profile.networking_title or profile.current_job_title or "professional networking")
        goal = f"Find public LinkedIn influencers and company voices relevant to {role_label}."
    if not keywords:
        keywords = (profile.search_keywords_list or profile.keywords_list)[:6]
    if not locations:
        locations = profile.locations_list[:5]

    profile_context = {
        "full_name": profile.full_name,
        "current_job_title": profile.current_job_title,
        "networking_title": profile.networking_title,
        "keywords": (profile.search_keywords_list or profile.keywords_list)[:8],
        "locations": profile.locations_list[:5],
    }

    try:
        import importlib

        service_module = importlib.import_module("apify_claude_service")
        service = service_module.ApifyClaudeResearchService(BASE_DIR / "openapi.json")
        result = service.plan_public_linkedin_research(
            goal=goal,
            companies=companies,
            keywords=keywords,
            locations=locations,
            max_profiles=max_profiles,
            actor_limit=actor_limit,
            run_actor=run_actor,
            actor_input=actor_input if isinstance(actor_input, dict) else None,
            profile_context=profile_context,
        )
        return jsonify(result)
    except Exception as exc:
        if exc.__class__.__name__ == "ApifyClaudeServiceError":
            return jsonify({"error": str(exc)}), 502
        app.logger.exception("Apify influencer planning failed for user_id=%s", user.id)
        return jsonify({"error": f"Failed to plan Apify influencer research: {exc}"}), 500


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
        last_completed_run = next((run for run in runs if run.status != "running"), None)
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
            for report in missing_skills_reports:
                report.requirements_summary = _load_requirements_summary(str(report.job_id or "").strip())
        except:
            missing_skills_reports = []
        
        return render_template(
            "dashboard.html",
            user=user,
            p=p,
            runs=runs,
            last_completed_run=last_completed_run,
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
        cleaned, errors = _validate_profile_submission(p, request.form, request.files)
        if errors:
            flash("Please correct the profile form before saving.", "danger")
            for message in errors:
                flash(message, "danger")
            return render_template("profile.html", user=user, p=_build_profile_form_state(p, cleaned))

        for field, value in cleaned.items():
            if field in {"linkedin_password", "cv_file"}:
                continue
            setattr(p, field, value)

        if cleaned["linkedin_password"]:
            p.set_linkedin_password(str(cleaned["linkedin_password"]))

        cv_file = cleaned["cv_file"]
        if cv_file and cv_file.filename:
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
        profile_apply_type = (getattr(p, "apply_type", "") or "easy_apply").strip().lower()
        if watch_browser:
            if profile_apply_type == "external_only":
                flash(
                    "LinkedIn external-only run started. This mode still starts from LinkedIn job search and opens company-site apply pages when available. Use External Websites Watch to bypass LinkedIn entirely.",
                    "info",
                )
            elif os.environ.get("RENDER"):
                flash("Run and Watch started in cloud mode. Live progress appears in the dashboard log (no desktop browser window on Render).", "info")
            else:
                flash("Bot run started in visible mode. A Chrome window should open on this machine.", "info")
        else:
            if profile_apply_type == "external_only":
                flash(
                    "LinkedIn external-only background run started. This mode still searches LinkedIn first; use External Websites Watch for direct external job boards.",
                    "info",
                )
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

        company = _clean_single_line(
            request.form.get("company") or "",
            max_length=120,
            label="Company",
            errors=[],
        )
        if company and not COMPANY_INPUT_RE.fullmatch(company):
            flash("Company contains unsupported characters.", "warning")
            return redirect(url_for("dashboard"))

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

                if "networking_title" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN networking_title VARCHAR(128) DEFAULT ''"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS networking_title VARCHAR(128) DEFAULT ''"))
                    db.session.commit()

                if "job_seniority" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN job_seniority VARCHAR(16) DEFAULT ''"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS job_seniority VARCHAR(16) DEFAULT ''"))
                    db.session.commit()

                if "job_seniority_custom" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN job_seniority_custom VARCHAR(128) DEFAULT ''"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS job_seniority_custom VARCHAR(128) DEFAULT ''"))
                    db.session.commit()

                if "max_network_companies_per_run" not in profile_cols:
                    if dialect == "sqlite":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN max_network_companies_per_run INTEGER DEFAULT 20"))
                    elif dialect == "postgresql":
                        db.session.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS max_network_companies_per_run INTEGER DEFAULT 20"))
                    db.session.commit()

                db.session.execute(text(
                    "UPDATE user_profiles SET max_network_companies_per_run=20 "
                    "WHERE max_network_companies_per_run IS NULL OR max_network_companies_per_run < 1"
                ))
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
if str(os.environ.get("AUTOAPPLY_DISABLE_WEBAPP_SCHEDULER", "") or "").strip().lower() not in {"1", "true", "yes", "on"}:
    from scheduler import start_scheduler as _start_scheduler
    _start_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
