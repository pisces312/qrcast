# Architecture

## System Overview

qrcast transfers files by encoding them into visual QR code grids that can be captured by a camera. It works entirely offline — no Bluetooth, Wi-Fi, or cable required.

```
+-----------+      +----------+      +----------+      +----------+
|   File    | ---> | Compress | ---> |  Chunk   | ---> |  Encode  |
+-----------+      +----------+      +----------+      +----------+
                                                              |
                                                              v
+-----------+      +----------+      +----------+      +----------+
|  Extract  | <--- | Assemble | <--- | Decode   | <--- |  Capture |
+-----------+      +----------+      +----------+      +----------+
```

## Three Architectures

### V1 — B&W Fixed

- **Generator**: Fixed QR version 32, `ERROR_CORRECT_L`
- **Layout**: Grid of 6 rows x 11 cols = 66 QR per canvas
- **Decoder**: Grid-splitting (known dimensions) or whole-image detection
- **Capacity**: ~122 KB per canvas

### V2 — B&W Configurable

- **Generator**: Configurable QR version 1-40, auto-calculated capacity
- **Layout**: Dynamic grid based on QR pixel size
- **Decoder**: Whole-image detection with strip-scanning fallback
- **Capacity**: Varies with version; optimal around ver 15-32

### V3 — RGB QR

- **Generator**: Uses `qrgb` library to encode across R/G/B channels
- **Layout**: 1 row x 3 cols = 3 QR per canvas (each QR is larger)
- **Decoder**: Channel separation via vectorized numpy, then zxingcpp per channel
- **Capacity**: ~21 KB per canvas (binary mode)

## Shared Constants

All versions share:

| Constant | Value | Description |
|----------|-------|-------------|
| `CANVAS_W` | 1850 | Canvas width in pixels |
| `CANVAS_H` | 1000 | Canvas height in pixels |
| `BOX_SIZE` | 3 | Pixels per QR module |
| `BORDER` | 4 | QR quiet zone in modules |

## QR Pixel Size Calculation

```
modules_per_side = 4 * version + 17          # per QR spec
pixel_size = modules_per_side * BOX_SIZE + 2 * BORDER * BOX_SIZE
           = (4 * ver + 17) * 3 + 24
```

## Grid Layout

```
rows = floor(CANVAS_H / pixel_size)
cols = floor(CANVAS_W / pixel_size)
qr_per_canvas = rows * cols
```

## Capacity Comparison

| System | Version | Error Correction | Bytes/QR | QR/Canvas | Bytes/Canvas |
|--------|---------|-----------------|----------|-----------|-------------|
| B&W V1 | 32 | L | 1,857 | 66 | ~122,562 |
| B&W V2 | 20 | L | 858 | 15 | ~12,870 |
| B&W V2 | 32 | L | 1,952 | 8 | ~15,616 |
| RGB Text | 40 | M | ~5,229 | 3 | ~15,687 |
| RGB Binary | 32 | M | **6,983** | 3 | **~20,949** |

## Payload Formats

### B&W QR (V1 & V2)

```
[ seq (4 bytes, big-endian) ]
[ total_chunks (4 bytes, big-endian) ]
[ payload bytes ... ]
```

Total header: 8 bytes.

### RGB QR Text (V3 base64)

```
"SEQ:TOTAL:base64_encoded_chunk"
```

The text is padded to a multiple of 3 characters, then split equally across R/G/B channels. On decode, channels are recombined and the qrgb `PAD_CHAR` is stripped.

### RGB QR Binary (V3 raw)

```
[ seq (4 bytes, big-endian) ]
[ total_chunks (4 bytes, big-endian) ]
[ data_len (2 bytes, big-endian) ]
[ raw chunk bytes ... ]
[ padding (0-2 bytes) ]
```

Total header: 10 bytes. `data_len` stores the exact chunk size so the decoder can strip zero-padding introduced by the 3-way channel split.

## Channel Separation (RGB Decode)

RGB QR decoding works by extracting each color channel into a separate B&W image:

- **R channel black** in pixels: BLACK, YELLOW, MAGENTA, RED
- **G channel black** in pixels: BLACK, YELLOW, CYAN, GREEN
- **B channel black** in pixels: BLACK, MAGENTA, CYAN, BLUE

Channel extraction uses vectorized numpy (Manhattan distance with tolerance), then each B&W image is decoded as a standard QR code via zxingcpp.

### Color Mapping

qrgb's `render_color` function maps 8 combinations of R/G/B module states to 8 colors:

| R | G | B | Color | RGB Value |
|---|---|---|-------|-----------|
| 0 | 0 | 0 | Black | (0, 0, 0) |
| 0 | 0 | 1 | Blue | (0, 0, 255) |
| 0 | 1 | 0 | Green | (0, 255, 0) |
| 0 | 1 | 1 | Cyan | (0, 255, 255) |
| 1 | 0 | 0 | Red | (255, 0, 0) |
| 1 | 0 | 1 | Magenta | (255, 0, 255) |
| 1 | 1 | 0 | Yellow | (255, 255, 0) |
| 1 | 1 | 1 | White | (255, 255, 255) |

## False Positive Filtering

Both receivers and verifiers filter out spurious QR decodes using majority vote on `total_chunks`:

1. Collect all decoded payloads
2. Take the most common `total` value as consensus
3. Discard any code where `total != consensus` or `seq >= total`

This handles cases where the decoder accidentally reads a partial or corrupted QR code.

## Strip Scanning Fallback (V2 Verifier)

When QR codes are tiled edge-to-edge with zero gap, zxingcpp's multi-barcode scanner can miss codes in dense grids. The verifier adds a fallback:

1. **Phase 1**: Whole-image scan (fast, finds most codes)
2. **Phase 2**: If chunk count < total, scan horizontal strips with 50% overlap

Strip height is derived from detected QR code heights, requiring no knowledge of the grid layout.

## Compression

Optional 7z compression (LZMA2 preset 9) is applied before chunking. This is most effective for text files, source code, and documents. Already-compressed files (images, videos, archives) see little benefit and may slightly increase in size.
