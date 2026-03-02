from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtCore import QThread, Signal, QTimer


class LoginVerifyWorker(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, eams_session, cookies):
        super().__init__()
        self.eams = eams_session
        self.cookies = cookies

    def run(self):
        try:
            self.eams.set_cookies_from_browser(self.cookies)
            if self.eams.step1_fetch_profile_id():
                self.finished_signal.emit(True, "验证成功")
            else:
                self.finished_signal.emit(False, "验证失败")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class LoginWindow(QWidget):
    login_success_signal = Signal()

    def __init__(self, eams_session):
        super().__init__()
        self.setWindowTitle("统一身份认证")
        self.resize(1200, 800)
        self.eams = eams_session
        self.login_processed = False
        self.cookie_storage = {}
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.top_bar = QWidget()
        self.top_bar.setFixedHeight(40)
        self.top_bar.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        bar_layout = QHBoxLayout(self.top_bar)
        self.lbl_status = QLabel("[INFO] 正在初始化浏览器...")
        self.lbl_status.setStyleSheet("color: grey; ")
        self.progress = QProgressBar()
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        bar_layout.addWidget(self.lbl_status)
        bar_layout.addWidget(self.progress)
        layout.addWidget(self.top_bar)

        self.webview = QWebEngineView()
        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.cookieStore().deleteAllCookies()
        self.webview.loadProgress.connect(lambda p: (self.progress.setValue(p), self.lbl_status.setText(
            f"[INFO] 加载中 {p}%..." if p < 100 else "请登录")))
        self.lbl_status.setStyleSheet("color: grey; ")
        self.profile.cookieStore().cookieAdded.connect(
            lambda c: self.cookie_storage.update({c.name().data().decode(): c}))
        layout.addWidget(self.webview)

        QTimer.singleShot(200, self._start_load)

    def _start_load(self):
        self.eams.set_user_agent(self.profile.httpUserAgent())
        self.webview.load(f"{self.eams.host}/eams/stdElectCourse.action")
        self.webview.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, success):
        if success and not self.login_processed and self.cookie_storage:
            self.lbl_status.setText("[INFO] 检测到 Cookie，验证中...")
            self.lbl_status.setStyleSheet("color: grey; ")
            self.webview.setEnabled(False)
            self.worker = LoginVerifyWorker(self.eams, list(self.cookie_storage.values()))
            self.worker.finished_signal.connect(self._on_verify)
            self.worker.start()

    def _on_verify(self, success, msg):
        if success:
            self.login_processed = True
            self.lbl_status.setText("[SUCCESS] 登录成功！")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
            self.login_success_signal.emit()
            QTimer.singleShot(1000, self.close)
        else:
            self.webview.setEnabled(True)
            self.lbl_status.setText("[INFO] 验证未通过，请继续登录...")
            self.lbl_status.setStyleSheet("color: grey; ")
