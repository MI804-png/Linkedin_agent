from __future__ import annotations

import json
import traceback
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from pathlib import Path

from bot import LinkedInAutoApplyBot
from config import BASE_DIR, MissingCredentialError, load_runtime_config


def _show_info(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(title, message)
    root.destroy()


def _show_error(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


def _prompt_for_credentials() -> bool:
    root = tk.Tk()
    root.withdraw()
    email = simpledialog.askstring("LinkedIn setup", "Enter your LinkedIn email:", parent=root)
    if not email:
        root.destroy()
        return False
    password = simpledialog.askstring(
        "LinkedIn setup",
        "Enter your LinkedIn password:",
        parent=root,
        show="*",
    )
    if not password:
        root.destroy()
        return False

    env_path = Path(BASE_DIR) / ".env"
    env_path.write_text(
        f"LINKEDIN_EMAIL={email.strip()}\nLINKEDIN_PASSWORD={password}\n",
        encoding="utf-8",
    )
    root.destroy()
    return True


def main() -> int:
    try:
        config = load_runtime_config(headless=True)
    except MissingCredentialError:
        if not _prompt_for_credentials():
            _show_error("Setup canceled", "No credentials were provided.")
            return 2
        try:
            config = load_runtime_config(headless=True)
        except Exception as exc:
            _show_error("Setup error", str(exc))
            return 2
    except Exception as exc:
        _show_error("Startup error", str(exc))
        return 2

    try:
        bot = LinkedInAutoApplyBot(
            config,
            dry_run=False,
            resume=False,
            limit=config.settings.max_applications_per_run,
        )
        result = bot.run()
        stats = result.get("stats", {})
        _show_info(
            "LinkedIn Auto-Apply finished",
            "Run completed successfully.\n\n"
            f"Submitted: {stats.get('submitted', 0)}\n"
            f"Skipped: {stats.get('skipped', 0)}\n"
            f"Failures: {stats.get('failures', 0)}",
        )
        return 0
    except Exception as exc:
        details = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
        _show_error("Run failed", details)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
