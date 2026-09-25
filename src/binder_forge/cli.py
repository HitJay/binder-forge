"""统一 CLI 入口。

funnel 六阶段, 每阶段独立可跑、产物落盘、可断点续跑:
  prepare -> generate -> validate -> filter -> rank -> export

用法示例见 README.md。所有阶段共享同一个 Design Registry(DuckDB),
通过 --target 指定靶点配置。
"""
from __future__ import annotations

import typer

app = typer.Typer(help="de novo binder design funnel")


@app.command()
def prepare(target: str = typer.Option(..., help="configs/targets/<id>.yaml")) -> None:
    """靶点结构准备: 清洗/截断/预测补全/表位标注/hotspot 选择。"""
    raise NotImplementedError("见 src/binder_forge/targets/prepare.py")


@app.command()
def generate(
    target: str = typer.Option(...),
    pipelines: str = typer.Option("boltzgen,bindcraft,rfantibody"),
    budget: int = typer.Option(2000, help="候选生成总量"),
) -> None:
    """按 pipeline_mix 配额并行调度设计适配器, 产物写入 Design Registry。"""
    raise NotImplementedError("见 src/binder_forge/design/base.py 及适配器")


@app.command()
def validate(
    target: str = typer.Option(...),
    predictors: str = typer.Option("boltz2,af2multimer"),
) -> None:
    """多预测器复折 + 指标提取。>=2 家一致才进入下一层(防对抗序列)。"""
    raise NotImplementedError("见 src/binder_forge/validate/refold.py")


@app.command()
def filter(target: str = typer.Option(...), profile: str = typer.Option(...)) -> None:
    """按 filters 配置做阈值过滤 + liability 硬淘汰。"""
    raise NotImplementedError("见 src/binder_forge/filters/apply.py")


@app.command()
def rank(
    target: str = typer.Option(...),
    quota: int = typer.Option(100),
    cluster_tm: float = typer.Option(0.6),
) -> None:
    """加权打分 -> TM-score 聚类 -> 簇内配额 -> 提交清单。"""
    raise NotImplementedError("见 src/binder_forge/rank/leaderboard.py")


@app.command()
def export(target: str = typer.Option(...), out: str = typer.Option(...)) -> None:
    """导出提交包: FASTA + 预测结构 + 方法文档(血缘可追溯)。"""
    raise NotImplementedError("见 src/binder_forge/submit/export.py")


if __name__ == "__main__":
    app()
