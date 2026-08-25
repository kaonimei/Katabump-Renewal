# Katabump-Renewal

基于 GitHub Actions + SeleniumBase 的 Katabump 自动续期脚本。

## 项目结构

- `/home/runner/work/Katabump-Renewal/Katabump-Renewal/main.py`：登录、验证、续期、Telegram 通知主逻辑
- `/home/runner/work/Katabump-Renewal/Katabump-Renewal/proxy_handler.py`：解析 `PROXY_URL` 并生成 sing-box 配置
- `/home/runner/work/Katabump-Renewal/Katabump-Renewal/.github/workflows/renew.yml`：定时与手动执行工作流

## 环境变量

### 必需（二选一）

1. 多账号（推荐）
   - `USERS_JSON`
   - 格式：
     ```json
     [{"username":"user1@example.com","password":"pass1"},{"email":"user2@example.com","password":"pass2"}]
     ```
2. 单账号
   - `KATABUMP_EMAIL`
   - `KATABUMP_PASSWORD`

### 可选

- `PROXY_URL`：代理分享链接（配置后工作流自动启用本地代理 `http://127.0.0.1:8080`）
- `TG_BOT_TOKEN`：Telegram Bot Token
- `TG_CHAT_ID`：Telegram Chat ID
- `NODE_ATTEMPTS`：每个账号失败后切换代理节点的最大重试次数，默认 `3`

## GitHub Actions 使用

1. 进入仓库 `Settings -> Secrets and variables -> Actions`
2. 配置上述 Secrets（至少配置 `USERS_JSON` 或单账号）
3. 在 `Actions` 页面手动触发 `Katabump Auto Renew`，或等待定时任务执行

## 本地运行

```bash
pip install seleniumbase requests
python3 /home/runner/work/Katabump-Renewal/Katabump-Renewal/main.py
```

## 注意事项

- 未配置 `PROXY_URL` 时会直连运行；配置后会先启动并检测 sing-box 代理
- Telegram 变量未配置时，会自动跳过通知，不影响续期流程
- 页面结构变化或验证方式变化时，可能需要同步调整脚本
