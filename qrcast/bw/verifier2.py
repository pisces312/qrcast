"""Verifier for B&W QR code file transfer (payload format v2).

Reads QR code canvas PNGs, decodes each cell via grid-based scan
(known cell size from ver), extracts filename + CRC32, and reconstructs
the original file.

Usage:
    python -m qrcast.bw.verifier2 [input_dir] [output_dir]
    # defaults: input=./tmp, output=./tmp/verify_output
"""

import argparse
import glob
import os
import tempfile
import zlib

import cv2
import numpy as np
import py7zr
import zxingcpp
from PIL import Image

from qrcast.common import parse_payload_v2, BOX_SIZE, BORDER


def calc_cell_size(ver):
    """Calculate cell size for a given QR version."""
    return (4 * ver + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE


def decode_image(image_path, ver=20):
    """Decode all QR codes from a canvas image via grid-based scan.

    Splits the canvas into fixed-size cells (based on QR version) and
    scans each cell individually. This avoids zxingcpp's whole-image
    detector failing on densely packed QR grids.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"  [!] Failed to read image: {image_path}")
        return []

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    cell_size = calc_cell_size(ver)
    rows = h // cell_size
    cols = w // cell_size

    raw = []
    empty = 0

    for row in range(rows):
        for col in range(cols):
            x_start = col * cell_size
            x_end = (col + 1) * cell_size
            y_start = row * cell_size
            y_end = (row + 1) * cell_size
            cell = img_rgb[y_start:y_end, x_start:x_end]

            # Skip mostly-white cells (empty slots)
            if np.mean(cell) > 250:
                empty += 1
                continue

            cell_pil = Image.fromarray(cell)
            cell_barcodes = zxingcpp.read_barcodes(cell_pil)
            for barcode in cell_barcodes:
                data = barcode.bytes
                if data:
                    parsed = parse_payload_v2(data)
                    if parsed is not None:
                        raw.append({
                            "seq": parsed["seq"],
                            "total": parsed["total"],
                            "payload": parsed,
                            "data": data,
                        })

    if not raw:
        return []

    # Filter false positives using consensus_total
    totals = [r["total"] for r in raw]
    consensus_total = max(set(totals), key=totals.count)

    results = []
    for r in raw:
        if r["total"] == consensus_total and r["seq"] < consensus_total:
            results.append(r)
        else:
            print(f"  [FILTER] Dropped false positive: seq={r['seq']}, total={r['total']}")

    print(f"  [OK] Grid scan: {len(results)}/{consensus_total} chunks ({empty} empty cells)")
    return results


def verify(base_dir, output_dir, ver=20):
    """Decode all QR images and reconstruct file.

    Args:
        base_dir: Directory containing qrcode_*.png files.
        output_dir: Directory to write reconstructed file.
        ver: QR version used during generation (default: 20).

    Returns:
        True if verification successful, False otherwise.
    """
    qr_files = sorted(glob.glob(os.path.join(base_dir, "qrcode_*.png")))
    if not qr_files:
        print(f"[X] No QR code files found in {base_dir}")
        return False

    print(f"[DIR] Found {len(qr_files)} QR code file(s)\n")

    received_chunks = {}
    total_chunks = None
    meta_info = {}

    for qr_file in qr_files:
        fname = os.path.basename(qr_file)
        print(f"[FILE] {fname}")

        results = decode_image(qr_file, ver=ver)

        if not results:
            print(f"  [!] No QR codes detected")
            continue

        for r in results:
            parsed = r["payload"]
            seq = parsed["seq"]
            total = parsed["total"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}\n")

            if seq in received_chunks:
                continue

            if seq == 0:
                meta_info = {
                    "filename": parsed.get("filename"),
                    "file_crc32": parsed.get("file_crc32"),
                    "file_size": parsed.get("file_size"),
                    "flags": parsed.get("flags", 0),
                }
                print(
                    f"  [META] filename={meta_info['filename']}, "
                    f"size={meta_info['file_size']}, crc32={meta_info['file_crc32']:08X}"
                )

            received_chunks[seq] = parsed["chunk_data"]
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(parsed['chunk_data'])} bytes)")

    if total_chunks is None:
        print("\n[X] No valid QR codes found!")
        return False

    print(f"\n[INFO] Chunks received: {len(received_chunks)}/{total_chunks}")

    if len(received_chunks) != total_chunks:
        missing = sorted(set(range(total_chunks)) - set(received_chunks.keys()))
        print(f"[!] Missing chunks: {missing}")
        return False

    if not meta_info.get("filename"):
        print("[!] Missing meta info (seq=0), cannot save")
        return False

    print("\n[INFO] Assembling chunks...")
    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]
    print(f"[OK] Assembled data: {len(full_data)} bytes")

    # Optional 7z decompression
    if meta_info.get("flags", 0) & 0x01:
        print("[INFO] Decompressing 7z data...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".7z") as tmp:
            tmp.write(full_data)
            tmp_path = tmp.name
        try:
            with py7zr.SevenZipFile(tmp_path, mode="r") as archive:
                extract_dir = tempfile.mkdtemp()
                archive.extractall(path=extract_dir)
                extracted_files = [
                    f for f in os.listdir(extract_dir)
                    if os.path.isfile(os.path.join(extract_dir, f))
                ]
                if not extracted_files:
                    print("[!] No file found in 7z archive")
                    return False
                with open(os.path.join(extract_dir, extracted_files[0]), "rb") as f:
                    full_data = f.read()
            print(f"[OK] Decompressed: {len(full_data)} bytes")
        finally:
            os.unlink(tmp_path)

    # CRC32 verification
    if meta_info.get("file_crc32") is not None:
        computed_crc = zlib.crc32(full_data) & 0xFFFFFFFF
        expected_crc = meta_info["file_crc32"]
        if computed_crc != expected_crc:
            print(f"[!] CRC32 mismatch! Expected {expected_crc:08X}, got {computed_crc:08X}")
        else:
            print(f"[OK] CRC32 verified: {computed_crc:08X}")

    # File size verification
    if meta_info.get("file_size") is not None:
        if len(full_data) != meta_info["file_size"]:
            print(f"[!] File size mismatch! Expected {meta_info['file_size']}, got {len(full_data)}")
        else:
            print(f"[OK] File size verified: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, meta_info["filename"])
    with open(output_file, "wb") as f:
        f.write(full_data)
    print(f"[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B&W QR verifier v2 (grid-based decode + CRC)")
    parser.add_argument("input_dir", nargs="?", default="./tmp", help="Input directory")
    parser.add_argument("output_dir", nargs="?", default="./tmp/verify_output", help="Output directory")
    parser.add_argument("--ver", type=int, default=20, help="QR version used during generation (default: 20)")
    args = parser.parse_args()
    base_dir = args.input_dir
    output_dir = args.output_dir

    print("=" * 50)
    print("QRCast Verifier v2 - Grid-based Decode")
    print("=" * 50)
    print(f"Input:  {base_dir}")
    print(f"Output: {output_dir}")
    print(f"QR ver: {args.ver}")
    print("=" * 50)

    success = verify(base_dir, output_dir, ver=args.ver)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
