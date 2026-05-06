from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import sys
from dotenv import load_dotenv


def _resolve_base_dir() -> Path:
    # When bundled as an executable, store runtime files next to the .exe.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _resolve_base_dir()


@dataclass
class CandidateProfile:
    full_name: str = "Mikhael Nabil Salama Rezk"
    email: str = "Mikhael.Nabil.Salama.Rezk@gmail.com"
    phone: str = "+36 70 635 5765"
    location: str = "Kecskemet, Hungary"
    graduation_year: str = "2027"
    total_experience_years: str = "5"

    # Work authorization
    work_authorization_hungary: str = "Yes, I have a valid Hungarian student residence permit."
    work_authorization_italy: str = "I may require sponsorship; open to discussion."
    is_eu_citizen: bool = False          # Not an EU citizen
    nationality: str = "Egyptian"        # Used for nationality questions

    # Compensation
    salary_hungary: str = "1000000 HUF/month"
    salary_italy: str = "35000"

    # Job preferences
    willing_to_relocate: bool = True
    willing_to_work_onsite: bool = False
    willing_to_work_remote: bool = True
    current_job_title: str = "Full Stack Developer"
    years_management_experience: str = "0"

    # Education
    highest_education: str = "Bachelor's Degree"
    field_of_study: str = "Computer Science Engineering"

    # Languages
    english_proficiency: str = "Professional"  # Professional / C1 / Advanced
    languages_spoken: str = "Arabic (Native), English (Professional), Italian (Professional)"

    # Documents & licenses
    has_drivers_license: bool = False
    drivers_license_category: str = ""

    # Online presence
    linkedin_url: str = "https://www.linkedin.com/in/mikhael-nabil"
    github_url: str = "https://github.com/mikhael-nabil"
    portfolio_url: str = ""   # Leave blank to fall back to github_url

    # Sensitive / optional — left blank means the bot won't auto-fill them
    gender: str = "Male"
    has_disability: bool = False
    veteran_status: str = "No"  # "No" / "Yes" / "Prefer not to say"


@dataclass
class BotSettings:
    keywords: list[str] = field(
        default_factory=lambda: [
            "Full Stack Developer",
            "Frontend Developer",
            "Backend Developer",
            "Web Developer",
            "Software Developer",
        ]
    )
    locations: list[str] = field(
        default_factory=lambda: ["Hungary", "Budapest", "Italy", "Milan", "Rome"]
    )
    workplace_type: str = "all"  # all/remote/hybrid/on_site
    apply_type: str = "easy_apply"  # easy_apply / all / external_only
    max_applications_per_run: int = 25
    retries_per_job: int = 2
    posted_days_ago: int = 7
    prioritize_recommended_jobs: bool = True
    scan_linkedin_notifications: bool = True
    headless: bool = False
    max_network_per_run: int = 20   # max connection requests per networking campaign run
    random_wait_min_seconds: float = 0.5
    random_wait_max_seconds: float = 1.2
    watch_hold_seconds: int = 0


@dataclass
class RuntimePaths:
    base_dir: Path = BASE_DIR
    cv_path: Path = BASE_DIR.parent / "Mikhael_CV.pdf"
    applied_log: Path = BASE_DIR / "applied_jobs.json"
    run_history_log: Path = BASE_DIR / "run_history.json"
    state_path: Path = BASE_DIR / "state.json"
    browser_state_path: Path = BASE_DIR / "playwright_state.json"
    gmail_alert_links_path: Path = BASE_DIR / "priority_job_links.txt"
    study_guides_dir: Path = BASE_DIR / "study_guides"
    # webapp user_data letters folder (user id 1 = single-user install)
    webapp_letters_dir: Path = BASE_DIR.parent / "webapp" / "user_data" / "1" / "generated_letters"


@dataclass
class RuntimeConfig:
    email: str
    password: str
    profile: CandidateProfile
    settings: BotSettings
    paths: RuntimePaths


class MissingCredentialError(RuntimeError):
    pass


def load_runtime_config(*, headless: bool | None = None) -> RuntimeConfig:
    load_dotenv(BASE_DIR / ".env")

    email = os.getenv("LINKEDIN_EMAIL", "").strip()
    password = os.getenv("LINKEDIN_PASSWORD", "").strip()
    if not email or not password:
        raise MissingCredentialError(
            "Missing LINKEDIN_EMAIL and/or LINKEDIN_PASSWORD in linkedin_bot/.env"
        )

    settings = BotSettings()
    if headless is not None:
        settings.headless = headless

    return RuntimeConfig(
        email=email,
        password=password,
        profile=CandidateProfile(),
        settings=settings,
        paths=RuntimePaths(),
    )


def validate_local_files(paths: RuntimePaths) -> list[str]:
    problems: list[str] = []

    if not paths.cv_path.exists():
        problems.append(f"CV file not found: {paths.cv_path}")

    for p in [paths.applied_log, paths.run_history_log, paths.state_path]:
        if not p.exists():
            problems.append(f"State/log file missing: {p}")

    return problems
