# Focus Buddy

一款面向 Windows 用户的本地 AI 小猫专注伙伴。

写下这一轮要完成的目标，Focus Buddy 会推荐可能需要的软件和页面，帮你建立白名单；当你偏离任务时，小猫会用简短、幽默的方式提醒你。完成专注可以积累成长值、猫币和徽章，把 Luna 慢慢养大。

![Focus Buddy 小猫专注场景](pictures/focus.png)

## 主要功能

- **AI 理解目标**：使用本机 Ollama 分析“40 分钟完成 Python 作业”这类自然语言目标，并推荐相关工具。
- **断网也能使用**：模型未启动、超时或输出异常时，自动切换到本地场景数据库。
- **软件与网址白名单**：支持应用、进程、页面关键词和网站域名规则。
- **小猫桌面提醒**：走神时摇头或推翻杯子，完成后害羞庆祝。
- **宠物养成**：专注时长会累积成长值、猫币、经验、连续天数和徽章。
- **自定义宠物**：上传自己的猫、狗或其他宠物照片，在本机生成四个成长阶段。
- **声音花园**：支持本地 MP3、WAV、OGG 和 M4A，可按雨声、溪流、海岸等类型播放。
- **隐私优先**：不截屏、不读取按键，不上传宠物照片或专注记录。

## 下载与安装

前往 [Releases](https://github.com/miaoooow/Focus-Buddy/releases/latest) 下载最新版：

```text
FocusBuddyAI-Setup-3.0.0.exe
```

双击安装即可。程序只监听本机 `127.0.0.1`，会自动从 8765–8775 中选择一个空闲端口。

Windows 首次运行未签名应用时可能显示 SmartScreen 提示，请核对 Release 中的 SHA-256 校验值后再运行。

## 启用本机 AI

AI 功能不使用收费 API，需要提前安装 [Ollama](https://ollama.com/) 并下载模型：

```powershell
ollama pull qwen3.5:9b
ollama list
```

推荐模型是 `qwen3.5:9b`。配置较低的电脑也可以使用 `qwen3.5:4b`；如果没有模型，Focus Buddy 会自动使用内置场景库，计时、提醒、养成和白名单功能仍能正常工作。

## 快速开始

1. 打开 Focus Buddy。
2. 输入目标，例如“45 分钟完成高数作业第三章”。
3. 点击“帮我安排场景”。
4. 检查推荐的软件和页面，可直接勾选或手动补充。
5. 点击“开始专注”。
6. 完成后领取猫币和成长值。

输入目标时尽量包含“时长 + 具体成果”，例如：

```text
30分钟整理完今天的会议纪要
50分钟完成Python数据分析，并用Excel核对结果
25分钟修改简历，禁止刷B站和微博
```

## 精确识别网站

如果只想允许浏览器中的某个网站，需要加载项目附带的浏览器桥接：

1. Edge 打开 `edge://extensions`，Chrome 打开 `chrome://extensions`。
2. 开启“开发人员模式”。
3. 点击“加载解压缩的扩展”。
4. 选择安装目录中的 `browser_extension` 文件夹。
5. 刷新 Focus Buddy 页面，确认“网址识别桥接”显示已连接。

桥接只把当前活动标签页的域名和标题发送到本机 Focus Buddy，不上传完整网址、网页正文或浏览历史。只允许整个 Edge、Chrome 或 Firefox 时不需要安装扩展。

## 自定义宠物

在“成长记录”中上传 PNG、JPG 或 WebP 照片并输入名字。图片只在当前电脑处理，生成内容保存在：

```text
%LOCALAPPDATA%\FocusBuddyAI\custom_pets
```

可以在内置小猫和自定义宠物之间切换，也可以删除自己上传的宠物。

## 添加自己的声音

声音花园支持 MP3、WAV、OGG 和 M4A。安装版可从本机用户数据目录读取音频：

```text
%LOCALAPPDATA%\FocusBuddyAI\Musics
```

请只添加自己拥有或有权使用的音频文件。

## 常见问题

### 页面显示“Failed to fetch”

确认 Focus Buddy 主程序仍在运行，然后重新打开或刷新页面。不要只保留浏览器页面后关闭桌面程序。

### AI 一直显示离线

在 PowerShell 中检查：

```powershell
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

如果 Ollama 没有运行，重新启动 Ollama。AI 离线期间不会影响本地专注功能。

### 已添加网址却仍被提醒

确认浏览器桥接显示已连接，并将规则类型设为“网站域名”。可以输入 `example.com` 或粘贴完整网址，程序会匹配该域名及其子域名。

### 普通版和 AI 版能同时安装吗？

可以，两者使用不同的数据目录。不建议同时运行，因为浏览器桥接一次只会连接其中一个本地实例。

## 从源码运行

开发环境需要 Windows、Python 3.11+、PowerShell 和可选的 Ollama：

```powershell
git clone https://github.com/miaoooow/Focus-Buddy.git
cd Focus-Buddy
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

运行测试：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

## 隐私说明

- 只读取当前前台窗口的进程名和窗口标题。
- 不截屏、不录屏、不读取键盘输入。
- 浏览器桥接数据只在内存中短暂保留。
- 宠物照片、成长记录、白名单记忆和专注历史保存在本机。
- 关闭程序后即停止监测，不安装后台系统服务。
- AI 请求只发送给本机 Ollama，不调用云端付费 API。

