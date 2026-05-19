"""V3 RGB QR code generator v2 (configurable version 1-40).

File -> optional 7z compress -> chunk -> raw binary into 3 QR channels -> RGB canvases (PNG).

Uses qrgb's color rendering to encode raw bytes into 3 color channels (R, G, B).
Each channel carries raw binary via QR byte mode — no base64 overhead.

Payload format: [seq(4B)][total(4B)][data_len(2B)][raw chunk bytes][padding]
data_len tells decoder exact chunk size so padding from 3-way split can be stripped.
"""

import argparse
import math
import os

import numpy as np
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M
from qrcode.main import QRCode

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER, file_to_7z_bytes

# qrgb is required for generation
try:
    from qrgb.qrgb import render_color, QR_CAPACITIES
except ImportError as e:
    raise ImportError("qrgb library is required for V3 generation. Install: pip install qrgb") from e

ERROR_M = ERROR_CORRECT_M


class QRConfig:
    """QR generation config derived from a given QR version."""

    def __init__(self, ver=32):
        if not 1 <= ver <= 40:
            raise ValueError(f"QR version must be 1-40, got {ver}")
        if ver not in QR_CAPACITIES:
            raise ValueError(f"QR version {ver} not supported by qrgb (available: {list(QR_CAPACITIES.keys())})")
        self.ver = ver
        self.channel_capacity = QR_CAPACITIES[ver]
        self.cell_size = (4 * ver + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE
        self.rows = math.floor(CANVAS_H / self.cell_size)
        self.cols = math.floor(CANVAS_W / self.cell_size)
        self.qr_per_image = self.rows * self.cols
        self.header_len = 10  # seq(4) + total(4) + data_len(2)
        self.data_per_qr = self.channel_capacity * 3 - self.header_len

    def print_config(self):
        print(f"QR version: {self.ver}")
        print(f"CELL_SIZE: {self.cell_size}, ROWS: {self.rows}, COLS: {self.cols}, QR_PER_IMAGE: {self.qr_per_image}")
        print(f"CHANNEL_CAPACITY: {self.channel_capacity}, DATA_PER_QR: {self.data_per_qr}")


def make_mono_qr(data_bytes, version):
    """Generate a mono (black/white) QR code image from raw bytes."""
    qr = QRCode(
        version=version,
        error_correction=ERROR_M,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    img = qr.make_image()
    img = img.convert("L").point(lambda p: 0 if p < 128 else 255)
    return img


def make_rgb_qr_image(payload_bytes, version):
    """Create an RGB QR code PIL image from raw binary payload."""
    pad_len = (3 - len(payload_bytes) % 3) % 3
    padded = payload_bytes + b"\x00" * pad_len
    chunk_size = len(padded) // 3

    r_data = padded[:chunk_size]
    g_data = padded[chunk_size:2 * chunk_size]
    b_data = padded[2 * chunk_size:]

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


def make_canvas(qr_images, qr_cfg):
    """Tile RGB QR images into a canvas."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    for idx, img in enumerate(qr_images):
        row = idx // qr_cfg.cols
        col = idx % qr_cfg.cols
        x = col * qr_cfg.cell_size
        y = row * qr_cfg.cell_size
        canvas.paste(img, (x, y))
    return canvas


def generate_qrgb_bin_images(file_path, ver=32, base_dir="./tmp", compress=False):
    if not os.path.exists(file_path):
        print("File not found!")
        return

    qr_cfg = QRConfig(ver)
    qr_cfg.print_config()

    os.makedirs(base_dir, exist_ok=True)

    if compress:
        file_bytes = file_to_7z_bytes(file_path)
    else:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

    chunks = [
        file_bytes[i: i + qr_cfg.data_per_qr] for i in range(0, len(file_bytes), qr_cfg.data_per_qr)
    ]
    total_chunks = len(chunks)
    total_images = math.ceil(total_chunks / qr_cfg.qr_per_image)

    print(f"{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
    print(f"Total chunks: {total_chunks}, total canvases: {total_images}")

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(qr_cfg.qr_per_image):
            chunk_idx = img_idx * qr_cfg.qr_per_image + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            chunk_data = chunks[chunk_idx]
            seq = chunk_idx.to_bytes(4, "big", signed=False)
            total = total_chunks.to_bytes(4, "big", signed=False)
            data_len = len(chunk_data).to_bytes(2, "big", signed=False)
            payload = seq + total + data_len + chunk_data

            print(f"Chunk {chunk_idx}: {len(chunks[chunk_idx])} raw bytes, "
                  f"payload: {len(payload)} bytes (max {qr_cfg.channel_capacity * 3})")

            qr_img = make_rgb_qr_image(payload, qr_cfg.ver)
            current_qrs.append(qr_img)

        canvas = make_canvas(current_qrs, qr_cfg)
        output_path = os.path.join(base_dir, f"qrcode_{img_idx + 1:03d}.png")
        canvas.save(output_path)
        print(f"Saved: {output_path}")

    print(f"\n[OK] All {total_images} canvas images generated in {base_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate V3 RGB QR code canvases (configurable version)")
    parser.add_argument("file_path", help="Path to file to encode")
    parser.add_argument("--ver", type=int, default=32, help="QR version (1-40, default: 32)")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    args = parser.parse_args()
    generate_qrgb_bin_images(
        file_path=args.file_path,
        ver=args.ver,
        base_dir=args.output_dir,
        compress=args.compress,
    )
