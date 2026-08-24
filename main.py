import os
import sys
import time
import requests
import json
import re
import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 状态码 ====================
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

# ==================== 核心逻辑 ====================

def wait_for_no_challenge(page, timeout=60):
    log(f">>> 等待 CF 全屏盾 (最多 {timeout}s)...")
    for _ in range(timeout):
        title = page.title.lower()
        if "just a moment" not in title and "checking" not in title:
            return True
        time.sleep(1)
    return False

def do_login(page, email, password):
    log(">>> 打开登录页...")
    page.get('https://dashboard.katabump.com/auth/login')
    wait_for_no_challenge(page, timeout=30)

    email_input = page.ele('css:input[name="email"]')
    if not email_input:
        log("❌ 未找到登录表单")
        return False

    email_input.input(email)
    page.ele('css:input[name="password"]').input(password)

    log(">>> 等待 Turnstile 自动验证...")
    time.sleep(60)  # 给插件足够时间处理

    log(">>> 提交登录...")
    page.ele('css:button#submit').click()
    time.sleep(10)

    current_url = page.url
    log(f"  登录后 URL: {current_url}")

    if 'error=captcha' in current_url:
        log("❌ Turnstile 验证未通过")
        return False

    log(">>> 访问 dashboard 验证...")
    page.get('https://dashboard.katabump.com/dashboard')
    time.sleep(5)
    wait_for_no_challenge(page, timeout=30)

    if 'dashboard' in page.url.lower() and 'login' not in page.url.lower():
        log("✅ 登录成功")
        return True

    log(f"❌ 登录失败，当前 URL: {page.url}")
    return False

def click_altcha(page):
    log(">>> 处理 Altcha 验证...")
    try:
        page.wait.ele_displayed('tag:altcha-widget', timeout=10)
        time.sleep(2)

        log(">>> 点击 Altcha...")
        page.ele('tag:altcha-widget').click(by_js=True)

        log(">>> 等待 Altcha 完成...")
        for _ in range(30):
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
                log(f"✅ Altcha 完成 (等待 {_}s)")
                return True
            time.sleep(1)
        return False
    except Exception as e:
        log(f"⚠️ Altcha 处理失败: {e}")
        return False

def analyze_result(page):
    log(">>> 检查结果...")
    danger = page.ele('css:.alert.alert-danger')
    if danger and danger.states.is_displayed:
        text = danger.text
        log(f"⬇️ 红色提示: {text}")
        if "can't renew" in text.lower() or "cannot renew" in text.lower():
            match = re.search(r'\(in (\d+) day', text)
            days = match.group(1) if match else "?"
            log(f"✅ 未到期 (等待 {days} 天)")
            return "SUCCESS_TOO_EARLY"
        return "FAIL_OTHER"

    success = page.ele('css:.alert.alert-success')
    if success and success.states.is_displayed:
        log(f"⬇️ 绿色提示: {success.text}")
        log("🎉 续期成功！")
        return "SUCCESS"

    return "UNKNOWN"

def renew_single_account(email, password, target_url, account_index, total_accounts):
    page = None
    last_error = None

    try:
        log(f"================ 账号 {account_index}/{total_accounts} 开始 ================")

        co = ChromiumOptions()
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # 挂载插件（Silk + CF-AutoClick）
        plugin_count = 0
        if os.path.exists("extensions/silk_ext"):
            co.add_extension("extensions/silk_ext")
            plugin_count += 1
        if os.path.exists("extensions/cf_autoclick_root"):
            co.add_extension("extensions/cf_autoclick_root")
            plugin_count += 1
        log(f">>> 已挂载插件数量: {plugin_count}")

        page = ChromiumPage(co)
        page.set.timeouts(30)

        # Step 1: 登录
        log(">>> [Step 1] 登录...")
        if not do_login(page, email, password):
            return "FAIL_LOGIN_FAILED"

        # Step 2: 续期
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            log(f"\n🚀 [Step 2] 尝试续期 (第 {attempt}/{max_retries} 次)...")
            page.get(target_url)
            time.sleep(5)
            wait_for_no_challenge(page, timeout=30)

            renew_btn = page.ele('css:button[data-bs-target="#renew-modal"]')
            if not renew_btn or not renew_btn.states.is_displayed:
                log("❌ 未找到续期按钮")
                last_error = "FAIL_NO_RENEW_BUTTON"
                continue

            log(">>> 点击 Renew 按钮...")
            renew_btn.click(by_js=True)
            time.sleep(3)

            modal = page.ele('css:#renew-modal', timeout=10)
            if not modal:
                log("❌ 弹窗未出现")
                last_error = "FAIL_MODAL_NOT_OPEN"
                continue

            click_altcha(page)
            time.sleep(3)

            confirm_btn = modal.ele('css:button[type="submit"].btn-primary', timeout=5)
            if not confirm_btn:
                last_error = "FAIL_NO_SUBMIT_BUTTON"
                continue

            log(">>> 点击弹窗内 Renew 按钮...")
            confirm_btn.click(by_js=True)
            time.sleep(8)

            result = analyze_result(page)
            log(f">>> 本次结果: {result}")

            if result in ("SUCCESS", "SUCCESS_TOO_EARLY"):
                return result
            if result == "FAIL_CAPTCHA":
                last_error = result
                time.sleep(3)
                continue
            last_error = result if result else "FAIL_OTHER"
            time.sleep(3)

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

# ==================== 账号与通知 ====================

def load_accounts():
    accounts_json = os.environ.get("KB_ACCOUNTS_JSON", "").strip()
    if not accounts_json:
        log("❌ 未配置 KB_ACCOUNTS_JSON")
        return None
    try:
        data = json.loads(accounts_json)
        if not isinstance(data, list):
            log("❌ KB_ACCOUNTS_JSON 必须是数组")
            return None
        accounts = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                log(f"❌ 第 {index} 个账号配置格式错误")
                return None
            email = str(item.get("email", "")).strip()
            password = str(item.get("password", "")).strip()
            url = str(item.get("url", "")).strip()
            if not all([email, password, url]):
                log(f"❌ 第 {index} 个账号缺少字段")
                return None
            accounts.append({"email": email, "password": password, "url": url})
        return accounts
    except json.JSONDecodeError as e:
        log(f"❌ JSON 解析失败: {e}")
        return None

def send_telegram_message(text):
    token = os.environ.get("TG_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TG_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15
        )
        return resp.status_code == 200
    except Exception:
        return False

def job():
    accounts = load_accounts()
    if not accounts:
        return 1

    trigger = os.environ.get("RUN_TRIGGER_SOURCE", "unknown")
    send_telegram_message(f"🚀 Katabump 续期开始\n触发: {trigger}\n账号数: {len(accounts)}")

    result_lines = []
    has_failure = False

    for index, account in enumerate(accounts, start=1):
        status = renew_single_account(
            account["email"],
            account["password"],
            account["url"],
            index,
            len(accounts)
        )

        readable = RESULT_CODES.get(status, status)
        if status in ("SUCCESS", "SUCCESS_TOO_EARLY"):
            status_text = f"✅ {readable}"
        else:
            status_text = f"❌ {readable}"
            has_failure = True

        email_hint = account["email"][:3] + "***"
        result_lines.append(f"{index}. {email_hint}: {status_text}")

    summary = "\n".join(result_lines)
    send_telegram_message(f"📣 Katabump 续期结束\n触发: {trigger}\n\n{summary}")

    log("===== 任务汇总 =====")
    log(summary)
    return 1 if has_failure else 0

if __name__ == "__main__":
    sys.exit(job())
