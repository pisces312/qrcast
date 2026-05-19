# QRCast Payload Format v2 Specification

> 状态: 已实施  
> 默认 MAX_QR_VER: 20

---

## 1. 设计目标

- **编入文件名**：receiver 输出不再固定为 `output.bin`
- **CRC32 校验**：文件级完整性验证
- **协议版本标识**：区分 v1 与 v2，支持后续扩展
- **压缩标志**：明确标识 payload 是否经过 7z 压缩
- **向后兼容**：v2 receiver 拒绝 v1 payload（通过 `proto_ver` 检测）

---

## 2. Payload Format

### 2.1 Fixed Header（每个块都有，12 bytes）

| 字段 | 大小 | 类型 | 说明 |
|------|------|------|------|
| `seq` | 4B | uint32 BE | 当前块序号 (0-based) |
| `total` | 4B | uint32 BE | 总块数 |
| `data_len` | 2B | uint16 BE | Data Segment 长度 |
| `proto_ver` | 1B | uint8 | 协议版本，固定 `0x02` |
| `flags` | 1B | uint8 | bit0=是否 7z 压缩，bit1-7 预留 |

### 2.2 Data Segment（seq == 0 时）

| 字段 | 大小 | 类型 | 说明 |
|------|------|------|------|
| `filename_len` | 1B | uint8 | 文件名 UTF-8 长度 |
| `filename` | N B | UTF-8 | 原始文件名 |
| `file_crc32` | 4B | uint32 BE | 完整原始文件的 CRC32 |
| `file_size` | 4B | uint32 BE | 原始文件大小（bytes）|
| `chunk_data` | M B | bytes | 第 0 块实际文件数据 |

> seq=0 同时携带元数据 + 第一块数据，不额外增加 QR 码数量。

### 2.3 Data Segment（seq > 0 时）

| 字段 | 大小 | 类型 | 说明 |
|------|------|------|------|
| `chunk_data` | M B | bytes | 第 seq 块实际文件数据 |

---

## 3. 容量计算（ver 20）

```
CHANNEL_CAPACITY(ver20) = 1161 bytes/channel
单 RGB QR 总容量 = 1161 * 3 = 3483 bytes
HEADER_LEN = 12 bytes
DATA_PER_QR = 3483 - 12 = 3471 bytes

seq=0 时元数据开销 = 1 + len(filename) + 4 + 4 = 9 + len(filename)
seq=0 实际可用数据 = 3471 - (9 + len(filename))
seq>0 实际可用数据 = 3471 bytes
```

---

## 4. 编码端（generator_bin2.py）修改点

| 修改项 | 内容 |
|--------|------|
| `MAX_QR_VER` 默认值 | `20`（可配置 1-40） |
| `HEADER_LEN` | `12`（原 10，新增 `proto_ver` + `flags`） |
| `flags` 计算 | 若启用压缩，`flags = 0x01`，否则 `0x00` |
| `proto_ver` | 固定 `0x02` |
| `seq=0` 特殊处理 | 预留 `meta_overhead = 1 + len(filename) + 4 + 4`，先塞入元数据再塞 chunk_data |
| CRC32 计算 | `zlib.crc32(file_bytes) & 0xFFFFFFFF` |
| 块切分逻辑 | seq=0 的 chunk 大小 = `data_per_qr - meta_overhead`，其余块满容量 |

---

## 5. 解码端（receiver_bin2.py）修改点

| 修改项 | 内容 |
|--------|------|
| `parse_payload` → `parse_payload_v2` | 解析 12 bytes Header，检查 `proto_ver == 0x02` |
| `seq=0` 特殊处理 | 从 Data Segment 解析 `filename`, `file_crc32`, `file_size` |
| 缓存逻辑 | 收到 seq=0 前可缓存其他块，等元数据到后组装 |
| 组装完成后 | 计算 CRC32 比对，不匹配报警告 |
| 解压逻辑 | 根据 `flags & 0x01` 决定是否 7z 解压 |
| 输出文件名 | 使用解析到的 `filename` |

---

## 6. common.py 新增方法

```python
def parse_payload_v2(data_bytes):
    """
    解析 v2 payload。
    返回 dict: {
        seq, total, data_len, proto_ver, flags,
        filename, file_crc32, file_size, chunk_data
    }
    或解析失败返回 None。
    """
```

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| seq=0 丢失导致无法获取元数据 | sender 循环播放所有 QR 码；receiver 缓存其他块等 seq=0 |
| 文件名过长 | 1B `filename_len` 上限 255，超长截断 |
| ver 20 容量下降 | ver 32→20 单 QR 容量下降约 50%，QR 码数量增加，需确认文件大小可接受 |
| v1/v2 混用 | `proto_ver` 明确区分，receiver_bin2 只认 v2 |

---

## 8. 字段是否还需要增加？

| 字段 | 评估 | 结论 |
|------|------|------|
| `proto_ver` | 必须 | 已加入 |
| `flags` | 建议 | 已加入（压缩标志） |
| `file_size` | 建议 | 已加入（长度验证 + 进度） |
| `filename` | 按需求 | 已加入 |
| `file_crc32` | 按需求 | 已加入 |
| chunk-level CRC | 不需要 | QR RS 纠错 + zxingcpp 已保证块级可靠 |
| timestamp | 不需要 | 增加开销，场景用不上 |
| mime_type | 不需要 | 增加开销，场景用不上 |
| 加密标志 | 不需要 | 当前无此需求 |

**结论：当前字段已足够，不再增加。**
