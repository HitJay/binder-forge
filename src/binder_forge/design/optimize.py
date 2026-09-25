"""迭代优化循环: predictor-guided evolutionary refinement。

动机(NK2R PDC 2025 榜单实测证据):
  单次生成管线(AF2/3、BindCraft、RFdiffusion、MPNN)活性率仅 5–8%,
  而迭代优化循环(ensemble/diffusion 迭代、进化算法)达 42–65%。
  generation 只负责起好头, 分数导向的突变-重评估循环才是命中率放大器。

位置: funnel 的 generate 之后、正式 filter/rank 之前。
  generate -> [optimize loop] -> validate -> filter -> rank -> export
  (loop 内部每轮对突变体做轻量重打分, 仅最终产物走完整 validate)

目标函数(可配置, objective 字段):
  - PDC 多肽:   AF3 iptm/ptm/ranking_score + NKA 置换 + SRS(选择性)
  - 长江杯 VHH: 双预测器一致口径 + 界面物理指标 (防单模型过拟合/对抗序列)
"""
from __future__ import annotations

from binder_forge.design.base import DesignRecord


class OptimizeConfig:
    """优化循环配置(从靶点 YAML 的 optimize 节读取)。"""

    rounds: int = 6                 # 进化轮数
    population: int = 256           # 每轮种群
    elite_frac: float = 0.1         # 精英保留比例
    mutations_per_seq: tuple = (1, 3)   # 每条亲本突变数范围
    objective: str = "pdc_peptide"  # pdc_peptide | vhh_cross_validated
    diversity_weight: float = 0.15  # 防早熟收敛


def mutate(seq: str, n_mut: int, rng) -> str:
    """随机点突变(可扩展: 片段重组/环区重采样/药效团锚定位点保护)。"""
    raise NotImplementedError


def light_score(record: DesignRecord, objective: str) -> float:
    """轻量重打分: 单预测器快速模式 + 规则项(长度/二硫键/相似度约束)。"""
    raise NotImplementedError


def optimize_pool(records: list[DesignRecord], cfg: OptimizeConfig) -> list[DesignRecord]:
    """主循环: score -> select elite -> mutate/crossover -> dedup -> 记录血缘(parent_id)。
    每轮把种群指标快照写入 Design Registry, 供复盘分析收敛曲线。"""
    raise NotImplementedError
