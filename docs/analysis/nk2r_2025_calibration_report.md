# NK2R PDC 2025 榜单校准报告

> 数据：2025 届公开榜单（1590 条提交 → AF3 预筛 142 条实测 + 7 条难合成弃测）
> 分析：`notebooks/nk2r_2025_calibration.ipynb`（可复跑）｜ 日期：2026-09-25

## TL;DR — 五条可直接执行的结论

1. **守门员函数已还原**：官方预筛 ≈ 复合物 `iptm_AB`（AUC 0.974，选中中位 0.91 vs 落选 0.30）+ 多肽链 pLDDT（AUC 0.955）+ **NKA 置换检验**（`iptm_AD(NK2R-NKA)` 选中 0.25 vs 落选 0.85，AUC 0.099——肽必须把天然配体挤出 pocket 才被合成）。
2. **实测集内最优区分指标是 iptm/ptm/ranking_score**（hit100 AUC 0.82–0.86）；`iptm_AB≥0.8 且 ranking_score≥0.8` 组合将命中率从 6.3% 提到 **15.2%（2.4× 富集）**，且 9 个强 hit 保住 7 个。
3. **序列层面的决定性特征**：NKA C端药效团样 motif 出现在 **52% 活性分子 vs 0% 无活性分子**；二硫键环肽 26% vs 0.8%；活性分子**中位长度仅 10 aa**（>15 aa 的只占 4%，而无活性分子 34% >15 aa）。
4. **可合成性教训**：7 条弃测序列全是 34–39 aa 长肽或含奇数 Cys——直接验证我们 `even_count_only` Cys 政策与长度上限的必要性。
5. **方法战绩颠覆直觉**：单次生成管线全体扑街（AF2/3: 5%、BindCraft: 8%、RFdiffusion: 8%、MPNN: 6%），而**迭代优化循环碾压**（ensemble/diffusion: 65%、进化算法: 42%）。→ binder-forge 必须加 `optimize` 阶段（见下）。

## 1. 预筛守门员（1590 → 142 的选择函数）

| 指标 | AUC(被选中) | 选中中位 | 落选中国位 |
|---|---|---|---|
| **iptm_AB (NK2R-肽)** | **0.974** | 0.91 | 0.30 |
| **mean pLDDT (肽链)** | **0.955** | 84.1 | 40.4 |
| iptm / ranking_score / ptm | ~0.5 | — | — |
| **iptm_AD (NK2R-NKA)** | **0.099** | **0.25** | **0.85** |

解读：预筛 = **高 iptm_AB + 高肽 pLDDT + 低 NK2R-NKA iptm（置换成功）**。
对 funnel 的含义：generate 阶段就应显式建模三元竞争（肽 + NKA + NK2R）或以口袋占据为约束；
validate 阶段必须用与官方一致的 AF3 口径复算这三项。

## 2. 实测集内的活性区分（注意：预筛压缩了取值范围，AUC 为保守下界）

| 指标 | AUC_active (23v119) | AUC_hit100 (9v133) |
|---|---|---|
| iptm | 0.783 | 0.834 |
| ptm | 0.778 | **0.857** |
| ranking_score | 0.751 | 0.824 |
| mean pLDDT (肽链) | 0.634 | 0.705 |
| iptm_AB | 0.595 | 0.647（范围被压缩） |

**组合阈值**：`iptm_AB ≥ 0.8 且 ranking_score ≥ 0.8` → 46/142 通过，命中率 15.2%（2.4×），召回 7/9。
已写入 `configs/filters/peptide.yaml` 的 select 层。

## 3. 激活谱与选择性隐患

- 9 个 hit100 分子的 NK2R 激活率 90.8%–153.3%（存在**超激动剂**，>NKA 自身）。
- NC（对照）激活率多 <27%，但 hit 中有一条达 63.3%——**强活性不等于干净的选择性**，
  Round 2 双倍权重下，负设计（NK1R/NK3R counter-screen）必须前置到第一轮设计里。

## 4. 序列设计规则（数据版）

| 规则 | 证据 |
|---|---|
| 保留/移植 NKA C端药效团几何（F/Y…L/M）| 52% 活性 vs 0% 无活性 |
| 优先二硫键环肽（C≥2，偶数）| 26% 活性 vs 0.8%；奇数 Cys 全部弃测 |
| **长度压到 8–15 aa** | 活性中位 10 aa；>17 aa 几乎无活性且难合成 |
| 避免 30+ aa 长疏水/复杂折叠肽 | 7 条难合成弃测全部为 34–39 aa |

## 5. 方法战绩与对 binder-forge 的架构影响

| 方法（实测集） | 实测数 | 有活性 | 活性率 |
|---|---|---|---|
| Custom ensemble/diffusion（迭代） | 17 | 11 | **65%** |
| Custom evolutionary（迭代） | 12 | 5 | **42%** |
| AlphaFold2/3 | 38 | 2 | 5% |
| BindCraft | 25 | 2 | 8% |
| RFdiffusion | 13 | 1 | 8% |
| ProteinMPNN/LigandMPNN | 17 | 1 | 6% |

**结论：generation 只负责起好头，winner 是 predictor-guided 的迭代优化循环。**
架构响应：funnel 在 generate 之后插入 `optimize` 阶段（`src/binder_forge/design/optimize.py`）——
以 validate 分数（iptm/ptm/ranking_score + SRS 选择性）为导向做突变-重评估进化循环，
每轮保留 elite、多样性维护，收敛后进入正式 filter/rank。
NK2R 靶点配置的 pipeline_mix 已相应加入 `optimize_loop` 份额。

> 对长江杯的迁移：同样的循环逻辑适用（将 AF3 换成双预测器一致口径），
> 但需警惕对单一预测器过拟合——长江杯没有官方守门员，循环目标函数必须内建交叉验证。
