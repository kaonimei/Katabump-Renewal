import os
import sys
import time
import requests
import zipfile
import io
import datetime
import re
from DrissionPage import ChromiumPage, ChromiumOptions

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
    """
    【插件1】Silk Privacy Pass
    作用：辅助通过全屏盾，增加信任度
    """
    extract_dir = "extensions/silk_ext"
    if os.path.exists(extract_dir): return os.path.abspath(extract_dir)
    
    log(">>> [插件1] 正在下载 Silk Privacy Pass...")
    url = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3Dajhmfdgkijocedmfjonnpjfojldioehi%26uc"
    if download_and_extract_zip(url, extract_dir, "插件1"):
        return os.path.abspath(extract_dir)
    return None

def download_cf_autoclick():
    """
    【插件2】CF-AutoClick
    作用：自动点击验证码复选框
    """
    extract_root = "extensions/cf_autoclick_root"
    
    # 下载逻辑
    if not os.path.exists(extract_root):
        log(">>> [插件2] 正在下载 CF-AutoClick (Master)...")
        url = "https://codeload.github.com/tenacious6/cf-autoclick/zip/refs/heads/master"
        if not download_and_extract_zip(url, extract_root, "插件2"):
            return None

    # 智能寻址：寻找 manifest.json
    for root, dirs, files in os.walk(extract_root):
        if "manifest.json" in files:
            log(f"✅ [插件2] 路径锁定: {os.path.basename(root)}")
            return os.path.abspath(root)
            
    return None

# ==================== 核心逻辑 ====================

def pass_full_page_shield(page):
    """处理全屏盾"""
    for _ in range(3):
        if "just a moment" in page.title.lower():
            log("--- [门神] 全屏盾出现，等待双插件配合过盾...")
            time.sleep(3)
        else:
            return True
    return False

def manual_click_checkbox(modal):
    """【补刀逻辑】手动点击 checkbox"""
    log(">>> [补刀] 检查是否需要手动点击...")
    
    # 1. iframe 内部扫描
    iframe = modal.ele('css:iframe[src*="cloudflare"], iframe[src*="turnstile"]', timeout=3)
    if iframe:
        checkbox = iframe.ele('css:input[type="checkbox"]', timeout=2)
        if checkbox:
            log(">>> [补刀] 🎯 在 iframe 里点击 Checkbox！")
            checkbox.click(by_js=True)
            return True
        else:
            # 没 checkbox 就点 iframe 中心
            log(">>> [补刀] 点击 iframe 主体...")
            iframe_body = iframe.ele('tag:body', timeout=1)
            if iframe_body:
                iframe_body.click(by_js=True)
                return True
            iframe.click(by_js=True)
            return True
            
    # 2. 外部扫描
    checkbox = modal.ele('css:input[type="checkbox"]', timeout=1)
    if checkbox:
        log(">>> [补刀] 🎯 在外部点击 Checkbox！")
        checkbox.click(by_js=True)
        return True
        
    log(">>> [补刀] 未找到元素 (可能插件已完成点击)")
    return False

def analyze_page_alert(page):
    """解析结果"""
    log(">>> [系统] 检查结果...")
    
    danger = page.ele('css:.alert.alert-danger')
    if danger and danger.states.is_displayed:
        text = danger.text
        log(f"⬇️ 红色提示: {text}")
        if "can't renew" in text.lower():
            match = re.search(r'\(in (\d+) day', text)
            days = match.group(1) if match else "?"
            log(f"✅ [结果] 未到期 (等待 {days} 天)")
            return "SUCCESS_TOO_EARLY"
        elif "captcha" in text.lower():
            return "FAIL_CAPTCHA"
        return "FAIL_OTHER"

    success = page.ele('css:.alert.alert-success')
    if success and success.states.is_displayed:
        log(f"⬇️ 绿色提示: {success.text}")
        log("🎉 [结果] 续期成功！")
        return "SUCCESS"

    return "UNKNOWN"

# ==================== 主程序 ====================
def job():
    page = None
    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        
        missing_env = [name for name, value in {
            "KB_EMAIL": email,
            "KB_PASSWORD": password,
            "KB_RENEW_URL": target_url
        }.items() if not value]
        if missing_env:
            log(f"❌ 配置缺失: {', '.join(missing_env)}")
            return 1

        # 1. 准备插件
        path_silk = download_silk()
        path_cf = download_cf_autoclick()
        
        # 2. 配置浏览器
        co = ChromiumOptions()
        co.set_argument('--headless=new')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        # 3. 同时挂载两个插件
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

        # Step 1: 登录
        log(">>> [Step 1] 登录...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)

        if page.ele('css:input[name="email"]'):
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button#submit').click()
            try:
                page.wait.url_change('login', exclude=True, timeout=20)
            except Exception:
                log("⚠️ 登录后页面跳转超时，继续检查后续页面状态...")
        
        # Step 2: 循环重试
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            log(f"\n🚀 [Step 2] 尝试续期 (第 {attempt} 次)...")
            page.get(target_url)
            pass_full_page_shield(page)
            
            renew_btn = None
            for _ in range(5):
                renew_btn = page.ele('css:button[data-bs-target="#renew-modal"]')
                if renew_btn and renew_btn.states.is_displayed: break
                time.sleep(1)

            if renew_btn:
                log(">>> 点击 Renew 按钮...")
                renew_btn.click(by_js=True)
                
                log(">>> 等待弹窗...")
                modal = page.ele('css:.modal-content', timeout=10)
                
                if modal:
                    log(">>> [操作] 弹窗出现，等待双插件干活 (10s)...")
                    
                    # 确保验证码加载，给插件目标
                    page.wait.ele_displayed('css:iframe[src*="cloudflare"], iframe[src*="turnstile"]', timeout=8)
                    
                    # 1. 插件自动处理时间
                    time.sleep(10)
                    
                    # 2. 脚本手动补刀 (如果插件漏了)
                    manual_click_checkbox(modal)
                    
                    # 3. 缓冲
                    time.sleep(3)
                    
                    confirm_btn = modal.ele('css:button[type="submit"].btn-primary')
                    if confirm_btn:
                        log(">>> 点击 Confirm...")
                        confirm_btn.click(by_js=True)
                        log(">>> 等待响应 (5s)...")
                        time.sleep(5)
                        
                        result = analyze_page_alert(page)
                        
                        if result == "SUCCESS" or result == "SUCCESS_TOO_EARLY":
                            break 
                        
                        if result == "FAIL_CAPTCHA":
                            log("⚠️ 验证未通过，刷新重试...")
                            time.sleep(2)
                            continue
                    else:
                        log("❌ 找不到确认按钮")
                else:
                    log("❌ 弹窗未出")
            else:
                log("⚠️ 未找到按钮，检查状态...")
                result = analyze_page_alert(page)
                if result == "SUCCESS_TOO_EARLY":
                    break
            
            if attempt == max_retries:
                log("❌ 最大重试次数已达，任务终止。")
                return 1

    except Exception as e:
        log(f"❌ 异常: {e}")
        return 1
    finally:
        if page:
            page.quit()
    return 0

if __name__ == "__main__":
    sys.exit(job())
