# V2 — B&W Configurable (可配置版本黑白二维码)

## Overview

An enhanced version of the B&W QR generator that introduces a configurable `--ver` parameter to set the QR version (1-40), with `QR_MAX_BYTES` and all derived constants automatically calculated from the version.

## Motivation

The original V1 hardcodes several interdependent constants:

```python
MAX_QR_VER = 32
QR_MAX_BYTES = 1865
ROWS = math.floor(CANVAS_H / ((4 * MAX_QR_VER + 17) * BOX_SIZE + 24))
COLS = math.floor(CANVAS_W / ((4 * MAX_QR_VER + 17) * BOX_SIZE + 24))
```

All of these derive from `MAX_QR_VER`, yet `QR_MAX_BYTES` was set independently (and conservatively at 1865 vs the true capacity of 1952 bytes for v32/L). Changing the QR version required manually recalculating every derived value, which is error-prone.

## Design Decisions

### 1. Automatic QR_MAX_BYTES Calculation

Reverse-engineered the `qrcode` library's internal data structure (`RS_BLOCK_TABLE` in `qrcode.base`) to compute exact capacity programmatically:

```python
def calc_qr_max_bytes(ver, error_correction=ERROR_L):
    blocks = rs_blocks(ver, error_correction)
    total_data_codewords = sum(b.data_count for b in blocks)
    header_bits = 4 + (8 if ver <= 9 else 16)
    return (total_data_codewords * 8 - header_bits) // 8
```

Validated empirically against actual `qrcode` library limits:

| Version | Formula | Empirical | Match |
|---------|---------|-----------|-------|
| 10 | 271 | 271 | Yes |
| 20 | 858 | 858 | Yes |
| 32 | 1,952 | 1,952 | Yes |
| 40 | 2,953 | 2,953 | Yes |

### 2. QRConfig Class

Bundles all derived constants into a single object:

```python
class QRConfig:
    def __init__(self, ver=32):
        self.ver = ver
        self.qr_max_bytes = calc_qr_max_bytes(ver)
        self.rows = math.floor(CANVAS_H / ((4 * ver + 17) * BOX_SIZE + 24))
        self.cols = math.floor(CANVAS_W / ((4 * ver + 17) * BOX_SIZE + 24))
        self.qr_per_image = self.rows * self.cols
        self.data_per_qr = self.qr_max_bytes - 8
```

### 3. argparse CLI

Exposes all parameters via command line:

```bash
python -m qrcast.bw.v2.generator <file> --ver 20 --output-dir ./tmp --compress --save-chunks
```

## Capacity Reference

| ver | max_bytes | rows x cols | QR/canvas | bytes/canvas |
|-----|-----------|-------------|-----------|-------------|
| 10 | 271 | 5 x 9 | 45 | ~11,895 |
| 15 | 520 | 4 x 7 | 28 | ~14,000 |
| 20 | 858 | 3 x 5 | 15 | ~12,030 |
| 25 | 1,273 | 2 x 4 | 8 | ~9,864 |
| 32 | 1,952 | 2 x 4 | 8 | ~15,056 |
| 40 | 2,953 | 1 x 3 | 3 | ~8,535 |

The total throughput per canvas is **not monotonic** with version — a mid-range version like 15 or 32 packs more data per canvas than v40, because smaller QR codes allow many more per canvas.

**Recommendation**: Use ver 15-25 for screen-to-camera transfer; use ver 32-40 if camera resolution is the bottleneck.

## Quick Sender

A companion tool for sending small files via a single QR code:

```bash
python -m qrcast.bw.v2.quick_sender myscript.py --minify --ver 40
```

The `--minify` flag strips comments and docstrings from Python files before encoding, often reducing size by 30-50%.

## Files

| File | Path | Purpose |
|------|------|---------|
| Generator | `qrcast/bw/v2/generator.py` | Configurable version generator |
| Quick Sender | `qrcast/bw/v2/quick_sender.py` | Single-QR sender for small files |
| Verifier | `qrcast/bw/verifier.py` | Whole-image verifier (V1 & V2 compatible) |

## Differences from V1

| Aspect | V1 | V2 |
|--------|----|----|
| QR version | Hardcoded `MAX_QR_VER=32` | `--ver` CLI arg, default 32 |
| QR_MAX_BYTES | Hardcoded 1865 (conservative) | Auto-calculated from `rs_blocks` (exact) |
| Derived constants | Global module-level | `QRConfig` instance |
| Function signatures | `make_qr(data)` | `make_qr(data, qr_cfg)` |
| CLI | Hardcoded paths in `__main__` | `argparse` with all parameters |
| Quick sender | Not available | `quick_sender.py` for small files |

## Bug Fix: Dense Grid Detection

When QR codes are tiled edge-to-edge with zero gap, zxingcpp's multi-barcode scanner can miss codes in dense grids. The generic verifier (`qrcast/bw/verifier.py`) adds a **horizontal strip scanning fallback**:

1. **Phase 1**: Whole-image scan (fast, finds most codes)
2. **Phase 2**: If chunk count < total, scan horizontal strips with overlap

This fix is backward-compatible with V1 generated images.
