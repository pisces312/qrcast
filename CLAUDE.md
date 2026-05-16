# CLAUDE.md

## Project: QR传文件 (QRCast Android)

通过二维码离线传输文件的 Android 接收端，配合 [QRCast Python](https://github.com/pisces312/qrcast) 生成端使用。

## Environment & Build Commands

### Environment
- Android SDK: `D:\nili\dev\android_sdk` (compileSdk 35)
- JDK: `D:\nili\dev\AndroidStudio\jbr` (JBR 21, Java 17)
- NDK: `27.0.12077973`
- AGP: 8.9.1, Gradle: 9.4.1, Kotlin: 2.1.0

### Build Commands
- **Debug**: `./gradlew assembleDebug`
- **Release**: `./gradlew assembleRelease`
- **Clean**: `./gradlew clean`

### Output Locations
- Debug APK: `app/build/outputs/apk/debug/app-debug.apk`
- Release APK: `app/build/outputs/apk/release/app-release.apk`
- Received Files: configurable via Settings, default `Download/QRTransfer/`

## Architecture

### Source Structure
```
app/src/main/kotlin/com/example/qr_transfer/
├── MainActivity.kt       — 相机扫码、图库选图、文件组装、UI状态管理
├── SettingsActivity.kt   — 输出目录配置(SAF + 手动输入)
├── LogActivity.kt        — 日志查看(复制/分享/清除)
├── LogCollector.kt       — 双轨日志收集器(内存缓冲 + 外部文件)
└── QrTransferApp.kt      — Application基类
```

### Protocol
- **CHUNKED 模式**: `[seq(4B)][total(4B)][payload]` (Big-endian), 收集所有块后按序拼接，自动识别 .7z/.zip 并解压
- **RAW 模式**: 单张二维码直接编码文件原始字节，无分块头

### Key Dependencies
- CameraX (camera-core/camera2/lifecycle/view 1.4.1) — 相机预览与图像分析
- ML Kit Barcode Scanning (17.3.0) — 二维码识别
- AndroidX ConstraintLayout (2.2.0) — 布局
- Lifecycle runtime/viewmodel-ktx (2.8.7) — 协程作用域

### File Naming
- 接收文件: `yyyyMMdd_HHmmss_SSS.txt` / `.7z` / `.zip` / `.bin` (根据文件头自动判断扩展名)
- 设置存储: SharedPreferences (`qr_transfer_settings`)

## Code Style
- Kotlin + AndroidX conventions
- SharedPreferences for settings (companion object in SettingsActivity)
- LogCollector for all logging (i() / w() / e() static methods)
- UI uses `fitsSystemWindows="true"` on root layout to avoid status bar overlap
