"""阈值过滤 + liability 检查。

两层制(见 configs/filters/*.yaml):
  screen  —— 生成池 -> 精选池(放宽, 保住多样性)
  select  —— 精选池 -> 提交候选(收紧)
liability 为硬淘汰, 不看总分: 游离 Cys、NG/NS/DG、N-X-S/T、表面疏水超标等。
"""
from __future__ import annotations

import re

from binder_forge.design.base import DesignRecord


def scan_sequence_liabilities(seq: str, profile: dict) -> list[str]:
    """序列层面基序扫描(不依赖结构)。返回命中的 liability 标签列表。"""
    flags: list[str] = []
    forbid = set(profile.get("developability", {}).get("forbid_motifs", []))
    if "NG" in forbid and re.search(r"NG", seq):
        flags.append("deamidation_NG")
    if "NS" in forbid and re.search(r"NS", seq):
        flags.append("deamidation_NS")
    if "DG" in forbid and re.search(r"DG", seq):
        flags.append("isomerization_DG")
    if re.search(r"N[^P][ST]", seq):  # N-X-S/T, X != P
        flags.append("n_glycosylation")
    if profile.get("developability", {}).get("forbid_free_cys") and "C" in seq:
        flags.append("cys_present")  # VHH 需进一步区分框架保守二硫键
    return flags


def apply_thresholds(record: DesignRecord, profile: dict, level: str) -> bool:
    """按 screen/select 层阈值判定。指标方向注意: i_PAE 越小越好。"""
    raise NotImplementedError
