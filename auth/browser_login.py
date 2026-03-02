import html
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl


class BrowserLoginController(QObject):
    login_success_signal = Signal()
    login_failed_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(self, eams_session, parent=None):
        super().__init__(parent)
        self.eams = eams_session
        self._state = None
        self._server = None
        self._callback_url = None
        self._lock = threading.Lock()
        self._handled = False

    def start_login(self):
        self._state = secrets.token_urlsafe(24)
        self._handled = False

        try:
            self._server = _CallbackServer(("127.0.0.1", 0), _CallbackHandler)
            self._server.controller = self
            self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._server_thread.start()
        except Exception as exc:
            self.login_failed_signal.emit(f"启动本地回调服务失败: {exc}")
            return

        port = self._server.server_address[1]
        self._callback_url = f"http://127.0.0.1:{port}/callback"
        auth_url = self.eams.build_unified_auth_url(self._callback_url, self._state)

        self.status_signal.emit(f"[INFO] 已启动本地回调服务: 127.0.0.1:{port}")
        self.status_signal.emit("[INFO] 正在调用系统浏览器打开统一认证页面...")

        if not QDesktopServices.openUrl(QUrl(auth_url)):
            self.stop_server()
            self.login_failed_signal.emit("无法打开系统浏览器，请手动复制认证链接后登录。")
            return

        self.status_signal.emit("[INFO] 请在浏览器中完成统一认证登录。")

    def stop_server(self):
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None

    def _finish_callback(self, params):
        with self._lock:
            if self._handled:
                return
            self._handled = True

        state = params.get("state", [""])[0]
        ticket = params.get("ticket", [""])[0] or params.get("code", [""])[0]

        if state and state != self._state:
            self.stop_server()
            self.login_failed_signal.emit("登录状态校验失败（state 不匹配）")
            return

        if not ticket:
            self.stop_server()
            self.login_failed_signal.emit("回调中未携带 ticket/code，无法完成登录。")
            return

        ok = self.eams.exchange_ticket_for_session(ticket=ticket, callback_service=self._callback_url, state=self._state)
        self.stop_server()

        if ok:
            self.status_signal.emit("[SUCCESS] 浏览器登录验证通过。")
            self.login_success_signal.emit()
        else:
            self.login_failed_signal.emit("ticket 换取会话失败，请重试。")


class _CallbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        self.server.controller._finish_callback(params)

        message = "认证结果已接收，可关闭此页面并返回客户端。"
        if "error" in params:
            message = f"认证失败: {params['error'][0]}"

        payload = (
            "<html><head><meta charset='utf-8'></head>"
            "<body><h3>SUFE 选课助手</h3>"
            f"<p>{html.escape(message)}</p></body></html>"
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        return
