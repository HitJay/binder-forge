"""排名与配额分配: 从"过滤后候选池"到"提交清单"。

三步:
  1) 多指标加权打分(final_score) —— 亲和力不可直接预测, 用界面置信+物理互补代理
  2) TM-score 全对全聚类 —— 保证提交集合的拓扑/表位多样性
  3) 簇配额轮转选取 —— 防止一个高得分 fold 占满全部名额

权重依据: Anthropic(2026.08)与历届头部队伍实践表明,
"多预测器界面一致性 + 物理互补"的组合优于任何单一指标。
"""
from __future__ import annotations

from binder_forge.design.base import DesignRecord

# 打分权重(精选层); 可按 Phase 复盘结果调整
# ⚠️ 全 Rosetta-free: 不含 Rosetta sc / ddG(见 configs/filters/rosetta_profile.yaml)
WEIGHTS = {
    "i_pTM_mean": 0.30,           # 多家预测器平均
    "i_PAE_mean_inv": 0.20,       # 取倒数归一
    "pLDDT_binder": 0.15,
    "buried_sasa_norm": 0.15,     # freesasa 埋藏面积, 替代 Rosetta sc
    "boltz2_affinity_prob": 0.10, # Boltz-2 结合概率, 亲和力代理(替代 ddG)
    "predictors_agreeing": 0.10,  # 一致家数加成
}


def final_score(record: DesignRecord) -> float:
    """加权聚合分。缺指标的字段记 0 并在日志中告警。"""
    raise NotImplementedError


def cluster_by_tm(records: list[DesignRecord], tm_threshold: float = 0.6) -> list[int]:
    """TM-align 全对全 -> 贪婪/层次聚类, 返回 cluster_id 列表。"""
    raise NotImplementedError


def allocate_quota(records: list[DesignRecord], quota: int) -> list[DesignRecord]:
    """簇配额轮转: 每轮从各簇取簇内最高分, 直到名额用尽。
    预留 ~15% 名额给'高新颖高风险'设计(低分但远缘簇)作对冲。"""
    raise NotImplementedError
