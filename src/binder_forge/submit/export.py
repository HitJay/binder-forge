"""提交包导出。

产出:
  submission.fasta     —— 按官方格式(待赛规确认 header 规范)
  structures/          —— 每条设计的最佳复折结构(若官方需要)
  METHODS.md           —— 方法文档: pipeline 版本、参数、阈值、血缘统计
                         (赛事强调 Benchmark 沉淀, 规范文档利于评审与复用)

导出必须经过 reviewer 门禁(docs/reviewer.md P3): 先建包, 再复核, 有 BLOCK 即拦截。
顺序是"先建包后复核"而非"先复核后建包", 因为 R12 校验的就是这个包本身 ——
不建出来就没得查。被拦截时包保留在原处(便于排查), 但打上 .UNVERIFIED 标记。
"""
from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path


class ExportBlocked(RuntimeError):
    """reviewer 判定存在 BLOCK, 提交包不予放行。"""


def export_fasta(records: list, out_path: str) -> Path:
    """header: >{design_id}|{target_id}|{modality}|{pipeline}|score={final_score}"""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in records:
        rec = r if isinstance(r, dict) else r.model_dump()
        score = rec.get("final_score")
        score_txt = f"{score:.3f}" if isinstance(score, (int, float)) else "NA"
        lines.append(
            f">{rec['design_id']}|{rec.get('target_id')}|{rec.get('modality')}"
            f"|{rec.get('pipeline')}|score={score_txt}"
        )
        lines.append(rec["sequence"])
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def render_methods(records: list, out_path: str, *, target_id: str = "", profile: dict | None = None) -> Path:
    """从入选记录统计生成方法文档(管线构成/许可构成/聚类数/指标分位数)。"""
    recs = [r if isinstance(r, dict) else r.model_dump() for r in records]
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    pipelines = Counter(r.get("pipeline") for r in recs)
    licenses = Counter(r.get("toolchain_license") for r in recs)
    runs = Counter(r.get("run_id") for r in recs)
    clusters = {r.get("cluster_id") for r in recs}

    lines = [
        f"# METHODS · {target_id or '(未指定靶点)'}",
        "",
        f"- 入选设计: {len(recs)} 条",
        f"- 聚类数: {len(clusters)}",
        "",
        "## 管线构成",
        "",
    ]
    lines += [f"- `{k}`: {v} 条" for k, v in pipelines.most_common()]
    lines += ["", "## 许可构成", ""]
    lines += [f"- `{k}`: {v} 条" for k, v in licenses.most_common()]
    if "pyrosetta-dependent" in licenses:
        lines += ["", "> ⚠️ 含 pyrosetta-dependent 产物，商业使用需 UW/RosettaCommons 授权。"]
    lines += ["", "## 运行溯源", ""]
    lines += [f"- `{k}`: {v} 条" for k, v in runs.most_common()]
    if profile:
        lines += ["", "## 过滤阈值", "", "```yaml"]
        import yaml
        lines.append(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False).rstrip())
        lines.append("```")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def build_submission(records: list, out_dir: str, *, target_id: str = "", profile: dict | None = None) -> Path:
    """建包: FASTA + structures/ + METHODS.md。不含门禁(门禁在 export_submission)。"""
    out = Path(out_dir)
    (out / "structures").mkdir(parents=True, exist_ok=True)
    export_fasta(records, out / "submission.fasta")
    render_methods(records, out / "METHODS.md", target_id=target_id, profile=profile)

    for r in records:
        rec = r if isinstance(r, dict) else r.model_dump()
        sp = rec.get("structure_path")
        if not sp:
            continue
        src = Path(sp)
        if src.exists():
            shutil.copy2(src, out / "structures" / f"{rec['design_id']}{src.suffix}")
    return out


def export_submission(
    *,
    registry,
    target_id: str,
    out_dir: str,
    target_cfg_path: str | None = None,
    profile_path: str | None = None,
    runs_root: str | None = None,
    repo_root: str | None = None,
    quota: int | None = None,
    fail_on: str = "block",
) -> dict:
    """导出提交包, 并强制过 reviewer 门禁。

    返回 {"out_dir", "report", "blocked"}。blocked=True 时包已建但标记为 .UNVERIFIED。
    """
    from binder_forge.review.context import build_context
    from binder_forge.review.report import Report
    from binder_forge.review.runner import run_review

    profile = {}
    if profile_path:
        import yaml
        profile = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8")) or {}

    ctx_all = build_context(
        registry=registry, target_id=target_id,
        target_cfg_path=target_cfg_path, profile_path=profile_path,
        runs_root=runs_root, repo_root=repo_root, quota=quota,
        submission_dir=out_dir, scope="export",
    )
    selected = [r for r in ctx_all.records if r.get("selected")]
    out = build_submission(selected, out_dir, target_id=target_id, profile=profile)

    # 建完包再复核: R12 校验的就是这个包
    ctx = build_context(
        registry=registry, target_id=target_id,
        target_cfg_path=target_cfg_path, profile_path=profile_path,
        runs_root=runs_root, repo_root=repo_root, quota=quota,
        submission_dir=out, scope="export",
    )
    report = run_review(ctx)
    blocked = report.exit_code(fail_on) != 0

    (out / "review_report.md").write_text(report.render_md(fail_on), encoding="utf-8")
    (out / "review_findings.json").write_text(
        __import__("json").dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    marker = out / (".UNVERIFIED" if blocked else ".VERIFIED")
    marker.write_text(report.generated_at, encoding="utf-8")

    result = {"out_dir": str(out), "report": report, "blocked": blocked,
              "n_selected": len(selected)}
    if blocked:
        raise ExportBlocked(
            f"reviewer 判定存在 {report.counts['BLOCK']} 项 BLOCK, 提交包未放行; "
            f"详见 {out / 'review_report.md'}"
        )
    return result
