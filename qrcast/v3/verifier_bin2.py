"""V3 RGB QR code verifier v2 (raw binary, no base64).

Reads RGB QR canvas PNGs, decodes each cell via channel separation,
and reconstructs the original file with filename and CRC32 verification.

Payload format v2:
  Fixed Header (12B): [seq(4B)][total(4B)][data_len(2B)][proto_ver(1B)][flags(1B)]
  Data Segment:
    - seq==0: [filename_len(1B)][filename(N B)][file_crc32(4B)][file_size(4B)][chunk_data(M B)]
    - seq>0:  [chunk_data(M B)]

Uses zxingcpp .bytes for reliable binary data recovery.
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

# ===================== Grid Config (must match generator) =====================
BOX_SIZE = 3
BORDER = 4


def calc_cell_size(ver):
    """Calculate cell size for a given QR version."""
    return (4 * ver + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE


R_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (255, 0, 255), (255, 0, 0)])
G_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (0, 255, 255), (0, 255, 0)])
B_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 0, 255), (0, 255, 255), (0, 0, 255)])


def extract_channel(img_array, channel_colors, tolerance=30):
    """Extract a single color channel as a binary image (vectorized numpy)."""
    h, w = img_array.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    img_int = img_array.astype(np.int16)

    for color in channel_colors:
        diff = np.abs(img_int - color.astype(np.int16))
        dist = diff.sum(axis=2)
        mask |= (dist <= tolerance)

    return np.where(mask, 0, 255).astype(np.uint8)


def decode_channel_bytes(binary_img):
    """Decode a binary channel image as QR, returning raw bytes."""
    pil_img = Image.fromarray(binary_img, mode="L")
    results = zxingcpp.read_barcodes(pil_img)
    if results:
        return results[0].bytes
    return None


def decode_rgb_qr_cell(cell_img_array, tolerance=30):
    """Decode a single RGB QR cell by separating R, G, B channels.

    Returns the combined raw bytes (with padding), or None.
    """
    r_binary = extract_channel(cell_img_array, R_CHANNEL_COLORS, tolerance)
    g_binary = extract_channel(cell_img_array, G_CHANNEL_COLORS, tolerance)
    b_binary = extract_channel(cell_img_array, B_CHANNEL_COLORS, tolerance)

    r_bytes = decode_channel_bytes(r_binary)
    g_bytes = decode_channel_bytes(g_binary)
    b_bytes = decode_channel_bytes(b_binary)

    if r_bytes is None or g_bytes is None or b_bytes is None:
        failed = []
        if r_bytes is None:
            failed.append("R")
        if g_bytes is None:
            failed.append("G")
        if b_bytes is None:
            failed.append("B")
        print(f"    [!] Failed to decode channel(s): {', '.join(failed)}")
        return None

    return r_bytes + g_bytes + b_bytes


def parse_payload_v2(data_bytes):
    """Parse v2 binary payload.

    Returns dict with keys:
      seq, total, data_len, proto_ver, flags,
      filename, file_crc32, file_size, chunk_data
    or None if invalid.
    """
    if len(data_bytes) < 12:
        return None

    seq = int.from_bytes(data_bytes[0:4], "big", signed=False)
    total = int.from_bytes(data_bytes[4:8], "big", signed=False)
    data_len = int.from_bytes(data_bytes[8:10], "big", signed=False)
    proto_ver = data_bytes[10]
    flags = data_bytes[11]

    if proto_ver != 0x02:
        return None

    if len(data_bytes) < 12 + data_len:
        return None

    data_segment = data_bytes[12:12 + data_len]

    result = {
        "seq": seq,
        "total": total,
        "data_len": data_len,
        "proto_ver": proto_ver,
        "flags": flags,
        "filename": None,
        "file_crc32": None,
        "file_size": None,
        "chunk_data": b"",
    }

    if seq == 0:
        if len(data_segment) < 9:
            return None
        filename_len = data_segment[0]
        if len(data_segment) < 1 + filename_len + 8:
            return None
        filename = data_segment[1:1 + filename_len].decode("utf-8", errors="replace")
        file_crc32 = int.from_bytes(
            data_segment[1 + filename_len:5 + filename_len], "big", signed=False
        )
        file_size = int.from_bytes(
            data_segment[5 + filename_len:9 + filename_len], "big", signed=False
        )
        chunk_data = data_segment[9 + filename_len:]

        result["filename"] = filename
        result["file_crc32"] = file_crc32
        result["file_size"] = file_size
        result["chunk_data"] = chunk_data
    else:
        result["chunk_data"] = data_segment

    return result


def decode_canvas(image_path, cell_size, tolerance=30):
    """Decode all RGB QR cells from a canvas image."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"  [!] Could not read {image_path}")
        return []

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    rows = h // cell_size
    cols = w // cell_size

    results = []

    for row in range(rows):
        for col in range(cols):
            x_start = col * cell_size
            x_end = (col + 1) * cell_size
            y_start = row * cell_size
            y_end = (row + 1) * cell_size

            cell = img_rgb[y_start:y_end, x_start:x_end]

            if np.mean(cell) > 250:
                continue

            print(f"  Decoding cell [{row},{col}]...")
            raw = decode_rgb_qr_cell(cell, tolerance)
            if raw is None:
                continue

            parsed = parse_payload_v2(raw)
            if parsed is not None:
                results.append(parsed)

    return results


def verify_qrgb_bin(base_dir, output_dir, ver=20, tolerance=30):
    """Verify all RGB QR canvas PNGs v2 and reconstruct the file."""
    cell_size = calc_cell_size(ver)
    print(f"CELL_SIZE: {cell_size} (ver={ver})")

    received_chunks = {}
    total_chunks = None
    meta_info = {}

    qr_files = sorted(glob.glob(os.path.join(base_dir, "qrcode_*.png")))
    if not qr_files:
        print(f"[X] No QR code files found in {base_dir}")
        return False

    print(f"[DIR] Found {len(qr_files)} canvas files")

    for qr_file in qr_files:
        print(f"\n[FILE] Processing: {os.path.basename(qr_file)}")
        results = decode_canvas(qr_file, cell_size, tolerance)

        if not results:
            print(f"  [!] No RGB QR codes detected")
            continue

        print(f"  [OK] Detected {len(results)} RGB QR codes")

        for parsed in results:
            seq = parsed["seq"]
            total = parsed["total"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                print(f"  [SKIP] Chunk {seq} already received")
                continue

            if seq >= total_chunks:
                print(f"  [!] seq {seq} >= total {total_chunks}, ignoring")
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
        print("\n[X] No valid RGB QR codes found!")
        return False

    print(f"\n[INFO] Chunks received: {len(received_chunks)}/{total_chunks}")

    if len(received_chunks) != total_chunks:
        print("\n[!] Not all chunks received! Cannot reconstruct file.")
        missing = set(range(total_chunks)) - set(received_chunks.keys())
        print(f"Missing chunks: {sorted(missing)}")
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
            print(
                f"[!] File size mismatch! Expected {meta_info['file_size']}, got {len(full_data)}"
            )
        else:
            print(f"[OK] File size verified: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, meta_info["filename"])
    with open(output_file, "wb") as f:
        f.write(full_data)
    print(f"\n[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QRCast V3 RGB QR Verifier v2 (raw binary + CRC)")
    parser.add_argument("base_dir", nargs="?", default="./tmp", help="Input directory with qrcode_*.png files")
    parser.add_argument("output_dir", nargs="?", default="./tmp/qrgb_bin_verify_output", help="Output directory")
    parser.add_argument("--ver", type=int, default=20, help="QR version used during generation (default: 20)")
    parser.add_argument("--tolerance", type=int, default=30, help="Color tolerance for channel extraction (default: 30)")
    args = parser.parse_args()

    print("=" * 50)
    print("QRCast V3 RGB QR Verifier v2 (raw binary + CRC)")
    print("=" * 50)
    print(f"Input directory:  {args.base_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"QR version:       {args.ver}")
    print("=" * 50)

    success = verify_qrgb_bin(args.base_dir, args.output_dir, ver=args.ver, tolerance=args.tolerance)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
