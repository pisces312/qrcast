"""V2 B&W QR code generator — individual mode only, self-contained.

File -> chunk -> encode QR codes -> save individual PNGs.
Payload format v2 with filename + CRC32 support.
No canvas/grid mode, no compression. All code in this single file.
"""

import argparse
import os
import zlib

from qrcode.base import rs_blocks
from qrcode.constants import ERROR_CORRECT_L
from qrcode.main import QRCode

# ===================== qrcode library bug fix =====================
# qrcode >=8.2 has a bug: Polynomial.__mod__ doesn't handle leading zero
# coefficients in Reed-Solomon encoding, causing ValueError: glog(0)
# when encoding certain binary data patterns.
try:
    from qrcode import base as _qrcode_base

    def _patched_mod(self, other):
        num = self.num[:]
        while len(num) > 0 and num[0] == 0:
            num.pop(0)
        if len(num) == 0:
            return _qrcode_base.Polynomial([0], 0)
        if len(num) < len(other):
            return _qrcode_base.Polynomial(num, 0)
        self = _qrcode_base.Polynomial(num, 0)

        difference = len(self) - len(other)
        if difference < 0:
            return self
        ratio = _qrcode_base.glog(self[0]) - _qrcode_base.glog(other[0])
        new_num = [
            item ^ _qrcode_base.gexp(_qrcode_base.glog(other_item) + ratio)
            for item, other_item in zip(self, other)
        ]
        if difference:
            new_num.extend(self[-difference:])
        return _qrcode_base.Polynomial(new_num, 0) % other

    _qrcode_base.Polynomial.__mod__ = _patched_mod
except Exception:
    pass  # If qrcode isn't installed or API changes, ignore silently

# ===================== Constants =====================
BOX_SIZE = 3
BORDER = 4
ERROR_L = ERROR_CORRECT_L


# ===================== QR Capacity =====================


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
        # v2 payload fixed header: seq(4) + total(4) + data_len(2) + proto_ver(1) + flags(1)
        self.header_len = 12
        self.data_per_qr = self.qr_max_bytes - self.header_len

    def print_config(self):
        print(f"QR version: {self.ver}")
        print(f"QR_MAX_BYTES: {self.qr_max_bytes}, DATA_PER_QR: {self.data_per_qr}")


# ===================== QR Generation =====================


def make_qr(data_bytes, qr_cfg):
    """Encode bytes into a QR code image."""
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


# ===================== v2 Payload =====================


def build_payload(
    seq, total, flags, chunk_data, filename=None, file_crc32=None, file_size=None
):
    """Build v2 payload bytes.

    Fixed header (12B): [seq(4B)][total(4B)][data_len(2B)][proto_ver(1B)][flags(1B)]

    Data segment for seq==0:
        [filename_len(1B)][filename(N B)][file_crc32(4B)][file_size(4B)][chunk_data(M B)]
    Data segment for seq>0:
        [chunk_data(M B)]
    """
    seq_b = seq.to_bytes(4, "big", signed=False)
    total_b = total.to_bytes(4, "big", signed=False)
    proto_ver_b = b"\x02"
    flags_b = flags.to_bytes(1, "big", signed=False)

    if seq == 0:
        # First chunk carries file metadata
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

    return seq_b + total_b + data_len_b + proto_ver_b + flags_b + data_segment


# ===================== Main =====================


def generate_qr_images(file_path, ver=20, output_dir="./tmp"):
    """Generate individual QR code images from a file (no compression).

    Args:
        file_path: Path to the file to encode.
        ver: QR version (1-40).
        output_dir: Base output directory. Individual QR PNGs saved to
                    {output_dir}/{filename}-individual/.
    """
    if not os.path.exists(file_path):
        print("File not found!")
        return

    qr_cfg = QRConfig(ver)
    qr_cfg.print_config()

    # Read the entire file into memory without compression
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    file_size = len(file_bytes)
    file_crc = zlib.crc32(file_bytes) & 0xFFFFFFFF
    filename = os.path.basename(file_path)
    filename_base = os.path.splitext(filename)[0]

    # Calculate meta overhead for seq==0 chunk
    filename_bytes = filename.encode("utf-8")
    if len(filename_bytes) > 255:
        filename_bytes = filename_bytes[:255]
    meta_overhead = (
        1 + len(filename_bytes) + 4 + 4
    )  # filename_len + filename + crc32 + file_size

    # Split file into chunks
    data_per_qr = qr_cfg.data_per_qr
    chunks = []
    offset = 0
    seq = 0
    while offset < len(file_bytes):
        chunk_size = data_per_qr - meta_overhead if seq == 0 else data_per_qr
        chunk = file_bytes[offset : offset + chunk_size]
        chunks.append(chunk)
        offset += chunk_size
        seq += 1

    total_chunks = len(chunks)

    print(f"File size: {file_size} bytes, CRC32: {file_crc:08X}")
    print(f"Total chunks: {total_chunks}")

    # Always no compression
    flags = 0x00

    # Create output directory
    out_dir = os.path.join(output_dir, f"{filename_base}-individual")
    os.makedirs(out_dir, exist_ok=True)

    # Generate QR images
    for chunk_idx in range(total_chunks):
        payload = build_payload(
            seq=chunk_idx,
            total=total_chunks,
            flags=flags,
            chunk_data=chunks[chunk_idx],
            filename=filename if chunk_idx == 0 else None,
            file_crc32=file_crc if chunk_idx == 0 else None,
            file_size=file_size if chunk_idx == 0 else None,
        )

        print(
            f"Chunk {chunk_idx + 1}/{total_chunks}: "
            f"data={len(chunks[chunk_idx])}B, "
            f"payload={len(payload)}B, "
            f"max={qr_cfg.qr_max_bytes}B"
        )

        qr_img = make_qr(payload, qr_cfg)
        qr_path = os.path.join(out_dir, f"qr_{chunk_idx:04d}.png")
        qr_img.save(qr_path)

    print(f"\n[OK] Generated {total_chunks} QR images in {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate individual QR codes from a file — v2 payload, no compression"
    )
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument(
        "--ver", type=int, default=20, help="QR version (1-40, default: 20)"
    )
    parser.add_argument(
        "--output-dir", default="./tmp", help="Output directory (default: ./tmp)"
    )
    args = parser.parse_args()

    generate_qr_images(
        file_path=args.file_path,
        ver=args.ver,
        output_dir=args.output_dir,
    )
