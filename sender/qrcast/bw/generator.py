"""V2 B&W QR code generator (configurable version 1-40).

File -> optional 7z compression -> chunk -> encode QR codes -> save grid canvases as PNG.
Automatically calculates capacity from the specified QR version.
"""

from qrcode.main import QRCode
from qrcode.constants import ERROR_CORRECT_L
from qrcode.base import rs_blocks
from PIL import Image
import numpy as np
import os
import math
import argparse

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER, file_to_7z_bytes

# ===================== Core Config =====================
ERROR_L = ERROR_CORRECT_L


def calc_qr_max_bytes(ver, error_correction=ERROR_L):
    """Calculate the max byte-mode payload capacity for a given QR version."""
    blocks = rs_blocks(ver, error_correction)
    total_data_codewords = sum(b.data_count for b in blocks)
    header_bits = 4 + (8 if ver <= 9 else 16)
    return (total_data_codewords * 8 - header_bits) // 8


class QRConfig:
    """QR generation config derived from a given QR version."""

    def __init__(self, ver=32):
        if not 1 <= ver <= 40:
            raise ValueError(f"QR version must be 1-40, got {ver}")
        self.ver = ver
        self.qr_max_bytes = calc_qr_max_bytes(ver)
        self.rows = math.floor(CANVAS_H / ((4 * ver + 17) * BOX_SIZE + 24))
        self.cols = math.floor(CANVAS_W / ((4 * ver + 17) * BOX_SIZE + 24))
        self.qr_per_image = self.rows * self.cols
        self.header_len = 8
        self.data_per_qr = self.qr_max_bytes - self.header_len

    def print_config(self):
        print(f"QR version: {self.ver}")
        print(f"rows: {self.rows}, cols: {self.cols}, QR_PER_IMAGE: {self.qr_per_image}")
        print(f"QR_MAX_BYTES: {self.qr_max_bytes}, DATA_PER_QR: {self.data_per_qr}")


def make_qr(data_bytes, qr_cfg):
    qr = QRCode(
        version=qr_cfg.ver,
        error_correction=ERROR_L,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    print(f" QR version: {qr.version}, size: {qr.modules_count}x{qr.modules_count}")
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")


def make_canvas(qr_images, qr_cfg):
    qr_w, qr_h = qr_images[0].size
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    for idx, img in enumerate(qr_images):
        row = idx // qr_cfg.cols
        col = idx % qr_cfg.cols
        x = col * qr_w
        y = row * qr_h
        print(f"qr_w: {qr_w}, qr_h: {qr_h}, row: {row}, col: {col}, x: {x}, y: {y}")
        canvas.paste(img, (x, y))
    return canvas


def generate_qr_images(file_path, ver=32, base_dir="./tmp", compress=False, save_chunks=False):
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
    total_images = (total_chunks + qr_cfg.qr_per_image - 1) // qr_cfg.qr_per_image

    print(f"{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
    print(f"Total chunks: {total_chunks}, total canvases: {total_images}")

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(qr_cfg.qr_per_image):
            chunk_idx = img_idx * qr_cfg.qr_per_image + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            seq = chunk_idx.to_bytes(4, "big", signed=False)
            total = total_chunks.to_bytes(4, "big", signed=False)
            payload = seq + total + chunks[chunk_idx]

            print(
                f"Chunk {chunk_idx}: {len(chunks[chunk_idx])} bytes, payload total: {len(payload)} bytes, max allowed: {qr_cfg.qr_max_bytes}"
            )

            qr_img = make_qr(payload, qr_cfg)
            current_qrs.append(qr_img)

            if save_chunks:
                qr_debug_path = os.path.join(base_dir, f"qr_chunk_{chunk_idx:04d}.png")
                qr_img.save(qr_debug_path)

        canvas = make_canvas(current_qrs, qr_cfg)
        output_path = os.path.join(base_dir, f"qrcode_{img_idx + 1:03d}.png")
        canvas.save(output_path)
        print(f"Saved: {output_path}")

    print(f"\n[OK] All {total_images} canvas images generated in {base_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate V2 B&W QR code canvases (configurable version)")
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--ver", type=int, default=32, help="QR version (1-40, default: 32)")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    parser.add_argument("--save-chunks", action="store_true", help="Save individual QR chunk images")
    args = parser.parse_args()

    generate_qr_images(
        file_path=args.file_path,
        ver=args.ver,
        base_dir=args.output_dir,
        compress=args.compress,
        save_chunks=args.save_chunks,
    )
