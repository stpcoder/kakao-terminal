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
- Run approval-gated agent workflows from shell scripts

## Install as a skill

SkillHub-style install target:

```bash
npx skillhub install stpcoder/kakao-terminal/kakao-terminal --project
```

After installation:

```bash
bash .claude/skills/kakao-terminal/scripts/install.sh
python3 .claude/skills/kakao-terminal/scripts/run.py doctor
python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan
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
python kakao_cli.py --json session-close conv_0001
python kakao_cli.py --json sessions-list 30
python kakao_cli.py --json sessions-cleanup 30
python kakao_cli.py --json sessions-cleanup --force
```

Long-running automation:

```bash
python kakao_cli.py daemon-run 5 10 5 30
python kakao_cli.py event-watch conv_0001 3 5 30
```

Approval-gated scenario wrappers:

```bash
mkdir -p logs

./scripts/triage.sh | tee logs/triage.json
./scripts/review.sh | tee logs/review.json
./scripts/monitor.sh | tee logs/monitor.json

# Draft only. This must not send.
./scripts/safe_reply.sh | tee logs/safe_reply.json

# Explicitly approved send path. Use only for a real approved message.
./scripts/approve_send.sh "Room Name" "Approved message text" | tee logs/approve_send.json
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
- `event-watch`: keep one session open and stream NDJSON delta events continuously
- `session-reply`: verify the latest transcript and send a reply safely
- `session-close`: release the room session and close the chat window when possible
- `sessions-list`: inspect stored agent sessions and identify stale ones
- `sessions-cleanup`: clean up stale or all lingering sessions
- `daemon-run`: keep a long-lived inbox/session daemon running and emit NDJSON events for inbox changes and active session updates

These commands are meant to be used with `--json` so an agent can parse room metadata, messages, cursors, and session ids directly instead of scraping human-readable terminal output.

`event-watch` and `daemon-run` are long-running event streams. They emit newline-delimited JSON events so an agent can react to inbox changes, message deltas, heartbeats, and connectivity state changes without repeatedly invoking one-shot commands itself.

## Recommended agent workflows

There are two reply modes. Keep them distinct.

### 1. Read-only or draft-only mode

Use this for triage, review, or any workflow that must not send without approval.

```bash
python kakao_cli.py --json inbox-scan
python kakao_cli.py --json session-open "Customer Name"
python kakao_cli.py --json session-fetch conv_0001 latest 20
python kakao_cli.py --json session-close conv_0001
```

Shell scenario:

```bash
./scripts/safe_reply.sh | tee logs/safe_reply.json
```

Expected behavior:

- Reads one room
- May produce a reply candidate
- Must not call `session-reply`
- Closes the session before finishing

### 2. Approved send mode

Use this only after a human has approved the exact room target and final reply text.

```bash
./scripts/approve_send.sh "Room Name" "Approved message text" | tee logs/approve_send.json
```

Expected behavior:

- Re-checks setup
- Re-opens the approved room
- Re-reads recent context
- Sends exactly the approved message
- Closes the session before finishing

This split exists to make the approval boundary explicit. `safe_reply.sh` is for drafting and review. `approve_send.sh` is the only shell scenario that should send.

Recommended quick path:

```bash
python kakao_cli.py --json inbox-scan
python kakao_cli.py --json session-open "Customer Name"
python kakao_cli.py --json session-fetch conv_0001 latest 20
python kakao_cli.py --json session-close conv_0001
```

Manual approved send path:

```bash
python kakao_cli.py --json room-resolve "Customer Name"
python kakao_cli.py --json session-open "Customer Name"
python kakao_cli.py --json session-fetch conv_0001 latest 20
python kakao_cli.py --json session-reply conv_0001 "Approved message text"
python kakao_cli.py --json session-close conv_0001
```

## Scenario scripts

The repository includes shell entrypoints that run OpenAI-compatible tool-calling against the public skill runner.

- `./scripts/triage.sh`
  Check readiness, scan inbox, pick one room, open it, and summarize what needs attention.
- `./scripts/review.sh`
  Open one room and read the current conversation without replying.
- `./scripts/monitor.sh`
  Validate daemon/event monitoring and inspect NDJSON events.
- `./scripts/safe_reply.sh`
  Draft-only reply workflow. No sending allowed.
- `./scripts/approve_send.sh "<room>" "<message>"`
  Explicitly approved send workflow. This is the only wrapper that should send.
- `./scripts/list_kakao_agent_scenarios.sh`
  Print available scenario names and descriptions.
- `./scripts/list_kakao_agent_tools.sh`
  Print the structured tool list that the scenario harness exposes to the model.

These wrappers are intended to run in a local macOS GUI terminal session that already has Accessibility permission. They are not meant for SSH-only execution.

## Logs and verification

The shell scenarios print a JSON report to stdout. Save the run with `tee` if you want to inspect it later.

```bash
./scripts/review.sh | tee logs/review.json
```

What to check in the saved report:

- `transcript`
  The exact tool calls the model made
- `final_message`
  The model's operational summary
- `cleanup`
  Automatic session closing performed by the harness

Useful success checks:

- `triage` / `review`
  `kakao_session_open` should succeed and include `messages`
- `monitor`
  `kakao_daemon_run_sample` should emit `daemon_started`, `connection_state`, and inbox or session delta events
- `safe_reply`
  Must not contain `kakao_session_reply`
- `approve_send`
  Must contain `kakao_session_reply` and then `kakao_session_close`

## Stale session cleanup

Scenario wrappers now close the sessions they open. Older test sessions or interrupted runs can still leave state behind in `~/.kakao-terminal-state.json`.

Inspect current stored sessions:

```bash
python kakao_cli.py --json sessions-list 30
```

Clean up sessions older than 30 minutes:

```bash
python kakao_cli.py --json sessions-cleanup 30
```

Force-close every stored session:

```bash
python kakao_cli.py --json sessions-cleanup --force
```

Recommended use:

- Run `sessions-list` before long monitoring sessions if old tests have accumulated
- Run `sessions-cleanup --force` once after major refactors or interrupted manual testing
- Let normal scenario wrappers handle cleanup for sessions they create

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
python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan
```

Then test a fresh install in another project:

```bash
npx skillhub install stpcoder/kakao-terminal/kakao-terminal --project
```

## Safety

Automated message sending may violate KakaoTalk policy or trigger account restrictions.

Current safeguards:

- Explicit `doctor` and setup flow
- Session-scoped JSON commands instead of raw UI scripting only
- Draft-only flow separated from approved send flow
- Approved send wrapper that re-opens and re-reads context before sending
- Session cleanup after scenario completion

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
scripts/openai_tool_calling_harness.py  OpenAI-compatible tool-calling harness
scripts/*.sh                    Scenario wrappers for agent workflows
scripts/sync_skill_bundle.py    Sync bundled skill runtime
.claude/skills/kakao-terminal/  Public distributable skill
internal/legacy-skills/         Archived micro-skills
```
