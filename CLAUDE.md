# QRCast — Sender (Python)

QR-based offline file transfer tool. Generates b&w (v2) and color RGB (v3) QR code canvases/individual images, verifies and reconstructs files.

## Environment
- **Python**: `D:\nili\dev\conda_envs\qrcast_env\python.exe` (conda env: qrcast_env, Python 3.11)
- All scripts, tests, and CLI commands MUST use this Python, not system/conda-base python
- Install deps: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pip install <pkg>`
- Run tests: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pytest tests/ -v`

## Project Structure
```
qrcast/
  qrcast/
    bw/           # v2: B&W QR (configurable ver 1-40)
      generator.py, generator2.py      # 分步生成：文件 → 切片 → QR 图片序列
      gen_individual_all_in_one.py     # 单文件一站式生成黑白 QR 序列（v2 payload，无压缩）
      gen_and_display_individual.py    # 边生成边显示：生产者-消费者模式，CLI 一键发送
      display.py                       # 播放已生成的 QR 图片序列（全屏 cv2）
      quick_sender.py                  # 单文件单 QR 码快速发送（小文件）
      verifier.py, verifier2.py        # 验证 QR 序列并重建原始文件
      receiver.py, receiver2.py        # 摄像头实时接收端（黑白模式）
    rgb/          # v3: RGB color QR (was qrcast/v3/)
      generator_bin.py, generator_bin2.py, generator_text.py
      verifier_bin.py, verifier_bin2.py, verifier_text.py
      receiver_bin.py, receiver_bin2.py, receiver_text.py
    common.py     # shared: CANVAS_W/H, parse_payload_v2, etc.
    cli.py        # unified CLI: qrcast generate|display|verify|receive|quick-send
  tests/
    test_v2_roundtrip.py  # 25 unit tests (all pass)
```

## bw/ 脚本速查表（B&W 黑白二维码）

| 脚本 | 功能 | 典型场景 |
|------|------|---------|
| `gen_and_display_individual.py` | **边生成边全屏显示**，生产者-消费者并发 | **CLI 一键发送文件** — 最常用 |
| `gen_individual_all_in_one.py` | 单文件生成 QR 序列，保存到磁盘 | 预生成图片，离线测试或单独播放 |
| `display.py` | 播放已生成的 QR 图片序列 | 配合 `gen_individual_all_in_one` 使用 |
| `quick_sender.py` | 单文件编码为单张 QR 码 | 小文件（< 3KB）快速发送 |
| `receiver2.py` | 摄像头实时接收，重建文件 | 接收端运行 |
| `verifier2.py` | 验证已保存的 QR 图片序列，重建文件 | 离线验证/调试 |

## CLI 用法示例

### 1. 一键发送（推荐）
```bash
# 边生成边全屏播放，5 fps，适合手机接收
python -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2

# 启用 7z 压缩后再编码
python -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.2 --compress
```

### 2. 分步：生成 → 显示
```bash
# 生成 QR 序列到 ./tmp/myfile-individual/
python -m qrcast.bw.gen_individual_all_in_one myfile.zip --ver 20 --output-dir ./tmp

# 全屏播放（0.5 秒/帧）
python -m qrcast.bw.display ./tmp/myfile-individual --interval 0.5
```

### 3. 小文件单 QR 码快速发送
```bash
python -m qrcast.bw.quick_sender myfile.txt
```

### 4. 接收端（摄像头）
```bash
python -m qrcast.bw.receiver2
```

### 5. 验证与重建
```bash
python -m qrcast.bw.verifier2 ./tmp/myfile-individual --output ./output/myfile.zip
```

## Dependency Notes
- `qrgb` library required for v3 (RGB color) mode — installed in qrcast_env
- v3 tests skip gracefully if qrgb unavailable (`HAS_V3 = False`)
