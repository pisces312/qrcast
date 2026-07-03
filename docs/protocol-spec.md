
# QRCast 协议规范

**版本**: v1.0
**最后更新**: 2026-07-03

本文档是 QRCast 协议的唯一权威来源，Sender 和 Receiver 的所有实现都必须遵循此规范。

---

## 1. 概述

QRCast 支持两种传输模式：
- **CHUNKED 模式**：大文件分多个二维码传输
- **RAW 模式**：小文件单张二维码直接传输

---

## 2. CHUNKED 模式（分块）

### 2.1 数据格式

每个二维码的 payload 结构（大端序 Big-endian）：

```
[0-3]   seq (4 bytes)      - 当前块序号，从 0 开始
[4-7]   total (4 bytes)    - 总块数
[8+]    payload (N bytes)  - 文件数据块
```

- **Header 长度**: 固定 8 bytes
- **Endianness**: Big-endian（网络字节序）

### 2.2 组装规则

1. Receiver 收集所有块，按 `seq` 序号排序
2. 当收集到 `total` 个不同的块时，组装完成
3. 组装方式：按序号顺序拼接所有块的 `payload` 部分
4. 忽略重复块（相同 seq）

### 2.3 压缩支持

- Sender 可以选择用 7z (LZMA2) 压缩文件后再分块
- Receiver 必须检测文件头，自动识别并解压：
  - `37 7A BC AF 27 1C` → 7z 格式
  - `50 4B 03 04` → ZIP 格式
- 解压后才是最终文件

### 2.4 文件扩展名检测

Receiver 组装完成后，根据文件头自动推断扩展名：
- 7z: `.7z`
- ZIP: `.zip`
- 其他: `.bin` 或 `.txt`

---

## 3. RAW 模式（原始数据）

### 3.1 数据格式

整个二维码的 payload 就是文件原始字节，无任何头信息。

```
[raw file bytes]
```

### 3.2 适用场景

- 文件大小 ≤ 单张二维码容量
- QR Version 40 + Error Correction L: 约 2953 bytes
- 不支持压缩（Sender 可以先压缩再用 RAW 模式）

---

## 4. 二维码配置

### 4.1 Sender 端

| 模式 | QR 版本 | 纠错级别 | 编码模式 |
|------|---------|---------|---------|
| V1 (BW) | 32 (固定) | L | Binary |
| V2 (BW) | 1-40 (可配置) | L | Binary |
| V3 (RGB) | 40 (推荐) | M | 3 通道 Binary |

### 4.2 Receiver 端

- 支持所有 QR 版本（自动检测）
- 支持所有纠错级别（自动检测）
- 摄像头分辨率：默认 1920x1080

---

## 5. 版本兼容性

### 5.1 协议版本号

协议本身有版本号，编码在 QR 内容的**前 4 字节**（未来版本）：

| 协议版本 | 说明 |
|---------|------|
| v1.0    | 当前版本，无前导 magic number |
| v2.0    | （未来）增加 magic number 和校验和 |

### 5.2 向后兼容

- Receiver 必须支持所有旧版本协议
- Sender 生成的二维码必须明确标识协议版本（v2.0+）

---

## 6. 测试向量

用于验证实现正确性的测试数据。

### 6.1 CHUNKED 模式

测试文件: `"hello world"` (11 bytes)，分 2 块:

- **Chunk 0**:
  - seq: 0 (0x00 0x00 0x00 0x00)
  - total: 2 (0x00 0x00 0x00 0x02)
  - payload: "hello" (0x68 0x65 0x6C 0x6C 0x6F)
  - 完整: `00 00 00 00 00 00 00 02 68 65 6C 6C 6F`

- **Chunk 1**:
  - seq: 1 (0x00 0x00 0x00 0x01)
  - total: 2 (0x00 0x00 0x00 0x02)
  - payload: " world" (0x20 0x77 0x6F 0x72 0x6C 0x64)
  - 完整: `00 00 00 01 00 00 00 02 20 77 6F 72 6C 64`

组装结果: `"hello world"`

---

## 7. 实现参考

### Python (Sender)
```python
import struct

# 编码 CHUNKED 头
header = struct.pack('&gt;II', seq, total)
payload = header + chunk_data
```

### Kotlin (Receiver)
```kotlin
import java.nio.ByteBuffer
import java.nio.ByteOrder

// 解码 CHUNKED 头
val buffer = ByteBuffer.wrap(payload).order(ByteOrder.BIG_ENDIAN)
val seq = buffer.int
val total = buffer.int
val data = ByteArray(buffer.remaining())
buffer.get(data)
```

