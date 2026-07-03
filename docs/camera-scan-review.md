# QRCast Android 相机扫码实现 Review 报告

**审查日期**: 2026-05-26  
**审查范围**: 相机二维码扫描核心逻辑 (`MainActivity.kt`, `RgbQrDecoder.kt`, `FileReceiveState.kt`)  
**技术栈**: CameraX 1.4.1 + ML Kit Barcode Scanning 17.3.0

---

## 一、总体评价

当前实现功能完整，Mono/RGB 双模式、分块协议、多文件接收均已跑通。架构上所有逻辑集中在 `MainActivity`（~1145 行），扫描管线简洁清晰。以下是按优先级排列的优化建议。

---

## 二、性能问题（P0 - 直接影响扫描速度/流畅度）

### 2.1 RGB 扫描路径未接入相机实时流

**现状**: `processImage()` 只走 ML Kit `BarcodeScanner`（Mono 路径），RGB 模式下相机仍在走 Mono 解码，无法实时扫描彩色二维码。RGB 解码仅用于图库选图。

**影响**: RGB 模式下"相机扫码"按钮实际无法工作，用户必须使用图库。

**建议**: 若需支持 RGB 实时扫描，在 `processImage()` 中根据 `currentQrType` 分流：
```kotlin
if (currentQrType == QrType.RGB) {
    // 将 ImageProxy 转 Bitmap → RgbQrDecoder.decodeImage()
} else {
    barcodeScanner.process(image) ...
}
```
注意 `ImageProxy → Bitmap` 转换有性能开销，需降低帧率或使用 YUV → Bitmap 高效转换。

### 2.2 `assembleFile()` 中 `fullData` 使用 `mutableListOf<Byte>()` 逐字节追加

**现状** (L712-715):
```kotlin
val fullData = mutableListOf<Byte>()
for (key in sortedKeys) {
    fullData.addAll(fileState.chunks[key]!!.toList())
}
var data = fullData.toByteArray()
```

**问题**: `mutableListOf<Byte>()` + `addAll(toList())` 每次追加都产生临时 `List<Byte>`，且 `toByteArray()` 再做一次拷贝。对于 1MB 文件（~100 万 Byte），这意味着 **3 次内存分配 + 3 次全量拷贝**。

**建议**: 使用 `ByteArrayOutputStream`：
```kotlin
val bos = ByteArrayOutputStream(expectedSize)
for (key in sortedKeys) {
    bos.write(fileState.chunks[key]!!)
}
var data = bos.toByteArray()
```
内存分配从 O(n) 降为 O(log n)（内部自动扩容），省去 `toList()` 中间产物。

### 2.3 `RgbQrDecoder.decodeRgbQr()` 逐像素 `getPixel()` 调用

**现状** (L167-205): 双层循环中每像素调用 `bitmap.getPixel(x, y)`，这是 JNI 调用，开销大。

**建议**: 一次性取全部像素：
```kotlin
val pixels = IntArray(width * height)
qrBitmap.getPixels(pixels, 0, width, 0, 0, width, height)
// 然后直接用 pixels[y * width + x] 访问
```
实测可提速 **3-5x**（避免每像素 JNI 开销）。

### 2.4 `classifyColor()` 每像素遍历 8 候选色 + 创建临时 Pair 列表

**现状** (L270-300): 每个像素创建 8 个 `Pair<ColorClass, Triple>` 对象，遍历求 Manhattan 距离。

**问题**: 
- `candidates` 列表在每次调用时重新创建 → 对象分配开销
- 遍历 8 个候选色做 abs 计算 → 算术密集

**建议**:
1. 将 `candidates` 提取为 `companion object` 常量，避免重复分配
2. 更优：使用查表法。对于 256 级通道，预计算分类结果；或用阈值树：
```kotlin
// 快速路径：先检查灰度，快速分流黑/白
val brightness = r + g + b
if (brightness < 90) return ColorClass.BLACK
if (brightness > 680) return ColorClass.WHITE
// 再做精确分类
```

### 2.5 `processImage()` 节流逻辑有缺陷

**现状** (L437-442):
```kotlin
if (now - lastProcessTime < throttleMs) {
    imageProxy.close()
    return
}
lastProcessTime = now
```

**问题**: 
1. **ML Kit 处理未完成时也更新 `lastProcessTime`**，导致实际 FPS 被双重限制（80ms 节流 + ML Kit 处理耗时）
2. 若 ML Kit 处理慢（>80ms），节流没有实际作用，但仍丢弃帧
3. 应改为：仅在 `addOnCompleteListener` 后更新时间戳

**建议**: 改为"处理完成后才允许下一帧"模式：
```kotlin
private var isProcessing = false

private fun processImage(imageProxy: ImageProxy) {
    if (isProcessing) {
        imageProxy.close()
        return
    }
    isProcessing = true
    // ... 处理 ...
    .addOnCompleteListener {
        isProcessing = false
        imageProxy.close()
    }
}
```
这样 ML Kit 处理一完成立刻拿最新帧，零浪费。

---

## 三、架构/设计问题（P1 - 影响可维护性和正确性）

### 3.1 `MainActivity` 职责过重（God Activity）

**现状**: `MainActivity`（1145 行）承担了相机管理、扫码处理、文件组装、UI 状态切换、7z 解压、文件保存/分享等全部职责。

**建议**: 拆分为：
| 类 | 职责 |
|---|---|
| `QrCameraManager` | CameraX 初始化/绑定/解绑/生命周期 |
| `QrScanProcessor` | ML Kit 扫码 + 节流 + FPS |
| `FileAssembler` | 分块拼接 + 7z 解压 + CRC32 校验 |
| `MainActivity` | 仅 UI 编排 |

### 3.2 `BarcodeScanner` 实例未复用（RGB 路径）

**现状**: `MainActivity` 和 `RgbQrDecoder` 各自创建一个 `BarcodeScanner` 实例。

**问题**: ML Kit 的 `BarcodeScanner` 内部加载 TFLite 模型，创建开销大。`RgbQrDecoder` 每次 `decodeImage()` 都新建实例（被 `processGalleryImages` 中 `val decoder = RgbQrDecoder()` 触发）。

**建议**: 使用单例或依赖注入复用：
```kotlin
object QrScannerProvider {
    val monoScanner: BarcodeScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
    )
}
```

### 3.3 `RgbQrDecoder.decodeCanvas()` 串行逐格解码

**现状** (L104-128): 双层 for 循环中，每个格子串行调用 `decodeRgbQr()`。

**建议**: 使用协程并行解码网格中的 QR 码：
```kotlin
val deferredChunks = (0 until rows).flatMap { row ->
    (0 until cols).map { col ->
        async(Dispatchers.Default) {
            val qrBitmap = Bitmap.createBitmap(bitmap, col * cellSize, row * cellSize, cellSize, cellSize)
            val payload = decodeRgbQr(qrBitmap)
            qrBitmap.recycle()
            payload?.let { parsePayloadV2(it) }
        }
    }
}
deferredChunks.awaitAll().filterNotNull()
```

### 3.4 `fileState.chunks` 线程安全

**现状**: `fileState.chunks` 是 `mutableMapOf<Int, ByteArray>()`，在 `cameraExecutor` 线程写入（`processFileChunks`），在 Main 线程读取（`updateMultiFileProgress`），无同步。

**风险**: 理论上存在 `ConcurrentModificationException` 可能。当前因为 `STRATEGY_KEEP_ONLY_LATEST` + 串行 `cameraExecutor`，实际触发概率低，但非零。

**建议**: 改用 `ConcurrentHashMap` 或在写入时加锁。

### 3.5 `pendingData: ByteArray?` 持有大块内存

**现状** (L103): 解压后的完整文件内容作为 `ByteArray` 挂在 `pendingData` 上，直到用户选择保存或取消。

**问题**: 如果用户不操作，大文件（几十 MB）会一直留在内存中。

**建议**: 将解压数据写入临时文件，`pendingData` 只存 `File` 引用：
```kotlin
private var pendingTempFile: File? = null
```

### 3.6 `formatBytes()` 使用 `Int` 而非 `Long`

**现状** (L1078): `formatBytes(bytes: Int)` 最大只支持 ~2GB，且 `fileSize` 也是 `Int`。

**问题**: 无法处理 >2GB 文件。

**建议**: 统一改为 `Long`（当前 QR 码传输 >2GB 的场景极少，但 API 设计应预留）。

---

## 四、细节优化（P2 - 锦上添花）

### 4.1 FPS 计算不准确

**现状** (L463-468): FPS 基于两次检测间隔计算，但仅在 `barcodes.isNotEmpty()` 时更新，扫描但未识别到码时 FPS 显示不更新。

**建议**: 改用滑动窗口法：记录最近 N 帧的时间戳，FPS = N / (latest - earliest)。

### 4.2 `cameraExecutor` 使用 `Executors.newSingleThreadExecutor()`

**建议**: CameraX 1.4.x 推荐 `ContextCompat.getMainExecutor()` 或自定义 `HandlerExecutor`，以便在 `onDestroy` 时正确清理。当前实现在 `onDestroy` 中 `shutdown()` 是可以的，但如果 Activity 快速重建，可能出现竞态。

### 4.3 `setTargetResolution(Size(640, 480))` 已过时

**现状**: `setTargetResolution()` 在 CameraX 1.3+ 已标记为 `@Deprecated`。

**建议**: 改用 `setResolutionSelector()`：
```kotlin
val resolutionSelector = ResolutionSelector.Builder()
    .setResolutionStrategy(ResolutionStrategy(
        Size(640, 480),
        ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER
    ))
    .build()
ImageAnalysis.Builder()
    .setResolutionSelector(resolutionSelector)
    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
    .build()
```

### 4.4 `decompress7z()` 使用 `ByteArrayOutputStream` + 8KB buffer

**现状** (L836-841): 8KB buffer 偏小，对于大文件解压时频繁扩容。

**建议**: 若已知 entry 大小，用 `ByteArrayOutputStream(entry.size.toInt())`；或增大 buffer 到 64KB。

### 4.5 `LogCollector.log()` 同步写文件

**现状** (L44-60): 每条日志同步 `appendText()`，在 IO 线程执行时尚可，但 `cameraExecutor` 上的日志会阻塞分析器。

**建议**: 使用 `CoroutineScope(Dispatchers.IO)` 异步写文件，或用 `ArrayBlockingQueue` + 后台消费者线程。

### 4.6 `LogCollector.trimLogFile()` 全量读 + 写

**现状** (L79-89): 日志超 1MB 时 `file.readLines()` 全量读入再写回一半。

**建议**: 用 `RandomAccessFile` 或 `FileChannel` 截断文件尾部，避免全量读取。

### 4.7 RGB `decodeRgbQr()` 中通道 Bitmap 使用 ARGB_8888

**现状** (L209-211): 三通道分离后生成 `ARGB_8888` Bitmap，每像素 4 字节。

**建议**: 因为通道图只有黑/白两色，使用 `ALPHA_8`（1 字节/像素）即可，内存省 75%。ML Kit 的 `InputImage.fromBitmap()` 支持 `ALPHA_8`。

---

## 五、问题汇总表

| # | 优先级 | 问题 | 位置 | 预估收益 |
|---|--------|------|------|----------|
| 2.1 | P0 | RGB 模式未接入相机实时流 | `processImage()` | 功能修复 |
| 2.2 | P0 | `assembleFile` 逐字节拼ByteArray | L712-715 | 内存-60%，速度+3x |
| 2.3 | P0 | RGB 逐像素 `getPixel()` JNI开销 | `decodeRgbQr()` L169 | 速度+3~5x |
| 2.4 | P0 | `classifyColor` 每次重建候选列表 | L275-284 | 对象分配-87.5% |
| 2.5 | P0 | 节流逻辑导致帧浪费 | `processImage()` L437 | 实际FPS+30% |
| 3.1 | P1 | God Activity，职责过重 | `MainActivity` 全局 | 可维护性 |
| 3.2 | P1 | BarcodeScanner 未复用 | `RgbQrDecoder` L41 | 初始化时间-2x |
| 3.3 | P1 | Canvas 串行解码 | `decodeCanvas()` | 速度+N倍(N=格子数) |
| 3.4 | P1 | chunks Map 线程不安全 | `FileReceiveState` L17 | 崩溃风险 |
| 3.5 | P1 | pendingData 大文件常驻内存 | L103 | 内存-文件大小 |
| 3.6 | P1 | fileSize 用 Int 限制 2GB | 多处 | API健壮性 |
| 4.1 | P2 | FPS 计算不准确 | L463-468 | 用户体验 |
| 4.2 | P2 | cameraExecutor 重建竞态 | L91 | 稳定性 |
| 4.3 | P2 | setTargetResolution 已弃用 | L312 | API 合规 |
| 4.4 | P2 | 7z 解压 buffer 太小 | L837 | 解压速度+20% |
| 4.5 | P2 | LogCollector 同步写文件 | `log()` L53 | IO延迟 |
| 4.6 | P2 | 日志 trim 全量读写 | `trimLogFile()` | IO |
| 4.7 | P2 | 通道 Bitmap 用 ARGB_8888 太浪费 | L209-211 | 内存-75% |

---

## 六、推荐优化顺序

1. **2.5** 节流改为 `isProcessing` 标志位 → 立竿见影的扫描流畅度提升
2. **2.3** + **2.4** RGB 解码批量化 `getPixels` + 候选色常量化 → RGB 路径核心瓶颈
3. **2.2** `assembleFile` 改用 `ByteArrayOutputStream` → 大文件组装加速
4. **3.4** `chunks` 改用 `ConcurrentHashMap` → 消除潜在崩溃
5. **3.2** `BarcodeScanner` 单例复用 → 减少 RGB 路径初始化时间
6. 其余按优先级逐步推进

---

*报告由 Nix 生成，基于源码静态分析，未做运行时 profiling。建议结合 Android Profiler 实测验证。*
