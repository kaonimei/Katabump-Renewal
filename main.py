#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import subprocess
import requests
from seleniumbase import SB

TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""

BASE_URL = "https://dashboard.katabump.com"

def load_accounts():
    raw = os.environ.get("USERS_JSON", "")
    if not raw:
        email = os.environ.get("KATABUMP_EMAIL", "")
        pwd   = os.environ.get("KATABUMP_PASSWORD", "")
        if email:
            return [{"email": email, "password": pwd}]
        print("no accounts configured")
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
        print(f"USERS_JSON parse error: {e}")
        return []

ACCOUNTS = load_accounts()
CURRENT_EMAIL = ""

def send_tg_message(status_icon, status_text, time_left=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    email = CURRENT_EMAIL
    if '@' in email:
        name, domain = email.split('@', 1)
        if len(name) > 4:
            masked_email = f"{name[:2]}****{name[-2:]}@{domain}"
        else:
            masked_email = f"{name}@{domain}"
    else:
        masked_email = (email[:2] + '****') if email else "unknown"
    detail = (time_left or "").strip()
    text = (
        f"katabump renewal notice\n\n"
        f"{status_icon} {status_text}\n"
        f"account: {masked_email}\n"
        f"time: {current_time_str}"
    )
    if detail:
        text += f"\ndetail: {detail}"
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text}, timeout=10)
        if r.status_code == 200:
            print("Telegram notification sent")
        else:
            print(f"Telegram notification failed: {r.text}")
    except Exception as e:
        print(f"Telegram notification error: {e}")

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

_IFRAME_MAP_JS = """
(function(){
    var out=[];
    var frames=document.querySelectorAll('iframe');
    for (var i=0;i<frames.length;i++){
        var f=frames[i], r=f.getBoundingClientRect();
        out.push({ src:(f.src||'').slice(0,80),
                   x:Math.round(r.left), y:Math.round(r.top),
                   w:Math.round(r.width), h:Math.round(r.height) });
    }
    return JSON.stringify(out);
})()
"""

_ALTCHA_EXPAND_JS = """
(function() {
    var modal = document.querySelector('div.modal.show') || document;
    var iframes = modal.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            iframes[i].style.width  = '300px';
            iframes[i].style.height = '150px';
            iframes[i].style.minWidth  = '300px';
            iframes[i].style.minHeight = '150px';
            iframes[i].style.visibility = 'visible';
            iframes[i].style.opacity = '1';
            var el = iframes[i];
            for (var j = 0; j < 10; j++) {
                el = el.parentElement;
                if (!el) break;
                el.style.overflow = 'visible';
            }
            var r2 = iframes[i].getBoundingClientRect();
            return { cx: Math.round(r2.x + 30), cy: Math.round(r2.y + r2.height / 2) };
        }
    }
    return null;
})()
"""

_ALTCHA_SOLVED_JS = """
(function(){
    var modal = document.querySelector('div.modal.show') || document;
    var inputs = modal.querySelectorAll('input[type="hidden"]');
    for (var i = 0; i < inputs.length; i++) {
        var n = (inputs[i].name || '').toLowerCase();
        if ((n.includes('altcha') || n.includes('captcha')) &&
            inputs[i].value && inputs[i].value.length > 20) return true;
    }
    var cbs = modal.querySelectorAll('input[type="checkbox"]');
    for (var j = 0; j < cbs.length; j++) {
        if (cbs[j].disabled) return true;
    }
    var w = modal.querySelector('[data-state="verified"],.altcha--verified,.altcha-verified');
    if (w) return true;
    return false;
})()
"""

def js_fill_input(sb, selector, text):
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (nativeInputValueSetter) {{
            nativeInputValueSetter.call(el, "{safe_text}");
        }} else {{
            el.value = "{safe_text}";
        }}
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)

def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls],
                               capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]],
                               timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except Exception:
            pass
    try:
        subprocess.run(["xdotool", "getactivewindow", "windowactivate"],
                       timeout=3, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _xdotool_click(x, y):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)],
                       timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, stderr=subprocess.DEVNULL)
    except Exception:
        os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")

def _restart_proxy():
    if not os.path.exists("sing-box"):
        print("no sing-box binary, skipping proxy switch")
        return
    print("restarting sing-box...")
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
    try:
        with open("singbox.log", "rb") as f:
            lines = f.read().decode("utf-8", "ignore").splitlines()
        shown = 0
        for ln in lines[-40:]:
            if ("urltest" in ln or "selected" in ln or "node-" in ln) and shown < 5:
                print("sing-box:", ln.strip())
                shown += 1
    except Exception:
        pass

def _switch_to_turnstile_frame(sb):
    try:
        el = sb.driver.execute_script("""
        (function(){
            var frames = document.querySelectorAll('iframe');
            for (var i = 0; i < frames.length; i++){
                var f = frames[i], s = f.src || '';
                if (s.indexOf('challenges.cloudflare.com') > -1 ||
                    s.indexOf('turnstile') > -1) return f;
            }
            var q = document.querySelector('[class*="cf-turnstile"], [id*="turnstile"]');
            if (q){ var qf = q.querySelector('iframe'); if (qf) return qf; }
            return null;
        })()
        """)
        if el is None:
            return False
        sb.driver.switch_to.frame(el)
        return True
    except Exception:
        return False

def handle_turnstile(sb):
    print("handling Cloudflare Turnstile...")
    time.sleep(2)
    if sb.execute_script(_SOLVED_JS):
        print("Turnstile already solved")
        return True
    try:
        fm = sb.execute_script(_IFRAME_MAP_JS)
        print(f"page iframes: {fm}")
    except Exception:
        pass
    for _ in range(3):
        try:
            sb.execute_script(_EXPAND_JS)
        except Exception:
            pass
        time.sleep(0.5)

    for attempt in range(4):
        if sb.execute_script(_SOLVED_JS):
            print(f"Turnstile solved (A attempt {attempt + 1})")
            return True
        print(f"[A] attempt {attempt + 1}/4 uc_gui_click_captcha...")
        try:
            if attempt < 2:
                sb.uc_gui_click_captcha()
            else:
                sb.uc_gui_click_cf(frame="iframe", retry=True, blind=True)
        except Exception as e:
            print(f"[A] error: {e}")
        solved = False
        for _ in range(8):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                solved = True
                break
        if solved:
            print(f"Turnstile solved (A attempt {attempt + 1})")
            return True

    for attempt in range(4):
        if sb.execute_script(_SOLVED_JS):
            print("Turnstile solved (B prefix check)")
            return True
        bbox = None
        try:
            bbox = sb.execute_script(_TURNSTILE_BBOX_JS)
        except Exception:
            pass
        if not bbox:
            print("[B] Turnstile iframe not found, retrying...")
            time.sleep(2)
            continue
        try:
            wi = sb.execute_script(_WININFO_JS)
        except Exception:
            wi = {"sx": 0, "sy": 0, "oh": 800, "ih": 768}
        bar = wi.get("oh", 800) - wi.get("ih", 768)
        cx = bbox["x"] + wi.get("sx", 0) + 30
        cy = bbox["y"] + wi.get("sy", 0) + bar + max(28, int(bbox["h"]) // 2)
        print(f"[B] xdotool click ({cx}, {cy})  bbox={bbox}")
        _xdotool_click(cx, cy)
        solved = False
        for _ in range(8):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                solved = True
                break
        if solved:
            print(f"Turnstile solved (B attempt {attempt + 1})")
            return True
        print(f"[B] attempt {attempt + 1} failed")

    for attempt in range(3):
        if sb.execute_script(_SOLVED_JS):
            print("Turnstile solved (C prefix check)")
            return True
        print(f"[C] attempt {attempt + 1}/3 switching into iframe...")
        if not _switch_to_turnstile_frame(sb):
            print("[C] Turnstile iframe not found")
            sb.driver.switch_to.default_content()
            time.sleep(2)
            continue
        try:
            cb = sb.driver.execute_script("""
            (function(){
                var cands = document.querySelectorAll(
                    '[role="checkbox"], input[type="checkbox"],'+
                    '[class*="checkbox"], [class*="btn-check"]'
                );
                for (var i = 0; i < cands.length; i++){
                    var e = cands[i]; var r = e.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return e;
                }
                return null;
            })()
            """)
            if cb is not None:
                sb.driver.execute_script("arguments[0].focus(); arguments[0].click();", cb)
                print("[C] clicked checkbox element")
            else:
                sb.driver.switch_to.active_element.send_keys(" ")
                print("[C] no checkbox found, sent space key")
        except Exception as e:
            print(f"[C] error: {e}")
        finally:
            sb.driver.switch_to.default_content()
        solved = False
        for _ in range(6):
            time.sleep(1)
            if sb.execute_script(_SOLVED_JS):
                solved = True
                break
        if solved:
            print(f"Turnstile solved (C attempt {attempt + 1})")
            return True

    print("Turnstile A/B/C all failed")
    return False

def login(sb, email, password):
    print(f"opening login page: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(6)
    print("waiting for Cloudflare...")
    cf_passed = False
    for i in range(30):
        page_src = sb.get_page_source() or ""
        if 'name="email"' in page_src.lower():
            cf_passed = True
            print(f"Cloudflare passed ({i+1}s)")
            break
        time.sleep(1)
    if not cf_passed:
        print("Cloudflare may not have passed, continuing...")
    try:
        sb.wait_for_element('input[name="email"]', timeout=15)
    except Exception:
        try:
            sb.wait_for_element('input[name="Email"]', timeout=5)
        except Exception:
            print("login form not found")
            print(f"URL: {sb.get_current_url()}")
            sb.save_screenshot("login_load_fail.png")
            return False
    try:
        for btn in sb.find_elements("button"):
            if "Accept" in (btn.text or ""):
                btn.click()
                time.sleep(0.5)
                break
    except Exception:
        pass
    print("filling email...")
    js_fill_input(sb, 'input[name="email"]', email)
    time.sleep(0.3)
    print("filling password...")
    js_fill_input(sb, 'input[name="password"]', password)
    time.sleep(1)
    print("waiting for Turnstile...")
    ts_found = False
    for i in range(10):
        if sb.execute_script(_EXISTS_JS):
            ts_found = True
            print(f"Turnstile detected ({i+1}s)")
            break
        time.sleep(1)
    if ts_found:
        if not handle_turnstile(sb):
            print("Turnstile failed")
            sb.save_screenshot("login_turnstile_fail.png")
            return False
    else:
        print("no Turnstile detected")
    print("submitting form...")
    sb.press_keys('input[name="password"]', '\n')
    print("waiting for redirect...")
    for _ in range(12):
        time.sleep(1)
        cur_url = sb.get_current_url().split('?')[0].lower()
        page_title = (sb.get_title() or "").lower()
        if "/dashboard" in cur_url or "dashboard" in page_title:
            break
    cur_url = sb.get_current_url().split('?')[0].lower()
    page_title = (sb.get_title() or "").lower()
    if "/dashboard" in cur_url or "dashboard" in page_title:
        print(f"login successful (URL: {sb.get_current_url()})")
        return True
    print(f"login failed (URL: {sb.get_current_url()})")
    sb.save_screenshot("login_failed.png")
    return False

def _read_alert(sb):
    try:
        el = sb.find_element("div.alert", timeout=4)
        return (el.text or "").strip()
    except Exception:
        return ""

def _goto_server_detail(sb):
    print("navigating to server detail page...")
    time.sleep(5)
    alert_text = _read_alert(sb)
    if alert_text and "can't renew" in alert_text.lower():
        print(f"alert: {alert_text}")
        send_tg_message("i", "not yet time to renew", alert_text)
        return False
    see_link = None
    try:
        see_link = sb.find_element('a[href*="/servers/edit?id="]', timeout=10)
        print(f"found link: {see_link.get_attribute('href')}")
    except Exception:
        print("link /servers/edit?id= not found")
        sb.save_screenshot("servers_page_fail.png")
        return False
    see_link.click()
    time.sleep(5)
    print(f"current page: {sb.get_current_url()}")
    return True

def _open_renew_modal(sb):
    print("looking for Renew button...")
    try:
        renew_btn = sb.find_element('button[data-bs-target="#renew-modal"]', timeout=10)
    except Exception:
        try:
            renew_btn = sb.find_element('button.btn.btn-outline-primary', timeout=5)
        except Exception:
            print("Renew button not found")
            return False
    sb.execute_script("""
        (function(){
            var btn = document.querySelector('button[data-bs-target="#renew-modal"]')
                     || document.querySelector('button.btn.btn-outline-primary');
            if (btn) btn.scrollIntoView({behavior:'smooth',block:'center'});
        })()
    """)
    time.sleep(0.8)
    renew_btn.click()
    print("clicked Renew button, waiting for ALTCHA...")
    time.sleep(3)
    try:
        sb.find_element('div.modal.show', timeout=5)
        print("modal opened")
        return True
    except Exception:
        print("modal did not open")
        return False

def _solve_altcha(sb):
    print("handling ALTCHA...")
    time.sleep(2)
    if sb.execute_script(_ALTCHA_SOLVED_JS):
        print("ALTCHA already solved")
        return True
    coords = None
    try:
        coords = sb.execute_script(_ALTCHA_EXPAND_JS)
    except Exception:
        pass
    if coords:
        print(f"iframe coords: ({coords['cx']}, {coords['cy']})")
    for attempt in range(3):
        if sb.execute_script(_ALTCHA_SOLVED_JS):
            print(f"ALTCHA solved (round {attempt + 1})")
            return True
        if coords:
            try:
                wi = sb.execute_script(_WININFO_JS)
            except Exception:
                wi = {"sx": 0, "sy": 0, "oh": 800, "ih": 768}
            bar = wi["oh"] - wi["ih"]
            ax = coords["cx"] + wi["sx"]
            ay = coords["cy"] + wi["sy"] + bar
            print(f"xdotool click ALTCHA ({ax}, {ay})")
            _xdotool_click(ax, ay)
        try:
            iframes = sb.find_elements('div.modal.show iframe')
            for iframe in iframes:
                try:
                    iframe.click()
                    print("clicked modal iframe")
                except Exception:
                    pass
        except Exception:
            pass
        sb.execute_script("""
            (function(){
                var modal = document.querySelector('div.modal.show');
                if (!modal) return;
                var iframes = modal.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    iframes[i].click();
                    iframes[i].dispatchEvent(new MouseEvent('click', {bubbles:true}));
                }
                var labels = modal.querySelectorAll('label');
                for (var j = 0; j < labels.length; j++) {
                    var txt = (labels[j].textContent || '').toLowerCase();
                    if (txt.includes('robot') || txt.includes('captcha') || txt.includes('verify'))
                        labels[j].click();
                }
                var cbs = modal.querySelectorAll('input[type="checkbox"]');
                for (var k = 0; k < cbs.length; k++) {
                    if (!cbs[k].disabled) {
                        cbs[k].click();
                        cbs[k].dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    }
                }
            })()
        """)
        for _ in range(6):
            time.sleep(1)
            if sb.execute_script(_ALTCHA_SOLVED_JS):
                print(f"ALTCHA solved (round {attempt + 1})")
                return True
        print(f"ALTCHA round {attempt + 1} failed, retrying...")
        try:
            new_coords = sb.execute_script(_ALTCHA_EXPAND_JS)
            if new_coords:
                coords = new_coords
        except Exception:
            pass
    print("ALTCHA failed after 3 rounds")
    return False

def _submit_renew(sb):
    print("clicking Renew submit button...")
    try:
        submit = sb.find_element('div.modal.show button.btn-primary', timeout=5)
        submit.click()
    except Exception:
        sb.execute_script("""
            (function(){
                var m = document.querySelector('div.modal.show');
                if (!m) return;
                var bs = m.querySelectorAll('button');
                for (var i = 0; i < bs.length; i++)
                    if (/renew/i.test(bs[i].textContent)) bs[i].click();
            })()
        """)
    time.sleep(3)

def _check_renew_result(sb):
    print("checking renew result...")
    alert_text = _read_alert(sb)
    if not alert_text:
        time.sleep(3)
        alert_text = _read_alert(sb)
    if alert_text:
        print(f"page alert: {alert_text}")
        low = alert_text.lower()
        if "can't renew" in low or "unable" in low:
            send_tg_message("x", "not yet time to renew", alert_text)
        elif any(kw in low for kw in ("renewed", "success", "extended")):
            send_tg_message("v", "renewal successful", alert_text)
        else:
            send_tg_message("i", "renewal executed", alert_text)
    else:
        print("no alert detected")
        send_tg_message("i", "renewal executed", "no alert detected")

def renew_server(sb):
    print("=" * 25)
    print("starting renewal flow")
    print("=" * 25)
    if not _goto_server_detail(sb):
        return
    if not _open_renew_modal(sb):
        return
    altcha_ok = _solve_altcha(sb)
    if not altcha_ok:
        print("ALTCHA not solved, attempting submit anyway...")
    _submit_renew(sb)
    _check_renew_result(sb)

def _run_account(sb_kwargs, email, pwd):
    global CURRENT_EMAIL
    CURRENT_EMAIL = email
    print("launching browser...")
    try:
        with SB(**sb_kwargs) as sb:
            try:
                sb.open("https://api.ip.sb/ip")
                print(f"exit IP: {sb.get_text('body')}")
            except Exception:
                pass
            if login(sb, email, pwd):
                renew_server(sb)
                return True
            else:
                print("login failed")
                send_tg_message("x", "login failed", "")
                return False
    except Exception as e:
        print(f"account {email} error: {e}")
        send_tg_message("x", f"error: {e}", "")
        return False

def main():
    print("=" * 25)
    print("katabump auto renewal")
    print("=" * 25)
    if not ACCOUNTS:
        print("no accounts configured")
        raise SystemExit(1)
    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:8080"
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        print(f"using proxy: {proxy_str}")
        sb_kwargs["proxy"] = proxy_str
    else:
        print("no proxy, direct connection")
    print(f"accounts to process: {len(ACCOUNTS)}")
    ok_count = 0
    max_attempts = int(os.environ.get("NODE_ATTEMPTS", "3"))
    for idx, acc in enumerate(ACCOUNTS, 1):
        email = acc["email"]
        pwd   = acc["password"]
        print("\n" + "=" * 25)
        print(f"account {idx}/{len(ACCOUNTS)}: {email}")
        print("=" * 25)
        acc_ok = False
        for attempt in range(1, max_attempts + 1):
            print(f"attempt {attempt}/{max_attempts}")
            if attempt > 1:
                _restart_proxy()
            if _run_account(sb_kwargs, email, pwd):
                acc_ok = True
                break
        if acc_ok:
            ok_count += 1
        else:
            print(f"all attempts failed for {email}")
            send_tg_message("x", "all attempts failed", f"{max_attempts} attempts")
    print("\n" + "=" * 25)
    print(f"done: {ok_count}/{len(ACCOUNTS)} succeeded")
    print("=" * 25)
    if ok_count < len(ACCOUNTS):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
