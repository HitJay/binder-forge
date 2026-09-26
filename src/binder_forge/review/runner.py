"""复核执行器：跑规则、收 finding、出报告。

刻意把"跑哪些规则"和"规则怎么判"分开 —— checks.py 里的每条规则都是纯函数,
这里只负责编排, 这样合成错误探针可以逐条独立验证。
"""
from __future__ import annotations

from binder_forge.review.checks import RULES
from binder_forge.review.finding import INFO, Finding, sort_findings
from binder_forge.review.report import Report
from binder_forge.review.semantic import DisabledSemanticReviewer


def run_review(ctx, semantic=None) -> Report:
    """执行全部适用规则。

    规则执行出错不该让复核静默通过: 捕获异常并转成 INFO finding,
    "这条规则没能跑完"必须显式说出来。
    """
    semantic = semantic or DisabledSemanticReviewer()
    report = Report(target_id=ctx.target_id)

    if not ctx.records and not ctx.runs:
        report.findings.append(Finding("-", INFO, "库中无该靶点记录, 无可复核内容"))
        return report

    # 提交包相关规则: 显式要求 export 范围, 或给了提交包目录才跑
    run_export_rules = (ctx.stage_scope == "export") or (ctx.submission_dir is not None)

    for rule_id, title, fn, scope in RULES:
        if scope == "export" and not run_export_rules:
            continue
        report.rules_run.append(rule_id)
        try:
            report.findings.extend(fn(ctx))
        except Exception as exc:                       # noqa: BLE001 - 规则隔离
            report.findings.append(
                Finding(rule_id, INFO, f"规则执行异常未完成, 结果不可用: {exc!r}")
            )

    # P4 语义层: 一律 INFO, 不参与放行判定
    try:
        report.findings.extend(semantic.review(_artifacts_summary(ctx)))
    except Exception as exc:                           # noqa: BLE001
        report.findings.append(Finding("R-SEM", INFO, f"语义复核异常: {exc!r}"))

    report.findings = sort_findings(report.findings)
    return report


def _artifacts_summary(ctx) -> dict:
    """给语义层的产物摘要(只给路径与元数据, 不给大文件内容)。"""
    return {
        "target_id": ctx.target_id,
        "n_records": len(ctx.records),
        "runs": [rid for rid in ctx.runs],
        "submission_dir": str(ctx.submission_dir) if ctx.submission_dir else None,
        "manifest_uris": [r.get("manifest_uri") for r in ctx.records if r.get("manifest_uri")],
    }
