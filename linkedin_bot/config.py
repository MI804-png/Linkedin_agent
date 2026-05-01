from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class CandidateProfile:
    full_name: str = "Mikhael Nabil Salama Rezk"
    email: str = "Mikhael.Nabil.Salama.Rezk@gmail.com"
    phone: str = "+36 70 635 5765"
    location: str = "Kecskemet, Hungary"
    graduation_year: str = "2027"
    total_experience_years: str = "5"
    work_authorization_hungary: str = "Yes, I have a valid Hungarian student residence permit."
    work_authorization_italy: str = "I may require sponsorship; open to discussion."
    salary_hungary: str = "1000000 HUF/month"
    salary_italy: str = "Negotiable"


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
    max_applications_per_run: int = 25
    retries_per_job: int = 2
    posted_days_ago: int = 7
    headless: bool = False
    random_wait_min_seconds: float = 1.5
    random_wait_max_seconds: float = 3.8


@dataclass
class RuntimePaths:
    base_dir: Path = BASE_DIR
    cv_path: Path = BASE_DIR.parent / "Mikhael_CV.pdf"
    applied_log: Path = BASE_DIR / "applied_jobs.json"
    run_history_log: Path = BASE_DIR / "run_history.json"
    state_path: Path = BASE_DIR / "state.json"
    browser_state_path: Path = BASE_DIR / "playwright_state.json"


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
