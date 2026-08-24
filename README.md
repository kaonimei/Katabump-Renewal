# Katabump-Renewal
Katabump 自动化续约脚本 (GitHub Actions 版本)
这是一个运行在 GitHub Actions 上的自动化脚本，用于自动续期 Katabump 面板上的服务器。
针对 Cloudflare 验证进行了优化，支持可选的 CapSolver Turnstile 自动解题，并保留浏览器侧兜底流程。
续期。
✨ 功能特性
 🛡️ 自动过盾：支持可选 CapSolver Turnstile token 注入方案，失败时自动回退到页面轮询与补刀流程。
👥 多账号续期：支持单账号环境变量，也支持 JSON 数组格式的多账号配置。
🔔 Telegram 通知：任务开始/结束自动推送执行结果到 TG。
📲 TG 手动触发：支持通过 `repository_dispatch` 事件由 TG Bot 间接触发执行。
🤖 全自动流程：下载插件 -> 登录 -> 进入服务器 -> 点击续期 -> 处理弹窗 -> 确认。
⏰ 定时运行：默认每天自动执行一次续期任务。

 🚀 部署指南
第一步：准备源码
将本项目的所有文件上传到你的 GitHub 仓库。
第二步：设置 GitHub Secrets（关键）
进入你的 GitHub 仓库，依序点击：
Settings -> Secrets and variables -> Actions -> New repository secret

请新增以下密钥变量：

必需（推荐，多账号）：
- `KB_ACCOUNTS_JSON`

示例（JSON 数组）：
```json
[
  {
    "email": "user1@example.com",
    "password": "password123",
    "url": "https://dashboard.katabump.com/renew?id=xxx"
  },
  {
    "email": "user2@example.com",
    "password": "password456",
    "url": "https://dashboard.katabump.com/renew?id=yyy"
  }
]
```

兼容（旧版单账号，可不填 JSON 时使用）：
- `KB_EMAIL`
- `KB_PASSWORD`
- `KB_RENEW_URL`

Telegram 通知：
- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

可选（推荐，Turnstile 稳定性增强）：
- `CAPSOLVER_API_KEY`

第三步：启用和测试
 自动运行：配置完成后，脚本将按照 ⁠renew.yml⁠ 中的设置（默认每天）自动运行。
 手动测试：
1. 点击仓库上方的 Actions 标签。
2. 在左侧选择 Katabump 自动更新 工作流。
3. 点击右侧的 Run workflow 下拉按钮，再点击绿色的 Run workflow。
4. 等待运行完成，成功后日志将显示 ⁠🎉🎉🎉 续期成功！任务完成。⁠

通过 TG 手动触发（间接）：
1. 让你的 TG Bot 或中间服务调用 GitHub API 发送 `repository_dispatch`。
2. `event_type` 使用 `tg_manual_renew`。
3. 触发后该工作流会立即执行，并发送 TG 结果通知。

常见问题：
 ⁠login_fail.jpg⁠：登录失败（可能是密码错误或被验证码拦截）。
 ⁠no_renew.jpg⁠：未找到续期按钮（可能是服务器暂不需要续期，或页面加载较慢）。
 ⁠crash.jpg⁠：脚本崩溃报错截图。
