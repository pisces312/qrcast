# Flutter → 原生 Android 迁移构建记录

> 日期：2026-05-16
> 分支：`remove-flutter`
> 基于 commit：`1d90b22 chore: commit current state before Flutter removal`

## 版本组合

| 组件 | 版本 | 来源 |
|------|------|------|
| AGP | 8.9.1 | 参考 StreamClip 项目 |
| Gradle | 9.4.1-bin | 腾讯镜像 `mirrors.cloud.tencent.com/gradle/` |
| Kotlin | 2.1.0 | 参考 StreamClip 项目 |
| Java | 17 | sourceCompatibility / targetCompatibility |
| NDK | 27.0.12077973 | — |
| compileSdk | 35 | — |
| targetSdk | 35 | — |
| minSdk | 21 | — |

## Gradle 配置文件

### settings.gradle.kts

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "QRTransfer"
include(":app")
```

### build.gradle.kts (root)

```kotlin
plugins {
    id("com.android.application") version "8.9.1" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
}
```

### app/build.gradle.kts

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.qr_transfer"
    compileSdk = 35
    ndkVersion = "27.0.12077973"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = "com.example.qr_transfer"
        minSdk = 21
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.2.0")
    implementation("androidx.camera:camera-core:1.4.1")
    implementation("androidx.camera:camera-camera2:1.4.1")
    implementation("androidx.camera:camera-lifecycle:1.4.1")
    implementation("androidx.camera:camera-view:1.4.1")
    implementation("com.google.mlkit:barcode-scanning:17.3.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
}
```

### gradle.properties

```properties
org.gradle.jvmargs=-Xmx4G -XX:+HeapDumpOnOutOfMemoryError
android.useAndroidX=true
android.enableJetifier=false
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.configureondemand=true
```

## 依赖库

| 库 | 版本 | 用途 |
|----|------|------|
| androidx.core:core-ktx | 1.15.0 | Kotlin 扩展 |
| androidx.appcompat:appcompat | 1.7.0 | 兼容性支持 |
| com.google.android.material:material | 1.12.0 | Material Design 组件 |
| androidx.constraintlayout:constraintlayout | 2.2.0 | 布局 |
| androidx.camera:camera-core | 1.4.1 | 相机核心 |
| androidx.camera:camera-camera2 | 1.4.1 | Camera2 实现 |
| androidx.camera:camera-lifecycle | 1.4.1 | 相机生命周期管理 |
| androidx.camera:camera-view | 1.4.1 | 相机预览 View |
| com.google.mlkit:barcode-scanning | 17.3.0 | 二维码/条形码扫描 |
| androidx.lifecycle:lifecycle-runtime-ktx | 2.8.7 | 生命周期 |
| androidx.lifecycle:lifecycle-viewmodel-ktx | 2.8.7 | ViewModel |

## 项目结构

```
android/app/src/main/
├── AndroidManifest.xml
├── kotlin/com/example/qr_transfer/
│   └── MainActivity.kt
└── res/
    ├── drawable/
    │   ├── ic_check_circle.xml
    │   ├── ic_error.xml
    │   ├── progress_teal.xml
    │   ├── result_background.xml
    │   └── scan_frame.xml
    ├── layout/
    │   └── activity_main.xml
    ├── mipmap-{hdpi,mdpi,xhdpi,xxhdpi,xxxhdpi}/
    │   └── ic_launcher.png
    ├── values/
    │   ├── colors.xml
    │   └── themes.xml
    └── xml/
        └── file_paths.xml
```

## AndroidManifest.xml 关键配置

- 权限：CAMERA、WRITE_EXTERNAL_STORAGE(maxSdk=28)、READ_EXTERNAL_STORAGE(maxSdk=32)
- Feature：android.hardware.camera(required)、android.hardware.camera.autofocus(optional)
- Application：label="QR传文件"、requestLegacyExternalStorage=true
- Activity：theme=@style/Theme.QRTransfer、configChanges=orientation|screenSize|smallestScreenSize
- FileProvider：authorities=${applicationId}.fileprovider

## 迁移过程遇到的问题与解决

### 1. Kotlin 插件重复注册

**错误**: `Cannot add extension with name 'kotlin', as there is an extension already registered with that name`

**原因**: AGP 9.0.0 自动应用 Kotlin 插件，与显式声明冲突

**解决**: 降级 AGP 到 8.9.1（参考 StreamClip 稳定组合）

### 2. Flutter 资源引用残留

**错误**: `AAPT: error: resource color/flutter_color (aka com.example.qr_transfer:color/flutter_color) not found`

**原因**: `launch_background.xml` 仍引用 `@color/flutter_color`

**解决**: 删除 `res/drawable/launch_background.xml`

### 3. Flutter 插件注册类残留

**错误**: `io.flutter.plugins.GeneratedPluginRegistrant` 编译失败

**原因**: Flutter 自动生成的 `app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java` 未删除

**解决**: 删除整个 `app/src/main/java/` 目录

### 4. Flutter 主题残留

**原因**: `res/values/styles.xml` 仍含 Flutter LaunchTheme/NormalTheme

**解决**: 删除 `styles.xml`，使用新写的 `themes.xml`（Theme.QRTransfer，parent=Theme.Material3.Dark.NoActionBar）

### 5. 根目录 build/ 无法删除

**原因**: Windows 长路径限制（Flutter 插件 dex 文件路径超 260 字符）

**现状**: 目录非空但已被 `.gitignore` 忽略，不影响构建和版本控制

## 版本组合迭代历史

| 尝试 | AGP | Gradle | Kotlin | 结果 |
|------|-----|--------|--------|------|
| 1 | 9.0.0 | 9.4.1 | 2.1.0 | ❌ Kotlin 插件重复注册 |
| 2 | 8.7.3 | 8.10.2 | 2.1.0 | ❌ flutter_color 引用缺失 |
| 3 | 8.7.3 | 8.10.2 | 2.1.0 | ❌ GeneratedPluginRegistrant 残留 |
| 4 | **8.9.1** | **9.4.1** | **2.1.0** | ✅ BUILD SUCCESSFUL |

## 构建结果

- 命令：`gradlew assembleDebug --no-daemon`
- 耗时：51s
- 产出：`android/app/build/outputs/apk/debug/app-debug.apk`（约 17.9 MB）
- Tasks：38 actionable tasks (18 executed, 20 up-to-date)
- 警告：kotlinOptions 弃用（建议迁移到 compilerOptions）

## 已删除的 Flutter 文件

| 文件/目录 | 说明 |
|-----------|------|
| `lib/` | Dart 源码 |
| `pubspec.yaml` | Flutter 依赖配置 |
| `pubspec.lock` | 依赖锁定 |
| `.dart_tool/` | Dart 工具缓存 |
| `.flutter-plugins` | Flutter 插件列表 |
| `.flutter-plugins-dependencies` | 插件依赖 |
| `flutter.bat` / `flutter_run.bat` | Flutter 启动脚本 |
| `run_flutter.py` | Python 启动脚本 |
| `build.sh` | 构建脚本 |
| `app/src/main/java/` | GeneratedPluginRegistrant.java |
| `res/drawable/launch_background.xml` | Flutter 启动背景 |
| `res/values/styles.xml` | Flutter 主题 |
| `res/gen_icon.py` | 图标生成脚本 |

## 待办

- [ ] 将 `kotlinOptions` 迁移到 `compilerOptions`（消除弃用警告）
- [ ] 配置 Release 签名（当前 release 使用 debug 签名）
- [ ] 清理根目录 `build/`（Windows 长路径问题，考虑 WSL 下删除）
- [ ] 将分支 `remove-flutter` 合并回 `main`
