# Katabump-Renewal
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

 🚀 部署指南
第一步：准备源码
将本项目的所有文件上传到你的 GitHub 仓库。
第二步：设置 GitHub Secrets（关键）
进入你的 GitHub 仓库，依序点击：
Settings -> Secrets and variables -> Actions -> New repository secret

请新增以下 3 个必需的密钥变量：
KB_EMAIL——邮箱
KB_PASSWORD———密码
KB_RENEW_URL——续期链接

第三步：启用和测试
 自动运行：配置完成后，脚本将按照 ⁠renew.yml⁠ 中的设置（默认每2天）自动运行。
 手动测试：
1. 点击仓库上方的 Actions 标签。
2. 在左侧选择 Katabump 自动更新 工作流。
3. 点击右侧的 Run workflow 下拉按钮，再点击绿色的 Run workflow。
4. 等待运行完成，成功后日志将显示 ⁠🎉🎉🎉 续期成功！任务完成。⁠。
常见问题：
 ⁠login_fail.jpg⁠：登录失败（可能是密码错误或被验证码拦截）。
 ⁠no_renew.jpg⁠：未找到续期按钮（可能是服务器暂不需要续期，或页面加载较慢）。
 ⁠crash.jpg⁠：脚本崩溃报错截图。
