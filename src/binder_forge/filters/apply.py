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


# 越小越好的指标(方向写反会让过滤完全反向, 是这类漏斗最常见的静默 bug)
LOWER_IS_BETTER = {
    "i_pae", "ipae", "monomer_rmsd_a", "monomer_rmsd", "rmsd",
    "interface_energy", "min_interface_energy",
}

# 配置里的阈值键 -> 记录里可能的指标键(命名尚未统一, 容错匹配)
THRESHOLD_KEY_CANDIDATES = {
    "pLDDT_binder": ("pLDDT_binder", "plddt_binder", "pLDDT", "plddt"),
    "i_pTM": ("i_pTM", "iptm", "i_ptm"),
    "i_PAE": ("i_PAE", "i_pae", "ipae"),
    "monomer_rmsd_A": ("monomer_rmsd_A", "RMSD", "rmsd"),
    "buried_sasa_A2": ("buriedSASA", "buried_sasa", "buried_sasa_A2"),
    "interface_hbonds": ("interface_hbonds", "hbonds"),
    "min_interface_energy": ("interface_energy", "min_interface_energy"),
    "boltz2_affinity_prob": ("boltz2_prob", "boltz2_affinity_prob", "affinity_prob"),
}


def resolve_metric(metrics: dict, config_key: str):
    """按候选名在 metrics 里取值, 找不到返回 None(表示该指标未测, 不参与判定)。"""
    lower = {str(k).lower(): v for k, v in (metrics or {}).items()}
    for cand in THRESHOLD_KEY_CANDIDATES.get(config_key, (config_key,)):
        v = lower.get(cand.lower())
        if isinstance(v, (int, float)):
            return float(v)
    return None


def metric_passes(config_key: str, value: float, threshold) -> bool | None:
    """单指标判定。threshold 为 None/null 时返回 None(该阈值未启用)。"""
    if threshold is None or value is None:
        return None
    if config_key.lower() in LOWER_IS_BETTER or config_key.lower() in {
        k.lower() for k in LOWER_IS_BETTER
    }:
        return value <= float(threshold)
    return value >= float(threshold)


def threshold_report(record, profile: dict, level: str) -> dict[str, dict]:
    """逐指标给出判定明细, 供 R6 阈值重放比对, 也让"为什么被刷掉"可解释。"""
    metrics = getattr(record, "metrics", {}) or {}
    report: dict[str, dict] = {}
    for section in ("folding_confidence", "interface_physics"):
        block = profile.get(section) or {}
        for key, spec in block.items():
            if not isinstance(spec, dict) or level not in spec:
                continue
            if spec.get("enabled") is False:
                continue
            value = resolve_metric(metrics, key)
            report[key] = {
                "threshold": spec.get(level),
                "value": value,
                "pass": metric_passes(key, value, spec.get(level)),
            }
    return report


def apply_thresholds(record: DesignRecord, profile: dict, level: str) -> bool:
    """按 screen/select 层阈值判定。指标方向注意: i_PAE 越小越好。

    未测的指标(pass=None)不参与判定 —— 缺数据不该被静默判为通过或淘汰,
    这一点由 reviewer 的 R6 单独把关。
    """
    for detail in threshold_report(record, profile, level).values():
        if detail["pass"] is False:
            return False
    cross = ((profile.get("folding_confidence") or {}).get("cross_predictor") or {})
    min_agree = cross.get("min_agreeing")
    if isinstance(min_agree, int) and record.predictors_agreeing < min_agree:
        return False
    return True
