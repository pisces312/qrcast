"""V1 grid-based verifier (fixed version 32 layout).

Reads QR code images using known grid dimensions, decodes each cell
with zxingcpp, and reconstructs the original file.

This is the original grid-splitting verifier. For whole-image detection
without knowing the grid layout, use qrcast.verifier instead.
"""

import zxingcpp
import cv2
import os
import glob
import tempfile
from PIL import Image

from qrcast.common import parse_payload

MAX_QR_VER = 32
BOX_SIZE = 3
SIZE_PER_QR = (4 * MAX_QR_VER + 17) * BOX_SIZE + 24
print(f"SIZE_PER_QR: {SIZE_PER_QR}")


def decode_qr_grid(image_path):
    """Decode QR codes from a known grid layout using zxingcpp."""
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    qr_w = SIZE_PER_QR
    qr_h = SIZE_PER_QR

    results = []

    ROWS = h // qr_h
    COLS = w // qr_w

    for row in range(ROWS):
        for col in range(COLS):
            x_start = col * qr_w
            x_end = (col + 1) * qr_w
            y_start = row * qr_h
            y_end = (row + 1) * qr_h

            roi = img[y_start:y_end, x_start:x_end]
            pil_img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
            barcodes = zxingcpp.read_barcodes(pil_img)

            for barcode in barcodes:
                data = barcode.bytes
                if data:
                    seq, total, payload = parse_payload(data)
                    if seq is not None:
                        results.append({
                            "seq": seq,
                            "total": total,
                            "payload": payload,
                            "data": data,
                        })

    return results


def verify_qr_codes(base_dir, output_dir="./verify_output", compress=False):
    """Verify all QR code files and reconstruct the original file.

    Args:
        base_dir: Directory containing qrcode_*.png files.
        output_dir: Directory to write reconstructed file.
        compress: If True, treat data as 7z and extract.

    Returns:
        True if verification successful, False otherwise.
    """
    received_chunks = {}
    total_chunks = None

    qr_files = sorted(glob.glob(os.path.join(base_dir, "qrcode_*.png")))
    if not qr_files:
        print(f"[X] No QR code files found in {base_dir}")
        return False

    print(f"[DIR] Found {len(qr_files)} QR code files")

    for qr_file in qr_files:
        print(f"\n[FILE] Processing: {os.path.basename(qr_file)}")
        results = decode_qr_grid(qr_file)

        if not results:
            print(f"  [!] No QR codes detected in this image")
            continue

        print(f"  [OK] Detected {len(results)} QR codes")

        for result in results:
            seq = result["seq"]
            total = result["total"]
            payload = result["payload"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                print(f"  [SKIP] Chunk {seq} already received, skipping")
                continue

            if seq >= total_chunks:
                print(f" ERROR: seq {seq} cannot be larger than {total_chunks}. Ignore")
                continue

            received_chunks[seq] = payload
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(payload)} bytes)")

    if total_chunks is None:
        print("\n[X] No valid QR codes found!")
        return False

    print(f"\n[INFO] Chunks received: {len(received_chunks)}/{total_chunks}")

    if len(received_chunks) != total_chunks:
        print("\n[!] Not all chunks received! Cannot reconstruct file.")
        missing = set(range(total_chunks)) - set(received_chunks.keys())
        print(f"Missing chunks: {sorted(missing)}")
        return False

    print("\n[INFO] Assembling chunks...")
    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]

    print(f"[OK] Assembled data: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    if compress:
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as f:
            f.write(full_data)
            tmp_7z = f.name

        try:
            import py7zr
            with py7zr.SevenZipFile(tmp_7z, "r") as archive:
                archive.extractall(output_dir)

            print(f"\n[OK] Extraction successful! Files saved to: {output_dir}")

            extracted_files = []
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    extracted_files.append((file, os.path.getsize(file_path)))

            print("\n[FILES] Extracted files:")
            for filename, size in extracted_files:
                print(f"  - {filename}: {size} bytes")

            return True

        except Exception as e:
            print(f"\n[X] Extraction failed: {e}")
            return False
        finally:
            if os.path.exists(tmp_7z):
                os.unlink(tmp_7z)
    else:
        output_file = os.path.join(output_dir, "output.bin")
        with open(output_file, "wb") as f:
            f.write(full_data)

        print(f"\n[OK] File saved to: {output_file} ({len(full_data)} bytes)")
        return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V1 grid-based QR verifier")
    parser.add_argument("input_dir", nargs="?", default="./tmp", help="Input directory")
    parser.add_argument("output_dir", nargs="?", default="./verify_output", help="Output directory")
    args = parser.parse_args()
    base_dir = args.input_dir
    output_dir = args.output_dir

    print("=" * 50)
    print("QRCast V1 Grid-based Verifier")
    print("=" * 50)
    print(f"Input directory:  {base_dir}")
    print(f"Output directory: {output_dir}")
    print("=" * 50)

    success = verify_qr_codes(base_dir, output_dir)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
