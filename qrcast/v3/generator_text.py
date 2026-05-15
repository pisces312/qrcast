"""V3 RGB QR code generator (base64 text payload).

File -> optional 7z compress -> chunk -> base64 encode -> RGB QR canvases (PNG).

Uses the qrgb library to encode data into 3 color channels (R, G, B),
achieving ~3x data density per QR code compared to standard B&W QR.

Protocol: each RGB QR code carries text payload "SEQ:TOTAL:base64data"
"""

import base64
import math
import os
import argparse

import numpy as np
from PIL import Image

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER, file_to_7z_bytes

# qrgb is required for generation
try:
    from qrgb.qrgb import (
        ensure_multiple_of_3, split_data, get_max_version,
        generate_qr, render_color, QR_CAPACITIES,
    )
except ImportError as e:
    raise ImportError("qrgb library is required for V3 generation. Install: pip install qrgb") from e

# ===================== Core Config =====================
MAX_QR_VER = 40
MAX_TEXT_CAPACITY = QR_CAPACITIES[MAX_QR_VER] * 3  # 6993
HEADER_RESERVE = 20  # generous room for "SEQ:TOTAL:"
DATA_PER_QR = ((MAX_TEXT_CAPACITY - HEADER_RESERVE) // 4) * 3  # 5229

CELL_SIZE = (4 * MAX_QR_VER + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE  # 555
COLS = CANVAS_W // CELL_SIZE   # 3
ROWS = CANVAS_H // CELL_SIZE   # 1
QR_PER_IMAGE = ROWS * COLS     # 3

print(f"CELL_SIZE: {CELL_SIZE}, ROWS: {ROWS}, COLS: {COLS}, QR_PER_IMAGE: {QR_PER_IMAGE}")
print(f"MAX_TEXT_CAPACITY: {MAX_TEXT_CAPACITY}, DATA_PER_QR: {DATA_PER_QR}")


def make_rgb_qr_image(text_data):
    """Create an RGB QR code PIL image from text data using qrgb internals."""
    padded = ensure_multiple_of_3(text_data)
    r_data, g_data, b_data = split_data(padded)

    version = get_max_version((r_data, g_data, b_data))
    r_img = generate_qr(r_data, version, BOX_SIZE, BORDER)
    g_img = generate_qr(g_data, version, BOX_SIZE, BORDER)
    b_img = generate_qr(b_data, version, BOX_SIZE, BORDER)

    r_arr = np.array(r_img)
    g_arr = np.array(g_img)
    b_arr = np.array(b_img)

    height, width = r_arr.shape
    color_img = np.zeros((height, width, 3), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            color_img[y, x] = render_color(r_arr[y, x], g_arr[y, x], b_arr[y, x])

    print(f"  RGB QR: version={version}, size={width}x{height}, text_len={len(text_data)}")
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


def generate_qrgb_images(file_path, base_dir="./tmp", compress=False):
    if not os.path.exists(file_path):
        print("File not found!")
        return

    os.makedirs(base_dir, exist_ok=True)

    if compress:
        file_bytes = file_to_7z_bytes(file_path)
    else:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

    chunks = [
        file_bytes[i: i + DATA_PER_QR] for i in range(0, len(file_bytes), DATA_PER_QR)
    ]
    total_chunks = len(chunks)
    total_images = math.ceil(total_chunks / QR_PER_IMAGE)

    print(f"{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
    print(f"Total chunks: {total_chunks}, total canvases: {total_images}")

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(QR_PER_IMAGE):
            chunk_idx = img_idx * QR_PER_IMAGE + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            b64_data = base64.b64encode(chunks[chunk_idx]).decode("ascii")
            text_payload = f"{chunk_idx}:{total_chunks}:{b64_data}"

            print(f"Chunk {chunk_idx}: {len(chunks[chunk_idx])} raw bytes, "
                  f"text payload: {len(text_payload)} chars (max {MAX_TEXT_CAPACITY})")

            qr_img = make_rgb_qr_image(text_payload)
            current_qrs.append(qr_img)

        canvas = make_canvas(current_qrs)
        output_path = os.path.join(base_dir, f"qrcode_{img_idx + 1:03d}.png")
        canvas.save(output_path)
        print(f"Saved: {output_path}")

    print(f"\n[OK] All {total_images} canvas images generated in {base_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate V3 RGB QR code canvases (base64 text)")
    parser.add_argument("file_path", help="Path to file to encode")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress file with 7z before encoding")
    args = parser.parse_args()

    generate_qrgb_images(args.file_path, base_dir=args.output_dir, compress=args.compress)
