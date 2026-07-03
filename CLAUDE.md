# QRCast — Monorepo

跨平台二维码离线文件传输工具。包含：
- Sender (Python): 二维码生成端（黑白 V1/V2 + 彩色 V3）
- Receiver (Android): Android 扫码接收端

## 全局环境

### 工具路径
- Git: `C:\nili\dev\git`
- Conda: `C:\nili\dev\miniconda3`
- Android SDK: `D:\nili\dev\android_sdk`
- JDK: `D:\nili\dev\AndroidStudio\jbr` (JBR 21, Java 17)
- Flutter SDK: `D:\nili\dev\flutter`

---

## Sender (Python)

### 环境
- Python: `D:\nili\dev\conda_envs\qrcast_env\python.exe` (conda env: qrcast_env, Python 3.11)
- 所有脚本、测试和 CLI 命令必须使用该 Python，而非系统/conda-base python
- 工作目录: `D:/my-projects/qrcast`

### 命令
- 安装依赖: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pip install <pkg>`
- 运行测试: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pytest tests/ -v`
- 生成 + 显示: `D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.gen_and_display_individual`

### 项目结构
```
qrcast/
  qrcast/
    bw/           # v2: B&W QR (configurable ver 1-40)
      generator.py, generator2.py      # 分步生成：文件 → 切片 → QR 图片序列
      gen_individual_all_in_one.py     # 单文件一站式生成黑白 QR 序列（v2 payload，无压缩）
      gen_and_display_individual.py    # 边生成边显示：生产者-消费者模式，CLI 一键发送
      display.py                       # 播放已生成的 QR 图片序列（全屏 cv2）
      quick_sender.py                  # 单文件单 QR 码快速发送（小文件）
      verifier.py, verifier2.py        # 验证 QR 序列并重建原始文件
      receiver.py, receiver2.py        # 摄像头实时接收端（黑白模式）
    rgb/          # v3: RGB color QR (was qrcast/v3/)
      generator_bin.py, generator_bin2.py, generator_text.py
      verifier_bin.py, verifier_bin2.py, verifier_text.py
      receiver_bin.py, receiver_bin2.py, receiver_text.py
    common.py     # shared: CANVAS_W/H, parse_payload_v2, etc.
    cli.py        # unified CLI: qrcast generate|display|verify|receive|quick-send
  tests/
    test_v2_roundtrip.py  # 25 unit tests (all pass)
```

### bw/ 脚本速查表（B&W 黑白二维码）

| 脚本 | 功能 | 典型场景 |
|------|------|---------|
| `gen_and_display_individual.py` | **边生成边全屏显示**，生产者-消费者并发 | **CLI 一键发送文件** — 最常用 |
| `gen_individual_all_in_one.py` | 单文件生成 QR 序列，保存到磁盘 | 预生成图片，离线测试或单独播放 |
| `display.py` | 播放已生成的 QR 图片序列 | 配合 `gen_individual_all_in_one` 使用 |
| `quick_sender.py` | 单文件编码为单张 QR 码 | 小文件（< 3KB）快速发送 |
| `receiver2.py` | 摄像头实时接收，重建文件 | 接收端运行 |
| `verifier2.py` | 验证已保存的 QR 图片序列，重建文件 | 离线验证/调试 |

### CLI 用法示例

#### 1. 一键发送（推荐）
```bash
# 边生成边全屏播放，5 fps，适合手机接收
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2

# 启用 7z 压缩后再编码
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2 --compress
```

#### 2. 分步：生成 → 显示
```bash
# 生成 QR 序列到 ./tmp/myfile-individual/
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.gen_individual_all_in_one myfile.zip --ver 20 --output-dir ./tmp

# 全屏播放（0.5 秒/帧）
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.display ./tmp/myfile-individual --interval 0.5
```

#### 3. 小文件单 QR 码快速发送
```bash
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.quick_sender myfile.txt
```

#### 4. 接收端（摄像头）
```bash
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.receiver2
```

#### 5. 验证与重建
```bash
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.verifier2 ./tmp/myfile-individual --output ./output/myfile.zip
```

### 依赖说明
- `qrgb` library required for v3 (RGB color) mode — installed in qrcast_env
- v3 tests skip gracefully if qrgb unavailable (`HAS_V3 = False`)

---

## Receiver (Android)

### 环境
- compileSdk: 36
- AGP: 8.10.1, Gradle: 9.4.1, Kotlin: 2.2.0
- NDK: 27.0.12077973
- 工作目录: `receiver-android/`

### 签名配置
- 默认密钥: `D:\nili\my-git-projects\my-backup\backup-settings\my-android-release.keystore`
- alias: `pisces312`
- 密码: `******`

### 命令
- Debug 构建: `cd receiver-android && ./gradlew assembleDebug`
- Release 构建: `cd receiver-android && ./gradlew assembleRelease`
- Clean: `cd receiver-android && ./gradlew clean`
- Build 脚本: `cd receiver-android && ./build.sh debug/release`

### 输出路径
- Debug APK: `receiver-android/app/build/outputs/apk/debug/app-debug.apk`
- Release APK: `receiver-android/app/build/outputs/apk/release/app-release.apk`
- Received Files: configurable via Settings, default `Download/QRTransfer/`

### 项目结构
```
receiver-android/
  app/src/main/kotlin/com/example/qr_transfer/
    MainActivity.kt       - 相机扫码、图库选图、文件组装、UI状态管理
    SettingsActivity.kt   - 输出目录配置(SAF + 手动输入)
    LogActivity.kt        - 日志查看(复制/分享/清除)
    LogCollector.kt       - 双轨日志收集器(内存缓冲 + 外部文件)
    QrTransferApp.kt      - Application基类
```

### 协议
- **CHUNKED 模式**: `[seq(4B)][total(4B)][payload]` (Big-endian), 收集所有块后按序拼接，自动识别 .7z/.zip 并解压
- **RAW 模式**: 单张二维码直接编码文件原始字节，无分块头

### 关键依赖
- CameraX (camera-core/camera2/lifecycle/view 1.4.1) — 相机预览与图像分析
- ML Kit Barcode Scanning (17.3.0) — 二维码识别
- AndroidX ConstraintLayout (2.2.0) — 布局
- Lifecycle runtime/viewmodel-ktx (2.8.7) — 协程作用域

### 文件命名
- 接收文件: `yyyyMMdd_HHmmss_SSS.txt` / `.7z` / `.zip` / `.bin` (根据文件头自动判断扩展名)
- 设置存储: SharedPreferences (`qr_transfer_settings`)

### 版本策略
- **版本号升级**: 每次代码修改后，`app/build.gradle.kts` 中 `versionName` 和 `versionCode` 各 +1
- `build.sh` 从 `build.gradle.kts` 读取 `versionName` 作为 APK 文件名前缀

### 提交与推送
- `git commit` 后**不自动 push**，等用户确认
- 修改后用 `cd receiver-android && ./build.sh debug` 构建 debug APK 验证

---

## 协议规范
参见: `docs/protocol-spec.md`

## 代码风格
- Python: PEP 8
- Kotlin: AndroidX conventions
