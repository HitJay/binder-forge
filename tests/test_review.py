"""reviewer 回归测试(docs/reviewer.md)。

核心是两条互为镜像的断言:
  - clean 场景必须 0 个 BLOCK   -> 证明规则不会误报
  - corrupt 场景 13 条规则全中 -> 证明规则确实有检出能力

后者是这套东西存在的理由: Anthropic 的 reviewer 无法证明自己能抓到什么, 我们要求
每条规则都必须配一个合成错误探针。
"""
import json
from pathlib import Path

import pytest

from binder_forge.review import (
    BLOCK,
    INFO,
    WARN,
    build_context,
    run_review,
)
from binder_forge.review.report import Report
from binder_forge.review.semantic import (
    DisabledSemanticReviewer,
    HttpSemanticReviewer,
    build_semantic_reviewer,
)

from fixtures import make_case

ALL_RULES = {f"R{i}" for i in range(1, 14)}


def _ctx(case, *, scope="export", submission=True):
    return build_context(
        registry=case.registry,
        target_id=case.target_id,
        target_cfg_path=case.target_yaml,
        profile_path=case.profile_yaml,
        runs_root=case.runs_root,
        repo_root=case.repo,
        submission_dir=case.submission_dir if submission else None,
        scope=scope,
    )


def test_clean_case_has_no_block(tmp_path):
    """无误报: 一份合规的库不许出现任何 BLOCK。"""
    case = make_case(tmp_path, corrupt=False)
    report = run_review(_ctx(case))
    blocks = report.by_severity(BLOCK)
    assert blocks == [], "\n".join(f"{f.rule_id} {f.design_id}: {f.message}" for f in blocks)


def test_all_thirteen_rules_trigger_on_synthetic_errors(tmp_path):
    """有检出: 13 类已知缺陷必须被 13 条规则各自命中。"""
    case = make_case(tmp_path, corrupt=True)
    report = run_review(_ctx(case))
    hit = {f.rule_id for f in report.findings if f.severity in (BLOCK, WARN)}
    missing = ALL_RULES - hit
    assert not missing, f"以下规则未命中, 说明规则或探针失效: {sorted(missing)}"


def test_rules_run_only_export_scoped_when_asked(tmp_path):
    case = make_case(tmp_path, corrupt=False)
    r_all = run_review(_ctx(case, scope="all", submission=False))
    assert "R12" not in r_all.rules_run
    r_exp = run_review(_ctx(case, scope="export"))
    assert "R12" in r_exp.rules_run


def test_exit_code_is_a_real_gate(tmp_path):
    """退出码是 CI 门禁的契约, 不是装饰。"""
    clean = run_review(_ctx(make_case(tmp_path / "c", corrupt=False)))
    assert clean.exit_code("block") == 0 and clean.exit_code("warn") == 0

    case = make_case(tmp_path / "d", corrupt=True)
    dirty = run_review(_ctx(case))
    assert dirty.exit_code("block") == 1
    assert dirty.exit_code("warn") == 1
    assert dirty.exit_code("none") == 0


def test_report_renders_markdown_and_json(tmp_path):
    case = make_case(tmp_path, corrupt=True)
    report = run_review(_ctx(case))
    md = report.render_md("block")
    assert "拦截" in md and "必须处理" in md
    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["counts"][BLOCK] > 0
    assert {f["rule_id"] for f in payload["findings"]} & ALL_RULES


def test_missing_data_is_reported_not_silent(tmp_path):
    """沉默不等于通过: 没数据必须显式报 INFO。"""
    case = make_case(tmp_path, corrupt=False)
    ctx = _ctx(case)
    ctx.records = []
    for r in ctx.records:
        r["predictor_outputs"] = {}
    report = run_review(ctx)
    assert report.has(INFO), "无可复核内容时必须给出 INFO, 不能空报告"


def test_rule_exception_is_contained(tmp_path, monkeypatch):
    import binder_forge.review.runner as runner
    from binder_forge.review.finding import Finding

    def boom(_ctx):
        raise RuntimeError("探针规则故意抛错")

    monkeypatch.setattr(runner, "RULES", [("R99", "探针", boom, "all")])
    report = runner.run_review(_ctx(make_case(tmp_path, corrupt=False)))
    assert any(f.rule_id == "R99" and f.severity == INFO for f in report.findings), \
        "规则崩溃不能被静默吞掉"


def test_export_gate_blocks_corrupt_and_passes_clean(tmp_path):
    from binder_forge.submit.export import ExportBlocked, export_submission

    clean = make_case(tmp_path / "c", corrupt=False)
    res = export_submission(
        registry=clean.registry, target_id=clean.target_id,
        out_dir=tmp_path / "c" / "out", target_cfg_path=clean.target_yaml,
        profile_path=clean.profile_yaml, runs_root=clean.runs_root, repo_root=clean.repo,
    )
    assert res["blocked"] is False
    assert (Path(res["out_dir"]) / ".VERIFIED").exists()
    assert (Path(res["out_dir"]) / "submission.fasta").exists()

    bad = make_case(tmp_path / "d", corrupt=True)
    with pytest.raises(ExportBlocked):
        export_submission(
            registry=bad.registry, target_id=bad.target_id,
            out_dir=tmp_path / "d" / "out", target_cfg_path=bad.target_yaml,
            profile_path=bad.profile_yaml, runs_root=bad.runs_root, repo_root=bad.repo,
        )
    assert (tmp_path / "d" / "out" / ".UNVERIFIED").exists()


def test_cli_exit_code_contract(tmp_path, monkeypatch):
    """退出码必须真的接到 CLI 上, 否则门禁只是一句口号。"""
    from typer.testing import CliRunner

    from binder_forge.cli import app

    case = make_case(tmp_path, corrupt=True)
    monkeypatch.chdir(case.repo)
    runner = CliRunner()
    res = runner.invoke(app, [
        "review", "--target", "configs/targets/TEST.yaml",
        "--profile", "configs/filters/test.yaml",
        "--runs-root", "runs", "--db", str(case.db_path),
        "--submission", str(case.submission_dir), "--stage", "export",
        "--out", str(case.repo / "review_out"),
    ])
    assert res.exit_code == 1, res.output
    assert (case.repo / "review_out" / "review_report.md").exists()

    clean = make_case(tmp_path / "clean", corrupt=False)
    monkeypatch.chdir(clean.repo)
    res2 = runner.invoke(app, [
        "review", "--target", "configs/targets/TEST.yaml",
        "--profile", "configs/filters/test.yaml",
        "--runs-root", "runs", "--db", str(clean.db_path),
        "--submission", str(clean.submission_dir), "--stage", "export",
        "--out", str(clean.repo / "review_out"),
    ])
    assert res2.exit_code == 0, res2.output


def test_semantic_layer_is_off_by_default_and_never_gates(tmp_path, monkeypatch):
    """P4: 默认不发任何请求; 即使启用, 语义层结论也只能是 INFO, 不参与放行。"""
    import urllib.request

    def _no_network(*a, **k):                       # 若被调用即测试失败
        raise AssertionError("默认配置下不得发起任何网络请求")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    reviewer = build_semantic_reviewer(False)
    assert isinstance(reviewer, DisabledSemanticReviewer)

    case = make_case(tmp_path, corrupt=False)
    report = run_review(_ctx(case), semantic=reviewer)
    assert not any(f.rule_id == "R-SEM" for f in report.findings)


def test_http_semantic_findings_are_downgraded_to_info(monkeypatch):
    import io
    import urllib.request

    payload = json.dumps({"findings": [{"rule_id": "R-SEM", "message": "方法文档与代码不符",
                                        "severity": "BLOCK"}]}).encode()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(payload))
    out = HttpSemanticReviewer("http://example.invalid/review").review({"artifacts": {}})
    assert out and all(f.severity == INFO for f in out), "语义层结论不得作为放行依据"

    rep = Report(target_id="T")
    rep.findings.extend(out)
    assert rep.exit_code("block") == 0
