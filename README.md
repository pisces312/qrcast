# QRCast / 码上通

跨平台二维码离线文件传输工具。无需网络、无需配对，有光就能传。

Cross-platform offline file transfer via QR codes. No network, no pairing — just light.

**Sender (Python):** 生成端，支持黑白二维码和 RGB 彩色二维码  
**Receiver (Android):** 接收端，Android 应用实时扫码组装文件

---

## 功能 / Features

### Sender (Python)

| | 中文 | English |
|---|------|---------|
| 🖤 | 黑白二维码 (V2) — 可配置 QR version 1-40 | B&W QR (V2) — configurable QR version 1-40 |
| 🌈 | RGB 彩色二维码 (V3) — 3 通道 ~3x 密度 | RGB Color QR (V3) — 3-channel ~3x density |
| 📦 | 7z 压缩 — LZMA2 preset 9 | 7z compression — LZMA2 preset 9 |
| ⚡ | 边生成边显示 — 生产者-消费者并发 | Generate & display concurrently — producer-consumer |
| 🖥️ | 全屏播放 — 可配帧率 | Fullscreen display — configurable frame rate |
| 🔍 | 摄像头接收 — OpenCV 实时扫码 | Camera receiver — OpenCV real-time scanning |

### Receiver (Android)

| | 中文 | English |
|---|------|---------|
| 🧩 | 分块传输模式 — 大文件分多个二维码，自动组装 | Chunked mode — split large files across multiple QR codes, auto-assemble |
| 📄 | 原始数据模式 — 单张二维码编码小文件 | Raw mode — single QR encodes small files |
| 📷 | 相机扫码 — 实时摄像头扫描 | Camera scan — real-time camera scanning |
| 🖼️ | 图库选图 — 从相册选择二维码图片解析 | Gallery pick — select QR image from photos |
| 📁 | 可配置输出目录 | Configurable output directory |
| 🏷️ | 时间戳文件名 `yyyyMMdd_HHmmss_SSS` | Timestamp filenames `yyyyMMdd_HHmmss_SSS` |
| 🔧 | 调试日志 — 内置日志查看器 | Debug logs — built-in log viewer |
| 📤 | 打开/分享接收的文件 | Open/share received files |

---

## 快速开始 / Quick Start

### Sender (Python)

```bash
cd sender

# 一键发送（边生成边全屏播放，5 fps，适合手机接收）
python -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2

# 启用 7z 压缩
python -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2 --compress

# 小文件单 QR 码快速发送
python -m qrcast.bw.quick_sender myfile.txt
```

### Receiver (Android)

```bash
cd receiver-android
./build.sh debug
# 安装 app/build/outputs/apk/debug/app-debug.apk
```

---

## 项目结构 / Project Structure

```
qrcast/
├── sender/              # Python 发送端
│   ├── qrcast/         # Python package
│   │   ├── bw/         # 黑白二维码 (V2)
│   │   └── rgb/        # RGB 彩色二维码 (V3)
│   ├── tests/
│   └── pyproject.toml
├── receiver-android/   # Android 接收端
│   ├── app/
│   └── build.gradle.kts
├── docs/               # 统一文档
│   └── protocol-spec.md # 协议规范（权威来源）
├── CLAUDE.md           # 开发环境配置
└── README.md
```

---

## 协议规范 / Protocol

### 分块模式 (CHUNKED)

每个二维码编码一个数据块，格式：

Each QR code encodes one data chunk:

```
[4 bytes: seq] [4 bytes: total] [remaining: payload]
```

- 序号从 0 开始 / Sequence starts from 0
- 接收端收集所有块后按序号拼接，自动识别 7z/zip 压缩包并解压
- Receiver collects all chunks, assembles by sequence, auto-detects & decompresses 7z/zip

### 原始数据模式 (RAW)

单张二维码直接编码文件原始字节，无分块头。适合小文件。

Single QR encodes raw file bytes with no chunking header. For small files.

详细协议文档 / Detailed spec: [docs/protocol-spec.md](docs/protocol-spec.md)

---

## 构建 / Build

### Sender (Python)

要求 / Requirements:
- Python 3.11+
- OpenCV, qrcode, Pillow, py7zr

```bash
cd sender
pip install -e .
```

### Receiver (Android)

要求 / Requirements:
- Android SDK (compileSdk 36)
- JDK 17
- Gradle 9.4.1

```bash
cd receiver-android
./build.sh debug      # Debug APK
./build.sh release    # Release APK (需要签名环境变量)
```

---

## 技术栈 / Tech Stack

| | Sender (Python) | Receiver (Android) |
|---|---|---|
| 语言 / Language | Python 3.11 | Kotlin |
| 二维码 / QR | qrcode + Pillow | CameraX + ML Kit Barcode Scanning |
| 相机 / Camera | OpenCV | CameraX |
| 压缩 / Compression | py7zr (LZMA2) | Apache Commons Compress |
| UI | — | AndroidX + Material Design |

---

## ☕ 捐赠 / Donate

如果这个项目对你有帮助，欢迎支持维护：<br>
If this project helps you, consider supporting maintenance:

<div align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <img src="assets/donate-alipay.png" width="200" alt="支付宝 / Alipay"><br>
        <b>支付宝 / Alipay</b>
      </td>
      <td align="center" width="50%">
        <img src="assets/donate-wechat.png" width="200" alt="微信 / WeChat"><br>
        <b>微信 / WeChat</b>
      </td>
    </tr>
  </table>
</div>

---

## 许可证 / License

MIT
