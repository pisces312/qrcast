# qrcast / 码上通

File transfer via QR codes. No network required — just light.

通过二维码实现文件传输。无需网络，只要有光即可。

---

## Overview

qrcast encodes files into a sequence of QR code canvases displayed on screen. A receiver (another computer, phone, or camera) captures these images and reconstructs the original file.

This is useful when:
- You have no network between two devices
- Air-gapped environments
- Quick one-way data transfer across screens

## Three Versions

| Version | Name | Description | Data/QR | QR/Canvas | Bytes/Canvas |
|---------|------|-------------|---------|-----------|-------------|
| **V1** | B&W Fixed | Fixed QR ver 32, grid-based decode | ~1,857 B | 66 (6x11) | ~122 KB |
| **V2** | B&W Configurable | Configurable ver 1-40, auto capacity | varies | varies | varies |
| **V3** | RGB QR | 3 color channels (R/G/B) for ~3x density | ~6,983 B | 3 (1x3) | ~21 KB |

### V1 — B&W Fixed (固定版本)

The original implementation. Uses QR version 32 with `ERROR_CORRECT_L`, fixed at 66 QR codes per 1850x1000 canvas.

```bash
# Generate
python scripts/v1_generate.py <file> --output-dir ./tmp

# Display
python scripts/display.py ./tmp

# Receive (camera)
python -m qrcast.bw.receiver --camera 0

# Verify (without camera)
python scripts/v2_verify.py ./tmp ./verify_output
# or use grid-based verifier:
python scripts/v1_verify_grid.py ./tmp ./verify_output
```

### V2 — B&W Configurable (可配置版本)

Adds a `--ver` parameter to control QR version (1-40). Automatically calculates capacity from the version. Includes a quick sender for small files.

```bash
# Generate with custom version
python scripts/v2_generate.py <file> --ver 20 --output-dir ./tmp

# Quick send (single QR, small files only)
python scripts/v2_quick_send.py <small_file> --minify

# Receive and verify — same as V1
python -m qrcast.bw.receiver --camera 0
python scripts/v2_verify.py ./tmp ./verify_output
```

### V3 — RGB QR (彩色二维码)

Uses the [qrgb](https://pypi.org/project/qrgb/) library to encode data across R/G/B color channels, achieving ~3x data density per QR code.

Two sub-modes:
- **Text (base64)**: Encodes chunk as `SEQ:TOTAL:base64data` text payload
- **Binary (raw)**: Direct binary payload, no base64 overhead (~33% more efficient)

```bash
# Generate RGB QR (text mode)
python scripts/v3_generate_text.py <file> --output-dir ./tmp

# Generate RGB QR (binary mode — recommended)
python scripts/v3_generate_bin.py <file> --output-dir ./tmp

# Display (same displayer works)
python scripts/display.py ./tmp

# Receive (text mode)
python -m qrcast.v3.receiver_text --camera 0

# Receive (binary mode)
python -m qrcast.v3.receiver_bin --camera 0

# Verify (text mode)
python scripts/v3_verify_text.py ./tmp ./verify_output

# Verify (binary mode)
python scripts/v3_verify_bin.py ./tmp ./verify_output
```

## Installation

### Option A: Conda

```bash
conda env create -f env.yml
conda activate qrcast_env
```

### Option B: pip

```bash
pip install -r requirements.txt
```

## Project Structure

```
qrcast/
├── qrcast/                 # Python package
│   ├── __init__.py
│   ├── common.py           # Shared utilities (display, compression, payload)
│   ├── pyminify.py         # Python code minifier (for quick sender)
│   ├── camera_test.py      # Camera diagnostics
│   ├── bw/                 # Black-and-white QR (V1 & V2)
│   │   ├── __init__.py
│   │   ├── receiver.py         # B&W QR receiver (V1 & V2)
│   │   ├── verifier.py         # B&W QR verifier (whole-image, V1 & V2)
│   │   ├── v1/
│   │   │   ├── generator.py        # Fixed ver32 generator
│   │   │   └── verifier_grid.py    # Grid-based verifier
│   │   └── v2/
│   │       ├── generator.py        # Configurable generator
│   │       └── quick_sender.py     # Single-QR quick sender
│   └── v3/
│       ├── generator_text.py   # RGB QR generator (base64)
│       ├── generator_bin.py    # RGB QR generator (raw binary)
│       ├── receiver_text.py    # RGB QR receiver (base64)
│       ├── receiver_bin.py     # RGB QR receiver (raw binary)
│       ├── verifier_text.py    # RGB QR verifier (base64)
│       └── verifier_bin.py     # RGB QR verifier (raw binary)
├── scripts/                # CLI entry points
│   ├── v1_generate.py
│   ├── v1_verify_grid.py
│   ├── v2_generate.py
│   ├── v2_quick_send.py
│   ├── v2_verify.py
│   ├── v3_generate_text.py
│   ├── v3_generate_bin.py
│   ├── v3_verify_text.py
│   ├── v3_verify_bin.py
│   ├── display.py
│   └── test_camera.py
├── docs/                   # Documentation
│   ├── architecture.md
│   ├── v1_bw_fixed.md
│   ├── v2_bw_configurable.md
│   └── v3_rgb_qr.md
├── env.yml
├── requirements.txt
├── LICENSE
└── README.md
```

## Payload Formats

### B&W QR (V1 & V2)

Each QR code carries: `[seq (4B big-endian)][total_chunks (4B big-endian)][payload bytes]`

Header is 8 bytes.

### RGB QR Text (V3 base64)

Each RGB QR code carries text: `SEQ:TOTAL:base64_encoded_chunk`

Text is padded to multiple of 3, split equally across R/G/B channels.

### RGB QR Binary (V3 raw)

Each RGB QR code carries: `[seq (4B)][total_chunks (4B)][data_len (2B)][raw chunk bytes][padding]`

Header is 10 bytes. `data_len` tells the decoder the exact chunk size.

## How It Works

1. **Sender** reads a file, optionally compresses with 7z (LZMA2 preset 9), splits into chunks, encodes each chunk into QR codes, and tiles them into canvas PNGs.
2. **Displayer** shows the canvas PNGs fullscreen at a configurable interval.
3. **Receiver** captures camera frames, detects all QR codes, extracts payload chunks, deduplicates, and assembles the file when all chunks are received.
4. **Verifier** reads saved canvas PNGs (no camera needed) and reconstructs the file for testing.

## Notes

- Canvas size is fixed at **1850x1000** pixels to maximize screen real-estate on typical displays.
- V1/V2 use `ERROR_CORRECT_L` for maximum capacity.
- V3 uses `ERROR_CORRECT_M` for better reliability with color channel separation.
- Camera receivers default to 1920x1080 resolution. Adjust `cv2.CAP_PROP_FRAME_*` if needed.

## License

MIT License — see [LICENSE](LICENSE)
