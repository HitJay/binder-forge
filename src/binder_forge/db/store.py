"""Design Registry: 所有设计的单一事实来源(DuckDB)。

表 designs 与 DesignRecord 模型一一对应。血缘字段(pipeline/seed/config_hash/
parent_id)是赛后复盘与赛事 Benchmark 复用的核心资产, 不允许缺省。

溯源扩展见 docs/provenance.md: run_id/stage/code_rev/artifact_hashes/... 由
RunContext 在产出时填写。对旧库执行幂等 ALTER(ADD COLUMN IF NOT EXISTS),
旧行这些字段为 NULL —— reviewer 只报 WARN 不报 BLOCK(见 docs/reviewer.md)。
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS designs (
    design_id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    modality TEXT NOT NULL,
    pipeline TEXT NOT NULL,
    seed INTEGER,
    config_hash TEXT NOT NULL,
    parent_id TEXT,
    sequence TEXT NOT NULL,
    length INTEGER NOT NULL,
    structure_path TEXT,
    metrics JSON,
    predictors_agreeing INTEGER DEFAULT 0,
    passed_screen BOOLEAN DEFAULT FALSE,
    passed_select BOOLEAN DEFAULT FALSE,
    liability_flags JSON,
    cluster_id INTEGER,
    final_score DOUBLE,
    selected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now()
);
"""

# 后加的列: (列名, 类型)。幂等执行, 旧库升级无需迁移脚本。
MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("toolchain_license", "TEXT"),      # DesignRecord 已有, 但初版 schema 漏了
    ("run_id", "TEXT"),
    ("stage", "TEXT"),
    ("code_rev", "TEXT"),
    ("inputs_hash", "TEXT"),
    ("artifact_hashes", "JSON"),
    ("command", "TEXT"),
    ("predictor_outputs", "JSON"),
    ("manifest_uri", "TEXT"),
)

# 与 DesignRecord 字段一一对应, SQL 由此生成, 避免两处漂移
COLUMNS: tuple[str, ...] = (
    "design_id", "target_id", "modality", "pipeline", "seed", "config_hash",
    "parent_id", "sequence", "length", "structure_path", "metrics",
    "toolchain_license", "predictors_agreeing", "passed_screen", "passed_select",
    "liability_flags", "cluster_id", "final_score", "selected",
    "run_id", "stage", "code_rev", "inputs_hash", "artifact_hashes",
    "command", "predictor_outputs", "manifest_uri",
)

JSON_COLUMNS = frozenset({"metrics", "liability_flags", "artifact_hashes", "predictor_outputs"})


class Registry:
    def __init__(self, db_path: str | Path) -> None:
        self.con = duckdb.connect(str(db_path))
        self.con.execute(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        for col, typ in MIGRATIONS:
            self.con.execute(f"ALTER TABLE designs ADD COLUMN IF NOT EXISTS {col} {typ}")

    def upsert(self, record: "object") -> None:
        """按 design_id 幂等写入(接受 DesignRecord)。

        用 ON CONFLICT DO UPDATE 而非 INSERT OR REPLACE —— 后者会重置 created_at,
        丢掉"这条设计最初什么时候进来的"这条信息。
        """
        cols = ", ".join(COLUMNS)
        marks = ", ".join("?" for _ in COLUMNS)
        updates = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "design_id")
        values = []
        for c in COLUMNS:
            v = getattr(record, c, None)
            if c in JSON_COLUMNS and v is not None:
                v = json.dumps(v)
            values.append(v)
        self.con.execute(
            f"INSERT INTO designs ({cols}) VALUES ({marks}) "
            f"ON CONFLICT (design_id) DO UPDATE SET {updates}",
            values,
        )

    def upsert_many(self, records) -> int:
        n = 0
        for r in records:
            self.upsert(r)
            n += 1
        return n

    def query_target(self, target_id: str, stage: str = "all") -> "object":
        """取某靶点在某 funnel 阶段的全量记录, 返回 DataFrame。"""
        if stage == "all":
            return self.con.execute(
                "SELECT * FROM designs WHERE target_id = ?", [target_id]
            ).df()
        return self.con.execute(
            "SELECT * FROM designs WHERE target_id = ? AND stage = ?", [target_id, stage]
        ).df()

    def get(self, design_id: str) -> dict | None:
        row = self.con.execute(
            "SELECT * FROM designs WHERE design_id = ?", [design_id]
        ).fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self.con.description]
        return dict(zip(cols, row))
