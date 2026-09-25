#!/usr/bin/env bash
# 端到端彩排: 用 EGFR 校准 funnel —— 它是历届 Adaptyv 竞赛靶点,
# Proteinbase 上有公开湿实验结果(hit rate 2.5% -> 14%, 最佳 1.21 nM)可对答案。
#
# 目的:
#   1) 验证三条 pipeline 全部跑通
#   2) 用已知湿实验结果回测过滤阈值(我们的 select 层能否把已知 binder 排进前列?)
#   3) 估算单靶点 GPU 开销, 为正式赛题做预算
set -euo pipefail

T=configs/targets/EGFR_rehearsal.yaml   # 赛前需按 example_target.yaml 创建

forge prepare   --target $T
forge generate  --target $T --pipelines boltzgen,bindcraft --budget 500   # 彩排缩小预算
forge validate  --target $T --predictors boltz2,af2multimer
forge filter    --target $T --profile configs/filters/minibinder.yaml
forge rank      --target $T --quota 50 --cluster-tm 0.6
forge export    --target $T --out runs/EGFR_rehearsal/submission

echo "对照: https://proteinbase.com/competitions (EGFR 历届公开数据)"
