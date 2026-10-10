"""Native desktop HUD for macOS/Linux, also usable as a Windows alternative."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import os
from pathlib import Path
import queue
import sys
import threading
import time
import webbrowser

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

# XWayland supplies positioning/stacking that ordinary Wayland clients cannot
# request. Respect an explicit backend, and keep native Wayland usable otherwise.
if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

try:
    from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal, QLocale, QLockFile
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                                   QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                                   QSizeGrip, QSystemTrayIcon, QVBoxLayout, QWidget)
except ImportError as error:
    raise SystemExit("The desktop HUD needs Qt. Run: python3 -m pip install -r requirements-overlay.txt\n"
                     "Or use the ready-to-run macOS/Linux package. Details: " + str(error)) from error

from dashboard import data_directory, start_server
from metrics import atomic_json, read_selection
from overlay_state import OverlayState, presentation


STYLE = """
QWidget { background: #10171d; color: #edf3f7; font-size: 13px; }
QWidget#hud { border: 1px solid #526977; border-radius: 10px; }
QLabel { background: transparent; border: none; }
QLabel#badge { color: #83e5c9; font-size: 11px; font-weight: 700; }
QLabel#metric { color: #83e5c9; font-size: 30px; font-weight: 700; }
QLabel#muted { color: #b0bec8; font-size: 11px; }
QPushButton { background: #263943; border: 1px solid #6b8592; border-radius: 5px; padding: 5px 10px; min-height: 24px; }
QPushButton:hover { background: #334e5a; border-color: #83e5c9; }
QPushButton:focus { border: 2px solid #83e5c9; }
QPushButton:disabled { color: #87959e; background: #1b272f; border-color: #40515b; }
QMenu { background: #19232b; border: 1px solid #6b8592; padding: 6px; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background: #334e5a; }
QMenu::item:disabled { color: #87959e; }
QLineEdit, QListWidget { background: #19232b; border: 1px solid #6b8592; border-radius: 5px; padding: 8px; }
QListWidget::item { padding: 10px; }
QListWidget::item:selected { background: #334e5a; }
QSizeGrip { background: transparent; width: 18px; height: 18px; }
"""


def mac_window_state(widget, configure=False, restore=False):
    """Operate only on this Qt window, using AppKit via the public ObjC runtime."""
    if sys.platform != "darwin" or QApplication.platformName() != "cocoa":
        return {}
    objc = ctypes.CDLL(ctypes.util.find_library("objc"))
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    selector = lambda name: objc.sel_registerName(name.encode("ascii"))
    pointer = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    integer = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    boolean = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    set_integer = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", objc))
    set_bool = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(("objc_msgSend", objc))
    send_object = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    window = pointer(int(widget.winId()), selector("window"))
    if not window:
        return {}
    if restore and boolean(window, selector("isMiniaturized")):
        send_object(window, selector("deminiaturize:"), None)
    behavior = integer(window, selector("collectionBehavior"))
    if configure:
        # canJoinAllSpaces | fullScreenAuxiliary; conflicting primary/move flags off.
        behavior = (behavior & ~(2 | 128)) | 1 | 256
        set_integer(window, selector("setCollectionBehavior:"), behavior)
        set_bool(window, selector("setHidesOnDeactivate:"), False)
        set_integer(window, selector("setLevel:"), 3 if widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint else 0)
    return {"collection_behavior": integer(window, selector("collectionBehavior")),
            "level": integer(window, selector("level")),
            "miniaturized": boolean(window, selector("isMiniaturized"))}


class Instance(QObject):
    show_requested = Signal()

    def __init__(self, runtime):
        super().__init__()
        runtime.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(runtime / "overlay-instance.lock"))
        self.lock.setStaleLockTime(0)
        key = hashlib.sha256(str(runtime.resolve()).encode("utf-8")).hexdigest()[:24]
        self.name = "codex-token-hud-" + key
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.accept)
        self.connections = set()

    def acquire(self):
        # Windows named pipes permit multiple listeners; a file lock also closes
        # the simultaneous-launch race on every supported desktop.
        if not self.lock.tryLock(0):
            if self.lock.error() != QLockFile.LockError.LockFailedError:
                raise RuntimeError("Cannot lock the HUD runtime directory")
            other = QLocalSocket(self)
            other.connectToServer(self.name)
            if other.waitForConnected(1000):
                other.write(b"show\n")
                other.waitForBytesWritten(1000)
                other.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)  # Safe after acquiring the instance lock.
        if not self.server.listen(self.name):
            raise RuntimeError("Cannot acquire the HUD instance: " + self.server.errorString())
        return True

    def close(self):
        for socket in list(self.connections):
            socket.readyRead.disconnect()
            socket.disconnected.disconnect()
            socket.abort()
            socket.deleteLater()
        self.connections.clear()
        self.server.close()
        self.lock.unlock()

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections.add(socket)
            socket.readyRead.connect(lambda s=socket: self.read(s))
            socket.disconnected.connect(lambda s=socket: self.release(s))
            self.read(socket)

    def read(self, socket):
        if socket.canReadLine() and bytes(socket.readLine()).strip() == b"show":
            self.show_requested.emit()

    def release(self, socket):
        self.connections.discard(socket)
        socket.deleteLater()


class Worker(QObject):
    updated = Signal(object)

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.commands = queue.Queue()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="hud-telemetry", daemon=True)

    def run(self):
        while not self.stop.is_set():
            if self.state.service.lock.acquire(blocking=False):
                command = None
                try:
                    try:
                        command = self.commands.get_nowait()
                    except queue.Empty:
                        pass
                    result = self.state.command(command[1], command[2]) if command else self.state.snapshot()
                    if command:
                        result["ack"] = {"id": command[0], "name": command[1]}
                except Exception as error:
                    result = {"error": str(error), "updated_at_ms": time.time() * 1000}
                    if command:
                        result["ack"] = {"id": command[0], "name": command[1], "error": str(error)}
                finally:
                    self.state.service.lock.release()
                if not self.stop.is_set():
                    self.updated.emit(result)
            self.stop.wait(0.25)

    def shutdown(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=3)


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.full_text = ""
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self.full_text = text
        self.setToolTip(text)
        super().setText(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(10, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.full_text)


class ConversationPicker(QDialog):
    def __init__(self, hud):
        super().__init__(hud)
        self.hud = hud
        self.thread_id = None
        self.setWindowTitle(hud.tr("选择并固定对话", "Choose and pin a conversation"))
        self.resize(660, 440)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText(hud.tr("搜索标题或完整对话 ID", "Search title or full conversation ID"))
        layout.addWidget(self.search)
        self.items = QListWidget()
        layout.addWidget(self.items)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.pick)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.search.textChanged.connect(self.populate)
        self.items.itemDoubleClicked.connect(lambda item: self.pick())
        self.items.itemSelectionChanged.connect(self.enable_button)
        self.populate()

    def populate(self):
        current = (self.hud.snapshot.get("thread") or {}).get("id")
        query = self.search.text().strip().casefold()
        self.items.clear()
        for row in self.hud.snapshot.get("threads", []):
            if query and query not in (row["title"] + " " + row["id"]).casefold():
                continue
            item = QListWidgetItem(row["title"] + "\n" + row["id"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.items.addItem(item)
            if row["id"] == current:
                self.items.setCurrentItem(item)
        self.enable_button()

    def enable_button(self):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.items.currentItem() is not None)

    def pick(self):
        item = self.items.currentItem()
        if item:
            self.thread_id = item.data(Qt.ItemDataRole.UserRole)
            self.accept()


def tray_icon():
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#19232b"))
    painter.drawRoundedRect(0, 0, 32, 32, 7, 7)
    painter.setBrush(QColor("#83e5c9"))
    for x, height in ((6, 8), (14, 18), (22, 13)):
        painter.drawRoundedRect(x, 25 - height, 4, height, 2, 2)
    painter.end()
    return QIcon(image)


class ResizeGrip(QSizeGrip):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor("#b0bec8"))
        for offset in (5, 9, 13):
            painter.drawLine(self.width() - offset, self.height() - 3, self.width() - 3, self.height() - offset)
        painter.end()


class Hud(QWidget):
    def __init__(self, server, language="auto", start_worker=True, tray=True):
        super().__init__()
        self.server = server
        self.runtime = server.service.runtime
        self.zh = language == "zh" or language == "auto" and QLocale.system().name().startswith("zh")
        self.snapshot = {}
        self.received = 0.0
        self.request_id = 0
        self.pending_id = None
        self.feedback = ""
        self.feedback_until = 0.0
        self.drag_offset = None
        self.resize_start = None
        self.native_error = ""
        self.restore_until = 0.0
        self.restore_timer = QTimer(self)
        self.restore_timer.setInterval(100)
        self.restore_timer.timeout.connect(self.finish_restore)
        self.setObjectName("hud")
        self.setWindowTitle("Codex Token HUD")
        # A normal Linux window preserves a taskbar entry on desktops without trays.
        kind = Qt.WindowType.Tool if sys.platform == "darwin" else Qt.WindowType.Window
        self.setWindowFlags(kind | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(640, 140)
        self.setWindowIcon(tray_icon())
        self.setStyleSheet(STYLE)
        self.build_ui()
        self.build_menu()
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Codex Token HUD")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        if tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.restore_layout()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self.save_layout)
        self.worker = Worker(OverlayState(server.service))
        self.worker.updated.connect(self.apply_snapshot)
        if start_worker:
            self.worker.thread.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.render)
        self.timer.start(250)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.write_status)
        self.status_timer.start(1000)
        self.menu.aboutToShow.connect(self.update_menu)
        self.render()

    def tr(self, zh, en):
        return zh if self.zh else en

    def label(self, text="", name="", elided=False):
        item = ElidedLabel(text) if elided else QLabel(text)
        item.setObjectName(name)
        item.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return item

    def button(self, text, action):
        button = QPushButton(text)
        button.clicked.connect(action)
        return button

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 7)
        layout.setSpacing(5)
        header = QHBoxLayout()
        self.badge = self.label("CODEX TOKEN HUD", "badge")
        header.addWidget(self.badge)
        self.title_label = self.label("", elided=True)
        header.addWidget(self.title_label, 1)
        self.choose_button = self.button(self.tr("选对话", "Choose chat"), self.choose)
        self.panel_button = self.button(self.tr("区间统计", "Range stats"), self.open_dashboard)
        self.refresh_button = self.button(self.tr("立即刷新", "Refresh"), lambda: self.request("refresh"))
        self.more_button = self.button("⋯", lambda: self.menu.popup(self.more_button.mapToGlobal(QPoint(0, self.more_button.height()))))
        self.more_button.setAccessibleName(self.tr("更多操作", "More actions"))
        for button in (self.choose_button, self.panel_button, self.refresh_button, self.more_button):
            header.addWidget(button)
        layout.addLayout(header)
        values = QHBoxLayout()
        model_box = QVBoxLayout()
        self.mode_label = self.label("", "muted")
        self.model_label = self.label("", elided=True)
        model_box.addWidget(self.mode_label)
        model_box.addWidget(self.model_label)
        values.addLayout(model_box, 1)
        for name, caption, unit in (("rate_label", self.tr("输出速率", "Output speed"), "tok/s"),
                                    ("cache_label", self.tr("缓存命中率", "Input cache"), "%")):
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(self.label(caption, "muted"))
            line = QHBoxLayout()
            metric = self.label("—", "metric")
            setattr(self, name, metric)
            line.addWidget(metric)
            line.addWidget(self.label(unit, "muted"), 0, Qt.AlignmentFlag.AlignBottom)
            line.addStretch()
            box.addLayout(line)
            values.addLayout(box, 1)
        layout.addLayout(values, 1)
        footer = QHBoxLayout()
        self.status_label = self.label("", "muted", elided=True)
        footer.addWidget(self.status_label, 1)
        self.latest_button = self.button(self.tr("返回最近响应", "Latest response"), lambda: self.request("latest"))
        self.latest_button.hide()
        footer.addWidget(self.latest_button)
        self.grip = ResizeGrip(self)
        self.grip.setToolTip(self.tr("拖动调整大小", "Drag to resize"))
        footer.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(footer)
        self.title_label.setToolTip(self.tr("拖动空白处移动悬浮条", "Drag empty space to move the HUD"))

    def build_menu(self):
        self.menu = QMenu(self)
        self.show_action = self.menu.addAction(self.tr("显示悬浮条", "Show HUD"), self.show_hud)
        self.menu.addAction(self.tr("选择并固定对话…", "Choose and pin a chat…"), self.choose)
        self.follow_action = self.menu.addAction(self.tr("解除固定，跟随最新活动", "Unpin and follow latest activity"), lambda: self.request("follow"))
        self.menu.addAction(self.tr("区间统计：按时间或首尾消息…", "Range stats: times or messages…"), self.open_dashboard)
        self.refresh_action = self.menu.addAction(self.tr("立即刷新数据", "Refresh data now"), lambda: self.request("refresh"))
        self.menu.addSeparator()
        self.top_action = QAction(self.tr("始终置顶", "Always on top"), self, checkable=True, checked=True)
        self.top_action.triggered.connect(self.toggle_topmost)
        self.menu.addAction(self.top_action)
        self.menu.addAction(self.tr("重置位置与大小", "Reset position and size"), self.reset_layout)
        self.hide_action = self.menu.addAction(self.tr("隐藏悬浮条", "Hide HUD"), self.hide_hud)
        self.menu.addSeparator()
        self.menu.addAction(self.tr("退出工具", "Quit"), QApplication.instance().quit)

    def update_menu(self):
        self.show_action.setEnabled(not self.isVisible() or self.isMinimized())
        self.hide_action.setEnabled(self.tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable())
        self.follow_action.setEnabled(bool(self.snapshot.get("pinned_thread_id")))
        self.refresh_action.setEnabled(self.pending_id is None)

    def request(self, name, thread_id=None):
        self.request_id += 1
        self.pending_id = self.request_id
        thread_id = thread_id or (self.snapshot.get("thread") or {}).get("id", "")
        self.worker.commands.put((self.request_id, name, thread_id))
        self.feedback = self.tr("正在重新扫描并读取日志…", "Rescanning and reading logs…") if name == "refresh" else self.tr("正在应用…", "Applying…")
        self.feedback_until = time.monotonic() + 30
        self.render()

    def apply_snapshot(self, value):
        previous = ((self.snapshot.get("live") or {}).get("metrics") or {}).get("last") or {}
        self.snapshot = value
        self.received = time.monotonic()
        ack = value.get("ack") or {}
        if self.pending_id is not None and ack.get("id") == self.pending_id:
            self.pending_id = None
            if ack.get("error"):
                self.feedback = self.tr("操作失败：", "Action failed: ") + ack["error"]
            elif ack["name"] == "refresh":
                sample = (((value.get("live") or {}).get("metrics") or {}).get("last") or {})
                new = sample.get("measured_at_ms") != previous.get("measured_at_ms")
                self.feedback = self.tr("已重新读取日志 · " + ("发现新统计" if new else "暂无新的完成响应"),
                                        "Logs reread · " + ("new sample found" if new else "no new completed response"))
            else:
                self.feedback = self.tr("已应用", "Applied")
            self.feedback_until = time.monotonic() + 7
        self.render()

    def render(self):
        view = presentation(self.snapshot)
        if self.received and time.monotonic() - self.received > 4:
            view.update(rate="—", cache="—", kind="busy")
        self.title_label.setText(view["title"] or self.tr("请选择本地对话", "Select a local conversation"))
        self.model_label.setText(view["model"] or self.tr("模型尚无记录", "Model not recorded yet"))
        pinned = bool(self.snapshot.get("pinned_thread_id"))
        self.badge.setText("CODEX · " + self.tr("固定对话" if pinned else "最新活动", "PINNED" if pinned else "LATEST ACTIVITY"))
        self.mode_label.setText(self.tr("已确认区间平均值", "Confirmed range averages") if view["range"] else self.tr("最近完成响应", "Latest completed response"))
        self.rate_label.setText(view["rate"])
        self.cache_label.setText(view["cache"])
        self.latest_button.setVisible(view["range"])
        self.refresh_button.setEnabled(self.pending_id is None)
        self.refresh_button.setText(self.tr("刷新中…", "Refreshing…") if self.pending_id else self.tr("立即刷新", "Refresh"))
        names = {"empty": ("暂无本地日志，点击选对话或区间统计", "No local logs. Check the Codex home or offline files."),
                 "missing": ("固定对话的日志不可用，可解除固定或另选对话", "Pinned log unavailable. Unpin or choose another chat."),
                 "ambiguous": ("多个对话同时更新，请选择并固定对话", "Several chats updated together. Choose and pin one."),
                 "waiting": ("等待响应完成后记录计数", "Waiting for completed-response counts"),
                 "current": ("最近响应已更新", "Latest response updated"),
                 "generating": ("正在生成，等待本次计数", "Generating · awaiting completed counts"),
                 "tools": ("工具运行中", "Tools running"),
                 "pending": ("模型或轮次已变化，等待本次计数", "Model or turn changed · waiting for counts"),
                 "history": ("历史响应超过 15 分钟，已隐藏旧数值", "Response older than 15 minutes · old values hidden"),
                 "unreadable": ("日志暂不可读", "Log temporarily unreadable"),
                 "range": ("区间快照 · %s 条响应" % view["sample_count"], "Range snapshot · %s responses" % view["sample_count"]),
                 "error": ("读取失败，请立即刷新", "Read failed. Try Refresh."),
                 "busy": ("正在读取日志或计算区间…", "Reading logs or calculating a range…")}
        status = self.tr(*names[view["kind"]])
        if view["at_ms"]:
            status += " · " + time.strftime("%m-%d %H:%M:%S", time.localtime(view["at_ms"] / 1000))
        if self.feedback and time.monotonic() < self.feedback_until:
            status = self.feedback
        self.status_label.setText(status)
        if self.tray.isVisible() and not QSystemTrayIcon.isSystemTrayAvailable():
            self.show_hud()  # Removing a tray extension must not strand a hidden HUD.

    def choose(self):
        picker = ConversationPicker(self)
        if picker.exec() == QDialog.DialogCode.Accepted:
            self.request("pin", picker.thread_id)

    def open_dashboard(self):
        webbrowser.open(self.server.url((self.snapshot.get("thread") or {}).get("id", "")))

    def show_hud(self):
        self.restore_until = time.monotonic() + 2
        self.restore_window()
        # Cocoa animations and X11 window-manager replies may complete after
        # showNormal() returns. Watch briefly without rebinding or taking focus.
        self.restore_timer.start()

    def restore_window(self):
        if self.isMinimized():
            self.showNormal()
        elif not self.isVisible():
            self.show()
        try:
            mac_window_state(self, restore=True)
        except (OSError, ValueError, AttributeError) as error:
            self.native_error = str(error)
        self.raise_()

    def finish_restore(self):
        if time.monotonic() >= self.restore_until:
            self.restore_timer.stop()
            return
        try:
            if self.isMinimized() or not self.isVisible() or mac_window_state(self).get("miniaturized"):
                self.restore_window()
        except (OSError, ValueError, AttributeError) as error:
            self.native_error = str(error)

    def hide_hud(self):
        if self.tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_hud()

    def toggle_topmost(self, checked):
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        if visible:
            self.show()
        self.save_layout()

    def contextMenuEvent(self, event):
        self.menu.popup(event.globalPos())

    def closeEvent(self, event):
        if self.tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide_hud()
        else:
            event.accept()
            QApplication.instance().quit()

    def default_rect(self):
        area = QApplication.primaryScreen().availableGeometry()
        width, height = min(850, area.width()), 150
        return QRect(area.x() + (area.width() - width) // 2, area.bottom() - height - 18, width, height)

    def restore_layout(self):
        saved = read_selection(self.runtime / "overlay-layout.json")
        default = self.default_rect()
        try:
            rect = QRect(*(int(saved.get(k, fallback)) for k, fallback in zip(("x", "y", "width", "height"),
                                                                                 (default.x(), default.y(), default.width(), default.height()))))
            rect.setWidth(max(self.minimumWidth(), min(rect.width(), 4096)))
            rect.setHeight(max(self.minimumHeight(), min(rect.height(), 2048)))
            # Require a visible usable area after monitor removal / resolution changes.
            if not any(rect.intersected(s.availableGeometry()).width() >= 160 and
                       rect.intersected(s.availableGeometry()).height() >= 60 for s in QApplication.screens()):
                rect = default
        except (TypeError, ValueError, OverflowError):
            rect = default
        self.setGeometry(rect)
        topmost = saved.get("topmost", True) is not False
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
        self.top_action.setChecked(topmost)

    def reset_layout(self):
        self.setGeometry(self.default_rect())
        self.show_hud()
        self.save_layout()

    def save_layout(self):
        if self.isMinimized():
            return
        rect = self.geometry()
        try:
            atomic_json(self.runtime / "overlay-layout.json", {"x": rect.x(), "y": rect.y(), "width": rect.width(),
                        "height": rect.height(), "topmost": self.top_action.isChecked()})
        except OSError as error:
            self.native_error = str(error)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_timer"):
            self.save_timer.start()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "save_timer"):
            self.save_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            mac_window_state(self, configure=True)
        except (OSError, ValueError, AttributeError) as error:
            self.native_error = str(error)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position().toPoint()
            edges = Qt.Edge(0)
            if point.x() <= 8:
                edges |= Qt.Edge.LeftEdge
            elif point.x() >= self.width() - 8:
                edges |= Qt.Edge.RightEdge
            if point.y() <= 8:
                edges |= Qt.Edge.TopEdge
            elif point.y() >= self.height() - 8:
                edges |= Qt.Edge.BottomEdge
            handle = self.windowHandle()
            if edges:
                if not handle.startSystemResize(edges):
                    self.resize_start = (event.globalPosition().toPoint(), self.geometry(), edges)
            elif not handle.startSystemMove():
                self.drag_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
        elif self.resize_start:
            origin, rect, edges = self.resize_start
            rect = QRect(rect)
            delta = event.globalPosition().toPoint() - origin
            if edges & Qt.Edge.LeftEdge:
                rect.setLeft(min(rect.right() - self.minimumWidth() + 1, rect.left() + delta.x()))
            if edges & Qt.Edge.RightEdge:
                rect.setRight(max(rect.left() + self.minimumWidth() - 1, rect.right() + delta.x()))
            if edges & Qt.Edge.TopEdge:
                rect.setTop(min(rect.bottom() - self.minimumHeight() + 1, rect.top() + delta.y()))
            if edges & Qt.Edge.BottomEdge:
                rect.setBottom(max(rect.top() + self.minimumHeight() - 1, rect.bottom() + delta.y()))
            self.setGeometry(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        self.resize_start = None
        super().mouseReleaseEvent(event)

    def write_status(self):
        try:
            native = mac_window_state(self)
            atomic_json(self.runtime / "status.json", {"pid": os.getpid(), "visible": self.isVisible(),
                        "minimized": self.isMinimized(), "topmost_requested": bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                        "platform": QApplication.platformName(), "window_id": int(self.winId()),
                        "thread_id": (self.snapshot.get("thread") or {}).get("id"),
                        "pinned_thread_id": self.snapshot.get("pinned_thread_id"), "updated_at_ms": time.time() * 1000,
                        "rate": self.rate_label.text(), "cache": self.cache_label.text(), "native": native,
                        "native_error": self.native_error})
        except (OSError, ValueError, AttributeError) as error:
            self.native_error = str(error)

    def shutdown(self):
        self.restore_timer.stop()
        self.timer.stop()
        self.status_timer.stop()
        self.save_timer.stop()
        self.save_layout()
        self.tray.hide()
        self.worker.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--runtime", type=Path, default=data_directory() / "overlay-runtime")
    parser.add_argument("--log", type=Path, action="append", default=[])
    parser.add_argument("--thread", default="", help="Pin an exact local conversation ID on launch")
    parser.add_argument("--language", choices=("auto", "zh", "en"), default="auto")
    parser.add_argument("--quit-after", type=float, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--no-tray", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Codex Token HUD")
    app.setOrganizationName("CodexTokenHud")
    app.setQuitOnLastWindowClosed(False)
    instance = Instance(args.runtime)
    if not instance.acquire():
        return 0
    server = start_server(args.codex_home, args.runtime, args.log, native_enabled=True,
                          native_follow_mode="activity", native_label="macOS 悬浮条" if sys.platform == "darwin" else "Linux 悬浮条" if sys.platform.startswith("linux") else "跨平台悬浮条")
    if args.thread:
        try:
            server.service.post("pin", {"thread_id": args.thread})
        except ValueError:
            # Keep the requested binding visible as unavailable rather than guess.
            atomic_json(args.runtime / "manual-binding.json", {"thread_id": args.thread})
    hud = Hud(server, args.language, tray=not args.no_tray)
    instance.show_requested.connect(hud.show_hud)
    app.applicationStateChanged.connect(lambda state: hud.show_hud() if state == Qt.ApplicationState.ApplicationActive and not hud.isVisible() else None)
    app.aboutToQuit.connect(hud.shutdown)
    hud.show()
    if args.quit_after > 0:
        QTimer.singleShot(int(args.quit_after * 1000), app.quit)
    try:
        return app.exec()
    finally:
        instance.close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
