import os
import sys
import time
import requests
import zipfile
import io
import datetime
import re
import json
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 状态码 ====================
RESULT_CODES = {
    "SUCCESS": "续期成功",
    "SUCCESS_TOO_EARLY": "未到续期时间",
    "FAIL_LOGIN_NO_FORM": "登录页无表单",
    "FAIL_LOGIN_STILL_ON_PAGE": "登录失败仍在登录页",
    "FAIL_NO_RENEW_BUTTON": "找不到续期按钮",
    "FAIL_MODAL_NOT_OPEN": "弹窗未打开",
    "FAIL_ALTCHA_TIMEOUT": "Altcha验证超时",
    "FAIL_NO_SUBMIT_BUTTON": "弹窗内无提交按钮",
    "FAIL_CAPTCHA": "验证码未通过",
    "FAIL_OTHER": "其他错误",
    "FAIL_MAX_RETRY": "达到最大重试次数",
    "FAIL_EXCEPTION": "程序异常"
}

# ==================== 基础工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def ensure_extensions_dir():
    if not os.path.exists("extensions"):
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
    except requests.RequestException as e:
        log(f"❌ [{plugin_name}] 网络异常: {e}")
    except zipfile.BadZipFile:
        log(f"❌ [{plugin_name}] 下载内容不是有效压缩包")
    except Exception as e:
        log(f"❌ [{plugin_name}] 处理异常: {e}")
    return False

def download_silk():
    extract_dir = "extensions/silk_ext"
    if os.path.exists(extract_dir): return os.path.abspath(extract_dir)
    log(">>> [插件1] 正在下载 Silk Privacy Pass...")
    url = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3Dajhmfdgkijocedmfjonnpjfojldioehi%26uc"
    if download_and_extract_zip(url, extract_dir, "插件1"):
        return os.path.abspath(extract_dir)
    return None

def download_cf_autoclick():
    extract_root = "extensions/cf_autoclick_root"
    if not os.path.exists(extract_root):
        log(">>> [插件2] 正在下载 CF-AutoClick (Master)...")
        url = "https://codeload.github.com/tenacious6/cf-autoclick/zip/refs/heads/master"
        if not download_and_extract_zip(url, extract_root, "插件2"):
            return None
    for root, dirs, files in os.walk(extract_root):
        if "manifest.json" in files:
            log(f"✅ [插件2] 路径锁定: {os.path.basename(root)}")
            return os.path.abspath(root)
    return None

# ==================== 核心逻辑 ====================

def pass_full_page_shield(page):
    """处理全屏盾 — 只在真正是 CF 盾时等待"""
    for _ in range(6):
        title = page.title.lower()
        if "just a moment" in title or "checking your browser" in title or "please wait" in title:
            log("--- [门神] 全屏盾检测中，等待 5s...")
            time.sleep(5)
        else:
            return True
    log("--- [门神] 全屏盾可能未通过，继续执行...")
    return False

def click_and_wait_altcha(page, timeout=30):
    """点击 Altcha 复选框，然后等待 PoW 自动完成"""
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
            return false;
        """)
    except Exception as e:
        log(f"⚠️ JS 点击失败: {e}")

    if clicked:
        log("✅ [Altcha] 复选框已点击，等待 PoW 完成...")
    else:
        log("⚠️ [Altcha] JS 点击未成功，尝试 DrissionPage 直接点击...")
        try:
            modal_ele = page.ele('css:#renew-modal')
            altcha = modal_ele.ele('tag:altcha-widget', timeout=3)
            if altcha:
                altcha.click(by_js=True)
                log("✅ [Altcha] 点击了 altcha-widget 元素")
                clicked = True
        except Exception as e:
            log(f"⚠️ 备用点击也失败: {e}")

    log(f">>> [Altcha] 等待验证完成 (最多 {timeout}s)...")
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
                log(f"✅ [Altcha] PoW 验证完成！(等待了 {i}s)")
                return True
        except Exception:
            pass
        time.sleep(1)

    log("⚠️ [Altcha] 超时，尝试直接提交...")
    return False

def analyze_page_alert(page):
    """解析续期结果"""
    log(">>> [系统] 检查结果...")
    danger = page.ele('css:.alert.alert-danger')
    if danger and danger.states.is_displayed:
        text = danger.text
        log(f"⬇️ 红色提示: {text}")
        if "can't renew" in text.lower() or "cannot renew" in text.lower():
            match = re.search(r'\(in (\d+) day', text)
            days = match.group(1) if match else "?"
            log(f"✅ [结果] 未到期 (等待 {days} 天)")
            return "SUCCESS_TOO_EARLY"
        elif "captcha" in text.lower() or "altcha" in text.lower():
            return "FAIL_CAPTCHA"
        return "FAIL_OTHER"

    success = page.ele('css:.alert.alert-success')
    if success and success.states.is_displayed:
        log(f"⬇️ 绿色提示: {success.text}")
        log("🎉 [结果] 续期成功！")
        return "SUCCESS"

    return "UNKNOWN"

# ==================== 账号与通知 ====================

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
        log("❌ 你可以改用 KB_ACCOUNTS_JSON 传入多账号配置")
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

# ==================== 主续期逻辑 ====================

def renew_single_account(email, password, target_url, path_silk, path_cf, account_index, total_accounts):
    page = None
    last_error = None

    try:
        log(f"================ 账号 {account_index}/{total_accounts} 开始 ================")

        co = ChromiumOptions()
        co.set_argument('--headless=new')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

        plugin_count = 0
        if path_silk:
            co.add_extension(path_silk)
            plugin_count += 1
        if path_cf:
            co.add_extension(path_cf)
            plugin_count += 1
        log(f">>> [浏览器] 已挂载插件数量: {plugin_count}")

        co.auto_port()
        page = ChromiumPage(co)
        page.set.timeouts(15)

        # ── Step 1: 登录 ──────────────────────────────────────
        log(">>> [Step 1] 登录...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)

        email_input = page.ele('css:input[name="email"]')
        if not email_input:
            log("❌ 未找到登录表单")
            return "FAIL_LOGIN_NO_FORM"

        email_input.input(email)
        page.ele('css:input[name="password"]').input(password)
        page.ele('css:button#submit').click()

        try:
            page.wait.url_change('login', exclude=True, timeout=20)
            log("✅ 登录跳转成功")
        except Exception:
            if 'login' in page.url.lower():
                log("❌ 登录失败，仍在登录页")
                return "FAIL_LOGIN_STILL_ON_PAGE"
            log("⚠️ 登录跳转超时但可能已登录，继续...")

        # ── Step 2: 续期重试循环 ──────────────────────────────
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            log(f"\n🚀 [Step 2] 尝试续期 (第 {attempt}/{max_retries} 次)...")
            page.get(target_url)
            time.sleep(3)
            log(f"  页面标题: {page.title} | URL: {page.url}")
            pass_full_page_shield(page)

            # 等待续期按钮出现（最多 120 秒）
            log(">>> 等待续期按钮出现...")
            try:
                page.wait.ele_displayed('css:button[data-bs-target="#renew-modal"]', timeout=120)
                log("✅ 续期按钮已出现")
            except Exception:
                log("⚠️ 等待按钮超时，检查页面状态...")
                result = analyze_page_alert(page)
                if result == "SUCCESS_TOO_EARLY":
                    return result
                last_error = "FAIL_NO_RENEW_BUTTON"
                continue

            renew_btn = page.ele('css:button[data-bs-target="#renew-modal"]')
            if not renew_btn:
                log("❌ 未找到续期按钮")
                last_error = "FAIL_NO_RENEW_BUTTON"
                continue

            # 点击按钮，打开弹窗
            log(">>> 点击 Renew 按钮（打开弹窗）...")
            renew_btn.click(by_js=True)
            time.sleep(2)

            # 等待弹窗显示
            modal = None
            for _ in range(10):
                candidate = page.ele('css:#renew-modal', timeout=1)
                if candidate:
                    try:
                        display = candidate.style('display')
                        if display and display != 'none':
                            modal = candidate
                            break
                    except Exception:
                        pass
                time.sleep(0.5)

            if not modal:
                log("❌ 弹窗未出现")
                last_error = "FAIL_MODAL_NOT_OPEN"
                continue

            log("✅ 弹窗已打开")

            # 等待 Altcha 控件加载，然后点击
            time.sleep(1)
            altcha_ok = click_and_wait_altcha(page, timeout=30)
            if not altcha_ok:
                log("⚠️ Altcha 验证未确认完成，仍尝试提交...")
                last_error = "FAIL_ALTCHA_TIMEOUT"

            # 找弹窗内的提交按钮
            confirm_btn = modal.ele('css:button[type="submit"].btn-primary', timeout=5)
            if not confirm_btn:
                confirm_btn = modal.ele('css:form button[type="submit"]', timeout=3)

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

            if result == "FAIL_OTHER":
                last_error = result
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

# ==================== 主入口 ====================

def job():
    accounts = load_accounts()
    if not accounts:
        return 1

    path_silk = download_silk()
    path_cf = download_cf_autoclick()

    trigger_source = os.environ.get("RUN_TRIGGER_SOURCE", "unknown")
    send_telegram_message(f"🚀 Katabump 续期任务开始\n触发方式: {trigger_source}\n账号数量: {len(accounts)}")

    result_lines = []
    has_failure = False

    for index, account in enumerate(accounts, start=1):
        status = renew_single_account(
            account["email"],
            account["password"],
            account["url"],
            path_silk,
            path_cf,
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
    final_message = f"📣 Katabump 续期任务结束\n触发方式: {trigger_source}\n\n{summary}"
    send_telegram_message(final_message)

    log("===== 任务汇总 =====")
    log(summary)
    return 1 if has_failure else 0

if __name__ == "__main__":
    sys.exit(job())
