from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from bot import LinkedInAutoApplyBot
from config import MissingCredentialError, RuntimePaths, load_runtime_config, validate_local_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Apply Bot")
    parser.add_argument("--dry-run", action="store_true", help="Search and inspect only, no submissions.")
    parser.add_argument("--resume", action="store_true", help="Resume from saved cursor in state.json.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode.")
    parser.add_argument("--limit", type=int, default=None, help="Max processed jobs in this run.")
    parser.add_argument("--apply-type", choices=["easy_apply", "all", "external_only"], default=None, help="easy_apply / all / external_only")
    parser.add_argument("--validate", action="store_true", help="Validate local setup without opening browser.")
    parser.add_argument("--network", action="store_true", help="Run LinkedIn networking campaign (connect with recruiters at big companies).")
    parser.add_argument("--interviews", action="store_true", help="Scan LinkedIn messages for interview invites and generate study guides.")
    return parser.parse_args()


def run_validation() -> int:
    paths = RuntimePaths()
    problems = validate_local_files(paths)

    env_path = paths.base_dir / ".env"
    if not env_path.exists():
        problems.append(f"Missing .env file: {env_path}")

    report = {
        "ok": len(problems) == 0,
        "problems": problems,
        "checked_paths": {
            "cv": str(paths.cv_path),
            "applied_log": str(paths.applied_log),
            "run_history_log": str(paths.run_history_log),
            "state_path": str(paths.state_path),
            "env_path": str(env_path),
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 2


def main() -> int:
    args = parse_args()

    if args.network:
        try:
            config = load_runtime_config(headless=args.headless)
        except MissingCredentialError as exc:
            print(str(exc))
            return 2
        bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
        try:
            result = bot.run_networking_campaign()
        except Exception as exc:
            print(f"Networking run failed: {exc}")
            return 1
        print("Networking run completed")
        print(json.dumps(result, indent=2))
        return 0

    if args.interviews:
        try:
            config = load_runtime_config(headless=args.headless)
        except MissingCredentialError as exc:
            print(str(exc))
            return 2
        bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
        try:
            result = bot.run_interview_prep()
        except Exception as exc:
            print(f"Interview prep run failed: {exc}")
            return 1
        print("\nInterview prep completed")
        print(json.dumps(result, indent=2))
        return 0

    if args.validate:
        return run_validation()

    try:
        config = load_runtime_config(headless=args.headless)
    except MissingCredentialError as exc:
        print(str(exc))
        return 2

    if args.apply_type:
        config.settings.apply_type = args.apply_type

    bot = LinkedInAutoApplyBot(
        config,
        dry_run=args.dry_run,
        resume=args.resume,
        limit=args.limit,
    )

    try:
        result = bot.run()
    except Exception as exc:
        print(f"Run failed: {exc}")
        return 1

    print("Run completed")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
