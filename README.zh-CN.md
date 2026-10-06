# Codex Token HUD

[English](README.md) | [简体中文](README.zh-CN.md)

在 Windows 上，为当前 Codex Desktop 对话显示模型、输出 token 速率和输入缓存命中率。状态条可拖拽、调整大小，默认显示在窗口底部。

![状态条实际截图](docs/images/hud.png)

**当前版本：1.2.0-beta.1，Windows x64 测试版。** 本项目为独立工具，与 OpenAI 无隶属关系，读取本地统计，不修改 Codex 安装文件。

## 直接使用

1. 从仓库 Releases 下载 `CodexTokenHud-1.2.0-beta.1-win-x64.zip`。
2. **完整解压**到自己的文件夹，保留 EXE、`metrics.py` 和 `python/` 的相对位置。
3. 双击 `CodexTokenHud.exe`，在 Codex Desktop 中打开本地对话。

便携包自带独立 Python，无需自行安装 Python 或 pip 包。目标系统为 Windows 10/11 x64，需有 .NET Framework 4.8。程序请求当前用户可获得的最高权限，以读取管理员模式 Codex 的无障碍窗口信息；管理员账户可能看到 Windows UAC 提示。测试版 EXE 尚未签名。

拖动状态条中间可移动，拖动边缘或角落可缩放。右键状态条或托盘图标，可以立即刷新、恢复底部布局、设置登录启动或退出。状态条随当前 Codex 窗口显示，退出后后台采集器一起结束。

自动启动为可选操作：在管理员 PowerShell 中运行 `Install.ps1`，或使用右键菜单。安装脚本创建桌面快捷方式和当前用户的登录启动任务。`Uninstall.ps1` 只移除指向当前副本的启动任务和快捷方式，并保留布局数据。临时使用只需双击 EXE。

## 统计口径

| 项目 | 含义 |
| --- | --- |
| 模型 | 当前本地对话最近记录的模型 |
| tok/s | 最近一次已完成模型响应的输出 token ÷ 生成时间，推理 token 只计一次 |
| 缓存 | 同一次响应的缓存输入 token ÷ 全部输入 token |
| 更新时间 | 统计产生时间；新一轮待统计或数据过期时隐藏旧数值 |
| 本对话周额度 | 暂无数据；本地记录不提供按对话归属的周额度扣减值或额度总量 |

**速率是一次响应的平均值，计数在响应完成后到达。** 有流式条目时间时从最早的模型条目开始计时；缺少该时间时使用请求区间，包含首 token 等待。日志边界允许时排除工具执行时间。悬停查看计时依据和完整统计时间。

新一轮尚无计数、模型切换、统计超过 15 分钟、采集器失联时显示 `--`。缓存比例衡量输入 token 的缓存占比，不代表缓存请求成功率。不能把 token 数、API 价格或账号整体已用百分比当作“当前对话消耗的周额度百分比”，本工具不估算该值。

后台每 100 毫秒检查新记录，至少每秒发布一次心跳；界面每 150 毫秒刷新，约每 350 毫秒检查当前对话。Codex 写入统计本身可能更晚。

## 本地数据与设置

- 只读打开兼容的 `state_*.sqlite`，查询对话元数据，读取所选对话最近的 JSONL 日志。解析过程会经过消息文本，但不导出或另存聊天正文。
- 程序运行时没有网络请求、遥测、凭证读取或账号额度查询，也不写入 Codex 数据。开发者的打包脚本会从 python.org 下载 Python 并校验固定 SHA256。
- 布局和派生统计保存在 `%LOCALAPPDATA%\CodexTokenHud`。其中包含对话标题、ID 和本机路径，**不要上传这个目录**。
- Codex 数据目录默认 `%USERPROFILE%\.codex`，支持 `CODEX_HOME`。
- 如需覆盖 Python 或 Codex 目录，将 `settings.example.json` 复制为 EXE 旁或数据目录中的 `settings.json`，设置 `pythonw`、`codex_home`。数据目录配置优先；相对 Python 路径以 EXE 目录为起点。不配置时优先使用便携包内 Python，其次搜索 PATH。
- 开发时可用 `CODEX_TOKEN_HUD_HOME` 隔离数据目录。旧版 EXE 旁的布局会在首次运行时复制到新位置。

## 兼容性与排错

已在 Windows、Codex Desktop 26.930.7945、150% 缩放下验证。当前通过无障碍标题栏和本地对话标题匹配，支持中文、英文标题栏；其他语言和未来布局尚未验证。同名对话需要右键明确选择，不会猜测。Codex 更新后，内部布局变化可能需要适配。

本版本支持有可读日志的**本地桌面对话**。CLI/VS Code 窗口、纯云端对话、macOS、Linux 和 ARM64 原生版本尚不支持。只有托盘图标时，请将本地 Codex 对话窗口切到前台，检查工具和 Codex 的权限是否匹配。新对话或闲置对话可能没有当前样本；数据库不兼容或日志不可读会显示相应状态。

更多验证边界见 [验证记录](docs/VALIDATION.md)、[隐私说明](PRIVACY.md)、[更新日志](CHANGELOG.md)。提交问题时只提供脱敏或人工构造的样例，请勿上传真实会话日志、认证文件或凭证。

## 开发与构建

从源码仓库构建，需要 Windows x64、Windows 自带的 .NET Framework 4.x 编译器，以及 Python 3.10+。后台仅使用标准库。便携包用户不需要构建源码。

```powershell
.\Test.ps1
.\Build.ps1
.\Start.ps1
```

Python 不在 PATH 时使用 `Build.ps1 -PythonExecutable 'C:\path\to\python.exe'`，它会生成不入库的本地配置。运行中的 EXE 重新编译前先执行 `Stop.ps1`；也可 `Build.ps1 -OutputDirectory build\app` 编译到其他目录。

```powershell
.\Package.ps1
```

打包会运行测试、编译、按白名单复制文件、下载并验证固定 Python 便携运行时，再在不依赖系统 Python 的条件下验证解压后的发布包。输出位于 `dist/`，不入 Git。参见 [贡献指南](CONTRIBUTING.md) 和 [发布步骤](docs/RELEASING.md)。

GitHub Actions 配有 Windows 下 Python 3.10 / 3.12 / 3.14 的测试与构建，以及版本标签触发的**草稿预发布**流程。[首次托管 CI](https://github.com/drkang7/codex-token-hud/actions/runs/37492761938) 已于 2026-10-07 通过全部三组测试和便携包构建。实际 Codex 窗口的验证范围另见验证记录。

## 许可证

项目采用 [MIT](LICENSE)。便携包包含的 CPython 使用其原有许可，完整保留在 `python/LICENSE.txt`，见 [第三方说明](THIRD_PARTY_NOTICES.md)。
