"""
Terminal chat client - Claude Code style UI
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Input, RichLog, Static
from textual.containers import Container
from textual.binding import Binding
from textual import on
from datetime import datetime
import asyncio
import random

from kakao_bridge import KakaoBridge, Message


# Fake log messages for Claude Code style
FAKE_ACTIONS = [
    "Reading file contents",
    "Analyzing codebase structure",
    "Parsing AST nodes",
    "Resolving dependencies",
    "Checking type definitions",
    "Scanning for patterns",
    "Building syntax tree",
    "Evaluating expressions",
    "Processing modules",
    "Indexing symbols",
    "Validating schema",
    "Compiling templates",
]

FAKE_FILES = [
    "src/components/Chat.tsx",
    "lib/utils/parser.ts",
    "core/runtime/executor.py",
    "pkg/handlers/message.go",
    "internal/cache/store.rs",
    "modules/auth/session.js",
    "services/api/client.ts",
]

FAKE_AGENTS = [
    "Explore", "Bash", "Read", "Grep", "Glob", "Task"
]

# Loading spinner frames
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class LoadingIndicator:
    """Simple loading indicator that updates log output"""

    def __init__(self, log: RichLog, message: str):
        self.log = log
        self.message = message
        self.frame_idx = 0
        self.running = False
        self._task = None

    async def start(self):
        """Start the loading animation"""
        self.running = True
        self.log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] {self.message}")

    async def animate(self):
        """Animate the spinner (call periodically)"""
        if self.running:
            self.frame_idx = (self.frame_idx + 1) % len(SPINNER_FRAMES)

    def stop(self, success: bool = True):
        """Stop the loading animation"""
        self.running = False
        if success:
            self.log.write(f"[green]✓[/] {self.message} - done")
        else:
            self.log.write(f"[red]✗[/] {self.message} - failed")


class CommandPalette(Container):
    """Command palette shown when / is typed"""

    DEFAULT_CSS = """
    CommandPalette {
        dock: bottom;
        layer: above;
        height: auto;
        max-height: 12;
        background: #1e1e2e;
        border: solid #89b4fa;
        padding: 1;
        margin: 0 0 3 0;
        display: none;
    }
    CommandPalette.visible {
        display: block;
    }
    CommandPalette > Static {
        padding: 0 1;
        height: 1;
    }
    CommandPalette > Static:hover {
        background: #313244;
    }
    """

    def compose(self) -> ComposeResult:
        commands = [
            ("/l", "/list", "List rooms", ""),
            ("/o", "/open", "Connect to room", "number"),
            ("/r", "/refresh", "Refresh messages", ""),
            ("/u", "/up", "Older messages", ""),
            ("/d", "/down", "Newer messages", ""),
            ("/b", "/back", "Back to room list", ""),
            ("/s", "/search", "Search rooms", "query"),
            ("/h", "/help", "Help", ""),
            ("/q", "/quit", "Exit", ""),
        ]
        for short, full, desc, arg in commands:
            if arg:
                yield Static(f"[bold cyan]{short}[/][dim]({full})[/] [dim]<{arg}>[/]  [dim]{desc}[/]")
            else:
                yield Static(f"[bold cyan]{short}[/][dim]({full})[/]  [dim]{desc}[/]")


class KakaoTerminal(App):
    """Terminal-based chat client"""

    TITLE = "KaKao Agentic Code"
    SUB_TITLE = "~/workspace"

    CSS = """
    Screen {
        background: #11111b;
    }

    #chat-log {
        height: 1fr;
        border: solid #313244;
        padding: 0 1;
        background: #11111b;
    }

    #input-container {
        dock: bottom;
        height: 3;
    }

    #input-bar {
        border: solid #45475a;
        background: #1e1e2e;
        padding: 0 1;
    }

    #input-bar:focus {
        border: solid #89b4fa;
    }
    """

    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+l", "clear_log", "Clear"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("escape", "hide_palette", "Close", show=False),
        Binding("down", "load_more_rooms", "More", show=False),
        Binding("up", "load_prev_rooms", "Prev", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.kakao = KakaoBridge()
        self.current_room = None
        self.messages = []
        self.fake_task_id = 0
        self.room_list = []  # Room list for number selection
        self.auto_refresh_timer = None
        self.in_chat = False  # True when inside a chat room
        self.room_offset = 0  # For pagination
        self.msg_offset = 0  # Message scroll offset (0 = latest)
        self.in_room_list = False  # True when viewing room list
        self.search_results = []  # Search results
        self._refreshing = False  # Guard against overlapping refreshes

    def _escape_markup(self, text: str) -> str:
        """Escape Rich markup characters"""
        if not text:
            return ""
        # Escape brackets for Rich markup
        return text.replace("[", "\\[").replace("]", "\\]")

    def _write_message(self, log: RichLog, msg: Message) -> None:
        """Format and write a single message to the log"""
        if msg.is_date:
            log.write(f"  [dim]── {self._escape_markup(msg.text)} ──[/]")
            return

        if msg.text == "[Image]":
            safe_text = "[dim italic]Image[/]"
        else:
            safe_text = self._escape_markup(msg.text)
        time_str = f" [dim]{msg.time}[/]" if msg.time else ""
        read_str = f" [yellow]{msg.read_count}[/]" if msg.read_count > 0 else ""

        if msg.is_me:
            log.write(f"  [dim]│[/] [green]>[/] {safe_text}{read_str}{time_str}")
        else:
            safe_sender = self._escape_markup(msg.sender) if msg.sender else "?"
            log.write(f"  [dim]│[/] [cyan]{safe_sender}[/] {safe_text}{read_str}{time_str}")

    async def fake_working(self, log: RichLog) -> None:
        """Fake Claude Code style work logs"""
        task_id = f"{random.choice('abcdef')}{random.randint(10000, 99999)}"

        num_actions = random.randint(1, 2)

        for i in range(num_actions):
            action = random.choice(FAKE_ACTIONS)
            file = random.choice(FAKE_FILES)
            agent = random.choice(FAKE_AGENTS)

            style = random.randint(1, 4)
            if style == 1:
                log.write(f"[dim]⏺[/] [cyan]{agent}[/] agent")
                lines = random.randint(10, 200)
                log.write(f"  [dim]⎿[/]  Read {lines} lines")
            elif style == 2:
                log.write(f"[dim]⏺[/] {action}...")
            elif style == 3:
                matches = random.randint(3, 25)
                log.write(f"[dim]⏺[/] Found {matches} matches in [dim]{file.split('/')[0]}/[/]")
            else:
                log.write(f"[dim]⏺[/] Task [yellow]{task_id}[/]")

            await asyncio.sleep(0.05)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", highlight=False, markup=True, wrap=True)
        yield Container(
            CommandPalette(id="command-palette"),
            Input(placeholder="> ", id="input-bar"),
            id="input-container"
        )

    def on_mount(self) -> None:
        """On app start"""
        log = self.query_one("#chat-log", RichLog)
        self._print_welcome(log)

        # 입력창에 포커스
        self._focus_input()

        if self.kakao.check_accessibility_permission():
            log.write("[green]✓[/] Accessibility granted")
            # Load rooms on startup
            self.set_timer(0.5, self._initial_load)
            # Auto refresh only when in chat (every 5 seconds)
            self.auto_refresh_timer = self.set_interval(5, self._auto_refresh)
            # 주기적으로 입력창 포커스 확인 (2초마다 - 너무 자주하면 느려짐)
            self.set_interval(2, self._ensure_input_focus)
        else:
            log.write("[red]✗[/] Accessibility permission required")
            log.write("[yellow]  → System Preferences > Privacy > Accessibility[/]")

    def _focus_input(self) -> None:
        """입력창에 포커스"""
        try:
            input_bar = self.query_one("#input-bar", Input)
            input_bar.focus()
        except Exception:
            pass

    async def _ensure_input_focus(self) -> None:
        """입력창 포커스 유지 (다른 창 갔다 오면 자동 복구)"""
        try:
            input_bar = self.query_one("#input-bar", Input)
            if not input_bar.has_focus:
                input_bar.focus()
        except Exception:
            pass

    async def _initial_load(self) -> None:
        """Initial room list load"""
        log = self.query_one("#chat-log", RichLog)

        # 열린 카톡 창 상태 체크
        try:
            windows = self.kakao.get_open_windows()
        except Exception:
            windows = []
        chat_windows = [w for w in windows if w["type"] == "chat"]
        if chat_windows:
            log.write(f"[dim]⏺[/] Open chat windows:")
            for w in chat_windows:
                safe_name = self._escape_markup(w["name"])
                log.write(f"  [dim]•[/] {safe_name}")
            log.write("")

        log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Loading rooms...")
        # 카톡 활성화 없이 백그라운드에서 읽기 (창 안 뜸)
        self.room_offset = 0
        try:
            rooms = self.kakao.get_chat_rooms(limit=10, offset=0)
        except Exception:
            rooms = []
        self.room_list = rooms
        self.in_room_list = True
        if rooms:
            log.write(f"[green]✓[/] Found [cyan]{len(rooms)}[/] rooms (1-10)")
            for i, room in enumerate(rooms):
                safe_name = self._escape_markup(room.name)
                if room.unread > 0:
                    log.write(f"  [cyan]{i+1:2}.[/] {safe_name} [bold red]({room.unread})[/]")
                else:
                    log.write(f"  [cyan]{i+1:2}.[/] {safe_name}")
            log.write("")
            log.write("[dim]  /o <n> to connect | ↓ more | /s <query>[/]")
        else:
            reason = self.kakao.diagnose_no_rooms()
            log.write(f"[red]✗[/] {reason}")

    async def _auto_refresh(self) -> None:
        """Auto refresh - chat messages or rooms list"""
        if self.in_chat:
            await self._refresh_messages_silent()
        elif self.in_room_list:
            await self._refresh_rooms_silent()

    async def _refresh_rooms_silent(self) -> None:
        """Silent rooms refresh - update unread counts"""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            loop = asyncio.get_event_loop()
            rooms = await loop.run_in_executor(
                None, lambda: self.kakao.get_chat_rooms(limit=10, offset=self.room_offset)
            )
        except Exception:
            return
        finally:
            self._refreshing = False
        if not rooms:
            return
        # Check if unread counts changed
        old_unreads = {r.name: r.unread for r in self.room_list}
        changed = False
        for r in rooms:
            if r.name not in old_unreads or old_unreads[r.name] != r.unread:
                changed = True
                break
        if changed:
            self.room_list = rooms
            log = self.query_one("#chat-log", RichLog)
            log.write("[dim]---[/]")
            for i, room in enumerate(rooms):
                safe_name = self._escape_markup(room.name)
                if room.unread > 0:
                    log.write(f"  [cyan]{self.room_offset + i + 1:2}.[/] {safe_name} [bold red]({room.unread})[/]")
                else:
                    log.write(f"  [cyan]{self.room_offset + i + 1:2}.[/] {safe_name}")
            log.write("")

    async def _fetch_and_display_messages(self, log: RichLog) -> None:
        """Fetch and display messages after entering a room"""
        log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Loading messages...")

        # 메시지 가져오기 (재시도 1번, 10개로 제한하여 속도 향상)
        messages = self.kakao.get_chat_messages(limit=10, retry=1)

        if messages:
            log.write(f"[green]✓[/] {len(messages)} messages loaded")
            log.write("")
            for msg in messages[-10:]:
                self._write_message(log, msg)
            log.write("")
            self.messages = messages
        else:
            reason = self.kakao.diagnose_no_messages()
            log.write(f"[red]✗[/] {reason}")

    async def _scroll_messages_up(self) -> None:
        """Load older messages (up arrow / /u)"""
        self.msg_offset += 10
        log = self.query_one("#chat-log", RichLog)
        messages = self.kakao.get_chat_messages(limit=10, retry=0, msg_offset=self.msg_offset)
        if messages:
            log.clear()
            log.write(f"[dim]── older messages (offset {self.msg_offset}) | ↓ newer ──[/]")
            log.write("")
            for msg in messages:
                self._write_message(log, msg)
            log.write("")
            self.messages = messages
        else:
            self.msg_offset -= 10  # revert, no more messages
            log.write("[dim]No older messages[/]")

    async def _scroll_messages_down(self) -> None:
        """Load newer/latest messages (down arrow / /d)"""
        if self.msg_offset <= 0:
            # Already at latest, just refresh
            self.msg_offset = 0
            log = self.query_one("#chat-log", RichLog)
            await self._fetch_and_display_messages(log)
            return
        self.msg_offset = max(0, self.msg_offset - 10)
        log = self.query_one("#chat-log", RichLog)
        messages = self.kakao.get_chat_messages(limit=10, retry=0, msg_offset=self.msg_offset)
        if messages:
            log.clear()
            if self.msg_offset > 0:
                log.write(f"[dim]── offset {self.msg_offset} | ↑ older | ↓ newer ──[/]")
            else:
                log.write(f"[dim]── latest messages ──[/]")
            log.write("")
            for msg in messages:
                self._write_message(log, msg)
            log.write("")
            self.messages = messages

    async def _refresh_messages_silent(self) -> None:
        """Silent message refresh - fast, no position calculation"""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None, lambda: self.kakao.get_latest_messages_fast(count=5)
            )
        except Exception:
            return
        finally:
            self._refreshing = False
        if messages:
            log = self.query_one("#chat-log", RichLog)
            old_texts = {m.text for m in self.messages[-10:]}
            for msg in messages:
                if msg.text not in old_texts:
                    self._write_message(log, msg)
                    self.messages.append(msg)

    async def _refresh_after_send(self) -> None:
        """전송 후 자동 새로고침 (경량)"""
        if not self.in_chat:
            return
        try:
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None, lambda: self.kakao.get_latest_messages_fast(count=5)
            )
        except Exception:
            return
        if messages:
            log = self.query_one("#chat-log", RichLog)
            old_texts = {m.text for m in self.messages[-10:]}
            for msg in messages:
                if msg.text not in old_texts:
                    self._write_message(log, msg)
                    self.messages.append(msg)

    def _print_welcome(self, log: RichLog) -> None:
        """Welcome message"""
        log.write("[dim]⏺[/] Ready. Type [cyan]/[/] for commands.")
        log.write("")

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Show palette when / is typed"""
        palette = self.query_one("#command-palette")
        if event.value == "/":
            palette.add_class("visible")
        elif not event.value.startswith("/"):
            palette.remove_class("visible")

    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        message = event.value.strip()
        if not message:
            return

        event.input.clear()
        self.query_one("#command-palette").remove_class("visible")

        if message.startswith("/"):
            await self.handle_command(message)
        else:
            await self.send_message(message)

        # 명령어 실행 후 입력창에 포커스 복구
        self._focus_input()

    async def handle_command(self, cmd: str) -> None:
        """명령어 처리"""
        log = self.query_one("#chat-log", RichLog)
        parts = cmd[1:].split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("o", "open", "room"):
            if args:
                room_name = args
                row_index = 0

                # Select by number - use fast index-based opening
                if args.isdigit():
                    num = int(args)
                    idx = num - self.room_offset - 1
                    if 0 <= idx < len(self.room_list):
                        room_name = self.room_list[idx].name
                        row_index = self.room_list[idx].row_index
                    else:
                        log.write(f"[red]✗[/] Invalid room number {num}. Current range: {self.room_offset + 1}-{self.room_offset + len(self.room_list)}")
                        return

                safe_room = self._escape_markup(room_name)
                log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Connecting to '{safe_room}'...")

                # In the TUI, force AXPress-only room opening so we can confirm
                # whether foreground jumping comes from the raise+Return fallback.
                if row_index > 0:
                    success = self.kakao.open_room_by_index(
                        row_index,
                        room_name,
                        allow_raise_fallback=False,
                    )
                else:
                    success = self.kakao.open_room_by_name(
                        room_name,
                        allow_raise_fallback=False,
                    )

                if success:
                    self.current_room = room_name
                    self.in_chat = True
                    self.in_room_list = False
                    self.msg_offset = 0
                    log.write(f"[green]✓[/] Connected to {safe_room}")
                    log.write("[dim]  /r refresh | ↑ older | ↓ newer | /b back[/]")
                    log.write("")
                    self.messages = []
                    await self._fetch_and_display_messages(log)
                else:
                    log.write(f"[red]✗[/] Failed to open '{safe_room}' with AXPress-only mode.")
                    log.write("[dim]  This means the old raise+Return fallback was likely doing the real work.[/]")
                    log.write("[dim]  CLI fallback is still available while we test a better no-focus-open strategy.[/]")
            else:
                log.write("[yellow]Usage:[/] /o <number> or /o <name>")
                log.write("[dim]  Run /l first to see the list[/]")

        elif command in ("l", "list", "rooms"):
            log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Fetching rooms...")
            # 카톡 활성화 없이 백그라운드에서 읽기 (창 안 뜸)
            self.room_offset = 0
            try:
                rooms = self.kakao.get_chat_rooms(limit=10, offset=0)
            except Exception:
                rooms = []
            self.room_list = rooms
            self.in_room_list = True
            self.in_chat = False
            if rooms:
                log.write(f"[green]✓[/] Found [cyan]{len(rooms)}[/] rooms (1-10)")
                log.write("")
                for i, room in enumerate(rooms):
                    safe_name = self._escape_markup(room.name)
                    if room.unread > 0:
                        log.write(f"  [cyan]{i+1:2}.[/] {safe_name} [bold red]({room.unread})[/]")
                    else:
                        log.write(f"  [cyan]{i+1:2}.[/] {safe_name}")
                log.write("")
                log.write("[dim]  /o <n> to connect | ↓ more | /s <query>[/]")
            else:
                reason = self.kakao.diagnose_no_rooms()
                log.write(f"[red]✗[/] {reason}")

        elif command in ("s", "search"):
            if args:
                log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Searching for '{args}'...")
                rooms = self.kakao.search_rooms(args)
                self.search_results = rooms
                self.room_list = rooms  # Use search results for /o command
                self.in_room_list = True
                self.in_chat = False
                if rooms:
                    log.write(f"[green]✓[/] Found [cyan]{len(rooms)}[/] results")
                    log.write("")
                    for i, room in enumerate(rooms):
                        safe_name = self._escape_markup(room.name)
                        log.write(f"  [cyan]{i+1:2}.[/] {safe_name}")
                    log.write("")
                    log.write("[dim]  /o <n> to connect[/]")
                else:
                    log.write(f"[yellow]⚠[/] No rooms found for '{args}'")
            else:
                log.write("[yellow]Usage:[/] /s <query>")

        elif command in ("r", "refresh"):
            if self.in_chat:
                self.msg_offset = 0
                await self._fetch_and_display_messages(log)
            elif self.in_room_list:
                await self.handle_command("/l")
            else:
                log.write("[dim]Use /o to enter a room first.[/]")

        elif command in ("u", "up"):
            if self.in_chat:
                await self._scroll_messages_up()
            elif self.in_room_list:
                await self.action_load_prev_rooms()
            else:
                log.write("[dim]Use /o to enter a room first.[/]")

        elif command in ("d", "down"):
            if self.in_chat:
                await self._scroll_messages_down()
            elif self.in_room_list:
                await self.action_load_more_rooms()
            else:
                log.write("[dim]Use /o to enter a room first.[/]")

        elif command in ("b", "back"):
            if self.in_chat:
                closed = False
                if self.current_room:
                    self.kakao.current_room = self.current_room
                    closed = self.kakao.close_current_chat()
                self.in_chat = False
                self.in_room_list = True
                self.msg_offset = 0
                self.messages = []
                self.current_room = None
                log.clear()
                if closed:
                    log.write("[dim]⏺[/] Closed chat window")
                else:
                    log.write("[dim]⏺[/] Returned to room list mode")
                    log.write("[dim]  Chat window may still be open[/]")
                log.write("")
                await self.handle_command("/l")
            else:
                log.write("[dim]Already at room list[/]")

        elif command in ("c", "clear"):
            log.clear()
            if self.in_chat:
                safe_room = self._escape_markup(self.current_room or "")
                log.write(f"[dim]⏺[/] {safe_room}")
                log.write("[dim]  /r refresh | /b back[/]")
                log.write("")
            else:
                self._print_welcome(log)

        elif command in ("h", "help"):
            self._show_help(log)

        elif command in ("q", "quit"):
            self.exit()

        else:
            log.write(f"[red]Unknown command: /{command}[/]")
            log.write("[dim]Type /h for available commands[/]")

    async def send_message(self, msg: str) -> None:
        """Send message"""
        log = self.query_one("#chat-log", RichLog)

        if not self.current_room:
            log.write("[yellow]⚠[/] Select a room first with /o <name>")
            return

        # If the user is reading older messages, return to the latest position first.
        if self.msg_offset > 0:
            log.write("[dim]⏺[/] Returning to latest messages before sending...")
            self.msg_offset = 0
            self.kakao.scroll_to_bottom()
            await asyncio.sleep(0.15)

        # 가짜 전송 로그 (딜레이 없이)
        log.write(f"[dim]⏺[/] Sending...")

        # Send message
        success = self.kakao.send_message(msg)

        if success:
            now = datetime.now().strftime("%H:%M")
            safe_msg = self._escape_markup(msg)
            log.write(f"  [dim]│[/] [green]>[/] {safe_msg} [dim]{now}[/]")
            # Add to self.messages so refresh won't show it again
            self.messages.append(Message(sender="", text=msg, is_me=True))
            # 전송 후 1초 뒤 자동 새로고침 (카톡이 처리할 시간)
            self.set_timer(1.0, self._refresh_after_send)
        else:
            reason = self.kakao.diagnose_send_failure()
            log.write(f"[red]✗[/] {reason}")

    def _update_room_bar(self) -> None:
        """No longer used - room bar removed"""
        pass

    def _show_help(self, log: RichLog) -> None:
        """Show help"""
        log.write("")
        log.write("[bold cyan]Commands[/]")
        log.write("")
        log.write("  [cyan]/l[/]  [dim]/list[/]       List chat rooms")
        log.write("  [cyan]/o[/]  [dim]/open <n>[/]   Connect to room #n")
        log.write("  [cyan]/r[/]  [dim]/refresh[/]    Refresh messages")
        log.write("  [cyan]/u[/]  [dim]/up[/]         Older messages")
        log.write("  [cyan]/d[/]  [dim]/down[/]       Newer messages")
        log.write("  [cyan]/b[/]  [dim]/back[/]       Back to room list")
        log.write("  [cyan]/s[/]  [dim]/search[/]     Search rooms")
        log.write("  [cyan]/c[/]  [dim]/clear[/]      Clear screen")
        log.write("  [cyan]/h[/]  [dim]/help[/]       This help")
        log.write("  [cyan]/q[/]  [dim]/quit[/]       Exit (Ctrl+Q)")
        log.write("")
        log.write("[bold cyan]Navigation[/]")
        log.write("")
        log.write("  [cyan]↑[/]  Older messages (in chat) / prev rooms")
        log.write("  [cyan]↓[/]  Newer messages (in chat) / more rooms")
        log.write("")
        log.write("[dim]Just type to send a message when in a room[/]")
        log.write("")

    async def action_refresh(self) -> None:
        """Refresh messages (non-blocking)"""
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Refreshing messages...")
        try:
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None, lambda: self.kakao.get_chat_messages(retry=1)
            )
        except Exception:
            reason = self.kakao.diagnose_no_messages()
            log.write(f"[red]✗[/] {reason}")
            self._focus_input()
            return
        if messages:
            log.write(f"[green]✓[/] Retrieved [cyan]{len(messages)}[/] messages")
            log.write("")
            for msg in messages[-10:]:
                safe_text = self._escape_markup(msg.text)
                if msg.is_me:
                    log.write(f"  [dim]│[/] [green]>[/] {safe_text}")
                else:
                    safe_sender = self._escape_markup(msg.sender) if msg.sender else "?"
                    log.write(f"  [dim]│[/] [cyan]{safe_sender}[/] {safe_text}")
            log.write("")
            self.messages = messages
        else:
            reason = self.kakao.diagnose_no_messages()
            log.write(f"[red]✗[/] {reason}")

        self._focus_input()

    def action_clear_log(self) -> None:
        """Clear screen"""
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        self._print_welcome(log)

    def action_hide_palette(self) -> None:
        """Hide palette"""
        self.query_one("#command-palette").remove_class("visible")

    async def action_load_more_rooms(self) -> None:
        """Load next 10 rooms (down arrow) or latest messages in chat"""
        if self.in_chat:
            await self._scroll_messages_down()
            return
        if not self.in_room_list:
            return

        log = self.query_one("#chat-log", RichLog)
        self.room_offset += 10
        log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Loading rooms {self.room_offset + 1}-{self.room_offset + 10}...")

        # 카톡 활성화 없이 백그라운드에서 읽기
        rooms = self.kakao.get_chat_rooms(limit=10, offset=self.room_offset)

        if rooms:
            self.room_list = rooms
            log.write(f"[green]✓[/] Rooms {self.room_offset + 1}-{self.room_offset + len(rooms)}")
            log.write("")
            for i, room in enumerate(rooms):
                safe_name = self._escape_markup(room.name)
                if room.unread > 0:
                    log.write(f"  [cyan]{self.room_offset + i + 1:2}.[/] {safe_name} [bold red]({room.unread})[/]")
                else:
                    log.write(f"  [cyan]{self.room_offset + i + 1:2}.[/] {safe_name}")
            log.write("")
            log.write("[dim]  /o <n> | ↑ prev | ↓ more[/]")
        else:
            log.write("[yellow]⚠[/] No more rooms")
            self.room_offset -= 10  # Revert offset

        self._focus_input()

    async def action_load_prev_rooms(self) -> None:
        """Load previous 10 rooms (up arrow) or older messages in chat"""
        if self.in_chat:
            await self._scroll_messages_up()
            return
        if not self.in_room_list:
            return

        if self.room_offset <= 0:
            return

        log = self.query_one("#chat-log", RichLog)
        self.room_offset -= 10
        if self.room_offset < 0:
            self.room_offset = 0

        log.write(f"[yellow]{SPINNER_FRAMES[0]}[/] Loading rooms {self.room_offset + 1}-{self.room_offset + 10}...")

        # 카톡 활성화 없이 백그라운드에서 읽기
        rooms = self.kakao.get_chat_rooms(limit=10, offset=self.room_offset)

        if rooms:
            self.room_list = rooms
            log.write(f"[green]✓[/] Rooms {self.room_offset + 1}-{self.room_offset + len(rooms)}")
            log.write("")
            for i, room in enumerate(rooms):
                safe_name = self._escape_markup(room.name)
                if room.unread > 0:
                    log.write(f"  [cyan]{self.room_offset + i + 1:2}.[/] {safe_name} [bold red]({room.unread})[/]")
                else:
                    log.write(f"  [cyan]{self.room_offset + i + 1:2}.[/] {safe_name}")
            log.write("")
            log.write("[dim]  /o <n> | ↑ prev | ↓ more[/]")

        self._focus_input()


if __name__ == "__main__":
    app = KakaoTerminal()
    app.run()
