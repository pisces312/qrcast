# RGB 模式待优化事项

> 从 camera-scan-review.md 提取，优先级延后处理。

## P0

### RGB 扫描路径未接入相机实时流
- **位置**: `processImage()` — 仅走 ML Kit BarcodeScanner（Mono 路径），RGB 模式下相机仍走 Mono 解码
- **影响**: RGB 模式"相机扫码"按钮实际无法工作，用户必须使用图库
- **方案**: 在 `processImage()` 中根据 `currentQrType` 分流：ImageProxy → Bitmap → RgbQrDecoder.decodeImage()
- **注意**: ImageProxy → Bitmap 转换有性能开销，需降低帧率或使用 YUV → Bitmap 高效转换

### RGB decodeRgbQr() 逐像素 getPixel() JNI 开销
- **位置**: `RgbQrDecoder.kt` L167-205
- **方案**: 一次性 `getPixels()` 取全部像素，用数组索引访问，实测可提速 3-5x

### classifyColor() 每像素重建 8 元素候选列表
- **位置**: `RgbQrDecoder.kt` L275-284
- **方案**: 将 candidates 提取为 companion object 常量；加入亮度快速分流路径

## P1

### BarcodeScanner 未复用（RGB 路径）
- **位置**: `RgbQrDecoder` L41 — 每次 `decodeImage()` 新建实例，ML Kit 内部加载 TFLite 模型开销大
- **方案**: 使用单例或 DI 复用

### decodeCanvas() 串行逐格解码
- **位置**: `RgbQrDecoder.kt` L104-128
- **方案**: 协程 async/awaitAll 并行解码网格中各 QR 码

## P2

### 通道 Bitmap 使用 ARGB_8888 浪费内存
- **位置**: `RgbQrDecoder.kt` L209-211
- **现状**: 三通道分离后生成 ARGB_8888（4 字节/像素），但通道图只有黑/白两色
- **方案**: 改用 ALPHA_8（1 字节/像素），内存省 75%。ML Kit InputImage.fromBitmap() 支持 ALPHA_8
