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

    def __init__(self):
        self.current_room: Optional[str] = None
        self.app_name = "KakaoTalk"
        self._last_error: Optional[str] = None  # Last AppleScript error
        self._pid: Optional[int] = None  # KakaoTalk process ID

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

    def _find_ax_scroll_and_table(self, window_name: str) -> Tuple[Any, Any]:
        """Find scroll area and table in a window by name.
        For main window: exact match 'window_name'
        For chat windows: contains 'window_name'
        Returns (scroll_area, table) or (None, None)
        """
        app = self._get_ax_app()
        windows = self._ax_val(app, 'AXWindows')
        if not windows:
            return None, None
        for win in windows:
            title = self._ax_val(win, 'AXTitle')
            if not title:
                continue
            match = (title == window_name) if window_name == '카카오톡' else (window_name in title)
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
        return re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9.,!?~\-_()@#$%^&*+=]', '', text).strip()

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
        script = '''
        tell application "System Events"
            try
                tell process "KakaoTalk"
                    get name
                end tell
                return "granted"
            on error
                return "denied"
            end try
        end tell
        '''
        return "granted" in self._run_applescript(script).lower()

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

            if name == "카카오톡":
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
        scroll_area, table = self._find_ax_scroll_and_table('카카오톡')
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

        skip_names = {"전체 폴더", "안읽음 폴더", "즐겨찾기", "채팅", "친구", "더보기", ""}
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

    def open_room_by_index(self, row_index: int, room_name: str = "") -> bool:
        """Open chat room by row index - background, no window activation"""
        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if name of w is "카카오톡" then
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
                -- Make main window the key window so Return goes here
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
        time.sleep(0.3)  # Wait for chat window to open

        self.current_room = room_name
        return True

    def open_room_by_name(self, room_name: str) -> bool:
        """Open chat room by name - background, no window activation"""
        search_name = self._strip_emoji(room_name)
        if not search_name:
            return False

        script = f'''
tell application "System Events"
    tell process "KakaoTalk"
        repeat with w in windows
            if name of w is "카카오톡" then
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
                -- Make main window the key window so Return goes here
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
        time.sleep(0.3)  # Wait for chat window to open

        self.current_room = room_name
        return True

    def send_message(self, message: str) -> bool:
        """Send message to the open chat room - background, no window activation"""
        if not message:
            return False

        # Escape quotes for AppleScript string
        safe_msg = message.replace('\\', '\\\\').replace('"', '\\"')

        # Target specific room window
        if self.current_room:
            search_name = self._strip_emoji(self.current_room)
            win_check = f'name of w contains "{search_name}"'
        else:
            win_check = 'name of w is not "카카오톡" and name of w is not ""'

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
            return False

        time.sleep(0.1)
        self._send_key(36)  # Return key to send
        return True

    @staticmethod
    def _is_time_string(text: str) -> bool:
        """Check if a string looks like a KakaoTalk time stamp (e.g. '오후 6:26', '오전 9:43')"""
        if not text:
            return False
        return text.startswith("오전 ") or text.startswith("오후 ")

    @staticmethod
    def _is_date_string(text: str) -> bool:
        """Check if text is a date separator (e.g. '2025년 1월 24일 금요일')"""
        if not text:
            return False
        return "년 " in text and "월 " in text and "일" in text

    @staticmethod
    def _is_read_count(text: str) -> bool:
        """Check if text is a read count (small integer)"""
        try:
            n = int(text)
            return 0 < n < 1000
        except (ValueError, TypeError):
            return False

    def scroll_to_bottom(self) -> None:
        """Scroll the current chat room's message view to the bottom."""
        search_name = self._strip_emoji(self.current_room) if self.current_room else ""
        if search_name:
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
            if search_name:
                scroll_area, table = self._find_ax_scroll_and_table(search_name)
            else:
                # Find any non-main chat window
                app = self._get_ax_app()
                windows = self._ax_val(app, 'AXWindows')
                scroll_area, table = None, None
                if windows:
                    for win in windows:
                        title = self._ax_val(win, 'AXTitle')
                        if title and title != '카카오톡' and title != '':
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
                threshold = cell_x + (cell_w * 0.3)
            else:
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

            # Pre-scan 3 rows before start to establish sender context
            if start_idx > 0:
                for row in rows[max(0, start_idx - 3):start_idx]:
                    cells = self._ax_val(row, 'AXChildren')
                    if not cells:
                        continue
                    children = self._ax_val(cells[0], 'AXChildren')
                    if not children:
                        continue
                    for child in children:
                        role = self._ax_val(child, 'AXRole')
                        if role == 'AXStaticText':
                            v = self._ax_val(child, 'AXValue')
                            if v and not self._is_time_string(v) and '\n' not in v:
                                try:
                                    int(v)
                                except (ValueError, TypeError):
                                    last_sender = v

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
                            # Determine is_me from image position
                            img_pos = self._ax_val(large_img_elem, 'AXPosition')
                            img_x = 0.0
                            if img_pos:
                                img_x, _ = self._ax_coord(img_pos)
                            if img_x > 5:
                                is_me_img = img_x > threshold
                            else:
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

                # Determine is_me from text area x-position
                ta_pos = self._ax_val(ta_elem, 'AXPosition')
                ta_x = 0.0
                if ta_pos:
                    ta_x, _ = self._ax_coord(ta_pos)
                if ta_x > 5:  # valid position (not off-screen 0,0)
                    is_me = ta_x > threshold
                else:
                    # Fallback: check if row has sender name or profile image
                    # Sent messages have no sender/profile; received first-in-seq do
                    has_sender_or_profile = False
                    for child in children:
                        role = self._ax_val(child, 'AXRole')
                        if role == 'AXStaticText':
                            v = self._ax_val(child, 'AXValue')
                            if v and not self._is_time_string(v) and '\n' not in v:
                                try:
                                    int(v)
                                except (ValueError, TypeError):
                                    if not self._is_date_string(v):
                                        has_sender_or_profile = True
                                        break
                        elif role == 'AXImage':
                            sz = self._ax_val(child, 'AXSize')
                            if sz:
                                iw, ih = self._ax_coord(sz)
                                if iw < 60 and ih < 60:  # profile pic
                                    has_sender_or_profile = True
                                    break
                    is_me = not has_sender_or_profile

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
                    if not is_metadata and not sender:
                        sender = val

                # For non-me messages, use last_sender if no sender found
                if not is_me:
                    if not sender:
                        sender = last_sender
                    else:
                        last_sender = sender

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
        print("❌ 접근성 권한이 필요합니다")
        print("   → 시스템 환경설정 > 개인정보 보호 및 보안 > 손쉬운 사용")
        return

    print("✅ 접근성 권한 확인됨\n")

    # 채팅방 목록
    print("\n=== 채팅방 목록 ===")
    rooms = bridge.get_chat_rooms(limit=10)
    for i, room in enumerate(rooms, 1):
        print(f"{i}. 💬 {room.name}")
        print(f"      {room.time} | {room.last_message[:30]}..." if len(room.last_message) > 30 else f"      {room.time} | {room.last_message}")


if __name__ == "__main__":
    test_bridge()
