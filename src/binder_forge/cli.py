"""统一 CLI 入口。

funnel 六阶段, 每阶段独立可跑、产物落盘、可断点续跑:
  prepare -> generate -> validate -> filter -> rank -> review -> export

`review` 是自建的产物溯源 + 事实一致性校验器(docs/reviewer.md), 也是 export 的强制门禁:
它有退出码契约, 有 BLOCK 就不放行提交包。

用法示例见 README.md。所有阶段共享同一个 Design Registry(DuckDB),
通过 --target 指定靶点配置。
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml

app = typer.Typer(help="de novo binder design funnel")


def _target_id(target_cfg: str) -> str:
    cfg = yaml.safe_load(Path(target_cfg).read_text(encoding="utf-8")) or {}
    return (cfg.get("target") or {}).get("id") or Path(target_cfg).stem


def _default_db(target_id: str) -> str:
    return str(Path("runs") / target_id / "registry.duckdb")


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
def review(
    target: str = typer.Option(..., help="configs/targets/<id>.yaml"),
    stage: str = typer.Option("all", help="复核范围: all | export(含提交包一致性)"),
    profile: str = typer.Option(None, help="configs/filters/<name>.yaml, 供 R6/R7 重算"),
    db: str = typer.Option(None, help="DuckDB 路径, 默认 runs/<target>/registry.duckdb"),
    runs_root: str = typer.Option("runs", help="run 目录根"),
    submission: str = typer.Option(None, help="提交包目录(给 R12 校验)"),
    out: str = typer.Option(None, help="报告输出目录"),
    fail_on: str = typer.Option("block", help="block | warn | none(永远退出 0)"),
    semantic: bool = typer.Option(False, help="P4 可选 LLM 语义层, 默认关闭"),
    semantic_endpoint: str = typer.Option(None, help="语义层端点(启用时必填)"),
) -> None:
    """产物溯源 + 事实一致性复核。有 BLOCK 时退出码为 1(export 的强制门禁)。"""
    from binder_forge.db.store import Registry
    from binder_forge.review.context import build_context
    from binder_forge.review.runner import run_review
    from binder_forge.review.semantic import build_semantic_reviewer

    target_id = _target_id(target)
    db_path = db or _default_db(target_id)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    ctx = build_context(
        registry=Registry(db_path),
        target_id=target_id,
        target_cfg_path=target,
        profile_path=profile,
        runs_root=runs_root,
        repo_root=Path.cwd(),
        submission_dir=submission,
        scope=stage,
    )
    report = run_review(ctx, semantic=build_semantic_reviewer(semantic, semantic_endpoint))

    out_dir = Path(out) if out else (Path(runs_root) / target_id / "review")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "review_report.md").write_text(report.render_md(fail_on), encoding="utf-8")
    (out_dir / "review_findings.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    c = report.counts
    typer.echo(
        f"[review] {target_id}: BLOCK {c['BLOCK']} · WARN {c['WARN']} · INFO {c['INFO']} → "
        + ("拦截" if report.exit_code(fail_on) else "放行")
    )
    typer.echo(f"[review] 报告: {out_dir / 'review_report.md'}")
    raise typer.Exit(report.exit_code(fail_on))


@app.command()
def export(
    target: str = typer.Option(...),
    out: str = typer.Option(...),
    profile: str = typer.Option(None, help="configs/filters/<name>.yaml"),
    db: str = typer.Option(None),
    runs_root: str = typer.Option("runs"),
    quota: int = typer.Option(None, help="提交配额(缺省取 target.budget.submit_quota)"),
    fail_on: str = typer.Option("block"),
    allow_blocked: bool = typer.Option(False, help="强行出包(跳过门禁, 不推荐)"),
) -> None:
    """导出提交包: FASTA + 预测结构 + 方法文档(血缘可追溯)。

    导出前强制跑 reviewer; 存在 BLOCK 默认不放行。
    """
    from binder_forge.db.store import Registry
    from binder_forge.submit.export import ExportBlocked, export_submission

    target_id = _target_id(target)
    db_path = db or _default_db(target_id)
    try:
        result = export_submission(
            registry=Registry(db_path), target_id=target_id, out_dir=out,
            target_cfg_path=target, profile_path=profile, runs_root=runs_root,
            repo_root=Path.cwd(), quota=quota,
            fail_on="none" if allow_blocked else fail_on,
        )
    except ExportBlocked as exc:
        typer.echo(f"[export] 被门禁拦截: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"[export] {result['n_selected']} 条 → {result['out_dir']}")


if __name__ == "__main__":
    app()
