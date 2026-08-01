# -*- coding: utf-8 -*-
"""
WorkBuddy 每日积分领取 - CDP 版（当前生产脚本，由 run.bat/计划任务调用）
针对 WorkBuddy 5.3.5：头像菜单里仍保留「Buddy 加油站 · 签到领积分」，
但该入口异步加载，且 DOM 中可能被包含在更大的父容器里，
因此本脚本在 .user-menu-popover 子树中按面积最小原则精确选择菜单项，
避免误点父容器或误点「积分余额」等其他项。
- 不杀 WorkBuddy 进程，仅通过 CDP 连接注入鼠标事件。
- 打开签到面板后读取按钮文本，「立即领取」则点击，「今日已领」则跳过。
- 领取后多轮轮询确认状态，失败则截图诊断。
"""
import os, sys, time, socket, json, logging
from datetime import datetime
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_PORT = 9222
LOG_FILE = os.path.join(SCRIPT_DIR, "claim_cdp_log.txt")
LAST_CLAIM = os.path.join(SCRIPT_DIR, "last_claim_date.txt")
SHOT = os.path.join(SCRIPT_DIR, "claim_cdp_result.png")

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
log = logging.getLogger("claim_cdp")


def lp(*a):
    s = " ".join(str(x) for x in a)
    print(s); log.info(s)


def port_open():
    try:
        with socket.create_connection(("127.0.0.1", DEBUG_PORT), timeout=2): return True
    except Exception: return False


def find_main_page(browser):
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if pg.url and pg.url != "about:blank":
                if "index.html" in pg.url or "app.asar" in pg.url: return pg
    try: return browser.contexts[0].pages[0]
    except Exception: return None


def menu_opened(page):
    try: return page.evaluate("() => !!document.querySelector('.user-menu-popover')")
    except Exception: return False


def avatar_center(page):
    try:
        return page.evaluate("""() => {
            const el=document.querySelector('.user-menu')||document.querySelector('.user-menu-trigger');
            if(!el) return null; const r=el.getBoundingClientRect();
            if(r.width<5||r.height<5) return null;
            return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)];
        }""")
    except Exception: return None


def find_station_entry(page):
    """在菜单弹层中找「Buddy 加油站 / 签到领积分」菜单项，返回中心坐标+文本。
    按面积最小原则选择，避免误点父容器。"""
    try:
        return page.evaluate("""() => {
            const pop=document.querySelector('.user-menu-popover');
            if(!pop) return {err:'no popover'};
            const roots=[pop];
            const collect=(root)=>{ for(const el of root.querySelectorAll('*')){ if(el.shadowRoot&&!roots.includes(el.shadowRoot)) roots.push(el.shadowRoot);} };
            for(let i=0;i<roots.length;i++) collect(roots[i]);
            let cands=[];
            for(const root of roots){
                for(const el of root.querySelectorAll('.fuel-menu-entry, *')){
                    const t=(el.innerText||el.textContent||'').trim();
                    if(!t) continue;
                    const r=el.getBoundingClientRect();
                    if(r.width<20||r.height<10) continue;
                    if(/加油站|签到领积分/.test(t)){
                        cands.push({t, r, area:r.width*r.height});
                    }
                }
            }
            if(!cands.length) return {none:true};
            cands.sort((a,b)=>a.area-b.area);
            const c=cands[0];
            return {coord:[Math.round(c.r.x+c.r.width/2),Math.round(c.r.y+c.r.height/2)], text:c.t.slice(0,60), area:c.area, all:cands.slice(0,5).map(x=>[x.t.slice(0,20),x.area])};
        }""")
    except Exception as e:
        return {"err": str(e)}


def bubble_state(page):
    try:
        return page.evaluate("""() => {
            const b=document.querySelector('.daily-checkin');
            if(!b) return {exists:false};
            const slot=b.querySelector('.wb-slot--avatar-top');
            if(!slot||!slot.shadowRoot) return {exists:true, hasShadow:false};
            const root=slot.shadowRoot;
            const ex=root.querySelector('.fuel-card.fuel-expanded');
            const co=root.querySelector('.fuel-card.fuel-compact');
            const er=ex?ex.getBoundingClientRect():{width:0,height:0};
            const cr=co?co.getBoundingClientRect():{width:0,height:0};
            const btn=root.querySelector('.fuel-actions > .fuel-btn');
            const close=root.querySelector('.fuel-close');
            const br=btn?btn.getBoundingClientRect():{width:0,height:0};
            const clr=close?close.getBoundingClientRect():{width:0,height:0};
            return {exists:true, isExpanded:er.width>100&&er.height>100, isCompact:cr.width>100&&cr.height>100,
                btnText: btn?(btn.innerText||'').trim():'', btnCoord: btn?[Math.round(br.x+br.width/2),Math.round(br.y+br.height/2)]:null,
                closeCoord: close?[Math.round(clr.x+clr.width/2),Math.round(clr.y+clr.height/2)]:null};
        }""")
    except Exception as e:
        return {"err": str(e)}


def click(page, coord, label):
    try:
        x, y = int(coord[0]), int(coord[1])
        page.mouse.click(x, y)
        lp(f"点击 {label} @ ({x},{y})"); return True
    except Exception as e:
        lp(f"点击 {label} 失败: {e}"); return False


def dismiss_modals(page):
    """检测并关闭 WorkBuddy 内模态对话框。遇到『确认登出』类优先点『取消』，避免脚本误登出。"""
    try:
        res = page.evaluate("""() => {
            const sels=['.confirm-dialog','.modal','.dialog','.modal-mask','[role=dialog]'];
            const d=document.querySelector(sels.join(','));
            if(!d) return {none:true};
            const txt=(d.innerText||'');
            const btns=[...d.querySelectorAll('button,.btn,.modal-btn')];
            const find=(kw)=>btns.find(b=>((b.innerText||'')).includes(kw));
            const cancel=find('取消')||find('暂不')||find('关闭')||find('否');
            return {has:true, isLogout:/登出|退出登录|确认要登出/.test(txt), txt:txt.slice(0,80), cancelText:cancel?(cancel.innerText||'').trim():null};
        }""")
        if isinstance(res, dict) and res.get('has'):
            lp(f"检测到对话框: isLogout={res.get('isLogout')} text={res.get('txt')!r}")
            if res.get('isLogout'):
                if res.get('cancelText'):
                    page.evaluate("""() => {
                        const d=document.querySelector('.confirm-dialog,.modal,.dialog,.modal-mask,[role=dialog]');
                        const btns=[...d.querySelectorAll('button,.btn,.modal-btn')];
                        const c=btns.find(b=>((b.innerText||'').includes('取消')||(b.innerText||'').includes('暂不')||(b.innerText||'').includes('关闭')));
                        if(c) c.click();
                    }""")
                    lp("已点击『取消』关闭登出对话框（保留登录）")
                else:
                    page.keyboard.press('Escape'); lp("按 Esc 关闭登出对话框")
                time.sleep(1.0)
            else:
                if res.get('cancelText'):
                    page.evaluate("""() => {
                        const d=document.querySelector('.confirm-dialog,.modal,.dialog,.modal-mask,[role=dialog]');
                        const btns=[...d.querySelectorAll('button,.btn,.modal-btn')];
                        const c=btns.find(b=>((b.innerText||'').includes('取消')||(b.innerText||'').includes('暂不')||(b.innerText||'').includes('关闭')));
                        if(c) c.click();
                    }""")
                    lp("已关闭非登出对话框")
                else:
                    page.keyboard.press('Escape')
                time.sleep(0.8)
        return res
    except Exception as e:
        lp(f"dismiss_modals 异常: {e}")
        return None


CLAIMED = ("今日已领", "已领取", "已签", "今日已签到")


def main():
    lp("==== CDP 每日积分领取 开始 ====")
    today = datetime.now().strftime("%Y-%m-%d")
    if not port_open():
        lp("⚠ 调试端口 9222 未开启"); return False

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
        page = find_main_page(browser)
        if not page: lp("未找到主页"); return False
        lp(f"已连接页面: {page.url}")
        try: page.bring_to_front()
        except Exception: pass
        time.sleep(1.0)
        dismiss_modals(page)

        av = avatar_center(page) or [94, 694]
        lp(f"头像中心: {av}")

        panel = None
        entry = None
        for attempt in range(1, 5):
            lp(f"--- 第 {attempt}/4 次：打开菜单并定位加油站入口 ---")
            if menu_opened(page):
                try: page.keyboard.press("Escape")
                except Exception: pass
                time.sleep(0.6)
            click(page, av, "头像菜单")
            mo = False
            for i in range(20):
                if menu_opened(page): mo = True; break
                time.sleep(0.3)
            if not mo:
                lp("菜单未弹出，重试"); continue

            for i in range(30):
                res = find_station_entry(page)
                if isinstance(res, dict) and res.get("coord"):
                    entry = res
                    lp(f"找到加油站入口 (约 {i*0.5:.1f}s): {res}")
                    break
                time.sleep(0.5)
            if not entry:
                lp(f"未找到加油站入口: {res}")
                try: page.keyboard.press("Escape")
                except Exception: pass
                time.sleep(0.8); continue
            dismiss_modals(page)
            click(page, entry["coord"], "Buddy 加油站")
            for i in range(40):
                st = bubble_state(page)
                if st.get("exists"):
                    lp(f"签到面板出现 (约 {i*0.5:.1f}s): {st}")
                    panel = st; break
                time.sleep(0.5)
            if panel:
                break
            lp("面板未出现，重试")
            try: page.keyboard.press("Escape")
            except Exception: pass
            time.sleep(0.8)

        if not panel or not panel.get("exists"):
            lp("⚠ 无法打开签到面板")
            try: page.screenshot(path=SHOT)
            except Exception: pass
            return False

        btn_text = panel.get("btnText", "")
        claim_coord = panel.get("btnCoord") or [75, 638]
        close_coord = panel.get("closeCoord") or [230, 456]
        lp(f"领取按钮文本: {btn_text!r}")

        result = {"status": None}
        if btn_text in CLAIMED:
            lp("→ 当前已是已领取状态")
            result["status"] = "already_claimed"
            with open(LAST_CLAIM, "w", encoding="utf-8") as f:
                f.write(today)
        else:
            lp("→ 点击立即领取")
            dismiss_modals(page)
            click(page, claim_coord, "领取按钮")
            ok = False
            for i in range(12):
                time.sleep(0.5)
                st = bubble_state(page)
                t = st.get("btnText", "")
                if t in CLAIMED:
                    ok = True
                    lp(f"✅ 领取成功确认 (约 {(i+1)*0.5:.1f}s): {st}")
                    break
                if not st.get("exists"):
                    time.sleep(0.5); continue
                if i < 5:
                    dismiss_modals(page)
                    rc = st.get("btnCoord") or claim_coord
                    click(page, rc, f"领取按钮重试{i+1}")
            if ok:
                result["status"] = "claimed_now"
                try: page.screenshot(path=SHOT)
                except Exception: pass
                with open(LAST_CLAIM, "w", encoding="utf-8") as f:
                    f.write(today)
            else:
                lp(f"⚠ 未确认领取成功，最终面板: {bubble_state(page)}")
                try: page.screenshot(path=SHOT)
                except Exception: pass
                click(page, close_coord, "关闭 X")
                time.sleep(1.0)
                result["status"] = "uncertain"
                lp("RESULT " + json.dumps(result, ensure_ascii=False))
                return False

        click(page, close_coord, "关闭 X")
        time.sleep(0.8)
        lp("RESULT " + json.dumps(result, ensure_ascii=False))
    lp("==== 完成 ====")
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
