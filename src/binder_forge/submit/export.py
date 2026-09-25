"""提交包导出。

产出:
  submission.fasta     —— 按官方格式(待赛规确认 header 规范)
  structures/          —— 每条设计的最佳复折结构(若官方需要)
  METHODS.md           —— 方法文档: pipeline 版本、参数、阈值、血缘统计
                         (赛事强调 Benchmark 沉淀, 规范文档利于评审与复用)
"""
from __future__ import annotations


def export_fasta(records: list, out_path: str) -> None:
    """header 建议: >{design_id}|{target_id}|{modality}|{pipeline}|score={final_score:.3f}"""
    raise NotImplementedError


def render_methods(records: list, out_path: str) -> None:
    """从 Design Registry 统计生成方法文档(管线构成/聚类数/指标分位数)。"""
    raise NotImplementedError
