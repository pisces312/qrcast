"""V3 RGB QR code generator (raw binary, no base64 overhead).

File -> optional 7z compress -> chunk -> raw binary into 3 QR channels -> RGB canvases (PNG).

Uses qrgb's color rendering to encode raw bytes into 3 color channels (R, G, B).
Each channel carries raw binary via QR byte mode — no base64 overhead.

Payload format: [seq(4B)][total(4B)][data_len(2B)][raw chunk bytes][padding]
data_len tells decoder exact chunk size so padding from 3-way split can be stripped.
"""

import math
import os
import sys

import numpy as np
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M
from qrcode.main import QRCode

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER

# qrgb is required for generation
try:
    from qrgb.qrgb import render_color, QR_CAPACITIES
except ImportError as e:
    raise ImportError("qrgb library is required for V3 generation. Install: pip install qrgb") from e

# ===================== Core Config =====================
MAX_QR_VER = 32
CHANNEL_CAPACITY = QR_CAPACITIES[MAX_QR_VER]  # 2331
HEADER_LEN = 10  # seq(4) + total(4) + data_len(2)
DATA_PER_QR = CHANNEL_CAPACITY * 3 - HEADER_LEN  # 6983

CELL_SIZE = (4 * MAX_QR_VER + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE  # 555
COLS = CANVAS_W // CELL_SIZE  # 3
ROWS = CANVAS_H // CELL_SIZE  # 1
QR_PER_IMAGE = ROWS * COLS  # 3

print(f"CELL_SIZE: {CELL_SIZE}, ROWS: {ROWS}, COLS: {COLS}, QR_PER_IMAGE: {QR_PER_IMAGE}")
print(f"CHANNEL_CAPACITY: {CHANNEL_CAPACITY}, DATA_PER_QR: {DATA_PER_QR}")


def make_mono_qr(data_bytes, version):
    """Generate a mono (black/white) QR code image from raw bytes."""
    qr = QRCode(
        version=version,
        error_correction=ERROR_CORRECT_M,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    img = qr.make_image()
    img = img.convert("L").point(lambda p: 0 if p < 128 else 255)
    return img


def find_version(chunk_size):
    """Find minimum QR version that fits chunk_size bytes."""
    for ver, cap in QR_CAPACITIES.items():
        if chunk_size <= cap:
            return ver
    raise ValueError(f"Data too large: {chunk_size} bytes exceeds max QR capacity")


def make_rgb_qr_image(payload_bytes):
    """Create an RGB QR code PIL image from raw binary payload."""
    pad_len = (3 - len(payload_bytes) % 3) % 3
    padded = payload_bytes + b"\x00" * pad_len
    chunk_size = len(padded) // 3

    r_data = padded[:chunk_size]
    g_data = padded[chunk_size:2 * chunk_size]
    b_data = padded[2 * chunk_size:]

    version = find_version(chunk_size)

    r_img = make_mono_qr(r_data, version)
    g_img = make_mono_qr(g_data, version)
    b_img = make_mono_qr(b_data, version)

    r_arr = np.array(r_img)
    g_arr = np.array(g_img)
    b_arr = np.array(b_img)

    height, width = r_arr.shape
    color_img = np.zeros((height, width, 3), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            color_img[y, x] = render_color(r_arr[y, x], g_arr[y, x], b_arr[y, x])

    print(f"  RGB QR: version={version}, size={width}x{height}, payload={len(payload_bytes)} bytes")
    return Image.fromarray(color_img)


def make_canvas(qr_images):
    """Tile RGB QR images into a canvas."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    for idx, img in enumerate(qr_images):
        row = idx // COLS
        col = idx % COLS
        x = col * CELL_SIZE
        y = row * CELL_SIZE
        canvas.paste(img, (x, y))
    return canvas


def generate_qrgb_bin_images(file_path, base_dir="./tmp"):
    if not os.path.exists(file_path):
        print("File not found!")
        return

    os.makedirs(base_dir, exist_ok=True)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    chunks = [
        file_bytes[i: i + DATA_PER_QR] for i in range(0, len(file_bytes), DATA_PER_QR)
    ]
    total_chunks = len(chunks)
    total_images = math.ceil(total_chunks / QR_PER_IMAGE)

    print(f"Raw total size: {len(file_bytes)} bytes")
    print(f"Total chunks: {total_chunks}, total canvases: {total_images}")

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(QR_PER_IMAGE):
            chunk_idx = img_idx * QR_PER_IMAGE + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            chunk_data = chunks[chunk_idx]
            seq = chunk_idx.to_bytes(4, "big", signed=False)
            total = total_chunks.to_bytes(4, "big", signed=False)
            data_len = len(chunk_data).to_bytes(2, "big", signed=False)
            payload = seq + total + data_len + chunk_data

            print(f"Chunk {chunk_idx}: {len(chunks[chunk_idx])} raw bytes, "
                  f"payload: {len(payload)} bytes (max {CHANNEL_CAPACITY * 3})")

            qr_img = make_rgb_qr_image(payload)
            current_qrs.append(qr_img)

        canvas = make_canvas(current_qrs)
        output_path = os.path.join(base_dir, f"qrcode_{img_idx + 1:03d}.png")
        canvas.save(output_path)
        print(f"Saved: {output_path}")

    print(f"\n[OK] All {total_images} canvas images generated in {base_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate V3 RGB QR code canvases (raw binary)")
    parser.add_argument("file_path", help="Path to file to encode")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    args = parser.parse_args()
    generate_qrgb_bin_images(args.file_path, base_dir=args.output_dir)
