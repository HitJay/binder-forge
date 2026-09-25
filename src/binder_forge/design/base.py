"""设计管线适配器基类与核心数据模型。

原则: 不重写外部工具。BindCraft / BoltzGen / RFantibody 各自维护官方
代码库(scripts/setup_env.sh 克隆到 external/), 适配器只负责:
  1) 把靶点配置翻译成该工具的输入(PDB/YAML/命令行参数)
  2) 调用工具(建议子进程 + 独立 conda env)
  3) 把输出解析成统一的 DesignRecord 写入 Design Registry
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DesignRecord(BaseModel):
    """一条设计的完整血缘 + 指标。funnel 各阶段逐步填充。"""

    design_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_id: str
    modality: str                       # vhh | minibinder
    pipeline: str                       # boltzgen | bindcraft | rfantibody
    seed: int | None = None
    config_hash: str = ""               # 靶点配置哈希, 保证可复现
    parent_id: str | None = None        # 优化迭代时的父代

    sequence: str
    length: int
    structure_path: str | None = None   # runs/<target>/structures/<id>.pdb

    # validate 阶段填充
    metrics: dict = Field(default_factory=dict)   # pLDDT/i_pTM/i_PAE/RMSD/sc/ddG/...
    predictors_agreeing: int = 0

    # filter/rank 阶段填充
    passed_screen: bool = False
    passed_select: bool = False
    liability_flags: list[str] = Field(default_factory=list)
    cluster_id: int | None = None
    final_score: float | None = None
    selected: bool = False


def config_hash(target_config_path: str | Path) -> str:
    """对靶点配置内容取哈希, 任何参数变化都会生成新的命名空间。"""
    raw = yaml.safe_dump(yaml.safe_load(Path(target_config_path).read_text(encoding="utf-8")))
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


class DesignAdapter:
    """所有 pipeline 适配器的契约。"""

    name: str = "base"

    def __init__(self, target_config: dict, workdir: Path) -> None:
        self.cfg = target_config
        self.workdir = workdir

    def prepare_inputs(self) -> Path:
        """生成该工具所需的输入文件目录。"""
        raise NotImplementedError

    def run(self, n_designs: int) -> None:
        """调用外部工具生成 n_designs 条候选(子进程 + 独立 env)。"""
        raise NotImplementedError

    def collect(self) -> list[DesignRecord]:
        """解析输出为统一 DesignRecord 列表。"""
        raise NotImplementedError
