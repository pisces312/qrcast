# UI 设计决策记录

> 2026-05-26 讨论结论

## 扫描框

| 决策 | 理由 |
|---|---|
| 正方形 1:1，100% 屏宽 | QR 码天生正方形，正方形取景框适配竖屏/横屏旋转；100% 屏宽将二维码放到最大 |
| 居中（四向约束到 parent） | 直觉对齐，用户自然将 QR 码对准中心 |
| `scan_frame.xml`：teal 3dp 描边 + 16dp 圆角 | 视觉层级清晰，不遮挡二维码 |

## scanHint / scanFps 布局

| 元素 | 位置 | 字号/颜色 |
|---|---|---|
| scanHint "对准二维码" | 扫描框正上方 | 16sp / white |
| scanFps "扫描 XXfps XXms" | 扫描框正下方 | 18sp / #5DCAA5 |

- scanFps 仅在 ML Kit 成功识别到二维码时更新，非逐帧刷新
- FPS 计算: `1000 / interval`（两次成功检测之间的间隔），clamp 到 0.1~60

## 横屏适配

- **不创建** `layout-land/` 目录
- `sourcePanel` 外层用 `ScrollView` 包裹 + `fillViewport="true"`
- 竖屏时居中显示，横屏内容超出时自动可滚动

## 图像分析

| 项目 | 值 |
|---|---|
| 输入路径 | `InputImage.fromMediaImage()` 直传，不做手动 crop |
| 目标分辨率 | `setTargetResolution(Size(640, 480))` |
| 节流 | 80ms（~12.5fps 分析频率） |
| 后置摄像头 | `CameraSelector.DEFAULT_BACK_CAMERA` |

**为什么不手动裁剪**：实测相机输出 960×1080，宽高比约 0.89，已接近方形，手动 NV21 crop 没有实质收益。

## ML Kit 配置

- `BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE)` — 只检测 QR 码
- rotation 参数正确传入 `fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)`

## 扫描进度面板 (detailPanel)

- 识别到第一个分块时 `showReceiving()` 设为 VISIBLE
- 首次激活时填入占位文本（"正在接收..." / "已收到: --" / "缺失: --"），后续 `updateMultiFileProgress()` 覆盖实际数据
- 字体: fileInfoText 16sp bold, receivedChunksText 15sp, missingChunksText 15sp, fileMetaText 13sp

## 来源选择面板 (sourcePanel)

- 外层 `ScrollView`，内部 LinearLayout 居中
- 按钮高度 160dp，平分宽度
- 代码中 sourcePanel 类型为 `ScrollView`（`MainActivity.kt`）
