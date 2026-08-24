import os
import sys
import time
import requests
import json
import re
import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

def wait_for_no_challenge(driver, timeout=60):
    """等待 CF 全屏盾消失"""
    log(f">>> 等待 CF 全屏盾 (最多 {timeout}s)...")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            title = driver.title.lower()
            if "just a moment" not in title and "checking" not in title:
                return True
        except Exception:
            pass
        time.sleep(2)
    log("⚠️ 全屏盾超时，继续执行...")
    return False

def do_login(driver, email, password):
    """执行登录并验证"""
    log(">>> 打开登录页...")
    driver.get('https://dashboard.katabump.com/auth/login')
    time.sleep(3)
    wait_for_no_challenge(driver, timeout=30)
    
    try:
        # 填写表单
        log(">>> 填写登录信息...")
        email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="email"]'))
        )
        email_input.send_keys(email)
        driver.find_element(By.CSS_SELECTOR, 'input[name="password"]').send_keys(password)
        
        # 等待 Turnstile 自动验证
        log(">>> 等待 Turnstile 自动验证 (60s)...")
        time.sleep(60)
        
        # 提交
        log(">>> 提交登录...")
        driver.find_element(By.CSS_SELECTOR, 'button#submit').click()
        
        # 等待跳转
        time.sleep(10)
        current_url = driver.current_url
        log(f"  登录后 URL: {current_url}")
        
        # 检查是否有错误
        if 'error=captcha' in current_url:
            log("❌ Turnstile 验证未通过")
            return False
        
        # 验证 session
        log(">>> 访问 dashboard 验证...")
        driver.get('https://dashboard.katabump.com/dashboard')
        time.sleep(5)
        wait_for_no_challenge(driver, timeout=30)
        
        if 'dashboard' in driver.current_url.lower() and 'login' not in driver.current_url.lower():
            log("✅ 登录成功")
            return True
        else:
            log(f"❌ 登录失败，当前 URL: {driver.current_url}")
            return False
            
    except Exception as e:
        log(f"❌ 登录异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def click_altcha(driver):
    """点击并等待 Altcha 验证"""
    log(">>> 处理 Altcha 验证...")
    try:
        # 等待 altcha-widget 出现
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'altcha-widget'))
        )
        time.sleep(2)
        
        # 点击 altcha 触发 PoW
        log(">>> 点击 Altcha...")
        success = driver.execute_script("""
            try {
                const widget = document.querySelector('#renew-modal altcha-widget');
                if (!widget) return false;
                widget.click();
                return true;
            } catch (e) {
                return false;
            }
        """)
        
        if success:
            log("✅ Altcha 已点击")
        else:
            log("⚠️ Altcha 点击失败，尝试直接查找 input...")
        
        # 等待验证完成
        log(">>> 等待 Altcha PoW 完成 (最多 30s)...")
        for i in range(30):
            val = driver.execute_script("""
                try {
                    const w = document.querySelector('#renew-modal altcha-widget');
                    if (!w) return '';
                    const inp = w.querySelector('input[name="altcha"]');
                    if (inp && inp.value) return inp.value;
                    if (w.shadowRoot) {
                        const sinp = w.shadowRoot.querySelector('input[name="altcha"]');
                        if (sinp && sinp.value) return sinp.value;
                    }
                    return '';
                } catch (e) {
                    return '';
                }
            """)
            if val:
                log(f"✅ Altcha 验证完成 (等待了 {i}s)")
                return True
            time.sleep(1)
        
        log("⚠️ Altcha 超时，尝试继续提交...")
        return False
        
    except Exception as e:
        log(f"⚠️ Altcha 处理失败: {e}")
        return False

def analyze_result(driver):
    """分析续期结果"""
    log(">>> 检查结果...")
    try:
        # 检查红色警告
        dangers = driver.find_elements(By.CSS_SELECTOR, '.alert.alert-danger')
        for alert in dangers:
            if alert.is_displayed():
                text = alert.text
                log(f"⬇️ 红色提示: {text}")
                if "can't renew" in text.lower() or "cannot renew" in text.lower():
                    match = re.search(r'\(in (\d+) day', text)
                    days = match.group(1) if match else "?"
                    log(f"✅ 未到期 (等待 {days} 天)")
                    return "SUCCESS_TOO_EARLY"
                return "FAIL_OTHER"
        
        # 检查绿色成功
        successes = driver.find_elements(By.CSS_SELECTOR, '.alert.alert-success')
        for alert in successes:
            if alert.is_displayed():
                log(f"⬇️ 绿色提示: {alert.text}")
                log("🎉 续期成功！")
                return "SUCCESS"
        
        return "UNKNOWN"
    except Exception as e:
        log(f"⚠️ 结果检查异常: {e}")
        return "UNKNOWN"

# ==================== 主续期逻辑 ====================

def renew_single_account(email, password, target_url, account_index, total_accounts):
    driver = None
    last_error = None
    
    try:
        log(f"================ 账号 {account_index}/{total_accounts} 开始 ================")
        
        # 创建 undetected driver
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        log(">>> 启动浏览器...")
        driver = uc.Chrome(
            options=options,
            driver_executable_path='/usr/local/bin/chromedriver',
            use_subprocess=True
        )
        driver.set_page_load_timeout(60)
        
        # Step 1: 登录
        log(">>> [Step 1] 登录...")
        if not do_login(driver, email, password):
            return "FAIL_LOGIN_FAILED"
        
        # Step 2: 续期
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            log(f"\n🚀 [Step 2] 尝试续期 (第 {attempt}/{max_retries} 次)...")
            log(f">>> 访问续期页: {target_url}")
            driver.get(target_url)
            time.sleep(5)
            wait_for_no_challenge(driver, timeout=30)
            
            current_url = driver.current_url
            log(f"  当前 URL: {current_url}")
            
            # 检查是否被踢回登录页
            if 'login' in current_url.lower():
                log("⚠️ 被踢回登录页，重新登录...")
                if not do_login(driver, email, password):
                    last_error = "FAIL_LOGIN_FAILED"
                    continue
                driver.get(target_url)
                time.sleep(5)
                current_url = driver.current_url
                if 'login' in current_url.lower():
                    log("❌ 重新登录后仍被踢回")
                    last_error = "FAIL_LOGIN_FAILED"
                    continue
            
            # 查找续期按钮
            log(">>> 查找续期按钮...")
            try:
                renew_btn = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-bs-target="#renew-modal"]'))
                )
                log("✅ 找到续期按钮")
            except Exception:
                log("❌ 未找到续期按钮，检查页面状态...")
                result = analyze_result(driver)
                if result == "SUCCESS_TOO_EARLY":
                    return result
                last_error = "FAIL_NO_RENEW_BUTTON"
                continue
            
            # 点击按钮打开弹窗
            log(">>> 点击 Renew 按钮...")
            driver.execute_script("arguments[0].click();", renew_btn)
            time.sleep(3)
            
            # 等待弹窗
            try:
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '#renew-modal'))
                )
                log("✅ 弹窗已打开")
            except Exception:
                log("❌ 弹窗未出现")
                last_error = "FAIL_MODAL_NOT_OPEN"
                continue
            
            # 处理 Altcha
            click_altcha(driver)
            time.sleep(3)
            
            # 提交
            log(">>> 点击弹窗内 Renew 按钮...")
            try:
                submit_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '#renew-modal button[type="submit"].btn-primary'))
                )
                driver.execute_script("arguments[0].click();", submit_btn)
                log(">>> 等待响应 (8s)...")
                time.sleep(8)
            except Exception as e:
                log(f"❌ 提交失败: {e}")
                last_error = "FAIL_NO_SUBMIT_BUTTON"
                continue
            
            # 检查结果
            result = analyze_result(driver)
            log(f">>> 本次结果: {result} ({RESULT_CODES.get(result, result)})")
            
            if result in ("SUCCESS", "SUCCESS_TOO_EARLY"):
                return result
            
            if result == "FAIL_CAPTCHA":
                log("⚠️ 验证码未通过，重试...")
                last_error = result
                time.sleep(3)
                continue
            
            last_error = result if result else "FAIL_OTHER"
            time.sleep(3)
        
        log("❌ 最大重试次数已达")
        return last_error or "FAIL_MAX_RETRY"
        
    except Exception as e:
        log(f"❌ 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return "FAIL_EXCEPTION"
    finally:
        if driver:
            try:
                driver.quit()
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

# ==================== 主入口 ====================

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
