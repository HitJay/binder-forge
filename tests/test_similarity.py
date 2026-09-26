"""NKA 相似度检查回归测试(口径经 2025 获奖序列标定)。"""
from binder_forge.filters.similarity import similarity_vs_nka

CASES = [
    ("HKTDSFVGLM", False),        # NKA 本身必拒
    ("HKTDSFVGLMGG", False),      # 长段 NKA 样序列必拒
    ("CPYTKLNRCCFYFLM", True),    # 2025 第 1 名 (EC50 2.07 nM)
    ("GFPCFYFLM", True),          # 2025 第 2 名
    ("CFYFLM", True),             # 2025 第 3 名
    ("CQRFRPGKCCFYFLM", True),    # 2025 第 5 名
    ("AAAAAAAAAA", True),         # 完全无关序列
]


def test_nka_similarity_cases():
    for seq, expect in CASES:
        ok, _ = similarity_vs_nka(seq)
        assert ok == expect, f"{seq}: got {ok}, expect {expect}"
