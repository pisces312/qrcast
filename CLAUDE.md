# CLAUDE.md

## Project: QR Transfer App (Android Receiver)

QR code file transfer receiver for Android, matching with Python-based generators.

## Environment & Build Commands

### Environment
- Flutter SDK: `D:\nili\dev\flutter`
- Android SDK: `D:\nili\dev\android_sdk`
- JDK: `D:\nili\dev\AndroidStudio\jbr` (JBR 21)
- NDK: `27.0.12077973`

### Build Commands
- **Full Build (Standard)**: `bash build.sh release` (Generates ARM64 and x86_64 APKs)
- **ARM64 Only**: `flutter build apk --target-platform android-arm64 --release`
- **x86_64 Only**: `flutter build apk --target-platform android-x64 --release`
- **Debug**: `bash build.sh debug`
- **Dependencies**: `flutter pub get`
- **Clean**: `flutter clean`

### Output Locations
- ARM64 APK: `build/app/outputs/flutter-apk/app-arm64-v8a-release.apk`
- x86_64 APK: `build/app/outputs/flutter-apk/app-x86_64-release.apk`
- Received Files: `/storage/emulated/0/Download/QRTransfer/`

## Code Guidelines

### Architecture
- **Scanning**: Uses `mobile_scanner` with multi-QR detection enabled.
- **Protocol**: 
    - Header: `[seq(4B)][total(4B)]` (Big-endian)
    - Consensus: Multiple QR codes in one frame use majority vote for `total`.
    - Assembly: Chunks are kept in memory until `total` unique chunks are received.
- **File Naming**: 
    - `0x37` ('7') -> `.7z`
    - `0x50 0x4B` ('PK') -> `.zip`
    - Default -> `received_<timestamp>.bin`

### Style
- Standard Flutter/Dart conventions.
- Use `permission_handler` for storage and camera permissions.
- Minimize UI rebuilds during high-frequency scanning.

## Common Fixes
- **Build Failure**: If Gradle reports failure but APK exists, ignore and check `build/app/outputs/flutter-apk/`.
- **MainActivity Missing**: Ensure `android/app/src/main/kotlin/com/example/qr_transfer/MainActivity.kt` exists.
- **SDK Version**: If Flutter version detection fails, run `git -C "D:\nili\dev\flutter" tag --force 3.41.6`.
