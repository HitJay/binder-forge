"""P4：可选的 LLM 语义复核层(默认关闭, 且不进 CI 门禁)。

定位: 只补确定性规则补不了的部分 —— 方法文档与代码是否对得上、引用 DOI 是否解析到
正确的文章。它**不是**事实一致性的判据, 因此产出的 finding 一律降级为 INFO,
永远不参与 --fail-on 的判定。

两个硬约束:
  1) 默认 DisabledSemanticReviewer, 不发任何网络请求(由测试保证);
  2) 不引入任何模型 SDK —— 只留一个 HTTP 端点接口, 接线由使用方自己决定,
     以便遵守公司的数据出境规范。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from binder_forge.review.finding import INFO, Finding


class SemanticReviewer(Protocol):
    def review(self, artifacts: dict) -> list[Finding]: ...


class DisabledSemanticReviewer:
    """默认实现: 什么都不做。"""

    def __init__(self, reason: str = "未启用") -> None:
        self.reason = reason

    def review(self, artifacts: dict) -> list[Finding]:
        return []


class HttpSemanticReviewer:
    """把产物清单发给一个自建端点做语义校对。

    端点约定: POST {"artifacts": {...}} -> {"findings":[{"rule_id": "...", "message": "...", "artifact": "..."}]}
    返回的所有 finding 强制降级为 INFO —— 语义层的判断不作为放行依据。
    """

    def __init__(self, endpoint: str, timeout: float = 20.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def review(self, artifacts: dict) -> list[Finding]:
        payload = json.dumps({"artifacts": artifacts}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
            return [Finding("R-SEM", INFO, f"语义复核端点调用失败, 已忽略: {exc}")]

        out: list[Finding] = []
        for item in data.get("findings", []) if isinstance(data, dict) else []:
            out.append(Finding(
                rule_id=str(item.get("rule_id", "R-SEM")),
                severity=INFO,                       # 强制降级, 不进门禁
                message=str(item.get("message", "")),
                artifact=item.get("artifact"),
            ))
        return out


def build_semantic_reviewer(enabled: bool, endpoint: str | None = None) -> SemanticReviewer:
    if not enabled:
        return DisabledSemanticReviewer()
    if not endpoint:
        return DisabledSemanticReviewer(reason="已启用但未提供端点, 已跳过")
    return HttpSemanticReviewer(endpoint)
