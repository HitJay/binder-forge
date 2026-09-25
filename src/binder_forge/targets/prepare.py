"""靶点结构准备。

输入 configs/targets/<id>.yaml, 输出标准化靶点 PDB + 表位标注:
  1) 结构获取: 实验 PDB > AFDB > 本地 Boltz-2/AF3 预测(低置信区截断或告警)
  2) 清洗: 去无关链/配体/水, 补全缺失侧链(Rosetta 或 pdbfixer)
  3) 截断: 大靶点保留结合域(降低算力与假象风险)
  4) 表位分析(mode=auto): 表面可及性扫描 -> 功能位点优先(已知配体界面/
     受体结合区), 排除糖基化位点与高柔性环, 产出 hotspot 候选供确认
  5) 写出 runs/<target>/prepared/target.pdb + epitope.json
"""
from __future__ import annotations


def fetch_or_predict_structure(cfg: dict) -> str:
    raise NotImplementedError


def clean_and_truncate(pdb_path: str, cfg: dict) -> str:
    raise NotImplementedError


def annotate_epitope(pdb_path: str, cfg: dict) -> dict:
    """返回 {hotspot_residues, avoid_residues, rationale} 供人工确认。"""
    raise NotImplementedError
