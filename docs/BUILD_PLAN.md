# 构建计划：只生成 arm64-v8a 和 x86_64 两个架构的 Release APK

## 背景

用 `--split-per-abi` 会构建出3个 APK（含不需要的 armeabi-v7a），之前的 `splits.abi` Gradle 配置导致真机秒退（原生库丢失），已移除。

## 方案

分别执行两次构建命令，每次只指定一个目标平台，构建后重命名为带架构标识的文件名：

```bash
# 1. 清理旧 APK
rm -f build/app/outputs/flutter-apk/*.apk

# 2. 构建 ARM64（真机）
flutter build apk --target-platform android-arm64 --release
mv build/app/outputs/flutter-apk/app-release.apk build/app/outputs/flutter-apk/app-arm64-v8a-release.apk

# 3. 构建 x86_64（模拟器）
flutter build apk --target-platform android-x64 --release
mv build/app/outputs/flutter-apk/app-release.apk build/app/outputs/flutter-apk/app-x86_64-release.apk
```

## 不修改 build.gradle.kts

当前配置已移除 `splits.abi`，`--target-platform` 参数控制 Flutter 只打包指定架构的原生库。

## 验证

- `build/app/outputs/flutter-apk/` 下只有两个 APK
- arm64 版本安装到荣耀 Magic8 真机不秒退
- x86_64 版本可在模拟器运行