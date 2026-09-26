"""reviewer 的判定单元。

severity 只分三档, 且语义是"能不能放行", 不是"严不严重":
  BLOCK  -> 阻止 export(事实错误: 数字对不上、文件被改、许可不符)
  WARN   -> 需人工确认(可复现性风险: 代码未 pin、重复提交)
  INFO   -> 仅供参考(规则因数据缺失而跳过, 必须显式说出来, 沉默不等于通过)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

BLOCK, WARN, INFO = "BLOCK", "WARN", "INFO"
SEVERITY_ORDER = {INFO: 0, WARN: 1, BLOCK: 2}


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    design_id: str | None = None
    artifact: str | None = None
    expected: str | None = None
    actual: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Rule:
    rule_id: str
    title: str
    fn: "object"          # (ReviewContext) -> list[Finding]
    scope: str = "all"    # all | export
    doc: str = ""


def worst(findings: list[Finding]) -> str | None:
    if not findings:
        return None
    return max((f.severity for f in findings), key=lambda s: SEVERITY_ORDER[s])


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (-SEVERITY_ORDER[f.severity], f.rule_id, f.design_id or ""),
    )
