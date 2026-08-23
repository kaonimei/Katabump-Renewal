# Katabump-Renewal
Katabump续期脚本
Katabump 自动化续约脚本 (GitHub Actions 版本)
这是一个运行在 GitHub Actions 上的自动化脚本，用于自动续期 Katabump 面板上的服务器。
针对 Cloudflare 验证进行了深度优化，能够自动下载并配置 Silk Privacy Pass Client 插件，实现零人工干预的自动过盾和续期。
续期。
✨ 功能特性
 🛡️ 自动过盾：脚本启动时自动从官方下载 Silk 隐私通行证客户端插件并挂载，有效通过 Cloudflare 5秒盾。
 🔑 账号直连：直接使用 Katabump 邮箱 + 密码登录，无需提取复杂的 Token。
 🔗 灵活配置：通过 GitHub Secrets 配置目标服务器链接，更换服务器或账号时无需修改源码。
 🤖 全自动流程：下载插件 -> 登录 -> 进入服务器 -> 点击续期 -> 处理弹窗 -> 确认。
 📸 故障截图：若执行失败，会自动生成截图并保存至 GitHub Actions Artifacts（人工制品），方便排查问题。
 ⏰ 定时运行：默认每2天自动执行一次续期任务。
