"""reviewer：自建的产物/事实一致性校验器(docs/reviewer.md)。

与 Anthropic Claude Science 的 reviewer 的关键差别:
  - 判据是**独立重算**(从 predictor 原始输出重解析、按 filter 配置重放阈值),
    不是"模型自己的叙述 vs 执行记录";
  - 全本地, 零出境;
  - 有退出码契约(--fail-on block), 能当 export 的 CI 门禁;
  - 每条规则都有合成错误探针测试, 检出能力可证明而非声称。
"""
from binder_forge.review.context import ReviewContext, build_context
from binder_forge.review.finding import BLOCK, INFO, WARN, Finding
from binder_forge.review.report import Report
from binder_forge.review.runner import run_review
from binder_forge.review.semantic import (
    DisabledSemanticReviewer,
    HttpSemanticReviewer,
    build_semantic_reviewer,
)

__all__ = [
    "BLOCK", "WARN", "INFO", "Finding", "Report",
    "ReviewContext", "build_context", "run_review",
    "DisabledSemanticReviewer", "HttpSemanticReviewer", "build_semantic_reviewer",
]
