# qrcast CLI 使用手册

安装后，全局命令 `qrcast` 可用，也支持 `python -m qrcast`。

```bash
qrcast --help
python -m qrcast --help
```

---

## 命令概览

| 命令 | 功能 | 典型场景 |
|------|------|----------|
| `generate` | 将文件编码为 QR canvas 图片 | 发送端 |
| `display` | 全屏轮播展示 canvas 图片 | 发送端展示 |
| `receive` | 摄像头捕获 QR 码并还原文件 | 接收端 |
| `verify` | 从已保存的 canvas 图片还原文件（无需摄像头） | 离线验证/测试 |
| `quick-send` | 单 QR 码快速发送小文件 | 极简传输 |

---

## generate — 生成 QR Canvas

```bash
qrcast generate <mode> <file> [options]
```

### 参数

| 参数 | 说明 |
|------|------|
| `mode` | `v1` / `v2` / `v3` |
| `file` | 要编码的文件路径 |

### 通用选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--output-dir` | `./tmp` | 输出目录 |
| `--compress` | `false` | 先用 7z 压缩再编码 |
| `--save-chunks` | `false` | 保存单个 QR 切片（仅 v1/v2） |

### V2 专属选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--ver` | `32` | QR 版本 1-40，越大单码容量越高 |

### V3 专属选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--v3-mode` | `bin` | `bin`(原始二进制) 或 `text`(base64) |

### 示例

```bash
# V1 固定版本
qrcast generate v1 document.pdf --output-dir ./tmp

# V2 自定义 QR 版本（ver 20 更小更密）
qrcast generate v2 document.pdf --ver 20 --compress --output-dir ./tmp

# V3 RGB QR（推荐 bin 模式）
qrcast generate v3 document.pdf --v3-mode bin --compress --output-dir ./tmp

# 保存单个 QR 切片用于调试
qrcast generate v2 image.png --save-chunks --output-dir ./debug
```

---

## display — 全屏展示

```bash
qrcast display [image_dir] [options]
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `image_dir` | `./tmp` | 包含 canvas 图片的目录 |

### 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-i, --interval` | `2` | 每张图片显示秒数 |
| `-p, --pattern` | `qrcode_*.png` | 文件匹配模式 |

### 示例

```bash
qrcast display ./tmp
qrcast display ./tmp -i 1.5 -p "canvas_*.png"
```

操作提示：按 `q` 退出，按任意键立即切下一张。

---

## receive — 摄像头接收

```bash
qrcast receive [options]
```

### 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--camera` | `0` | 摄像头索引 |
| `--version` | `v2` | 解码版本 `v1`/`v2`/`v3` |
| `--v3-mode` | `bin` | V3 模式 `bin`/`text` |

### 示例

```bash
# 接收 V2 B&W QR
qrcast receive --camera 0 --version v2

# 接收 V3 RGB QR（bin 模式）
qrcast receive --camera 0 --version v3 --v3-mode bin
```

操作提示：窗口对准 QR 码，自动识别拼接。按 `q` 退出。接收完成后文件保存至当前目录。

---

## verify — 离线验证

无需摄像头，直接从已保存的 canvas PNG 还原文件，用于测试生成结果。

```bash
qrcast verify <image_dir> <output_dir> [options]
```

### 参数

| 参数 | 说明 |
|------|------|
| `image_dir` | 包含 canvas 图片的目录 |
| `output_dir` | 还原文件输出目录 |

### 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--version` | `v2` | 解码版本 `v1`/`v2`/`v3` |
| `--v3-mode` | `bin` | V3 模式 `bin`/`text` |

### 示例

```bash
qrcast verify ./tmp ./verify_output --version v1
qrcast verify ./tmp ./verify_output --version v3 --v3-mode bin
```

---

## quick-send — 快速单码发送

针对小文件（V2 ver40 单 QR 码容量内），直接生成单个 QR 码显示，无需 canvas。

```bash
qrcast quick-send <file> [options]
```

### 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--minify` | `false` | 若是 `.py` 文件，先压缩代码再编码 |

### 示例

```bash
qrcast quick-send script.py --minify
qrcast quick-send config.json
```

---

## 完整工作流示例

### 场景：两台无网络电脑传文件

**发送端（电脑 A）：**
```bash
# 1. 生成（V2 + 压缩，平衡容量和可靠性）
qrcast generate v2 report.pdf --compress --output-dir ./tmp

# 2. 全屏展示
qrcast display ./tmp -i 2
```

**接收端（电脑 B）：**
```bash
# 摄像头接收
qrcast receive --camera 0 --version v2
```

### 场景：本地验证生成结果

```bash
qrcast generate v2 test.zip --output-dir ./tmp
qrcast verify ./tmp ./verify_output --version v2
diff test.zip ./verify_output/output.bin   # 应该完全一致
```

### 场景：手机拍照接收（不用实时摄像头）

```bash
# 发送端展示 QR 码
qrcast generate v2 data.txt --output-dir ./tmp
qrcast display ./tmp -i 3

# 接收端用手机拍照保存到 ./phone_pics
# 然后电脑上验证：
qrcast verify ./phone_pics ./recovered --version v2
```

---

## 版本选择指南

| 需求 | 推荐版本 | 理由 |
|------|----------|------|
| 大文件、高可靠性 | V2 ver 20-32 | 容量大，容错适中 |
| 极大文件、最高密度 | V2 ver 40 | 单码容量最大 |
| 无网络、快速传小文件 | V2 quick-send | 单码直接显示 |
| 有高清屏幕、追求速度 | V3 bin | 3 倍密度，传输更快 |
| 兼容性优先（旧设备） | V1 | 固定参数，最稳定 |

---

## 故障排查

| 问题 | 可能原因 | 解决 |
|------|----------|------|
| 接收不完整 | 摄像头帧率低 / QR 码切换太快 | 增大 `display` 的 `--interval` |
| 识别率低 | 屏幕反光 / 摄像头对焦差 | 调暗屏幕、避免反光、手动对焦 |
| V3 报错 `No module named 'qrgb'` | 未安装 V3 依赖 | `pip install qrcast[full]` |
| 生成后文件比原文件大 | 未开 `--compress` | 大文件建议加 `--compress` |
| quick-send 失败 | 文件超过单 QR 容量 | 换用 `generate v2 --ver 40` |
