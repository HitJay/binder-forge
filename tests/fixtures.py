"""合成错误探针(docs/reviewer.md 第 5 节)。

reviewer 的可信度不来自"它检查了什么", 而来自"能证明它抓得到什么"。
所以这里造两个完整场景:
  - clean  : 一份完全合规的库, 跑出来必须 0 个 BLOCK(证明无误报)
  - corrupt: 同一份库注入 13 类已知缺陷, 13 条规则必须全部命中(证明有检出)

每加一条新规则, 就必须在这里补一个对应缺陷 —— 否则这条规则等于没写。
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from binder_forge.db.store import Registry
from binder_forge.design.base import DesignRecord, config_hash
from binder_forge.provenance import RunContext
from binder_forge.submit.export import build_submission

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}
ONE_TO_THREE = {v: k for k, v in THREE_TO_ONE.items()}

TARGET_YAML = {
    "target": {"id": "TEST", "name": "synthetic"},
    "modality": {"primary": "minibinder", "binder_length": [5, 25]},
    "budget": {"submit_quota": 3, "max_per_cluster": 2},
}

PROFILE_YAML = {
    "folding_confidence": {
        "pLDDT_binder": {"screen": 75, "select": 80},
        "i_pTM": {"screen": 0.5, "select": 0.8},
        "i_PAE": {"screen": 0.35, "select": 0.25},
        "cross_predictor": {"min_agreeing": 2},
    },
    "interface_physics": {
        "buried_sasa_A2": {"screen": 800, "select": 1000},
        "shape_complementarity": {"screen": 0.55, "select": 0.60, "enabled": False},
    },
    "diversity": {"max_per_cluster": 2},
}

GOOD_METRICS = {"pLDDT": 90.0, "i_pTM": 0.9, "i_PAE": 0.2}
GOOD_PREDICTOR = {"iptm": 0.9, "plddt": 90.0}


def write_pdb(path: Path, sequence: str, chain: str = "B") -> Path:
    """写一份最小但合法的 PDB(Bio.PDB 能解析出链序列即可)。"""
    lines = []
    for i, aa in enumerate(sequence, start=1):
        res3 = ONE_TO_THREE.get(aa, "ALA")
        lines.append(
            "ATOM  "
            f"{i:5d} "
            " CA "
            " "
            f"{res3:<3s}"
            " "
            f"{chain}"
            f"{i:4d}"
            " "
            "   "
            f"{0.0:8.3f}{0.0:8.3f}{float(i):8.3f}"
            f"{1.0:6.2f}{90.0:6.2f}"
            "          "
            " C"
        )
    lines.append("END")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_predictor(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _seq(n: int, seed: str = "HKTDSFVGLMWYACDEFGHIKLMNPQRSTVWY") -> str:
    return (seed * ((n // len(seed)) + 1))[:n]


def make_case(tmp_path: Path, *, corrupt: bool = False):
    """造一套完整的 registry + runs + 配置, 供 reviewer 复核。"""
    repo = tmp_path / "repo"
    (repo / "configs" / "targets").mkdir(parents=True, exist_ok=True)
    (repo / "configs" / "filters").mkdir(parents=True, exist_ok=True)

    target_yaml = repo / "configs" / "targets" / "TEST.yaml"
    profile_yaml = repo / "configs" / "filters" / "test.yaml"
    target_yaml.write_text(yaml.safe_dump(TARGET_YAML, allow_unicode=True), encoding="utf-8")
    profile_yaml.write_text(yaml.safe_dump(PROFILE_YAML, allow_unicode=True), encoding="utf-8")

    target_id = "TEST"
    ch = config_hash(target_yaml)
    runs_root = repo / "runs"

    run = RunContext.start(
        runs_root, target_id=target_id, stage="validate",
        config_path=target_yaml, config_hash=ch, repo_root=repo,
        run_id="val-TEST001", code_rev="testrev", code_dirty=False,
    )

    db_path = repo / "runs" / target_id / "registry.duckdb"
    reg = Registry(db_path)

    def add(design_id, seq, *, selected=False, cluster_id=None, metrics=None,
            pipeline="boltzgen", license_="permissive", stage="validate",
            agreeing=2, passed=(True, True), pred_payload=None, structure=True,
            cfg_hash=ch, run_id="val-TEST001", length=None, pdb_seq=None):
        pdb_rel = None
        if structure:
            pdb_path = run.run_dir / "artifacts" / f"{design_id}.pdb"
            write_pdb(pdb_path, pdb_seq or seq)
            run.register_artifact(pdb_path, design_id=design_id)
            pdb_rel = f"runs/{target_id}/val-TEST001/artifacts/{design_id}.pdb"
        outs = {}
        if pred_payload is not None:
            for name, payload in pred_payload.items():
                p = run.run_dir / "artifacts" / f"{design_id}_{name}.json"
                _write_predictor(p, payload)
                run.register_artifact(p, design_id=design_id)
                outs[name] = f"runs/{target_id}/val-TEST001/artifacts/{design_id}_{name}.json"
        rec = DesignRecord(
            design_id=design_id, target_id=target_id, modality="minibinder",
            pipeline=pipeline, sequence=seq, length=length if length is not None else len(seq),
            structure_path=pdb_rel, metrics=metrics if metrics is not None else dict(GOOD_METRICS),
            toolchain_license=license_, predictors_agreeing=agreeing,
            passed_screen=passed[0], passed_select=passed[1],
            cluster_id=cluster_id, selected=selected, stage=stage,
            config_hash=cfg_hash, run_id=run_id,
            predictor_outputs=outs,
            artifact_hashes=run.artifact_hashes.copy(),
            manifest_uri=str(run.manifest_path),
        )
        reg.upsert(rec)
        return rec

    good_pred = {"boltz2": dict(GOOD_PREDICTOR), "af2multimer": dict(GOOD_PREDICTOR)}
    add("clean1", _seq(12), selected=True, cluster_id=1, pred_payload=good_pred)
    add("clean2", _seq(13), selected=True, cluster_id=1, pred_payload=good_pred)
    add("clean3", _seq(14), selected=True, cluster_id=2, pred_payload=good_pred)

    if corrupt:
        # R1 血缘: config_hash 对不上任何现存配置
        add("bad01", _seq(12), cfg_hash="deadbeef00")
        # R2 序列: length 字段与实际长度不符
        add("bad02", _seq(12), length=99)
        # R3 结构: 指向不存在的文件
        rec3 = add("bad03", _seq(12), structure=False)
        rec3.structure_path = f"runs/{target_id}/missing.pdb"
        reg.upsert(rec3)
        # R4 序列-结构: PDB 里是另一条序列
        add("bad04", _seq(12), pdb_seq=_seq(11))
        # R5 指标重算: 原始输出与 registry 记录不符
        add("bad05", _seq(12), pred_payload={"boltz2": {"iptm": 0.1, "plddt": 40.0}})
        # R6 阈值重放: 声称通过, 但指标根本不达标
        add("bad06", _seq(12), metrics={"pLDDT": 40.0, "i_pTM": 0.1, "i_PAE": 0.9},
            agreeing=2, pred_payload=good_pred)
        # R7 交叉验证: 声称 2 家一致, 实际只有 1 家达标
        add("bad07", _seq(12), agreeing=2,
            pred_payload={"boltz2": dict(GOOD_PREDICTOR), "af2multimer": {"iptm": 0.1, "plddt": 40.0}})
        # R8 许可: BindCraft 产物未标 pyrosetta-dependent + 混入 Rosetta 指标
        add("bad08", _seq(12), pipeline="bindcraft", license_="permissive",
            metrics=dict(GOOD_METRICS, shape_complementarity=0.7))
        # R9 溯源: 登记过的产物被改动
        p = run.run_dir / "artifacts" / "bad09.pdb"
        write_pdb(p, _seq(12))
        run.register_artifact(p, design_id="bad09")
        p.write_text(p.read_text(encoding="utf-8") + "ATOM      9  CA  GLY B   9       0.000   0.000   9.000  1.00 90.00           C\n",
                     encoding="utf-8")
        add("bad09", _seq(12), structure=False)
        # R10 代码 pin: 另一个 run 的 manifest 没记 code_rev 且工作区脏
        bad_run = RunContext.start(
            runs_root, target_id=target_id, stage="export", repo_root=repo,
            run_id="exp-TEST002", code_rev=None, code_dirty=True,
        )
        bad_run.seal()
        # R11 配额: 入选却没有 cluster_id
        add("bad11", _seq(15), selected=True, cluster_id=None)
        # R12 提交包: 包里多一条不在 selected 里的序列
        # R13 重复: 两条入选序列完全相同
        dup = _seq(16)
        add("bad13a", dup, selected=True, cluster_id=3)
        add("bad13b", dup, selected=True, cluster_id=3)

    submission_dir = repo / "runs" / target_id / "submission"
    selected_rows = [r for r in reg.query_target(target_id, "all").to_dict("records")]
    selected = []
    for r in selected_rows:
        if not r["selected"]:
            continue
        for k in ("metrics", "liability_flags", "artifact_hashes", "predictor_outputs"):
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                r[k] = json.loads(v)
        selected.append(r)
    build_submission(selected, submission_dir, target_id=target_id, profile=PROFILE_YAML)
    if corrupt:
        fasta = submission_dir / "submission.fasta"
        fasta.write_text(fasta.read_text(encoding="utf-8") + ">ghost|EXTRA\n" + _seq(10) + "\n",
                         encoding="utf-8")

    return SimpleNamespace(
        repo=repo, target_id=target_id, db_path=db_path, registry=reg,
        target_yaml=target_yaml, profile_yaml=profile_yaml,
        runs_root=runs_root, submission_dir=submission_dir, run=run,
        config_hash=ch,
    )
