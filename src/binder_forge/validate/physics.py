"""Rosetta-free 物理打分: OpenMM 松弛 + freesasa 埋藏面积 + 界面氢键几何判定。

为什么必须 Rosetta-free:
  BindCraft / RFantibody 的最后一棒依赖 PyRosetta(FastRelax + InterfaceAnalyzer),
  而 Rosetta 商业使用需 UW/RosettaCommons 付费授权。本项目默认栈要求公司内可直接复用,
  因此用 MIT/LGPL 系组件替代:
    - 松弛:     OpenMM(MIT/LGPL) + Amber ff14SB 能量最小化
    - 埋藏面积: freesasa(MIT) 计算复合态与游离态 SASA 之差
    - 氢键:     Biopython NeighborSearch 几何判定( donor-H...acceptor )
    - 亲和力代理: Boltz-2 affinity head(MIT), 仅作排序, 不作硬门槛

Rosetta 指标(sc / ddG / SAP)仅在 configs/filters/rosetta_profile.yaml 启用时才计算,
并在 DesignRecord.toolchain_license 标记 "pyrosetta-dependent"。
"""
from __future__ import annotations

from pathlib import Path


def relax_openmm(pdb_path: str | Path, forcefield: str = "amber14-all.xml",
                 water: str = "amber14/tip3pfb.xml", iters: int = 500) -> Path:
    """OpenMM 能量最小化(替代 PyRosetta FastRelax), 返回松弛后结构路径。"""
    raise NotImplementedError


def buried_sasa_freesasa(complex_pdb: str | Path,
                         binder_chain: str = "B") -> dict:
    """复合态 vs 游离态 SASA 差 -> 埋藏面积(buried SASA)与界面残基表。"""
    raise NotImplementedError


def interface_hbonds(complex_pdb: str | Path, binder_chain: str = "B",
                     dist_cutoff: float = 3.5) -> int:
    """几何判定界面氢键数(供体-受体距离 + 角度粗筛)。"""
    raise NotImplementedError


def interface_energy_openmm(complex_pdb: str | Path,
                            binder_chain: str = "B") -> float:
    """最小化后界面残基对的相互作用能(kJ/mol), 仅用于相对排序。"""
    raise NotImplementedError
