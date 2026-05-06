# AGENTS.md

给后续协作者（人 / Claude / Codex / Cursor）的项目须知。一页够用。

## 项目定位

`nsz-to-nsp` 不是一个独立的解压器实现。它是：

```
上游 nicoboss/nsz（原样镜像在 nsz/ 下）  +  本仓库的薄 wrapper（batch_convert.* / README）
```

**用户视角**：把 NSZ 文件丢进 `input/`，跑 `batch_convert.py`，从 `output/` 取 NSP 给 Ryujinx。

**实现视角**：解压算法 100% 是上游的，本仓库只在外层加批量调度、日志保留、参数缺省、故障诊断这些"工程化"补丁。

## 仓库结构边界（最重要）

| 目录 / 文件 | 性质 | 修改原则 |
|------|------|----------|
| `nsz/` | **上游镜像**（nicoboss/nsz） | 默认禁止改。命中 bug 时优先去上游报，本地仅做"必须 cherry-pick"的修复，且在改动处加注释说明"为什么不能等上游"。 |
| `nsz/NszDecompressor.py`、`nsz/Fs/Pfs0.py` | 上游代码 | 已有两处本地补丁（FakeSection 漏算 / Pfs0Stream.getFirstFileOffset 的 dict 访问）—— 都有内联中文注释，删之前先看 `tests/`。 |
| `batch_convert.py` / `.sh` / `.cmd` | 本地 wrapper | 这才是放业务/可用性逻辑的地方。改默认参数、加日志、加诊断都进这里。 |
| `tests/` | 本地补丁的回归用例 | 改 `nsz/` 任何字节前必须先在这里加用例锁住行为。 |
| `input/` `output/` | 用户运行时目录 | 内容进 `.gitignore`，**永远不要 commit Switch ROM**。 |
| `azure-pipelines.yml` | CI 配置 | 上游原版的 4 个 ROM 测试步骤依赖 self-hosted runner，普通 fork 跑不了。本仓库新增的 `pytest tests/` 步骤是真正在跑的部分。 |

## 改动原则（按优先级）

1. **优先改 wrapper，不改 `nsz/`**。能在 `batch_convert.py` 里加默认参数 / 日志扫描 / 用户提示解决的，绝不下沉到 `nsz/` 里。
2. **改 `nsz/` 必须先加 pytest**。新增用例放在 `tests/`，先让它能复现 bug 再写修复。修复后用 `git stash` / 临时回滚一次确认测试确实在卡你。
3. **不要新增对网络 / API key / LLM 的依赖**。本工具是纯本地命令行，加任何外部依赖都会让用户配置成本翻倍。
4. **诊断逻辑用关键字扫描，不要用 LLM**。`batch_convert.py` 已有 `SUSPICIOUS_PATTERNS` 列表，新增一类失败模式时往这里加正则，比接 API 可靠且零成本。

## 跑测试

```bash
# 第一次：装开发依赖
pip install -r requirements-dev.txt

# 跑测试（< 1 秒）
pytest tests/

# 单文件
pytest tests/test_ncz_size_calc.py -v
```

> 测试时不需要 prod.keys，也不需要任何真实 NSZ 样本。所有用例都用合成的 mini PFS0/NCZ 二进制，跑在内存里。

## 不会做的事（明确范围）

下面这些被有意排除在项目范围外：

- **真实 ROM 样本的端到端测试**：Switch ROM 进仓库违反合规，做不了真 E2E。pytest 已足够覆盖本地补丁的回归。
- **AI 故障诊断（LLM 接入）**：当前关键字扫描已能命中 `[CORRUPTED]` / `missing from` / `[TICKETLESS]` 这类关键场景，价值/成本不划算。如确需扩展，先扩 `SUSPICIOUS_PATTERNS`。
- **GUI 二次开发**：上游有 Kivy GUI（`nsz/gui/`），本地 wrapper 不动它。

## 上游同步流程

跟上游 `nicoboss/nsz` 同步时：

1. `git remote add upstream https://github.com/nicoboss/nsz.git && git fetch upstream`
2. **diff 上游 master 与本地 nsz/**：`git diff upstream/master -- nsz/`，把本地补丁一条条标出来。
3. cherry-pick 上游修复时**保留本地补丁**——尤其是 `nsz/NszDecompressor.py` 里的 `for i in range(len(sections))` 和 `nsz/Fs/Pfs0.py:Pfs0Stream.getFirstFileOffset` 那两处。
4. 同步完跑 `pytest tests/`，全绿才算完成。

## 联系上游 bug

如果发现 `nsz/` 里的新 bug 不是本地补丁导致的，先去上游建 issue：<https://github.com/nicoboss/nsz/issues>。本仓库 issue 只跟踪 wrapper 层（batch_convert / README / 默认参数 / CI）。
