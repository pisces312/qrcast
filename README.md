# QRCast / 码上通

跨平台二维码离线文件传输工具。无需网络、无需配对，有光就能传。

**Sender (Python):** 生成端，支持黑白二维码 (V2) 和 RGB 彩色二维码 (V3)
**Receiver (Android):** 接收端，Android 应用实时扫码组装文件

---

## 快速开始

### Sender (Python)

```bash
cd sender
# 使用项目环境：D:/dev/conda_envs/qrcast_env/python.exe -m pip install -e .

# 生成并显示二维码（一键发送）
D:/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2
```

### Receiver (Android)

```bash
cd receiver-android
./build.sh debug
# 安装 app/build/outputs/apk/debug/app-debug.apk
```

---

## 项目结构

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

## 协议规范

### CHUNKED 模式（分块传输）
每个二维码编码：`[seq(4B big-endian)][total(4B big-endian)][payload]`

- 头长度：8 bytes
- 序号从 0 开始
- 接收端收集所有块后按序号拼接
- 自动识别 7z/zip 压缩包并解压

### RAW 模式（原始数据）
单张二维码直接编码文件原始字节，无分块头。适合小文件。

详细协议文档：[docs/protocol-spec.md](docs/protocol-spec.md)

---

## 兼容性矩阵

| Sender 版本 | Receiver-Android 版本 | 支持协议 |
|------------|----------------------|---------|
| v1.0.x     | v1.0.x              | CHUNKED, RAW |

---

## License

MIT
