#!/usr/bin/env python3
"""
Claude Code Skills CLI wrapper for kakao-terminal.
Provides state management, structured output, and agent-focused session workflows.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# Import kakao_bridge lazily so help and docs commands still work when
# macOS accessibility dependencies are not available in the current interpreter.
sys.path.insert(0, str(Path(__file__).parent))

if TYPE_CHECKING:
    from kakao_bridge import ChatRoom, KakaoBridge, Message

BRIDGE_IMPORT_ERROR: Optional[Exception] = None

STATE_FILE = Path.home() / ".kakao-terminal-state.json"
JSON_MODE = False


def _default_state() -> dict:
    return {
        "current_room": None,
        "current_window_title": None,
        "session_sends": 0,
        "last_room_index": None,
        "room_offset": 0,
        "msg_offset": 0,
        "in_chat": False,
        "agent_sessions": {},
        "next_session_id": 1,
    }


def load_state() -> dict:
    """Load state from file."""
    state = _default_state()
    if STATE_FILE.exists():
        try:
            loaded = json.loads(STATE_FILE.read_text())
            if isinstance(loaded, dict):
                state.update(loaded)
        except (json.JSONDecodeError, IOError):
            pass
    state.setdefault("agent_sessions", {})
    state.setdefault("next_session_id", 1)
    return state


def save_state(state: dict) -> None:
    """Save state to file."""
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except IOError:
        pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def print_payload(payload: dict, text_renderer) -> None:
    if JSON_MODE:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        text_renderer(payload)


def emit_error(command: str, message: str, details: Optional[dict] = None) -> dict:
    payload = {
        "ok": False,
        "command": command,
        "error": {
            "message": message,
        },
    }
    if details:
        payload["error"].update(details)
    return payload


def get_bridge_class():
    global BRIDGE_IMPORT_ERROR
    try:
        from kakao_bridge import KakaoBridge
    except ModuleNotFoundError as exc:
        BRIDGE_IMPORT_ERROR = exc
        raise
    return KakaoBridge


def create_bridge():
    try:
        bridge_cls = get_bridge_class()
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Missing macOS accessibility dependency: {exc.name}. "
            "Run this CLI with the project venv or the bundled skill runtime."
        ) from exc
    return bridge_cls()


def serialize_room(room: Any, index: Optional[int] = None) -> dict:
    return {
        "index": index,
        "row_index": room.row_index,
        "name": room.name,
        "time": room.time,
        "last_message": room.last_message,
        "unread": room.unread,
    }


def serialize_message(message: Any) -> dict:
    return {
        "sender": message.sender,
        "text": message.text,
        "time": message.time,
        "is_me": message.is_me,
        "read_count": message.read_count,
        "is_date": message.is_date,
    }


def summarize_message_data(message: dict) -> str:
    if message["is_date"]:
        return f"--- {message['text']} ---"
    sender = "Me" if message["is_me"] else (message["sender"] or "?")
    time_str = f"[{message['time']}] " if message["time"] else ""
    read_str = f" ({message['read_count']}명 안읽음)" if message["read_count"] > 0 else ""
    body = "[Image]" if message["text"] == "[Image]" else message["text"]
    return f"{time_str}{sender}: {body}{read_str}"


def messages_signature(messages: List[Any], tail: int = 5) -> List[str]:
    keys = []
    for message in messages[-tail:]:
        keys.append(
            json.dumps(
                {
                    "sender": message.sender,
                    "text": message.text,
                    "time": message.time,
                    "is_me": message.is_me,
                    "is_date": message.is_date,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return keys


def rooms_signature(rooms: List[dict]) -> List[str]:
    keys = []
    for room in rooms:
        keys.append(
            json.dumps(
                {
                    "name": room["name"],
                    "unread": room["unread"],
                    "row_index": room["row_index"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return keys


def clone_session_view(session: dict) -> dict:
    return {
        "session_id": session["session_id"],
        "room_name": session["room_name"],
        "window_title": session.get("window_title"),
        "room_row_index": session.get("room_row_index"),
        "room_index": session.get("room_index"),
        "msg_offset": session.get("msg_offset", 0),
        "last_fetch_limit": session.get("last_fetch_limit", 20),
        "opened_at": session.get("opened_at"),
        "last_seen_at": session.get("last_seen_at"),
        "at_latest": session.get("at_latest", True),
    }


def next_session_id(state: dict) -> str:
    counter = int(state.get("next_session_id", 1))
    state["next_session_id"] = counter + 1
    return f"conv_{counter:04d}"


def resolve_room_target(bridge: KakaoBridge, target: str) -> Tuple[Optional[ChatRoom], List[ChatRoom], str]:
    """Resolve a room target into a concrete room.

    Returns (selected_room, candidate_rooms, resolution_mode)
    """
    if target.isdigit():
        idx = int(target)
        rooms = bridge.get_chat_rooms(limit=idx + 5, offset=0)
        if 1 <= idx <= len(rooms):
            return rooms[idx - 1], rooms, "index"
        return None, rooms, "index"

    rooms = bridge.search_rooms(target)
    if not rooms:
        return None, [], "search"

    exact_matches = [room for room in rooms if room.name == target]
    if len(exact_matches) == 1:
        return exact_matches[0], rooms, "exact"
    if len(exact_matches) > 1:
        return None, exact_matches, "exact-ambiguous"
    if len(rooms) == 1:
        return rooms[0], rooms, "search"
    return None, rooms, "search-ambiguous"


def get_session_or_error(state: dict, session_id: str, command: str) -> Tuple[Optional[dict], Optional[dict]]:
    sessions = state.get("agent_sessions", {})
    session = sessions.get(session_id)
    if session:
        return session, None
    return None, emit_error(command, f"Unknown session: {session_id}", {"session_id": session_id})


def apply_room_context(bridge, room_name: Optional[str], window_title: Optional[str] = None) -> None:
    bridge.current_room = room_name
    bridge.current_window_title = window_title


def emit_stream_event(event_type: str, **data: Any) -> None:
    payload = {
        "event": event_type,
        "timestamp": now_iso(),
        **data,
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def render_setup(payload: dict) -> None:
    print("=== KakaoTalk Prerequisites Check ===\n")
    checks = payload["checks"]
    if checks["running"]:
        print("✓ KakaoTalk is running")
    else:
        print("✗ KakaoTalk is not running")
        print("  → Launch KakaoTalk and log in first")
        return

    if checks["accessibility"]:
        print("✓ Accessibility permission granted")
    else:
        print("✗ Accessibility permission denied")
        print("  → System Preferences > Privacy & Security > Accessibility")
        print("  → Add your terminal app (Terminal.app, iTerm2, VS Code, etc.)")
        return

    if checks["window_open"]:
        print("✓ KakaoTalk window is open")
    else:
        print("✗ No KakaoTalk windows found")
        print("  → Open KakaoTalk from the Dock")
        return

    if checks["chats_tab"]:
        print("✓ Chats tab is active")
        print("\nAll prerequisites met. You can start browsing rooms.")
    else:
        print("✗ Cannot read chat list")
        print("  → Make sure the 'Chats' tab is selected (not Friends/More)")


def render_list(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    offset = payload["offset"]
    rooms = payload["rooms"]
    print(f"=== Chat Rooms ({offset + 1}-{offset + len(rooms)}) ===\n")
    for room in rooms:
        unread = f" ({room['unread']} unread)" if room["unread"] > 0 else ""
        preview = room["last_message"][:30] + "..." if len(room["last_message"]) > 30 else room["last_message"]
        if preview:
            print(f"{room['index']}. {room['name']}{unread} - {preview}")
        else:
            print(f"{room['index']}. {room['name']}{unread}")


def render_open(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print(f"✓ Opened: {payload['room']['name']}")


def render_read(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    room_name = payload["room_name"]
    offset = payload["cursor"]["msg_offset"]
    offset_str = f" (offset: {offset})" if offset > 0 else ""
    print(f"=== {room_name}{offset_str} ===\n")
    for message in payload["messages"]:
        if message["is_date"]:
            print(f"\n--- {message['text']} ---\n")
        else:
            sender = "Me" if message["is_me"] else (message["sender"] or "?")
            time_str = f"[{message['time']}] " if message["time"] else ""
            read_str = f" ({message['read_count']}명 안읽음)" if message["read_count"] > 0 else ""
            body = "[Image]" if message["text"] == "[Image]" else message["text"]
            print(f"{time_str}{sender}: {body}{read_str}")


def render_send(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print(f"✓ Sent: {payload['preview']}")


def render_status(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print("=== KakaoTalk Status ===\n")
    print(f"Current room: {payload['current_room'] or 'None'}")
    print(f"Messages sent this session: {payload['session_sends']}")
    if payload["connected"]:
        print("Connection: ✓ Connected")
    else:
        print(f"Connection: ⚠ {payload['connection_message']}")
    print(f"Agent sessions: {payload['agent_session_count']}")


def render_search(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    query = payload["query"]
    rooms = payload["rooms"]
    print(f"=== Search Results: '{query}' ({len(rooms)} found) ===\n")
    for room in rooms:
        unread = f" ({room['unread']} unread)" if room["unread"] > 0 else ""
        print(f"{room['index']}. {room['name']}{unread}")


def render_back(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    if payload["closed"]:
        print("✓ Closed chat and returned to room list")
    else:
        print("✓ Back to room list")
        print("  → Chat window may still be open")
    render_list(payload["list"])


def render_windows(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print("=== Open KakaoTalk Windows ===\n")
    for idx, window in enumerate(payload["windows"], 1):
        name = window["name"] if window["name"] else "(unnamed)"
        print(f"{idx}. {name} [{window['type']}]")


def render_inbox_scan(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print(f"=== Inbox Scan ({payload['offset'] + 1}-{payload['offset'] + len(payload['rooms'])}) ===\n")
    for room in payload["rooms"]:
        unread = f" ({room['unread']} unread)" if room["unread"] > 0 else ""
        print(f"{room['index']}. {room['name']}{unread}")
    if payload["recommended"]:
        print("\nRecommended:")
        for room in payload["recommended"]:
            print(f"- {room['name']} ({room['unread']} unread)")


def render_room_resolve(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    room = payload["room"]
    print(f"✓ Resolved '{payload['query']}' -> {room['name']} (row {room['row_index']})")
    if payload["ambiguous"]:
        print("  → Multiple matches were found; the first match was selected")


def render_session_open(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print(f"✓ Session {payload['session']['session_id']} opened for {payload['room']['name']}")
    print("")
    for message in payload["messages"]:
        print(summarize_message_data(message))


def render_session_fetch(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    session = payload["session"]
    cursor = payload["cursor"]
    print(f"=== {session['room_name']} [{session['session_id']}] (offset {cursor['msg_offset']}) ===\n")
    for message in payload["messages"]:
        print(summarize_message_data(message))


def render_session_watch(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    if payload["status"] == "timed_out":
        print(f"✓ No new messages for {payload['waited_seconds']}s")
        return
    print(f"✓ Detected {len(payload['new_messages'])} new message(s)")
    print("")
    for message in payload["new_messages"]:
        print(summarize_message_data(message))


def render_session_reply(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    if payload["status"] == "stale_context":
        print("✗ Session context is stale. Refresh the conversation before sending.")
        return
    if payload["status"] == "sent_unverified":
        print(f"✓ Reply sent in {payload['session']['room_name']}, but echo verification timed out: {payload['preview']}")
        return
    print(f"✓ Sent reply in {payload['session']['room_name']}: {payload['preview']}")


def render_session_close(payload: dict) -> None:
    if not payload["ok"]:
        print(f"✗ {payload['error']['message']}")
        return
    print(f"✓ Closed session {payload['session_id']}")
    if payload["chat_closed"]:
        print("  → KakaoTalk chat window was closed")


def cmd_setup() -> dict:
    """Check prerequisites for KakaoTalk integration."""
    checks = {
        "running": False,
        "accessibility": False,
        "window_open": False,
        "chats_tab": False,
    }

    result = subprocess.run(["pgrep", "-x", "KakaoTalk"], capture_output=True, text=True)
    checks["running"] = bool(result.stdout.strip())
    if not checks["running"]:
        return {
            "ok": False,
            "command": "setup",
            "checks": checks,
            "error": {"message": "KakaoTalk is not running"},
        }

    bridge = create_bridge()
    checks["accessibility"] = bridge.check_accessibility_permission()
    if not checks["accessibility"]:
        return {
            "ok": False,
            "command": "setup",
            "checks": checks,
            "error": {"message": "Accessibility permission denied"},
        }

    try:
        app = bridge._get_ax_app()
        windows = bridge._ax_val(app, "AXWindows")
    except Exception:
        return {
            "ok": False,
            "command": "setup",
            "checks": checks,
            "error": {"message": "Cannot access KakaoTalk accessibility tree"},
        }

    checks["window_open"] = bool(windows)
    if not checks["window_open"]:
        return {
            "ok": False,
            "command": "setup",
            "checks": checks,
            "error": {"message": "No KakaoTalk windows found"},
        }

    rooms = bridge.get_chat_rooms(limit=1)
    checks["chats_tab"] = bool(rooms)
    if not checks["chats_tab"]:
        return {
            "ok": False,
            "command": "setup",
            "checks": checks,
            "error": {"message": "Cannot read chat list"},
        }

    return {
        "ok": True,
        "command": "setup",
        "checks": checks,
        "checked_at": now_iso(),
    }


def cmd_list(limit: int = 10, offset: int = -1) -> dict:
    """List chat rooms."""
    bridge = create_bridge()
    state = load_state()
    if offset < 0:
        offset = state.get("room_offset", 0)

    rooms = bridge.get_chat_rooms(limit=limit, offset=offset)
    if not rooms:
        return emit_error("list", bridge.diagnose_no_rooms(), {"offset": offset, "limit": limit})

    state["room_offset"] = offset
    state["in_chat"] = False
    save_state(state)

    return {
        "ok": True,
        "command": "list",
        "offset": offset,
        "limit": limit,
        "rooms": [serialize_room(room, index=offset + idx + 1) for idx, room in enumerate(rooms)],
    }


def cmd_open(target: str) -> dict:
    """Open a chat room by number or name."""
    bridge = create_bridge()
    state = load_state()
    room, candidates, mode = resolve_room_target(bridge, target)
    if not room:
        details = {
            "target": target,
            "matches": [serialize_room(candidate, index=idx + 1) for idx, candidate in enumerate(candidates)],
            "mode": mode,
        }
        message = f"Room target is ambiguous: {target}" if "ambiguous" in mode else f"Room not found: {target}"
        return emit_error("open", message, details)

    result = bridge.open_room_by_index(room.row_index, room.name)
    if not result:
        return emit_error("open", "Failed to open room", {"target": target, "diagnosis": bridge.diagnose_no_rooms()})

    state["current_room"] = room.name
    state["current_window_title"] = bridge.current_window_title
    state["last_room_index"] = room.row_index
    state["msg_offset"] = 0
    state["in_chat"] = True
    save_state(state)

    return {
        "ok": True,
        "command": "open",
        "target": target,
        "resolution_mode": mode,
        "room": serialize_room(room),
        "window_title": bridge.current_window_title,
    }


def cmd_read(limit: int = 20, offset: int = -1) -> dict:
    """Read messages from the current room."""
    state = load_state()
    if not state.get("current_room"):
        return emit_error("read", "No room is open", {"hint": "Use open <room> first"})

    if offset < 0:
        offset = state.get("msg_offset", 0)

    bridge = create_bridge()
    apply_room_context(bridge, state["current_room"], state.get("current_window_title"))
    messages = bridge.get_chat_messages(limit=limit, msg_offset=offset)
    if not messages:
        return emit_error("read", bridge.diagnose_no_messages(), {"room_name": state["current_room"], "msg_offset": offset})

    state["msg_offset"] = offset
    state["in_chat"] = True
    save_state(state)

    return {
        "ok": True,
        "command": "read",
        "room_name": state["current_room"],
        "messages": [serialize_message(message) for message in messages],
        "cursor": {
            "msg_offset": offset,
            "at_latest": offset == 0,
        },
    }


def cmd_send(message: str) -> dict:
    """Send a message to the current room."""
    state = load_state()
    if not state.get("current_room"):
        return emit_error("send", "No room is open", {"hint": "Use open <room> first"})
    if not message:
        return emit_error("send", "Message is empty")

    delay = 0.5 + random.uniform(0.1, 0.3)
    time.sleep(delay)

    state["session_sends"] = state.get("session_sends", 0) + 1
    warning = None
    if state["session_sends"] > 50:
        warning = "Over 50 messages sent this session. Risk of account restriction."

    bridge = create_bridge()
    apply_room_context(bridge, state["current_room"], state.get("current_window_title"))
    result = bridge.send_message(message)
    save_state(state)

    if not result:
        return emit_error("send", bridge.diagnose_send_failure(), {"room_name": state["current_room"]})

    preview = message[:40] + "..." if len(message) > 40 else message
    return {
        "ok": True,
        "command": "send",
        "room_name": state["current_room"],
        "preview": preview,
        "warning": warning,
    }


def cmd_status() -> dict:
    """Show current status."""
    state = load_state()
    bridge = create_bridge()
    diag = bridge.diagnose_no_rooms()
    connected = False
    if "not running" not in diag.lower() and "permission" not in diag.lower():
        connected = bool(bridge.get_chat_rooms(limit=1))

    return {
        "ok": True,
        "command": "status",
        "current_room": state.get("current_room"),
        "session_sends": state.get("session_sends", 0),
        "connected": connected,
        "connection_message": "Connected" if connected else diag,
        "agent_session_count": len(state.get("agent_sessions", {})),
        "agent_sessions": [clone_session_view(session) for session in state.get("agent_sessions", {}).values()],
    }


def cmd_search(query: str) -> dict:
    """Search chat rooms by name."""
    bridge = create_bridge()
    rooms = bridge.search_rooms(query)
    if not rooms:
        return emit_error("search", f"No rooms matching '{query}'", {"query": query})

    return {
        "ok": True,
        "command": "search",
        "query": query,
        "rooms": [serialize_room(room, index=idx + 1) for idx, room in enumerate(rooms)],
    }


def cmd_up(step: int = 10) -> dict:
    """Scroll up to see older messages."""
    state = load_state()
    if not state.get("current_room"):
        return emit_error("up", "No room is open", {"hint": "Use open <room> first"})
    new_offset = state.get("msg_offset", 0) + step
    state["msg_offset"] = new_offset
    save_state(state)
    return cmd_read(limit=20, offset=new_offset)


def cmd_down(step: int = 10) -> dict:
    """Scroll down to see newer messages."""
    state = load_state()
    if not state.get("current_room"):
        return emit_error("down", "No room is open", {"hint": "Use open <room> first"})
    new_offset = max(0, state.get("msg_offset", 0) - step)
    state["msg_offset"] = new_offset
    save_state(state)
    return cmd_read(limit=20, offset=new_offset)


def cmd_refresh() -> dict:
    """Refresh messages from the current room (reset to latest)."""
    state = load_state()
    if not state.get("current_room"):
        return emit_error("refresh", "No room is open", {"hint": "Use open <room> first"})
    state["msg_offset"] = 0
    save_state(state)
    return cmd_read(limit=20, offset=0)


def cmd_rooms_next(step: int = 10) -> dict:
    state = load_state()
    new_offset = state.get("room_offset", 0) + step
    return cmd_list(limit=10, offset=new_offset)


def cmd_rooms_prev(step: int = 10) -> dict:
    state = load_state()
    new_offset = max(0, state.get("room_offset", 0) - step)
    return cmd_list(limit=10, offset=new_offset)


def cmd_back() -> dict:
    state = load_state()
    closed = False
    if state.get("current_room"):
        bridge = create_bridge()
        apply_room_context(bridge, state["current_room"], state.get("current_window_title"))
        closed = bridge.close_current_chat()

    state["current_room"] = None
    state["current_window_title"] = None
    state["in_chat"] = False
    state["msg_offset"] = 0
    save_state(state)

    room_list = cmd_list(limit=10, offset=state.get("room_offset", 0))
    return {
        "ok": room_list["ok"],
        "command": "back",
        "closed": closed,
        "list": room_list,
    }


def cmd_windows() -> dict:
    bridge = create_bridge()
    try:
        windows = bridge.get_open_windows()
    except Exception as exc:
        return emit_error("windows", f"Failed to get windows: {exc}")

    if not windows:
        return emit_error("windows", "No KakaoTalk windows found")

    return {
        "ok": True,
        "command": "windows",
        "windows": windows,
    }


def cmd_inbox_scan(limit: int = 10, offset: int = 0) -> dict:
    listing = cmd_list(limit=limit, offset=offset)
    if not listing["ok"]:
        listing["command"] = "inbox-scan"
        return listing
    recommended = [room for room in listing["rooms"] if room["unread"] > 0]
    recommended.sort(key=lambda room: room["unread"], reverse=True)
    return {
        "ok": True,
        "command": "inbox-scan",
        "offset": listing["offset"],
        "limit": listing["limit"],
        "rooms": listing["rooms"],
        "recommended": recommended[: min(5, len(recommended))],
        "scanned_at": now_iso(),
    }


def cmd_room_resolve(query: str) -> dict:
    bridge = create_bridge()
    room, candidates, mode = resolve_room_target(bridge, query)
    if not room:
        details = {
            "query": query,
            "resolution_mode": mode,
            "matches": [serialize_room(candidate, index=idx + 1) for idx, candidate in enumerate(candidates[:10])],
        }
        message = f"Could not resolve room uniquely: {query}" if "ambiguous" in mode else f"Could not resolve room: {query}"
        return emit_error("room-resolve", message, details)
    return {
        "ok": True,
        "command": "room-resolve",
        "query": query,
        "resolution_mode": mode,
        "ambiguous": len(candidates) > 1 and room.name != query,
        "room": serialize_room(room),
        "matches": [serialize_room(candidate, index=idx + 1) for idx, candidate in enumerate(candidates[:10])],
    }


def cmd_session_open(target: str, limit: int = 20) -> dict:
    state = load_state()
    bridge = create_bridge()
    room, candidates, mode = resolve_room_target(bridge, target)
    if not room:
        details = {
            "target": target,
            "resolution_mode": mode,
            "matches": [serialize_room(candidate, index=idx + 1) for idx, candidate in enumerate(candidates[:10])],
        }
        message = f"Room target is ambiguous: {target}" if "ambiguous" in mode else f"Room not found: {target}"
        return emit_error("session-open", message, details)

    if not bridge.open_room_by_index(room.row_index, room.name):
        return emit_error("session-open", "Failed to open room", {"target": target, "diagnosis": bridge.diagnose_no_rooms()})

    apply_room_context(bridge, room.name, bridge.current_window_title)
    messages = bridge.get_chat_messages(limit=limit, msg_offset=0)
    if not messages:
        return emit_error("session-open", bridge.diagnose_no_messages(), {"target": target, "room_name": room.name})

    session_id = next_session_id(state)
    signature = messages_signature(messages)
    session = {
        "session_id": session_id,
        "room_name": room.name,
        "window_title": bridge.current_window_title,
        "room_row_index": room.row_index,
        "room_index": next((idx + 1 for idx, candidate in enumerate(candidates) if candidate.name == room.name), None),
        "msg_offset": 0,
        "last_fetch_limit": limit,
        "opened_at": now_iso(),
        "last_seen_at": now_iso(),
        "last_seen_signature": signature,
        "at_latest": True,
    }
    state["agent_sessions"][session_id] = session
    state["current_room"] = room.name
    state["current_window_title"] = bridge.current_window_title
    state["msg_offset"] = 0
    state["in_chat"] = True
    save_state(state)

    return {
        "ok": True,
        "command": "session-open",
        "target": target,
        "resolution_mode": mode,
        "room": serialize_room(room),
        "session": clone_session_view(session),
        "window_title": bridge.current_window_title,
        "messages": [serialize_message(message) for message in messages],
        "cursor": {
            "msg_offset": 0,
            "at_latest": True,
        },
    }


def cmd_session_fetch(session_id: str, mode: str = "latest", limit: int = 20, step: int = 10) -> dict:
    state = load_state()
    session, error = get_session_or_error(state, session_id, "session-fetch")
    if error:
        return error

    if mode not in {"latest", "refresh", "older", "newer"}:
        return emit_error("session-fetch", f"Unsupported fetch mode: {mode}", {"mode": mode})

    msg_offset = int(session.get("msg_offset", 0))
    if mode in {"latest", "refresh"}:
        msg_offset = 0
    elif mode == "older":
        msg_offset += step
    elif mode == "newer":
        msg_offset = max(0, msg_offset - step)

    bridge = create_bridge()
    apply_room_context(bridge, session["room_name"], session.get("window_title"))
    retry = 2 if mode in {"latest", "refresh"} else 1
    messages = bridge.get_chat_messages(limit=limit, retry=retry, msg_offset=msg_offset)
    if not messages:
        return emit_error("session-fetch", bridge.diagnose_no_messages(), {"session_id": session_id, "msg_offset": msg_offset})

    session["msg_offset"] = msg_offset
    session["last_fetch_limit"] = limit
    session["at_latest"] = msg_offset == 0
    if msg_offset == 0:
        session["last_seen_signature"] = messages_signature(messages)
        session["last_seen_at"] = now_iso()
    state["agent_sessions"][session_id] = session
    state["current_room"] = session["room_name"]
    state["current_window_title"] = session.get("window_title")
    state["msg_offset"] = msg_offset
    state["in_chat"] = True
    save_state(state)

    return {
        "ok": True,
        "command": "session-fetch",
        "mode": mode,
        "session": clone_session_view(session),
        "messages": [serialize_message(message) for message in messages],
        "cursor": {
            "msg_offset": msg_offset,
            "at_latest": msg_offset == 0,
            "step": step,
        },
    }


def cmd_session_watch(session_id: str, timeout_seconds: int = 60, interval_seconds: int = 3, count: int = 5) -> dict:
    state = load_state()
    session, error = get_session_or_error(state, session_id, "session-watch")
    if error:
        return error

    bridge = create_bridge()
    apply_room_context(bridge, session["room_name"], session.get("window_title"))
    baseline = session.get("last_seen_signature") or []
    baseline_set = set(baseline)
    started = time.time()

    while time.time() - started < timeout_seconds:
        messages = bridge.get_latest_messages_fast(count=count)
        if messages:
            signature = messages_signature(messages, tail=count)
            if signature != baseline:
                new_messages = []
                for message, key in zip(messages[-len(signature):], signature):
                    if key not in baseline_set:
                        new_messages.append(message)

                session["last_seen_signature"] = signature
                session["last_seen_at"] = now_iso()
                session["msg_offset"] = 0
                session["at_latest"] = True
                state["agent_sessions"][session_id] = session
                state["current_room"] = session["room_name"]
                state["current_window_title"] = session.get("window_title")
                state["msg_offset"] = 0
                state["in_chat"] = True
                save_state(state)
                return {
                    "ok": True,
                    "command": "session-watch",
                    "status": "updated",
                    "session": clone_session_view(session),
                    "new_messages": [serialize_message(message) for message in new_messages] if new_messages else [serialize_message(message) for message in messages],
                    "waited_seconds": round(time.time() - started, 2),
                }
        time.sleep(interval_seconds)

    return {
        "ok": True,
        "command": "session-watch",
        "status": "timed_out",
        "session": clone_session_view(session),
        "new_messages": [],
        "waited_seconds": timeout_seconds,
    }


def cmd_session_reply(session_id: str, message: str) -> dict:
    state = load_state()
    session, error = get_session_or_error(state, session_id, "session-reply")
    if error:
        return error
    if not message:
        return emit_error("session-reply", "Message is empty", {"session_id": session_id})

    bridge = create_bridge()
    apply_room_context(bridge, session["room_name"], session.get("window_title"))
    latest_messages = bridge.get_chat_messages(limit=max(10, int(session.get("last_fetch_limit", 20))), msg_offset=0)
    if not latest_messages:
        return emit_error("session-reply", bridge.diagnose_no_messages(), {"session_id": session_id})

    current_signature = messages_signature(latest_messages)
    previous_signature = session.get("last_seen_signature") or []
    if previous_signature and current_signature != previous_signature:
        session["last_seen_signature"] = current_signature
        session["last_seen_at"] = now_iso()
        session["msg_offset"] = 0
        session["at_latest"] = True
        state["agent_sessions"][session_id] = session
        save_state(state)
        return {
            "ok": True,
            "command": "session-reply",
            "status": "stale_context",
            "session": clone_session_view(session),
            "latest_messages": [serialize_message(message) for message in latest_messages[-10:]],
        }

    delay = 0.5 + random.uniform(0.1, 0.3)
    time.sleep(delay)

    state["session_sends"] = state.get("session_sends", 0) + 1
    if not bridge.send_message(message):
        save_state(state)
        return emit_error("session-reply", bridge.diagnose_send_failure(), {"session_id": session_id, "room_name": session["room_name"]})

    verification = []
    verified = False
    deadline = time.time() + 2.0
    while time.time() < deadline:
        verification = bridge.get_latest_messages_fast(count=8)
        if verification:
            signature = messages_signature(verification)
            sent_seen = any(msg.is_me and msg.text == message for msg in verification[-5:])
            if sent_seen or signature != previous_signature:
                verified = sent_seen
                break
        time.sleep(0.25)

    final_messages = verification or latest_messages
    session["last_seen_signature"] = messages_signature(final_messages)
    session["last_seen_at"] = now_iso()
    session["msg_offset"] = 0
    session["at_latest"] = True
    state["agent_sessions"][session_id] = session
    state["current_room"] = session["room_name"]
    state["current_window_title"] = session.get("window_title")
    state["msg_offset"] = 0
    state["in_chat"] = True
    save_state(state)

    preview = message[:40] + "..." if len(message) > 40 else message
    return {
        "ok": True,
        "command": "session-reply",
        "status": "sent" if verified else "sent_unverified",
        "session": clone_session_view(session),
        "preview": preview,
        "verified": verified,
        "verified_messages": [serialize_message(msg) for msg in final_messages],
    }


def cmd_session_close(session_id: str) -> dict:
    state = load_state()
    session, error = get_session_or_error(state, session_id, "session-close")
    if error:
        return error

    bridge = create_bridge()
    apply_room_context(bridge, session["room_name"], session.get("window_title"))
    chat_closed = bridge.close_current_chat()

    del state["agent_sessions"][session_id]
    if state.get("current_room") == session["room_name"]:
        state["current_room"] = None
        state["current_window_title"] = None
        state["msg_offset"] = 0
        state["in_chat"] = False
    save_state(state)

    return {
        "ok": True,
        "command": "session-close",
        "session_id": session_id,
        "chat_closed": chat_closed,
    }


def cmd_event_watch(session_id: str, interval_seconds: int = 3, count: int = 5, heartbeat_seconds: int = 30) -> int:
    """Stream event-like message deltas for a single session forever."""
    state = load_state()
    session, error = get_session_or_error(state, session_id, "event-watch")
    if error:
        emit_stream_event("watch_error", session_id=session_id, error=error["error"])
        return 1

    emit_stream_event(
        "watch_started",
        session_id=session_id,
        room_name=session["room_name"],
        interval_seconds=interval_seconds,
        count=count,
    )

    last_heartbeat = time.time()
    while True:
        state = load_state()
        session, error = get_session_or_error(state, session_id, "event-watch")
        if error:
            emit_stream_event("watch_stopped", session_id=session_id, reason="session_missing")
            return 0

        bridge = create_bridge()
        apply_room_context(bridge, session["room_name"], session.get("window_title"))
        messages = bridge.get_latest_messages_fast(count=count)
        if messages:
            signature = messages_signature(messages, tail=count)
            baseline = session.get("last_seen_signature") or []
            baseline_set = set(baseline)
            if signature != baseline:
                new_messages = []
                for message, key in zip(messages[-len(signature):], signature):
                    if key not in baseline_set:
                        new_messages.append(message)

                session["last_seen_signature"] = signature
                session["last_seen_at"] = now_iso()
                session["msg_offset"] = 0
                session["at_latest"] = True
                state["agent_sessions"][session_id] = session
                state["current_room"] = session["room_name"]
                state["current_window_title"] = session.get("window_title")
                state["msg_offset"] = 0
                state["in_chat"] = True
                save_state(state)

                emit_stream_event(
                    "message_delta",
                    session_id=session_id,
                    room_name=session["room_name"],
                    new_messages=[serialize_message(msg) for msg in new_messages] if new_messages else [serialize_message(msg) for msg in messages],
                )

        now = time.time()
        if now - last_heartbeat >= heartbeat_seconds:
            emit_stream_event(
                "heartbeat",
                session_id=session_id,
                room_name=session["room_name"],
                at_latest=session.get("at_latest", True),
            )
            last_heartbeat = now

        time.sleep(interval_seconds)


def cmd_daemon_run(interval_seconds: int = 5, room_limit: int = 10, watch_count: int = 5, heartbeat_seconds: int = 30) -> int:
    """Run a long-lived inbox/session daemon and emit NDJSON events."""
    emit_stream_event(
        "daemon_started",
        interval_seconds=interval_seconds,
        room_limit=room_limit,
        watch_count=watch_count,
    )

    last_room_signature: List[str] = []
    last_connection_state: Optional[bool] = None
    last_heartbeat = time.time()

    while True:
        state = load_state()
        try:
            bridge = create_bridge()
        except RuntimeError as exc:
            emit_stream_event("daemon_error", error=str(exc))
            return 1

        setup_payload = cmd_setup()
        connected = bool(setup_payload.get("ok"))
        if connected != last_connection_state:
            emit_stream_event(
                "connection_state",
                connected=connected,
                checks=setup_payload.get("checks"),
                error=setup_payload.get("error"),
            )
            last_connection_state = connected

        if connected:
            inbox = cmd_inbox_scan(limit=room_limit, offset=0)
            if inbox["ok"]:
                room_signature = rooms_signature(inbox["rooms"])
                if room_signature != last_room_signature:
                    emit_stream_event(
                        "inbox_changed",
                        rooms=inbox["rooms"],
                        recommended=inbox["recommended"],
                    )
                    last_room_signature = room_signature

            for session_id, session in state.get("agent_sessions", {}).items():
                bridge = create_bridge()
                apply_room_context(bridge, session["room_name"], session.get("window_title"))
                messages = bridge.get_latest_messages_fast(count=watch_count)
                if not messages:
                    continue
                signature = messages_signature(messages, tail=watch_count)
                baseline = session.get("last_seen_signature") or []
                if signature != baseline:
                    baseline_set = set(baseline)
                    new_messages = []
                    for message, key in zip(messages[-len(signature):], signature):
                        if key not in baseline_set:
                            new_messages.append(message)

                    session["last_seen_signature"] = signature
                    session["last_seen_at"] = now_iso()
                    session["msg_offset"] = 0
                    session["at_latest"] = True
                    state["agent_sessions"][session_id] = session
                    state["current_room"] = session["room_name"]
                    state["current_window_title"] = session.get("window_title")
                    state["msg_offset"] = 0
                    state["in_chat"] = True
                    save_state(state)

                    emit_stream_event(
                        "session_message_delta",
                        session_id=session_id,
                        room_name=session["room_name"],
                        new_messages=[serialize_message(msg) for msg in new_messages] if new_messages else [serialize_message(msg) for msg in messages],
                    )

        now = time.time()
        if now - last_heartbeat >= heartbeat_seconds:
            emit_stream_event(
                "daemon_heartbeat",
                connected=connected,
                session_count=len(state.get("agent_sessions", {})),
            )
            last_heartbeat = now

        time.sleep(interval_seconds)


def cmd_help() -> None:
    print(
        """kakao-terminal CLI - human and agent harness surface

Commands:
  setup           Check prerequisites (KakaoTalk running, accessibility, etc.)
  list            List chat rooms
  open            Open a chat room by number or name
  read            Read messages from the current room
  send            Send a message to the current room
  status          Show current status
  search          Search chat rooms by name
  up              Scroll up to see older messages
  down            Scroll down to see newer messages
  refresh         Refresh messages (go to latest)
  rooms-next      Show next 10 chat rooms
  rooms-prev      Show previous 10 chat rooms
  back            Go back to room list
  windows         Show open KakaoTalk windows

Agent harness:
  inbox-scan      Structured inbox scan with recommended unread rooms
  room-resolve    Resolve a room query into a concrete room
  session-open    Open a room and create an agent session
  session-fetch   Fetch latest/older/newer messages for a session
  session-watch   Poll for new messages until timeout
  event-watch     Stream message delta events for one session
  session-reply   Send a message safely for a session
  session-close   Close and remove an agent session
  daemon-run      Run a long-lived inbox/session event daemon

Global options:
  --json          Print structured JSON output

Examples:
  python kakao_cli.py --json inbox-scan
  python kakao_cli.py --json room-resolve "고객"
  python kakao_cli.py --json session-open "고객A"
  python kakao_cli.py --json session-fetch conv_0001 older 20 10
  python kakao_cli.py --json session-watch conv_0001 60 3 5
  python kakao_cli.py event-watch conv_0001 3 5 30
  python kakao_cli.py --json session-reply conv_0001 "Hello"
  python kakao_cli.py --json session-close conv_0001
  python kakao_cli.py daemon-run 5 10 5 30
"""
    )


def parse_global_flags(args: List[str]) -> List[str]:
    global JSON_MODE
    remaining = []
    for arg in args:
        if arg == "--json":
            JSON_MODE = True
        else:
            remaining.append(arg)
    return remaining


def main() -> None:
    args = parse_global_flags(sys.argv[1:])
    if not args:
        cmd_help()
        return

    cmd = args[0].lower()
    rest = args[1:]

    if cmd == "setup":
        print_payload(cmd_setup(), render_setup)
    elif cmd == "list":
        limit = int(rest[0]) if rest and rest[0].isdigit() else 10
        offset = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else -1
        print_payload(cmd_list(limit, offset), render_list)
    elif cmd == "open":
        if rest:
            print_payload(cmd_open(" ".join(rest)), render_open)
        else:
            print_payload(emit_error("open", "Usage: open <room_number> or open <room_name>"), render_open)
    elif cmd == "read":
        limit = int(rest[0]) if rest and rest[0].isdigit() else 20
        print_payload(cmd_read(limit), render_read)
    elif cmd == "send":
        if rest:
            print_payload(cmd_send(" ".join(rest)), render_send)
        else:
            print_payload(emit_error("send", "Usage: send <message>"), render_send)
    elif cmd == "status":
        print_payload(cmd_status(), render_status)
    elif cmd == "search":
        if rest:
            print_payload(cmd_search(" ".join(rest)), render_search)
        else:
            print_payload(emit_error("search", "Usage: search <query>"), render_search)
    elif cmd == "up":
        step = int(rest[0]) if rest and rest[0].isdigit() else 10
        print_payload(cmd_up(step), render_read)
    elif cmd == "down":
        step = int(rest[0]) if rest and rest[0].isdigit() else 10
        print_payload(cmd_down(step), render_read)
    elif cmd == "refresh":
        print_payload(cmd_refresh(), render_read)
    elif cmd in ("rooms-next", "roomsnext"):
        step = int(rest[0]) if rest and rest[0].isdigit() else 10
        print_payload(cmd_rooms_next(step), render_list)
    elif cmd in ("rooms-prev", "roomsprev"):
        step = int(rest[0]) if rest and rest[0].isdigit() else 10
        print_payload(cmd_rooms_prev(step), render_list)
    elif cmd == "back":
        print_payload(cmd_back(), render_back)
    elif cmd == "windows":
        print_payload(cmd_windows(), render_windows)
    elif cmd == "inbox-scan":
        limit = int(rest[0]) if rest and rest[0].isdigit() else 10
        offset = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 0
        print_payload(cmd_inbox_scan(limit, offset), render_inbox_scan)
    elif cmd == "room-resolve":
        if rest:
            print_payload(cmd_room_resolve(" ".join(rest)), render_room_resolve)
        else:
            print_payload(emit_error("room-resolve", "Usage: room-resolve <query>"), render_room_resolve)
    elif cmd == "session-open":
        if rest:
            target = " ".join(rest[:-1]) if len(rest) > 1 and rest[-1].isdigit() else " ".join(rest)
            limit = int(rest[-1]) if len(rest) > 1 and rest[-1].isdigit() else 20
            print_payload(cmd_session_open(target, limit), render_session_open)
        else:
            print_payload(emit_error("session-open", "Usage: session-open <room> [limit]"), render_session_open)
    elif cmd == "session-fetch":
        if rest:
            session_id = rest[0]
            mode = rest[1] if len(rest) > 1 else "latest"
            limit = int(rest[2]) if len(rest) > 2 and rest[2].isdigit() else 20
            step = int(rest[3]) if len(rest) > 3 and rest[3].isdigit() else 10
            print_payload(cmd_session_fetch(session_id, mode, limit, step), render_session_fetch)
        else:
            print_payload(emit_error("session-fetch", "Usage: session-fetch <session_id> [latest|refresh|older|newer] [limit] [step]"), render_session_fetch)
    elif cmd == "session-watch":
        if rest:
            session_id = rest[0]
            timeout_seconds = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 60
            interval_seconds = int(rest[2]) if len(rest) > 2 and rest[2].isdigit() else 3
            count = int(rest[3]) if len(rest) > 3 and rest[3].isdigit() else 5
            print_payload(cmd_session_watch(session_id, timeout_seconds, interval_seconds, count), render_session_watch)
        else:
            print_payload(emit_error("session-watch", "Usage: session-watch <session_id> [timeout] [interval] [count]"), render_session_watch)
    elif cmd == "event-watch":
        if rest:
            session_id = rest[0]
            interval_seconds = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 3
            count = int(rest[2]) if len(rest) > 2 and rest[2].isdigit() else 5
            heartbeat_seconds = int(rest[3]) if len(rest) > 3 and rest[3].isdigit() else 30
            raise SystemExit(cmd_event_watch(session_id, interval_seconds, count, heartbeat_seconds))
        else:
            error = emit_error("event-watch", "Usage: event-watch <session_id> [interval] [count] [heartbeat]")
            if JSON_MODE:
                print(json.dumps(error, ensure_ascii=False, indent=2))
            else:
                print(f"✗ {error['error']['message']}")
    elif cmd == "session-reply":
        if len(rest) >= 2:
            session_id = rest[0]
            print_payload(cmd_session_reply(session_id, " ".join(rest[1:])), render_session_reply)
        else:
            print_payload(emit_error("session-reply", "Usage: session-reply <session_id> <message>"), render_session_reply)
    elif cmd == "session-close":
        if rest:
            print_payload(cmd_session_close(rest[0]), render_session_close)
        else:
            print_payload(emit_error("session-close", "Usage: session-close <session_id>"), render_session_close)
    elif cmd == "daemon-run":
        interval_seconds = int(rest[0]) if rest and rest[0].isdigit() else 5
        room_limit = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 10
        watch_count = int(rest[2]) if len(rest) > 2 and rest[2].isdigit() else 5
        heartbeat_seconds = int(rest[3]) if len(rest) > 3 and rest[3].isdigit() else 30
        raise SystemExit(cmd_daemon_run(interval_seconds, room_limit, watch_count, heartbeat_seconds))
    elif cmd in ("help", "-h", "--help"):
        cmd_help()
    else:
        error = emit_error("unknown", f"Unknown command: {cmd}", {"hint": "Use help to see available commands"})
        if JSON_MODE:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"✗ Unknown command: {cmd}")
            print("  → Use 'help' to see available commands")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        payload = emit_error("runtime", str(exc))
        if JSON_MODE:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"✗ {exc}")
