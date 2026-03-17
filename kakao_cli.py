#!/usr/bin/env python3
"""
Claude Code Skills CLI wrapper for kakao-terminal.
Provides state management and prerequisite checks for Claude integration.
"""
import sys
import json
import time
import random
import subprocess
from pathlib import Path
from typing import Optional

# Import kakao_bridge from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from kakao_bridge import KakaoBridge

STATE_FILE = Path.home() / ".kakao-terminal-state.json"


def load_state() -> dict:
    """Load state from file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "current_room": None,
        "session_sends": 0,
        "last_room_index": None,
        "room_offset": 0,
        "msg_offset": 0,
        "in_chat": False
    }


def save_state(state: dict) -> None:
    """Save state to file."""
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except IOError:
        pass


def cmd_setup() -> None:
    """Check prerequisites for KakaoTalk integration."""
    print("=== KakaoTalk Prerequisites Check ===\n")

    # 1. KakaoTalk running check
    result = subprocess.run(['pgrep', '-x', 'KakaoTalk'], capture_output=True, text=True)
    if result.stdout.strip():
        print("\u2713 KakaoTalk is running")
    else:
        print("\u2717 KakaoTalk is not running")
        print("  \u2192 Launch KakaoTalk and log in first")
        return

    # 2. Accessibility permission check
    bridge = KakaoBridge()
    try:
        app = bridge._get_ax_app()
        windows = bridge._ax_val(app, 'AXWindows')
        print("\u2713 Accessibility permission granted")
    except Exception:
        print("\u2717 Accessibility permission denied")
        print("  \u2192 System Preferences > Privacy & Security > Accessibility")
        print("  \u2192 Add your terminal app (Terminal.app, iTerm2, VS Code, etc.)")
        return

    # 3. Window check
    if not windows:
        print("\u2717 No KakaoTalk windows found")
        print("  \u2192 Open KakaoTalk from the Dock")
        return
    print("\u2713 KakaoTalk window is open")

    # 4. Chats tab check
    rooms = bridge.get_chat_rooms(limit=1)
    if rooms:
        print("\u2713 Chats tab is active")
        print("\n\U0001F389 All prerequisites met! Use /kakao-list to see rooms.")
    else:
        print("\u2717 Cannot read chat list")
        print("  \u2192 Make sure the 'Chats' tab is selected (not Friends/More)")


def cmd_list(limit: int = 10, offset: int = -1) -> None:
    """List chat rooms."""
    bridge = KakaoBridge()
    state = load_state()

    # Use provided offset or state offset (-1 means use state)
    if offset < 0:
        offset = state.get("room_offset", 0)

    rooms = bridge.get_chat_rooms(limit=limit, offset=offset)

    if not rooms:
        print(f"\u2717 {bridge.diagnose_no_rooms()}")
        return

    # Update state
    state["room_offset"] = offset
    state["in_chat"] = False
    save_state(state)

    print(f"=== Chat Rooms ({offset + 1}-{offset + len(rooms)}) ===\n")
    for i, r in enumerate(rooms, offset + 1):
        unread = f" ({r.unread} unread)" if r.unread > 0 else ""
        preview = r.last_message[:30] + "..." if len(r.last_message) > 30 else r.last_message
        if preview:
            print(f"{i}. {r.name}{unread} - {preview}")
        else:
            print(f"{i}. {r.name}{unread}")


def cmd_open(target: str) -> None:
    """Open a chat room by number or name."""
    bridge = KakaoBridge()
    state = load_state()

    if target.isdigit():
        idx = int(target)
        rooms = bridge.get_chat_rooms(limit=idx + 5, offset=0)
        if idx < 1 or idx > len(rooms):
            print(f"\u2717 Invalid room number: {idx}")
            print(f"  \u2192 Use /kakao-list to see available rooms")
            return

        room = rooms[idx - 1]
        result = bridge.open_room_by_index(room.row_index, room.name)
        if result:
            state["current_room"] = room.name
            state["last_room_index"] = idx
            state["msg_offset"] = 0
            state["in_chat"] = True
            save_state(state)
            print(f"\u2713 Opened: {room.name}")
        else:
            print(f"\u2717 Failed to open room")
            print(f"  \u2192 {bridge.diagnose_no_rooms()}")
    else:
        result = bridge.open_room_by_name(target)
        if result:
            state["current_room"] = target
            state["msg_offset"] = 0
            state["in_chat"] = True
            save_state(state)
            print(f"\u2713 Opened: {target}")
        else:
            print(f"\u2717 Room not found: {target}")
            print(f"  \u2192 Use /kakao-list to see available rooms")


def cmd_read(limit: int = 20, offset: int = -1) -> None:
    """Read messages from the current room."""
    state = load_state()

    if not state.get("current_room"):
        print("\u2717 No room is open")
        print("  \u2192 Use /kakao-open <n> to open a room first")
        return

    # Use provided offset or state offset
    if offset < 0:
        offset = state.get("msg_offset", 0)

    bridge = KakaoBridge()
    bridge.current_room = state["current_room"]
    msgs = bridge.get_chat_messages(limit=limit, msg_offset=offset)

    if not msgs:
        print(f"\u2717 {bridge.diagnose_no_messages()}")
        return

    # Update state
    state["msg_offset"] = offset
    state["in_chat"] = True
    save_state(state)

    offset_str = f" (offset: {offset})" if offset > 0 else ""
    print(f"=== {state['current_room']}{offset_str} ===\n")
    for m in msgs:
        if m.is_date:
            print(f"\n--- {m.text} ---\n")
        else:
            sender = "Me" if m.is_me else (m.sender or "?")
            time_str = f"[{m.time}] " if m.time else ""
            read_str = f" ({m.read_count}명 안읽음)" if m.read_count > 0 else ""

            if m.text == "[Image]":
                print(f"{time_str}{sender}: [Image]{read_str}")
            else:
                print(f"{time_str}{sender}: {m.text}{read_str}")


def cmd_send(message: str) -> None:
    """Send a message to the current room."""
    state = load_state()

    if not state.get("current_room"):
        print("\u2717 No room is open")
        print("  \u2192 Use /kakao-open <n> to open a room first")
        return

    if not message:
        print("\u2717 Message is empty")
        return

    # Rate limiting
    delay = 0.5 + random.uniform(0.1, 0.3)
    time.sleep(delay)

    # Session send count tracking
    state["session_sends"] = state.get("session_sends", 0) + 1
    if state["session_sends"] > 50:
        print("\u26A0\uFE0F Warning: Over 50 messages sent this session. Risk of account restriction!")

    bridge = KakaoBridge()
    bridge.current_room = state["current_room"]
    result = bridge.send_message(message)
    save_state(state)

    if result:
        preview = message[:40] + "..." if len(message) > 40 else message
        print(f"\u2713 Sent: {preview}")
    else:
        print(f"\u2717 Failed to send: {bridge.diagnose_send_failure()}")


def cmd_status() -> None:
    """Show current status."""
    state = load_state()
    bridge = KakaoBridge()

    print("=== KakaoTalk Status ===\n")
    print(f"Current room: {state.get('current_room') or 'None'}")
    print(f"Messages sent this session: {state.get('session_sends', 0)}")

    # Check connection
    diag = bridge.diagnose_no_rooms()
    if "not running" in diag.lower():
        print(f"Connection: \u2717 {diag}")
    elif "permission" in diag.lower():
        print(f"Connection: \u2717 {diag}")
    else:
        rooms = bridge.get_chat_rooms(limit=1)
        if rooms:
            print("Connection: \u2713 Connected")
        else:
            print(f"Connection: \u26A0\uFE0F {diag}")


def cmd_search(query: str) -> None:
    """Search chat rooms by name."""
    bridge = KakaoBridge()
    rooms = bridge.search_rooms(query)

    if not rooms:
        print(f"\u2717 No rooms matching '{query}'")
        return

    print(f"=== Search Results: '{query}' ({len(rooms)} found) ===\n")
    for i, r in enumerate(rooms, 1):
        unread = f" ({r.unread} unread)" if r.unread > 0 else ""
        print(f"{i}. {r.name}{unread}")


def cmd_up(step: int = 10) -> None:
    """Scroll up to see older messages."""
    state = load_state()

    if not state.get("current_room"):
        print("\u2717 No room is open")
        print("  \u2192 Use /kakao-open <n> to open a room first")
        return

    new_offset = state.get("msg_offset", 0) + step
    state["msg_offset"] = new_offset
    save_state(state)

    cmd_read(limit=20, offset=new_offset)


def cmd_down(step: int = 10) -> None:
    """Scroll down to see newer messages."""
    state = load_state()

    if not state.get("current_room"):
        print("\u2717 No room is open")
        print("  \u2192 Use /kakao-open <n> to open a room first")
        return

    new_offset = max(0, state.get("msg_offset", 0) - step)
    state["msg_offset"] = new_offset
    save_state(state)

    cmd_read(limit=20, offset=new_offset)


def cmd_refresh() -> None:
    """Refresh messages from the current room (reset to latest)."""
    state = load_state()

    if not state.get("current_room"):
        print("\u2717 No room is open")
        print("  \u2192 Use /kakao-open <n> to open a room first")
        return

    state["msg_offset"] = 0
    save_state(state)

    cmd_read(limit=20, offset=0)


def cmd_rooms_next(step: int = 10) -> None:
    """Show next page of chat rooms."""
    state = load_state()
    new_offset = state.get("room_offset", 0) + step
    cmd_list(limit=10, offset=new_offset)


def cmd_rooms_prev(step: int = 10) -> None:
    """Show previous page of chat rooms."""
    state = load_state()
    new_offset = max(0, state.get("room_offset", 0) - step)
    cmd_list(limit=10, offset=new_offset)


def cmd_back() -> None:
    """Go back to chat room list."""
    state = load_state()
    closed = False
    if state.get("current_room"):
        bridge = KakaoBridge()
        bridge.current_room = state["current_room"]
        closed = bridge.close_current_chat()

    state["current_room"] = None
    state["in_chat"] = False
    state["msg_offset"] = 0
    save_state(state)

    if closed:
        print("\u2713 Closed chat and returned to room list")
    else:
        print("\u2713 Back to room list")
        print("  \u2192 Chat window may still be open")
    cmd_list(limit=10, offset=state.get("room_offset", 0))


def cmd_windows() -> None:
    """Show list of open KakaoTalk windows."""
    bridge = KakaoBridge()

    try:
        windows = bridge.get_open_windows()
    except Exception as e:
        print(f"\u2717 Failed to get windows: {e}")
        return

    if not windows:
        print("\u2717 No KakaoTalk windows found")
        print("  \u2192 Open KakaoTalk from the dock")
        return

    print("=== Open KakaoTalk Windows ===\n")
    for i, w in enumerate(windows, 1):
        name = w["name"] if w["name"] else "(unnamed)"
        print(f"{i}. {name} [{w['type']}]")


def cmd_help() -> None:
    """Show help."""
    print("""kakao-terminal CLI - Claude Code Skills integration

Commands:
  setup       Check prerequisites (KakaoTalk running, accessibility, etc.)
  list        List chat rooms
  open        Open a chat room by number or name
  read        Read messages from the current room
  send        Send a message to the current room
  status      Show current status

Navigation:
  search      Search chat rooms by name
  up          Scroll up to see older messages
  down        Scroll down to see newer messages
  refresh     Refresh messages (go to latest)
  rooms-next  Show next 10 chat rooms
  rooms-prev  Show previous 10 chat rooms
  back        Go back to room list
  windows     Show open KakaoTalk windows

  help        Show this help

Examples:
  python kakao_cli.py setup
  python kakao_cli.py list
  python kakao_cli.py open 3
  python kakao_cli.py open "Friend Name"
  python kakao_cli.py read
  python kakao_cli.py read 50
  python kakao_cli.py send "Hello!"
  python kakao_cli.py search "친구"
  python kakao_cli.py up
  python kakao_cli.py down
  python kakao_cli.py refresh
  python kakao_cli.py rooms-next
  python kakao_cli.py rooms-prev
  python kakao_cli.py back
  python kakao_cli.py windows
  python kakao_cli.py status
""")


def main():
    if len(sys.argv) < 2:
        cmd_help()
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd == "setup":
        cmd_setup()
    elif cmd == "list":
        limit = int(args[0]) if args and args[0].isdigit() else 10
        offset = int(args[1]) if len(args) > 1 and args[1].isdigit() else -1
        cmd_list(limit, offset)
    elif cmd == "open":
        if args:
            cmd_open(" ".join(args))
        else:
            print("\u2717 Usage: open <room_number> or open <room_name>")
    elif cmd == "read":
        limit = int(args[0]) if args and args[0].isdigit() else 20
        cmd_read(limit)
    elif cmd == "send":
        if args:
            cmd_send(" ".join(args))
        else:
            print("\u2717 Usage: send <message>")
    elif cmd == "status":
        cmd_status()
    elif cmd == "search":
        if args:
            cmd_search(" ".join(args))
        else:
            print("\u2717 Usage: search <query>")
    elif cmd == "up":
        step = int(args[0]) if args and args[0].isdigit() else 10
        cmd_up(step)
    elif cmd == "down":
        step = int(args[0]) if args and args[0].isdigit() else 10
        cmd_down(step)
    elif cmd == "refresh":
        cmd_refresh()
    elif cmd in ("rooms-next", "roomsnext"):
        step = int(args[0]) if args and args[0].isdigit() else 10
        cmd_rooms_next(step)
    elif cmd in ("rooms-prev", "roomsprev"):
        step = int(args[0]) if args and args[0].isdigit() else 10
        cmd_rooms_prev(step)
    elif cmd == "back":
        cmd_back()
    elif cmd == "windows":
        cmd_windows()
    elif cmd in ("help", "-h", "--help"):
        cmd_help()
    else:
        print(f"\u2717 Unknown command: {cmd}")
        print("  \u2192 Use 'help' to see available commands")


if __name__ == "__main__":
    main()
