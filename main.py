# --- START OF FILE main.py ---
import sys
import datetime
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLineEdit, QTableWidget,
                               QTableWidgetItem, QPlainTextEdit, QLabel, QHeaderView,
                               QMessageBox, QSpinBox, QProgressBar, QStyle)
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtCore import Slot, QTimer, Qt
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from qt_material import apply_stylesheet
from eams_core import EamsSession
from workers import MonitorWorker
from ui_extras import TopBarExtras
from ui_components import StatusDashboard
from auth.browser_login import BrowserLoginController
from auth.webengine_login import LoginWindow

# 表格列定义常量
COL_NO = 0
COL_NAME = 1
COL_CODE = 2
COL_ID = 3
COL_COUNT = 4
COL_STATUS = 5
COL_OP = 6


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SUFE 选课助手 GUI V2")
        self.resize(1150, 750)
        self.eams = EamsSession()
        self.worker = None
        self.target_list = []
        self.is_logged_in = False
        self.login_window = None
        self.browser_login_controller = None
        self.init_ui()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout(self.central_widget)

        # 1. 顶部状态栏
        top_layout = QHBoxLayout()

        # 使用新的仪表盘组件
        self.dashboard = StatusDashboard()
        self.dashboard.login_clicked.connect(self.open_login_window)  # 连接信号

        # 右上角的扩展按钮 (上财门户等)
        self.top_extras = TopBarExtras(self)

        top_layout.addWidget(self.dashboard, 1)  # 仪表盘占据主要空间
        top_layout.addSpacing(10)
        top_layout.addWidget(self.top_extras)  # 右侧工具栏

        main_layout.addLayout(top_layout)

        # 2. 中间操作区
        mid_layout = QHBoxLayout()

        # 左侧：输入+表格
        left_layout = QVBoxLayout()
        input_layout = QHBoxLayout()
        self.input_no = QLineEdit()
        self.input_no.setPlaceholderText("输入课程序号 (如: 001)")
        self.input_no.returnPressed.connect(self.add_course)
        self.btn_add = QPushButton("添加监控")
        self.btn_add.clicked.connect(self.add_course)
        input_layout.addWidget(self.input_no)
        input_layout.addWidget(self.btn_add)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["课程序号", "课程名称", "课程代码", "ID", "人数", "状态", "操作"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers) #禁止编辑
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_OP, QHeaderView.Fixed)
        self.table.setColumnWidth(COL_OP, 80)

        left_layout.addLayout(input_layout)
        left_layout.addWidget(self.table)

        # 右侧：日志+控制
        right_layout = QVBoxLayout()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("刷新(秒):"))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 60)
        self.spin_min.setValue(2)
        ctrl_layout.addWidget(self.spin_min)
        ctrl_layout.addWidget(QLabel("-"))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(1, 60)
        self.spin_max.setValue(4)
        ctrl_layout.addWidget(self.spin_max)
        ctrl_layout.addSpacing(10)

        self.btn_start = QPushButton("开始抢课")
        self.btn_start.clicked.connect(self.toggle_monitoring)
        self.btn_start.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        ctrl_layout.addWidget(self.btn_start, 1)

        # 运行日志标题行 + 清空按钮（×）
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("运行日志:"))

        btn_clear_log = QPushButton()
        btn_clear_log.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        btn_clear_log.setFixedSize(26, 26)
        btn_clear_log.setCursor(Qt.PointingHandCursor)
        btn_clear_log.setToolTip("清空日志")
        btn_clear_log.clicked.connect(self.log_view.clear)

        # 让按钮靠右
        log_header.addStretch(1)
        log_header.addWidget(btn_clear_log)

        right_layout.addLayout(log_header)
        right_layout.addWidget(self.log_view)

        right_layout.addLayout(ctrl_layout)

        mid_layout.addLayout(left_layout, 2)
        mid_layout.addLayout(right_layout, 1)
        main_layout.addLayout(mid_layout)

        self.update_ui_state()

    def update_ui_state(self):
        # 获取当前课程数量
        count = len(self.eams.course_db)
        pid = self.eams.profile_id if self.eams.profile_id else "--"

        # 一键更新仪表盘所有状态
        self.dashboard.update_state(self.is_logged_in, pid, count)

        # 更新其他按钮状态 (保持不变)
        if self.is_logged_in:
            self.btn_add.setEnabled(True)
            self.btn_start.setEnabled(True)
            self.input_no.setEnabled(True)
        else:
            self.btn_add.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.input_no.setEnabled(False)

    def open_login_window(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "警告", "请先停止抢课任务！")
            return

        backend = os.getenv("SUFE_LOGIN_BACKEND", "browser").strip().lower()
        if backend == "webengine":
            if self.login_window:
                self.login_window.close()
            self.login_window = LoginWindow(self.eams)
            self.login_window.login_success_signal.connect(self.on_login_success)
            self.login_window.show()
            self.login_window.activateWindow()
            self.log("[WARN] 已启用 WebEngine 登录回退模式。")
            return

        if self.browser_login_controller:
            self.browser_login_controller.stop_server()

        self.browser_login_controller = BrowserLoginController(self.eams, self)
        self.browser_login_controller.status_signal.connect(self.log)
        self.browser_login_controller.login_success_signal.connect(self.on_login_success)
        self.browser_login_controller.login_failed_signal.connect(
            lambda msg: self.log(f"[ERROR] {msg}")
        )
        self.browser_login_controller.start_login()

    def on_login_success(self):
        self.is_logged_in = True
        # 不需要手动 setText 了，统一调用 update_ui_state
        self.update_ui_state()
        self.log("[SUCCESS] 登录成功！正在后台刷新课程数据...")
        QTimer.singleShot(500, self.refresh_course_db)

    def refresh_course_db(self):
        if self.eams.step2_fetch_course_data():
            count = len(self.eams.course_db)
            # 更新仪表盘上的数量显示
            self.dashboard.chip_db.set_value(f"{count} 条")
            self.log(f"[INFO] 课程数据加载完毕，共 {count} 门课。")
        else:
            self.log("[ERROR] 课程数据获取失败。")

    def log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {msg}\n"

        # 按前缀判断等级（你项目里 worker/main 都用这些前缀）
        # workers.py 会 emit: [INFO]/[WARN]/[ERROR]/[SUCCESS]/[CRASH] ... :contentReference[oaicite:2]{index=2}
        level = None
        if msg.startswith("[SUCCESS]"):
            level = "SUCCESS"
        elif msg.startswith("[INFO]"):
            level = "INFO"
        elif msg.startswith("[WARN]"):
            level = "WARN"
        elif msg.startswith("[ERROR]"):
            level = "ERROR"
        elif msg.startswith("[CRASH]"):
            level = "CRASH"

        color_map = {
            "SUCCESS": QColor("#2ecc71"),  # 绿
            "INFO": QColor("#bdc3c7"),  # 浅灰（深色主题更清晰）
            "WARN": QColor("#f1c40f"),  # 黄
            "ERROR": QColor("#e74c3c"),  # 红
            "CRASH": QColor("#ff3b30"),  # 亮红
            None: QColor("#ffffff"),  # 未匹配到前缀：默认白
        }

        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(color_map.get(level, QColor("#ffffff")))

        cursor.insertText(line, fmt)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def add_course(self):
        no = self.input_no.text().strip()
        if not no: return
        info = self.eams.get_lesson_info_by_no(no)
        if not info:
            QMessageBox.warning(self, "错误", f"找不到课程序号为 {no} 的课程！")
            return

        if any(str(t['id']) == str(info['id']) for t in self.target_list):
            self.log(f"[WARN] 课程 {no} 已在列表中")
            return

        course_data = info.copy()
        course_data['success'] = False
        self.target_list.append(course_data)

        def _center_item(text: str):
            it = QTableWidgetItem(text)
            it.setTextAlignment(Qt.AlignCenter)
            return it

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, COL_NO, _center_item(str(info["no"])))
        self.table.setItem(row, COL_NAME, _center_item(info["name"]))
        self.table.setItem(row, COL_CODE, _center_item(info["code"]))
        self.table.setItem(row, COL_ID, _center_item(str(info["id"])))
        self.table.setItem(row, COL_COUNT, _center_item("waiting..."))
        self.table.setItem(row, COL_STATUS, _center_item("待机"))

        btn_del = QPushButton("删除")
        btn_del.setStyleSheet("color: red;")
        btn_del.clicked.connect(lambda: self.remove_course(str(info['id'])))
        self.table.setCellWidget(row, COL_OP, btn_del)
        self.input_no.clear()
        self.sync_worker()
        self.log(f"[INFO] 已添加监控: {info['name']}({info['no']})")

    def remove_course(self, lesson_id):
        self.target_list = [t for t in self.target_list if str(t['id']) != lesson_id]
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_ID)
            if item and item.text() == lesson_id:
                self.log(f"[INFO] 课程 {self.table.item(row, COL_NAME).text()}({self.table.item(row, COL_NO).text()}) 已移除")
                self.table.removeRow(row)
                break
        self.sync_worker()

    def sync_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.update_targets([t for t in self.target_list if not t.get('success', False)])

    def toggle_monitoring(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.btn_start.setEnabled(False)
            QTimer.singleShot(1000, lambda: self.btn_start.setEnabled(True))
            self.log("[INFO] 正在停止监控...")
        else:
            if not self.is_logged_in: return
            active_targets = [t for t in self.target_list if not t.get('success', False)]
            if not active_targets:
                QMessageBox.warning(self, "提示", "没有可抢的课程")
                return

            self.worker = MonitorWorker(self.eams, active_targets, self.spin_min.value(), self.spin_max.value())
            self.worker.log_signal.connect(self.log)
            self.worker.stats_signal.connect(self.update_table_stats)
            self.worker.result_signal.connect(self.handle_result)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.start()

            self.btn_start.setText("停止抢课")
            self.btn_start.setStyleSheet("background-color: red; color: white; font-weight: bold;")

    def on_worker_finished(self):
        self.btn_start.setText("开始抢课")
        self.btn_start.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        self.btn_start.setEnabled(True)
        self.log("[INFO] 监控已停止")

    @Slot(dict)
    def update_table_stats(self, counts):
        for row in range(self.table.rowCount()):
            lid = self.table.item(row, COL_ID).text()
            if lid in counts:
                data = counts[lid]
                sc, lc = data.get('sc', 0), data.get('lc', 0)
                new_text = f"{sc} / {lc}"

                item_c = self.table.item(row, COL_COUNT)
                if item_c.text() != new_text: item_c.setText(new_text)

                status_item = self.table.item(row, COL_STATUS)
                if status_item.text() not in ["抢课成功", "重复选课", "时间冲突", "选课未开放", "停止尝试"]:
                    is_full = sc >= lc
                    new_s = "满员" if is_full else "有空位"
                    if status_item.text() != new_s:
                        status_item.setText(new_s)


    @Slot(str, str)
    def handle_result(self, lid, msg):
        # 这里的 msg 已经是包含前缀的完整日志文本
        for t in self.target_list:
            if str(t['id']) == lid: t['success'] = True; break

        for row in range(self.table.rowCount()):
            if self.table.item(row, COL_ID).text() == lid:
                st = self.table.item(row, COL_STATUS)
                font = st.font()
                font.setBold(True)
                st.setFont(font)

                if "抢课成功" in msg:
                    st.setText("抢课成功")
                elif "重复" in msg:
                    st.setText("重复选课")
                elif "冲突" in msg:
                    st.setText("时间冲突")
                elif "未开放" in msg:
                    st.setText("选课未开放")
                else:
                    st.setText("停止尝试")
                st.setToolTip(msg)
                break


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    apply_stylesheet(app, theme='dark_blue.xml')
    window.show()
    sys.exit(app.exec())