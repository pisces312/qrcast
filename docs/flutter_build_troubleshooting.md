# Flutter Android 构建问题排查笔记

> 项目：`qr_transfer_app`
> 日期：2026-04-11
> Flutter SDK：`D:\nili\dev\flutter` (3.41.6)
> Android SDK：`D:\nili\dev\android_sdk`

---

## 问题一：Flutter SDK 版本检测失败 — `0.0.0-unknown`

### 症状

```
The current Flutter SDK version is 0.0.0-unknown.
Because qr_transfer depends on path_provider >=0.4.0 which requires Flutter SDK version >=0.1.4, version solving failed.
```

`flutter pub get` 失败，依赖解析无法进行。

### 根因分析

Flutter SDK 版本检测依赖于两个机制：

1. **`D:\nili\dev\flutter\version` 文件**（Flutter framework 的 git 版本标记）
   - 文件不存在或为空 → Flutter 工具链退化为 `0.0.0-unknown`

2. **`git describe --tags --abbrev=12 --first-parent`**（从当前 commit 往前找最近的 tag）
   - 要求 tag 必须是当前 commit 的**祖先**（ancestor）
   - 原始 tag `3.41.6` 指向 commit `db50e20168d...`
   - 当前 HEAD 是 `38503743b038...`
   - 两者不在同一分支历史上，`3.41.6` 不是 HEAD 的祖先 → `git describe` 永远失败

### 诊断命令

```bash
# 检查 version 文件
cat D:\nili\dev\flutter\version

# 检查 git tag 指向
git -C D:\nili\dev\flutter describe --tags
git -C D:\nili\dev\flutter tag --points-at HEAD

# 验证 tag 是否是 HEAD 的祖先
git -C D:\nili\dev\flutter merge-base --is-ancestor 3.41.6 HEAD
# 输出 NOT_ANCESTOR → 说明 tag 不在 HEAD 的祖先链上
```

### 解决方案

**Step 1：** 强制将 tag 绑定到当前 HEAD

```bash
git -C D:\nili\dev\flutter tag --force 3.41.6
# 输出：Updated tag '3.41.6' (was db50e20168d)
```

**Step 2：** 清理旧快照，强制重建 flutter_tools

```bash
# 删除快照和版本缓存
del /f D:\nili\dev\flutter\bin\cache\flutter_tools.snapshot
del /f D:\nili\dev\flutter\bin\cache\flutter_tools.stamp
del /f D:\nili\dev\flutter\bin\cache\flutter.version.json
```

**Step 3：** 重建后 flutter_tools 快照会在首次运行时自动生成

```bash
flutter pub get
# 会显示 "Building flutter tool..." 后自动重建
```

### 预防建议

- 克隆非官方 Flutter fork 后，应先检查 `git tag --points-at HEAD` 是否为空
- 如果 tag 指向错误 commit，使用 `git tag --force <tagname>` 重新绑定
- Flutter SDK 版本损坏时，核心判断逻辑在 `packages/flutter_tools/lib/src/version.dart`

---

## 问题二：`mobile_scanner` API 兼容性问题

### 症状

```
lib/main.dart:106:7: Error: No named parameter with the name 'cameraDirection'.
      cameraDirection: CameraFacing.back,
      ^^^^^^^^^^^^^^^
Target kernel_snapshot_program failed: Exception
```

### 根因分析

`mobile_scanner: 5.2.3` 版本中，`MobileScannerController` 构造函数的 API 发生了变化：

- `cameraDirection` 参数已被移除
- 统一使用 `facing` 参数

代码中同时写了两个参数：

```dart
// ❌ 错误写法
MobileScannerController(
  cameraDirection: CameraFacing.back,  // ← 5.x 已移除
  detectionSpeed: DetectionSpeed.normal,
  facing: CameraFacing.back,
);
```

### 解决方案

删除已废弃的 `cameraDirection` 参数：

```dart
// ✅ 正确写法
MobileScannerController(
  facing: CameraFacing.back,
  detectionSpeed: DetectionSpeed.normal,
);
```

修改位置：`lib/main.dart` 第 106 行附近

---

## 问题三：Android 原生资源缺失

### 症状

```
ERROR: ...AndroidManifest.xml:48: AAPT: error: resource mipmap/ic_launcher not found.
ERROR: ...AndroidManifest.xml:18: AAPT: error: resource style/LaunchTheme not found.
ERROR: ...AndroidManifest.xml:27: AAPT: error: resource style/NormalTheme not found.
```

Gradle 构建在 `processDebugResources` 阶段失败，Android AAPT 资源链接器找不到引用的资源。

### 根因分析

项目创建时未完整生成 Android 原生资源目录，整个 `android/app/src/main/res/` 目录为空。

`AndroidManifest.xml` 引用了三类资源：
- `@mipmap/ic_launcher` — 应用图标
- `@style/LaunchTheme` — 启动画面主题
- `@style/NormalTheme` — 正常运行主题
- `@drawable/launch_background` — LaunchTheme 的背景（被 styles.xml 引用）

### 诊断命令

```bash
dir android\app\src\main\res\
# system cannot find the file specified → 目录完全不存在
```

### 解决方案

手动补全缺失的 Android 资源文件：

#### 1. 创建目录结构

```bash
mkdir android\app\src\main\res\values
mkdir android\app\src\main\res\drawable
mkdir android\app\src\main\res\mipmap-hdpi
```

#### 2. `res/values/colors.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="flutter_color">#4C9A4C</color>
</resources>
```

#### 3. `res/values/styles.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- 启动主题：显示 Flutter 启动画面 -->
    <style name="LaunchTheme" parent="@android:style/Theme.Light.NoTitleBar">
        <item name="android:windowBackground">@drawable/launch_background</item>
    </style>
    <!-- 正常运行主题 -->
    <style name="NormalTheme" parent="@android:style/Theme.Light.NoTitleBar">
        <item name="android:windowBackground">?android:colorBackground</item>
    </style>
</resources>
```

#### 4. `res/drawable/launch_background.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:drawable="@color/flutter_color" />
</layer-list>
```

#### 5. `res/mipmap-hdpi/ic_launcher.png`

用 Python 生成 48x48 纯色图标（占位用，正式发布应替换为正式图标）：

```python
import zlib, struct, os

def create_png(w, h, r, g, b):
    def chunk(name, data):
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr_data = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    raw = b''
    for y in range(h):
        raw += b'\x00'  # filter byte
        for x in range(w):
            raw += bytes([r, g, b])
    idat = chunk(b'IDAT', zlib.compress(raw))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr_data) + idat + chunk(b'IEND', b'')

path = r'android\app\src\main\res\mipmap-hdpi\ic_launcher.png'
with open(path, 'wb') as f:
    f.write(create_png(48, 48, 0x4C, 0x9A, 0x4C))
```

> **正式图标建议**：替换为完整的多分辨率 PNG（mipmap-mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi），或使用 `flutter_launcher_icons` 包自动生成。

---

## 附：Flutter SDK 目录结构参考

```
D:\nili\dev\flutter\
├── version                          ← Flutter framework 版本（git commit hash）
├── bin\
│   ├── flutter.bat                  ← 入口脚本
│   └── cache\
│       ├── flutter_tools.snapshot   ← Flutter 工具链快照（重建时会自动刷新）
│       ├── flutter_tools.stamp     ← 快照版本标记
│       ├── flutter.version.json     ← 版本缓存
│       └── artifacts\engine\        ← 各平台预编译产物
│           ├── android-arm-release\
│           ├── android-arm64-release\
│           ├── android-x64-release\
│           └── windows-x64\         ← 桌面端工具
└── packages\flutter_tools\lib\src\version.dart  ← 版本检测逻辑源码
```

---

## 构建成功命令

```bash
# 路径
cd C:\nili\my-git-projects\my-notebooks\my_projects\qr_transfer_app

# 1. 确保 Flutter 版本正常
flutter --version

# 2. 获取依赖
flutter pub get

# 3. 构建 Debug APK
flutter build apk --debug

# 输出位置
# build\app\outputs\flutter-apk\app-debug.apk
```
