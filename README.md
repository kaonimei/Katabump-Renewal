# Katabump-Renewal

基于 GitHub Actions + SeleniumBase 的 Katabump 自动化续期脚本。

## 项目说明

当前仓库核心文件：

- `/home/runner/work/Katabump-Renewal/Katabump-Renewal/main.py`：自动化脚本（登录、验证码处理、退出、Telegram 通知等逻辑）
- `/home/runner/work/Katabump-Renewal/Katabump-Renewal/.github/workflows/renew.yml`：GitHub Actions 定时任务

## 功能特性

- 支持多账号（通过一个环境变量传入多个 `email:password`）
- 自动处理 Cloudflare Turnstile（含重试）
- 支持 Telegram 执行结果通知
- 支持 GitHub Actions 定时执行和手动触发

## 环境变量

### 必需

- `KATABUMP_ACCOUNTS`

格式为逗号分隔的账号对，每个账号为 `email:password`：

```text
user1@example.com:pass1,user2@example.com:pass2
```

### 可选（Telegram 通知）

- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

如果未配置，脚本会自动跳过 Telegram 推送。
### 可选（代理）
- `NODE_LINK`
代理格式（确认在v2rayN里使用正常的节点）
NODE_LINK 支持以下任意一种代理协议的完整分享链接（不配置则直连）：

VLESS：vless://uuid@server:port?security=reality&sni=...&type=ws&...
VMess：vmess://base64encoded...
Trojan：trojan://password@server:port?sni=...&type=ws&...
tuic：tuic://uuid:password@server:port...
anytls：anytls://uuid@server:port...
hysteria2：hysteria2://base64@server:port...
SOCKS5：socks5://user:pass@server:port 或 socks://user:pass@server:port
注意事项
尽量添加一个干净的节点，以免过不了cf盾
## GitHub Actions 配置

1. 打开仓库 `Settings -> Secrets and variables -> Actions`
2. 添加上述环境变量为 Repository Secrets
3. 在 `Actions` 页面手动运行工作流，或等待定时触发

默认工作流文件：`/home/runner/work/Katabump-Renewal/Katabump-Renewal/.github/workflows/renew.yml`

## 本地运行（可选）

```bash
pip install seleniumbase requests
python3 /home/runner/work/Katabump-Renewal/Katabump-Renewal/main.py
```

## 注意事项

- 该脚本依赖浏览器自动化环境（CI 中建议使用 `xvfb-run`）
- 账号信息请仅通过 Secrets 配置，不要写入仓库
- 若页面结构变化，续期流程可能需要同步调整脚本
