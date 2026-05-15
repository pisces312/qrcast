# V1 — B&W Fixed (固定版本黑白二维码)

## Overview

The original implementation of qrcast. Uses a fixed QR version 32 with `ERROR_CORRECT_L`, arranged in a dense 6x11 grid on each canvas.

## Design Decisions

### Fixed Version 32

Version 32 was chosen as a balance between:
- **Capacity per QR**: 1,857 bytes (with 8-byte header → 1,849 data bytes)
- **QR size**: 159 pixels per side
- **Grid density**: 66 QR codes per 1850x1000 canvas
- **Total throughput**: ~122 KB per canvas

### Grid Layout

```
rows = floor(1000 / 159) = 6
cols = floor(1850 / 159) = 11
qr_per_canvas = 6 * 11 = 66
```

### Payload Format

```
[ seq (4B big-endian) ]
[ total_chunks (4B big-endian) ]
[ payload bytes ... ]
```

## Files

| File | Path | Purpose |
|------|------|---------|
| Generator | `qrcast/bw/v1/generator.py` | Create QR canvases from file |
| Grid Verifier | `qrcast/bw/v1/verifier_grid.py` | Decode using known grid dimensions |
| CLI Generate | `scripts/v1_generate.py` | Entry point for generation |
| CLI Verify Grid | `scripts/v1_verify_grid.py` | Entry point for grid verification |

## Usage

```bash
# Generate QR canvases
python scripts/v1_generate.py myfile.zip --output-dir ./tmp --compress

# Display on screen
python scripts/display.py ./tmp --interval 3

# Receive via camera (generic receiver)
python -m qrcast.bw.receiver --camera 0

# Verify saved images (whole-image)
python scripts/v2_verify.py ./tmp ./verify_output

# Verify saved images (grid-based, V1 original)
python scripts/v1_verify_grid.py ./tmp ./verify_output
```

## Why Grid-Based Verifier?

The grid-based verifier (`verifier_grid.py`) knows the exact pixel dimensions of each QR code and crops the image into a grid before decoding. This was the original approach and is still useful for:

- **Debugging**: Isolates individual QR codes
- **Comparison**: Benchmarking against whole-image detection
- **Compatibility**: Works with images that whole-image detection might miss

However, the generic whole-image verifier (`qrcast/bw/verifier.py`) is recommended for everyday use as it handles dense grids better with its strip-scanning fallback.

## Limitations

- Fixed at version 32 — cannot tune for different screen/camera resolutions
- Grid layout is hardcoded — not adaptable to different canvas sizes
- Dense grid can challenge some QR decoders when tiles are edge-to-edge
