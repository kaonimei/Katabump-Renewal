#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import subprocess
import requests
from seleniumbase import SB

# 从环境变量获取账号密码和 TG 配置
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""        # tg通知 chat id(可选)
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""      # tg通知bot token(可选)

BASE_URL = "https://dashboard.katabump.com"  # 网站链接

# 多账号来源：USERS_JSON 格式 [{"username":"email","password":"pwd"}, ...]
def load_accounts():
    raw = os.environ.get("USERS_JSON", "")
    if not raw:
        # 兼容单账号 env（KATABUMP_EMAIL/KATABUMP_PASSWORD）
        email = os.environ.get("KATABUMP_EMAIL", "")
        pwd   = os.environ.get("KATABUMP_PASSWORD", "")
        if email:
            return [{"email": email, "password": pwd}]
        print("❌ 未配置 USERS_JSON 或 KATABUMP_EMAIL/KATABUMP_PASSWORD")
        return []
    try:
        users = json.loads(raw)
        accounts = []
        for u in users:
            accounts.append({
                "email": u.get("username") or u.get("email") or "",
                "password": u.get("password") or "",
            })
        return [a for a in accounts if a["email"]]
    except Exception as e:
        print(f"❌ USERS_JSON 解析失败: {e}")
        return []

ACCOUNTS = load_accounts()
CURRENT_EMAIL = ""  # 当前正在处理的账号，供 send_tg_message 脱敏

#  Telegram 推送模块
def send_tg_message(status_icon, status_text, time_left=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return

    # 获取北京时间 (UTC+8)
    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    # 邮箱脱敏：保留用户名前2位和后2位，中间用****代替
    email = CURRENT_EMAIL
    if '@' in email:
        name, domain = email.split('@', 1)
        if len(name) > 4:
            masked_email = f"{name[:2]}****{name[-2:]}@{domain}"
        else:
            masked_email = f"{name}@{domain}"
    else:
        masked_email = (email[:2] + '****') if email else "未知"

    detail = (time_left or "").strip()
    text = (
        f"🇫🇷 katabump 续期通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 续期账户: {masked_email}\n"
        f"⏱️ 续期时间: {current_time_str}"
    )
    if detail:
        text += f"\n📋 详情: {detail}"

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("📩 Telegram 通知发送成功！")
        else:
            print(f"⚠️ Telegram 通知发送失败: {r.text}")
    except Exception as e:
        print(f"⚠️ Telegram 通知发送异常: {e}")

#  页面注入脚本 (Turnstile 专用)
_EXPAND_JS = """
(function() {
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    if (!ts) return 'no-turnstile';
    var el = ts;
    for (var i = 0; i < 20; i++) {
        el = el.parentElement;
        if (!el) break;
        var s = window.getComputedStyle(el);
        if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden')
            el.style.overflow = 'visible';
        el.style.minWidth = 'max-content';
    }
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    return 'done';
})()
"""

_EXISTS_JS = """
(function(){
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

_WININFO_JS = """
(function(){
    return {
        sx: window.screenX || 0,
        sy: window.screenY || 0,
        oh: window.outerHeight,
        ih: window.innerHeight
    };
})()
"""

_TURNSTILE_BBOX_JS = """
(function(){
    function expand(f){
        f.style.width='300px'; f.style.height='80px';
        f.style.minWidth='300px'; f.style.minHeight='80px';
        f.style.visibility='visible'; f.style.opacity='1';
        f.style.zIndex='9999';
        var p=f.parentElement, guard=0;
        while(p && guard<14){ p.style.overflow='visible'; p=p.parentElement; guard++; }
        var r=f.getBoundingClientRect();
        return { x: Math.round(r.left), y: Math.round(r.top),
                 w: Math.round(r.width), h: Math.round(r.height) };
    }
    if (!window.frames) return null;
    var frames = document.querySelectorAll('iframe');
    for (var i=0;i<frames.length;i++){
        var f=frames[i]; var src=f.src||'';
        if (src.indexOf('challenges.cloudflare.com')>-1 || src.indexOf('/turnstile/')>-1){
            var r=f.getBoundingClientRect();
            if (r.width>0 && r.height>0) return expand(f);
        }
    }
    var q = document.querySelector(
        '[class*="cf-turnstile"] iframe, [id*="turnstile"] iframe, '+
        '[class*="turnstile"] iframe, .cf-turnstile-wrapper iframe'
    );
    if (q) return expand(q);
    return null;
})()
"""

_TURNSTILE_LAUNCH_CLICK_JS = """
(function(){
    if (document.querySelector('input[name="cf-turnstile-response"]')) return 'turnstile-ready';
    function isVisible(el){
        if (!el) return false;
        var r = el.getBoundingClientRect();
        var s = window.getComputedStyle(el);
        return r.width > 8 && r.height > 8 && s.display !== 'none' &&
               s.visibility !== 'hidden' && s.opacity !== '0';
    }
    function fireClick(el){
        if (!isVisible(el)) return false;
        var r = el.getBoundingClientRect();
        var cx = r.left + Math.min(30, Math.max(10, r.width / 2));
        var cy = r.top + r.height / 2;
        ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(tp){
            el.dispatchEvent(new MouseEvent(tp, {
                bubbles: true, cancelable: true, composed: true,
                clientX: cx, clientY: cy, button: 0
            }));
        });
        try { el.click(); } catch(e) {}
        return true;
    }
    var f = document.querySelector(
        'iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]'
    );
    if (f && fireClick(f)) return 'clicked-iframe';
    return 'no-launcher';
})()
"""

def js_fill_input(sb, selector: str, text: str):
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (setter) {{ setter.call(el, "{safe_text}"); }} else {{ el.value = "{safe_text}"; }}
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)

def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]], timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except Exception:
            pass

def _xdotool_click(x: int, y: int):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)], timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _restart_proxy():
    if not os.path.exists("sing-box"):
        return
    print("\n🔄 重启 sing-box 以切换代理节点...")
    subprocess.run(["pkill", "-9", "-f", "sing-box"], capture_output=True)
    time.sleep(2)
    log = open("singbox.log", "ab")
    try:
        subprocess.Popen(
            ["./sing-box", "run", "-c", "config.json"],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    finally:
        log.close()
    time.sleep(26)

def handle_turnstile(sb) -> bool:
    print("🔍 处理 Cloudflare Turnstile 验证...")
    time.sleep(2)
    if sb.execute_script(_SOLVED_JS):
        return True
    for _ in range(3):
        try: sb.execute_script(_EXPAND_JS)
        except Exception: pass
        time.sleep(0.5)
    for attempt in range(3):
        if sb.execute_script(_SOLVED_JS):
            return True
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass
        time.sleep(2)
    return sb.execute_script(_SOLVED_JS)

def login(sb, email, password) -> bool:
    print(f"🌐 打开登录页面: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(6)

    try:
        sb.wait_for_element('input[name="email"]', timeout=15)
    except Exception:
        print("❌ 页面未加载出登录表单")
        return False

    js_fill_input(sb, 'input[name="email"]', email)
    time.sleep(0.3)
    js_fill_input(sb, 'input[name="password"]', password)
    time.sleep(1)

    if sb.execute_script(_EXISTS_JS):
        handle_turnstile(sb)

    sb.press_keys('input[name="password"]', '\n')
    time.sleep(5)

    cur_url = sb.get_current_url().split('?')[0].lower()
    if "dashboard" in cur_url:
        print("✅ 登录成功！")
        return True
    print("❌ 登录失败，未跳转到面板")
    return False

def _read_alert(sb):
    try:
        el = sb.find_element("div.alert", timeout=2)
        return (el.text or "").strip()
    except Exception:
        return ""

# ==================== 纯 Python 稳健点击 See 按钮 ====================
def _goto_server_detail(sb) -> bool:
    print("\n🖥️  正在通过纯 Python 查找并点击 See 按钮...")
    time.sleep(3)

    alert_text = _read_alert(sb)
    if alert_text and "can't renew" in alert_text.lower():
        print(f"ℹ️  页面顶部提示: {alert_text}")
        send_tg_message("ℹ️", "⚠️ 未到续期时间", alert_text)
        return False

    # 寻找页面中所有链接和按钮，查找包含 'see' 的元素
    try:
        elements = sb.find_elements("a, button, span, td")
        target_el = None
        for el in elements:
            try:
                txt = (el.text or "").strip().lower()
                if txt == "see":
                    target_el = el
                    break
            except Exception:
                continue
        
        if target_el:
            target_el.click()
            print("✅ 成功通过文本匹配点击了 See 按钮")
        else:
            # 兜底：查找所有包含 /servers/ 的链接
            links = sb.find_elements('a[href*="/servers/"]')
            clicked_fallback = False
            for lnk in links:
                href = lnk.get_attribute("href") or ""
                if "/create" not in href:
                    lnk.click()
                    clicked_fallback = True
                    print("✅ 成功通过 URL 兜底点击了服务器详情链接")
                    break
            if not clicked_fallback:
                print("❌ 未能在页面中找到任何可点击的 See 链接")
                sb.save_screenshot("see_btn_fail.png")
                return False
    except Exception as e:
        print(f"❌ 点击 See 异常: {e}")
        return False

    time.sleep(5)
    print(f"📄 当前页面: {sb.get_current_url()}")
    return True

def _open_renew_modal(sb) -> bool:
    print("\n🔄 正在详情页底部查找 Renew 按钮...")
    time.sleep(2)
    sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)

    try:
        btns = sb.find_elements("button, a.btn")
        for btn in btns:
            if (btn.text or "").strip().lower() == "renew":
                btn.click()
                print("✅ 成功点击 Renew 按钮")
                time.sleep(3)
                return True
    except Exception:
        pass

    print("❌ 未能找到 Renew 按钮")
    sb.save_screenshot("renew_btn_fail.png")
    return False

def _submit_renew(sb):
    print("🖱️  确认弹窗中的 Renew...")
    time.sleep(1)
    try:
        btns = sb.find_elements("div.modal.show button, div.modal.show a.btn")
        for btn in btns:
            txt = (btn.text or "").strip().lower()
            if "renew" in txt or "vérification" in txt:
                btn.click()
                break
    except Exception:
        pass
    time.sleep(5)

def _check_renew_result(sb):
    print("\n📋 检查续期结果...")
    alert_text = _read_alert(sb)
    if not alert_text:
        time.sleep(3)
        alert_text = _read_alert(sb)

    if alert_text:
        print(f"📩 页面提示: {alert_text}")
        low = alert_text.lower()
        if "can't renew" in low or "unable" in low:
            send_tg_message("⏳", "未到续期时间", alert_text)
        elif any(kw in low for kw in ("renewed", "success", "extended")):
            send_tg_message("✅", "续期成功", alert_text)
        else:
            send_tg_message("ℹ️", "续期操作已执行", alert_text)
    else:
        print("ℹ️ 续期操作已执行")
        send_tg_message("ℹ️", "续期操作已执行", "未检测到明确提示")

def renew_server(sb):
    if not _goto_server_detail(sb):
        return
    if not _open_renew_modal(sb):
        return
    _submit_renew(sb)
    _check_renew_result(sb)

def _run_account(sb_kwargs, email, pwd) -> bool:
    global CURRENT_EMAIL
    CURRENT_EMAIL = email
    print(f"🚀 启动浏览器处理账号: {email}")
    try:
        with SB(**sb_kwargs) as sb:
            if login(sb, email, pwd):
                renew_server(sb)
                return True
            else:
                send_tg_message("❌", "登录失败", "未知")
                return False
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        send_tg_message("❌", f"处理异常: {e}", "未知")
        return False

def main():
    if not ACCOUNTS:
        print("❌ 没有可用的账号，退出。")
        raise SystemExit(1)

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:8080"
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        sb_kwargs["proxy"] = proxy_str

    ok_count = 0
    max_attempts = int(os.environ.get("NODE_ATTEMPTS", "3"))
    for idx, acc in enumerate(ACCOUNTS, 1):
        email = acc["email"]
        pwd   = acc["password"]
        acc_ok = False
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                _restart_proxy()
            if _run_account(sb_kwargs, email, pwd):
                acc_ok = True
                break
        if acc_ok:
            ok_count += 1

    if ok_count < len(ACCOUNTS):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
u
