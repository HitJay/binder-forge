"""产物溯源回归测试(docs/provenance.md 的五条不变式)。

每条不变式对应至少一个断言；"封存后不可写"与"篡改可检出"是其中最关键的两条,
因为它们直接决定 reviewer 的 R9 哈希对账能不能成立。
"""
import json
import os
import stat
from pathlib import Path

import duckdb
import pytest

from binder_forge.db.store import Registry
from binder_forge.design.base import DesignRecord
from binder_forge.provenance import RunContext, iter_events, load_manifest, sha256_file

ROOT = Path(__file__).parents[1]

# 初版 schema(不含溯源列与 toolchain_license), 用于验证旧库可平滑升级
LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS designs (
    design_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, modality TEXT NOT NULL,
    pipeline TEXT NOT NULL, seed INTEGER, config_hash TEXT NOT NULL, parent_id TEXT,
    sequence TEXT NOT NULL, length INTEGER NOT NULL, structure_path TEXT, metrics JSON,
    predictors_agreeing INTEGER DEFAULT 0, passed_screen BOOLEAN DEFAULT FALSE,
    passed_select BOOLEAN DEFAULT FALSE, liability_flags JSON, cluster_id INTEGER,
    final_score DOUBLE, selected BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT now()
);
"""


def _unlock_tree(root: Path) -> None:
    """seal() 会把文件设为只读; 测试结束恢复, 避免影响 tmp 目录清理。"""
    for p in root.rglob("*"):
        try:
            if p.is_file():
                os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass


@pytest.fixture
def run(tmp_path):
    ctx = RunContext.start(
        tmp_path / "runs", target_id="NK2R-PDC", stage="generate",
        config_path="configs/targets/NK2R_peptide.yaml", command="forge generate --budget 5000",
        seed=20261002, config_hash="9f3c1a2b7d", repo_root=ROOT, run_id="gen-20261002T0815Z-test",
    )
    yield ctx
    _unlock_tree(tmp_path)


def test_start_creates_layout_and_manifest(run):
    """不变式 5: manifest 必须带上代码 pin 与阶段边界。"""
    for sub in ("inputs", "artifacts", "logs", "review"):
        assert (run.run_dir / sub).is_dir()
    m = load_manifest(run.run_dir)
    assert m["run_id"] == "gen-20261002T0815Z-test"
    assert m["stage"] == "generate"
    assert m["started_at"] and m["ended_at"] is None
    assert m["config_hash"] == "9f3c1a2b7d"
    assert m["code_rev"], "manifest 必须记录 code_rev, 否则无法复现"
    assert isinstance(m["code_dirty"], bool)


def test_register_artifact_hashes_and_appends_events(run):
    """不变式 1+2+3: 登记即算哈希, 事件流只追加。"""
    f1 = run.run_dir / "artifacts" / "a.pdb"
    f2 = run.run_dir / "artifacts" / "b.pdb"
    f1.write_text("ATOM      1  N   ALA A   1\n", encoding="utf-8")
    f2.write_text("ATOM      1  N   GLY A   1\n", encoding="utf-8")

    e1 = run.register_artifact(f1, design_id="ab12cd34ef56", metrics={"plddt": 88.3})
    e2 = run.register_artifact(f2, design_id="cd34ef56ab12")

    assert e1["sha256"] == sha256_file(f1)
    assert e1["path"] == os.path.join("artifacts", "a.pdb")
    events = iter_events(run.run_dir)
    assert [e["action"] for e in events] == ["artifact_written", "artifact_written"]
    assert events[0]["metrics"] == {"plddt": 88.3}
    assert run.artifact_hashes == {e1["path"]: e1["sha256"], e2["path"]: e2["sha256"]}


def test_snapshot_input_copies_and_hashes(run, tmp_path):
    src = tmp_path / "NK2R.pdb"
    src.write_text("ATOM      1  CA  MET A   1\n", encoding="utf-8")
    entry = run.snapshot_input(src)
    assert (run.run_dir / "inputs" / "NK2R.pdb").exists()
    assert entry["sha256"] == sha256_file(run.run_dir / "inputs" / "NK2R.pdb")
    assert iter_events(run.run_dir)[0]["action"] == "input_snapshot"


def test_seal_blocks_further_writes(run):
    """不变式 4: 封存后任何登记动作必须失败。"""
    f = run.run_dir / "artifacts" / "a.pdb"
    f.write_text("ATOM\n", encoding="utf-8")
    run.register_artifact(f)
    run.seal()

    assert run.sealed and (run.run_dir / "SEALED").exists()
    assert load_manifest(run.run_dir)["ended_at"]
    with pytest.raises(RuntimeError, match="已封存"):
        run.register_artifact(f)
    with pytest.raises(RuntimeError):
        run.snapshot_input(f)


def test_verify_artifacts_detects_tamper(run):
    """reviewer R9 的地基: 产物被改动必须能被重算哈希抓到。"""
    f = run.run_dir / "artifacts" / "a.pdb"
    f.write_text("ATOM      1  N   ALA A   1\n", encoding="utf-8")
    run.register_artifact(f)
    assert run.verify_artifacts() == []

    f.write_text("ATOM      1  N   ALA A   1\nATOM      2  N   GLY A   2\n", encoding="utf-8")
    problems = run.verify_artifacts()
    assert len(problems) == 1
    assert problems[0]["reason"] == "hash_mismatch"
    assert problems[0]["expected"] != problems[0]["actual"]

    f.unlink()
    assert run.verify_artifacts()[0]["reason"] == "missing"


def _make_record(**kw) -> DesignRecord:
    base = dict(
        target_id="NK2R-PDC", modality="peptide", pipeline="boltzgen",
        sequence="HKTDSFVGLM", length=10,
    )
    base.update(kw)
    return DesignRecord(**base)


def test_registry_upsert_keeps_provenance_and_created_at(tmp_path):
    db = tmp_path / "reg.duckdb"
    reg = Registry(db)
    rec = _make_record(
        design_id="deadbeef0001", run_id="gen-20261002T0815Z-test", stage="generate",
        code_rev="a1b2c3d", artifact_hashes={"artifacts/a.pdb": "ff" * 32},
        predictor_outputs={"boltz2": "artifacts/a/confidence.json"},
        metrics={"plddt": 88.3}, toolchain_license="permissive",
    )
    reg.upsert(rec)

    got = reg.get("deadbeef0001")
    assert got["run_id"] == "gen-20261002T0815Z-test"
    assert got["stage"] == "generate"
    assert got["code_rev"] == "a1b2c3d"
    assert json.loads(got["artifact_hashes"]) == {"artifacts/a.pdb": "ff" * 32}
    assert json.loads(got["predictor_outputs"])["boltz2"] == "artifacts/a/confidence.json"
    assert json.loads(got["metrics"])["plddt"] == 88.3
    assert got["toolchain_license"] == "permissive"

    # 二次 upsert 是幂等的, 且不得重置 created_at
    before = got["created_at"]
    rec.stage = "validate"
    reg.upsert(rec)
    after = reg.get("deadbeef0001")
    assert after["stage"] == "validate"
    assert after["created_at"] == before


def test_legacy_database_is_migrated_without_data_loss(tmp_path):
    """旧库升级: 新增列必须补上, 旧行保持可读且溯源字段为 NULL(reviewer 走 WARN)。"""
    db = tmp_path / "legacy.duckdb"
    con = duckdb.connect(str(db))
    con.execute(LEGACY_SCHEMA)
    con.execute(
        "INSERT INTO designs (design_id,target_id,modality,pipeline,config_hash,sequence,length)"
        " VALUES ('old1','NK2R-PDC','peptide','boltzgen','abc','HKTDSFVGLM',10)"
    )
    con.close()

    reg = Registry(db)
    old = reg.get("old1")
    assert old["sequence"] == "HKTDSFVGLM"
    assert old["run_id"] is None, "旧行无溯源字段属正常, reviewer 只报 WARN 不报 BLOCK"
    assert old["toolchain_license"] is None, "初版 schema 漏掉的列也应被补上"

    # 新行照常写入
    reg.upsert(_make_record(design_id="new1", run_id="gen-x", stage="generate"))
    assert reg.get("new1")["run_id"] == "gen-x"
    assert len(reg.query_target("NK2R-PDC")) == 2
    assert len(reg.query_target("NK2R-PDC", stage="generate")) == 1
