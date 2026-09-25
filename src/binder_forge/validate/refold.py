"""复折验证: 用独立结构预测器重新审视每条设计。

为什么必须多家一致:
  只用 AF2 筛选会富集"骗过 AF2"的对抗性序列(BoltzGen 论文明确指出)。
  本层对每个候选用 >=2 家预测器(boltz2 / af2multimer / chai1 / esmfold)
  独立预测 binder-target 复合物, 提取统一指标, 统计"一致家数"。

指标契约(写入 DesignRecord.metrics):
  pLDDT_binder, i_pTM, i_PAE, monomer_rmsd_A(设计结构 vs 复折),
  每家预测器单独一组 + agreeing 计数。
"""
from __future__ import annotations

from binder_forge.design.base import DesignRecord

SUPPORTED_PREDICTORS = ("boltz2", "af2multimer", "chai1", "esmfold")

# 一致性判定: 两家预测器的 i_pTM 均 >= 阈值即视为"一致通过"
AGREE_IP_TM_THRESHOLD = 0.5


def refold_one(record: DesignRecord, predictor: str, target_structure: str) -> dict:
    """对单条设计跑一个预测器, 返回指标 dict。

    实现要点:
      - boltz2 / chai1: 官方 CLI, 输入序列 YAML/FASTA, 取 i_pTM/i_PAE/pLDDT
      - af2multimer: ColabDesign 或本地 AF2, 注意 MSA 策略(BindCraft 用单序列模式加速)
      - esmfold: 仅作大池子快速初筛(无复合物模式时只能验单体)
    """
    raise NotImplementedError


def agree_count(metrics_by_predictor: dict[str, dict]) -> int:
    """统计 i_pTM >= 阈值的预测器家数。"""
    return sum(
        1 for m in metrics_by_predictor.values()
        if m.get("i_pTM", 0.0) >= AGREE_IP_TM_THRESHOLD
    )
