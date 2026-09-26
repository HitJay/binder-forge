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

## 3. 项目决策（2026-09-26）：默认栈 = 全 Rosetta-free

用户目标含"公司内后续复用"，因此 binder-forge **默认不依赖 PyRosetta**：

| 环节 | 默认实现（可商用） | 可选 Rosetta 增强 |
|---|---|---|
| 生成 | BoltzGen（MIT）、RFdiffusion（BSD-3 含权重）| BindCraft（46.3% 平均命中率，需授权）|
| VHH 生成 | RFantibody 生成模块（代码 MIT；权重源自 RFdiffusion BSD-3）| RFantibody 自带 Rosetta scoring |
| 序列设计 | ProteinMPNN（MIT）| — |
| 复折 / 亲和力 | Boltz-2（MIT）+ AF2（Apache-2.0 / CC-BY）| — |
| 结构松弛 | OpenMM（MIT/LGPL）+ Amber ff14SB | FastRelax |
| 界面物理 | freesasa 埋藏面积 + 氢键几何 + Boltz-2 affinity 概率 | sc / ddG / SAP |

Rosetta 项通过 `configs/filters/rosetta_profile.yaml` 覆盖启用；
启用后 `DesignRecord.toolchain_license = "pyrosetta-dependent"`，便于赛后按许可分类处置。

| 环节 | Rosetta 方案 | 无 Rosetta 替代 |
|---|---|---|
| 生成 | BindCraft / RFantibody | **BoltzGen**（MIT，9 个全新靶点 6/9 拿到纳米抗体）、RFdiffusion（BSD）|
| 序列设计 | ProteinMPNN（本身 MIT，无碍） | ProteinMPNN |
| 复折验证 | — | **Boltz-2**（MIT，含亲和力 head）+ AF2（Apache/CC-BY）|
| 结构松弛 | PyRosetta FastRelax | **OpenMM**（MIT/LGPL）+ Amber ff14SB 最小化 |
| 界面物理打分 | InterfaceAnalyzer (ddG/SASA/sc/SAP) | **BindEnergyCraft**（用冻结预测器的统计能量替代界面置信目标）、freesasa（MIT，埋藏 SASA）、自实现/开源 sc 算法、Boltz-2 affinity 作排序代理 |

**结论**：若目标是"赛后成果可商业化"，主推 **BoltzGen + Boltz-2 + ProteinMPNN + OpenMM** 这条全 MIT/GPL 兼容栈；
BindCraft/RFantibody 作为**学术期**的性能上限工具（BindCraft 平均 46.3% 命中率仍是最强），商用时再替换其 Rosetta 环节或补授权。

## 4. PyRosetta 许可申请流程（2026-09 核实）

### ⚠️ 重要变化：学术许可通道已暂停
Rosetta 仓库 2026-05 更新 LICENSE.md 明示：
> "The academic Rosetta / PyRosetta license has been **temporarily removed** from the GitHub site
> **on 4/1/2026** to comply with University of Washington **export control review** process.
> Users seeking academic licenses should contact **license@uw.edu**, who will provide instructions."

→ 也就是说：老的在线填表通道（`https://els.comotion.uw.edu/licenses/88`）目前不可用，
**第一步是发邮件给 license@uw.edu 索取指引**。

### A. 学术 / 非营利（免费）
条件（许可原文）：非营利研究机构、政府实验室、大学雇员；**且排除** (a) 商业服务、
(b) IP 归营利公司所有的合同研究、(c) 为/代表营利实体的使用、(d) 指向商业利益或报酬的使用。

1. 发邮件至 `license@uw.edu` 说明机构 + 用途，索取学术许可指引
2. 按回执填写（机构邮箱，勿用 Gmail/163 等免费邮箱，易被自动拒）
3. 获批后邮件收到用户名/密码 → 安装：
   ```bash
   pip install pyrosetta --find-links https://west.rosettacommons.org/pyrosetta/quarterly/release
   # 备用源: https://graylab.jhu.edu/download/PyRosetta4/archive/release-quarterly/release
   ```
4. HPC 上使用（TACC 类）：先持证再向集群管理员申请模块授权。

### B. 商业 / 公司使用（付费）
- **前提**：PyRosetta 依附于 Rosetta 本体（Technology No. 45395），需先有 Rosetta 许可。
- 定价按**公司全球 FTE 总数**（不是用户数），三档协议（从 <https://els2.comotion.uw.edu/product/pyrosetta> 下载 PDF）：
  - `<200 FTE` — Commercial
  - `200+ FTE` — Commercial
  - `200+ FTE` — **首次许可：首年 30% ramp fee，之后全额**
- 流程：下载协议 PDF → 填公司信息 + 签字 → 发 `license@uw.edu` 终审签字。
  ⚠️ UW **不接受修改协议条款**，按原文签署。
- ⚠️ **中国实体（含中国香港，不含中国台湾）/ 伊朗 / 朝鲜 / 俄罗斯 / 叙利亚**：
  UW 需额外审查，**多预留 1 个月**（部分页面提示两个月）处理时间。
- 商业场景也可考虑云版 Cyrus Bench（<https://cyrusbio.com>，已含许可的云端 GUI）。

### C. 对我们的影响
用户明确"以后要在公司用"→ 若以公司主体使用 Rosetta 系工具，**必须走 B 通道**；
即便现在用学术许可参赛，一旦成果归属公司或用于商业，即越界（学术许可明确排除
"IP 归营利公司的合同研究"）。因此 **Rosetta-free 默认栈的决策是对的**，
BindCraft/RFantibody 仅作为学术期可选增强。

## 5. 行动项

- [ ] 若以公司主体参赛：走 B 通道（UW CoMotion，按全球 FTE 定价，中国实体预留 +1 个月审查）；或改用 BoltzGen 主线
- [ ] 若以高校/个人学术身份：先发邮件给 license@uw.edu 索取学术许可指引（在线通道 2026-04 起暂停）
- [ ] 核对 AF3 Server / 权重使用条款（若把 AF3 作为官方口径复折）
- [ ] funnel 的 `DesignRecord` 应记录**每条设计的工具链许可标签**，便于赛后按许可分类处置（已在 design/base.py 预留血缘字段，待加 `license` 字段）
