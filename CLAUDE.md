# QRCast — Sender (Python)

QR-based offline file transfer tool. Generates b&w (v2) and color RGB (v3) QR code canvases/individual images, verifies and reconstructs files.

## Environment
- **Python**: `D:\nili\dev\conda_envs\qrcast_env\python.exe` (conda env: qrcast_env, Python 3.11)
- All scripts, tests, and CLI commands MUST use this Python, not system/conda-base python
- Install deps: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pip install <pkg>`
- Run tests: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pytest tests/ -v`

## Project Structure
```
qrcast/
  qrcast/
    bw/           # v2: B&W QR (configurable ver 1-40)
      generator.py, generator2.py  # generate_qr_images
      display.py                   # display_individual_qr
      quick_sender.py              # single-QR send
      verifier.py, verifier2.py    # verify & reconstruct
      receiver.py, receiver2.py    # camera receive
    rgb/          # v3: RGB color QR (was qrcast/v3/)
      generator_bin.py, generator_bin2.py, generator_text.py
      verifier_bin.py, verifier_bin2.py, verifier_text.py
      receiver_bin.py, receiver_bin2.py, receiver_text.py
    common.py     # shared: CANVAS_W/H, parse_payload_v2, etc.
    cli.py        # unified CLI: qrcast generate|display|verify|receive|quick-send
  tests/
    test_v2_roundtrip.py  # 25 unit tests (all pass)
```

## CLI Usage
```bash
# Generate (v2 b&w, ver 30 recommended for phone)
qrcast generate v2 FILE --ver 30 --mode individual --output-dir ./tmp

# Display for phone scanning
qrcast display ./tmp/FILE-individual --mode individual -i 0.1

# Quick single-QR send (small files)
qrcast quick-send FILE

# Verify & reconstruct
qrcast verify ./tmp ./output --version v2
```

## Dependency Notes
- `qrgb` library required for v3 (RGB color) mode — installed in qrcast_env
- v3 tests skip gracefully if qrgb unavailable (`HAS_V3 = False`)
