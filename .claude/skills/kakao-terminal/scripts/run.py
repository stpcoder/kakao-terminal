#!/usr/bin/env python3
"""Launcher for the bundled kakao-terminal skill runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VENV_PYTHON = SCRIPT_DIR / ".venv" / "bin" / "python"
LIB_DIR = SCRIPT_DIR / "lib"
HELP_TEXT = """kakao-terminal skill runner

Usage:
  python3 .claude/skills/kakao-terminal/scripts/run.py <command> [args]

Commands:
  doctor       Run prerequisite checks
  setup        Same as doctor
  list         List chat rooms
  open         Open a room by number or name
  read         Read messages from the current room
  send         Send a message when the user explicitly asked for it
  status       Show connection and session status
  search       Search rooms by name
  up           Move toward older messages
  down         Move toward newer messages
  refresh      Reset to the latest messages
  rooms-next   Show the next page of rooms
  rooms-prev   Show the previous page of rooms
  back         Return to the room list
  windows      Show open KakaoTalk windows
  inbox-scan   Scan the current inbox page and rank unread rooms
  room-resolve Resolve a room query into a concrete room
  session-open Open a conversation session and fetch a snapshot
  session-fetch Fetch latest, older, or newer messages for a session
  session-watch Poll for new reply deltas
  session-reply Send a reply with session freshness checks
  session-close Close and release a session
  help         Show this help

Options:
  --json       Return structured JSON output for agent harnesses
"""


def maybe_reexec() -> None:
    if not VENV_PYTHON.exists():
        return

    venv_root = VENV_PYTHON.parent.parent.resolve()
    if Path(sys.prefix).resolve() == venv_root:
        return

    if os.environ.get("VIRTUAL_ENV") == str(venv_root):
        return

    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])


def print_install_help(module_name: str) -> None:
    rel_install = ".claude/skills/kakao-terminal/scripts/install.sh"
    abs_install = SCRIPT_DIR / "install.sh"
    print(f"Missing dependency: {module_name}")
    print(f"Install the bundled runtime with `bash {rel_install}`.")
    print(f"If this skill is installed globally, run `bash {abs_install}` instead.")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].lower() in {"help", "-h", "--help"}:
        print(HELP_TEXT)
        return

    maybe_reexec()
    sys.path.insert(0, str(LIB_DIR))

    if args and args[0].lower() == "doctor":
        args = ["setup", *args[1:]]

    try:
        from kakao_cli import main as cli_main
    except ModuleNotFoundError as exc:
        print_install_help(exc.name)
        raise SystemExit(1) from exc

    sys.argv = [sys.argv[0], *args]
    cli_main()


if __name__ == "__main__":
    main()
