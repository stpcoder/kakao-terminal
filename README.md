# kakao-terminal

Operate KakaoTalk on macOS from the terminal, a TUI, or a single installable AI skill.

`kakao-terminal` is built for people who already live in the terminal and want KakaoTalk access without breaking flow. It reads KakaoTalk through the macOS Accessibility API, keeps the main app in the background, and exposes the same core actions through both a local CLI and a public skill package.

## Why it stands out

- One product-level skill instead of fragmented sub-command skills
- Reads rooms and messages without hardcoding the author's local paths
- Works as a local developer tool and as a marketplace-installable skill
- Includes a setup check for KakaoTalk, Accessibility permission, and chat visibility
- Keeps the install path explicit, so agents can recover from setup issues instead of failing silently

## What you can do

- List KakaoTalk rooms
- Open a room by number or name
- Read recent messages
- Send a message when explicitly requested
- Search rooms
- Move older or newer through the current chat
- Refresh to the latest messages
- Inspect open KakaoTalk windows
- Run a doctor check before normal use

## Install as a skill

SkillHub-style install target:

```bash
npx skillhub install stpcoder/kakao-terminal/kakao-terminal --project
```

After installation:

```bash
bash .claude/skills/kakao-terminal/scripts/install.sh
python3 .claude/skills/kakao-terminal/scripts/run.py doctor
python3 .claude/skills/kakao-terminal/scripts/run.py list
```

Public skill entrypoint:

```text
.claude/skills/kakao-terminal/
```

The repository intentionally exposes one public skill. Older micro-skills were moved to `internal/legacy-skills/` so indexers do not pick up `kakao-down` or another partial wrapper as the main artifact.

## Install for local development

```bash
git clone https://github.com/stpcoder/kakao-terminal.git
cd kakao-terminal
./setup.sh
source venv/bin/activate
```

CLI examples:

```bash
python kakao_cli.py setup
python kakao_cli.py list
python kakao_cli.py open 3
python kakao_cli.py read 30
python kakao_cli.py send "hello"
python kakao_cli.py refresh
```

TUI:

```bash
python app.py
```

## Requirements

- macOS 12 or newer
- KakaoTalk for Mac installed and signed in
- Python 3.10 or newer
- Accessibility permission granted to the terminal or editor host
- KakaoTalk open with the Chats tab visible

The public skill setup checklist lives in [`.claude/skills/kakao-terminal/references/prereqs.md`](/Users/taehoje/space/kakao-terminal/.claude/skills/kakao-terminal/references/prereqs.md).

## Public skill layout

```text
.claude/skills/kakao-terminal/
├── agents/openai.yaml
├── SKILL.md
├── references/prereqs.md
└── scripts/
    ├── install.sh
    ├── requirements.txt
    ├── run.py
    └── lib/
        ├── kakao_bridge.py
        └── kakao_cli.py
```

`scripts/run.py` is the stable entrypoint for agents. `scripts/install.sh` provisions the bundled virtual environment. The bundled runtime is intentionally self-contained so the skill can be installed into other repositories.

## Keep the bundle in sync

If you change the root CLI sources, refresh the bundled skill runtime before publishing:

```bash
python3 scripts/sync_skill_bundle.py
```

Recommended verification flow:

```bash
python3 scripts/sync_skill_bundle.py
bash .claude/skills/kakao-terminal/scripts/install.sh
python3 .claude/skills/kakao-terminal/scripts/run.py doctor
python3 .claude/skills/kakao-terminal/scripts/run.py list
```

Then test a fresh install in another project:

```bash
npx skillhub install stpcoder/kakao-terminal/kakao-terminal --project
```

## Safety

Automated message sending may violate KakaoTalk policy or trigger account restrictions.

Current safeguards:

- Rate limiting before send
- Random jitter before send
- Session send-count warning
- Explicit doctor and setup flow

## Project structure

```text
kakao_bridge.py                 Core Accessibility bridge
kakao_cli.py                    Local CLI entrypoint
app.py                          Textual TUI
scripts/sync_skill_bundle.py    Sync bundled skill runtime
.claude/skills/kakao-terminal/  Public distributable skill
internal/legacy-skills/         Archived micro-skills
```
