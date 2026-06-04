from __future__ import annotations

import argparse
import importlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT_DIR = Path(__file__).resolve().parents[1]
BOT_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = ROOT_DIR / "webapp"
DEFAULT_CONFIG_PATH = BOT_DIR / ".scheduler.env"
DEFAULT_DB_PATH = WEBAPP_DIR / "app.db"
DEFAULT_LOG_PATH = BOT_DIR / "run_watch_scheduler.log"
DEFAULT_STATE_PATH = BOT_DIR / "run_watch_scheduler_state.json"
PLACEHOLDER_VALUES = {
    "your_dashboard_email@example.com",
    "your_dashboard_password_here",
}


@dataclass
class SchedulerConfig:
    account_user_id: int | None
    account_email: str
    account_password: str
    run_mode: str
    base_url: str
    db_path: Path
    python_exe: Path
    webapp_entry: str
    poll_seconds: int
    dashboard_start_timeout: int
    run_on_login: bool
    log_path: Path
    state_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Desktop scheduler that triggers the existing local 'Run and Watch' flow."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to the scheduler env file.")
    parser.add_argument("--check", action="store_true", help="Print current scheduler status without triggering a run.")
    parser.add_argument("--daemon", action="store_true", help="Run continuously and check every poll interval.")
    parser.add_argument("--trigger-now", action="store_true", help="Force an immediate visible run instead of waiting for the scheduled UTC minute.")
    parser.add_argument("--poll-seconds", type=int, default=None, help="Override polling interval for daemon mode.")
    return parser.parse_args()


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_run_mode(value: str | None) -> str:
    cleaned = (value or "watch").strip().lower()
    allowed = {"watch", "external_watch"}
    if cleaned not in allowed:
        raise ValueError(
            f"Unsupported AUTOAPPLY_RUN_MODE={value!r}. Expected one of: {', '.join(sorted(allowed))}."
        )
    return cleaned


def sanitize_secret_value(value: str | None) -> str:
    cleaned = (value or "").strip()
    return "" if cleaned in PLACEHOLDER_VALUES else cleaned


def resolve_python_executable(raw_value: str | None) -> Path:
    if raw_value:
        return Path(raw_value).expanduser().resolve()

    candidates = []
    if os.name == "nt":
        candidates.extend([
            ROOT_DIR / ".venv" / "Scripts" / "python.exe",
            ROOT_DIR / ".venv" / "Scripts" / "pythonw.exe",
        ])
    else:
        candidates.extend([
            ROOT_DIR / ".venv" / "bin" / "python3",
            ROOT_DIR / ".venv" / "bin" / "python",
        ])

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return Path(sys.executable).resolve()


def build_config(args: argparse.Namespace) -> SchedulerConfig:
    file_values = load_env_file(Path(args.config))
    env = {**file_values, **os.environ}

    base_url = (env.get("AUTOAPPLY_BASE_URL") or "http://127.0.0.1:5000").rstrip("/")
    parsed = urlparse(base_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    default_entry = "run_5001.py" if port == 5001 else "app.py"

    poll_seconds = args.poll_seconds or int(env.get("AUTOAPPLY_POLL_SECONDS", "60"))
    account_user_id_raw = (env.get("AUTOAPPLY_ACCOUNT_USER_ID") or "").strip()
    account_user_id = int(account_user_id_raw) if account_user_id_raw else None

    return SchedulerConfig(
        account_user_id=account_user_id,
        account_email=sanitize_secret_value(env.get("AUTOAPPLY_ACCOUNT_EMAIL")),
        account_password=sanitize_secret_value(env.get("AUTOAPPLY_ACCOUNT_PASSWORD")),
        run_mode=normalize_run_mode(env.get("AUTOAPPLY_RUN_MODE")),
        base_url=base_url,
        db_path=Path(env.get("AUTOAPPLY_DB_PATH") or DEFAULT_DB_PATH).expanduser().resolve(),
        python_exe=resolve_python_executable(env.get("AUTOAPPLY_PYTHON_EXE")),
        webapp_entry=(env.get("AUTOAPPLY_WEBAPP_ENTRY") or default_entry).strip(),
        poll_seconds=max(15, poll_seconds),
        dashboard_start_timeout=int(env.get("AUTOAPPLY_DASHBOARD_START_TIMEOUT", "30")),
        run_on_login=parse_bool(env.get("AUTOAPPLY_RUN_ON_LOGIN"), default=False),
        log_path=DEFAULT_LOG_PATH,
        state_path=DEFAULT_STATE_PATH,
    )


def write_log(config: SchedulerConfig, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    with config.log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)


def connect_db(config: SchedulerConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_profile_row(
    conn: sqlite3.Connection,
    *,
    account_email: str = "",
    account_user_id: int | None = None,
) -> sqlite3.Row | None:
    base_query = """
        SELECT
            users.id AS user_id,
            users.email AS email,
            user_profiles.auto_apply_enabled AS auto_apply_enabled,
            user_profiles.scheduled_run_hour AS scheduled_run_hour,
            user_profiles.scheduled_run_minute AS scheduled_run_minute,
            user_profiles.last_scheduled_run AS last_scheduled_run,
            user_profiles.posted_days_ago AS posted_days_ago,
            user_profiles.linkedin_email AS linkedin_email,
            user_profiles.linkedin_password_enc AS linkedin_password_enc,
            user_profiles.cv_filename AS cv_filename
        FROM users
        JOIN user_profiles ON user_profiles.user_id = users.id
    """

    if account_user_id is not None:
        query = base_query + " WHERE users.id = ? LIMIT 1"
        return conn.execute(query, (account_user_id,)).fetchone()

    query = base_query + " WHERE lower(users.email) = lower(?) LIMIT 1"
    return conn.execute(query, (account_email,)).fetchone()


def parse_db_datetime(raw_value: object) -> datetime | None:
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    candidates = [value]
    if value.endswith("Z"):
        candidates.append(value[:-1] + "+00:00")

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is not None:
                return parsed.astimezone(tz=None).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def profile_is_ready(profile: sqlite3.Row) -> bool:
    return bool(
        profile["auto_apply_enabled"]
        and str(profile["linkedin_email"] or "").strip()
        and str(profile["linkedin_password_enc"] or "").strip()
        and str(profile["cv_filename"] or "").strip()
    )


def latest_bot_run(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, status, started_at, finished_at FROM bot_runs WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def has_active_run(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT id, started_at FROM bot_runs WHERE user_id = ? AND status = 'running' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    started_at = parse_db_datetime(row["started_at"])
    if started_at is None:
        return True
    return datetime.utcnow() - started_at < timedelta(hours=8)


def is_due_now(profile: sqlite3.Row, now_utc: datetime) -> bool:
    if not profile_is_ready(profile):
        return False

    if int(profile["scheduled_run_hour"] or 0) != now_utc.hour:
        return False
    if int(profile["scheduled_run_minute"] or 0) != now_utc.minute:
        return False

    last_run = parse_db_datetime(profile["last_scheduled_run"])
    if last_run and now_utc - last_run < timedelta(hours=1):
        return False
    return True


def mark_last_scheduled_run(conn: sqlite3.Connection, user_id: int, when_utc: datetime) -> None:
    conn.execute(
        "UPDATE user_profiles SET last_scheduled_run = ? WHERE user_id = ?",
        (when_utc.strftime("%Y-%m-%d %H:%M:%S.%f"), user_id),
    )
    conn.commit()


def load_state(config: SchedulerConfig) -> dict[str, object]:
    if not config.state_path.exists():
        return {"startup_runs": {}}
    try:
        return json.loads(config.state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"startup_runs": {}}


def save_state(config: SchedulerConfig, state: dict[str, object]) -> None:
    config.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def should_run_on_login(config: SchedulerConfig, profile: sqlite3.Row) -> bool:
    if not config.run_on_login or not profile_is_ready(profile):
        return False
    state = load_state(config)
    startup_runs = state.setdefault("startup_runs", {})
    today = datetime.now().date().isoformat()
    return startup_runs.get(str(profile["user_id"]), "") != today


def mark_login_run(config: SchedulerConfig, profile: sqlite3.Row) -> None:
    state = load_state(config)
    startup_runs = state.setdefault("startup_runs", {})
    startup_runs[str(profile["user_id"])] = datetime.now().date().isoformat()
    save_state(config, state)


def dashboard_reachable(base_url: str, timeout_seconds: int = 3) -> bool:
    request = Request(base_url + "/login", method="GET")
    try:
        opener = build_opener()
        with opener.open(request, timeout=timeout_seconds) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError, TimeoutError):
        return False


def start_dashboard(config: SchedulerConfig) -> None:
    launcher_path = WEBAPP_DIR / config.webapp_entry
    if not launcher_path.exists():
        raise FileNotFoundError(f"Webapp launcher not found: {launcher_path}")

    stdout_path = BOT_DIR / "scheduler_webapp_stdout.log"
    stderr_path = BOT_DIR / "scheduler_webapp_stderr.log"
    stdout_handle = stdout_path.open("ab")
    stderr_handle = stderr_path.open("ab")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

    subprocess.Popen(
        [str(config.python_exe), str(launcher_path)],
        cwd=str(ROOT_DIR),
        stdout=stdout_handle,
        stderr=stderr_handle,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        creationflags=creation_flags,
    )

    deadline = time.time() + config.dashboard_start_timeout
    while time.time() < deadline:
        if dashboard_reachable(config.base_url):
            return
        time.sleep(1)

    raise RuntimeError(f"Dashboard did not start within {config.dashboard_start_timeout} seconds")


def _load_local_runtime_modules():
    os.environ["AUTOAPPLY_DISABLE_WEBAPP_SCHEDULER"] = "1"
    if str(WEBAPP_DIR) not in sys.path:
        sys.path.insert(0, str(WEBAPP_DIR))

    app_mod = importlib.import_module("app")
    bot_runner_mod = importlib.import_module("bot_runner")
    return app_mod, bot_runner_mod


def trigger_local_run(config: SchedulerConfig, user_id: int) -> int | None:
    app_mod, bot_runner_mod = _load_local_runtime_modules()

    if not dashboard_reachable(config.base_url):
        write_log(config, "Local dashboard not reachable. Starting it now...")
        try:
            start_dashboard(config)
        except Exception as exc:
            write_log(config, f"Dashboard auto-start failed: {exc}. Continuing with direct local trigger.")

    with app_mod.app.app_context():
        if config.run_mode == "external_watch":
            started, message = bot_runner_mod.run_direct_external_for_user_async(
                user_id,
                watch_browser=not bool(os.environ.get("RENDER")),
            )
            if not started:
                raise RuntimeError(message)
            return None

        return bot_runner_mod.run_for_user_async(user_id, watch_browser=True)


class DashboardClient:
    def __init__(self, base_url: str, timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))

    def _open(self, path: str, *, form_data: dict[str, str] | None = None):
        body = None
        method = "GET"
        headers = {"User-Agent": "AutoApplyRunWatchScheduler/1.0"}
        if form_data is not None:
            body = urlencode(form_data).encode("utf-8")
            method = "POST"
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(self.base_url + path, data=body, method=method, headers=headers)
        return self.opener.open(request, timeout=self.timeout_seconds)

    def login(self, email: str, password: str) -> None:
        response = self._open("/login", form_data={"email": email, "password": password})
        final_url = response.geturl()
        if "/dashboard" in final_url:
            return

        response = self._open("/dashboard")
        if "/login" in response.geturl():
            raise RuntimeError("Dashboard login failed. Check AUTOAPPLY_ACCOUNT_EMAIL and AUTOAPPLY_ACCOUNT_PASSWORD.")

    def trigger_watch_run(self) -> None:
        response = self._open("/run", form_data={"run_mode": "watch"})
        final_url = response.geturl()
        if "/login" in final_url:
            raise RuntimeError("Lost dashboard session while triggering Run and Watch.")
        if "/profile" in final_url:
            raise RuntimeError("Dashboard redirected to Profile. Complete the local profile before scheduling Run and Watch.")

    def trigger_external_watch_run(self) -> None:
        response = self._open("/run_external_watch", form_data={})
        final_url = response.geturl()
        if "/login" in final_url:
            raise RuntimeError("Lost dashboard session while triggering External Websites Watch.")
        if "/profile" in final_url:
            raise RuntimeError("Dashboard redirected to Profile. Complete the local profile before scheduling External Websites Watch.")


def status_snapshot(config: SchedulerConfig) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "config_path": str(DEFAULT_CONFIG_PATH),
        "db_path": str(config.db_path),
        "base_url": config.base_url,
        "run_mode": config.run_mode,
        "target_user_id": config.account_user_id,
        "dashboard_email_configured": bool(config.account_email),
        "dashboard_password_configured": bool(config.account_password),
        "run_on_login": config.run_on_login,
        "poll_seconds": config.poll_seconds,
        "dashboard_reachable": dashboard_reachable(config.base_url),
    }

    if not config.db_path.exists() or (not config.account_email and config.account_user_id is None):
        snapshot["profile_found"] = False
        return snapshot

    with connect_db(config) as conn:
        profile = fetch_profile_row(conn, account_email=config.account_email, account_user_id=config.account_user_id)
        if profile is None:
            snapshot["profile_found"] = False
            return snapshot

        now_utc = datetime.utcnow().replace(second=0, microsecond=0)
        snapshot.update({
            "profile_found": True,
            "user_id": profile["user_id"],
            "auto_apply_enabled": bool(profile["auto_apply_enabled"]),
            "profile_ready": profile_is_ready(profile),
            "scheduled_run_hour_utc": profile["scheduled_run_hour"],
            "scheduled_run_minute_utc": profile["scheduled_run_minute"],
            "posted_days_ago": profile["posted_days_ago"],
            "last_scheduled_run": profile["last_scheduled_run"],
            "due_now": is_due_now(profile, now_utc),
            "active_run": has_active_run(conn, int(profile["user_id"])),
            "run_on_login_pending_today": should_run_on_login(config, profile),
        })
    return snapshot


def maybe_trigger(config: SchedulerConfig, *, force_now: bool, startup_check: bool) -> int:
    if not config.db_path.exists():
        raise FileNotFoundError(f"Scheduler database not found: {config.db_path}")

    with connect_db(config) as conn:
        if not config.account_email and config.account_user_id is None:
            raise RuntimeError("AUTOAPPLY_ACCOUNT_EMAIL or AUTOAPPLY_ACCOUNT_USER_ID is required for scheduler operation.")

        profile = fetch_profile_row(conn, account_email=config.account_email, account_user_id=config.account_user_id)
        if profile is None:
            identifier = f"user_id={config.account_user_id}" if config.account_user_id is not None else config.account_email
            raise RuntimeError(f"No local dashboard user found for {identifier}.")

        if has_active_run(conn, int(profile["user_id"])):
            write_log(config, f"Skipped: user {profile['email']} already has a running bot job.")
            return 0

        now_utc = datetime.utcnow().replace(second=0, microsecond=0)
        trigger_reason = None
        if force_now:
            trigger_reason = "manual --trigger-now"
        elif startup_check and should_run_on_login(config, profile):
            trigger_reason = "AUTOAPPLY_RUN_ON_LOGIN"
        elif is_due_now(profile, now_utc):
            trigger_reason = "scheduled UTC minute match"

        if trigger_reason is None:
            write_log(config, f"No run due for {profile['email']} at {now_utc:%H:%M} UTC.")
            return 0

        if not profile_is_ready(profile):
            raise RuntimeError("Profile is incomplete. Upload CV and LinkedIn credentials in the local dashboard first.")

        previous_run = latest_bot_run(conn, int(profile["user_id"]))
        previous_run_id = previous_run["id"] if previous_run else None

        if config.account_password:
            login_email = config.account_email or str(profile["email"] or "").strip()
            if not login_email:
                raise RuntimeError("Could not determine dashboard login email for the selected profile.")

            if not dashboard_reachable(config.base_url):
                write_log(config, "Local dashboard not reachable. Starting it now...")
                start_dashboard(config)

            client = DashboardClient(config.base_url)
            client.login(login_email, config.account_password)
            if config.run_mode == "external_watch":
                client.trigger_external_watch_run()
            else:
                client.trigger_watch_run()
        else:
            trigger_local_run(config, int(profile["user_id"]))
        time.sleep(2)

        latest_run = latest_bot_run(conn, int(profile["user_id"]))
        if latest_run is None or latest_run["id"] == previous_run_id:
            raise RuntimeError("Dashboard request completed, but no new bot run was recorded.")

        mark_last_scheduled_run(conn, int(profile["user_id"]), datetime.utcnow())
        if startup_check and config.run_on_login:
            mark_login_run(config, profile)

        write_log(
            config,
            (
                f"Started {'External Websites Watch' if config.run_mode == 'external_watch' else 'Run and Watch'} "
                f"for {profile['email']} via {trigger_reason}. bot_run_id={latest_run['id']}"
            ),
        )
        return 0


def main() -> int:
    args = parse_args()
    config = build_config(args)

    if args.check:
        print(json.dumps(status_snapshot(config), indent=2, default=str))
        return 0

    if args.daemon:
        mode_label = "External Websites Watch" if config.run_mode == "external_watch" else "Run and Watch"
        write_log(config, f"{mode_label} scheduler daemon started. Poll interval={config.poll_seconds}s")
        first_loop = True
        while True:
            try:
                maybe_trigger(config, force_now=args.trigger_now and first_loop, startup_check=first_loop)
            except Exception as exc:
                write_log(config, f"Scheduler error: {exc}")
            first_loop = False
            time.sleep(config.poll_seconds)

    try:
        return maybe_trigger(config, force_now=args.trigger_now, startup_check=True)
    except Exception as exc:
        write_log(config, f"Scheduler error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
