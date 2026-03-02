# --- START OF FILE ui_extras.py ---
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl


class TopBarExtras(QWidget):
    """右上角的快捷工具栏：包含外部链接和关于按钮"""

    LINK_PORTAL = "https://portal.sufe.edu.cn/main.html#/ServiceCenter"
    LINK_RATING = "https://sufe.myrating.cn/"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent  # 保存父窗口引用用于弹窗
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 去掉边距，使其紧凑
        layout.setSpacing(10)

        # 1. 上财门户按钮
        self.btn_portal = QPushButton("上财门户")
        self.btn_portal.setToolTip("浏览器打开上财门户")
        self.btn_portal.clicked.connect(lambda: self._open_url(self.LINK_PORTAL))

        # 2. 上财锐评按钮
        self.btn_rating = QPushButton("上财锐评")
        self.btn_rating.setToolTip("查看课程评价")
        self.btn_rating.clicked.connect(lambda: self._open_url(self.LINK_RATING))

        # 3. 关于按钮
        self.btn_about = QPushButton("关于")
        self.btn_about.clicked.connect(self._show_about)

        # 样式美化（可选：让它们看起来像链接或者轻量级按钮）
        # 这里使用标准按钮样式，您可以根据喜好修改setStyleSheet

        layout.addWidget(self.btn_portal)
        layout.addWidget(self.btn_rating)
        layout.addWidget(self.btn_about)

    def _open_url(self, url):
        """调用系统默认浏览器打开链接"""
        QDesktopServices.openUrl(QUrl(url))

    def _show_about(self):
        """显示关于对话框"""
        title = "关于 SUFE 选课助手"
        content = (
            "<h3>SUFE 选课助手 GUI v2</h3>"
            "<p>基于 Python PySide6 开发的选课辅助工具。</p>"
            "<hr>"
            "<ul>"
            "<li><b>内置浏览器</b>：自动同步 Cookie 与 User-Agent，解决登录失效问题。</li>"
            "<li><b>智能监控</b>：自动检测空位、过滤重复选课与时间冲突、自动提交选课。</li>"
            "<li><b>多线程</b>：界面流畅，后台实时响应。</li>"
            "</ul>"
            "<p>仅供学习交流使用！</p>"
        )
        QMessageBox.about(self.parent_window, title, content)