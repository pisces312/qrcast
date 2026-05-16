# V3 — RGB QR (彩色二维码)

## Overview

Uses the [qrgb](https://pypi.org/project/qrgb/) library to encode data across three color channels (R, G, B), achieving approximately **3x data density** per QR code compared to standard black-and-white QR codes.

## How RGB QR Works

A standard QR code stores binary data in black/white modules. An RGB QR code extends this to 8 colors by encoding 3 independent bit streams (one per channel) in the same physical space:

```
Standard QR:  1 bit per module (black/white)
RGB QR:       3 bits per module (8 colors)
```

### Color Mapping

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

### Channel Separation (Decoding)

To decode an RGB QR code, each color channel is extracted as a separate B&W image:

- **R channel** is "black" (has data) in: BLACK, YELLOW, MAGENTA, RED
- **G channel** is "black" (has data) in: BLACK, YELLOW, CYAN, GREEN
- **B channel** is "black" (has data) in: BLACK, MAGENTA, CYAN, BLUE

Extraction uses vectorized numpy with Manhattan distance and tolerance:

```python
def extract_channel(img_array, channel_colors, tolerance=30):
    mask = np.zeros((h, w), dtype=bool)
    for color in channel_colors:
        diff = np.abs(img_array.astype(np.int16) - color.astype(np.int16))
        dist = diff.sum(axis=2)
        mask |= (dist <= tolerance)
    return np.where(mask, 0, 255).astype(np.uint8)
```

Each extracted B&W image is then decoded as a standard QR code via zxingcpp.

## Two Sub-Modes

### Text Mode (base64)

Encodes chunk as `SEQ:TOTAL:base64data` text payload.

- **Pros**: Human-readable payload format, easy to debug
- **Cons**: Base64 adds ~33% overhead (3 raw bytes → 4 text chars)
- **Capacity**: ~5,229 data bytes per QR

```
Text -> base64 -> pad to multiple of 3 -> split into R/G/B -> encode 3 QR codes -> render colors
```

### Binary Mode (raw) — Recommended

Direct binary payload, no base64 overhead.

- **Pros**: ~33% more efficient than text mode
- **Cons**: Binary payload is harder to debug
- **Capacity**: ~6,983 data bytes per QR (ver 32)

```
Raw bytes -> pad to multiple of 3 -> split into R/G/B -> encode 3 QR codes -> render colors
```

Payload format:
```
[ seq (4B) ][ total (4B) ][ data_len (2B) ][ raw chunk bytes ][ padding ]
```

`data_len` tells the decoder the exact chunk size so padding can be stripped.

## Layout

RGB QR codes are larger (v32 = 447 pixels, v40 = 555 pixels), so only 3 fit per canvas:

```
rows = floor(1000 / 555) = 1
cols = floor(1850 / 555) = 3
qr_per_canvas = 1 * 3 = 3
```

## Files

| File | Path | Purpose |
|------|------|---------|
| Text Generator | `qrcast/v3/generator_text.py` | RGB QR generator (base64) |
| Binary Generator | `qrcast/v3/generator_bin.py` | RGB QR generator (raw binary) |
| Text Receiver | `qrcast/v3/receiver_text.py` | Camera receiver (base64) |
| Binary Receiver | `qrcast/v3/receiver_bin.py` | Camera receiver (raw binary) |
| Text Verifier | `qrcast/v3/verifier_text.py` | Offline verifier (base64) |
| Binary Verifier | `qrcast/v3/verifier_bin.py` | Offline verifier (raw binary) |

## Usage

```bash
# Generate RGB QR (binary mode — recommended)
python -m qrcast.v3.generator_bin myfile.zip --output-dir ./tmp

# Display
python -m qrcast.common ./tmp --interval 3

# Receive via camera (binary mode)
python -m qrcast.v3.receiver_bin --camera 0

# Verify saved images (binary mode)
python -m qrcast.v3.verifier_bin ./tmp ./verify_output
```

## Comparison with B&W

| Metric | B&W V2 (ver 32) | RGB V3 Binary (ver 32) |
|--------|-----------------|------------------------|
| Bytes per QR | 1,952 | 6,983 |
| QR per canvas | 8 | 3 |
| Bytes per canvas | ~15,056 | ~20,949 |
| Error correction | L | M |
| Camera tolerance | Medium | Lower (color noise) |
| Decode complexity | Low | Higher (3 channels) |

## Recommendations

- **Use RGB Binary** when you need maximum throughput and have a high-quality camera
- **Use B&W V2 ver 15-25** when reliability is more important than raw speed
- RGB QR is more sensitive to camera noise and color distortion — ensure good lighting
- The tolerance parameter (default 30 for verify, 50 for camera) can be adjusted for noisy conditions
