# --- START OF FILE ui_components.py ---
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor


class InfoChip(QFrame):
    """显示信息的胶囊/芯片控件 (适配深色模式)"""

    def __init__(self, icon_char, label_text, value_text="--", icon_color="#ffc107"):
        super().__init__()
        # 改动：使用 rgba 实现半透明背景和边框，文字设为亮色
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 15, 0)
        layout.setSpacing(8)

        # 图标 (黄色/亮色以在深色背景突出)
        self.lbl_icon = QLabel(icon_char)
        self.lbl_icon.setStyleSheet(f"color: {icon_color}; font-weight: bold; font-size: 14px;")

        # 标题 (浅灰色)
        self.lbl_title = QLabel(label_text)
        self.lbl_title.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")

        # 数值 (亮白色)
        self.lbl_value = QLabel(value_text)
        self.lbl_value.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, text):
        self.lbl_value.setText(str(text))


class StatusBadge(QFrame):
    """状态指示器 (适配深色模式)"""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        self.dot = QLabel("●")
        self.text = QLabel("未登录")

        layout.addWidget(self.dot)
        layout.addWidget(self.text)

        self.set_status(False)

    def set_status(self, is_logged_in):
        if is_logged_in:
            # 登录状态：深绿色背景+亮绿文字
            bg = "rgba(25, 135, 84, 0.2)"
            fg = "#75b798"
            txt = "已登录"
        else:
            # 未登录：深红色背景+亮红文字
            bg = "rgba(220, 53, 69, 0.2)"
            fg = "#ea868f"
            txt = "未登录"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {bg}; 
                border-radius: 6px;
            }}
            QLabel {{
                color: {fg};
                font-weight: bold;
                border: none;
                background: transparent;
            }}
        """)
        self.text.setText(txt)


class ModernButton(QPushButton):
    """美化后的按钮"""

    def __init__(self, text, color="#0d6efd", hover_color="#0b5ed7"):
        super().__init__(text)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(32)
        # 字体颜色强制为白色
        self.default_style = f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 15px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {color};
                padding-top: 2px;
            }}
        """
        self.setStyleSheet(self.default_style)


class StatusDashboard(QFrame):
    """组合后的仪表盘组件 (深色模式容器)"""
    login_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 改动：背景改为极淡的白色透明，边框微亮
        self.setStyleSheet("""
            StatusDashboard {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
            }
        """)

        # 深色模式下阴影通常很难看，建议去掉或改得很淡
        # 这里我们移除 DropShadow，保持扁平干净

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(15)

        # 1. 状态指示
        self.badge = StatusBadge()

        # 2. 登录按钮
        self.btn_login = ModernButton("点击登录")
        self.btn_login.clicked.connect(self.login_clicked.emit)

        # 分割线 (改为半透明白)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("border: none; background-color: rgba(255, 255, 255, 0.2); width: 1px;")
        line.setFixedHeight(20)

        # 3. 信息芯片
        # icon_color 改为 Material Design 的强调色
        self.chip_profile = InfoChip("👤", "ProfileID", icon_color="#a688fa")  # 淡紫色图标
        self.chip_db = InfoChip("📚", "课程库", icon_color="#4fd1c5")  # 青色图标

        layout.addWidget(self.badge)
        layout.addWidget(self.btn_login)
        layout.addWidget(line)
        layout.addWidget(self.chip_profile)
        layout.addWidget(self.chip_db)
        layout.addStretch()

    def update_state(self, is_logged_in, profile_id="--", db_count=0):
        self.badge.set_status(is_logged_in)
        if is_logged_in:
            self.btn_login.setText("切换账号")
            # 登录后按钮变灰 (适配深色背景的灰色)
            self.btn_login.setStyleSheet(
                self.btn_login.default_style.replace("#0d6efd", "#495057").replace("#0b5ed7", "#343a40"))
            self.chip_profile.set_value(profile_id)
        else:
            self.btn_login.setText("点击登录")
            self.btn_login.setStyleSheet(self.btn_login.default_style)
            self.chip_profile.set_value("--")

        self.chip_db.set_value(f"{db_count} 条")