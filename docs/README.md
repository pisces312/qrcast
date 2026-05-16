# qr_transfer_app

二维码传文件 App（Android 接收端）

## 项目路径

`C:\nili\my-git-projects\my-notebooks\my_projects\qr_transfer_app`

## 系统架构

本项目是 QR 码文件传输系统的 **Android 接收端**，与以下 Python 脚本配套使用：

| 组件 | 路径 | 职责 |
|------|------|------|
| **qr_generator.py** | `../qrcode_transfer/qr_generator.py` | 将文件分块编码为多张 QR 码画布（版本32，纠错L） |
| **qr_displayer.py** | `../qrcode_transfer/qr_displayer.py` | 全屏轮播显示 QR 码画布 |
| **qr_receiver_v2.py** | `../qrcode_transfer/qr_receiver_v2.py` | Python 版接收端（PC摄像头 + zxingcpp 解码） |
| **本 App** | `qr_transfer_app/` | Android 版接收端（手机摄像头 + mobile_scanner 解码） |

### 数据格式（发送端与接收端一致）

每个 QR 码的 payload 格式：

```
[seq(4B big-endian)][total(4B big-endian)][data bytes]
```

- `seq`：当前分块序号（0-based）
- `total`：总分块数
- `data`：文件分块数据（最大 1857 字节 = 1865 - 8 头部）

### 误报过滤策略（与 Python 接收端一致）

当一帧中检测到多个 QR 码时，可能存在误报。两端采用相同的过滤逻辑：

1. **多数投票共识**：统计所有检测到的 QR 码中 `total` 值的出现次数，取出现最多的作为共识值
2. **有效性过滤**：只保留 `total == 共识值` 且 `seq < total` 的有效分块

```
# Python (qr_receiver_v2.py)
consensus_total = max(set(totals), key=totals.count)
results = [(s,t,p) for s,t,p in raw if t == consensus_total and s < consensus_total]

# Dart (main.dart) — 相同逻辑
consensusTotal = totalCounts.entries.reduce((a,b) => a.value > b.value ? a : b).key
validChunks = potentialChunks.where((c) => c.total == consensusTotal && c.seq < c.total)
```

### 缺失块检测（与 Python 接收端一致）

两端都在组装前检查是否所有分块都已收到：
- Python：打印缺失块编号列表
- Android：显示错误信息 + "继续接收"按钮，可恢复扫描补收

### 接收文件存放位置

接收完成的文件默认保存在手机的 **Download/QRTransfer/** 目录下：

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1（默认） | `/storage/emulated/0/Download/QRTransfer/` | 公共下载目录，可通过文件管理器直接找到 |
| 2（兜底） | `/data/data/<包名>/app_flutter/QRTransfer/` | 应用私有目录，仅当下载目录不可用时使用 |

文件名根据内容自动判断：

| 文件类型 | 文件名 | 判断依据 |
|----------|--------|----------|
| 7z 压缩包 | `received_file.7z` | 首字节为 `0x37`（ASCII '7'） |
| zip 压缩包 | `received_file.zip` | 首两字节为 `0x50 0x4B`（PK） |
| 其他 | `received_<时间戳>.bin` | 无法识别时使用时间戳命名 |

## 技术栈

- Flutter SDK：`D:\nili\dev\flutter`
- Android SDK：`D:\nili\dev\android_sdk`
- JDK 17+（使用 Android Studio 内置 JBR：`D:\nili\dev\AndroidStudio\jbr`）
- NDK：27.0.12077973（`D:\nili\dev\android_sdk\ndk\27.0.12077973`）

## 依赖

- mobile_scanner ^5.2.3（扫码，支持同时检测多 QR 码）
- camera ^0.11.0+2（相机）
- permission_handler ^11.3.1（权限管理）
- path_provider ^2.1.4（路径访问）
- share_plus ^10.0.2（分享）
- archive ^3.6.1（压缩）

## 构建产物

### Debug APK（单架构）
`build\app\outputs\flutter-apk\app-debug.apk`（98.5 MB，2026/4/11 23:03）

### Release APK（按架构拆分，2026/4/12）
| APK | 架构 | 用途 | 大小 |
|-----|------|------|------|
| `app-arm64-v8a-release.apk` | ARM64 | 荣耀 Magic8 真机 | ~4 MB |
| `app-x86_64-release.apk` | x86_64 | Android 模拟器 | ~11 MB |

---

## 构建步骤

### 1. 环境准备

```bash
# 绑定 Flutter 版本 tag（非官方源克隆需要）
git -C "D:\nili\dev\flutter" tag --force 3.41.6

# 确认环境（可选）
flutter doctor
```

### 2. 修改 build.gradle.kts（ABI Split 配置）

文件路径：`android\app\build.gradle.kts`

在 `android { }` 块内添加以下配置，只打包 ARM64 和 x86_64 两套架构：

```kotlin
splits {
    abi {
        isEnable = true
        reset()
        include("arm64-v8a", "x86_64")
        isUniversalApk = false
    }
}
```

> 注意：Flutter 的 `--target-platform` 参数用 `android-x64`（不是 `android-x86_64`）

### 3. 构建命令

```bash
# 切换到项目目录
cd "C:\nili\my-git-projects\my-notebooks\my_projects\qr_transfer_app"

# 清理旧 APK
Remove-Item "build\app\outputs\flutter-apk\*.apk" -Force

# 构建 ARM64 APK（荣耀 Magic8 真机）
flutter build apk --target-platform android-arm64 --release

# 构建 x86_64 APK（Android 模拟器）
flutter build apk --target-platform android-x64 --release
```

> **警告**：Flutter build 有时会报错"Gradle build failed to produce an .apk file"，
> 但 APK 文件实际已生成，需检查 `build\app\outputs\flutter-apk\` 目录确认。

### 4. 用 Python subprocess 构建（避免 PowerShell 路径问题）

```python
import subprocess, os

project = r"C:\nili\my-git-projects\my-notebooks\my_projects\qr_transfer_app"
flutter = r"D:\nili\dev\flutter\bin\flutter.bat"

# ARM64
r1 = subprocess.run(
    [flutter, "build", "apk", "--target-platform", "android-arm64", "--release"],
    cwd=project, capture_output=True, encoding="utf-8", errors="replace"
)
print(f"arm64 exit: {r1.returncode}")

# x86_64
r2 = subprocess.run(
    [flutter, "build", "apk", "--target-platform", "android-x64", "--release"],
    cwd=project, capture_output=True, encoding="utf-8", errors="replace"
)
print(f"x86_64 exit: {r2.returncode}")
```

### 5. 用 Android Studio 调试

1. 打开 Android Studio，`Open` → 选择项目的 `android` 目录
2. 连接真机或启动模拟器
3. 点击 **Run**，Android Studio 会自动匹配当前设备的架构 APK

---

## 常见问题

### MainActivity.kt 缺失
- 症状：APK 构建成功但启动即崩溃，logcat 报错 `Didn't find class com.example.qr_transfer.MainActivity`
- 原因：`src/main/kotlin/com/example/qr_transfer/` 目录或 `MainActivity.kt` 不存在
- 修复：手动创建 `MainActivity.kt`，内容为标准 Flutter 入口类

### Flutter SDK tag 丢失
- 问题：Flutter SDK 从非官方源克隆，`git describe --tags` 找不到版本
- 修复：`git -C "D:\nili\dev\flutter" tag --force 3.41.6` 重新绑定版本 tag

### Gradle 构建报 "failed to produce .apk" 但文件实际存在
- 原因：Flutter Gradle 插件在 ABI Split 模式下有时会误报失败
- 解决：直接检查 `build\app\outputs\flutter-apk\` 目录，APK 文件是否已生成

### PowerShell 路径含 `\n` 被误解为转义
- 问题：`D:\nili` 中的 `\n` 被 PowerShell 误解为换行符
- 解决：用 Python subprocess 调用 Flutter，或用单引号路径

### Flutter.bat 在 PowerShell 中挂起
- 症状：`flutter build apk` 卡在 `Running Gradle...`
- 解决：用 Android Studio 打开 `android/` 目录构建，或用 Python subprocess

---

## 构建历史

| 日期 | 事件 |
|------|------|
| 2026/4/11 23:03 | Debug APK 首次构建成功（98.5 MB） |
| 2026/4/12 17:58 | Release APK 按架构拆分构建成功（arm64: 4 MB，x86_64: 11 MB） |
| 2026/4/12 | 新增误报过滤（多数投票共识）和缺失块检测，与 Python 接收端逻辑一致 |
