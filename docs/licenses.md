# 许可证与商用可行性（重要：影响成果商业化）

> 核实日期 2026-09-26，依据各仓库 LICENSE 原文与 README 声明。

## 1. 许可矩阵

| 组件 | 角色 | 许可证 | 免费商用 | 备注 |
|---|---|---|---|---|
| **BindCraft** | 生成（minibinder） | MIT | ✅ | 代码本体无障碍 |
| **PyRosetta (Rosetta)** | BindCraft 依赖：FastRelax + InterfaceAnalyzer | UW / RosettaCommons | ❌ **商业需付费授权** | BindCraft README 明示 |
| **RFantibody** | 生成（VHH） | MIT | ⚠️ | 代码 MIT，但 `scripts/scoring/minterface.py` 依赖 PyRosetta（ddG / SAP）|
| **RFdiffusion**（含权重） | 生成 | BSD-3-Clause (UW) | ✅ | 权重与代码一并 BSD |
| **ProteinMPNN** | 序列设计 | MIT | ✅ | |
| **BoltzGen** | 生成（多肽/nanobody/minibinder） | MIT | ✅ | **完全无 Rosetta 依赖** |
| **Boltz-2** | 复折 + 亲和力 | MIT | ✅ | |
| **ColabDesign** | AF2 反向传播底座 | 需核对（非 SPDX 标准） | 视 AF2 条款 | AF2 代码 Apache-2.0、权重 CC-BY 4.0 |
| **AlphaFold2 / 3** | 复折验证 | 代码 Apache-2.0；AF2 权重 CC-BY 4.0 | ⚠️ | **AF3 Server 与权重的使用条款需单独核对（研究与商用边界）** |

## 2. 关键判断

- **BindCraft 本身不是障碍**，障碍是它最后一棒用 PyRosetta 做结构松弛与界面物理打分（ddG、埋藏 SASA、形状互补 sc、SAP）。
- **参赛 / 学术研究**：学术 PyRosetta 许可免费（UW 学术协议，注册即得），完全够用——长江杯、NK2R PDC 都在此列。
- **商用 / 以公司主体参赛**：需 Rosetta 商业授权（UW CoMotion / RosettaCommons 付费），否则走下面的无 Rosetta 路线。
- ⚠️ **设计产物本身的 IP 归属与工具许可通常分离**，但是否受"衍生品条款"约束需查具体许可文本或咨询法务——此处不作断言。

## 3. 商用干净的替代栈（推荐给未来转化场景）

| 环节 | Rosetta 方案 | 无 Rosetta 替代 |
|---|---|---|
| 生成 | BindCraft / RFantibody | **BoltzGen**（MIT，9 个全新靶点 6/9 拿到纳米抗体）、RFdiffusion（BSD）|
| 序列设计 | ProteinMPNN（本身 MIT，无碍） | ProteinMPNN |
| 复折验证 | — | **Boltz-2**（MIT，含亲和力 head）+ AF2（Apache/CC-BY）|
| 结构松弛 | PyRosetta FastRelax | **OpenMM**（MIT/LGPL）+ Amber ff14SB 最小化 |
| 界面物理打分 | InterfaceAnalyzer (ddG/SASA/sc/SAP) | **BindEnergyCraft**（用冻结预测器的统计能量替代界面置信目标）、freesasa（MIT，埋藏 SASA）、自实现/开源 sc 算法、Boltz-2 affinity 作排序代理 |

**结论**：若目标是"赛后成果可商业化"，主推 **BoltzGen + Boltz-2 + ProteinMPNN + OpenMM** 这条全 MIT/GPL 兼容栈；
BindCraft/RFantibody 作为**学术期**的性能上限工具（BindCraft 平均 46.3% 命中率仍是最强），商用时再替换其 Rosetta 环节或补授权。

## 4. 行动项

- [ ] 若以公司主体参赛：向 UW CoMotion 询价 Rosetta 商业许可，或改用 BoltzGen 主线
- [ ] 若以高校/个人学术身份：申请学术 PyRosetta 许可（免费），当前栈可直接用
- [ ] 核对 AF3 Server / 权重使用条款（若把 AF3 作为官方口径复折）
- [ ] funnel 的 `DesignRecord` 应记录**每条设计的工具链许可标签**，便于赛后按许可分类处置（已在 design/base.py 预留血缘字段，待加 `license` 字段）
