# 产物溯源补全（Provenance）

> 决策：2026-09-26。评估 Anthropic Claude Science（2026-06-30 beta）后确认其不可采购
> （支持地区清单不含中国大陆，且无自托管形态），但其最有价值的两块能力——**产物溯源**
> 与 **reviewer 复核**——值得自建。本文是溯源部分的设计；校验部分见 `docs/reviewer.md`。

## 1. 现状与缺口

`DesignRecord` 已有血缘骨架（`pipeline` / `seed` / `config_hash` / `parent_id`），
DuckDB registry 存全量指标，这比"只有一堆输出文件"已经强很多。但离"可复现"还差四件事：

| 缺口 | 后果 |
|---|---|
| 无 `run_id` / 运行边界 | 一次 `generate` 产出的 5000 条无法与另一次区分，回滚只能全量重跑 |
| 产物只有路径、无内容哈希 | 文件被覆盖/手工改过无法察觉，赛后复盘的指标对不上原始输出 |
| 无环境锁与代码 pin | 三个月后无法回答"这条序列是哪个版本的什么环境跑出来的" |
| 无不可变约定 | 任何阶段都能改写上一阶段的产物，溯源形同虚设 |

**结论**：溯源不是加字段，是加**运行边界 + 内容哈希 + 只追加事件流 + 不可变目录**这四条规定。

## 2. run 目录布局

```
runs/<target_id>/<run_id>/
  manifest.json          # 本次运行的不可变声明(stage 结束时封存)
  provenance.jsonl       # append-only 事件流: 每条设计/每个产物的登记记录
  inputs/                # 输入快照: 靶点 YAML、受体 PDB、hotspot 表
  artifacts/             # 产物: 结构 PDB/CIF、指标 JSON、PAE npz
  logs/                  # stdout/stderr、sbatch 脚本、Slurm job id
  env.lock.txt           # conda env export / pip freeze
  review/                # forge review 产出的报告(reviewer.md)
```

`run_id = <stage>-<UTC时间戳>-<git短sha>`，例：`gen-20261002T0815Z-a1b2c3d`。

## 3. manifest.json

```json
{
  "run_id": "gen-20261002T0815Z-a1b2c3d",
  "stage": "generate",
  "target_id": "NK2R-PDC",
  "config_path": "configs/targets/NK2R_peptide.yaml",
  "config_hash": "9f3c1a2b7d",
  "code_rev": "a1b2c3d",
  "code_dirty": false,
  "started_at": "2026-10-02T08:15:00Z",
  "ended_at": "2026-10-02T11:42:00Z",
  "host": "hpc-login-3",
  "scheduler_job_id": "12345",
  "command": "forge generate --target configs/targets/NK2R_peptide.yaml --budget 5000",
  "env_lock": "env.lock.txt",
  "tool_versions": { "boltzgen": "0.4.1", "torch": "2.14.0+cu128" },
  "seed": 20261002,
  "inputs":    [{ "path": "inputs/NK2R.pdb",       "sha256": "..." }],
  "artifacts": [{ "path": "artifacts/xxx.pdb",     "sha256": "...", "design_id": "..." }]
}
```

`code_dirty: true`（本地有未提交改动）时 reviewer 强制 WARN——这是最常见的"复现不了"根因。

## 4. provenance.jsonl（只追加）

每行一个事件，写满即封，绝不修改历史行：

```json
{"ts":"...","run_id":"...","stage":"validate","design_id":"ab12cd34ef56","action":"artifact_written","artifact":"artifacts/ab12cd34ef56.pdb","sha256":"...","metrics":{"plddt":88.3,"iptm":0.84}}
```

reviewer 的核心动作就是**拿这行的 sha256 去和磁盘当前文件重算哈希对账**——这是收益最高、
成本最低的一条检查（一条命令就能发现"文件被后续阶段覆盖了"）。

## 5. Registry schema 扩展

新增列（对旧库做 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`，旧行 `run_id` 为 NULL，
reviewer 对其报 WARN 而非 BLOCK，保证历史数据不炸）：

```sql
run_id             TEXT,
stage              TEXT,
code_rev           TEXT,
inputs_hash        TEXT,
artifact_hashes    JSON,      -- {relpath: sha256}
command            TEXT,
predictor_outputs  JSON,      -- {boltz2: "artifacts/.../confidence.json", af2: "..."}
manifest_uri       TEXT
```

保留既有 `config_hash` 不动；`predictor_outputs` 是 reviewer 能否**重算指标**的前提（见 reviewer R5）。

## 6. 五条不变式

1. **谁产出谁登记**：适配器 `collect()` 内必须调 `ctx.register_artifact()`，未登记产物视为无效。
2. **只追加不改**：`provenance.jsonl` 仅 append；`manifest.json` 在 stage 结束时写入一次，此后只读。
3. **哈希即证据**：所有输入与产物在落盘时算 sha256，事后只比对不信任。
4. **目录封存**：stage 结束写入 `ended_at` 后，该 run 目录转为只读（HPC 侧 `chmod a-w`）。
5. **代码可 pin**：`code_rev` 缺省或 `code_dirty=true` 的运行，不得进入 `export`（WARN 升级为 BLOCK 需人工确认）。

## 7. 与 HPC 的配合

`docs/hpc_setup.md` 的 Slurm 模板输出目录改为 `$SCRATCH/binder/runs/<target>/<run_id>`，
sbatch 脚本在 prologue 写 `manifest.started_at`、epilogue 写 `ended_at`，
job id 写回 manifest——这样"哪个作业跑了哪批设计"无需再靠日志人肉对。
