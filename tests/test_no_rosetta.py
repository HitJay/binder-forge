"""策略回归测试：默认栈必须保持 Rosetta-free。

背景：用户要求成果可在公司内直接使用，而 Rosetta/PyRosetta 商业使用需 UW 付费授权。
因此"无 Rosetta"不是偏好而是**硬性策略**，用测试固化，防止后续开发无意引入。

Rosetta 相关能力只允许出现在显式 opt-in 配置（configs/filters/rosetta_profile.yaml）中。
"""
import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src" / "binder_forge"
CONFIGS = ROOT / "configs"

DEFAULT_PROFILES = [
    "filters/default.yaml",
    "filters/peptide.yaml",
    "filters/vhh.yaml",
    "filters/minibinder.yaml",
]
ROSETTA_ONLY_METRICS = ("shape_complementarity", "dG_separated", "sap_score")


def test_no_pyrosetta_import_in_source():
    """默认代码路径不得 import pyrosetta（含任何子模块）。"""
    for f in SRC.rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for n in names:
                assert not n.lower().startswith("pyrosetta"), \
                    f"{f.relative_to(ROOT)} imports {n}; Rosetta 依赖只允许 opt-in"


def test_default_profiles_disable_rosetta_metrics():
    """默认过滤配置中，Rosetta 专属指标必须显式关闭。"""
    for rel in DEFAULT_PROFILES:
        p = CONFIGS / rel
        if not p.exists():
            continue
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        phys = cfg.get("interface_physics") or {}
        for key in ROSETTA_ONLY_METRICS:
            val = phys.get(key)
            if isinstance(val, dict):
                assert val.get("enabled") is False, \
                    f"{rel}: {key} 默认必须 enabled: false"
        engine = (cfg.get("relax") or {}).get("engine", "openmm")
        assert engine != "pyrosetta", f"{rel}: relax 默认引擎不得为 pyrosetta"


def test_rosetta_profile_is_explicit_opt_in():
    """Rosetta 增强配置必须显式标记，便于按许可分类处置。"""
    cfg = yaml.safe_load(
        (CONFIGS / "filters/rosetta_profile.yaml").read_text(encoding="utf-8")
    )
    assert cfg["license_flag"] == "pyrosetta-dependent"
    assert cfg["interface_physics"]["shape_complementarity"]["enabled"] is True
    assert cfg["relax"]["engine"] == "pyrosetta"
