# Reviewer 校验器

> 决策：2026-09-26。自建 Claude Science 中唯一无法用现成组件替代的一块。
> 溯源设计见 `docs/provenance.md`；本文含**设计 + 实现计划**。

## 0. 为什么自建，以及它和 Claude Science 的 reviewer 有什么不同

Anthropic 文档把它的 reviewer 描述为"比对 Claude 的回答、计划、产物与执行记录是否一致"，
并明确说明**它不重跑分析、不判断方法是否得当**。我们的场景反过来了：

| 维度 | Claude Science reviewer | binder-forge reviewer（本设计） |
|---|---|---|
| 判据 | 模型自己的叙述 vs 执行记录 | **独立重算**：从原始输出重新解析指标、从配置重新跑阈值 |
| 重跑能力 | 明确不做 | 指标重算（R5）、阈值重放（R6）——这是可信度的来源 |
| 数据出境 | prompt/response 发往 Anthropic | 全本地，零出境 |
| CI 门禁 | 无退出码契约 | `--fail-on block` 返回非零退出码，`forge export` 前置 |
| 误报处理 | 静默即视为正确（已知风险） | 每条规则必须有**合成错误探针**测试证明它能被触发 |

一句话：**它查"说的和做的一不一致"，我们查"记的和磁盘上的一不一致"**。后者才是漏斗数据可信度的瓶颈。

## 1. 定位与边界

- **v1 是确定性的、离线的、无 LLM 的**。判据全部是可重算的事实，不引入模型判断的不确定性。
- **不追求语义校对**（方法文档写得好不好、引用是否真实）——那是 P4 的可选层，默认关闭，且不进 CI 门禁。
- **降级优先**：产物缺失/registry 旧数据时报 WARN 而非崩溃，因为当前漏斗各阶段仍是骨架实现。

## 2. 检查项

严重度：`BLOCK`（阻止 `export`）/ `WARN`（需人工确认）/ `INFO`。

| ID | 检查 | 判据 | 严重度 |
|---|---|---|---|
| R1 | 血缘完整 | `config_hash` 能在 `configs/` 中重算命中；`target_id` 一致；`parent_id` 若非空必须存在于 designs 表（孤儿检测） | BLOCK |
| R2 | 序列自洽 | `length == len(sequence)`；字母表为天然 aa；长度落在 target `modality.binder_length` 区间内 | BLOCK |
| R3 | 结构存在 | `structure_path` 存在、非空、扩展名合法（pdb/cif） | BLOCK |
| R4 | 序列-结构一致 | 从 PDB 提取 binder 链残基（三字母→单字母）与 `sequence` 比对 | BLOCK |
| R5 | 指标重算 | 从 `predictor_outputs` 原始文件重新解析 pLDDT / i_pTM / i_PAE，与 `metrics` 比对，容差 1e-3；**有输出但不一致 → BLOCK，缺输出 → WARN**（早期阶段 INFO） | BLOCK / WARN |
| R6 | 阈值重放 | 用 `configs/filters/*.yaml` 重算 `passed_screen` / `passed_select`，与库内布尔值比对 | BLOCK |
| R7 | 交叉验证口径 | `predictors_agreeing` 与实测达标数一致；`< min_agreeing` 却 `passed_screen=True` | BLOCK |
| R8 | 许可合规 | `pipeline` 与 `toolchain_license` 匹配（bindcraft → 必须 `pyrosetta-dependent`）；Rosetta 指标键出现但 `rosetta_profile` 未启用 | BLOCK |
| R9 | 溯源对账 | run 级：`verify_artifacts()` 重算全部已登记产物；记录级：`artifact_hashes` 逐项重算。覆盖/篡改/丢失均检出 | BLOCK |
| R10 | 代码可 pin | `code_rev` 非空且 `code_dirty=false` | WARN（export 时升级 BLOCK） |
| R11 | 聚类/配额自洽 | `selected` 条数 ≤ quota；同 `cluster_id` 内不得超额；`selected=True` 必须有 `cluster_id` | BLOCK |
| R12 | 提交包一致 | export 的 FASTA 序列集合 == `selected` 集合；入选设计结构齐全；方法文档的许可标注与实际一致。**仅在 `--stage export` 或给了 `--submission` 时执行** | BLOCK |
| R13 | 重复提交 | `selected` 集合内无重复序列（`submit_early` 先到先得场景下，重复即浪费配额） | WARN |

R8 是 `tests/test_no_rosetta.py` 的**数据层补充**：那个测试守住源码与配置，R8 守住跑出来的数据。

## 3. CLI 与输出

```bash
forge review --target configs/targets/NK2R_peptide.yaml            # 全量体检
forge review --target ... --stage export --fail-on block           # export 前置门禁
```

产物落在 `runs/<target>/<run_id>/review/`：

- `findings.json` — 机器可读，供 CI 与后续复盘
- `review_report.md` — 人读：按严重度分组，每条给出 design_id、判据、期望值/实际值、建议动作
- 退出码：`0` 无 BLOCK；`1` 存在 BLOCK（配合 `--fail-on block`）

## 4. 实现计划

> 前提：漏斗六阶段目前仍是骨架（`raise NotImplementedError`），
> 因此 reviewer 必须**先于**生成管线上线——它先当"体检工具"，后当"门禁"。

### P0 溯源骨架（约半天）
- 新建 `src/binder_forge/provenance/{__init__.py,run.py}`：`RunContext`（run_id 生成、manifest 读写、
  `register_artifact()` 算 sha256 并 append 到 `provenance.jsonl`、封存目录）
- `db/store.py` 增加 schema 迁移（`ADD COLUMN IF NOT EXISTS`，兼容旧库）
- `design/base.py` 的 `DesignRecord` 增加 `run_id / stage / code_rev / artifact_hashes / predictor_outputs / manifest_uri`
- 验收：`tests/test_provenance.py` — 建 run、登记产物、封存后写入应失败；哈希对账可检出人为改文件

### P1 reviewer 内核（约 1 天）
- 新建 `src/binder_forge/review/{__init__.py,checks.py,report.py}`：规则注册表（每个 check 是一个
  `(id, severity, fn) -> Finding`）、md/json 渲染
- 实现 R1–R4、R7、R11、R13（不依赖外部工具输出，纯 registry + 文件系统即可跑）
- `cli.py` 增加 `review` 命令
- 验收：`tests/test_review.py` 用 fixtures 覆盖每条规则的命中与不命中

### P2 重算类检查（约 1 天）
- R5：Boltz-2 / AF2 输出解析器（`confidence.json` / `pae.npz` → pLDDT、i_pTM、i_PAE）
- R6：复用 `filters/apply.py` 的阈值逻辑做重放，比对库内布尔值
- R9：哈希对账
- 验收：同一批产物跑两次指标解析结果稳定；人为改 metrics 后 R5 必报 BLOCK

### P3 export 门禁（约半天）
- R8（许可合规）、R10（代码 pin）、R12（提交包一致）
- `forge export` 内部前置调用 `review --stage export --fail-on block`，BLOCK 即中止
- `tests/test_no_rosetta.py` 补充：fixture 数据里塞入 Rosetta 指标键时 R8 应拦截
- 验收：`pytest tests/` 全绿；含已知错误的 fixture 上退出码非零且报告列出全部触发项

### P4 可选：LLM 语义层（后续，默认关闭）
- 方法文档与代码是否对得上、引用 DOI 是否解析到正确文章
- 不进 CI 门禁；如需调用外部模型须显式开关，并遵守公司数据出境规范

## 5. 测试策略（关键）

每条规则**必须有合成错误探针**：在 fixture 里人为制造该类错误，断言规则被触发。
这是 Claude Science 的 reviewer 明确做不到的事（它无法证明自己能抓到什么），
也是我们自建的最大理由——**可证明的检出能力 > 声称的检查能力**。

`tests/fixtures/` 提供一份"已知含 13 类错误"的样例库，`forge review` 跑它应全数命中，
这条断言本身就是回归测试。

## 6. 不做的事

- 不做"方法是否得当"的判断（该由人负责，R 层的职责是事实一致性）
- 不做图表/文稿排版校对
- 不替代湿实验验证——所有指标仍是计算预测，reviewer 只保证"记录的数字确实是跑出来的那个数字"

## 7. 落地状态（P1–P4，2026-09-26 全部完成）

代码：`src/binder_forge/review/`（`finding` / `context` / `predictors` / `checks` /
`report` / `runner` / `semantic`）+ `cli.py::review` + `submit/export.py` 门禁。
测试：`tests/test_review.py`（10 项）+ `tests/fixtures.py`（合成错误探针）。

实现中相对原计划的三处调整，都是有意为之：

1. **R5 分档**：缺 predictor 原始输出报 WARN（早期阶段 INFO），只有"有输出却对不上"才是 BLOCK。
   一刀切 BLOCK 会让尚未跑复折的生成池刷满 BLOCK，门禁就没人用了。
2. **`--stage` 是复核范围，不是 registry 过滤**：复核始终取该靶点全部记录。
   按阶段过滤会把没写 `stage` 的旧行整批漏掉 —— 那正是最该被复核的数据。
3. **export 门禁是"先建包、后复核"**：因为 R12 校验的就是这个包，不建出来没得查。
   判定 BLOCK 时包保留在原处（便于排查），打 `.UNVERIFIED` 标记；通过则打 `.VERIFIED`。
   `--allow-blocked` 可强行出包，默认关闭。

另外两个实现细节值得记一笔：

- `registry.query_target` 走 pandas，SQL NULL 会变成 `NaN`，直接喂给 `Path()` 会炸；
  已在 `build_context` 统一还原成 `None`。
- 规则执行抛异常不会让复核静默通过 —— 会被捕获并转成一条 INFO（"这条规则没跑完"），
  沉默不等于通过在这套代码里是硬约束。

### P4 语义层的边界

`review/semantic.py` 只提供接口 + `DisabledSemanticReviewer`（默认）。启用需显式
`--semantic --semantic-endpoint <url>`，走 stdlib urllib，不引入任何模型 SDK；
端点返回的 finding **一律降级为 INFO**，永远不参与 `--fail-on` 判定。
默认路径不发任何网络请求，这一点由测试用 monkeypatch 钉死。
