# kakao-terminal

Operate KakaoTalk on macOS from the terminal, a TUI, or a single installable AI skill.

`kakao-terminal` is built for people who already live in the terminal and want KakaoTalk access without breaking flow. It reads KakaoTalk through the macOS Accessibility API, keeps the main app in the background, and exposes the same core actions through a local CLI, an interactive TUI, and a public skill package.

간단히 말하면, 카카오톡을 터미널에서 다루고 싶은 사람을 위한 macOS 도구입니다. 방 목록 보기, 채팅 열기, 최근 메시지 읽기, 새로고침, 메시지 보내기 같은 흐름을 CLI와 AI skill 형태로 제공합니다.

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
- Return structured JSON for agent harnesses
- Open session-scoped conversations and watch for replies

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

Agent harness examples:

```bash
python kakao_cli.py --json inbox-scan
python kakao_cli.py --json room-resolve "Customer Name"
python kakao_cli.py --json session-open "Customer Name"
python kakao_cli.py --json session-fetch conv_0001 latest 20
python kakao_cli.py --json session-watch conv_0001 60 3 5
python kakao_cli.py --json session-reply conv_0001 "Hello"
python kakao_cli.py --json session-close conv_0001
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

## Agent harness surface

For AI agents, the recommended surface is the JSON mode plus the session-oriented commands.

- `inbox-scan`: read the current room page and highlight unread candidates
- `room-resolve`: resolve a user query into a concrete room
- `session-open`: open a room and return a structured transcript snapshot
- `session-fetch`: page latest, older, or newer messages without manually juggling offsets
- `session-watch`: poll for new inbound messages and return only deltas
- `session-reply`: verify the latest transcript and send a reply safely
- `session-close`: release the room session and close the chat window when possible

These commands are meant to be used with `--json` so an agent can parse room metadata, messages, cursors, and session ids directly instead of scraping human-readable terminal output.

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

## Disclaimer

Use this project at your own risk.

This repository is provided for personal experimentation, research, and developer workflow automation. The author does not guarantee compatibility with KakaoTalk, does not guarantee account safety, and is not responsible for account restrictions, policy violations, message delivery issues, data loss, or any direct or indirect damage resulting from use of this project.

If you use message automation features, you are solely responsible for checking the applicable KakaoTalk terms, policies, workplace rules, and local laws before using them.

한국어로도 분명히 적어두면, 이 프로젝트 사용에 따른 책임은 전적으로 사용자에게 있습니다. 카카오톡 이용 제한, 계정 정지, 정책 위반, 메시지 오작동, 데이터 손실 등 사용으로 인해 발생하는 문제에 대해 작성자는 책임지지 않습니다.

## Project structure

```text
kakao_bridge.py                 Core Accessibility bridge
kakao_cli.py                    Local CLI entrypoint
app.py                          Textual TUI
scripts/sync_skill_bundle.py    Sync bundled skill runtime
.claude/skills/kakao-terminal/  Public distributable skill
internal/legacy-skills/         Archived micro-skills
```
