# Campaign: 2026 NK2R 多肽设计挑战赛 (PDC, 清华 FRCBS)

> binder-forge 的第二个 campaign（多肽模态首战），兼作长江杯实战彩排。
> 信息核实日期：2026-09-25。2026 届已于 09-24 由官方公众号"北京生物结构前沿研究中心"宣布全球征集，
> 详细时间表页面上线中（参考 2025 届规则与节奏，下文标注）。

## 1. 赛事速览

| 项目 | 内容 |
|---|---|
| 主办 | 清华大学北京生物结构前沿研究中心 (FRCBS)，学术顾问：施一公/王宏伟/王新泉/李海涛；组委会：田博学、马剑竹等 |
| 靶点 | **NK2R (TACR2, UniProt P21452)**，Class A GPCR；代谢疾病（肥胖/糖尿病）|
| 任务 | 设计**高选择性、高亲和力 NK2R 多肽激动剂**（规避 NK1R 副作用）|
| 模态 | **多肽 ≤40 天然氨基酸**；与天然 NKA (HKTDSFVGLM) 相似度 <30% (mmseqs2) |
| 轮次 | Round 1 拼活性 EC50[NK2R] → Round 2 拼选择性 EC50[NK2R]/EC50[NK1R] |
| 评分 | EC50<100 nM 时：Z[activity] + 2.0×Z[selectivity]（选择性权重双倍！）|
| 湿实验 | 组委会免费合成+测试；**AF3 预筛 ipTM/ipAE Top100 才进入合成** |
| 名额 | 相同序列**先到先得**；不得与 Round 1 已提交序列重复 |
| 奖金 | 金 ¥35,000 ×1 / 银 ¥14,000 ×2 / 铜 ¥7,000 ×3（2025 届标准）|
| ⚠️ IP 条款 | **所有提交序列与数据公开共享、他人可免费使用** |
| 社群 | 微信 FRCBS-THU（中文）/ Discord（英文）|
| 官网 | https://www.fbs.frcbs.tsinghua.edu.cn/competition/2025Peptide （2026 页待上线）|

参考 2025 届节奏：一轮提交 6 周（08.18–09.30）→ 合成测试 6 周 → 二轮提交 4 周 → 测试 → 次年 3 月颁奖。
**2026 届推断：一轮提交窗口约 10 月初–11 月中（待官方确认）。**

## 2. 为什么这是长江杯的最佳彩排

1. **同一靶点家族**：NK2R 正是长江杯社区热议靶点（药化猩球 9/25 攻略文），GPCR 结构准备、
   表位图谱、NK1R/NK3R 负设计设施在长江杯 VHH 赛道可**直接复用**。
2. **模态互补练兵**：多肽模态倒逼我们打通 BoltzGen `peptide-anything`、BindCraft 肽设计、
   RFdiffusion 肽扩散——adapter 层第一次实战，恰好验证 binder-forge 的复用性设计。
3. **规则透明、数据全公开**：2025 届 leaderboard ~1590 条实测序列，含每条 AF 指标
   (iptm/pae/plddt/clash/disordered) + 实验 EC50 + 激活率，可下载：
   `data/external/2025_pep_design_comp_all_entries_with_synthesize_highlight.xlsx`
   → **用真实湿实验结局回测我们的过滤阈值**（哪些指标真能区分 EC50<100 nM）。
4. **低成本**：免费合成测试；唯一成本是算力与序列设计。
5. 与长江杯时间窗错开（其靶点公布前），不与 Anthropic×Adaptyv (9/28–10/31) 冲突。

## 3. 制胜逻辑（与长江杯的关键差异）

- **守门员是 AF3**：组委会用 AF3 预测复合物并只合成 Top100。→ 本赛事中"针对 AF3 指标优化"
  不是对抗样本问题，而是**字面上的晋级条件**。但进入湿实验后仍拼真实活性，
  所以策略 = AF3 指标过闸 + 真实界面质量兜底（双目标）。
- **考察的是功能（激动）而非纯结合**：EC50 来自细胞水平激活实验。
  多肽需占据 orthosteric pocket 并稳定活性构象——借鉴 NKA 及已解析人工激动剂的相互作用几何。
- **选择性双倍权重**：Round 2 起 Z[selectivity]×2。负设计（counter-screen NK1R/NK3R）从第一天就要做。
- **先到先得** → 准备好后**尽早提交**，不要压哨。

## 4. 技术策略（融合药化猩球 GPCR 攻略 + 2025 榜单洞察）

**2025 榜单洞察**：头部序列多为含二硫键的环肽（`CP...C...CFYFLM` 类，保留 NKA C端
`F/Y-X-L/M` 药效团的骨架跃迁设计）；胜出方法 = 自定义 ensemble/扩散、进化算法、RFdiffusion、AF2/3。

**三路线配额**（对齐我们的多样性哲学）：
- A. 环肽口袋插入（50–60%）：二硫键/头尾环化稳定构象，深入 orthosteric pocket；
  迭代长度与环大小扫描（12–25 aa 甜区）。
- B. 药效团骨架跃迁（25–35%）：提取 NKA/合成激动剂的 3D interaction motif
  （H-bond 供受体、芳环-疏水口袋、盐桥），在全新骨架上复现相互作用几何——天然相似度天然 <30%。
- C. ECL 外围结合（15–20% 保险）：靶向 ECL2/ECL3 别构区域，正交机制。

**必备检查**：
- Target Construct Audit：官方 AF3 预筛用全长 NK2R + Gα（P50148）→ 我们也用全长 + G 蛋白复合物态做验证，别用截短结晶 construct。
- 负设计：每条候选并行预测 NK1R/NK3R 复合物，SRS = Score_NK2R − max(Score_NK1R, Score_NK3R) 纳入排名。
- 膜碰撞检查：肽-NK2R 复合物中肽段不得与膜平面冲突（GPCR 特有）。
- 二硫键可行性：多 Cys 序列标注氧化折叠风险，合成难度计入人工复核。

## 5. 行动清单

- [ ] 跟进 2026 届官方页面/微信群，确认一轮提交窗口与规则变动（尤其相似度口径、提交上限）
- [ ] 用 2025 榜单数据做阈值校准 notebook（`notebooks/nk2r_2025_calibration.ipynb`）：
      AF 指标 vs EC50 的区分度分析 → 反推 screen/select 阈值
- [ ] NK2R/NK1R/NK3R 三受体结构准备（全长序列 → AF3/Boltz-2 复合物建模，含 Gα）
- [ ] 打通 BoltzGen `peptide-anything` 适配器 + NKA 相似度 mmseqs2 检查脚本
- [ ] 生成 → 三受体负设计 → 膜碰撞/环化可行性过滤 → 配额提交（尽早！）
- [ ] 长江杯侧：NK2R 表位图谱与负设计设施标记为可复用资产（VHH campaign 直接继承）

## 6. 关键参考

- 2025 届规则/榜单: https://www.fbs.frcbs.tsinghua.edu.cn/competition/2025Peptide
- 榜单数据(xlsx): https://www.fbs.frcbs.tsinghua.edu.cn/2025_pep_design_comp_all_entries_with_synthesize_highlight.xlsx
- Science 报道(2025 届): https://www.science.org/content/article/peptide-design-challenge
- GPCR VHH 攻略(药化猩球): 表位图谱 Outer rim T24/A25/F26, ECL D175/Q176/K180,
  口袋入口 Y280/N97/Y289, 深口袋 Y266/F293; VUN701(抗 ACKR3) CDR3 插袋范式
