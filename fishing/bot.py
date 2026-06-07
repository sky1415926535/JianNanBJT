"""
钓鱼自动化状态机（v3.2，从 main.py 提取）

FishingBot 是整个钓鱼流程的核心控制器，采用有限状态机（FSM）架构。

状态说明：
  IDLE
      空闲态，等待玩家进入钓鱼界面。
      进入条件：脚本启动 / 一轮结束后等待下一轮。
      退出条件：检测到光珠 → 切 FISHING。

  FISHING
      钓鱼进行态，核心循环。
      行为：持续截图 → 光珠检测 → 区域判断 → 点击「拉一下」。
      退出条件：
          (a) 光珠连续消失超过 disc_lost_timeout 秒
               且连续未检测到次数 >= bead_miss_threshold
               → 切 ROUND_OVER
          (b) 检测到弹窗（success/failure）→ 切 IDLE（经由 _handle_popup）

  ROUND_OVER
      一轮结束态，处理钓鱼结果。
      行为：点击「收杆/领取」→ 点击「再来一次」→ 等待新轮开始。
      退出条件：
          (a) 检测到光珠重新出现 → 切 FISHING（新一轮）
          (b) 多次尝试仍无光珠 → 重试或停止（取决于 retry_on_failure）

  STOP
      终止态，状态机退出。
      进入条件：达到 max_rounds / 重试次数耗尽 / 超时。

状态转换图：
  [IDLE] --检测到光珠--> [FISHING] --光珠消失超时--> [ROUND_OVER]
     ^                                        |
     |                                        v
     +-------- [FISHING] <--disc 重新出现--- [ROUND_OVER]
"""
import time
import random
import logging
from datetime import datetime

from common import ADB, Vision, SCRIPT_DIR, load_config

log = logging.getLogger("Fishing.Bot")


class FishingBot:
    """
    钓鱼流程的状态机控制器。

    使用示例：
      >>> cfg = load_config()
      >>> bot = FishingBot(cfg)
      >>> bot.start_from_retry()   # 从结果页开始
      >>> bot.run()                 # 正常循环（从 IDLE 开始）

    属性说明：
      - state: 当前状态（STATE_IDLED / STATE_FISHING / ...）
      - round_count: 已完成钓鱼轮次
      - retry_count: 连续失败重试次数
      - last_bead_time: 最后一次检测到光珠的时间（戳）
         用于判定光珠是否消失超时
      - last_click_time: 最后一次点击「拉一下」的时间戳
         用于超时保护（activity_timeout）
      - bead_miss_count: 连续未检测到光珠的帧数计数器
         达到 bead_miss_threshold 后触发 ROUND_OVER
      - click_count_this_round: 当前轮已点击次数（用于日志）
    """

    # ---- 状态常量 ----
    STATE_IDLE = "idle"
    STATE_FISHING = "fishing"
    STATE_ROUND_OVER = "round_over"
    STATE_STOP = "stop"

    def __init__(self, cfg):
        """
        用配置字典初始化状态机。

        参数：
          cfg: dict，从 config.json 加载的配置（由 load_config() 返回）

        副作用：
          - 创建 Vision 实例（self.vision）
          - 初始化所有状态追踪变量
        """
        self.cfg = cfg
        self.state = self.STATE_IDLE
        self.round_count = 0
        self.retry_count = 0
        self.last_bead_angle = None
        self.last_click_time = time.time()
        self.last_bead_time = None
        self.fishing_start_time = None
        self.vision = Vision(cfg)
        self.miss_count = 0
        self.click_count_this_round = 0
        self.bead_miss_count = 0
        self.last_activity_time = time.time()
        self.activity_timeout = cfg["timing"].get("activity_timeout", 60.0)

    # ==============================================================
    # 主循环（由 run() 驱动）
    # ==============================================================
    def run(self):
        """
        状态机主循环，持续运行直到 state == STATE_STOP 或 Ctrl+C。

        行为：
          每个循环迭代：
            1. 调用 _check_timeout() 检查是否无响应超时
            2. 根据 self.state 分发到对应处理方法

        退出条件：
          - state 变为 STATE_STOP
          - 用户按下 Ctrl+C（KeyboardInterrupt）

        副作用：
          - 修改 self.state
          - 调用 ADB.tap()（点击屏幕）
          - 写日志文件（fishing_log.txt）
        """
        log.info("=" * 50)
        log.info("钓鱼脚本启动 v4.0 (模块化重构)")
        log.info(f"优先黄区: {self.cfg['fishing']['prefer_yellow']}")
        log.info(f"蓝区点击率: {self.cfg['fishing']['click_blue_probability']}")
        log.info(f"光珠消失超时: {self.cfg['detection']['disc_lost_timeout']}秒")
        retry_cfg = self.cfg.get("retry", {})
        log.info(f"失败重试: {retry_cfg.get('retry_on_failure', True)}")
        log.info(f"无响应超时: {self.activity_timeout:.0f}秒")
        log.info("=" * 50)

        self.state = self.STATE_IDLE
        try:
            while self.state != self.STATE_STOP:
                self._check_timeout()
                if self.state == self.STATE_STOP:
                    break
                if self.state == self.STATE_IDLE:
                    self._on_idle()
                elif self.state == self.STATE_FISHING:
                    self._on_fishing()
                elif self.state == self.STATE_ROUND_OVER:
                    self._on_round_over()
                else:
                    log.error(f"未知状态: {self.state}")
                    break
        except KeyboardInterrupt:
            log.info("用户中断（Ctrl+C），脚本停止")
        finally:
            log.info(f"脚本结束，共完成 {self.round_count} 轮钓鱼")

    # ==============================================================
    # IDLE 状态处理器
    # ==============================================================
    def _on_idle(self):
        """
        IDLE 状态：等待玩家进入钓鱼界面。

        行为：
          - 每帧截图
          - 检测弹窗（success/failure/start_fishing 等）
          - 检测光珠（find_bead_on_disc）
          - 光珠出现 → 切 FISHING
          - 光珠未出现 → 等待 3 秒后重试

        超时：
          此状态不会触发 ROUND_OVER，但会触发 activity_timeout。
        """
        log.info("[状态] 空闲中，等待进入钓鱼界面...")
        while self.state == self.STATE_IDLE:
            img = ADB.screenshot()
            if img is None:
                time.sleep(1)
                continue
            popup = self.vision.detect_popup(img)
            if popup:
                self._handle_popup(popup)
                time.sleep(self.cfg["timing"]["popup_wait"])
                continue
            angle, found = self.vision.find_bead_on_disc(img)
            if found:
                log.info("[状态] [OK] 检测到光珠，已进入钓鱼界面")
                self.state = self.STATE_FISHING
                self.fishing_start_time = time.time()
                self.last_bead_time = time.time()
                self.click_count_this_round = 0
                self.miss_count = 0
                self.bead_miss_count = 0
                return
            else:
                log.info("  未在钓鱼界面，请手动进入 白雪镇 -> 寒雪冰洞 -> 钓鱼界面")
                time.sleep(3)

    # ==============================================================
    # FISHING 状态处理器（核心）
    # ==============================================================
    def _on_fishing(self):
        """
        FISHING 状态：钓鱼核心循环，每帧执行一次。

        执行流程（每帧）：
          1. 截图
          2. 弹窗检测（优先处理）
          3. 光珠检测
              有光珠：
                - 计算角度，判断区域（蓝/黄）
                - 黄区 → 必点
                - 蓝区 → 按 click_blue_probability 概率点击
                - 点击后等待 animation_wait 秒（让动画播放）
              无光珠：
                - bead_miss_count += 1
                - 若连续消失超过 disc_lost_timeout 秒
                  且 miss 次数 >= bead_miss_threshold
                  → 切 ROUND_OVER
          4. 空闲检测（idle_timeout 警告）

        副作用：
          - 调用 ADB.tap() 点击「拉一下」按钮
          - 修改 self.state（可能在内部切 ROUND_OVER）
        """
        img = ADB.screenshot()
        if img is None:
            time.sleep(0.5)
            return
        popup = self.vision.detect_popup(img)
        if popup:
            self._handle_popup(popup)
            return

        angle, found = self.vision.find_bead_on_disc(img)
        now = time.time()

        if found:
            # ---- 光珠可见：判断是否点击 ----
            if self.last_bead_time is None:
                self.last_bead_time = now
            self.last_bead_time = now
            self.bead_miss_count = 0
            zone = self.vision.which_zone(angle)
            should_click = False
            reason = ""
            if zone == "yellow":
                should_click = True
                reason = "黄区-水位暴增"
            elif zone == "blue":
                prob = self.cfg["fishing"]["click_blue_probability"]
                if random.random() < prob:
                    should_click = True
                    reason = "蓝区-正常收杆"
                else:
                    reason = "蓝区-跳过"

            # 点击前检查最小间隔（防止过快点击）
            if should_click and (now - self.last_click_time) >= self.cfg["timing"]["min_click_interval"]:
                jitter = random.uniform(0.05, 0.20)
                time.sleep(jitter)
                reel_x = self.cfg["buttons"]["reel_x"]
                reel_y = self.cfg["buttons"]["reel_y"]
                ADB.tap(reel_x, reel_y)
                self.last_click_time = time.time()
                self.click_count_this_round += 1
                log.info(f"点击 #{self.click_count_this_round} | 区域={zone} | "
                         f"角度={angle:.0f}deg | {reason}")
                time.sleep(self.cfg["timing"]["animation_wait"])
            elif should_click:
                log.debug(f"点击间隔太短，跳过 | 区域={zone}")

            self.last_bead_angle = angle
        else:
            # ---- 光珠不可见：累计 miss，判定是否结束 ----
            if self.last_bead_time is None:
                self.last_bead_time = now
            self.bead_miss_count += 1
            disc_lost_duration = now - self.last_bead_time
            disc_lost_timeout = self.cfg["detection"]["disc_lost_timeout"]
            bead_miss_threshold = self.cfg["detection"].get("bead_miss_threshold", 8)

            # 核心判定：光珠消失超过 N 秒 且 连续 miss 达到阈值
            if disc_lost_duration > disc_lost_timeout and self.bead_miss_count >= bead_miss_threshold:
                log.info("=" * 40)
                log.info(f"* 光珠已消失 {disc_lost_duration:.1f}秒 "
                         f"(连续 {self.bead_miss_count} 次未检测到)，判定本轮钓鱼结束")
                log.info(f"  本轮点击次数: {self.click_count_this_round}")
                log.info("=" * 40)
                self.state = self.STATE_ROUND_OVER
                self.bead_miss_count = 0
                self.last_bead_time = None
                return

            # 每 12 次 miss 输出一次调试日志（避免刷屏）
            elif self.bead_miss_count > 0 and self.bead_miss_count % 12 == 0:
                log.debug(f"未检测到光珠 (连续 {self.bead_miss_count} 次, "
                          f"已消失 {disc_lost_duration:.1f}s / {disc_lost_timeout}s)")

        # 空闲警告：有光珠但长时间未点击
        if (now - self.last_click_time) > self.cfg["timing"]["idle_timeout"]:
            log.warning("空闲超时警告，可能检测失败，继续尝试...")

        time.sleep(self.cfg["timing"]["screenshot_cooldown"])

    # ==============================================================
    # ROUND_OVER 状态处理器
    # ==============================================================
    def _on_round_over(self):
        """
        ROUND_OVER 状态：处理一轮钓鱼结束后的结果页。

        执行流程：
          1. 等待 result_wait 秒（让结果页加载）
          2. 确认光珠已消失（防误判）
               → 若光珠仍在，切回 FISHING
          3. 点击「收杆/领取」按钮
          4. 点击「再来一次」按钮
          5. 等待 restart_wait 秒（让钓鱼界面重新加载）
          6. 轮询检测光珠是否重新出现
               → 出现：切 FISHING（新一轮）
               → 未出现：重试点击「再来一次」
               → 仍失败：根据 retry_on_failure 决定是否停止

        重试逻辑：
          - retry_on_failure = True 且 max_retries > 0：
              retry_count 累加，达到 max_retries 后停止
          - max_retries = 0：无限重试
        """
        log.info("[状态] 处理钓鱼结果...")
        result_wait = self.cfg["detection"]["result_wait"]
        restart_wait = self.cfg["detection"]["restart_wait"]

        log.info(f"  (1/5) 等待结果界面加载 ({result_wait}秒)...")
        time.sleep(result_wait)

        # ---- 步骤 2：确认光珠已消失 ----
        log.info("  (2/5) 确认 bead 已消失...")
        img = ADB.screenshot()
        if img is not None:
            angle, found = self.vision.find_bead_on_disc(img)
            if found:
                log.warning(f"  WARNING bead 仍可检测到 (角度={angle:.0f}deg)，切回 FISHING")
                self.state = self.STATE_FISHING
                self.last_bead_time = time.time()
                self.bead_miss_count = 0
                return
        log.info("  [OK] bead 已消失，确认进入结果界面")

        # ---- 步骤 3：点击「收杆/领取」----
        claim_x = self.cfg["buttons"]["claim_x"]
        claim_y = self.cfg["buttons"]["claim_y"]
        log.info(f"  (3/5) 点击「收杆/领取」({claim_x}, {claim_y})...")
        ADB.tap(claim_x, claim_y)
        time.sleep(1.0)

        # ---- 步骤 4：点击「再来一次」----
        retry_x = self.cfg["buttons"]["retry_x"]
        retry_y = self.cfg["buttons"]["retry_y"]
        log.info(f"  (4/5) 点击「再来一次」({retry_x}, {retry_y})...")
        time.sleep(0.5)
        ADB.tap(retry_x, retry_y)

        # ---- 步骤 5：等待钓鱼界面重新加载 ----
        log.info(f"  (5/5) 等待钓鱼界面重新加载 ({restart_wait}秒)...")
        time.sleep(restart_wait)

        # ---- 步骤 6：轮询检测光珠是否重新出现 ----
        max_disc_check_retries = 10
        disc_reappeared = False
        for check_i in range(max_disc_check_retries):
            img = ADB.screenshot()
            if img is not None:
                angle, found = self.vision.find_bead_on_disc(img)
                if found:
                    disc_reappeared = True
                    log.info(f"  [OK] disc 已重新出现（第 {check_i + 1} 次检测到光珠，角度={angle:.0f}deg）")
                    break
            time.sleep(0.5)

        if disc_reappeared:
            self._start_new_round()
        else:
            log.warning("  WARNING 未能检测到 disc 重新出现，尝试再次点击「再来一次」...")
            ADB.tap(retry_x, retry_y)
            time.sleep(restart_wait)

            # 第二次尝试
            for check_i in range(max_disc_check_retries):
                img = ADB.screenshot()
                if img is not None:
                    angle, found = self.vision.find_bead_on_disc(img)
                    if found:
                        disc_reappeared = True
                        log.info(f"  [OK] 第二次尝试成功！disc 已重新出现")
                        break
                time.sleep(0.5)

            if disc_reappeared:
                self._start_new_round()
            else:
                log.error("  [FAIL] 无法回到钓鱼界面！可能需要手动干预")
                self._handle_round_over_failure()

    def _start_new_round(self):
        """
        成功进入新一轮：重置状态，切 FISHING。
        （从 _on_round_over 中提取的公共逻辑）
        """
        self.round_count += 1
        log.info(f"  [OK] 第 {self.round_count} 轮完成！开始新一轮钓鱼")
        self.state = self.STATE_FISHING
        self.last_bead_time = time.time()
        self.last_click_time = time.time()
        self.click_count_this_round = 0
        self.miss_count = 0
        self.bead_miss_count = 0

        # 检查是否达到最大轮次
        if self.round_count >= self.cfg["fishing"]["max_rounds"]:
            log.info(f"已达到最大钓鱼轮次 ({self.cfg['fishing']['max_rounds']})，停止")
            self.state = self.STATE_STOP

    def _handle_round_over_failure(self):
        """
        一轮结束后无法回到钓鱼界面的失败处理。

        行为：
          - retry_count += 1
          - 若 retry_on_failure = True：
              - max_retries > 0 且 retry_count > max_retries → 停止
              - 否则 → 切 IDLE（等待玩家手动回到钓鱼界面）
          - 若 retry_on_failure = False → 停止
        """
        self.retry_count += 1
        retry_cfg = self.cfg.get("retry", {})
        if retry_cfg.get("retry_on_failure", True):
            max_retries = retry_cfg.get("max_retries", 10)
            if max_retries > 0 and self.retry_count > max_retries:
                log.error(f"已达到最大重试次数 ({max_retries})，停止")
                self.state = self.STATE_STOP
            else:
                log.info(f"重试 ({self.retry_count}/{max_retries})...")
                self.state = self.STATE_IDLE
        else:
            self.state = self.STATE_STOP

    # ==============================================================
    # 弹窗处理
    # ==============================================================
    def _handle_popup(self, popup):
        """
        处理 detect_popup() 检测到的弹窗。

        弹窗类型及行为：
          - "success": 钓鱼成功
              → round_count += 1，切 IDLE
          - "failure": 钓鱼失败
              → retry_count += 1，根据 retry_on_failure 决定是否重试
          - "start_fishing": 「开始钓鱼」按钮
              → 点击，切 FISHING
          - 其他（"close"/"confirm" 等）:
              → 点击关闭，切 IDLE

        参数：
          popup: dict，格式为 {"type": str, "x": int, "y": int}
        """
        ptype = popup["type"]
        x, y = popup["x"], popup["y"]
        if ptype == "success":
            log.info("  [OK] 模板匹配：钓鱼成功！")
            self.round_count += 1
            self.retry_count = 0
            ADB.tap(x, y)
            time.sleep(self.cfg["timing"]["popup_wait"])
            if self.round_count >= self.cfg["fishing"]["max_rounds"]:
                log.info("已达到最大轮次，停止")
                self.state = self.STATE_STOP
            else:
                self.state = self.STATE_IDLE
        elif ptype == "failure":
            log.warning("  [FAIL] 模板匹配：钓鱼失败")
            self.retry_count += 1
            ADB.tap(x, y)
            time.sleep(self.cfg["timing"]["popup_wait"])
            retry_cfg = self.cfg.get("retry", {})
            if retry_cfg.get("retry_on_failure", True):
                max_retries = retry_cfg.get("max_retries", 10)
                if max_retries > 0 and self.retry_count > max_retries:
                    log.error(f"达到最大重试次数 ({max_retries})，停止")
                    self.state = self.STATE_STOP
                else:
                    log.info(f"失败后重试 ({self.retry_count}/{max_retries})...")
                    time.sleep(retry_cfg.get("retry_delay", 2.0))
                    self.state = self.STATE_IDLE
            else:
                self.state = self.STATE_STOP
        elif ptype == "start_fishing":
            log.info("  点击「开始钓鱼」...")
            ADB.tap(x, y)
            time.sleep(2.0)
            self.state = self.STATE_FISHING
            self.last_bead_time = time.time()
        else:
            log.info(f"  关闭弹窗: {ptype}")
            ADB.tap(x, y)
            time.sleep(self.cfg["timing"]["popup_wait"])
            self.state = self.STATE_IDLE

    # ==============================================================
    # 超时检查 + Windows 通知
    # ==============================================================
    def _check_timeout(self):
        """
        检查是否无响应超时，触发则停止状态机并发送通知。

        判定条件（双 timestamps 均超时）：
          - (now - last_click_time) > activity_timeout
          - (last_bead_time is None OR (now - last_bead_time) > activity_timeout)

        触发后行为：
          1. 写 alert.txt（包含时间戳）
          2. 弹 Windows MessageBox（ctypes.windll）
          3. 切 STATE_STOP
        """
        now = time.time()
        no_click = (now - self.last_click_time) > self.activity_timeout
        no_bead = self.last_bead_time is None or (now - self.last_bead_time) > self.activity_timeout
        if no_click and no_bead:
            msg = f"[超时退出] 已 {self.activity_timeout:.0f} 秒无任何点击或检测到光珠，脚本自动退出！"
            log.error("=" * 50)
            log.error(msg)
            log.error(f"  最后点击: {time.strftime('%H:%M:%S', time.localtime(self.last_click_time))}")
            if self.last_bead_time:
                log.error(f"  最后光珠: {time.strftime('%H:%M:%S', time.localtime(self.last_bead_time))}")
            log.error("=" * 50)
            self._alert(msg)
            self.state = self.STATE_STOP

    def _alert(self, msg):
        """
        发送超时通知：写 alert.txt + Windows 弹窗。

        通知方式：
          1. 写 alert.txt（项目根目录）
              内容：时间戳 + 消息内容
              用途：用户可检查脚本退出原因
          2. Windows MessageBox（ctypes.windll.user32.MessageBoxW）
              标题："钓鱼脚本通知"
              按钮：确定 + 取消（0x40|0x1）
              用途：即时提醒用户

        参数：
          msg: str，通知消息内容
        """
        alert_file = SCRIPT_DIR / "alert.txt"
        try:
            with open(alert_file, "w", encoding="utf-8") as f:
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"消息: {msg}\n")
            log.info(f"  已写通知文件: {alert_file}")
        except Exception as e:
            log.warning(f"  写 alert 文件失败: {e}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"钓鱼脚本超时退出！\n\n{msg}\n\n请检查游戏状态。",
                "钓鱼脚本通知",
                0x40 | 0x1,
            )
        except Exception:
            pass

    # ==============================================================
    # 「再来一次」模式入口
    # ==============================================================
    def start_from_retry(self):
        """
        「再来一次」模式：直接从结果页「再来一次」按钮开始。

        使用场景：
          脚本异常退出后，游戏停留在结果页（有「再来一次」按钮），
          用此模式可跳过重新进入钓鱼界面的步骤。

        执行流程：
          1. 点击「收杆/领取」
          2. 点击「再来一次」
          3. 等待钓鱼界面加载（最多 restart_wait * 3 秒）
          4. 检测到光珠 → 切 FISHING
          5. 未检测到 → 报错停止 + 通知

        副作用：
          - 若成功，切为 FISHING 状态
          - 若失败，切为 STOP 状态 + 弹窗通知
        """
        log.info("=" * 50)
        log.info("[模式] 「再来一次」模式：直接从结果页开始")
        log.info("=" * 50)

        retry_x = self.cfg["buttons"]["retry_x"]
        retry_y = self.cfg["buttons"]["retry_y"]
        claim_x = self.cfg["buttons"]["claim_x"]
        claim_y = self.cfg["buttons"]["claim_y"]
        restart_wait = self.cfg["detection"]["restart_wait"]

        log.info(f"  (1/4) 尝试点击「收杆/领取」({claim_x}, {claim_y})...")
        ADB.tap(claim_x, claim_y)
        time.sleep(1.0)

        log.info(f"  (2/4) 点击「再来一次」({retry_x}, {retry_y})...")
        ADB.tap(retry_x, retry_y)
        time.sleep(restart_wait)

        log.info(f"  (3/4) 等待钓鱼界面加载（最多 {restart_wait * 3:.0f} 秒）...")
        max_wait = int(restart_wait * 3)
        for i in range(max_wait * 2):
            img = ADB.screenshot()
            if img is not None:
                angle, found = self.vision.find_bead_on_disc(img)
                if found:
                    log.info(f"  [OK] 检测到光珠（角度={angle:.0f}deg），进入钓鱼")
                    self.state = self.STATE_FISHING
                    self.fishing_start_time = time.time()
                    self.last_bead_time = time.time()
                    self.last_click_time = time.time()
                    self.click_count_this_round = 0
                    self.miss_count = 0
                    self.bead_miss_count = 0
                    return
            time.sleep(0.5)
            if (i + 1) % 4 == 0:
                log.debug(f"  仍在等待钓鱼界面加载... ({(i + 1) // 2}s)")

        log.error("  [FAIL] 点击「再来一次」后未检测到钓鱼界面！")
        self._alert("「再来一次」模式失败：未检测到钓鱼界面，请检查按钮坐标！")
        self.state = self.STATE_STOP
