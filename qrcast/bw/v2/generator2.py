"""V2 B&W QR code generator v2 (configurable version 1-40).

File -> optional 7z compression -> chunk -> encode QR codes -> save grid canvases as PNG.
Payload format v2 with filename + CRC32 support.
"""

import argparse
import math
import os
import zlib

import numpy as np
from PIL import Image
from qrcode.base import rs_blocks
from qrcode.constants import ERROR_CORRECT_L
from qrcode.main import QRCode

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER, file_to_7z_bytes

ERROR_L = ERROR_CORRECT_L


def calc_qr_max_bytes(ver, error_correction=ERROR_L):
    """Calculate the max byte-mode payload capacity for a given QR version."""
    blocks = rs_blocks(ver, error_correction)
    total_data_codewords = sum(b.data_count for b in blocks)
    header_bits = 4 + (8 if ver <= 9 else 16)
    return (total_data_codewords * 8 - header_bits) // 8


class QRConfig:
    """QR generation config derived from a given QR version."""

    def __init__(self, ver=20):
        if not 1 <= ver <= 40:
            raise ValueError(f"QR version must be 1-40, got {ver}")
        self.ver = ver
        self.qr_max_bytes = calc_qr_max_bytes(ver)
        self.rows = math.floor(CANVAS_H / ((4 * ver + 17) * BOX_SIZE + 24))
        self.cols = math.floor(CANVAS_W / ((4 * ver + 17) * BOX_SIZE + 24))
        self.qr_per_image = self.rows * self.cols
        self.header_len = 12  # seq(4) + total(4) + data_len(2) + proto_ver(1) + flags(1)
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


def build_payload(seq, total, flags, chunk_data, filename=None, file_crc32=None, file_size=None):
    """Build v2 payload bytes."""
    seq_b = seq.to_bytes(4, "big", signed=False)
    total_b = total.to_bytes(4, "big", signed=False)
    proto_ver_b = b"\x02"
    flags_b = flags.to_bytes(1, "big", signed=False)

    if seq == 0:
        filename_bytes = filename.encode("utf-8") if filename else b""
        if len(filename_bytes) > 255:
            filename_bytes = filename_bytes[:255]
        meta = (
            len(filename_bytes).to_bytes(1, "big", signed=False)
            + filename_bytes
            + file_crc32.to_bytes(4, "big", signed=False)
            + file_size.to_bytes(4, "big", signed=False)
        )
        data_segment = meta + chunk_data
    else:
        data_segment = chunk_data

    data_len = len(data_segment)
    data_len_b = data_len.to_bytes(2, "big", signed=False)

    payload = seq_b + total_b + data_len_b + proto_ver_b + flags_b + data_segment
    return payload


def generate_qr_images(file_path, ver=20, base_dir="./tmp", compress=False, mode="canvas"):
    """Generate QR code images from a file.

    Args:
        file_path: Path to the file to encode.
        ver: QR version (1-40).
        base_dir: Base output directory.
        compress: Whether to compress with 7z first.
        mode: Output mode - "canvas" (grid images for HDMI),
              "individual" (single QR images for phone display),
              "both" (both outputs).
    """
    if mode not in ("canvas", "individual", "both"):
        raise ValueError(f"mode must be 'canvas', 'individual', or 'both', got '{mode}'")

    if not os.path.exists(file_path):
        print("File not found!")
        return

    qr_cfg = QRConfig(ver)
    qr_cfg.print_config()

    with open(file_path, "rb") as f:
        original_bytes = f.read()

    original_size = len(original_bytes)
    original_crc = zlib.crc32(original_bytes) & 0xFFFFFFFF
    filename = os.path.basename(file_path)
    filename_base = os.path.splitext(filename)[0]

    if compress:
        file_bytes = file_to_7z_bytes(file_path)
    else:
        file_bytes = original_bytes

    data_per_qr = qr_cfg.data_per_qr
    filename_bytes = filename.encode("utf-8")
    if len(filename_bytes) > 255:
        filename_bytes = filename_bytes[:255]
    meta_overhead = 1 + len(filename_bytes) + 4 + 4

    chunks = []
    offset = 0
    seq = 0
    while offset < len(file_bytes):
        if seq == 0:
            chunk_size = data_per_qr - meta_overhead
        else:
            chunk_size = data_per_qr
        chunk = file_bytes[offset:offset + chunk_size]
        chunks.append(chunk)
        offset += chunk_size
        seq += 1

    total_chunks = len(chunks)

    print(f"{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
    print(f"Original size: {original_size} bytes, CRC32: {original_crc:08X}")
    print(f"Total chunks: {total_chunks}")

    flags = 0x01 if compress else 0x00

    # Prepare output directories
    canvas_dir = None
    individual_dir = None
    if mode in ("canvas", "both"):
        canvas_dir = os.path.join(base_dir, f"{filename_base}-canvas")
        os.makedirs(canvas_dir, exist_ok=True)
    if mode in ("individual", "both"):
        individual_dir = os.path.join(base_dir, f"{filename_base}-individual")
        os.makedirs(individual_dir, exist_ok=True)

    total_images = (total_chunks + qr_cfg.qr_per_image - 1) // qr_cfg.qr_per_image

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(qr_cfg.qr_per_image):
            chunk_idx = img_idx * qr_cfg.qr_per_image + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            payload = build_payload(
                seq=chunk_idx,
                total=total_chunks,
                flags=flags,
                chunk_data=chunks[chunk_idx],
                filename=filename if chunk_idx == 0 else None,
                file_crc32=original_crc if chunk_idx == 0 else None,
                file_size=original_size if chunk_idx == 0 else None,
            )

            print(
                f"Chunk {chunk_idx}: {len(chunks[chunk_idx])} bytes, payload total: {len(payload)} bytes, max allowed: {qr_cfg.qr_max_bytes}"
            )

            qr_img = make_qr(payload, qr_cfg)
            current_qrs.append(qr_img)

            if individual_dir is not None:
                qr_path = os.path.join(individual_dir, f"qr_{chunk_idx:04d}.png")
                qr_img.save(qr_path)

        if canvas_dir is not None:
            canvas = make_canvas(current_qrs, qr_cfg)
            output_path = os.path.join(canvas_dir, f"qrcode_{img_idx + 1:03d}.png")
            canvas.save(output_path)
            print(f"Saved: {output_path}")

    print(f"\n[OK] QR images generated in {base_dir}")
    if canvas_dir:
        print(f"  Canvas mode: {canvas_dir}")
    if individual_dir:
        print(f"  Individual mode: {individual_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate V2 B&W QR code canvases v2 (with filename + CRC)")
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--ver", type=int, default=20, help="QR version (1-40, default: 20)")
    parser.add_argument("--output-dir", default="./tmp", help="Base output directory")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    parser.add_argument("--mode", choices=["canvas", "individual", "both"], default="canvas",
                        help="Output mode: canvas (grid images for HDMI), "
                             "individual (single QR for phone display), both (default: canvas)")
    args = parser.parse_args()

    generate_qr_images(
        file_path=args.file_path,
        ver=args.ver,
        base_dir=args.output_dir,
        compress=args.compress,
        mode=args.mode,
    )
