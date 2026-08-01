#!/usr/bin/env python3
"""
screenshot_demo.py — 截取 WorkBuddy 签到面板，作为 README 演示图。

仅通过 CDP 读取，不重启任何进程。截图区域裁剪到签到面板本身，
不含用户名/聊天内容等隐私信息。

依赖：playwright（使用已运行的 WorkBuddy 自带 Chromium；无需额外下载浏览器）
运行：<python with playwright> screenshot_demo.py
"""
import os
import time
from playwright.sync_api import sync_playwright

PORT = "http://127.0.0.1:9222"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "demo-checkin.png")

# 穿透 Shadow DOM，返回第一个匹配选择器的元素的视口矩形
RECT_JS = """
(sel) => {
  function deep(el) {
    if (!el) return null;
    try { if (el.matches && el.matches(sel)) return el; } catch (e) {}
    try { if (el.shadowRoot) { const r = deep(el.shadowRoot); if (r) return r; } } catch (e) {}
    if (el.querySelectorAll) {
      for (const c of el.querySelectorAll('*')) {
        const r = deep(c);
        if (r) return r;
      }
    }
    return null;
  }
  const r = deep(document);
  if (!r) return null;
  const b = r.getBoundingClientRect();
  return { x: b.x, y: b.y, width: b.width, height: b.height };
}
"""


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(PORT)
        page = b.contexts[0].pages[0]
        page.bring_to_front()

        # 打开签到面板：点头像菜单 -> 点加油站
        page.mouse.click(94, 694)
        time.sleep(1.2)
        page.mouse.click(172, 262)
        time.sleep(2.0)

        # 读取面板矩形（裁剪到面板，避免泄露隐私）
        rect = page.evaluate(RECT_JS, ".daily-checkin")
        if not rect:
            rect = {"x": 8, "y": 380, "width": 260, "height": 360}
        rect = {k: max(0, int(v)) for k, v in rect.items()}

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        page.screenshot(path=OUT, clip=rect)
        print("SAVED", OUT, rect)

        # 关闭面板，恢复现场
        try:
            page.mouse.click(230, 454)
        except Exception:
            pass
        time.sleep(0.5)
        print("DONE")


if __name__ == "__main__":
    main()
