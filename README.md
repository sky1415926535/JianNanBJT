# 江南百景图 - 白雪镇自动钓鱼脚本

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

基于计算机视觉（OpenCV）的《江南百景图》白雪镇寒雪冰洞自动钓鱼脚本。通过 ADB 控制雷电模拟器，实时分析屏幕画面，自动识别收杆圆盘上的光珠位置，在最佳时机点击「拉一下」按钮，实现全自动钓鱼循环。

> 当前版本：**v4.2** — 所有府大地图坐标OCR自动标定 + 坐标模式支持滚动偏移

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
- [钓鱼机制说明](#钓鱼机制说明)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [常见问题](#常见问题)
- [更新日志](#更新日志)

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 🎯 **光珠追踪** | 基于灰度阈值 + 环形掩码 + 圆形度校验 + 轨道距离约束，精准检测移动光珠 |
| 🔵🟡 **区域识别** | 自动区分蓝色安全区和黄色暴击区，优先点击黄色区域 |
| 🎣 **自动收杆** | 光珠消失后自动判定钓鱼结束，无需模板匹配 |
| 🔄 **再来一次** | 自动点击「收杆/领取」→「再来一次」，实现无限循环 |
| ⚠️ **失误保护** | 连续多次未检测到光珠自动进入结果处理，失败后自动重试 |
| ⏱️ **超时保护** | 60 秒无响应自动退出 + Windows 弹窗通知 + alert.txt 记录 |
| 🗺️ **州府切换** | 大地图州府切换：**OCR文字识别** / 坐标直点(支持滚动偏移) / 模板匹配 三种模式，自动降级 |
| 🏷️ **两步进入** | v4.2 新增：州府印→弹窗→大地图，自动检测弹窗并点击"大地图"按钮 |
| 🎯 **界面判定** | 左下角红色比例检测：自动区分大地图(<8%)和城镇视图(>20%) |
| 🆕 **OCR 引擎** | v4.1 新增：RapidOCR / PaddleOCR / EasyOCR / MSER 四引擎自动检测 |
| 🗺️ **坐标滚动** | v4.2 新增：坐标模式支持 `scroll_x`/`scroll_y` 滚动偏移，适应超屏幕尺寸大地图 |
| 📦 **模块化** | v4.0 重构：公共模块 + 功能模块分离，`launcher.py` 统一入口 |

---

## 环境要求

| 组件 | 版本/说明 |
|------|----------|
| 操作系统 | Windows 10/11 |
| 模拟器 | 雷电模拟器 9（1920×1080 分辨率） |
| Python | 3.9+ |
| ADB | 雷电模拟器自带（`D:\leidian\LDPlayer9\adb.exe`） |
| 游戏 | 江南百景图 — 白雪镇 → 寒雪冰洞 → 钓鱼界面 |

### Python 依赖

**基础依赖（必需）：**
```bash
pip install opencv-python numpy
```

**OCR 依赖（推荐，用于大地图州府文字识别）：**
```bash
# 推荐：RapidOCR（轻量快速，中文精度高）
pip install rapidocr

# 备选：PaddleOCR / EasyOCR
pip install paddlepaddle paddleocr
# 或
pip install easyocr

# 若不安装 OCR 库，将降级为 MSER 纯区域检测（仅定位不识别文字）
```

或使用项目根目录的 `requirements.txt`：

```bash
pip install -r requirements.txt
```

---

## 快速开始

```bash
# 1. 确认模拟器已连接
D:\leidian\LDPlayer9\adb.exe devices
# 应输出: emulator-5554  device

# 2. 进入游戏钓鱼界面（白雪镇 → 寒雪冰洞）

# 3. 首次运行：校准屏幕坐标
python launcher.py calibrate

# 4. 测试各模块是否正常
python launcher.py test

# 5. 开始自动钓鱼
python launcher.py fish
```

如果屏幕已经显示钓鱼结果页（有「再来一次」按钮），使用：

```bash
python launcher.py fish --retry
```

---

## 使用方法

### 子命令一览

| 命令 | 说明 |
|------|------|
| `python launcher.py fish` | 正常模式：从钓鱼界面开始，自动循环 |
| `python launcher.py fish --retry` | 续钓模式：从结果页「再来一次」按钮开始 |
| `python launcher.py switch-prefecture` | 切换州府（**OCR 文字识别优先**，自动降级坐标/模板） |
| `python launcher.py switch-prefecture --target 苏州府` | 指定目标州府名称 |
| `python launcher.py diagnose-map` | **截图+OCR 诊断**：输出检测到的文字区域和识别结果 |
| `python launcher.py switch-town` | 切换行囊城镇（骨架代码，待截图确认后实现） |
| `python launcher.py switch-town --target 应天府` | 指定目标城镇名称 |
| `python launcher.py test` | 测试模式：检查 ADB 连接、截图、光珠检测 |
| `python launcher.py calibrate` | 校准模式：交互式校准圆盘和按钮坐标 |
| `python launcher.py menu` | 交互式菜单选择（默认） |

### 运行流程

```
进入钓鱼界面 → 检测光珠 → 分析光珠所在区域
    ├─ 蓝色区域 → 点击「拉一下」（水位正常上涨）
    ├─ 黄色区域 → 点击「拉一下」（水位暴增）
    └─ 无效区域 → 等待（不点击，避免失误）

光珠消失 → 判定钓鱼结束 → 点击「收杆/领取」
    → 点击「再来一次」→ 等待新钓鱼界面加载
    → 检测到光珠 → 新一轮循环
```

---

## 钓鱼机制说明

《江南百景图》白雪镇钓鱼的核心机制：

1. 进入钓鱼界面后，屏幕右侧出现**收杆圆盘**
2. 一个**光珠**在圆盘上持续沿轨道顺时针移动
3. 光珠经过**蓝色区域**时点击「拉一下」→ 水位线正常上涨
4. 光珠经过**黄色区域**时点击「拉一下」→ 水位暴增（大幅上涨）
5. 光珠不在有效区域时点击 = **失误**，累计多次失误 → 钓鱼失败
6. 水位线充满整个圆盘 → 钓鱼成功
7. 圆盘消失 → 结果界面（领取奖励 / 再来一次）

### 光珠检测原理（v3.1+）

光珠并非纯白色（BGR ≈ 174,242,250，偏暖色调），因此不使用 RGB 等值检测，而是采用：

1. **灰度阈值**：光珠亮度远高于其他 UI 元素（灰度 > 180），用阈值二值化提取候选区域
2. **环形掩码**：仅保留光珠轨道环带内的像素，过滤轨道外噪声
3. **圆形度校验**：光珠是圆形，用 `4π·面积/周长²` 过滤不规则 UI 碎片
4. **轨道距离校验**：光珠必须距离圆盘中心约 `bead_radius` 像素（允许 ±tolerance 误差）
5. **综合打分**：结合轨道贴合度和圆形度选出最佳候选

---

## 配置说明

配置文件 `config.json` 主要参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `adb.device` | `emulator-5554` | ADB 设备标识（IP:端口 或 emulator-XXXX） |
| `adb.path` | `""` | ADB 可执行文件完整路径（空则自动查找） |
| `screen.width/height` | `1920/1080` | 模拟器分辨率，首次运行 test 模式会自动更新 |
| `disc.center_x/y` | `1535/505` | 收杆圆盘中心坐标（需校准） |
| `disc.outer_radius` | `170` | 圆盘外圈半径（像素） |
| `disc.bead_radius` | `135` | 光珠轨道半径（像素，距圆盘中心距离） |
| `zones.yellow_start/end` | `300/360` | 黄色暴击区角度范围（度，顺时针） |
| `zones.blue_start/end` | `0/300` | 蓝色安全区角度范围（度，顺时针） |
| `buttons.reel_x/y` | `1540/825` | 「拉一下」按钮坐标 |
| `buttons.claim_x/y` | `960/750` | 「收杆/领取」按钮坐标（结果页） |
| `buttons.retry_x/y` | `960/850` | 「再来一次」按钮坐标（结果页） |
| `detection.bead_brightness_min` | `180` | 光珠最低灰度阈值（0-255） |
| `detection.bead_min_area` | `15` | 光珠最小轮廓面积（过滤噪声） |
| `detection.bead_max_area` | `300` | 光珠最大轮廓面积（过滤大块 UI） |
| `detection.bead_circularity_min` | `0.55` | 光珠最小圆形度（0-1，1=完美圆） |
| `detection.bead_track_tolerance` | `20` | 轨道距离容忍度（像素） |
| `detection.disc_lost_timeout` | `4.0` | 光珠连续消失判定超时（秒） |
| `detection.bead_miss_threshold` | `8` | 连续未检测到光珠次数阈值（触发进入 ROUND_OVER） |
| `detection.result_wait` | `2.0` | 点击「收杆」后等待结果页加载（秒） |
| `detection.restart_wait` | `2.5` | 点击「再来一次」后等待界面重启（秒） |
| `timing.screenshot_cooldown` | `0.06` | 截图间隔冷却时间（秒，控制 CPU 占用） |
| `timing.min_click_interval` | `0.20` | 最小点击间隔（秒，防止过快点击） |
| `timing.animation_wait` | `0.3` | 点击后等待动画播放（秒） |
| `timing.popup_wait` | `0.8` | 检测到弹窗后等待（秒） |
| `timing.idle_timeout` | `15.0` | 钓鱼状态下无点击警告超时（秒） |
| `timing.activity_timeout` | `60.0` | 全局无活动超时（秒），触发自动退出 + 通知 |
| `fishing.max_rounds` | `999` | 最大钓鱼轮次（达到后自动停止，0=无限） |
| `fishing.prefer_yellow` | `true` | 是否优先点击黄色区域 |
| `fishing.click_blue_probability` | `1.0` | 蓝区点击概率（0.0-1.0，1.0=始终点击） |
| `retry.retry_on_failure` | `true` | 失败后是否自动重试 |
| `retry.max_retries` | `0` | 最大重试次数（0=无限重试） |
| `retry.retry_delay` | `2.0` | 重试前等待时间（秒） |
| `prefecture.target` | `白雪镇` | 默认目标州府名称 |
| `prefecture.mode` | `ocr` | 定位模式：`ocr`(文字识别 / 推荐) / `coordinate`(坐标直点) / `template`(模板匹配) |
| `prefecture.mode_order` | `["ocr","coordinate","template"]` | 多模式降级顺序 |
| `prefecture.big_map_enter_btn` | `{x:108, y:908}` | 左下角州府印(红色印章) — 点击后弹出功能菜单 |
| `prefecture.big_map_menu_btn` | `{x:218, y:389}` | 弹窗中"大地图"按钮 — 5个红色按钮最左边(v4.2新增) |
| `prefecture.popup_wait` | `0.5` | 点击州府印后等待弹窗出现的时间(秒, v4.2新增) |
| `prefecture.loading_wait` | `3.0` | 大地图/城镇加载等待时间(秒) |
| `prefecture.big_map_indicator` | `{x:960, y:30}` | 大地图界面特征检测点 |
| `prefecture.default_confirm_btn` | `{x:960, y:600}` | 通用确认进入按钮坐标 |

每个州府的独立配置在 `prefecture.prefectures.<name>` 下：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `map_coord` | `{x:0, y:0, scroll_x:0, scroll_y:0}` | 大地图上该州府的像素坐标 + 滚动偏移量（0=未配置，需用 `diagnose-map` 获取） |
| `confirm_btn` | `null` | 该州府专属确认按钮坐标（null 则回退到 `default_confirm_btn`） |
| `search_templates` | `[]` | 模板匹配用图片文件名（位于 `templates/` 目录） |
| `travel_bag.target` | `白雪镇` | 默认目标城镇名称（switch-town 模式） |

---

## 项目结构

```
JianNanBJT/
├── launcher.py            # ★ 统一入口（v4.0 新增），argparse 子命令分发
├── main.py                # 旧版单体脚本（v3.2，已保留作为参考）
├── config.json            # 全局配置文件（git 跟踪，但敏感/临时数据不在此）
├── requirements.txt       # Python 依赖列表
├── fishing_log.txt        # 运行日志（已 .gitignore）
├── alert.txt              # 超时通知内容（已 .gitignore）
│
├── common/                # ★ 公共模块（v4.0 新增）
│   ├── __init__.py
│   ├── paths.py           # 路径常量（SCRIPT_DIR / TEMPLATE_DIR / SCREENSHOT_DIR 等）
│   ├── adb.py             # ADB 封装（设备检测/连接/截图/点击/滑动/返回键）
│   ├── vision.py          # 视觉识别（光珠检测/区域判定/模板匹配/红色按钮检测）
│   ├── ocr.py             # ★ OCR 文字识别（v4.1 新增，PaddleOCR/EasyOCR/MSER）
│   └── config.py          # 配置加载/保存 + DEFAULT_CONFIG 定义
│
├── fishing/               # ★ 钓鱼模块（v4.0 从 main.py 提取）
│   ├── __init__.py
│   └── bot.py             # FishingBot 状态机（IDLE → FISHING → ROUND_OVER → STOP）
│
├── map_switch/            # ★ 大地图州府切换（v4.2 坐标滚动偏移支持）
│   ├── __init__.py
│   └── prefecture.py      # PrefectureSwitcher（OCR/坐标(支持滚动)/模板 三模式降级）
│                           #   + _scroll_to() 按偏移量自动滚动大地图
├── map_explorer.py         # 大地图网格扫描 + MSER区域检测 + 交互式标定（v4.2 新增）
├── rapid_ocr_calibrate.py  # RapidOCR 自动标定所有府坐标（v4.2 新增）
├── four_dir_scan.py        # 四方向扫描大地图（解决5x5网格遗漏问题，v4.2 新增）
│                           #   + _ensure_on_big_map() 两步进入
│                           #   + _exit_big_map() 返回城镇
│                           #   + _is_popup_open() 弹窗检测
│                           #   + _is_on_big_map() 四层降级检测
│
├── travel_bag/            # ★ 行囊城镇切换（v4.0 新增，骨架代码）
│   ├── __init__.py
│   └── town_switch.py     # TownSwitcher 类（待截图确认 UI 后实现）
│
├── templates/             # 弹窗模板图片（success/failure/close/confirm 等）
├── screenshots/           # 调试截图保存目录（已 .gitignore）
├── tests/                  # ★ 测试与探索脚本（v4.1-v4.2 大地图入口探索历程）
│   │
│   ├── ── UI 分析阶段 ──
│   ├── test_full_analysis.py   # 全面分析游戏屏幕布局，理解 UI 结构
│   └── test_analyze_ui.py      # 不按返回键，直接分析当前界面组成
│   │
│   ├── ── 按钮探索阶段 ──
│   ├── test_find_bigmap.py     # 全面检测左侧 UI 区域所有按钮
│   ├── test_bottom_buttons.py  # 逐个尝试底部圆形按钮，找大地图入口
│   ├── test_find_map_btn.py    # 在游戏内容区域重新定位入口按钮
│   ├── test_try_game_coords.py # 估算游戏坐标→屏幕坐标映射，测试左下角
│   └── test_grid_explore.py    # 网格化全屏点击，系统探索所有可交互元素
│   │
│   ├── ── 州府印定位阶段 ──
│   ├── test_find_seal.py        # 颜色分割定位"州府印"红色圆形印章 ★发现
│   ├── test_best_candidates.py # 测试最有希望的候选坐标组合
│   └── test_final_analysis.py  # 精确分析 UI 布局，定标州府印坐标
│   │
│   └── ── 验证阶段 ──
│       ├── test_verify_bigmap.py  # 多维度分析验证是否真的进入大地图
│       └── test_enter_bigmap.py # 点击州府印→进入大地图 ★最终验证
│
├── .gitignore
├── LICENSE
└── README.md
```

> **提示**：`tests/` 中的 12 个脚本记录了从全屏盲搜到精确定标 (108,908) 的完整探索过程，按执行时间先后分为 UI分析 → 按钮探索 → 州府印定位 → 验证 四个阶段。

### 模块依赖关系

```
launcher.py
  ├── common/adb.py        # ADB 操作
  ├── common/config.py     # 配置读写
  ├── common/paths.py      # 路径常量
  ├── common/vision.py     # 视觉识别
  ├── fishing/bot.py       # 钓鱼状态机
  ├── map_switch/prefecture.py   # 州府切换
  └── travel_bag/town_switch.py  # 城镇切换
```

---

## 常见问题

### Q: 脚本报 "ADB 连接失败" 怎么办？
确认雷电模拟器已开启 ADB 调试（设置 → 其他设置 → ADB 调试），然后检查：
```bash
D:\leidian\LDPlayer9\adb.exe devices
```

### Q: 光珠检测不准确？
运行校准模式重新定位圆盘中心、轨道半径和亮度阈值：
```bash
python launcher.py calibrate
```
如果圆盘位置正确但光珠仍检测不到，尝试降低 `config.json` 中 `detection.bead_brightness_min` 的值（如从 180 降至 150）。

### Q: 「拉一下」按钮点不中？
按钮坐标因分辨率不同而变化。校准后若仍不准确，手动修改 `config.json` 中 `buttons.reel_x/y`，或用微信/QQ 截图工具获取准确坐标。

### Q: 脚本一直循环 FISHING↔ROUND_OVER？
这是 v3.0 版本的已知 Bug（已通过 disc 可见性误判触发），v3.1 已修复。请确认运行的是 v4.0 版本：
```bash
python launcher.py --help  # 应显示 v4.0
```

### Q: 脚本 60 秒后自动退出？
这是超时保护机制，防止无限等待。检查项目目录下的 `alert.txt` 了解退出原因。可在 `config.json` 中调整 `timing.activity_timeout`（秒）。

### Q: v4.2 的州府切换功能怎么用？

州府切换已完整实现 **OCR 文字识别**、**坐标模式(支持滚动偏移)** 和 **两步大地图进入**，所有府坐标已预配置。

**自动模式（推荐）：**
```bash
# 1. 安装 RapidOCR（推荐，轻量快速）
pip install rapidocr

# 或 PaddleOCR（中文精度最高）
pip install paddlepaddle paddleocr

# 2. 在任意城镇界面运行（自动两步进入大地图）
python launcher.py switch-prefecture --target 苏州府
```

**大地图进入机制（v4.2）：**
```
城镇视图 → 点击左下角州府印(108,908) → 弹出5按钮菜单 →
  → 自动检测弹窗 → 点击"大地图"(218,389) → 大地图加载
```
州府印弹出菜单包含：`大地图 | 改布局 | 地基 | 截图 | 羽翼仙`

**大地图检测策略（4层降级）：**
| 优先级 | 策略 | 判定条件 |
|--------|------|----------|
| 0 | 左下角红色比例 | <8%→大地图(州府印消失), >20%→城镇视图(州府印可见) |
| 1 | 模板匹配 big_map_navbar.png | 置信度阈值 |
| 2 | 行囊按钮 travel_bag_btn.png | 存在=大地图 |
| 3 | 文字区域密度 | ≥2个=大地图 |

**坐标模式（备选）：**
```bash
# 1. 先用诊断模式截取大地图
python launcher.py diagnose-map
# 2. 查看日志中输出的文字区域坐标
# 3. 将坐标填入 config.json
# 4. 设置 mode_order 为 ["coordinate", "ocr", "template"]
```

**模式配置：**
在 `config.json` → `prefecture` 中：
- `mode`: 首选模式（`"ocr"` / `"coordinate"` / `"template"`）
- `mode_order`: 模式降级顺序，如 `["ocr", "coordinate", "template"]`

---

## 更新日志

### v4.2（2026-06-13）
- ★ **所有府大地图坐标OCR自动标定完成**（7/7，排除白雪镇）：应天府/苏州府/杭州府/松江府/徽州府/扬州府/绍兴府
- ★ **坐标模式支持滚动偏移**：`map_coord` 新增 `scroll_x`/`scroll_y`，`_try_coordinate_mode` 先滚动再点击
- ★ 新增 `_scroll_to()` 方法：按偏移量自动计算滑动步数（支持超屏幕尺寸大地图）
- ★ **RapidOCR 替代 PaddleOCR**：解决 PaddlePaddle 3.x 与 PaddleOCR 3.x 不兼容问题
- ★ 新增 `map_explorer.py`：3x3/5x5 网格扫描 + MSER区域检测 + 交互式标定
- ★ 新增 `rapid_ocr_calibrate.py`：RapidOCR 自动识别府名并标定坐标
- ★ 新增 `four_dir_scan.py`：四方向扫描（从默认视图出发，解决5x5从左上角扫描遗漏问题）
- ★ **两步大地图进入**：发现州府印点击后弹出菜单，实现两步流程（州府印→弹窗→大地图）
- ★ **界面判定增强**：`_is_on_big_map()` 新增策略0—左下角红色比例检测
- ★ 新增 `popup_wait` 配置项(0.5s)

### v4.1（2026-06-07）
- ★ **OCR 文字识别完整实现**：大地图州府切换支持真正的文字识别
- ★ 新增 `common/ocr.py`：PaddleOCR / EasyOCR / MSER 三引擎自动检测切换
- ★ 多模式自动降级：OCR → 坐标 → 模板，按 `mode_order` 顺序尝试
- ★ 增强 `vision.py` 文字区域检测：双相 MSER + 颜色过滤 + 宽高比筛选
- ★ `diagnose-map` 增强：同时输出 MSER 区域 + OCR 识别结果
- ★ `config.json` 补全所有已知州府（应天府~绍兴府+白雪镇）及其别名
- ★ 新增 `mode_order` 配置，支持多模式降级链

### v4.0（2026-06-07）
- ★ 模块化重构：拆分为 `common/`、`fishing/`、`map_switch/`、`travel_bag/` 四个模块包
- ★ 新增 `launcher.py` 统一入口，支持 `argparse` 子命令分发
- ★ 新增 `common/` 公共模块：`adb.py`（ADB 封装）、`vision.py`（视觉识别）、`config.py`（配置管理）、`paths.py`（路径常量）
- ★ **大地图州府切换完整实现**（`map_switch/prefecture.py`）：坐标/模板/MSER 三种定位模式 + 诊断工具 + 确认弹窗处理
- ★ 新增行囊城镇切换骨架（`travel_bag/town_switch.py`）
- ★ `vision.py` 新增 `find_red_buttons()`（HSV 红色按钮检测）和 `find_text_regions()`（MSER 文字区域检测）
- ★ 新增 `diagnose-map` 子命令（州府坐标诊断工具）
- 补全所有模块的详细代码注释（光珠 5 层过滤算法、FSM 状态转换、ADB 连接逻辑等）
- 更新 README.md：修正配置默认值、新增光珠检测原理章节、模块依赖关系图

### v3.2（2026-06-04）
- 新增 `retry` 子命令：从结果页「再来一次」按钮开始执行
- 新增 60 秒无响应超时退出 + Windows 弹窗通知（`ctypes.windll.user32.MessageBoxW`）+ `alert.txt` 记录
- 基于 `last_click_time` + `last_bead_time` 双时间戳判定超时
- 新增 `_on_retry()` 方法：`retry` 模式专用入口

### v3.1（2026-06-04）
- 修复 ROUND_OVER 死循环 Bug（FISHING↔ROUND_OVER 无限切换）
- 根因：`is_disc_visible()` 用亮度方差检测，光珠消失后始终返回 True
- 修复：改为连续未检测到光珠计数器（`bead_miss_threshold`）+ 更长超时（4.0s）
- ROUND_OVER 状态改用光珠检测（而非 disc 可见性）判定是否回到钓鱼界面
- 新增 `bead_circularity_min` 和 `bead_track_tolerance` 配置项

### v3.0（2026-06-04）
- 收杆检测：追踪光珠消失时间判定钓鱼结束（不再依赖模板匹配）
- 再来一次：钓鱼结束后自动点击「收杆/领取」→「再来一次」循环
- 截图稳定性增强：唯一文件名（时间戳+随机数）避免多进程写入冲突
- 失败重试机制：支持配置 `retry_on_failure` 开关和 `max_retries` 次数

### v2.x 及更早
- 基础钓鱼循环
- 光珠灰度检测
- 按钮自动定位（HSV 红色检测）
- 蓝/黄区域角度校准

---

## 许可证

本项目基于 MIT 许可证开源，详见 [LICENSE](LICENSE) 文件。
