# WorkBuddy 每日积分自动领取（Daily Check-in Auto-Claim）

> 让本机 WorkBuddy 客户端每天自动完成「签到领积分」，无需人工点击。
> WorkBuddy Daily Check-in Auto-Claim — automate the daily points check-in of the WorkBuddy desktop client via CDP.

---

## 它是怎么工作的

WorkBuddy 桌面客户端基于 Electron（Chromium）。启动时若带上 `--remote-debugging-port=9222`，就可以通过 **Chrome DevTools Protocol (CDP)** 连接它内部的渲染进程。

本工具用 [Playwright](https://playwright.dev) 的 `connect_over_cdp` 连上本机 `127.0.0.1:9222`，然后用 `page.mouse.click(x, y)` **直接注入鼠标渲染事件**，按固定路径完成签到：

```
点头像菜单（左下角 user-menu）
   └─> 在弹出的 Shadow DOM 菜单里点「Buddy 加油站 / 签到领积分」
         └─> 左侧签到面板出现
               └─> 点「立即领取」→ 文本变为「今日已领」→ 关面板
```

### 几个关键设计

- **坐标点击而非系统级自动化**：`page.mouse.click` 注入的是渲染层事件，**锁屏/未解锁时也能触发 UI 响应**（相比 pyautogui 这类系统级点击更稳）。
- **入口动态探测**：头像菜单项在 `user-menu-popover` 的 Shadow DOM 内，脚本会遍历子树、按「面积最小」原则精确锁定「Buddy 加油站」菜单项，避免误点父容器或「积分余额」等其它项。
- **模态对话框防御**：若 WorkBuddy 弹出「确认登出」之类的模态框（长期带调试端口运行可能触发会话过期），脚本会优先点「取消」保留登录态，再继续领取。
- **领取失败重试**：点击「立即领取」后若无变化，会再次重试点击（最多 5 次），应对动画/时序导致的偶发无效点击。
- **防重复**：`last_claim_date.txt` 记录已领日期，同一天重复运行会跳过。

---

## 环境要求

| 项目 | 说明 |
| --- | --- |
| 系统 | Windows（脚本中的 `run.bat` / `register_task.ps1` 为 Windows 专用） |
| Python | 3.10+ |
| 客户端 | 已安装 WorkBuddy 桌面客户端 |
| 依赖 | `playwright`（仅需 Python 库；`connect_over_cdp` 连接的是已运行的 WorkBuddy 自带 Chromium，无需额外下载浏览器） |

---

## 快速开始

### 1. 安装依赖

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 以调试端口启动 WorkBuddy

WorkBuddy 必须带着 `--remote-debugging-port=9222` 运行，脚本才能连接。

直接双击 **`start_workbuddy_debug.bat`**（它会先结束旧进程，再以调试端口重启 WorkBuddy）。
> 注意：由于 Electron 单实例锁，请先**完全退出** WorkBuddy（托盘→退出）再双击该 bat。

启动后确认端口已监听：

```bash
netstat -ano | findstr 9222
```

### 3. 手动跑一次验证

```bash
run.bat
# 或
venv\Scripts\python claim_cdp.py
```

正常输出会显示：打开菜单 → 定位加油站 → 面板出现 → `点击 立即领取` → `✅ 领取成功确认`。

### 4.（可选）注册每日计划任务

用**管理员 PowerShell** 运行 `register_task.ps1`，即可创建每天 `07:10` 自动执行的计划任务（调用 `run.bat`）。

```powershell
# 以管理员身份打开 PowerShell，cd 到本目录后：
.\register_task.ps1
```

> 提示：若电脑处于睡眠状态，计划任务默认不会唤醒（`WakeToRun` 未启用）。如需睡眠也能触发，请在脚本里启用唤醒或保持电脑不睡眠。

---

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `claim_cdp.py` | **主脚本**：连接 CDP、定位入口、领取积分、写记录 |
| `run.bat` | 激活 venv 并运行主脚本（供计划任务调用） |
| `start_workbuddy_debug.bat` | 以 `--remote-debugging-port=9222` 重启 WorkBuddy |
| `register_task.ps1` | 注册 Windows 计划任务（每日 07:10） |
| `calibration.json` | 坐标参考快照（特定分辨率/版本下的面板坐标，**脚本运行并不读取此文件**，仅供理解与重新校准时参考） |
| `requirements.txt` | Python 依赖（仅需 `playwright`） |

---

## 校准坐标（换分辨率 / WorkBuddy 升级后）

脚本已尽量动态探测入口，但若 WorkBuddy 版本更新导致布局变化，可自行校准：

1. 以调试端口启动 WorkBuddy，端口 9222 监听。
2. 用 Playwright 连接 `127.0.0.1:9222`，依次读取：
   - 头像菜单 `.user-menu` / `.user-menu-trigger` 的中心坐标
   - 弹出菜单中 `.fuel-menu-entry`（文本含「加油站 / 签到领积分」）的坐标
   - 签到面板 `.daily-checkin` 内 `.fuel-actions > .fuel-btn`（领取按钮）与 `.fuel-close`（关闭）的坐标
3. 将实际坐标回填到 `claim_cdp.py` 里对应的兜底值 / `calibration.json` 参考。

---

## 注意事项与免责声明

- ⚠️ **合规使用**：本项目仅供个人学习与自动化便利，**请遵守 WorkBuddy 用户协议**，不要用于异常刷分或破坏公平性的行为。
- ⚠️ **内部 UI 依赖**：脚本依赖 WorkBuddy 客户端内部 UI 结构（Shadow DOM、类名、坐标）。WorkBuddy 版本升级可能改动这些结构，导致选择器失效，需要重新校准（见上）。
- ⚠️ **调试端口副作用**：长期让 WorkBuddy 带 `--remote-debugging-port` 运行，可能触发会话过期弹窗，并在默认浏览器（Edge）打开调试页面残留标签页。建议**仅在需要领取时临时开启调试端口**，领取完成后正常使用（不带端口）启动 WorkBuddy。
- 🔒 本项目不含任何账号密码 / Token，所有操作都在你本机已登录的 WorkBuddy 上进行。

---

## 许可证

[MIT](./LICENSE) © 2026 theon
