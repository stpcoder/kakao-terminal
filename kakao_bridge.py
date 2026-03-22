"""
카카오톡 Mac 앱을 Accessibility API로 제어하는 브릿지 (v2)
"""
import subprocess
import time
import re
from typing import List, Optional, Any, Tuple
from dataclasses import dataclass
from Quartz import CGEventCreateKeyboardEvent, CGEventPostToPid
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
)


@dataclass
class ChatRoom:
    name: str
    time: str
    last_message: str
    unread: int = 0
    row_index: int = 0  # actual row index in KakaoTalk table


@dataclass
class Message:
    sender: str
    text: str
    time: str = ""
    is_me: bool = False
    read_count: int = 0  # unread count shown next to message
    is_date: bool = False  # date separator row


class KakaoBridge:
    """macOS Accessibility API를 통해 카카오톡 제어"""

    # Possible main window titles (Korean / English KakaoTalk)
    MAIN_WINDOW_NAMES = ("카카오톡", "KakaoTalk", "Kakao Talk")

    def __init__(self):
        self.current_room: Optional[str] = None
        self.current_window_title: Optional[str] = None
        self.app_name = "KakaoTalk"
        self._last_error: Optional[str] = None  # Last AppleScript error
        self._pid: Optional[int] = None  # KakaoTalk process ID
        self._main_title: Optional[str] = None  # Detected main window title

    def _get_pid(self) -> int:
        """Get KakaoTalk process ID (cached)"""
        if self._pid is None:
            result = subprocess.run(['pgrep', '-x', 'KakaoTalk'], capture_output=True, text=True)
            if result.stdout.strip():
                self._pid = int(result.stdout.strip())
            else:
                raise RuntimeError("KakaoTalk is not running")
        return self._pid

    def _send_key(self, key_code: int) -> None:
        """Send a key event to KakaoTalk in background via CGEventPostToPid"""
        pid = self._get_pid()
        event_down = CGEventCreateKeyboardEvent(None, key_code, True)
        event_up = CGEventCreateKeyboardEvent(None, key_code, False)
        CGEventPostToPid(pid, event_down)
        CGEventPostToPid(pid, event_up)

    # --- Direct AX API helpers (20x faster than AppleScript) ---

    def _ax_val(self, elem: Any, attr: str) -> Any:
        """Get AX attribute value, returns None on failure"""
        err, val = AXUIElementCopyAttributeValue(elem, attr, None)
        return val if err == 0 else None

    def _ax_coord(self, ax_value: Any) -> Tuple[float, float]:
        """Extract (x,y) or (w,h) from AXValueRef"""
        s = str(ax_value)
        m = re.search(r'x:([\d.]+)\s*y:([\d.]+)', s)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = re.search(r'w:([\d.]+)\s*h:([\d.]+)', s)
        if m:
            return float(m.group(1)), float(m.group(2))
        return 0.0, 0.0

    def _get_ax_app(self) -> Any:
        """Get AX application element for KakaoTalk (cached)"""
        if not hasattr(self, '_ax_app') or self._ax_app is None:
            pid = self._get_pid()
            self._ax_app = AXUIElementCreateApplication(pid)
        return self._ax_app

    def _get_main_title(self) -> str:
        """Detect the main window title (cached). Works for both Korean and English."""
        if self._main_title:
            return self._main_title
        app = self._get_ax_app()
        windows = self._ax_val(app, 'AXWindows')
        if windows:
            for win in windows:
                title = self._ax_val(win, 'AXTitle')
                if title and title in self.MAIN_WINDOW_NAMES:
                    self._main_title = title
                    return title
        self._main_title = self.MAIN_WINDOW_NAMES[0]  # fallback
        return self._main_title

    def _is_main_window(self, title: str) -> bool:
        """Check if a window title is the main KakaoTalk window."""
        return title in self.MAIN_WINDOW_NAMES

    def diagnose_no_rooms(self) -> str:
        """Diagnose why get_chat_rooms returned empty. Returns error message."""
        # Check if KakaoTalk is running
        result = subprocess.run(['pgrep', '-x', 'KakaoTalk'], capture_output=True, text=True)
        if not result.stdout.strip():
            return "KakaoTalk is not running. Launch KakaoTalk and log in."

        # Check if main window exists
        try:
            app = self._get_ax_app()
            windows = self._ax_val(app, 'AXWindows')
        except Exception:
            return "Cannot access KakaoTalk. Grant accessibility permission to your terminal."

        if not windows:
            return "No KakaoTalk windows found. Open KakaoTalk from the dock."

        # Check if main window is present
        main_found = False
        for win in windows:
            title = self._ax_val(win, 'AXTitle')
            if title and self._is_main_window(title):
                main_found = True
                # Check if it has a scroll area with a table (Chats tab)
                children = self._ax_val(win, 'AXChildren')
                if children:
                    for child in children:
                        if self._ax_val(child, 'AXRole') == 'AXScrollArea':
                            sa_children = self._ax_val(child, 'AXChildren')
                            if sa_children:
                                for sc in sa_children:
                                    if self._ax_val(sc, 'AXRole') == 'AXTable':
                                        return "Room list is empty. Try scrolling or restarting KakaoTalk."
                    # No table found - wrong tab
                    return "Switch to the Chats tab in KakaoTalk. Currently showing a different tab (Friends/More)."
                break

        if not main_found:
            return "KakaoTalk main window is not open. Click the KakaoTalk icon in the dock."

        return "Could not read room list. Check if KakaoTalk is responsive."

    def diagnose_no_messages(self) -> str:
        """Diagnose why get_chat_messages returned empty. Returns error message."""
        if not self.current_room:
            return "No room is open. Use /o <n> to open a room first."

        if self._current_chat_window_exists():
            return "Chat window is open but no messages loaded. Try /r to refresh."

        return "Chat window not found. The room may have closed. Use /o to reopen."

    def diagnose_send_failure(self) -> str:
        """Diagnose why send_message failed. Returns error message."""
        if not self.current_room:
            return "No room is open. Use /o <n> to open a room first."

        if self._current_chat_window_exists():
            return "Chat window exists but input failed. KakaoTalk may be unresponsive. Try clicking the KakaoTalk window once."

        return "Chat window not found. Use /o to reopen the room, then send again."

    def _find_ax_scroll_and_table(self, window_name: str, exact_title: bool = False) -> Tuple[Any, Any]:
        """Find scroll area and table in a window by name.
        For main window: matches any known main window title
        For chat windows: contains 'window_name' unless exact_title is set
        Returns (scroll_area, table) or (None, None)
        """
        app = self._get_ax_app()
        windows = self._ax_val(app, 'AXWindows')
        if not windows:
            return None, None
        is_main = self._is_main_window(window_name)
        for win in windows:
            title = self._ax_val(win, 'AXTitle')
            if not title:
                continue
            if is_main:
                match = self._is_main_window(title)
            elif exact_title:
                match = title == window_name
            else:
                match = self._title_matches_room(title, window_name)
            if match:
                children = self._ax_val(win, 'AXChildren')
                if not children:
                    continue
                for child in children:
                    role = self._ax_val(child, 'AXRole')
                    if role == 'AXScrollArea':
                        sa_children = self._ax_val(child, 'AXChildren')
                        if sa_children:
                            for sc in sa_children:
                                if self._ax_val(sc, 'AXRole') == 'AXTable':
                                    return child, sc
                        break
        return None, None

    @staticmethod
    def _strip_emoji(text: str) -> str:
        """Strip emoji and special unicode characters for AppleScript compatibility"""
        import re
        # Keep Korean, ASCII, common punctuation, spaces
        return re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9.,!?~\-_()\[\]@#$%^&*+=]', '', text).strip()

    @staticmethod
    def _normalize_match_text(text: str) -> str:
        """Normalize titles and room names so matching is resilient to punctuation/emoji differences."""
        import re
        normalized = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9]', ' ', text or "")
        normalized = re.sub(r'\s+', ' ', normalized).strip().lower()
        return normalized

    def _title_matches_room(self, title: str, room_name: str) -> bool:
        """Return True when a KakaoTalk window title refers to the given room."""
        if not title or not room_name:
            return False
        if room_name in title:
            return True
        normalized_title = self._normalize_match_text(title)
        normalized_room = self._normalize_match_text(room_name)
        if not normalized_title or not normalized_room:
            return False
        return normalized_room in normalized_title

    def _run_applescript(self, script: str, timeout: int = 15) -> str:
        """AppleScript 실행 (임시 파일 사용)"""
        import tempfile
        import os
        try:
            # 임시 파일에 스크립트 저장
            with tempfile.NamedTemporaryFile(mode='w', suffix='.applescript', delete=False) as f:
                f.write(script)
                temp_path = f.name

            # 파일에서 실행
            result = subprocess.run(
                ["osascript", temp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # 임시 파일 삭제
            os.unlink(temp_path)

            # Debug: print stderr if there's an error
            if result.returncode != 0 and result.stderr:
                self._last_error = result.stderr.strip()
            else:
                self._last_error = None

            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            self._last_error = "Timeout"
            return ""
        except Exception as e:
            self._last_error = str(e)
            return ""

    def check_accessibility_permission(self) -> bool:
        """접근성 권한 확인"""
        try:
            if not AXIsProcessTrusted():
                return False
        except Exception:
            return False

        # A trusted process should also be able to inspect the system-wide focused element.
        # This avoids false positives where AppleScript access works partially but AX reads fail.
        try:
            app = self._get_ax_app()
            err, _ = AXUIElementCopyAttributeValue(app, 'AXRole', None)
            return err == 0
        except Exception:
            return False

    def activate_app(self) -> bool:
        """Activate KakaoTalk app (only needed for rare UI operations)"""
        script = f'tell application "{self.app_name}" to activate'
        self._run_applescript(script, timeout=3)
        return True

    def get_open_windows(self) -> List[dict]:
        """Get info about all open KakaoTalk windows.
        Returns list of dicts with 'name' and 'type' (main/chat/unknown).
        """
        script = '''
tell application "System Events"
    tell process "KakaoTalk"
        set output to ""
        repeat with w in windows
            set winName to name of w
            -- Check if it has scroll area 2 (chat input = chat window)
            set hasInput to "no"
            try
                tell w
                    set sa2 to scroll area 2
                    set hasInput to "yes"
                end tell
            end try
            set output to output & winName & "::" & hasInput & "|||"
        end repeat
        return output
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=5)
        windows = []
        for part in result.split("|||"):
            part = part.strip()
            if not part:
                continue
            sep = part.find("::")
            if sep < 0:
                continue
            name = part[:sep].strip()
            has_input = part[sep + 2:].strip()

            if self._is_main_window(name):
                win_type = "main"
            elif has_input == "yes":
                win_type = "chat"
            elif name == "":
                win_type = "unknown"
            else:
                win_type = "popup"
            windows.append({"name": name, "type": win_type})
        return windows

    def get_chat_rooms(self, limit: int = 10, offset: int = 0) -> List[ChatRoom]:
        """Get chat room list with row indices and unread counts (direct AX API)"""
        scroll_area, table = self._find_ax_scroll_and_table(self._get_main_title())
        if not table:
            return []

        rows = self._ax_val(table, 'AXRows')
        if not rows:
            return []

        # Get scroll area position/size for right-side threshold
        sa_pos = self._ax_val(scroll_area, 'AXPosition')
        sa_size = self._ax_val(scroll_area, 'AXSize')
        if sa_pos and sa_size:
            sa_x, _ = self._ax_coord(sa_pos)
            sa_w, _ = self._ax_coord(sa_size)
            # Unread badge is positioned in the right 30% of the cell
            unread_threshold = sa_x + (sa_w * 0.7)
        else:
            unread_threshold = 99999

        skip_names = {
            # Korean UI tabs/folders
            "전체", "안읽음", "즐겨찾기", "채팅", "친구", "더보기", "채널",
            # English UI tabs/folders
            "All", "Unread", "Favorites", "Chats", "Friends", "More", "Channels",
            ""
        }
        rooms = []
        fetch_limit = limit + offset + 5

        for i, row in enumerate(rows[:fetch_limit]):
            cells = self._ax_val(row, 'AXChildren')
            if not cells or len(cells) == 0:
                continue
            cell = cells[0]
            children = self._ax_val(cell, 'AXChildren')
            if not children:
                continue

            # Collect static text values with position check for numbers
            room_name = ""
            unread = 0
            for child in children:
                role = self._ax_val(child, 'AXRole')
                if role == 'AXStaticText':
                    val = self._ax_val(child, 'AXValue')
                    if val:
                        if not room_name:
                            room_name = val
                        else:
                            try:
                                n = int(val)
                                if n > 0:
                                    # Only count as unread if positioned on the RIGHT side
                                    st_pos = self._ax_val(child, 'AXPosition')
                                    if st_pos:
                                        st_x, _ = self._ax_coord(st_pos)
                                        if st_x >= unread_threshold:
                                            unread = n
                            except (ValueError, TypeError):
                                pass

            if room_name and room_name not in skip_names:
                rooms.append(ChatRoom(
                    name=room_name, time="", last_message="",
                    unread=unread, row_index=i + 1
                ))

        return rooms[offset:offset + limit]

    def search_rooms(self, query: str) -> List[ChatRoom]:
        """Search for chat rooms by name - client-side filtering, no activation"""
        all_rooms = self.get_chat_rooms(limit=50, offset=0)
        query_lower = query.lower()
        return [r for r in all_rooms if query_lower in r.name.lower()]

    def _list_chat_window_titles(self, search_name: str = "", exact_title: bool = False) -> List[str]:
        """Return open chat window titles, optionally filtered by room name or exact title."""
        app = self._get_ax_app()
        windows = self._ax_val(app, 'AXWindows')
        titles = []
        if not windows:
            return titles
        for win in windows:
            title = self._ax_val(win, 'AXTitle')
            if not title or self._is_main_window(title):
                continue
            if search_name:
                if exact_title and title != search_name:
                    continue
                if not exact_title and not self._title_matches_room(title, search_name):
                    continue
            titles.append(title)
        return titles

    def _capture_window_title_after_open(self, room_name: str, before_titles: List[str]) -> Optional[str]:
        """Capture the best exact chat window title after opening a room."""
        after_titles = self._list_chat_window_titles(room_name)
        if not after_titles:
            return None

        before_set = set(before_titles)
        new_titles = [title for title in after_titles if title not in before_set]
        if len(new_titles) == 1:
            return new_titles[0]

        exact_titles = [title for title in after_titles if title == room_name]
        if len(exact_titles) == 1:
            return exact_titles[0]

        matching_titles = [title for title in after_titles if self._title_matches_room(title, room_name)]
        if len(matching_titles) == 1:
            return matching_titles[0]

        if len(after_titles) == 1:
            return after_titles[0]

        return None

    def _wait_for_chat_window_open(
        self,
        room_name: str,
        before_titles: List[str],
        attempts: int = 6,
        delay: float = 0.2,
    ) -> Optional[str]:
        """Wait for a room open action to surface a readable chat window title."""
        for _ in range(max(1, attempts)):
            title = self._capture_window_title_after_open(room_name, before_titles)
            if title:
                return title
            if self._list_chat_window_titles(room_name):
                return None
            time.sleep(delay)
        return None

    def _current_chat_window_exists(self) -> bool:
        """Check whether the currently selected chat window still exists."""
        if self.current_window_title:
            return self._chat_window_exists(exact_title=self.current_window_title)
        search_name = self.current_room or ""
        if not search_name:
            return False
        return self._chat_window_exists(search_name=search_name)

    def _as_main_window_check(self) -> str:
        """Generate AppleScript condition to match main window by any known name."""
        conditions = [f'name of w is "{n}"' for n in self.MAIN_WINDOW_NAMES]
        return "(" + " or ".join(conditions) + ")"

    def _open_room_by_index_press(self, row_index: int) -> bool:
        """Try to open a room by pressing the row directly, without raising the window."""
        main_check = self._as_main_window_check()
        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if {main_check} then
                tell w
                    tell scroll area 1
                        tell table 1
                            try
                                perform action "AXPress" of row {row_index}
                                return "pressed-row"
                            end try
                            try
                                perform action "AXPress" of UI element 1 of row {row_index}
                                return "pressed-cell"
                            end try
                            try
                                set selected of row {row_index} to true
                                return "selected-only"
                            on error
                                return "not found"
                            end try
                        end tell
                    end tell
                end tell
            end if
        end repeat
        return "not found"
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=5)
        return any(token in result for token in ("pressed-row", "pressed-cell"))

    def _open_room_by_index_raise(self, row_index: int) -> bool:
        """Fallback strategy: raise the main window and send Return."""
        main_check = self._as_main_window_check()
        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if {main_check} then
                tell w
                    tell scroll area 1
                        tell table 1
                            try
                                set selected of row {row_index} to true
                            on error
                                return "not found"
                            end try
                        end tell
                    end tell
                end tell
                perform action "AXRaise" of w
                return "ok"
            end if
        end repeat
        return "not found"
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=5)
        if "not found" in result or not result:
            return False

        time.sleep(0.1)
        self._send_key(36)  # Return key
        return True

    def open_room_by_index(self, row_index: int, room_name: str = "", allow_raise_fallback: bool = True) -> bool:
        """Open chat room by row index. Prefer direct press, then optionally fall back."""
        before_titles = self._list_chat_window_titles()
        opened = self._open_room_by_index_press(row_index)
        if opened:
            if room_name:
                window_title = self._wait_for_chat_window_open(room_name, before_titles)
                if self._chat_window_exists(search_name=room_name):
                    self.current_room = room_name
                    self.current_window_title = window_title
                    return True
            else:
                self.current_room = room_name
                self.current_window_title = None
                return True

        if not allow_raise_fallback:
            return False

        if not self._open_room_by_index_raise(row_index):
            return False

        if room_name:
            window_title = self._wait_for_chat_window_open(room_name, before_titles, attempts=8, delay=0.25)
            if not self._chat_window_exists(search_name=room_name):
                return False
        else:
            window_title = None

        self.current_room = room_name
        self.current_window_title = window_title
        return True

    def _open_room_by_name_press(self, room_name: str) -> bool:
        """Try to open a room by pressing the matching row directly."""
        search_name = self._strip_emoji(room_name)
        if not search_name:
            return False

        main_check = self._as_main_window_check()
        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if {main_check} then
                tell w
                    tell scroll area 1
                        tell table 1
                            repeat with i from 1 to count of rows
                                try
                                    set cellElem to UI element 1 of row i
                                    set rName to value of static text 1 of cellElem
                                    if rName contains "{search_name}" then
                                        try
                                            perform action "AXPress" of row i
                                            return "pressed-row"
                                        end try
                                        try
                                            perform action "AXPress" of cellElem
                                            return "pressed-cell"
                                        end try
                                        set selected of row i to true
                                        return "selected-only"
                                    end if
                                end try
                            end repeat
                        end tell
                    end tell
                end tell
            end if
        end repeat
        return "not found"
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=8)
        return any(token in result for token in ("pressed-row", "pressed-cell"))

    def _open_room_by_name_raise(self, room_name: str) -> bool:
        """Fallback strategy: select the row, raise the main window, and send Return."""
        search_name = self._strip_emoji(room_name)
        if not search_name:
            return False

        main_check = self._as_main_window_check()
        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if {main_check} then
                tell w
                    tell scroll area 1
                        tell table 1
                            repeat with i from 1 to count of rows
                                try
                                    set cellElem to UI element 1 of row i
                                    set rName to value of static text 1 of cellElem
                                    if rName contains "{search_name}" then
                                        set selected of row i to true
                                        exit repeat
                                    end if
                                end try
                            end repeat
                        end tell
                    end tell
                end tell
                perform action "AXRaise" of w
                return "ok"
            end if
        end repeat
        return "not found"
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=8)
        if "not found" in result or not result:
            return False

        time.sleep(0.1)
        self._send_key(36)  # Return key
        return True

    def open_room_by_name(self, room_name: str, allow_raise_fallback: bool = True) -> bool:
        """Open chat room by name. Prefer direct press, then optionally fall back."""
        search_name = self._strip_emoji(room_name)
        if not search_name:
            return False

        before_titles = self._list_chat_window_titles()
        opened = self._open_room_by_name_press(room_name)
        if opened:
            window_title = self._wait_for_chat_window_open(room_name, before_titles)
            if self._chat_window_exists(search_name=room_name):
                self.current_room = room_name
                self.current_window_title = window_title
                return True

        if not allow_raise_fallback:
            return False

        if not self._open_room_by_name_raise(room_name):
            return False

        window_title = self._wait_for_chat_window_open(room_name, before_titles, attempts=8, delay=0.25)
        if not self._chat_window_exists(search_name=room_name):
            return False

        self.current_room = room_name
        self.current_window_title = window_title
        return True

    def send_message(self, message: str) -> bool:
        """Send message to the open chat room - background, no window activation"""
        if not message:
            return False

        # KakaoTalk can refuse to send while the message list is scrolled up.
        # Always return to the latest position before targeting the input area.
        self.scroll_to_bottom()
        time.sleep(0.12)

        # Escape quotes for AppleScript string
        safe_msg = message.replace('\\', '\\\\').replace('"', '\\"')

        # Target specific room window
        if self.current_window_title:
            safe_title = self.current_window_title.replace('\\', '\\\\').replace('"', '\\"')
            win_check = f'name of w is "{safe_title}"'
        elif self.current_room:
            search_name = self._strip_emoji(self.current_room)
            win_check = f'name of w contains "{search_name}"'
        else:
            # Exclude all possible main window names
            excludes = ' and '.join(f'name of w is not "{n}"' for n in self.MAIN_WINDOW_NAMES)
            win_check = f'{excludes} and name of w is not ""'

        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if {win_check} then
                tell w
                    tell scroll area 2
                        set value of text area 1 to "{safe_msg}"
                        set focused of text area 1 to true
                    end tell
                end tell
                return "ready"
            end if
        end repeat
        return "no window"
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=5)
        if "ready" not in result:
            # One more attempt after forcing the chat to the bottom again.
            self.scroll_to_bottom()
            time.sleep(0.2)
            result = self._run_applescript(script, timeout=5)
            if "ready" not in result:
                return False

        time.sleep(0.1)
        self._send_key(36)  # Return key to send
        return True

    def _chat_window_exists(self, search_name: str = "", exact_title: Optional[str] = None) -> bool:
        """Check whether a chat window matching the room name is still open."""
        app = self._get_ax_app()
        windows = self._ax_val(app, 'AXWindows')
        if not windows:
            return False
        for win in windows:
            title = self._ax_val(win, 'AXTitle')
            if not title or self._is_main_window(title):
                continue
            if exact_title is not None and title == exact_title:
                return True
            if search_name and self._title_matches_room(title, search_name):
                return True
        return False

    def close_current_chat(self) -> bool:
        """Close the currently open chat window without closing the main room list."""
        if not self.current_room:
            return False

        search_name = self._strip_emoji(self.current_room)
        exact_title = self.current_window_title
        if not search_name and not exact_title:
            return False

        title_check = f'name of w is "{exact_title.replace("\\", "\\\\").replace("\"", "\\\"")}"' if exact_title else f'name of w contains "{search_name}"'
        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if {title_check} then
                try
                    perform action "AXRaise" of w
                end try
                try
                    perform action "AXClose" of w
                    return "closed"
                on error
                    return "escape"
                end try
            end if
        end repeat
        return "not found"
    end tell
end tell
'''
        result = self._run_applescript(script, timeout=5)
        if "closed" in result:
            time.sleep(0.15)
            self.current_room = None
            self.current_window_title = None
            return True

        if "escape" in result:
            time.sleep(0.1)
            self._send_key(53)  # Escape
            time.sleep(0.2)
            if not self._chat_window_exists(search_name=search_name, exact_title=exact_title):
                self.current_room = None
                self.current_window_title = None
                return True

        return False

    @staticmethod
    def _is_time_string(text: str) -> bool:
        """Check if a string looks like a KakaoTalk time stamp.
        Korean: '오후 6:26', '오전 9:43'
        Japanese: '午後 6:26', '午前 9:43'
        English: '6:26 PM', '9:43 AM', '18:26'
        """
        if not text:
            return False
        # Korean format
        if text.startswith("오전 ") or text.startswith("오후 "):
            return True
        # Japanese format
        if text.startswith("午前") or text.startswith("午後"):
            return True
        # English format: "6:26 PM", "11:43 AM"
        if text.endswith(" AM") or text.endswith(" PM"):
            return bool(re.match(r'^\d{1,2}:\d{2}\s*[AP]M$', text))
        # 24h format: "18:26"
        if re.match(r'^\d{1,2}:\d{2}$', text):
            return True
        return False

    @staticmethod
    def _is_date_string(text: str) -> bool:
        """Check if text is a date separator.
        Korean: '2025년 1월 24일 금요일'
        English: 'Friday, January 24, 2025', 'January 24, 2025'
        Japanese: '2025年1月24日 金曜日'
        """
        if not text:
            return False
        # Korean format (년/월/일)
        if "년 " in text and "월 " in text and "일" in text:
            return True
        # Japanese format (年/月/日)
        if "年" in text and "月" in text and "日" in text:
            return True
        # English format: month name + 4-digit year
        months = ("January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December")
        for m in months:
            if m in text and re.search(r'\d{4}', text):
                return True
        return False

    @staticmethod
    def _is_read_count(text: str) -> bool:
        """Check if text is a read count (small integer)"""
        try:
            n = int(text)
            return 0 < n < 1000
        except (ValueError, TypeError):
            return False

    def _is_sender_candidate_text(self, text: str) -> bool:
        """Check if text is a plausible sender label, not message metadata."""
        if not text:
            return False
        text = text.strip()
        if not text or '\n' in text:
            return False
        if len(text) > 40:
            return False
        if self._is_time_string(text) or self._is_date_string(text) or self._is_read_count(text):
            return False
        return True

    def _find_sender_label(self, st_elems: List[Tuple[str, Any]], threshold: float, ta_y: float = 0.0) -> str:
        """Find a likely sender label for received messages.

        Sender labels in KakaoTalk are short, single-line texts shown on the left side
        above or near the message bubble. Long message fragments should not match here.
        """
        for val, elem in st_elems:
            if not self._is_sender_candidate_text(val):
                continue

            st_pos = self._ax_val(elem, 'AXPosition')
            if st_pos:
                st_x, st_y = self._ax_coord(st_pos)
                if st_x > threshold:
                    continue
                if ta_y > 5 and st_y > ta_y + 12:
                    continue
            return val.strip()
        return ""

    def _has_profile_image(self, children: List[Any]) -> bool:
        """Detect the small profile image used on received text messages."""
        for child in children:
            if self._ax_val(child, 'AXRole') != 'AXImage':
                continue
            sz = self._ax_val(child, 'AXSize')
            if not sz:
                continue
            iw, ih = self._ax_coord(sz)
            if 0 < iw < 60 and 0 < ih < 60:
                return True
        return False

    def _infer_is_me_from_frame(self, elem: Any, container_x: float, container_w: float) -> Optional[bool]:
        """Infer message side from the full rendered frame.

        Long sent bubbles can stretch far to the left. Using only the left edge causes
        them to look like received messages, so compare both outer gaps first.
        """
        if not elem or container_w <= 0:
            return None

        elem_pos = self._ax_val(elem, 'AXPosition')
        elem_size = self._ax_val(elem, 'AXSize')
        if not elem_pos or not elem_size:
            return None

        elem_x, _ = self._ax_coord(elem_pos)
        elem_w, _ = self._ax_coord(elem_size)
        if elem_x <= 0 or elem_w <= 0:
            return None

        left_gap = max(0.0, elem_x - container_x)
        right_edge = elem_x + elem_w
        right_gap = max(0.0, (container_x + container_w) - right_edge)

        if abs(left_gap - right_gap) >= 8:
            return right_gap < left_gap

        center_x = elem_x + (elem_w / 2.0)
        return center_x > (container_x + (container_w / 2.0))

    def scroll_to_bottom(self) -> None:
        """Scroll the current chat room's message view to the bottom."""
        search_name = self._strip_emoji(self.current_room) if self.current_room else ""
        if self.current_window_title:
            scroll_area, table = self._find_ax_scroll_and_table(self.current_window_title, exact_title=True)
        elif search_name:
            scroll_area, table = self._find_ax_scroll_and_table(search_name)
        else:
            scroll_area, table = None, None
        if not scroll_area:
            return
        sa_children = self._ax_val(scroll_area, 'AXChildren')
        if not sa_children:
            return
        for child in sa_children:
            if self._ax_val(child, 'AXRole') == 'AXScrollBar':
                orient = self._ax_val(child, 'AXOrientation')
                if orient and 'Vertical' in str(orient):
                    try:
                        AXUIElementSetAttributeValue(child, 'AXValue', 1.0)
                        time.sleep(0.1)
                    except Exception:
                        pass
                    break

    def get_chat_messages(self, limit: int = 20, retry: int = 2, msg_offset: int = 0) -> List[Message]:
        """Get messages with sender info from the current room (direct AX API).
        Uses text area x-position to determine is_me vs others.
        msg_offset: how many messages from the end to skip (for scrolling up).
        """
        search_name = self._strip_emoji(self.current_room) if self.current_room else ""

        for attempt in range(retry + 1):
            # Find the chat window
            if self.current_window_title:
                scroll_area, table = self._find_ax_scroll_and_table(self.current_window_title, exact_title=True)
            elif search_name:
                scroll_area, table = self._find_ax_scroll_and_table(search_name)
            else:
                # Find any non-main chat window
                app = self._get_ax_app()
                windows = self._ax_val(app, 'AXWindows')
                scroll_area, table = None, None
                if windows:
                    for win in windows:
                        title = self._ax_val(win, 'AXTitle')
                        if title and not self._is_main_window(title) and title != '':
                            children = self._ax_val(win, 'AXChildren')
                            if children:
                                for child in children:
                                    if self._ax_val(child, 'AXRole') == 'AXScrollArea':
                                        sa_children = self._ax_val(child, 'AXChildren')
                                        if sa_children:
                                            for sc in sa_children:
                                                if self._ax_val(sc, 'AXRole') == 'AXTable':
                                                    scroll_area, table = child, sc
                                                    break
                                        break
                            if table:
                                break

            if not table:
                if attempt < retry:
                    time.sleep(0.2)
                continue

            # Get scroll area position for is_me threshold
            sa_pos = self._ax_val(scroll_area, 'AXPosition')
            sa_size = self._ax_val(scroll_area, 'AXSize')
            if sa_pos and sa_size:
                cell_x, _ = self._ax_coord(sa_pos)
                cell_w, _ = self._ax_coord(sa_size)
                threshold = cell_x + (cell_w * 0.5)
            else:
                cell_x = 0.0
                cell_w = 0.0
                threshold = 99999  # fallback: assume nothing is "me"

            rows = self._ax_val(table, 'AXRows')
            if not rows:
                if attempt < retry:
                    time.sleep(0.2)
                continue

            # Read last N rows (with offset for scrolling)
            fetch_rows = limit + 5
            total_rows = len(rows)
            end_idx = max(0, total_rows - msg_offset)
            start_idx = max(0, end_idx - fetch_rows)
            messages = []
            last_sender = ""
            last_is_me: Optional[bool] = None

            # If reading off-screen rows, scroll the view to make them visible
            vbar = None
            original_scroll = None
            if msg_offset > 0:
                sa_children = self._ax_val(scroll_area, 'AXChildren')
                if sa_children:
                    for child in sa_children:
                        if self._ax_val(child, 'AXRole') == 'AXScrollBar':
                            orient = self._ax_val(child, 'AXOrientation')
                            if orient and 'Vertical' in str(orient):
                                vbar = child
                                break
                if vbar:
                    original_scroll = self._ax_val(vbar, 'AXValue')
                    # Scroll to make target rows visible (0.0=top, 1.0=bottom)
                    target_scroll = max(0.0, min(1.0, start_idx / max(1, total_rows)))
                    try:
                        AXUIElementSetAttributeValue(vbar, 'AXValue', target_scroll)
                        time.sleep(0.15)
                    except Exception:
                        vbar = None  # scroll failed, proceed anyway

            # Pre-scan a few rows to establish sender and side context.
            if start_idx > 0:
                for row in rows[max(0, start_idx - 3):start_idx]:
                    cells = self._ax_val(row, 'AXChildren')
                    if not cells:
                        continue
                    children = self._ax_val(cells[0], 'AXChildren')
                    if not children:
                        continue
                    ta_elem = None
                    st_elems = []
                    for child in children:
                        role = self._ax_val(child, 'AXRole')
                        if role == 'AXTextArea' and ta_elem is None:
                            ta_elem = child
                        elif role == 'AXStaticText':
                            v = self._ax_val(child, 'AXValue')
                            if v:
                                st_elems.append((v, child))

                    ta_y = 0.0
                    ta_x = 0.0
                    if ta_elem:
                        ta_pos = self._ax_val(ta_elem, 'AXPosition')
                        if ta_pos:
                            ta_x, ta_y = self._ax_coord(ta_pos)
                    sender_label = self._find_sender_label(st_elems, threshold, ta_y=ta_y)
                    has_profile = self._has_profile_image(children)
                    inferred_side = self._infer_is_me_from_frame(ta_elem, cell_x, cell_w)
                    if inferred_side is not None:
                        last_is_me = inferred_side
                    elif sender_label or has_profile:
                        last_is_me = False

                    if sender_label:
                        last_sender = sender_label

            for row in rows[start_idx:end_idx]:
                cells = self._ax_val(row, 'AXChildren')
                if not cells or len(cells) == 0:
                    continue
                cell = cells[0]
                children = self._ax_val(cell, 'AXChildren')
                if not children:
                    continue

                # Find text area, static text, and image elements
                ta_elem = None
                st_elems = []  # (value, element) pairs
                large_img_elem = None  # first large image element
                for child in children:
                    role = self._ax_val(child, 'AXRole')
                    if role == 'AXTextArea' and ta_elem is None:
                        ta_elem = child
                    elif role == 'AXStaticText':
                        val = self._ax_val(child, 'AXValue')
                        if val:
                            st_elems.append((val, child))
                    elif role == 'AXImage':
                        img_size = self._ax_val(child, 'AXSize')
                        if img_size:
                            iw, ih = self._ax_coord(img_size)
                            if (iw > 60 or ih > 60) and large_img_elem is None:
                                large_img_elem = child

                # Date separator row (no text area, has date text)
                if not ta_elem:
                    # Check for date
                    for val, _ in st_elems:
                        if self._is_date_string(val):
                            messages.append(Message(
                                sender="", text=val, is_date=True
                            ))
                            break
                    else:
                        # Image message (no TextArea, has large image)
                        if large_img_elem:
                            is_me_img = self._infer_is_me_from_frame(large_img_elem, cell_x, cell_w)
                            if is_me_img is None:
                                # Fallback: received images always have sender name
                                has_sender = False
                                for val, _ in st_elems:
                                    if not self._is_time_string(val) and not self._is_read_count(val):
                                        has_sender = True
                                        break
                                is_me_img = not has_sender

                            img_sender = ""
                            if not is_me_img:
                                for val, _ in st_elems:
                                    if not self._is_time_string(val) and not self._is_read_count(val):
                                        img_sender = val
                                        last_sender = val
                                        break
                                if not img_sender:
                                    img_sender = last_sender
                            messages.append(Message(
                                sender=img_sender, text="[Image]",
                                is_me=is_me_img
                            ))
                    continue

                ta_val = self._ax_val(ta_elem, 'AXValue')
                if not ta_val or len(ta_val) == 0 or len(ta_val) > 1000:
                    continue

                ta_y = 0.0
                ta_pos = self._ax_val(ta_elem, 'AXPosition')
                ta_x = 0.0
                if ta_pos:
                    ta_x, ta_y = self._ax_coord(ta_pos)

                sender_label = self._find_sender_label(st_elems, threshold, ta_y=ta_y)
                has_profile = self._has_profile_image(children)

                # Determine is_me from the full bubble alignment, not only the left edge.
                inferred_side = self._infer_is_me_from_frame(ta_elem, cell_x, cell_w)
                if inferred_side is not None:
                    is_me = inferred_side
                else:
                    # Fallback: only trust strong received-side markers.
                    # If the row is partially visible, preserve the previous side context
                    # instead of misclassifying long sent messages as received.
                    if sender_label or has_profile:
                        is_me = False
                    elif last_is_me is not None:
                        is_me = last_is_me
                    else:
                        is_me = True

                # Classify static texts into time, read_count, sender
                # KakaoTalk combines read_count + time in one element: "1\n오후 3:32"
                msg_time = ""
                read_count = 0
                sender = ""
                for val, elem in st_elems:
                    # Split by newline - KakaoTalk combines values
                    parts = val.split('\n')
                    is_metadata = False
                    for part in parts:
                        part = part.strip()
                        if not part:
                            continue
                        if self._is_time_string(part):
                            msg_time = part
                            is_metadata = True
                        elif self._is_read_count(part):
                            # Verify position: LEFT of sent, RIGHT of received
                            st_pos = self._ax_val(elem, 'AXPosition')
                            if st_pos:
                                st_x, _ = self._ax_coord(st_pos)
                                if is_me and st_x < ta_x:
                                    read_count = int(part)
                                    is_metadata = True
                                elif not is_me and st_x > ta_x:
                                    read_count = int(part)
                                    is_metadata = True
                    if not is_metadata and not sender and self._is_sender_candidate_text(val):
                        sender = val.strip()

                # For non-me messages, use last_sender if no sender found
                if not is_me:
                    if not sender:
                        sender = sender_label
                    if not sender:
                        sender = last_sender
                    else:
                        last_sender = sender
                last_is_me = is_me

                messages.append(Message(
                    sender=sender, text=ta_val, time=msg_time,
                    is_me=is_me, read_count=read_count
                ))

            # Scroll back to original position
            if vbar and original_scroll is not None:
                try:
                    AXUIElementSetAttributeValue(vbar, 'AXValue', original_scroll)
                except Exception:
                    pass

            if messages:
                return messages[-limit:] if len(messages) > limit else messages

            if attempt < retry:
                time.sleep(0.2)

        return []

    def get_latest_messages_fast(self, count: int = 5) -> List[Message]:
        """Fast message check using direct AX API.
        Used for auto-refresh to detect new messages quickly.
        """
        return self.get_chat_messages(limit=count, retry=0)



def test_bridge():
    """브릿지 테스트"""
    bridge = KakaoBridge()

    print("=== 카카오톡 브릿지 테스트 v2 ===\n")

    # 권한 확인
    if not bridge.check_accessibility_permission():
        print("Accessibility permission is required")
        print("   → 시스템 환경설정 > 개인정보 보호 및 보안 > 손쉬운 사용")
        return

    print("Accessibility permission confirmed\n")

    # 채팅방 목록
    print("\n=== 채팅방 목록 ===")
    rooms = bridge.get_chat_rooms(limit=10)
    for i, room in enumerate(rooms, 1):
        print(f"{i}. {room.name}")
        print(f"      {room.time} | {room.last_message[:30]}..." if len(room.last_message) > 30 else f"      {room.time} | {room.last_message}")


if __name__ == "__main__":
    test_bridge()
