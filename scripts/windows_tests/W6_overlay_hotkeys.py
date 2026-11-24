"""W6 - Overlay click-through, edit mode (60 s idle timer) and global hotkeys on Windows.

    uv run python scripts/windows_tests/W6_overlay_hotkeys.py
    uv run python scripts/windows_tests/W6_overlay_hotkeys.py --method qt --idle-seconds 5

This is a measurement prototype of the *approved behaviour* (DECISIONS.md D-16, PRODUCT_SCOPE.md),
not product code. It opens two windows:

* "W6 fake game": an opaque window that counts mouse clicks it receives.
* a transparent always-on-top Vietnamese overlay placed over the middle of the fake game.

Play mode: the overlay must be click-through, so a click on it must reach the fake game.
Edit mode (Ctrl+Alt+E): the overlay takes the mouse so it can be dragged. The idle timer starts
at the last interaction, resets on every interaction, never fires during a drag, and on exit the
overlay must be click-through again.

Hotkeys are registered with the Win32 ``RegisterHotKey`` API in a dedicated message-loop thread.
Registration failure (for example error 1409, already registered) is reported, never ignored.

Steps to follow while the window is open (about --duration seconds, default 120):
 1. Press F6, F7, F8, F9 once each, and Ctrl+Alt+E.            (hotkey delivery)
 2. In play mode click the middle of the overlay 3 times.       (click-through)
 3. Press Ctrl+Alt+E, drag the overlay, then press it again.   (edit mode)
 4. Press Ctrl+Alt+E, release the mouse and wait --idle-seconds (default 60) without touching.
    The overlay should leave edit mode by itself and become click-through again.
 5. Press Ctrl+Alt+E, keep the button held on a drag longer than --idle-seconds: it must NOT exit.

Then close the fake-game window or wait for the duration. A short manual questionnaire follows.
Everything the script could not observe stays ``N/A`` (never PASS).
"""

import argparse
import ctypes
import sys
import threading
import time
from ctypes import wintypes

from _common import Recorder, require_windows

# ---- Win32 constants -----------------------------------------------------------------------
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_LAYERED, WS_EX_TOPMOST = 0x00000020, 0x00080000, 0x00000008
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

HOTKEYS = {
    "F6": (0, 0x75),
    "F7": (0, 0x76),
    "F8": (0, 0x77),
    "F9": (0, 0x78),
    "Ctrl+Alt+E": (MOD_CONTROL | MOD_ALT, 0x45),
}


def setup_user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetForegroundWindow.restype = wintypes.HWND
    return user32


class HotkeyThread(threading.Thread):
    """Registers hotkeys and pumps WM_HOTKEY in the same thread (a Win32 requirement)."""

    def __init__(self, user32, on_fire) -> None:
        super().__init__(daemon=True)
        self.user32 = user32
        self.on_fire = on_fire
        self.registration: dict[str, dict[str, object]] = {}
        self.ready = threading.Event()
        self.thread_id = 0

    def run(self) -> None:
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        ids: dict[int, str] = {}
        for index, (name, (mods, vk)) in enumerate(HOTKEYS.items(), start=1):
            ok = bool(self.user32.RegisterHotKey(None, index, mods | MOD_NOREPEAT, vk))
            error = None if ok else ctypes.get_last_error()
            self.registration[name] = {
                "registered": ok,
                "error_code": error,
                "already_registered": error == ERROR_HOTKEY_ALREADY_REGISTERED,
            }
            if ok:
                ids[index] = name
        self.ready.set()
        msg = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in ids:
                self.on_fire(ids[msg.wParam], time.perf_counter())
        for index in ids:
            self.user32.UnregisterHotKey(None, index)

    def stop(self) -> None:
        if self.thread_id:
            self.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


def keyboard_layout() -> str | None:
    buffer = ctypes.create_unicode_buffer(16)
    return buffer.value if ctypes.windll.user32.GetKeyboardLayoutNameW(buffer) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--method",
        choices=("win32", "qt"),
        default="win32",
        help="click-through mechanism: Win32 extended style or Qt window flag",
    )
    parser.add_argument("--idle-seconds", type=float, default=60.0)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--no-questions", action="store_true", help="skip the manual questionnaire")
    args = parser.parse_args()

    rec = Recorder("W6", f"Overlay click-through, edit mode and hotkeys [{args.method}]")
    print(f"W6 - overlay and hotkeys [{args.method}]")
    if not require_windows(rec):
        return rec.finish()
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception as exc:  # noqa: BLE001
        rec.check("import PySide6", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()

    user32 = setup_user32()
    log: list[dict[str, object]] = []
    t0 = time.perf_counter()

    def event(kind: str, **data: object) -> None:
        entry = {"t": round(time.perf_counter() - t0, 3), "event": kind, **data}
        log.append(entry)
        print(f"    {entry}")

    class Bridge(QtCore.QObject):
        fired = QtCore.Signal(str, float)

    bridge = Bridge()

    class FakeGame(QtWidgets.QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("W6 fake game (click the overlay area through the overlay)")
            self.resize(900, 500)
            self.clicks = 0
            self.clicks_play = 0
            self.setStyleSheet("background:#264653;color:white;")

        def mousePressEvent(self, e) -> None:  # noqa: N802
            self.clicks += 1
            if not overlay.edit_mode:
                self.clicks_play += 1
            event("fake_game_click", edit_mode=overlay.edit_mode, total=self.clicks)
            self.update()

        def paintEvent(self, e) -> None:  # noqa: N802
            p = QtGui.QPainter(self)
            p.fillRect(self.rect(), QtGui.QColor("#264653"))
            p.setPen(QtGui.QColor("white"))
            p.drawText(20, 30, f"fake game: clicks received = {self.clicks}")
            p.drawText(
                20, 55, "English text of the game would be here: You should not have come here."
            )

    class Overlay(QtWidgets.QWidget):
        def __init__(self) -> None:
            super().__init__()
            flags = (
                QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.WindowStaysOnTopHint
                | QtCore.Qt.WindowType.Tool
                | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setWindowFlags(flags)
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setMouseTracking(True)
            self.resize(520, 90)
            self.edit_mode = False
            self.dragging = False
            self.drag_offset = QtCore.QPoint()
            self.last_interaction = time.perf_counter()
            self.presses_in_edit = 0
            self.presses_in_play = 0
            self.drag_distance = 0
            self.edit_entered_at = 0.0
            self.exit_events: list[dict[str, object]] = []
            self.exit_while_dragging = 0
            self.toggle_ms: list[float] = []
            self.topmost_after_toggle: list[bool] = []
            self.focus_stolen = 0

        # -- helpers ---------------------------------------------------------------------
        def hwnd(self) -> int:
            return int(self.winId())

        def exstyle(self) -> int:
            return int(user32.GetWindowLongPtrW(self.hwnd(), GWL_EXSTYLE))

        def is_click_through(self) -> bool:
            if args.method == "win32":
                return bool(self.exstyle() & WS_EX_TRANSPARENT)
            return bool(self.windowFlags() & QtCore.Qt.WindowType.WindowTransparentForInput)

        def set_click_through(self, on: bool) -> None:
            start = time.perf_counter()
            if args.method == "win32":
                style = self.exstyle() | WS_EX_LAYERED
                style = style | WS_EX_TRANSPARENT if on else style & ~WS_EX_TRANSPARENT
                user32.SetWindowLongPtrW(self.hwnd(), GWL_EXSTYLE, style)
            else:
                self.setWindowFlag(QtCore.Qt.WindowType.WindowTransparentForInput, on)
                self.show()
            self.toggle_ms.append((time.perf_counter() - start) * 1000)
            self.topmost_after_toggle.append(bool(self.exstyle() & WS_EX_TOPMOST))
            self.update()

        def touch(self) -> None:
            self.last_interaction = time.perf_counter()

        # -- modes -----------------------------------------------------------------------
        def enter_edit(self) -> None:
            self.edit_mode = True
            self.touch()
            self.edit_entered_at = time.perf_counter()
            foreground_before = user32.GetForegroundWindow()
            self.set_click_through(False)
            if user32.GetForegroundWindow() == self.hwnd() and foreground_before != self.hwnd():
                self.focus_stolen += 1
            event("edit_enter", click_through=self.is_click_through())

        def exit_edit(self, reason: str) -> None:
            idle = time.perf_counter() - self.last_interaction
            if reason == "idle" and self.dragging:
                self.exit_while_dragging += 1
            self.edit_mode = False
            self.dragging = False
            self.set_click_through(True)
            record = {
                "reason": reason,
                "idle_s": round(idle, 2),
                "click_through_restored": self.is_click_through(),
            }
            self.exit_events.append(record)
            event("edit_exit", **record)

        def tick(self) -> None:
            if (
                self.edit_mode
                and not self.dragging
                and time.perf_counter() - self.last_interaction >= args.idle_seconds
            ):
                self.exit_edit("idle")

        # -- mouse (only reachable in edit mode) -------------------------------------------
        def mousePressEvent(self, e) -> None:  # noqa: N802
            self.touch()
            if self.edit_mode:
                self.presses_in_edit += 1
                self.dragging = True
                self.drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            else:
                self.presses_in_play += 1
                event("overlay_received_click_in_play_mode")

        def mouseMoveEvent(self, e) -> None:  # noqa: N802
            if self.edit_mode:
                self.touch()
                if self.dragging:
                    target = e.globalPosition().toPoint() - self.drag_offset
                    self.drag_distance += abs(target.x() - self.x()) + abs(target.y() - self.y())
                    self.move(target)

        def mouseReleaseEvent(self, e) -> None:  # noqa: N802
            if self.edit_mode:
                self.touch()
                self.dragging = False

        def paintEvent(self, e) -> None:  # noqa: N802
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            p.setBrush(QtGui.QColor(0, 0, 0, int(255 * 0.85)))
            border = QtGui.QPen(QtGui.QColor("#ff3b30" if self.edit_mode else "#00000000"), 3)
            p.setPen(border)
            p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 10, 10)
            p.setPen(QtGui.QColor("white"))
            font = p.font()
            font.setPointSize(16)
            p.setFont(font)
            label = "CHẾ ĐỘ CHỈNH SỬA" if self.edit_mode else "Ngươi không nên đến đây."
            p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, label)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    overlay = Overlay()
    game = FakeGame()
    game.show()
    geo = game.frameGeometry()
    overlay.move(geo.center().x() - overlay.width() // 2, geo.center().y() - overlay.height() // 2)
    overlay.show()
    overlay.set_click_through(True)
    rec.check("overlay starts click-through", overlay.is_click_through())
    event("started", method=args.method, click_through=overlay.is_click_through())

    fired_counts: dict[str, int] = {name: 0 for name in HOTKEYS}
    latencies_ms: list[float] = []

    def on_fire_thread(name: str, when: float) -> None:
        bridge.fired.emit(name, when)

    def on_fired(name: str, when: float) -> None:
        fired_counts[name] += 1
        latencies_ms.append((time.perf_counter() - when) * 1000)
        event("hotkey", key=name, count=fired_counts[name])
        if name == "Ctrl+Alt+E":
            if overlay.edit_mode:
                overlay.exit_edit("key")
            else:
                overlay.enter_edit()
        elif name == "F7":
            overlay.setVisible(not overlay.isVisible())

    bridge.fired.connect(on_fired)
    thread = HotkeyThread(user32, on_fire_thread)
    thread.start()
    thread.ready.wait(5)
    rec.measure("keyboard_layout", keyboard_layout())
    for name, info in thread.registration.items():
        rec.check(f"hotkey {name} registered", bool(info["registered"]), str(info))
    rec.extra["hotkey_registration"] = thread.registration

    timer = QtCore.QTimer()
    timer.timeout.connect(overlay.tick)
    timer.start(250)
    QtCore.QTimer.singleShot(int(args.duration * 1000), app.quit)
    print(f"\nWindow open for {args.duration:.0f} s. Follow the steps in the script docstring.\n")
    app.exec()
    thread.stop()
    thread.join(3)

    # ---- evaluation (None = the step was not performed, so nothing is claimed) ---------------
    for name, count in fired_counts.items():
        if thread.registration[name]["registered"]:
            rec.check(
                f"hotkey {name} delivered",
                True if count else None,
                f"{count} presses" if count else "not pressed during the run",
            )
    if latencies_ms:
        rec.measure("hotkey_dispatch_latency_ms_max", round(max(latencies_ms), 2))

    if game.clicks_play or overlay.presses_in_play:
        rec.check(
            "play mode is click-through (clicks reach the game, none stop at the overlay)",
            game.clicks_play > 0 and overlay.presses_in_play == 0,
            f"game got {game.clicks_play}, overlay swallowed {overlay.presses_in_play}",
        )
    else:
        rec.check("play mode is click-through", None, "no clicks were made in play mode")

    rec.check(
        "edit mode lets the overlay receive clicks and be dragged",
        True if (overlay.presses_in_edit and overlay.drag_distance) else None,
        f"presses={overlay.presses_in_edit}, drag_px={overlay.drag_distance}",
    )

    idle_exits = [x for x in overlay.exit_events if x["reason"] == "idle"]
    if idle_exits:
        e0 = idle_exits[0]
        ok = args.idle_seconds <= float(e0["idle_s"]) <= args.idle_seconds + 2.0
        rec.check(
            f"idle exit fired about {args.idle_seconds:.0f} s after the last interaction",
            ok,
            f"measured {e0['idle_s']} s",
        )
    else:
        rec.check(
            f"idle exit fired after {args.idle_seconds:.0f} s",
            None,
            "not observed (step 4 not performed or run too short)",
        )
    if overlay.exit_events:
        rec.check(
            "every exit from edit mode restored click-through",
            all(x["click_through_restored"] for x in overlay.exit_events),
        )
    rec.check(
        "idle timer never fired during a drag",
        overlay.exit_while_dragging == 0,
        f"{overlay.exit_while_dragging} violations",
    )
    if overlay.topmost_after_toggle:
        rec.check(
            "overlay stayed topmost after every click-through toggle",
            all(overlay.topmost_after_toggle),
        )
        rec.measure("click_through_toggle_ms", [round(x, 2) for x in overlay.toggle_ms])
    rec.measure("overlay_stole_focus_count", overlay.focus_stolen)
    rec.extra["event_log"] = log

    if not args.no_questions and sys.stdin.isatty():
        print("\nManual questionnaire (answer y / n / s to skip):")
        for key, question in (
            (
                "game_receives_f6_f9_when_registered",
                "In a REAL borderless game, did F6-F9 still do what the game expects "
                "while this script held them? (we expect the game NOT to see them)",
            ),
            ("overlay_above_borderless_game", "Did the overlay appear above a BORDERLESS game?"),
            (
                "overlay_above_exclusive_game",
                "Did the overlay appear above an EXCLUSIVE fullscreen game?",
            ),
            (
                "ctrl_alt_e_typed_character",
                "Did Ctrl+Alt+E type a character anywhere (AltGr layouts)?",
            ),
            (
                "game_lost_focus_or_flickered",
                "Did the game lose focus or flicker when overlay mode changed?",
            ),
        ):
            answer = input(f"  {question} ").strip().lower()
            rec.measure(f"manual_{key}", {"y": True, "n": False}.get(answer))
    else:
        rec.note("Manual questionnaire skipped; record the five observations by hand.")
    rec.extra["hotkey_status"] = {
        "specified_in_decisions": list(HOTKEYS),
        "registered_by_this_test_script_only": [
            n for n, info in thread.registration.items() if info["registered"]
        ],
        "wired_to_an_action_in_this_script": ["F7 (toggle overlay visibility)", "Ctrl+Alt+E"],
        "implemented_in_product_code": [],
    }
    rec.note(
        "Hotkey status: F6/F7/F8/F9 and Ctrl+Alt+E are SPECIFIED (DECISIONS.md). This script "
        "only registers them to measure OS behaviour; F6, F8 and F9 trigger no action here and "
        "no product code registers any hotkey yet. Registration working here is not an "
        "implemented feature."
    )
    rec.note(
        "Ctrl+Alt+E is only confirmed once registration succeeded AND the owner finds no "
        "clash in games."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
