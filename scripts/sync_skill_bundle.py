#!/usr/bin/env python3
"""Sync the distributable kakao-terminal skill runtime from the repo sources."""

from __future__ import annotations

from pathlib import Path
import shutil


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / ".claude" / "skills" / "kakao-terminal"
LIB_DIR = SKILL_ROOT / "scripts" / "lib"
SOURCES = ("kakao_cli.py", "kakao_bridge.py")


def main() -> None:
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    for name in SOURCES:
        src = REPO_ROOT / name
        dst = LIB_DIR / name
        if not src.exists():
            raise FileNotFoundError(f"Missing source file: {src}")
        shutil.copy2(src, dst)
        print(f"synced {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
