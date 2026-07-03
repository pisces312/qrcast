# QRCast Monorepo 集成设计方案

**日期**: 2026-07-03
**状态**: 设计待审批

## 一、背景与目标

### 背景
QRCast 项目目前分为两个独立仓库：
- `qrcast` (Python): 发送端，生成黑白/彩色二维码
- `qrcast-android` (Kotlin): 接收端，Android 应用扫码接收文件

两项目共享相同的协议规范，但独立管理代码、版本、文档。

### 目标
1. **统一管理**：将两项目合并为单仓库 (monorepo)，方便协同开发
2. **保留历史**：完整保留两边的 git 提交历史
3. **协议统一**：合并协议文档，作为单一权威来源
4. **最小侵入**：各平台可独立构建、测试、发布，互不干扰
5. **路径清晰**：目录结构语义化，便于未来扩展新平台

## 二、最终目录结构

```
qrcast/                           # 根目录
├── sender/                       # Python 发送端（原 qrcast）
│   ├── qrcast/                   # Python package
│   │   ├── bw/                   # 黑白二维码
│   │   ├── v3/                   # RGB 彩色二维码
│   │   ├── cli.py
│   │   └── common.py
│   ├── tests/                    # Python 单元测试
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── env.yml
│   └── ...
├── receiver-android/             # Android 接收端（原 qrcast-android）
│   ├── app/
│   │   └── src/main/kotlin/com/example/qr_transfer/
│   ├── gradle/
│   ├── build.gradle.kts
│   ├── settings.gradle.kts
│   ├── build.sh
│   └── ...
├── docs/                         # 统一文档
│   ├── protocol-spec.md          # 协议规范（两边共享，权威来源）
│   ├── architecture.md           # 总体架构说明
│   ├── sender-getting-started.md # 发送端快速开始
│   ├── receiver-android-guide.md # 接收端使用指南
│   └── CHANGELOG.md              # 统一变更日志，两边变更集中记录
├── scripts/                      # 通用脚本（可选）
│   ├── build-sender.sh
│   ├── build-receiver-android.sh
│   └── release.sh
├── .gitignore                    # 根目录统一 gitignore（合并两边）
├── CLAUDE.md                     # 统一开发环境说明
├── LICENSE                       # MIT
└── README.md                     # 项目总览 README
```

## 三、关键文件更新详情

### 3.1 `.vscode/tasks.json` 路径更新

需要更新所有任务的工作目录和命令路径：

- **Python 相关任务**：`"cwd": "${workspaceFolder}/sender"`
- **Android 相关任务**：`"cwd": "${workspaceFolder}/receiver-android"`
- 可增加分组：`"group": "sender"` / `"group": "receiver-android"` 便于识别

示例：
```json
{
    "label": "Python: Run tests",
    "type": "shell",
    "command": "D:/nili/dev/conda_envs/qrcast_env/python.exe -m pytest tests/ -v",
    "cwd": "${workspaceFolder}/sender",
    "group": "sender"
}
```

### 3.2 根目录 `.gitignore` 合并

合并两边现有的 `.gitignore` 内容：

**Python 相关**：
- `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`
- `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`
- `tmp/`, `.venv/`, `env.yml`

**Android 相关**：
- `.gradle/`, `build/`, `*.apk`, `*.ap_`, `*.idsig`
- `.idea/`, `.kotlin/`, `local.properties`
- `*.iml`, `.DS_Store`, `Thumbs.db`

### 3.3 根目录 `README.md`

内容结构：
1. **项目总览**：QRCast - 跨平台二维码离线文件传输工具
2. **项目组成**：
   - Sender (Python): 发送端，支持 V1/V2/V3 二维码
   - Receiver (Android): Android 接收端
3. **协议兼容性矩阵**
4. **快速链接**：各平台详细文档、构建指南
5. **统一协议说明**（链接到 protocol-spec.md）
6. **License**

### 3.4 根目录 `CLAUDE.md`

合并两边的环境配置：

**Sender (Python)**：
- Conda 环境路径：`D:\nili\dev\conda_envs\qrcast_env\python.exe`
- 构建命令、测试命令
- 依赖管理

**Receiver (Android)**：
- SDK 路径、JDK 路径
- AGP/Gradle/Kotlin 版本
- 签名密钥配置
- 构建命令（debug/release）
- 输出路径

### 3.5 `docs/protocol-spec.md` 统一

从两边文档提取协议定义，合并为单一权威来源：

1. **CHUNKED 模式（分块）**：
   - 格式：`[seq(4B big-endian)][total(4B big-endian)][payload]`
   - 头长度：8 bytes
   - 序号从 0 开始

2. **RAW 模式（原始数据）**：
   - 单张二维码直接编码文件原始字节，无分块头
   - 适用：不超过单张二维码容量的文件

3. **压缩与解压**：
   - 发送端支持 7z 压缩
   - 接收端自动识别 7z/zip 文件头并解压
   - 文件扩展名自动识别逻辑

4. **版本兼容矩阵**：Sender 版本 ↔ Receiver 版本对应关系

## 四、迁移步骤（12 步）

### 前置准备（Step 0）
- [ ] 提交并推送 qrcast 仓库所有未提交更改
- [ ] 提交并推送 qrcast-android 仓库所有未提交更改
- [ ] 确认两边都是 clean 的工作区

### 第一阶段：合并仓库（Step 1-3）

**Step 1: 添加 Android remote 并 fetch**
```bash
cd qrcast
git remote add android ../qrcast-android
git fetch android
```

**Step 2: 合并两个独立历史**
```bash
git merge --allow-unrelated-histories android/main --no-commit
```

**Step 3: 处理合并冲突**
预计冲突文件：
- `README.md` - 保留两边内容，后续合并到根目录
- `LICENSE` - 两边相同，保留一份即可
- `CLAUDE.md` - 后续合并到根目录统一版本
- `.gitignore` - 后续合并到根目录统一版本

### 第二阶段：目录重构（Step 4-6）

**Step 4: 创建 sender 子目录，移动 Python 相关文件**
```bash
mkdir -p sender
mv qrcast/ sender/
mv tests/ sender/
mv pyproject.toml sender/
mv requirements.txt sender/
mv env.yml sender/
mv docs/v*.md sender/docs/  # 版本特定文档移动到 sender 下
# ... 其他 Python 相关文件 (test_*.py, gen_and_display.bat 等)
```

> 注意：移动后需要确保 Python 能正确导入包：
> - `cd sender && pip install -e .` 开发模式安装（推荐）
> - 或设置 `PYTHONPATH=sender/` 环境变量

**Step 5: 创建 receiver-android 子目录，移动 Android 相关文件**
```bash
mkdir -p receiver-android
mv app/ receiver-android/
mv gradle/ receiver-android/
mv build.gradle.kts receiver-android/
mv settings.gradle.kts receiver-android/
mv gradlew* receiver-android/
mv build.sh receiver-android/
mv gradle.properties receiver-android/
mv .gitignore receiver-android/  # 临时保留，后续合并到根目录
# ... 其他 Android 相关文件
```

> APK 文件处理：
> - 根目录下 `QRCast-v*.apk` 和 `*.idsig` 是构建产物，不提交到 git
> - 通过根目录 `.gitignore` 排除，或移动到 `receiver-android/build-outputs/` 后忽略

**Step 6: 统一 .gitignore**
- 合并两边 `.gitignore` 内容到根目录
- 删除 `sender/.gitignore` 和 `receiver-android/.gitignore`
- 增加 `*.apk` 和 `*.idsig` 规则，忽略 APK 构建产物

> 其他特殊目录处理：
> - `.workbuddy/` 保留在根目录，作为整个项目的记忆
> - `.vscode/` 保留在根目录，tasks.json 路径已更新

### 第三阶段：文档合并（Step 7-9）

**Step 7: 合并根目录 README.md**
- 编写项目总览
- 介绍 sender 和 receiver-android
- 链接到各平台详细文档

**Step 8: 合并根目录 CLAUDE.md**
- 整合两边环境配置
- 统一构建命令说明

**Step 9: 统一协议文档**
- 创建 `docs/protocol-spec.md`
- 从两边现有文档提取并整合协议定义
- 两边代码中相关注释可以链接到此文档

### 第四阶段：配置更新（Step 10-11）

**Step 10: 更新 .vscode/tasks.json 路径**
- 更新所有任务的 `cwd` 到正确子目录
- 验证每个任务仍然可正常运行

**Step 11: 验证各平台内部路径引用**
- Python: 验证 `pyproject.toml` 中包路径配置
- Android: 验证 Gradle 配置中的路径
- 如有硬编码路径，更新为相对路径

### 第五阶段：验证与提交（Step 12）

**Step 12: 验证构建并提交**
- 验证 Sender: `cd sender && python -m pytest tests/ -v`
- 验证 Receiver: `cd receiver-android && ./gradlew assembleDebug`
- 一次提交完成所有迁移更改

## 五、版本管理策略

采用 **独立版本 + 统一变更日志** 策略：

1. **版本号独立**
   - Sender (Python): 继续使用 `sender/pyproject.toml` 中的 `version` 字段
   - Receiver (Android): 继续使用 `receiver-android/app/build.gradle.kts` 中的 `versionName` / `versionCode`
   - 两边可以独立迭代小版本

2. **统一变更日志**
   - `docs/CHANGELOG.md` 记录两边的所有变更
   - 格式示例：
     ```
     ## [sender v1.1.0] - 2026-07-xx
     - 新增 xxx 功能
     - 修复 xxx bug

     ## [receiver-android v1.0.5] - 2026-07-xx
     - 兼容 sender v1.1.0 新协议
     ```

3. **协议版本**
   - 协议本身有版本号（如 CHUNKED v2, RAW v1）
   - 协议变更同步更新两边代码和 `protocol-spec.md`

## 六、验证清单

迁移完成后需要验证：

### Sender (Python)
- [ ] `pip install -e .` 正常工作
- [ ] 所有单元测试通过
- [ ] `qrcast` CLI 命令正常运行
- [ ] `gen_and_display.bat` 脚本更新路径后正常工作

### Receiver (Android)
- [ ] `./gradlew assembleDebug` 正常构建
- [ ] `./gradlew assembleRelease` 正常构建（配置签名密钥）
- [ ] `build.sh` 脚本正常工作
- [ ] 生成的 APK 可以安装和扫码

### 集成验证
- [ ] `docs/protocol-spec.md` 与两边实现一致
- [ ] `.vscode/tasks.json` 所有任务正常运行
- [ ] 根目录 `.gitignore` 正确忽略两边构建产物

## 七、风险与回滚

### 主要风险
1. **路径变更导致构建失败** - 通过验证清单逐一确认
2. **Git 历史混乱** - 使用 `git log --follow` 追溯文件历史
3. **合并冲突处理错误** - 合并前先在本地分支测试

### 回滚方案
如果出现严重问题，可以立即回滚：
```bash
git reset --hard HEAD  # 回到合并前状态
git remote remove android
```

原 qrcast-android 仓库仍然完整保留，不会丢失任何代码。
