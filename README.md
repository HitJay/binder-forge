# binder-forge

从头结合蛋白（de novo binder）设计的端到端 funnel 编排仓库。
并行调度 **BindCraft / RFantibody / BoltzGen** 三条开源管线，
经统一漏斗（复折验证 → 物理/可开发性过滤 → 多样性聚类 → 配额排名）产出可提交/可合成的高质量序列。

> **定位**：长期复用的通用设计 funnel，任何"给定靶点、产出 binder 序列"的任务都可接入。
> 首个应用 campaign：[「长江杯」2026 全球AI蛋白质设计挑战赛](https://www.jfdaily.com/sgh/detail?id=4063302)（参赛项目，非官方仓库），
> 调研与完整规划见上级目录《长江杯AI蛋白质设计挑战赛_调研与规划.md》。

## 架构

```
                        ┌──────────────┐
                        │ configs/     │  靶点即配置(YAML): 结构/表位/hotspot/模态/配额
                        └──────┬───────┘
                               ▼
   ┌────────────────────────────────────────────────────┐
   │ 1. prepare  (targets/prepare.py)                   │  结构清洗、截断、表位标注
   └──────────────────────┬─────────────────────────────┘
                          ▼
   ┌────────────────────────────────────────────────────┐
   │ 2. generate (design/ adapters, 并行)                │
   │    ├─ BoltzGen     (nanobody-anything / protein)   │
   │    ├─ BindCraft    (AF2-backprop hallucination)    │
   │    └─ RFantibody   (VHH CDR 设计, 需 hotspot)       │
   └──────────────────────┬─────────────────────────────┘
                          ▼  候选池 10^3–10^4 / 靶点 → Design Registry (DuckDB)
   ┌────────────────────────────────────────────────────┐
   │ 3. validate (validate/refold.py)                   │  ≥2 家预测器复折一致才放行
   │    AF2-Multimer / Boltz-2 / Chai-1 / ESMFold       │
   └──────────────────────┬─────────────────────────────┘
                          ▼
   ┌────────────────────────────────────────────────────┐
   │ 4. filter (filters/apply.py)                       │  阈值 + liability 硬淘汰
   └──────────────────────┬─────────────────────────────┘
                          ▼
   ┌────────────────────────────────────────────────────┐
   │ 5. rank (rank/leaderboard.py)                      │  加权打分 → TM-score 聚类 → 簇配额
   └──────────────────────┬─────────────────────────────┘
                          ▼
   ┌────────────────────────────────────────────────────┐
   │ 6. export (submit/export.py)                       │  提交 FASTA + 方法文档
   └────────────────────────────────────────────────────┘
```

## 快速上手

```bash
# 0. 基础环境(各 pipeline 有独立 env, 见 scripts/setup_env.sh)
conda env create -f environment.yml && conda activate binder-forge
pip install -e .        # 提供 forge 命令

# 1. 端到端彩排: 用 EGFR(历届 Adaptyv 竞赛靶点, 有公开湿实验答案) 自检 funnel
bash scripts/rehearsal_egfr.sh

# 2. 正式流程(任意新靶点: 写一份 configs/targets/<id>.yaml 即可)
forge prepare   --target configs/targets/T01.yaml
forge generate  --target configs/targets/T01.yaml --pipelines boltzgen,bindcraft,rfantibody --budget 2000
forge validate  --target configs/targets/T01.yaml --predictors boltz2,af2
forge filter    --target configs/targets/T01.yaml --profile configs/filters/vhh.yaml
forge rank      --target configs/targets/T01.yaml --quota 100 --cluster-tm 0.6
forge export    --target configs/targets/T01.yaml --out runs/T01/submission
```

## 设计原则

- **Adapter 模式**：不重写外部工具，统一契约 = 序列 + 结构 + 指标 JSON；新管线（如未来的 BindCraft2/Chai 系开源）只需新增一个适配器。
- **Config-driven**：靶点即配置，换靶点/换任务不改代码——这是复用性的基础。
- **Design Registry**：每条设计 UUID + 血缘（pipeline/seed/config hash）+ 全指标，落 DuckDB，赛后复盘与 Benchmark 复用的核心资产。
- **交叉验证防对抗序列**：单预测器（尤其 AF2-only）筛选会选出对抗性序列，强制双家一致。
- **表达先于结合**：可开发性（无游离 Cys、无 NG/NS/N-X-S/T、低聚集）是硬门槛。

## 当前状态（2026-09-26）

| 职能 | 位置 | 状态 |
|---|---|---|
| 编排 / 分析 / 过滤配置 / 校准分析 | **本机 Windows** | ✅ 已完成 |
| 生成管线（BoltzGen / BindCraft / RFantibody） | **HPC / 云** | ⏳ 建库中（`docs/hpc_setup.md`）|
| 复折验证（AF3 / Boltz-2） | **HPC / 云** | ⏳ |

> 本机结论：Windows + RTX 5060(8GB) 不适合跑 GPU 管线——CUDA torch 轮子下载受阻、
> PyRosetta 无 Windows 版、boltz 要求 py<3.13。本机保留编排与数据分析职能，
> 重活走 HPC（见 `docs/hpc_setup.md`），踩坑记录见 `docs/env_setup.md`。

## 里程碑（长江杯 campaign）

- M0 (2026-10-31 前): EGFR 彩排跑通，报名完成
- M1 (靶点公布 +2 周): 每靶点候选池 ≥1000 入库
- M2 (+5 周): 提交清单冻结
- M3: 湿实验结果回流复盘，更新阈值
