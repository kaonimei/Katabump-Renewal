import os
import sys
import time
import socket
import requests
import zipfile
import io
import datetime
import re
import json
from DrissionPage import ChromiumPage, ChromiumOptions

RESULT_CODES = {
    "SUCCESS": "续期成功",
    "SUCCESS_TOO_EARLY": "未到续期时间",
    "FAIL_LOGIN_NO_FORM": "登录页无表单",
    "FAIL_LOGIN_FAILED": "登录失败",
    "FAIL_NO_RENEW_BUTTON": "找不到续期按钮",
    "FAIL_MODAL_NOT_OPEN": "弹窗未打开",
    "FAIL_ALTCHA_TIMEOUT": "Altcha验证超时",
    "FAIL_NO_SUBMIT_BUTTON": "弹窗内无提交按钮",
    "FAIL_CAPTCHA": "验证码未通过",
    "FAIL_OTHER": "其他错误",
    "FAIL_MAX_RETRY": "达到最大重试次数",
    "FAIL_EXCEPTION": "程序异常"
}

def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def find_chrome_path():
    candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        os.environ.get("CHROME_BIN", ""),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None

def ensure_extensions_dir():
    os.makedirs("extensions", exist_ok=True)

def download_and_extract_zip(url, extract_dir, plugin_name):
    try:
        ensure_extensions_dir()
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        if resp.status_code != 200:
            log(f"❌ [{plugin_name}] 下载失败: HTTP {resp.status_code}")
            return False
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(extract_dir)
        return True
    except Exception as e:
        log(f"❌ [{plugin_name}] 异常: {e}")
        return False

def download_silk():
    extract_dir = "extensions/silk_ext"
    if os.path.exists(extract_dir):
        return os.path.abspath(extract_dir)
    log(">>> [插件1] 正在下载 Silk Privacy Pass...")
    url = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3Dajhmfdgkijocedmfjonnpjfojldioehi%26uc"
    if download_and_extract_zip(url, extract_dir, "插件1"):
        return os.path.abspath(extract_dir)
    return None

def pass_full_page_shield(page):
    for _ in range(6):
        title = (page.title or "").lower()
        if "just a moment" in title or "checking your browser" in title or "please wait" in title:
            log("--- [门神] 全屏盾检测中，等待 5s...")
            time.sleep(5)
        else:
            return True
    log("--- [门神] 全屏盾可能未通过，继续执行...")
    return False

def wait_turnstile_ready(page, timeout=90):
    saw_iframe = False
    for second in range(timeout):
        try:
            state = page.run_js("""
                const iframes = Array.from(document.querySelectorAll('iframe'));
                const hasIframe = iframes.some(f => {
                    const src = (f.getAttribute('src') || '').toLowerCase();
                    return src.includes('turnstile') || src.includes('cloudflare');
                });
                const tokenInput = document.querySelector('input[name="cf-turnstile-response"]');
                const token = tokenInput ? (tokenInput.value || '') : '';
                return { hasIframe, hasToken: !!token };
            """)
            if isinstance(state, dict):
                has_iframe = bool(state.get("hasIframe"))
                has_token = bool(state.get("hasToken"))
            else:
                has_iframe = False
                has_token = False
            if has_iframe:
                saw_iframe = True
            if has_token:
                log(f"✅ [Turnstile] 检测到 token，等待 {second}s 后继续")
                return True
            if saw_iframe and not has_iframe:
                log(f"✅ [Turnstile] 验证 iframe 已消失，等待 {second}s 后继续")
                return True
        except Exception:
            pass
        if second > 0 and second % 10 == 0:
            log(f">>> [Turnstile] 等待中... {second}/{timeout}s")
        time.sleep(1)
    if saw_iframe:
        log("⚠️ [Turnstile] 超时，准备补刀后继续")
        return False
    log(">>> [Turnstile] 未检测到挑战组件，继续执行")
    return True

def nudge_turnstile(page):
    log(">>> [补刀] 尝试点击 Turnstile...")
    try:
        iframes = page.eles("tag:iframe")
        log(f"  找到 {len(iframes)} 个 iframe")
        for idx, fr in enumerate(iframes):
            try:
                checkbox = fr.ele('css:input[type="checkbox"]', timeout=1)
                if checkbox:
                    log(f"  iframe[{idx}] 点击 checkbox")
                    checkbox.click(by_js=True)
                    time.sleep(3)
                    return
                body = fr.ele("tag:body", timeout=1)
                if body:
                    log(f"  iframe[{idx}] 点击 body")
                    body.click(by_js=True)
                    time.sleep(3)
                    return
            except Exception:
                continue
    except Exception as e:
        log(f"⚠️ 补刀失败: {e}")

def extract_turnstile_sitekey(page):
    try:
        sitekey = page.run_js("""
            const frames = Array.from(document.querySelectorAll('iframe[src*="turnstile"], iframe[src*="cloudflare"]'));
            for (const frame of frames) {
                const src = frame.getAttribute('src') || '';
                if (!src) continue;
                try {
                    const u = new URL(src, location.href);
                    const sk = u.searchParams.get('sitekey') || u.searchParams.get('k');
                    if (sk) return sk;
                } catch (e) {}
                const m = src.match(/[?&](?:sitekey|k)=([^&]+)/i);
                if (m && m[1]) return decodeURIComponent(m[1]);
            }
            const widget = document.querySelector('.cf-turnstile,[data-sitekey]');
            if (widget) {
                const sk = widget.getAttribute('data-sitekey');
                if (sk) return sk;
            }
            return '';
        """)
        return str(sitekey or "").strip()
    except Exception:
        return ""

def inject_turnstile_token(page, token):
    if not token:
        return False
    try:
        count = page.run_js("""
            const token = arguments[0];
            let filled = 0;
            const selectors = [
                'input[name="cf-turnstile-response"]',
                'textarea[name="cf-turnstile-response"]'
            ];
            for (const selector of selectors) {
                const nodes = document.querySelectorAll(selector);
                for (const node of nodes) {
                    node.value = token;
                    node.dispatchEvent(new Event('input', { bubbles: true }));
                    node.dispatchEvent(new Event('change', { bubbles: true }));
                    filled += 1;
                }
            }
            const widgets = document.querySelectorAll('.cf-turnstile,[data-sitekey]');
            for (const w of widgets) {
                const cb = w.getAttribute('data-callback');
                if (cb && typeof window[cb] === 'function') {
                    try { window[cb](token); } catch (e) {}
                }
            }
            return filled;
        """, token)
        return bool(count)
    except Exception:
        return False

def solve_turnstile_by_capsolver(page, page_url, timeout=120):
    api_key = os.environ.get("CAPSOLVER_API_KEY", "").strip()
    if not api_key:
        return False
    sitekey = extract_turnstile_sitekey(page)
    if not sitekey:
        log("⚠️ [CapSolver] 未获取到 Turnstile sitekey，跳过")
        return False

    try:
        create_resp = requests.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": api_key,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": sitekey
                }
            },
            timeout=20
        )
        data = create_resp.json()
    except Exception as e:
        log(f"⚠️ [CapSolver] createTask 失败: {e}")
        return False

    task_id = data.get("taskId")
    if not task_id:
        log(f"⚠️ [CapSolver] createTask 返回异常: {data}")
        return False

    log(">>> [CapSolver] 任务已创建，等待返回 token...")
    waited = 0
    while waited < timeout:
        time.sleep(3)
        waited += 3
        try:
            poll_resp = requests.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": api_key, "taskId": task_id},
                timeout=20
            )
            poll_data = poll_resp.json()
        except Exception as e:
            log(f"⚠️ [CapSolver] 轮询异常: {e}")
            continue

        status = str(poll_data.get("status", "")).lower()
        if status == "ready":
            token = str((poll_data.get("solution") or {}).get("token", "")).strip()
            if token and inject_turnstile_token(page, token):
                log(f"✅ [CapSolver] token 已注入 (耗时 {waited}s)")
                return True
            log("⚠️ [CapSolver] token 注入失败")
            return False
        if status == "failed" or poll_data.get("errorId"):
            log(f"⚠️ [CapSolver] 解题失败: {poll_data}")
            return False
    log("⚠️ [CapSolver] 解题超时")
    return False

def do_login(page, email, password):
    log(">>> 打开登录页...")
    page.get("https://dashboard.katabump.com/auth/login")
    time.sleep(2)
    pass_full_page_shield(page)

    email_input = page.ele('css:input[name="email"]', timeout=10)
    if not email_input:
        log("❌ 未找到登录表单")
        return False

    log(">>> 填写登录信息...")
    email_input.clear()
    email_input.input(email)
    page.ele('css:input[name="password"]').clear()
    page.ele('css:input[name="password"]').input(password)

    log(">>> 等待 Turnstile 加载...")
    time.sleep(3)
    iframe = page.ele('css:iframe[src*="turnstile"], iframe[src*="cloudflare"]', timeout=5)
    if iframe:
        log(">>> 检测到 Turnstile，等待验证结果...")
    else:
        log("⚠️ 未检测到 Turnstile iframe，继续轮询是否自动放行")

    solved = False
    if iframe:
        solved = solve_turnstile_by_capsolver(page, page.url or "https://dashboard.katabump.com/auth/login")
    if solved:
        wait_turnstile_ready(page, timeout=30)
    elif not wait_turnstile_ready(page, timeout=90):
        nudge_turnstile(page)
        wait_turnstile_ready(page, timeout=30)

    log(">>> 提交登录...")
    page.ele("css:button#submit").click()
    time.sleep(10)
    log(f"  提交后 URL: {page.url}")

    if "error=captcha" in (page.url or "").lower():
        log("❌ Turnstile 验证未通过")
        return False

    log(">>> 访问 dashboard 验证 session...")
    page.get("https://dashboard.katabump.com/dashboard")
    time.sleep(3)
    pass_full_page_shield(page)
    log(f"  Dashboard URL: {page.url}")

    if "dashboard" in page.url.lower() and "login" not in page.url.lower():
        log("✅ 登录成功，Session 有效")
        return True

    log("❌ 登录失败，仍被重定向到登录页")
    return False

def click_and_wait_altcha(page, timeout=30):
    log(">>> [Altcha] 尝试点击复选框...")
    clicked = False
    try:
        clicked = page.run_js("""
            const w = document.querySelector('#renew-modal altcha-widget');
            if (!w) return false;
            const cb = w.querySelector('input[type="checkbox"]');
            if (cb) { cb.click(); return true; }
            if (w.shadowRoot) {
                const scb = w.shadowRoot.querySelector('input[type="checkbox"]');
                if (scb) { scb.click(); return true; }
                const btn = w.shadowRoot.querySelector('button, label, .altcha-checkbox');
                if (btn) { btn.click(); return true; }
            }
            w.click();
            return true;
        """)
    except Exception as e:
        log(f"⚠️ JS 点击失败: {e}")

    if clicked:
        log("✅ [Altcha] 已点击，等待 PoW...")
    else:
        try:
            modal_ele = page.ele("css:#renew-modal")
            altcha = modal_ele.ele("tag:altcha-widget", timeout=3)
            if altcha:
                altcha.click(by_js=True)
                log("✅ [Altcha] 点击了 altcha-widget")
        except Exception as e:
            log(f"⚠️ 备用点击失败: {e}")

    for i in range(timeout):
        try:
            val = page.run_js("""
                const w = document.querySelector('#renew-modal altcha-widget');
                if (!w) return '';
                const inp = w.querySelector('input[name="altcha"]');
                if (inp && inp.value) return inp.value;
                if (w.shadowRoot) {
                    const sinp = w.shadowRoot.querySelector('input[name="altcha"]');
                    if (sinp && sinp.value) return sinp.value;
                }
                return '';
            """)
            if val:
                log(f"✅ [Altcha] PoW 完成 (等待了 {i}s)")
                return True
        except Exception:
            pass
        time.sleep(1)

    log("⚠️ [Altcha] 超时，尝试直接提交...")
    return False

def analyze_page_alert(page):
    log(">>> [系统] 检查结果...")
    danger = page.ele("css:.alert.alert-danger")
    if danger and danger.states.is_displayed:
        text = danger.text
        log(f"⬇️ 红色提示: {text}")
        if "can't renew" in text.lower() or "cannot renew" in text.lower():
            match = re.search(r"\(in (\d+) day", text)
            days = match.group(1) if match else "?"
            log(f"✅ [结果] 未到期 (等待 {days} 天)")
            return "SUCCESS_TOO_EARLY"
        if "captcha" in text.lower() or "altcha" in text.lower():
            return "FAIL_CAPTCHA"
        return "FAIL_OTHER"

    success = page.ele("css:.alert.alert-success")
    if success and success.states.is_displayed:
        log(f"⬇️ 绿色提示: {success.text}")
        log("🎉 [结果] 续期成功！")
        return "SUCCESS"
    return "UNKNOWN"

def load_accounts():
    accounts_json = os.environ.get("KB_ACCOUNTS_JSON", "").strip()
    if accounts_json:
        try:
            data = json.loads(accounts_json)
            if not isinstance(data, list):
                log("❌ KB_ACCOUNTS_JSON 必须是数组")
                return None
            accounts = []
            for index, item in enumerate(data, start=1):
                if not isinstance(item, dict):
                    log(f"❌ 第 {index} 个账号配置不是对象")
                    return None
                email = str(item.get("email", "")).strip()
                password = str(item.get("password", "")).strip()
                target_url = str(item.get("url", "")).strip()
                if not email or not password or not target_url:
                    log(f"❌ 第 {index} 个账号缺少 email/password/url")
                    return None
                accounts.append({"email": email, "password": password, "url": target_url})
            return accounts
        except json.JSONDecodeError as e:
            log(f"❌ KB_ACCOUNTS_JSON 不是合法 JSON: {e}")
            return None

    email = os.environ.get("KB_EMAIL")
    password = os.environ.get("KB_PASSWORD")
    target_url = os.environ.get("KB_RENEW_URL")
    missing_env = [name for name, value in {
        "KB_EMAIL": email, "KB_PASSWORD": password, "KB_RENEW_URL": target_url
    }.items() if not value]
    if missing_env:
        log(f"❌ 配置缺失: {', '.join(missing_env)}")
        return None
    return [{"email": email, "password": password, "url": target_url}]

def send_telegram_message(text):
    tg_token = os.environ.get("TG_BOT_TOKEN", "").strip()
    tg_chat_id = os.environ.get("TG_CHAT_ID", "").strip()
    if not tg_token or not tg_chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            json={"chat_id": tg_chat_id, "text": text},
            timeout=15
        )
        if resp.status_code != 200:
            log(f"⚠️ TG 发送失败: HTTP {resp.status_code}")
            return False
        return True
    except requests.RequestException as e:
        log(f"⚠️ TG 网络异常: {e}")
        return False

def create_page(path_silk, account_index):
    co = ChromiumOptions()
    co.set_argument("--headless=new")
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--window-size=1920,1080")
    co.set_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    chrome_path = find_chrome_path()
    if chrome_path:
        co.set_browser_path(chrome_path)
        log(f">>> Chrome 路径: {chrome_path}")
    else:
        log("⚠️ 未找到 Chrome 路径，使用默认")

    port = get_free_port()
    address = f"127.0.0.1:{port}"
    log(f">>> 调试端口: {address}")

    # 必须是 ip:port，否则 DrissionPage 4.1 会 split 失败
    if hasattr(co, "set_local_port"):
        try:
            co.set_local_port(port)
        except Exception:
            pass
    if hasattr(co, "set_address"):
        co.set_address(address)
    elif hasattr(co, "set_paths"):
        try:
            co.set_paths(address=address)
        except Exception:
            pass

    addr_now = str(getattr(co, "address", "") or "")
    if ":" not in addr_now:
        log(f"⚠️ address 异常: {addr_now!r}，强制写入 {address}")
        try:
            co._address = address
        except Exception:
            pass
        try:
            co.set_argument(f"--remote-debugging-port={port}")
        except Exception:
            pass

    user_dir = f"/tmp/kb_chrome_{account_index}_{int(time.time())}_{port}"
    os.makedirs(user_dir, exist_ok=True)
    co.set_user_data_path(user_dir)

    plugin_count = 0
    if path_silk:
        co.add_extension(path_silk)
        plugin_count += 1
    log(f">>> [浏览器] 已挂载插件数量: {plugin_count}")
    log(f">>> ChromiumOptions.address = {getattr(co, 'address', None)!r}")

    page = ChromiumPage(co)
    page.set.timeouts(15)
    return page

def renew_single_account(email, password, target_url, path_silk, account_index, total_accounts):
    page = None
    last_error = None
    try:
        log(f"================ 账号 {account_index}/{total_accounts} 开始 ================")
        page = create_page(path_silk, account_index)

        log(">>> [Step 1] 登录...")
        if not do_login(page, email, password):
            return "FAIL_LOGIN_FAILED"

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            log(f"\n🚀 [Step 2] 尝试续期 (第 {attempt}/{max_retries} 次)...")
            log(f">>> 目标 URL: {target_url}")
            page.get(target_url)
            time.sleep(5)
            log(f"  页面标题: {page.title} | URL: {page.url}")

            if "login" in page.url.lower():
                log("⚠️ 被重定向到登录页，重新登录...")
                if not do_login(page, email, password):
                    last_error = "FAIL_LOGIN_FAILED"
                    continue
                page.get(target_url)
                time.sleep(5)
                log(f"  重新登录后 URL: {page.url}")
                if "login" in page.url.lower():
                    log("❌ 重新登录后仍被踢回")
                    last_error = "FAIL_LOGIN_FAILED"
                    continue

            pass_full_page_shield(page)

            log(">>> 查找续期按钮...")
            renew_btn = page.ele('css:button[data-bs-target="#renew-modal"]', timeout=15)
            if not renew_btn or not renew_btn.states.is_displayed:
                log("❌ 未找到续期按钮，检查页面状态...")
                result = analyze_page_alert(page)
                if result == "SUCCESS_TOO_EARLY":
                    return result
                last_error = "FAIL_NO_RENEW_BUTTON"
                continue

            log("✅ 找到续期按钮")
            log(">>> 点击 Renew 按钮（打开弹窗）...")
            renew_btn.click(by_js=True)
            time.sleep(2)

            modal = None
            for _ in range(10):
                candidate = page.ele("css:#renew-modal", timeout=1)
                if candidate:
                    try:
                        display = candidate.style("display")
                        if display and display != "none":
                            modal = candidate
                            break
                    except Exception:
                        modal = candidate
                        break
                time.sleep(0.5)

            if not modal:
                log("❌ 弹窗未出现")
                last_error = "FAIL_MODAL_NOT_OPEN"
                continue

            log("✅ 弹窗已打开")
            time.sleep(1)
            if not click_and_wait_altcha(page, timeout=30):
                log("⚠️ Altcha 未确认完成，仍尝试提交...")
                last_error = "FAIL_ALTCHA_TIMEOUT"

            confirm_btn = modal.ele("css:button[type='submit'].btn-primary", timeout=5)
            if not confirm_btn:
                confirm_btn = modal.ele("css:form button[type='submit']", timeout=3)
            if not confirm_btn:
                log("❌ 弹窗内未找到提交按钮")
                last_error = "FAIL_NO_SUBMIT_BUTTON"
                continue

            log(">>> 点击弹窗内 Renew 提交按钮...")
            confirm_btn.click(by_js=True)
            log(">>> 等待响应 (8s)...")
            time.sleep(8)

            result = analyze_page_alert(page)
            log(f">>> 本次结果: {result} ({RESULT_CODES.get(result, result)})")

            if result in ("SUCCESS", "SUCCESS_TOO_EARLY"):
                return result
            if result == "FAIL_CAPTCHA":
                log("⚠️ 验证码未通过，重试...")
                last_error = result
                time.sleep(2)
                continue
            last_error = result if result else "FAIL_OTHER"

        log("❌ 最大重试次数已达")
        return last_error or "FAIL_MAX_RETRY"

    except Exception as e:
        log(f"❌ 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return "FAIL_EXCEPTION"
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass

def job():
    accounts = load_accounts()
    if not accounts:
        return 1

    path_silk = download_silk()

    trigger_source = os.environ.get("RUN_TRIGGER_SOURCE", "unknown")
    send_telegram_message(
        f"🚀 Katabump 续期任务开始\n触发方式: {trigger_source}\n账号数量: {len(accounts)}"
    )

    result_lines = []
    has_failure = False
    for index, account in enumerate(accounts, start=1):
        status = renew_single_account(
            account["email"],
            account["password"],
            account["url"],
            path_silk,
            index,
            len(accounts)
        )
        readable = RESULT_CODES.get(status, status)
        if status in ("SUCCESS", "SUCCESS_TOO_EARLY"):
            status_text = f"✅ {readable}"
        else:
            status_text = f"❌ {readable}"
            has_failure = True
        email_hint = account["email"][:3] + "***" if account["email"] else "unknown"
        result_lines.append(f"{index}. {email_hint}: {status_text}")

    summary = "\n".join(result_lines)
    send_telegram_message(
        f"📣 Katabump 续期任务结束\n触发方式: {trigger_source}\n\n{summary}"
    )
    log("===== 任务汇总 =====")
    log(summary)
    return 1 if has_failure else 0

if __name__ == "__main__":
    sys.exit(job())
