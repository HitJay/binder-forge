"""报告渲染：人读的 markdown + 机器读的 json + 退出码。

退出码是这套东西能不能当 CI 门禁的关键 —— 没有它, 报告就只是一份没人看的日志。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from binder_forge.review.finding import BLOCK, INFO, SEVERITY_ORDER, WARN, Finding, sort_findings


@dataclass
class Report:
    target_id: str
    findings: list[Finding] = field(default_factory=list)
    rules_run: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    # ── 判定 ──────────────────────────────────────────────────────────────
    def by_severity(self, sev: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == sev]

    @property
    def counts(self) -> dict[str, int]:
        return {s: len(self.by_severity(s)) for s in (BLOCK, WARN, INFO)}

    def has(self, sev: str) -> bool:
        return bool(self.by_severity(sev))

    def exit_code(self, fail_on: str = "block") -> int:
        """fail_on: block(默认) | warn | none(永远 0, 只出报告)。"""
        if fail_on == "none":
            return 0
        threshold = SEVERITY_ORDER[BLOCK] if fail_on == "block" else SEVERITY_ORDER[WARN]
        return 1 if any(SEVERITY_ORDER[f.severity] >= threshold for f in self.findings) else 0

    # ── 渲染 ──────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "generated_at": self.generated_at,
            "rules_run": self.rules_run,
            "counts": self.counts,
            "findings": [f.to_dict() for f in sort_findings(self.findings)],
        }

    def render_md(self, fail_on: str = "block") -> str:
        c = self.counts
        verdict = "放行" if self.exit_code(fail_on) == 0 else "拦截"
        lines = [
            f"# reviewer 报告 · {self.target_id}",
            "",
            f"- 生成时间: {self.generated_at}",
            f"- 执行规则: {', '.join(self.rules_run) if self.rules_run else '(无)'}",
            f"- 判定: **{verdict}**（fail-on={fail_on}）",
            f"- 计数: BLOCK {c[BLOCK]} · WARN {c[WARN]} · INFO {c[INFO]}",
            "",
        ]
        if not self.findings:
            lines.append("无异常。")
            return "\n".join(lines) + "\n"

        for sev, title in ((BLOCK, "必须处理（阻止 export）"),
                           (WARN, "需人工确认"),
                           (INFO, "提示 / 规则跳过")):
            group = sort_findings(self.by_severity(sev))
            if not group:
                continue
            lines += [f"## {title} ({len(group)})", ""]
            for f in group:
                loc = f.design_id or f.artifact or "-"
                lines.append(f"- **{f.rule_id}** `{loc}` — {f.message}")
                if f.expected is not None or f.actual is not None:
                    lines.append(f"  - 期望: `{f.expected}` / 实际: `{f.actual}`")
            lines.append("")
        return "\n".join(lines) + "\n"
