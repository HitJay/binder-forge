"""解析预测器原始输出, 供 R5(指标重算) 与 R7(交叉验证口径) 使用。

各家输出 schema 不统一(Boltz-2 / ColabFold / AF3 各不相同), 这里只做一件事:
把任意嵌套 JSON 里的 pLDDT / i_pTM / i_PAE / affinity prob 抽成规范名。
抽不到就返回空 —— 抽不到必须报出来, 不能当成"没问题"。
"""
from __future__ import annotations

import json
from pathlib import Path

# 归一化后的输出键 -> 规范指标名
KEY_MAP = {
    "plddt": "plddt",
    "plddt_binder": "plddt",
    "iptm": "iptm",
    "i_ptm": "iptm",
    "ipTM": "iptm",
    "iptm_complex": "iptm",
    "ptm": "ptm",
    "i_pae": "i_pae",
    "ipae": "i_pae",
    "pae": "i_pae",
    "min_pae": "i_pae",
    "interface_pae": "i_pae",
    "rmsd": "rmsd",
    "monomer_rmsd": "rmsd",
    "monomer_rmsd_a": "rmsd",
    "affinity_prob": "boltz2_affinity_prob",
    "affinity_probability": "boltz2_affinity_prob",
    "binding_prob": "boltz2_affinity_prob",
}

SUPPORTED_SUFFIXES = {".json"}
UNSUPPORTED_SUFFIXES = {".npz", ".npy", ".pkl"}


def _norm(key: str) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "")


def parse_predictor_output(path: str | Path) -> dict:
    """从预测器原始输出抽取规范指标。返回 {} 表示无法解析(调用方须显式报出)。"""
    p = Path(path)
    if not p.exists():
        return {}
    if p.suffix.lower() in UNSUPPORTED_SUFFIXES:
        return {}
    if p.suffix.lower() not in SUPPORTED_SUFFIXES:
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    found: dict[str, float] = {}
    stack = [data]
    while stack:
        node = stack.pop(0)
        if not isinstance(node, dict):
            continue
        for k, v in node.items():
            canon = KEY_MAP.get(_norm(k))
            if canon and isinstance(v, (int, float)) and canon not in found:
                found[canon] = float(v)
            if isinstance(v, dict):
                stack.append(v)
            elif isinstance(v, list):
                stack.extend(x for x in v if isinstance(x, dict))
    return found


def parse_all(record: dict, resolver=None) -> dict[str, dict]:
    """解析一条记录的 predictor_outputs: {predictor: {metric: value}}。

    resolver 用于把 registry 里的相对路径解析到磁盘(默认按原样), 不传会导致
    "文件其实在, 只是路径相对"被误判成"无法解析"。
    """
    outs = record.get("predictor_outputs") or {}
    if not isinstance(outs, dict):
        return {}
    resolved = {name: (resolver(path) if resolver else path) for name, path in outs.items()}
    return {name: parse_predictor_output(path) for name, path in resolved.items()}


def agreeing_count(record: dict, profile: dict, level: str = "screen", resolver=None) -> int:
    """按该层的阈值, 统计有多少家预测器独立达标。

    与 filters.apply_thresholds 用同一套方向定义, 避免两套口径。
    """
    from binder_forge.filters.apply import metric_passes, resolve_metric

    fold = profile.get("folding_confidence") or {}
    count = 0
    for _name, metrics in parse_all(record, resolver=resolver).items():
        ok = True
        checked = False
        for key, spec in fold.items():
            if not isinstance(spec, dict) or level not in spec or spec.get("enabled") is False:
                continue
            value = resolve_metric(metrics, key)
            verdict = metric_passes(key, value, spec.get(level))
            if verdict is None:
                continue
            checked = True
            if verdict is False:
                ok = False
                break
        if ok and checked:
            count += 1
    return count
