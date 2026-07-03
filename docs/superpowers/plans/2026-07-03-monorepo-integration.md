# QRCast Monorepo 集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 qrcast (Python) 和 qrcast-android 两个独立仓库合并为 monorepo，统一管理但保留各平台独立构建能力，完整保留 git 历史。

**Architecture:** 使用 `git merge --allow-unrelated-histories` 合并两个独立仓库的历史，然后将代码分别移动到 `sender/` 和 `receiver-android/` 子目录，合并文档和配置文件。

**Tech Stack:** Git, Python 3.11, Android Gradle Plugin 8.9.1, Kotlin 2.1.0

## 全局约束

- **保留完整 git 历史**：所有提交必须可通过 `git log --follow` 追溯
- **最小侵入原则**：移动代码后尽量少修改内部逻辑
- **可回滚**：每一步都可以安全回滚到之前状态
- **两边构建必须正常**：完成迁移后 sender 和 receiver-android 都必须能正常构建和测试
- **独立版本号**：sender 用 `pyproject.toml`，receiver-android 用 `build.gradle.kts`，各自维护版本

---

## 前置准备：提交并推送两边的未提交更改

### Task 0: 提交并推送 qrcast 仓库更改

**Files:**
- Check: `D:\my-projects\qrcast\.git`

**Interfaces:**
- Consumes: 无（这是第一个任务）
- Produces: qrcast 仓库 clean 状态，所有更改已推送到 remote

- [ ] **Step 1: 检查 qrcast 当前状态**

```bash
cd D:\my-projects\qrcast
git status
```

Expected: 列出所有未提交的更改

- [ ] **Step 2: 提交 qrcast 所有更改**

```bash
git add -A
git commit -m "chore: commit all pending changes before monorepo merge"
```

- [ ] **Step 3: 推送到 remote**

```bash
git push
```

- [ ] **Step 4: 确认 clean 状态**

```bash
git status
```

Expected: "nothing to commit, working tree clean"

---

### Task 1: 提交并推送 qrcast-android 仓库更改

**Files:**
- Check: `D:\my-projects\qrcast-android\.git`

**Interfaces:**
- Consumes: 无
- Produces: qrcast-android 仓库 clean 状态，所有更改已推送到 remote

- [ ] **Step 1: 检查 qrcast-android 当前状态**

```bash
cd D:\my-projects\qrcast-android
git status
```

Expected: 列出所有未提交的更改

- [ ] **Step 2: 提交 qrcast-android 所有更改**

```bash
git add -A
git commit -m "chore: commit all pending changes before monorepo merge"
```

- [ ] **Step 3: 推送到 remote**

```bash
git push
```

- [ ] **Step 4: 确认 clean 状态**

```bash
git status
```

Expected: "nothing to commit, working tree clean"

---

## 第一阶段：合并仓库

### Task 2: 添加 Android remote 并 fetch

**Files:**
- Modify: `D:\my-projects\qrcast\.git\config`

**Interfaces:**
- Consumes: Task 0 和 Task 1 的 clean 状态
- Produces: qrcast 仓库添加了 android remote，已 fetch 所有提交

- [ ] **Step 1: 切换到 qrcast 仓库**

```bash
cd D:\my-projects\qrcast
```

- [ ] **Step 2: 添加 android remote**

```bash
git remote add android ../qrcast-android
```

- [ ] **Step 3: 验证 remote 已添加**

```bash
git remote -v
```

Expected: 显示 "android ../qrcast-android (fetch)" 和 "android ../qrcast-android (push)"

- [ ] **Step 4: Fetch android remote**

```bash
git fetch android
```

Expected: 显示 fetch 进度，获取所有 android/main 的提交

---

### Task 3: 合并两个独立历史

**Files:**
- Modify: 工作区（合并冲突文件需要处理）

**Interfaces:**
- Consumes: Task 2 的 android remote fetch 完成
- Produces: 合并后的工作区，冲突已标记待解决

- [ ] **Step 1: 执行合并（不自动提交）**

```bash
git merge --allow-unrelated-histories android/main --no-commit
```

Expected: 显示 "Automatic merge failed; fix conflicts and then commit the result."（预期会有冲突）

- [ ] **Step 2: 查看冲突文件列表**

```bash
git diff --name-only --diff-filter=U
```

Expected: 冲突文件列表（预计：README.md, LICENSE, CLAUDE.md, .gitignore）

- [ ] **Step 3: 暂不解决冲突，只确认合并状态**

```bash
git status
```

Expected: 显示 "You have unmerged paths." 以及冲突文件列表

---

## 第二阶段：目录重构

### Task 4: 创建 sender 目录并移动 Python 文件

**Files:**
- Create: `D:\my-projects\qrcast\sender\`
- Modify: 所有 Python 相关文件的路径

**Interfaces:**
- Consumes: Task 3 合并后的工作区
- Produces: Python 文件全部移动到 `sender/` 子目录

- [ ] **Step 1: 创建 sender 目录**

```bash
cd D:\my-projects\qrcast
mkdir sender
mkdir sender\docs
```

- [ ] **Step 2: 移动 Python 核心文件**

```bash
mv qrcast/ sender/
mv tests/ sender/
mv pyproject.toml sender/
mv requirements.txt sender/
mv env.yml sender/
```

- [ ] **Step 3: 移动版本特定文档**

```bash
mv docs/v1_bw_fixed.md sender/docs/
mv docs/v2_bw_configurable.md sender/docs/
mv docs/v3_rgb_qr.md sender/docs/
```

- [ ] **Step 4: 移动其他 Python 相关文件**

```bash
mv test_qrcode_leading_zero.py sender/
mv gen_and_display.bat sender/
```

- [ ] **Step 5: 删除 sender 子目录的 .gitignore（后续合并到根目录）**

```bash
rm -f sender/.gitignore
```

- [ ] **Step 6: 验证目录结构**

```bash
ls -la sender/
```

Expected: 看到 qrcast/, tests/, pyproject.toml, requirements.txt, env.yml, docs/, test_qrcode_leading_zero.py, gen_and_display.bat

---

### Task 5: 创建 receiver-android 目录并移动 Android 文件

**Files:**
- Create: `D:\my-projects\qrcast\receiver-android\`
- Modify: 所有 Android 相关文件的路径

**Interfaces:**
- Consumes: Task 4 的 sender 目录创建完成
- Produces: Android 文件全部移动到 `receiver-android/` 子目录

- [ ] **Step 1: 创建 receiver-android 目录**

```bash
cd D:\my-projects\qrcast
mkdir receiver-android
```

- [ ] **Step 2: 移动 Android 核心构建文件**

```bash
mv app/ receiver-android/
mv gradle/ receiver-android/
mv build.gradle.kts receiver-android/
mv settings.gradle.kts receiver-android/
mv gradlew receiver-android/
mv gradlew.bat receiver-android/
mv gradle.properties receiver-android/
mv build.sh receiver-android/
```

- [ ] **Step 3: 移动其他 Android 相关文件**

```bash
mv QRCast-v*.apk receiver-android/ 2>/dev/null || true
mv *.idsig receiver-android/ 2>/dev/null || true
mv .kotlin receiver-android/ 2>/dev/null || true
```

- [ ] **Step 4: 保留 receiver-android 目录的 .gitignore 用于后续合并**

```bash
# 从 android 合并过来的 .gitignore 应该在根目录，移动过去
mv .gitignore receiver-android/.gitignore.android
```

- [ ] **Step 5: 验证目录结构**

```bash
ls -la receiver-android/
```

Expected: 看到 app/, gradle/, build.gradle.kts, settings.gradle.kts, gradlew*, build.sh, .gitignore.android

---

## 第三阶段：合并配置文件

### Task 6: 统一根目录 .gitignore

**Files:**
- Modify: `D:\my-projects\qrcast\.gitignore`
- Delete: `D:\my-projects\qrcast\receiver-android\.gitignore.android`

**Interfaces:**
- Consumes: Task 4 和 Task 5 的目录重构完成
- Produces: 根目录统一的 .gitignore，包含两边的规则

- [ ] **Step 1: 查看当前根目录和 Android 的 .gitignore**

```bash
cat .gitignore
echo "---"
cat receiver-android/.gitignore.android
```

- [ ] **Step 2: 合并内容到根目录 .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.venv/
env/
venv/
tmp/

# Android
*.iml
.gradle/
/local.properties
/.idea/
.DS_Store
/build/
/captures/
.externalNativeBuild
.cxx
*.apk
*.ap_
*.aab
*.idsig
.kotlin/

# OS
Thumbs.db
```

- [ ] **Step 3: 删除临时文件**

```bash
rm receiver-android/.gitignore.android
```

- [ ] **Step 4: 验证 .gitignore 生效**

```bash
git status
```

Expected: 不会列出 __pycache__, .gradle, build 等目录的未追踪文件

---

### Task 7: 合并根目录 CLAUDE.md

**Files:**
- Modify: `D:\my-projects\qrcast\CLAUDE.md`
- Check: `D:\my-projects\qrcast\receiver-android\CLAUDE.md`

**Interfaces:**
- Consumes: Task 6 的 .gitignore 合并完成
- Produces: 根目录统一的 CLAUDE.md，包含两边的环境配置

- [ ] **Step 1: 查看 Android 的 CLAUDE.md 内容**

```bash
cat receiver-android/CLAUDE.md
```

- [ ] **Step 2: 合并内容到根目录 CLAUDE.md**

编辑文件，统一结构：

```markdown
# QRCast — Monorepo

跨平台二维码离线文件传输工具。包含：
- Sender (Python): 二维码生成端（黑白 V1/V2 + 彩色 V3）
- Receiver (Android): Android 扫码接收端

## 全局环境

### 工具路径
- Git: `C:\nili\dev\git`
- Conda: `C:\nili\dev\miniconda3`
- Android SDK: `D:\nili\dev\android_sdk`
- JDK: `D:\nili\dev\AndroidStudio\jbr` (JBR 21, Java 17)
- Flutter SDK: `D:\nili\dev\flutter`

---

## Sender (Python)

### 环境
- Python: `D:\nili\dev\conda_envs\qrcast_env\python.exe` (conda env: qrcast_env, Python 3.11)
- 工作目录: `sender/`

### 命令
- 安装依赖: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pip install -e .`
- 运行测试: `D:/nili/dev/conda_envs/qrcast_env/python.exe -s -m pytest tests/ -v`
- 生成 + 显示: `cd sender && D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast.bw.gen_and_display_individual`

### 项目结构
```
sender/
  qrcast/
    bw/           # V1/V2: 黑白二维码
      generator.py, display.py, verifier.py, receiver.py
    v3/           # V3: RGB 彩色二维码
      generator_bin.py, receiver_bin.py, etc.
    common.py     # 共享工具
    cli.py        # 统一 CLI
  tests/
  docs/           # 版本特定文档
  pyproject.toml
```

---

## Receiver (Android)

### 环境
- compileSdk: 35
- AGP: 8.9.1, Gradle: 9.4.1, Kotlin: 2.1.0
- NDK: 27.0.12077973
- 工作目录: `receiver-android/`

### 签名配置
- 默认密钥: `D:\nili\my-git-projects\my-backup\backup-settings\my-android-release.keystore`
- alias: `pisces312`
- 密码: `314159`

### 命令
- Debug 构建: `cd receiver-android && ./gradlew assembleDebug`
- Release 构建: `cd receiver-android && ./gradlew assembleRelease`
- Clean: `cd receiver-android && ./gradlew clean`
- Build 脚本: `cd receiver-android && ./build.sh debug/release`

### 输出路径
- Debug APK: `receiver-android/app/build/outputs/apk/debug/app-debug.apk`
- Release APK: `receiver-android/app/build/outputs/apk/release/app-release.apk`

### 项目结构
```
receiver-android/
  app/src/main/kotlin/com/example/qr_transfer/
    MainActivity.kt       - 相机扫码、文件组装
    SettingsActivity.kt   - 输出目录配置
    LogActivity.kt        - 日志查看
    LogCollector.kt       - 日志收集器
    QrTransferApp.kt      - Application 基类
```

## 协议规范
参见: `docs/protocol-spec.md`

## 代码风格
- Python: PEP 8
- Kotlin: AndroidX conventions
```

- [ ] **Step 3: 删除 receiver-android 的 CLAUDE.md**

```bash
rm receiver-android/CLAUDE.md
```

- [ ] **Step 4: 验证文件存在**

```bash
ls -la CLAUDE.md
```

---

### Task 8: 更新根目录 README.md

**Files:**
- Modify: `D:\my-projects\qrcast\README.md`
- Check: `D:\my-projects\qrcast\receiver-android\README.md`

**Interfaces:**
- Consumes: Task 7 的 CLAUDE.md 合并完成
- Produces: 根目录统一的 README.md，项目总览

- [ ] **Step 1: 查看 Android 的 README.md 内容**

```bash
cat receiver-android/README.md
```

- [ ] **Step 2: 编写根目录统一的 README.md**

```markdown
# QRCast / 码上通

跨平台二维码离线文件传输工具。无需网络、无需配对，有光就能传。

**Sender (Python):** 生成端，支持黑白二维码 (V1/V2) 和 RGB 彩色二维码 (V3)
**Receiver (Android):** 接收端，Android 应用实时扫码组装文件

---

## 快速开始

### Sender (Python)

```bash
cd sender
pip install -e .

# 生成并显示二维码
qrcast generate v2 myfile.zip --ver 30 --interval 0.2
```

### Receiver (Android)

```bash
cd receiver-android
./build.sh debug
# 安装 app/build/outputs/apk/debug/app-debug.apk
```

---

## 项目结构

```
qrcast/
├── sender/              # Python 发送端
│   ├── qrcast/         # Python package
│   │   ├── bw/         # 黑白二维码 (V1/V2)
│   │   └── v3/         # RGB 彩色二维码
│   ├── tests/
│   └── pyproject.toml
├── receiver-android/   # Android 接收端
│   ├── app/
│   └── build.gradle.kts
├── docs/               # 统一文档
│   └── protocol-spec.md # 协议规范（权威来源）
├── CLAUDE.md           # 开发环境配置
└── README.md
```

---

## 协议规范

### CHUNKED 模式（分块传输）
每个二维码编码：`[seq(4B big-endian)][total(4B big-endian)][payload]`

- 头长度：8 bytes
- 序号从 0 开始
- 接收端收集所有块后按序号拼接
- 自动识别 7z/zip 压缩包并解压

### RAW 模式（原始数据）
单张二维码直接编码文件原始字节，无分块头。适合小文件。

详细协议文档：[docs/protocol-spec.md](docs/protocol-spec.md)

---

## 兼容性矩阵

| Sender 版本 | Receiver-Android 版本 | 支持协议 |
|------------|----------------------|---------|
| v1.0.x     | v1.0.x              | CHUNKED, RAW |

---

## License

MIT
```

- [ ] **Step 3: 删除 receiver-android 的 README.md**

```bash
rm receiver-android/README.md
```

- [ ] **Step 4: 保留 receiver-android 的 LICENSE 吗？**

两边都是 MIT，保留根目录的即可：

```bash
rm receiver-android/LICENSE
```

---

### Task 9: 创建统一的 protocol-spec.md

**Files:**
- Create: `D:\my-projects\qrcast\docs\protocol-spec.md`

**Interfaces:**
- Consumes: Task 8 的 README 更新完成
- Produces: 统一的协议规范文档

- [ ] **Step 1: 查看现有文档中的协议描述**

```bash
cat docs/payload-v2-spec.md
cat sender/docs/v2_bw_configurable.md 2>/dev/null || echo "skip"
```

- [ ] **Step 2: 创建 docs/protocol-spec.md**

```markdown
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
header = struct.pack('>II', seq, total)
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
```

- [ ] **Step 3: 验证文件创建成功**

```bash
ls -la docs/protocol-spec.md
```

---

## 第四阶段：配置更新

### Task 10: 更新 .vscode/tasks.json 路径

**Files:**
- Modify: `D:\my-projects\qrcast\.vscode\tasks.json`

**Interfaces:**
- Consumes: Task 9 的 protocol-spec.md 创建完成
- Produces: 更新后的 tasks.json，所有任务路径指向正确的子目录

- [ ] **Step 1: 查看当前 tasks.json 内容**

```bash
cat .vscode/tasks.json
```

- [ ] **Step 2: 更新所有任务的 cwd 和命令路径**

对于每个 Python 任务：
- 添加 `"cwd": "${workspaceFolder}/sender"`
- 如果命令中有相对路径，更新为 sender/ 下的路径

对于每个 Android 任务：
- 添加 `"cwd": "${workspaceFolder}/receiver-android"`
- 更新 gradlew 路径

示例更新后：
```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Python: Run all tests",
            "type": "shell",
            "command": "D:/nili/dev/conda_envs/qrcast_env/python.exe -m pytest tests/ -v",
            "cwd": "${workspaceFolder}/sender",
            "group": "sender",
            "problemMatcher": []
        },
        {
            "label": "Android: Build debug",
            "type": "shell",
            "command": "./gradlew assembleDebug",
            "cwd": "${workspaceFolder}/receiver-android",
            "group": "receiver-android",
            "problemMatcher": []
        },
        {
            "label": "Android: Build release",
            "type": "shell",
            "command": "./gradlew assembleRelease",
            "cwd": "${workspaceFolder}/receiver-android",
            "group": "receiver-android",
            "problemMatcher": []
        }
    ]
}
```

- [ ] **Step 3: 验证 JSON 语法正确**

```bash
python -c "import json; json.load(open('.vscode/tasks.json')); print('JSON is valid')"
```

Expected: "JSON is valid"

---

## 第五阶段：验证构建

### Task 11: 验证 Sender (Python) 构建

**Files:**
- Test: `D:\my-projects\qrcast\sender\tests\`

**Interfaces:**
- Consumes: Task 10 的 tasks.json 更新完成
- Produces: Sender 验证通过，可正常安装和运行测试

- [ ] **Step 1: 安装 sender 为开发模式**

```bash
cd D:\my-projects\qrcast\sender
D:/nili/dev/conda_envs/qrcast_env/python.exe -m pip install -e .
```

Expected: Successfully installed qrcast-x.x.x

- [ ] **Step 2: 运行所有测试**

```bash
D:/nili/dev/conda_envs/qrcast_env/python.exe -m pytest tests/ -v
```

Expected: 所有测试通过（no failed tests）

- [ ] **Step 3: 验证 qrcast CLI 可用**

```bash
D:/nili/dev/conda_envs/qrcast_env/python.exe -m qrcast --help
```

Expected: 显示 CLI 帮助信息

- [ ] **Step 4: 验证导入正常**

```bash
D:/nili/dev/conda_envs/qrcast_env/python.exe -c "import qrcast; print(qrcast.__version__ if hasattr(qrcast, '__version__') else 'OK')"
```

Expected: 打印版本号或 "OK"

---

### Task 12: 验证 Receiver (Android) 构建

**Files:**
- Test: `D:\my-projects\qrcast\receiver-android\app\build\`

**Interfaces:**
- Consumes: Task 11 的 Sender 验证通过
- Produces: Receiver 验证通过，可正常构建 debug APK

- [ ] **Step 1: 执行 Gradle clean**

```bash
cd D:\my-projects\qrcast\receiver-android
./gradlew clean
```

Expected: BUILD SUCCESSFUL

- [ ] **Step 2: 构建 debug APK**

```bash
./gradlew assembleDebug
```

Expected: BUILD SUCCESSFUL

- [ ] **Step 3: 验证 APK 生成**

```bash
ls -la app/build/outputs/apk/debug/app-debug.apk
```

Expected: 文件存在，大小合理

- [ ] **Step 4: 可选：测试 build.sh 脚本**

```bash
./build.sh debug
```

Expected: 脚本正常执行，生成 APK

---

## 第六阶段：提交并完成

### Task 13: 提交所有迁移更改

**Files:**
- All: 整个工作区

**Interfaces:**
- Consumes: Task 11 和 Task 12 的构建验证通过
- Produces: 一次提交完成所有迁移更改

- [ ] **Step 1: 查看当前更改状态**

```bash
cd D:\my-projects\qrcast
git status
```

Expected: 所有文件 staged 或 modified

- [ ] **Step 2: 暂存所有更改**

```bash
git add -A
```

- [ ] **Step 3: 提交迁移**

```bash
git commit -m "chore: merge qrcast-android into monorepo

- Move Python code to sender/ subdirectory
- Move Android code to receiver-android/ subdirectory
- Merge .gitignore, CLAUDE.md, README.md at root
- Create unified docs/protocol-spec.md
- Update .vscode/tasks.json paths
- Preserve full git history from both repositories"
```

- [ ] **Step 4: 验证提交包含正确的文件**

```bash
git show --stat HEAD
```

Expected: 显示所有移动和修改的文件

---

### Task 14: 推送并清理（可选）

**Files:**
- Check: `D:\my-projects\qrcast-android\`

**Interfaces:**
- Consumes: Task 13 的提交完成
- Produces: 迁移最终完成

- [ ] **Step 1: 推送到 remote**

```bash
git push
```

- [ ] **Step 2: 移除 android remote（可选）**

```bash
git remote remove android
```

- [ ] **Step 3: 验证历史可追溯**

```bash
# 追溯 Python 文件历史
git log --follow sender/qrcast/cli.py --oneline | head -5

# 追溯 Android 文件历史
git log --follow receiver-android/app/src/main/kotlin/com/example/qr_transfer/MainActivity.kt --oneline | head -5
```

Expected: 两边都能看到合并前的提交历史

- [ ] **Step 4: 清理原 qrcast-android 仓库（可选，不建议立即删除）**

```bash
# 建议保留原仓库作为备份，不立即删除
```

---

## 迁移完成检查清单

- [ ] 所有 Python 文件在 `sender/` 目录
- [ ] 所有 Android 文件在 `receiver-android/` 目录
- [ ] 根目录有统一的 `.gitignore`, `CLAUDE.md`, `README.md`
- [ ] `docs/protocol-spec.md` 存在
- [ ] `.vscode/tasks.json` 路径已更新
- [ ] Sender 所有测试通过
- [ ] Receiver debug 构建成功
- [ ] Git 历史可通过 `git log --follow` 追溯两边文件
- [ ] 所有更改已提交并推送

---

## 回滚方案

如果迁移过程中出现严重问题，可以随时回滚：

```bash
# 在合并前的任何阶段，硬重置到 merge 前
git reset --hard HEAD

# 如果已经提交了 merge，可以 revert
git revert -m 1 HEAD
```

原 `qrcast-android` 仓库保持不变，不会丢失任何代码。
