"""Design Registry: 所有设计的单一事实来源(DuckDB)。

表 designs 与 DesignRecord 模型一一对应。血缘字段(pipeline/seed/config_hash/
parent_id)是赛后复盘与赛事 Benchmark 复用的核心资产, 不允许缺省。
"""
from __future__ import annotations

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


class Registry:
    def __init__(self, db_path: str | Path) -> None:
        self.con = duckdb.connect(str(db_path))
        self.con.execute(SCHEMA)

    def upsert(self, record: "object") -> None:
        """按 design_id 幂等写入(接受 DesignRecord)。"""
        raise NotImplementedError

    def query_target(self, target_id: str, stage: str = "all") -> "object":
        """取某靶点在某 funnel 阶段的全量记录, 返回 DataFrame。"""
        raise NotImplementedError
