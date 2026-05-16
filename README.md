# QR传文件 (QRCast Android)

通过二维码在设备间离线传输小文件的 Android 应用。

扫描由 [QRCast Python](https://github.com/pisces312/qrcast) 生成的二维码，即可在手机上接收文件。无需网络、无需配对，即扫即得。

## 功能

- **分块传输模式**：支持大文件分多个二维码传输，自动组装还原
- **原始数据模式**：单张二维码直接编码文件内容，适合小文件
- **相机扫码**：实时摄像头扫描，支持自动对焦
- **图库选图**：从相册选择二维码图片解析
- **可配置输出目录**：设置页面可修改文件保存位置
- **时间戳文件名**：接收文件自动命名为 `yyyyMMdd_HHmmss_SSS` 格式
- **调试日志**：内置日志查看器，方便排查问题
- **打开/分享**：接收完成后可直接打开或分享文件

## 协议

### 分块模式 (CHUNKED)

每个二维码编码一个数据块，格式：

```
[4 bytes: 序号 seq] [4 bytes: 总块数 total] [剩余: 文件数据]
```

- 序号从 0 开始
- 接收端收集所有块后按序号拼接，自动识别 7z/zip 压缩包并解压

### 原始数据模式 (RAW)

整个二维码直接编码文件原始字节，无分块头。适合不超过单张二维码容量的文件（QR version 40 约 2953 字节）。

## 构建

要求：
- Android SDK (compileSdk 35)
- JDK 17
- Gradle 9.4.1

```bash
./gradlew assembleDebug
```

APK 输出路径：`app/build/outputs/apk/debug/app-debug.apk`

## 技术栈

- Kotlin + AndroidX
- CameraX (相机预览与图像分析)
- ML Kit Barcode Scanning (二维码识别)
- SharedPreferences (设置持久化)
- FileProvider (文件分享)

## 许可证

MIT
