# Compress

Compress 是一个基于 PySide6 的通用代码打包工具，提供图形界面来帮助开发者把 Python、C#、Node.js、Java 项目以及网页文件夹打包或转换为可分发产物。项目内置中英文界面，适合快速生成桌面程序、Android Buildozer 工程、Android WebView 工程，以及常见语言生态的发布命令。

## 功能特性

- **图形化操作**：使用 PySide6 构建桌面 GUI，支持中英文切换。
- **Python 打包**：支持 PyInstaller 和 Nuitka，可配置单文件、无控制台、清理构建等选项。
- **Python -> Android**：通过 Buildozer / python-for-android 生成 Android 打包工程，支持权限、版本号、屏幕方向、API 等级、图标、启动图和 Kivy 项目检测。
- **C# 打包**：调用 `dotnet publish`，支持 Runtime Identifier、self-contained、single-file 和 trim 配置。
- **Node.js 打包**：通过 `npx pkg` 生成指定 Node 目标平台产物。
- **Java 打包**：通过 JDK `jpackage` 生成 exe、msi 或 app-image。
- **网页文件夹 -> Android**：把 HTML/CSS/JS 网页目录转换为 Android Studio WebView 项目，可选择只生成项目，也可直接生成 Debug APK、Release APK 或 Release AAB。
- **移动端适配**：网页转 Android 时可自动注入移动端适配 CSS/JS，并优先识别 `dist/`、`build/`、`public/`、`www/` 等前端构建输出目录。

## 项目结构

```text
Compress/
├── src/
│   ├── main.py                  # 程序入口
│   ├── core/                    # 构建逻辑与配置模型
│   │   ├── builders.py           # 各语言构建命令封装
│   │   ├── config.py             # dataclass 配置定义
│   │   ├── android_project.py    # 网页文件夹生成 Android 项目
│   │   ├── python_android.py     # Python / Buildozer Android 打包
│   │   └── utils.py
│   ├── ui/
│   │   └── main_window.py        # PySide6 主窗口
│   └── resources/
│       └── translations.json     # 中英文文案
├── tests/
│   └── test_builders.py          # 构建逻辑单元测试
├── AGENTS.md
└── GEMINI.md
```

## 环境要求

建议使用 Python 3.10 或更高版本。

基础运行依赖：

```bash
pip install PySide6
```

根据需要安装以下可选工具：

- Python 桌面打包：`PyInstaller` 或 `Nuitka`
- C# 打包：.NET SDK，提供 `dotnet`
- Node.js 打包：Node.js / npm，提供 `npx`
- Java 打包：JDK，提供 `jpackage`
- Python Android 打包：Linux、macOS 或 WSL 环境下安装 Buildozer
- 网页文件夹转 Android APK/AAB：Android SDK、Gradle 或 Gradle Wrapper、JDK 17+

## 快速开始

```bash
git clone https://github.com/throwbananana/Compress.git
cd Compress

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install PySide6
python src/main.py
```

> 注意：`src/main.py` 当前默认设置了 `QT_QPA_PLATFORM=windows` 来规避部分 Windows Qt 显示问题。如果在 macOS 或 Linux 上运行 GUI 遇到 Qt platform plugin 相关错误，请根据系统环境调整该设置。

## 使用说明

启动程序后，在「构建目标」中选择要处理的项目类型，然后填写对应参数并点击「开始构建」。构建日志会显示在窗口底部。

### Python

支持两种桌面打包后端：

- `PyInstaller`
- `Nuitka`

常用配置包括：

- 入口 `.py` 文件或项目文件夹
- Python 解释器路径
- 单文件输出
- 无控制台模式
- 清理构建目录

如果选择 Android Buildozer 后端，还可以配置：

- Android 应用标题
- 包域名与包名
- 版本号
- requirements
- Android 权限
- 屏幕方向
- min SDK / target SDK
- icon / presplash
- Buildozer 可执行文件路径

### C#

选择 `.csproj` 文件后，可设置：

- Runtime Identifier，例如 `win-x64`、`linux-x64`、`osx-arm64`
- 是否 self-contained
- 是否生成单文件
- 是否裁剪未使用代码

底层会调用：

```bash
dotnet publish
```

### Node.js

选择 `.js` 文件或 `package.json`，并选择目标 Node 平台，例如：

- `node18-win-x64`
- `node18-linux-x64`
- `node18-macos-x64`

底层会通过 `npx pkg` 生成输出。

### Java

选择主 JAR 或 JAR 所在目录后，可设置：

- main class
- 输出类型：`exe`、`msi`、`app-image`

底层会调用 JDK 的：

```bash
jpackage
```

### Android（网页文件夹）

该模式会把本地网页目录转换为 Android Studio WebView 工程。

支持：

- 自动检测启动页，例如 `index.html`
- 自动优先选择 `dist/`、`build/`、`public/`、`www/` 等前端构建输出目录
- 自定义应用名和包名
- 设置 min SDK / target SDK
- 只生成 Android Studio 项目
- 生成 Debug APK
- 生成 Release APK
- 生成 Release AAB
- 可选移动端适配注入

Release 构建可通过生成的 `keystore.properties.example` 配置签名，或使用环境变量：

```text
COMPASS_ANDROID_KEYSTORE_FILE
COMPASS_ANDROID_KEYSTORE_PASSWORD
COMPASS_ANDROID_KEY_ALIAS
COMPASS_ANDROID_KEY_PASSWORD
```

如需使用国内 Maven 镜像，可在 Gradle 属性或环境变量中设置：

```text
COMPASS_USE_ALIYUN_MIRRORS=true
```

## 运行测试

```bash
python -m unittest discover -s tests
```

测试覆盖内容包括：

- Python / C# / Node.js / Java 构建命令生成
- Python Android Buildozer 工程生成
- Android WebView 工程生成
- Android 产物路径推断
- requirements、icon、presplash 自动检测
- 构建参数校验和异常处理

## 常见问题

### 1. 启动时提示 PySide6 不存在

请先安装基础依赖：

```bash
pip install PySide6
```

### 2. Python Android 打包在 Windows 下失败

Buildozer / python-for-android 更适合在 Linux、macOS 或 WSL 中运行。Windows 用户建议在 WSL 中进入项目目录后再执行 Android 打包流程。

### 3. Release APK / AAB 没有签名

请复制生成目录中的 `keystore.properties.example` 为 `keystore.properties` 并填写签名配置，或设置对应的 `COMPASS_ANDROID_*` 环境变量。

### 4. Android Gradle 构建失败

请确认以下环境可用：

- JDK 17+
- Android SDK
- Gradle 或 Gradle Wrapper
- `ANDROID_SDK_ROOT` 或 `ANDROID_HOME` 环境变量
- Release 构建所需签名配置

## 开发建议

如果要继续完善项目，建议补充：

- `requirements.txt` 或 `pyproject.toml`
- LICENSE 文件
- 打包后的可执行文件发布流程
- GitHub Actions CI
- 更完整的跨平台启动说明

## 许可证

当前仓库中未包含明确的开源许可证文件。正式发布前建议补充 `LICENSE`，例如 MIT、Apache-2.0 或 GPL 等。
