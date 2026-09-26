"""reviewer 的入力装配：把 registry、run 目录、配置装成一个可判定的上下文。

刻意做成纯数据容器 —— 所有判断逻辑在 checks.py, 这里只负责"把材料备齐",
这样每条规则都能被单独测试(合成错误探针)。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from binder_forge.design.base import config_hash
from binder_forge.provenance import RunContext

JSON_FIELDS = ("metrics", "liability_flags", "artifact_hashes", "predictor_outputs")


@dataclass
class ReviewContext:
    target_id: str
    records: list[dict] = field(default_factory=list)
    profile: dict = field(default_factory=dict)
    target_cfg: dict = field(default_factory=dict)
    runs_root: Path | None = None
    runs: dict[str, RunContext] = field(default_factory=dict)   # run_id -> RunContext
    quota: int | None = None
    submission_dir: Path | None = None
    config_hashes: dict[str, str] = field(default_factory=dict)  # hash -> relpath
    stage_scope: str = "all"
    base_dirs: list[Path] = field(default_factory=list)   # 相对路径的解析基点

    @property
    def design_ids(self) -> set[str]:
        return {r["design_id"] for r in self.records}

    def metrics_of(self, rec: dict) -> dict:
        m = rec.get("metrics")
        return m if isinstance(m, dict) else {}


def load_target_cfg(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def collect_config_hashes(configs_dir: str | Path) -> dict[str, str]:
    """configs/ 下所有 yaml 的内容哈希 -> 路径。

    R1 用它验证"记录里的 config_hash 真能对上一份存在的配置", 防止参数改了但没重跑。
    """
    root = Path(configs_dir)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.yaml")):
        try:
            out[config_hash(p)] = str(p)
        except (OSError, yaml.YAMLError):
            continue
    return out


def discover_runs(runs_root: str | Path, target_id: str) -> dict[str, RunContext]:
    base = Path(runs_root) / target_id
    runs: dict[str, RunContext] = {}
    if not base.exists():
        return runs
    for manifest in sorted(base.glob("*/manifest.json")):
        try:
            ctx = RunContext.open(manifest.parent)
        except (OSError, json.JSONDecodeError):
            continue
        runs[ctx.manifest["run_id"]] = ctx
    return runs


def build_context(
    *,
    registry,
    target_id: str,
    target_cfg_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    runs_root: str | Path | None = None,
    configs_dir: str | Path | None = None,
    repo_root: str | Path | None = None,
    quota: int | None = None,
    submission_dir: str | Path | None = None,
    scope: str = "all",
) -> ReviewContext:
    """装配复核上下文。

    注意: registry 一律取该靶点的**全部**记录 —— `--stage export` 指的是复核范围
    (是否跑提交包相关规则), 不是只查某个阶段的行; 否则会把没写 stage 的旧行全漏掉。
    """
    df = registry.query_target(target_id, "all")
    records = df.to_dict("records") if hasattr(df, "to_dict") else list(df)
    for r in records:
        # pandas 会把 SQL NULL 变成 NaN(float), 直接喂给 Path() 会炸, 统一还原成 None
        for k, v in list(r.items()):
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
        for k in JSON_FIELDS:
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                try:
                    r[k] = json.loads(v)
                except json.JSONDecodeError:
                    pass
            elif v is None:
                r[k] = {} if k != "liability_flags" else []

    repo = Path(repo_root) if repo_root else Path.cwd()
    cfg = load_target_cfg(target_cfg_path) if target_cfg_path else {}
    prof = load_target_cfg(profile_path) if profile_path else {}
    if quota is None:
        q = (cfg.get("budget") or {}).get("submit_quota")
        quota = int(q) if isinstance(q, (int, float)) else None

    runs = discover_runs(runs_root, target_id) if runs_root else {}
    bases = [repo]
    if runs_root:
        bases.append(Path(runs_root))
    bases.append(Path.cwd())
    return ReviewContext(
        target_id=target_id,
        records=records,
        profile=prof,
        target_cfg=cfg,
        runs_root=Path(runs_root) if runs_root else None,
        runs=runs,
        quota=quota,
        submission_dir=Path(submission_dir) if submission_dir else None,
        config_hashes=collect_config_hashes(configs_dir or repo / "configs"),
        stage_scope=scope,
        base_dirs=bases,
    )
