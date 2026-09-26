"""reviewer 的 13 条规则(docs/reviewer.md)。

设计约束:
  1) 每条规则都是纯函数 (ReviewContext -> list[Finding]), 可单独测试;
  2) **缺数据必须显式报 INFO**, 沉默不等于通过 —— 这是与 Claude Science reviewer
     最关键的区别(它只比对叙述与执行记录, 且无法证明自己能抓到什么);
  3) 重算类规则(R5/R6/R7)与 funnel 运行时共用同一套方向定义
     (filters.apply), 不允许出现第二套口径。
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from binder_forge.filters.apply import apply_thresholds, threshold_report
from binder_forge.review.finding import BLOCK, INFO, WARN, Finding
from binder_forge.review.predictors import agreeing_count, parse_all

AA20 = set("ACDEFGHIKLMNPQRSTVWY")
STAGES_WITH_STRUCTURE = {"validate", "filter", "rank", "export"}
ROSETTA_METRIC_KEYS = {"shape_complementarity", "dG_separated", "sap_score", "sc", "ddG"}
TOLERANCE = 1e-3

# 规范指标名 -> 配置里的阈值键(用于把 predictor 输出与 registry 指标对齐)
CANON_TO_CONFIG = {
    "plddt": "pLDDT_binder",
    "iptm": "i_pTM",
    "ptm": "i_pTM",
    "i_pae": "i_PAE",
    "rmsd": "monomer_rmsd_A",
    "boltz2_affinity_prob": "boltz2_affinity_prob",
}


class _Duck:
    """让 dict 行能直接喂给 apply_thresholds(它按属性取值)。"""

    def __init__(self, d: dict) -> None:
        self.__dict__.update(d)


def _resolve(ctx, p):
    path = Path(p)
    if path.is_absolute():
        return path
    for base in ctx.base_dirs:
        cand = base / path
        if cand.exists():
            return cand
    return None


def _run_dir(ctx, rec):
    run = ctx.runs.get(rec.get("run_id"))
    return run.run_dir if run else None


# ── R1 血缘完整 ───────────────────────────────────────────────────────────
def r01_lineage(ctx) -> list[Finding]:
    if not ctx.config_hashes:
        return [Finding("R1", INFO, "未找到 configs/ 目录, 血缘校验跳过")]
    out: list[Finding] = []
    ids = ctx.design_ids
    for r in ctx.records:
        ch = r.get("config_hash")
        if not ch or ch not in ctx.config_hashes:
            out.append(Finding(
                "R1", BLOCK, "config_hash 对不上任何现存配置(配置改过但未重跑设计?)",
                r["design_id"], expected="configs/**.yaml 的内容哈希", actual=str(ch),
            ))
        if r.get("target_id") != ctx.target_id:
            out.append(Finding(
                "R1", BLOCK, "target_id 与本次复核目标不一致",
                r["design_id"], expected=ctx.target_id, actual=str(r.get("target_id")),
            ))
        pid = r.get("parent_id")
        if pid and pid not in ids:
            out.append(Finding(
                "R1", BLOCK, "parent_id 在库内不存在(孤儿设计, 优化迭代链断了)",
                r["design_id"], expected="库内已有的 design_id", actual=str(pid),
            ))
    return out


# ── R2 序列自洽 ───────────────────────────────────────────────────────────
def r02_sequence(ctx) -> list[Finding]:
    out: list[Finding] = []
    bounds = (ctx.target_cfg.get("modality") or {}).get("binder_length")
    for r in ctx.records:
        seq = r.get("sequence") or ""
        if r.get("length") != len(seq):
            out.append(Finding(
                "R2", BLOCK, "length 字段与实际序列长度不符",
                r["design_id"], expected=str(len(seq)), actual=str(r.get("length")),
            ))
        bad = sorted(set(seq) - AA20)
        if bad:
            out.append(Finding(
                "R2", BLOCK, "序列含非天然氨基酸/非法字符",
                r["design_id"], expected="20 种天然氨基酸", actual="".join(bad),
            ))
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            lo, hi = bounds
            if not (lo <= len(seq) <= hi):
                out.append(Finding(
                    "R2", BLOCK, "序列长度超出靶点 modality 允许区间(赛规硬约束)",
                    r["design_id"], expected=f"{lo}-{hi} aa", actual=f"{len(seq)} aa",
                ))
    return out


# ── R3 结构存在 ───────────────────────────────────────────────────────────
def r03_structure(ctx) -> list[Finding]:
    out: list[Finding] = []
    for r in ctx.records:
        sp = r.get("structure_path")
        if not sp or not isinstance(sp, str):
            if r.get("stage") in STAGES_WITH_STRUCTURE or r.get("passed_screen"):
                out.append(Finding(
                    "R3", BLOCK, "已进入复折/筛选阶段却无结构文件",
                    r["design_id"], expected="存在的 pdb/cif 路径", actual="None",
                ))
            continue
        p = _resolve(ctx, sp)
        if p is None or not p.exists():
            out.append(Finding(
                "R3", BLOCK, "structure_path 指向的文件不存在",
                r["design_id"], artifact=str(sp), expected="文件存在", actual="缺失",
            ))
        elif p.stat().st_size == 0:
            out.append(Finding(
                "R3", BLOCK, "结构文件为空", r["design_id"], artifact=str(sp),
            ))
        elif p.suffix.lower() not in {".pdb", ".cif"}:
            out.append(Finding(
                "R3", BLOCK, "结构文件扩展名不受支持",
                r["design_id"], artifact=str(sp), expected=".pdb/.cif", actual=p.suffix,
            ))
    return out


# ── R4 序列-结构一致 ──────────────────────────────────────────────────────
def r04_seq_structure(ctx) -> list[Finding]:
    try:
        from Bio.PDB import PDBParser
        from Bio.PDB.Polypeptide import protein_letters_3to1
    except ImportError:
        return [Finding("R4", INFO, "biopython 不可用, 序列-结构一致性校验跳过")]

    out: list[Finding] = []
    for r in ctx.records:
        sp = r.get("structure_path")
        if not sp or not isinstance(sp, str):
            continue
        p = _resolve(ctx, sp)
        if p is None or not p.exists() or p.suffix.lower() != ".pdb":
            continue
        try:
            structure = PDBParser(QUIET=True).get_structure("m", str(p))
            model = next(iter(structure))
            chains = list(model)
        except Exception as exc:  # 坏文件不该让整个复核崩掉
            out.append(Finding("R4", BLOCK, f"PDB 解析失败: {exc}", r["design_id"], artifact=str(sp)))
            continue
        if not chains:
            out.append(Finding("R4", BLOCK, "结构中无链", r["design_id"], artifact=str(sp)))
            continue
        # binder 链约定: 优先 'B', 否则取最短链(binder 通常比受体短)
        chain = next((c for c in chains if c.id == "B"), min(chains, key=lambda c: len(c)))
        try:
            seq3 = [res.get_resname().strip() for res in chain if res.id[0] == " "]
            from_pdb = "".join(protein_letters_3to1.get(r3, "X") for r3 in seq3)
        except Exception:
            continue
        if "X" in from_pdb:
            out.append(Finding("R4", INFO, "结构含非标准残基, 序列比对跳过",
                               r["design_id"], artifact=str(sp)))
            continue
        if from_pdb != (r.get("sequence") or ""):
            out.append(Finding(
                "R4", BLOCK, "结构中的 binder 链序列与 registry 记录不符",
                r["design_id"], artifact=str(sp),
                expected=r.get("sequence"), actual=from_pdb,
            ))
    return out


# ── R5 指标重算 ───────────────────────────────────────────────────────────
def r05_metrics(ctx) -> list[Finding]:
    from binder_forge.filters.apply import resolve_metric

    out: list[Finding] = []
    for r in ctx.records:
        outs = r.get("predictor_outputs") or {}
        if not outs:
            sev = WARN if r.get("stage") in STAGES_WITH_STRUCTURE else INFO
            out.append(Finding("R5", sev, "无 predictor 原始输出, 指标无法重算(只能信 registry)",
                               r["design_id"]))
            continue
        parsed = parse_all(r, resolver=lambda p: _resolve(ctx, p))
        if not any(parsed.values()):
            out.append(Finding("R5", WARN, "predictor 原始输出无法解析出任何指标", r["design_id"]))
            continue
        metrics = ctx.metrics_of(r)
        for name, vals in parsed.items():
            for canon, value in vals.items():
                cfg_key = CANON_TO_CONFIG.get(canon, canon)
                recorded = resolve_metric(metrics, cfg_key)
                if recorded is None:
                    continue
                if abs(recorded - value) > TOLERANCE:
                    out.append(Finding(
                        "R5", BLOCK, f"{name} 原始输出中的 {canon} 与 registry 记录不一致",
                        r["design_id"], artifact=str(outs.get(name)),
                        expected=f"{value}", actual=f"{recorded}",
                    ))
    return out


# ── R6 阈值重放 ───────────────────────────────────────────────────────────
def r06_thresholds(ctx) -> list[Finding]:
    if not ctx.profile:
        return [Finding("R6", INFO, "未提供 filter profile, 阈值重放跳过")]
    out: list[Finding] = []
    for r in ctx.records:
        duck = _Duck(r)
        for level, field in (("screen", "passed_screen"), ("select", "passed_select")):
            claimed = r.get(field)
            if claimed is None:
                continue
            recomputed = apply_thresholds(duck, ctx.profile, level)
            if bool(claimed) != recomputed:
                failed = [k for k, d in threshold_report(duck, ctx.profile, level).items()
                          if d["pass"] is False]
                out.append(Finding(
                    "R6", BLOCK, f"{field} 与按当前配置重算的结果不符(改了阈值却没重跑 filter?)",
                    r["design_id"], expected=f"{recomputed}" + (f", 未过项: {failed}" if failed else ""),
                    actual=f"{bool(claimed)}",
                ))
    return out


# ── R7 交叉验证口径 ───────────────────────────────────────────────────────
def r07_cross_predictor(ctx) -> list[Finding]:
    if not ctx.profile:
        return [Finding("R7", INFO, "未提供 filter profile, 交叉验证校验跳过")]
    out: list[Finding] = []
    cross = ((ctx.profile.get("folding_confidence") or {}).get("cross_predictor") or {})
    min_agree = cross.get("min_agreeing")
    checked_any = False
    for r in ctx.records:
        if not (r.get("predictor_outputs") or {}):
            continue
        checked_any = True
        actual = agreeing_count(r, ctx.profile, resolver=lambda p: _resolve(ctx, p))
        claimed = r.get("predictors_agreeing")
        if claimed is not None and actual != claimed:
            out.append(Finding(
                "R7", BLOCK, "predictors_agreeing 与实测达标家数不符",
                r["design_id"], expected=str(actual), actual=str(claimed),
            ))
        if isinstance(min_agree, int) and actual < min_agree and r.get("passed_screen"):
            out.append(Finding(
                "R7", BLOCK, "达不到双家一致却标记为通过初筛(对抗序列风险)",
                r["design_id"], expected=f">= {min_agree} 家", actual=f"{actual} 家",
            ))
    if not checked_any:
        out.append(Finding("R7", INFO, "无 predictor 原始输出, 交叉验证口径无法核对"))
    return out


# ── R8 许可合规 ───────────────────────────────────────────────────────────
def r08_license(ctx) -> list[Finding]:
    out: list[Finding] = []
    physics = ctx.profile.get("interface_physics") or {}
    for r in ctx.records:
        pipe = (r.get("pipeline") or "").lower()
        expect_dep = "bindcraft" in pipe
        lic = r.get("toolchain_license")
        if lic is None:
            out.append(Finding("R8", WARN, "旧数据未标注 toolchain_license, 无法按许可分类处置",
                               r["design_id"]))
        elif expect_dep and lic != "pyrosetta-dependent":
            out.append(Finding("R8", BLOCK, "BindCraft 产物必须标记 pyrosetta-dependent(商用需 UW 授权)",
                               r["design_id"], expected="pyrosetta-dependent", actual=str(lic)))
        elif not expect_dep and lic == "pyrosetta-dependent":
            out.append(Finding("R8", BLOCK, "非 BindCraft 产物被标记为 pyrosetta-dependent",
                               r["design_id"], expected="permissive", actual=str(lic)))

        metrics = ctx.metrics_of(r)
        for key in ROSETTA_METRIC_KEYS:
            if key not in metrics:
                continue
            spec = physics.get(key)
            enabled = spec.get("enabled") if isinstance(spec, dict) else None
            if enabled is not True:
                out.append(Finding(
                    "R8", BLOCK, f"出现 Rosetta 专属指标 {key}, 但当前 profile 未启用(默认栈须 Rosetta-free)",
                    r["design_id"], artifact=key,
                ))
    return out


# ── R9 溯源哈希对账 ───────────────────────────────────────────────────────
def r09_hashes(ctx) -> list[Finding]:
    out: list[Finding] = []
    for run_id, run in ctx.runs.items():
        for prob in run.verify_artifacts():
            out.append(Finding(
                "R9", BLOCK, f"run {run_id}: {prob['path']} 被改动或丢失({prob['reason']})",
                artifact=prob["path"], expected=prob["expected"], actual=str(prob["actual"]),
            ))
    for r in ctx.records:
        for rel, expected in (r.get("artifact_hashes") or {}).items():
            run_dir = _run_dir(ctx, r)
            p = (run_dir / rel) if run_dir else _resolve(ctx, rel)
            if p is None or not Path(p).exists():
                out.append(Finding("R9", BLOCK, "登记过的产物已不存在", r["design_id"],
                                   artifact=str(rel), expected=str(expected), actual="缺失"))
                continue
            from binder_forge.provenance import sha256_file
            actual = sha256_file(p)
            if actual != expected:
                out.append(Finding("R9", BLOCK, "登记过的产物内容与当时不一致", r["design_id"],
                                   artifact=str(rel), expected=str(expected), actual=actual))
    if not ctx.runs and not any(r.get("artifact_hashes") for r in ctx.records):
        out.append(Finding("R9", INFO, "无 run manifest / 无产物哈希, 溯源对账跳过"))
    return out


# ── R10 代码可 pin ────────────────────────────────────────────────────────
def r10_code_pin(ctx) -> list[Finding]:
    if not ctx.runs:
        return [Finding("R10", INFO, "无 run manifest, 代码 pin 无法校验")]
    out: list[Finding] = []
    for run_id, run in ctx.runs.items():
        m = run.manifest
        sev = BLOCK if m.get("stage") == "export" else WARN
        if not m.get("code_rev"):
            out.append(Finding("R10", sev, f"manifest 未记录 code_rev: 无法回答'跑的是哪个版本'",
                               artifact=f"run {run_id}"))
        if m.get("code_dirty"):
            out.append(Finding("R10", sev, f"运行时工作区有未提交改动: 结果不可复现",
                               artifact=f"run {run_id}", expected="code_dirty=false", actual="true"))
    return out


# ── R11 聚类/配额自洽 ─────────────────────────────────────────────────────
def r11_quota(ctx) -> list[Finding]:
    out: list[Finding] = []
    selected = [r for r in ctx.records if r.get("selected")]
    if not selected:
        return [Finding("R11", INFO, "尚无 selected 记录, 配额校验跳过")]
    for r in selected:
        if r.get("cluster_id") is None:
            out.append(Finding("R11", BLOCK, "已入选但未分配 cluster_id(多样性配额无从核算)",
                               r["design_id"]))
    if ctx.quota is not None and len(selected) > ctx.quota:
        out.append(Finding("R11", BLOCK, "入选数量超出提交配额",
                           expected=f"<= {ctx.quota}", actual=str(len(selected))))
    cap = ((ctx.profile.get("diversity") or {}).get("max_per_cluster")
           or (ctx.target_cfg.get("budget") or {}).get("max_per_cluster"))
    if cap:
        counts = Counter(r.get("cluster_id") for r in selected)
        for cid, n in counts.items():
            if n > cap:
                out.append(Finding("R11", BLOCK, f"cluster {cid} 入选数超出单簇上限",
                                   expected=f"<= {cap}", actual=str(n)))
    else:
        out.append(Finding("R11", INFO, "未配置 max_per_cluster, 单簇配额校验跳过"))
    return out


# ── R12 提交包一致 ────────────────────────────────────────────────────────
def _read_fasta(path: Path) -> list[str]:
    seqs, cur = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if cur:
                seqs.append("".join(cur))
                cur = []
        elif line.strip():
            cur.append(line.strip())
    if cur:
        seqs.append("".join(cur))
    return seqs


def r12_submission(ctx) -> list[Finding]:
    d = ctx.submission_dir
    if d is None or not d.exists():
        return [Finding("R12", INFO, "未指定提交包目录, 一致性校验跳过")]
    out: list[Finding] = []
    fastas = list(d.glob("*.fasta")) + list(d.glob("*.fa"))
    if not fastas:
        sev = BLOCK if ctx.stage_scope == "export" else WARN
        return [Finding("R12", sev, "提交包内没有 FASTA", artifact=str(d))]
    in_pkg = {s for f in fastas for s in _read_fasta(f)}
    selected = {r["sequence"] for r in ctx.records if r.get("selected")}
    if in_pkg != selected:
        only_pkg = sorted(in_pkg - selected)
        only_db = sorted(selected - in_pkg)
        out.append(Finding(
            "R12", BLOCK,
            f"FASTA 序列集合与 selected 不一致(仅包内 {len(only_pkg)} 条, 仅库内 {len(only_db)} 条)",
            artifact=str(d), expected=f"selected {len(selected)} 条", actual=f"FASTA {len(in_pkg)} 条",
        ))
    for r in ctx.records:
        if not r.get("selected"):
            continue
        sp = r.get("structure_path")
        if not sp or _resolve(ctx, sp) is None:
            out.append(Finding("R12", BLOCK, "入选设计的预测结构缺失, 提交包不完整", r["design_id"]))
    licenses = {r.get("toolchain_license") for r in ctx.records if r.get("selected")}
    for md in list(d.glob("methods*.md")) + list(d.glob("METHODS*.md")):
        text = md.read_text(encoding="utf-8")
        if "pyrosetta-dependent" in text and "pyrosetta-dependent" not in licenses:
            out.append(Finding("R12", BLOCK, "方法文档声明了 pyrosetta 依赖, 但入选设计中无对应产物",
                               artifact=str(md.name)))
    return out


# ── R13 重复提交 ──────────────────────────────────────────────────────────
def r13_duplicates(ctx) -> list[Finding]:
    selected = [r for r in ctx.records if r.get("selected")]
    if not selected:
        return [Finding("R13", INFO, "尚无 selected 记录, 重复检查跳过")]
    counts = Counter(r["sequence"] for r in selected)
    out = []
    for seq, n in counts.items():
        if n > 1:
            dup_ids = [r["design_id"] for r in selected if r["sequence"] == seq]
            out.append(Finding(
                "R13", WARN, "入选集合内有重复序列(先到先得赛制下等于浪费配额)",
                design_id=",".join(dup_ids), expected="唯一", actual=f"{n} 次: {seq}",
            ))
    return out


RULES = [
    ("R1", "血缘完整", r01_lineage, "all"),
    ("R2", "序列自洽", r02_sequence, "all"),
    ("R3", "结构存在", r03_structure, "all"),
    ("R4", "序列-结构一致", r04_seq_structure, "all"),
    ("R5", "指标重算", r05_metrics, "all"),
    ("R6", "阈值重放", r06_thresholds, "all"),
    ("R7", "交叉验证口径", r07_cross_predictor, "all"),
    ("R8", "许可合规", r08_license, "all"),
    ("R9", "溯源哈希对账", r09_hashes, "all"),
    ("R10", "代码可 pin", r10_code_pin, "all"),
    ("R11", "聚类/配额自洽", r11_quota, "all"),
    ("R12", "提交包一致", r12_submission, "export"),
    ("R13", "重复提交", r13_duplicates, "all"),
]
