# --- START OF FILE workers.py ---
from PySide6.QtCore import QThread, Signal
import time
import random
import traceback


class MonitorWorker(QThread):
    log_signal = Signal(str)
    stats_signal = Signal(dict)
    result_signal = Signal(str, str)

    def __init__(self, eams_session, targets, min_interval=2, max_interval=5):
        super().__init__()
        self.eams = eams_session
        self.targets = targets
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.running = True
        self.success_ids = set()

    def smart_sleep(self, seconds):
        if seconds <= 0: return
        steps = int(seconds * 10)
        for _ in range(steps):
            if not self.running: return
            time.sleep(0.1)

    def _analyze_result(self, success, msg):
        """解析提交结果"""
        is_duplicate = any(k in msg for k in ["已经", "重复", "已选"])
        is_conflict = "冲突" in msg
        is_closed = "不开放" in msg or "登入失败" in msg

        is_done = success or is_duplicate or is_conflict or is_closed

        # 定义日志级别和前缀
        level = "[ERROR]"  # 默认
        status_text = msg

        if success:
            level = "[SUCCESS]"
            status_text = "抢课成功"
        elif is_duplicate:
            level = "[WARN]"
            status_text = f"重复选课 ({msg})"
        elif is_conflict:
            level = "[WARN]"
            status_text = f"时间冲突 ({msg})"
        elif is_closed:
            level = "[WARN]"
            status_text = f"选课未开放 ({msg})"
        else:
            # 普通失败
            level = "[ERROR]"
            status_text = f"提交失败 ({msg})"

        return is_done, level, status_text

    def run(self):
        try:
            self.log_signal.emit("[INFO] 正在初始化上下文...")
            if not self.eams.refresh_context():
                self.log_signal.emit("[ERROR] 上下文初始化失败，请重新登录")
                self.running = False
                return

            self.log_signal.emit("[INFO] 监控已启动，等待数据...")
            self.smart_sleep(1)

            # --- 新增：连续失败计数器 ---
            empty_data_count = 0
            cnt = 0
            while self.running:
                active_targets = [t for t in self.targets if str(t['id']) not in self.success_ids]
                if not active_targets:
                    self.log_signal.emit("[INFO] ✅ 所有待抢课程均已完成！自动停止监控。")
                    self.running = False
                    break

                counts = self.eams.step3_query_counts()

                # --- 修改：数据为空时的处理逻辑 ---
                if not counts:
                    empty_data_count += 1
                    # 只有当连续失败次数较多时才打印日志，避免网络波动时刷屏
                    if empty_data_count == 1:
                        self.log_signal.emit("[WARN] 未获取到课程数据，正在重试...")

                    # 核心修复：如果连续 3 次拿不到数据，强制刷新上下文
                    if empty_data_count >= 3:
                        self.log_signal.emit("[WARN] 数据获取连续失败，尝试自动修复上下文...")
                        if self.eams.refresh_context():
                            self.log_signal.emit("[INFO] 上下文修复成功，继续监控")
                            empty_data_count = 0  # 重置计数器
                        else:
                            self.log_signal.emit("[ERROR] 上下文修复失败，请检查网络")
                        # 修复后多睡一会儿
                        self.smart_sleep(2)
                    else:
                        self.smart_sleep(1)
                    continue

                # 如果成功获取数据，重置计数器
                empty_data_count = 0
                # ------------------------------

                self.stats_signal.emit(counts)
                cnt += 1
                self.log_signal.emit(f"[INFO] 数据获取中，已请求 {cnt} 次")
                for target in active_targets:
                    if not self.running: break

                    lid = str(target['id'])
                    if lid not in counts: continue

                    info = counts[lid]
                    sc, lc = info.get('sc', 0), info.get('lc', 0)
                    if sc < lc:
                        self.log_signal.emit(f"[INFO] 发现空位: {target['name']} ({sc}/{lc})，提交中...")
                        success, raw_msg = self.eams.step4_submit(lid)

                        is_done, level, log_msg = self._analyze_result(success, raw_msg)

                        if is_done:
                            self.success_ids.add(lid)
                            self.result_signal.emit(lid, log_msg)
                            self.log_signal.emit(f"{level} {target['name']}: {log_msg}")
                        else:
                            self.log_signal.emit(f"{level} {target['name']}: {log_msg}")

                        self.smart_sleep(0.5)
                        if not self.eams.refresh_context():
                            self.log_signal.emit("[WARN] 页面上下文重置失败")
                        self.smart_sleep(1)

                self.smart_sleep(random.uniform(self.min_interval, self.max_interval))

        except Exception as e:
            self.log_signal.emit(f"[CRASH] 监控线程发生未知错误: {str(e)}")
            print(traceback.format_exc())
            self.running = False

    def update_targets(self, new_targets):
        self.targets = new_targets

    def stop(self):
        self.running = False
