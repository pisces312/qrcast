"""V1 B&W QR code generator (fixed version 32).

File -> optional 7z compression -> chunk -> encode QR codes -> save grid canvases as PNG.
"""

from qrcode.main import QRCode
from qrcode.constants import ERROR_CORRECT_L
from PIL import Image
import numpy as np
import os
import math

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER, file_to_7z_bytes

# ===================== Core Config =====================
ERROR_L = ERROR_CORRECT_L

MAX_QR_VER = 32
QR_MAX_BYTES = 1865

ROWS = math.floor(CANVAS_H / ((4 * MAX_QR_VER + 17) * BOX_SIZE + 24))
COLS = math.floor(CANVAS_W / ((4 * MAX_QR_VER + 17) * BOX_SIZE + 24))
QR_PER_IMAGE = ROWS * COLS

HEADER_LEN = 8
DATA_PER_QR = QR_MAX_BYTES - HEADER_LEN

print(f"rows: {ROWS}")
print(f"cols: {COLS}")
print(f"QR_PER_IMAGE: {QR_PER_IMAGE}")
print(f"QR_MAX_BYTES: {QR_MAX_BYTES}, DATA_PER_QR: {DATA_PER_QR}")


def make_qr(data_bytes):
    qr = QRCode(
        version=MAX_QR_VER,
        error_correction=ERROR_L,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    print(f" QR version: {qr.version}, size: {qr.modules_count}x{qr.modules_count}")
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")


def make_canvas(qr_images):
    qr_w, qr_h = qr_images[0].size
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    for idx, img in enumerate(qr_images):
        row = idx // COLS
        col = idx % COLS
        x = col * qr_w
        y = row * qr_h
        print(f"qr_w: {qr_w}, qr_h: {qr_h}, row: {row}, col: {col}, x: {x}, y: {y}")
        canvas.paste(img, (x, y))
    return canvas


def generate_qr_images(file_path, base_dir="./tmp", compress=False, save_chunks=False):
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
    total_images = (total_chunks + QR_PER_IMAGE - 1) // QR_PER_IMAGE

    print(f"{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
    print(f"Total chunks: {total_chunks}, total canvases: {total_images}")

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(QR_PER_IMAGE):
            chunk_idx = img_idx * QR_PER_IMAGE + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            seq = chunk_idx.to_bytes(4, "big", signed=False)
            total = total_chunks.to_bytes(4, "big", signed=False)
            payload = seq + total + chunks[chunk_idx]

            print(
                f"Chunk {chunk_idx}: {len(chunks[chunk_idx])} bytes, payload total: {len(payload)} bytes, max allowed: {QR_MAX_BYTES}"
            )

            qr_img = make_qr(payload)
            current_qrs.append(qr_img)

            if save_chunks:
                qr_debug_path = os.path.join(base_dir, f"qr_chunk_{chunk_idx:04d}.png")
                qr_img.save(qr_debug_path)

        canvas = make_canvas(current_qrs)
        output_path = os.path.join(base_dir, f"qrcode_{img_idx + 1:03d}.png")
        canvas.save(output_path)
        print(f"Saved: {output_path}")

    print(f"\n[OK] All {total_images} canvas images generated in {base_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate V1 B&W QR code canvases (fixed ver 32)")
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    parser.add_argument("--save-chunks", action="store_true", help="Save individual QR chunk images")
    args = parser.parse_args()

    generate_qr_images(
        file_path=args.file_path,
        base_dir=args.output_dir,
        compress=args.compress,
        save_chunks=args.save_chunks,
    )
