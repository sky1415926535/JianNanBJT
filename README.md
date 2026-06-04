# 江南百景图 - 白雪镇自动钓鱼脚本

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

基于计算机视觉（OpenCV）的《江南百景图》白雪镇寒雪冰洞自动钓鱼脚本。通过 ADB 控制雷电模拟器，实时分析屏幕画面，自动识别收杆圆盘上的光珠位置，在最佳时机点击「拉一下」按钮，实现全自动钓鱼循环。

> 当前版本：**v3.2** — 支持「再来一次」自动循环 + 60秒无响应超时保护

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
| 🎯 **光珠追踪** | 基于灰度阈值 + 圆形度校验 + 轨道距离约束，精准检测移动光珠 |
| 🔵🟡 **区域识别** | 自动区分蓝色安全区和黄色暴击区，优先点击黄色区域 |
| 🎣 **自动收杆** | 光珠消失后自动判定钓鱼结束，无需模板匹配 |
| 🔄 **再来一次** | 自动点击「收杆/领取」→「再来一次」，实现无限循环 |
| ⚠️ **失误保护** | 累计 3 次失误自动放弃，失败后自动重试 |
| ⏱️ **超时保护** | 60 秒无响应自动退出 + Windows 弹窗通知 + alert.txt 记录 |
| 🎛️ **多模式** | `run` 正常启动 / `retry` 从结果页开始 / `test` 测试 / `calibrate` 校准 |

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

```bash
pip install opencv-python numpy
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
python main.py calibrate

# 4. 测试各模块是否正常
python main.py test

# 5. 开始自动钓鱼
python main.py run
```

如果屏幕已经显示钓鱼结果页（有「再来一次」按钮），使用：

```bash
python main.py retry
```

---

## 使用方法

### 子命令一览

| 命令 | 说明 |
|------|------|
| `python main.py run` | 正常模式：从钓鱼界面开始，自动循环 |
| `python main.py retry` | 续钓模式：从结果页「再来一次」按钮开始 |
| `python main.py test` | 测试模式：检查 ADB 连接、截图、光珠检测 |
| `python main.py calibrate` | 校准模式：交互式校准圆盘和按钮坐标 |
| `python main.py help` | 显示完整帮助信息 |

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
2. 一个**白色光珠**在圆盘上持续沿轨道移动
3. 光珠经过**蓝色区域**时点击「拉一下」→ 水位线正常上涨
4. 光珠经过**黄色区域**时点击「拉一下」→ 水位暴增（大幅上涨）
5. 光珠不在有效区域时点击 = **失误**，累计 3 次失误 → 钓鱼失败
6. 水位线充满整个圆盘 → 钓鱼成功
7. 圆盘消失 → 结果界面（领取奖励 / 再来一次）

---

## 配置说明

配置文件 `config.json` 主要参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `adb.device` | `emulator-5554` | ADB 设备标识 |
| `adb.path` | `D:/leidian/LDPlayer9/adb.exe` | ADB 可执行文件路径 |
| `screen.width/height` | 1920/1080 | 模拟器分辨率 |
| `disc.center_x/y` | 1535/505 | 圆盘中心坐标 |
| `disc.outer_radius` | 170 | 圆盘外圈半径（像素） |
| `disc.bead_radius` | 135 | 光珠轨道半径（像素） |
| `zones.blue_start/end` | 290/230 | 蓝色区域角度范围 |
| `zones.yellow_start/end` | 320/360 | 黄色区域角度范围 |
| `buttons.reel_x/y` | 958/931 | 「拉一下」按钮坐标 |
| `buttons.claim_x/y` | 772/854 | 「收杆/领取」按钮坐标 |
| `buttons.retry_x/y` | 1141/854 | 「再来一次」按钮坐标 |
| `detection.bead_brightness_min` | 200 | 光珠最低灰度阈值 |
| `detection.disc_lost_timeout` | 4.0 | 光珠消失判定超时（秒） |
| `detection.bead_miss_threshold` | 8 | 连续未检测到光珠阈值 |
| `timing.activity_timeout` | 60.0 | 无响应超时（秒） |
| `fishing.prefer_yellow` | true | 是否优先点击黄色区域 |
| `retry.retry_on_failure` | true | 失败后是否自动重试 |

---

## 项目结构

```
JianNanBJT/
├── main.py              # 主脚本（含全部逻辑：视觉检测、状态机、ADB 控制）
├── config.json           # 校准后的配置文件
├── requirements.txt      # Python 依赖列表
├── fishing_log.txt       # 运行日志（自动生成，已 gitignore）
├── alert.txt             # 超时通知文件（自动生成，已 gitignore）
├── templates/            # 弹窗模板图片目录（可选，增强弹窗检测）
├── screenshots/          # 运行时截图缓存（自动生成，已 gitignore）
├── .gitignore            # Git 忽略规则
├── LICENSE               # MIT 许可证
└── README.md             # 本文件
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
python main.py calibrate
```

### Q: 「拉一下」按钮点不中？
按钮坐标因分辨率不同而变化，脚本支持 HSV 红色检测自动定位。如果自动检测不准，手动修改 `config.json` 中 `buttons.reel_x/y`。

### Q: 脚本一直循环 FISHING↔ROUND_OVER？
这是 v3.0 版本的已知 Bug（已通过 disc 可见性误判触发），v3.1 已修复。请确认运行的是最新版本：
```bash
python main.py help  # 查看版本号，应为 v3.2
```

### Q: 脚本 60 秒后自动退出？
这是超时保护机制，防止无限等待。检查 `fishing_bot/alert.txt` 了解退出原因。可在 `config.json` 中调整 `timing.activity_timeout`。

---

## 更新日志

### v3.2（2026-06-04）
- 新增 `retry` 子命令：从结果页「再来一次」按钮开始执行
- 新增 60 秒无响应超时退出 + Windows 弹窗通知 + alert.txt 记录
- 基于 `last_click_time` + `last_bead_time` 双时间戳判定超时

### v3.1（2026-06-04）
- 修复 ROUND_OVER 死循环 Bug（FISHING↔ROUND_OVER 无限切换）
- 新增连续未检测到光珠计数器（`bead_miss_threshold`）
- 消失超时从 2.5s 延长到 4.0s
- ROUND_OVER 改用光珠检测替代 disc 可见性检测

### v3.0（2026-06-04）
- 收杆检测：追踪光珠消失时间判定钓鱼结束（不再依赖模板匹配）
- 再来一次：钓鱼结束后自动点击「收杆/领取」→「再来一次」循环
- 截图稳定性增强：唯一文件名避免写入冲突
- 失败重试机制：支持配置重试开关和最大次数

### v2.x 及更早
- 基础钓鱼循环
- 光珠灰度检测
- 按钮自动定位（HSV 红色检测）
- 蓝/黄区域角度校准

---

## 许可证

本项目基于 MIT 许可证开源，详见 [LICENSE](LICENSE) 文件。
