"""Generic verifier for B&W QR code file transfer (v1 & v2 compatible).

Reads QR code images, decodes all codes per image using whole-image detection
with strip-scanning fallback, filters false positives, and reconstructs
the original file.

Usage:
    python -m qrcast.verifier [input_dir] [output_dir]
    # defaults: input=./tmp, output=./tmp/verify_output
"""

import statistics
import zxingcpp
import cv2
import os
import sys
import glob
from PIL import Image

from qrcast.common import parse_payload


# ===================== Decode whole image =====================
def decode_whole_image(image_path):
    """Decode all QR codes from the full image without grid splitting.

    Uses whole-image scan first, then falls back to horizontal-strip scanning
    if some chunks are missing (zxingcpp can miss tightly-packed QR rows in
    dense grids when scanning the whole image at once).
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"  [!] Failed to read image: {image_path}")
        return []

    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    h, w = img.shape[:2]

    def _parse_results(barcodes):
        raw = []
        for barcode in barcodes:
            data = barcode.bytes
            if data:
                seq, total, payload = parse_payload(data)
                if seq is not None:
                    raw.append({"seq": seq, "total": total, "payload": payload, "data": data})
        if not raw:
            return []
        totals = [r["total"] for r in raw]
        consensus_total = max(set(totals), key=totals.count)
        results = []
        for r in raw:
            if r["total"] == consensus_total and r["seq"] < consensus_total:
                results.append(r)
            else:
                print(f"  [FILTER] Dropped false positive: seq={r['seq']}, total={r['total']}")
        return results

    # Phase 1: whole-image scan
    barcodes = zxingcpp.read_barcodes(pil_img)
    results = _parse_results(barcodes)

    if not results:
        return []

    total = results[0]["total"]
    if len(results) >= total:
        return results

    # Phase 2: strip scan fallback
    missing_seqs = set(range(total)) - {r["seq"] for r in results}
    if not missing_seqs:
        return results

    print(f"  [STRIP] Whole-image found {len(results)}/{total}, scanning strips for missing chunks...")

    heights = []
    for bc in barcodes:
        try:
            pos = bc.position
            pts = [pos.top_left, pos.top_right, pos.bottom_right, pos.bottom_left]
            bh = max(p.y for p in pts) - min(p.y for p in pts)
            if bh > 10:
                heights.append(bh)
        except Exception:
            pass
    qr_size = int(statistics.median(heights)) if heights else min(h // 3, w // 7)

    strip_h = qr_size * 2
    overlap = qr_size // 2
    y = 0
    found_in_strips = {}

    while y < h:
        y_end = min(y + strip_h, h)
        strip = pil_img.crop((0, y, w, y_end))
        strip_barcodes = zxingcpp.read_barcodes(strip)
        strip_results = _parse_results(strip_barcodes)
        for r in strip_results:
            if r["seq"] in missing_seqs:
                found_in_strips[r["seq"]] = r
                missing_seqs.discard(r["seq"])
        if not missing_seqs:
            break
        y += strip_h - overlap
        if y >= h:
            break

    if found_in_strips:
        print(f"  [STRIP] Found {len(found_in_strips)} additional chunk(s) via strip scan")
        results.extend(found_in_strips.values())

    return results


# ===================== Verify =====================
def verify(base_dir, output_dir):
    """Decode all QR images and reconstruct file.

    Args:
        base_dir: Directory containing qrcode_*.png files.
        output_dir: Directory to write reconstructed file.

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

    for qr_file in qr_files:
        fname = os.path.basename(qr_file)
        print(f"[FILE] {fname}")

        results = decode_whole_image(qr_file)

        if not results:
            print(f"  [!] No QR codes detected")
            continue

        print(f"  [OK] Detected {len(results)} QR codes")

        for r in results:
            seq, total, payload = r["seq"], r["total"], r["payload"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}\n")

            if seq in received_chunks:
                continue

            received_chunks[seq] = payload
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(payload)} bytes)")

    if total_chunks is None:
        print("\n[X] No valid QR codes found!")
        return False

    print(f"\n[INFO] Chunks received: {len(received_chunks)}/{total_chunks}")

    if len(received_chunks) != total_chunks:
        missing = sorted(set(range(total_chunks)) - set(received_chunks.keys()))
        print(f"[!] Missing chunks: {missing}")
        return False

    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]
    print(f"[OK] Assembled data: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "output.bin")
    with open(output_file, "wb") as f:
        f.write(full_data)
    print(f"[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generic B&W QR verifier (whole-image decode)")
    parser.add_argument("input_dir", nargs="?", default="./tmp", help="Input directory")
    parser.add_argument("output_dir", nargs="?", default="./tmp/verify_output", help="Output directory")
    args = parser.parse_args()
    base_dir = args.input_dir
    output_dir = args.output_dir

    print("=" * 50)
    print("QRCast Verifier - Whole Image Decode")
    print("=" * 50)
    print(f"Input:  {base_dir}")
    print(f"Output: {output_dir}")
    print("=" * 50)

    success = verify(base_dir, output_dir)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
