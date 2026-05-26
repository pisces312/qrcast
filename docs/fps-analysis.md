# QRCast Android 扫描帧率分析

## 管道架构

```
display 脚本放 QR
    ↓
CameraX 预览帧 (30fps 默认)
    ↓
throttle(80ms) → 节流至最高 12.5fps
    ↓
KEEP_ONLY_LATEST → ML Kit 忙时丢弃中间帧
    ↓
ML Kit BarcodeScanning (QR_CODE only)
    ↓
ImageAnalysis 分辨率: 640×480
    ↓
onDetect() → UI 更新
```

## 各环节耗时

| 环节 | 耗时 | 理论吞吐 |
|------|------|----------|
| CameraX 帧供 | ~33ms/帧 | 30 fps |
| throttle | 80ms 最小间隔 | 12.5 fps |
| ML Kit 处理 | **33ms** (实测) | **30 fps** |
| display 端播放 | 200ms/帧 (用户端) | 5 fps |

## 实测数据 (2026-05-26)

- 扫描间隔: ~204ms
- 实际 FPS: **4.9**
- ML Kit 单帧: **33ms**

## 瓶颈分析

**瓶颈在 display 端，不在 Android 端。**

Android 端理论可达 12.5 fps（受 throttle 限制）或 30 fps（ML Kit 处理速度上限）。
当前 display 端以 ~5fps 播放 QR 码，Android 端完全跟得上。

## 优化历史

| 日期 | 改动 | 效果 |
|------|------|------|
| 2026-05-26 | QR_CODE only（跳过 PDF417/EAN） | 减少无谓格式检测 |
| 2026-05-26 | ImageAnalysis 640×480 | 像素量降至 ~1/4 |
| 2026-05-26 | throttleMs 200→80 | 从 5fps 提高到 12.5fps 上限 |
| 2026-05-26 | FPS 实时显示 | 可视化性能数据 |

## 进一步优化方向

1. **throttleMs 降到 33ms** — 匹配 ML Kit 33ms 处理速度，理论上限 30fps
2. **分辨率降到 480×360** — 进一步减少像素，QR 码通常不需要 640×480
3. **display 端增速** — 当前是主要瓶颈，改到 10fps 即可翻倍传输速度
