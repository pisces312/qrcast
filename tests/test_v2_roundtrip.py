"""Unit tests for v2 payload format encode/decode round-trip.

Tests both B&W (generator2) and color (generator_bin2) QR code generation
and verification using the v2 payload format with filename + CRC32 support.
"""

import os
import tempfile
import zlib

import numpy as np
import pytest
import zxingcpp
from PIL import Image

from qrcast.bw.v2.generator2 import (
    QRConfig,
    build_payload,
    generate_qr_images,
    make_qr,
)
from qrcast.common import parse_payload_v2, BOX_SIZE, BORDER

# Try importing v3 color modules (optional dependency)
try:
    from qrcast.v3.generator_bin2 import (
        QRConfig as ColorQRConfig,
        build_payload as color_build_payload,
        generate_qrgb_bin_images,
        make_rgb_qr_image,
    )
    from qrcast.v3.verifier_bin2 import (
        decode_rgb_qr_cell,
        parse_payload_v2 as color_parse_payload_v2,
    )
    HAS_V3 = True
except ImportError:
    HAS_V3 = False


# ===================== Helpers =====================


def _decode_bw_qr_image(pil_img):
    """Decode a single B&W QR image, return raw bytes or None."""
    results = zxingcpp.read_barcodes(pil_img.convert("RGB"))
    for r in results:
        if r.bytes:
            return r.bytes
    return None


def _generate_and_decode_bw(file_bytes, filename, ver=20, compress=False, mode="individual"):
    """Generate B&W QR images from file bytes, decode all, return assembled data + meta."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        generate_qr_images(
            file_path=file_path,
            ver=ver,
            base_dir=tmpdir,
            compress=compress,
            mode=mode,
        )

        filename_base = os.path.splitext(filename)[0]

        # Collect decoded chunks
        received = {}
        meta_info = {}

        if mode in ("individual", "both"):
            indiv_dir = os.path.join(tmpdir, f"{filename_base}-individual")
            qr_files = sorted(
                f for f in os.listdir(indiv_dir) if f.startswith("qr_") and f.endswith(".png")
            )
            for qr_file in qr_files:
                img = Image.open(os.path.join(indiv_dir, qr_file))
                raw = _decode_bw_qr_image(img)
                if raw is None:
                    continue
                parsed = parse_payload_v2(raw)
                if parsed is None:
                    continue
                seq = parsed["seq"]
                if seq == 0:
                    meta_info = {
                        "filename": parsed.get("filename"),
                        "file_crc32": parsed.get("file_crc32"),
                        "file_size": parsed.get("file_size"),
                        "flags": parsed.get("flags", 0),
                    }
                received[seq] = parsed["chunk_data"]
        elif mode == "canvas":
            canvas_dir = os.path.join(tmpdir, f"{filename_base}-canvas")
            qr_files = sorted(
                f for f in os.listdir(canvas_dir) if f.startswith("qrcode_") and f.endswith(".png")
            )
            cell_size = (4 * ver + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE
            for qr_file in qr_files:
                canvas = np.array(Image.open(os.path.join(canvas_dir, qr_file)))
                h, w = canvas.shape[:2]
                rows = h // cell_size
                cols = w // cell_size
                for row in range(rows):
                    for col in range(cols):
                        y0, y1 = row * cell_size, (row + 1) * cell_size
                        x0, x1 = col * cell_size, (col + 1) * cell_size
                        cell = canvas[y0:y1, x0:x1]
                        if np.mean(cell) > 250:
                            continue
                        cell_pil = Image.fromarray(cell)
                        raw = _decode_bw_qr_image(cell_pil)
                        if raw is None:
                            continue
                        parsed = parse_payload_v2(raw)
                        if parsed is None:
                            continue
                        seq = parsed["seq"]
                        if seq == 0:
                            meta_info = {
                                "filename": parsed.get("filename"),
                                "file_crc32": parsed.get("file_crc32"),
                                "file_size": parsed.get("file_size"),
                                "flags": parsed.get("flags", 0),
                            }
                        received[seq] = parsed["chunk_data"]

        # Assemble
        if not received:
            return None, None
        full_data = b"".join(received[i] for i in sorted(received.keys()))
        return full_data, meta_info


def _generate_and_decode_color(file_bytes, filename, ver=10, compress=False):
    """Generate color QR images from file bytes, decode all, return assembled data + meta."""
    if not HAS_V3:
        return None, None

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        generate_qrgb_bin_images(
            file_path=file_path,
            ver=ver,
            base_dir=tmpdir,
            compress=compress,
        )

        # Decode canvas images
        qr_cfg = ColorQRConfig(ver)
        cell_size = qr_cfg.cell_size
        received = {}
        meta_info = {}

        qr_files = sorted(
            f for f in os.listdir(tmpdir) if f.startswith("qrcode_") and f.endswith(".png")
        )
        for qr_file in qr_files:
            canvas = np.array(Image.open(os.path.join(tmpdir, qr_file)).convert("RGB"))
            h, w = canvas.shape[:2]
            rows = h // cell_size
            cols = w // cell_size
            for row in range(rows):
                for col in range(cols):
                    y0, y1 = row * cell_size, (row + 1) * cell_size
                    x0, x1 = col * cell_size, (col + 1) * cell_size
                    cell = canvas[y0:y1, x0:x1]
                    if np.mean(cell) > 250:
                        continue
                    raw = decode_rgb_qr_cell(cell)
                    if raw is None:
                        continue
                    parsed = color_parse_payload_v2(raw)
                    if parsed is None:
                        continue
                    seq = parsed["seq"]
                    if seq == 0:
                        meta_info = {
                            "filename": parsed.get("filename"),
                            "file_crc32": parsed.get("file_crc32"),
                            "file_size": parsed.get("file_size"),
                            "flags": parsed.get("flags", 0),
                        }
                    received[seq] = parsed["chunk_data"]

        if not received:
            return None, None
        full_data = b"".join(received[i] for i in sorted(received.keys()))
        return full_data, meta_info


# ===================== Tests: v2 payload build/parse round-trip =====================


class TestV2PayloadRoundTrip:
    """Test build_payload / parse_payload_v2 round-trip at the byte level."""

    def test_seq0_with_meta(self):
        data = b"hello world"
        crc = 0xDEADBEEF
        fsize = 12345
        payload = build_payload(seq=0, total=5, flags=0x00, chunk_data=data,
                                filename="test.txt", file_crc32=crc, file_size=fsize)
        parsed = parse_payload_v2(payload)
        assert parsed is not None
        assert parsed["seq"] == 0
        assert parsed["total"] == 5
        assert parsed["proto_ver"] == 0x02
        assert parsed["flags"] == 0x00
        assert parsed["filename"] == "test.txt"
        assert parsed["file_crc32"] == crc
        assert parsed["file_size"] == fsize
        assert parsed["chunk_data"] == data

    def test_seq_greater_than_zero(self):
        data = b"\x00\x01\x02\x03" * 100
        payload = build_payload(seq=3, total=10, flags=0x01, chunk_data=data)
        parsed = parse_payload_v2(payload)
        assert parsed is not None
        assert parsed["seq"] == 3
        assert parsed["total"] == 10
        assert parsed["flags"] == 0x01
        assert parsed["chunk_data"] == data
        assert parsed["filename"] is None
        assert parsed["file_crc32"] is None

    def test_unicode_filename(self):
        data = b"data"
        payload = build_payload(seq=0, total=1, flags=0x00, chunk_data=data,
                                filename="中文文件名.pdf", file_crc32=0, file_size=4)
        parsed = parse_payload_v2(payload)
        assert parsed["filename"] == "中文文件名.pdf"

    def test_long_filename_truncated(self):
        data = b"x"
        long_name = "a" * 300
        payload = build_payload(seq=0, total=1, flags=0x00, chunk_data=data,
                                filename=long_name, file_crc32=0, file_size=1)
        parsed = parse_payload_v2(payload)
        assert len(parsed["filename"]) == 255

    def test_too_short_returns_none(self):
        assert parse_payload_v2(b"\x00" * 5) is None
        assert parse_payload_v2(b"") is None

    def test_wrong_proto_ver_returns_none(self):
        # v1 payload: seq(4) + total(4) + data (no v2 header)
        data = b"\x00" * 8 + b"data"
        assert parse_payload_v2(data) is None

    def test_flags_compress_bit(self):
        data = b"abc"
        payload = build_payload(seq=0, total=1, flags=0x01, chunk_data=data,
                                filename="f.bin", file_crc32=1, file_size=3)
        parsed = parse_payload_v2(payload)
        assert parsed["flags"] & 0x01 == 0x01

    def test_empty_chunk_data(self):
        payload = build_payload(seq=1, total=2, flags=0x00, chunk_data=b"")
        parsed = parse_payload_v2(payload)
        assert parsed["chunk_data"] == b""


# ===================== Tests: B&W QR encode/decode =====================


class TestBWQREncodeDecode:
    """Test B&W (generator2) QR code generation and decode round-trip."""

    def test_small_file_individual(self):
        data = b"Hello, QRCast v2!" * 10
        decoded, meta = _generate_and_decode_bw(data, "hello.txt", ver=10, mode="individual")
        assert decoded is not None
        assert decoded == data
        assert meta["filename"] == "hello.txt"
        assert meta["file_crc32"] == (zlib.crc32(data) & 0xFFFFFFFF)
        assert meta["file_size"] == len(data)

    def test_small_file_canvas(self):
        data = b"Canvas mode test!" * 10
        decoded, meta = _generate_and_decode_bw(data, "canvas_test.txt", ver=10, mode="canvas")
        assert decoded is not None
        assert decoded == data
        assert meta["filename"] == "canvas_test.txt"

    def test_small_file_both(self):
        data = b"Both mode test!" * 10
        decoded, meta = _generate_and_decode_bw(data, "both_test.txt", ver=10, mode="both")
        assert decoded is not None
        assert decoded == data

    def test_binary_data(self):
        data = bytes(range(256)) * 5
        decoded, meta = _generate_and_decode_bw(data, "binary.bin", ver=15, mode="individual")
        assert decoded is not None
        assert decoded == data

    def test_empty_file(self):
        """Empty file produces 0 chunks — no QR images generated, decode returns None."""
        data = b""
        decoded, meta = _generate_and_decode_bw(data, "empty.txt", ver=10, mode="individual")
        # No chunks = no QR images, so nothing to decode
        assert decoded is None

    def test_crc32_verification(self):
        data = os.urandom(500)
        decoded, meta = _generate_and_decode_bw(data, "rand.bin", ver=10, mode="individual")
        expected_crc = zlib.crc32(data) & 0xFFFFFFFF
        assert meta["file_crc32"] == expected_crc

    def test_unicode_filename(self):
        data = b"unicode test"
        decoded, meta = _generate_and_decode_bw(data, "测试文件.dat", ver=10, mode="individual")
        assert decoded is not None
        assert decoded == data
        assert meta["filename"] == "测试文件.dat"

    def test_output_directory_structure_individual(self):
        """Verify individual mode creates {base_dir}/{filename_base}-individual/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "myfile.dat")
            with open(file_path, "wb") as f:
                f.write(b"test data here" * 5)
            generate_qr_images(file_path=file_path, ver=10, base_dir=tmpdir, mode="individual")
            indiv_dir = os.path.join(tmpdir, "myfile-individual")
            assert os.path.isdir(indiv_dir)
            files = os.listdir(indiv_dir)
            assert any(f.startswith("qr_") and f.endswith(".png") for f in files)

    def test_output_directory_structure_canvas(self):
        """Verify canvas mode creates {base_dir}/{filename_base}-canvas/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "myfile.dat")
            with open(file_path, "wb") as f:
                f.write(b"test data here" * 5)
            generate_qr_images(file_path=file_path, ver=10, base_dir=tmpdir, mode="canvas")
            canvas_dir = os.path.join(tmpdir, "myfile-canvas")
            assert os.path.isdir(canvas_dir)
            files = os.listdir(canvas_dir)
            assert any(f.startswith("qrcode_") and f.endswith(".png") for f in files)

    def test_output_directory_structure_both(self):
        """Verify both mode creates both subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "myfile.dat")
            with open(file_path, "wb") as f:
                f.write(b"test data here" * 5)
            generate_qr_images(file_path=file_path, ver=10, base_dir=tmpdir, mode="both")
            assert os.path.isdir(os.path.join(tmpdir, "myfile-canvas"))
            assert os.path.isdir(os.path.join(tmpdir, "myfile-individual"))


# ===================== Tests: Color QR encode/decode =====================


class TestColorQREncodeDecode:
    """Test color (generator_bin2) QR code generation and decode round-trip."""

    @pytest.mark.skipif(not HAS_V3, reason="qrgb not installed")
    def test_small_file(self):
        data = b"Color QR test!" * 10
        decoded, meta = _generate_and_decode_color(data, "color_test.txt", ver=10)
        assert decoded is not None
        assert decoded == data
        assert meta["filename"] == "color_test.txt"
        assert meta["file_crc32"] == (zlib.crc32(data) & 0xFFFFFFFF)

    @pytest.mark.skipif(not HAS_V3, reason="qrgb not installed")
    def test_binary_data(self):
        data = bytes(range(256)) * 3
        decoded, meta = _generate_and_decode_color(data, "color_bin.dat", ver=10)
        assert decoded is not None
        assert decoded == data

    @pytest.mark.skipif(not HAS_V3, reason="qrgb not installed")
    def test_crc32_verification(self):
        data = os.urandom(300)
        decoded, meta = _generate_and_decode_color(data, "color_crc.bin", ver=10)
        expected_crc = zlib.crc32(data) & 0xFFFFFFFF
        assert meta["file_crc32"] == expected_crc

    @pytest.mark.skipif(not HAS_V3, reason="qrgb not installed")
    def test_unicode_filename(self):
        data = b"color unicode"
        decoded, meta = _generate_and_decode_color(data, "彩色测试.dat", ver=10)
        assert decoded is not None
        assert meta["filename"] == "彩色测试.dat"


# ===================== Tests: QRConfig =====================


class TestQRConfig:
    def test_version_range(self):
        QRConfig(1)
        QRConfig(40)
        try:
            QRConfig(0)
            assert False, "Should raise ValueError"
        except ValueError:
            pass
        try:
            QRConfig(41)
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_data_per_qr_positive(self):
        cfg = QRConfig(20)
        assert cfg.data_per_qr > 0
        assert cfg.qr_max_bytes > cfg.header_len

    def test_calc_qr_max_bytes(self):
        from qrcast.bw.v2.generator2 import calc_qr_max_bytes
        # Version 1 with L error correction
        cap = calc_qr_max_bytes(1)
        assert cap > 0
        # Higher version should have more capacity
        assert calc_qr_max_bytes(40) > calc_qr_max_bytes(1)


import pytest
