"""运行级产物溯源：run 边界 + 内容哈希 + 只追加事件流。

设计见 docs/provenance.md。五条不变式由本模块强制执行：

  1) 谁产出谁登记  -> register_artifact() 是登记产物的唯一入口
  2) 只追加不改    -> provenance.jsonl 仅 append，历史行永不修改
  3) 哈希即证据    -> 落盘即算 sha256，事后只比对不信任
  4) 目录封存      -> seal() 之后禁止再写
  5) 代码可 pin    -> code_rev / code_dirty 写入 manifest

关于 (4)：Windows 不强制目录只读位（OS 层面形同虚设），因此封存的真正保证来自
**代码层拒绝写入** + reviewer 的哈希对账（R9）。这里的 chmod 只是尽力而为的额外提示。
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

SEAL_MARKER = "SEALED"

STAGE_TOKENS = {
    "prepare": "prep",
    "generate": "gen",
    "validate": "val",
    "filter": "flt",
    "rank": "rank",
    "export": "exp",
    "review": "rev",
}

# 只在能 import 时记录版本，缺失即跳过（HPC 各 env 装的包不一样）
TRACKED_PACKAGES = ("torch", "boltz", "openmm", "freesasa", "numpy", "duckdb", "biopython")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    """流式 sha256，避免大结构文件/PAE 矩阵一次读入内存。"""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def git_state(root: str | Path) -> tuple[str | None, bool]:
    """(短 sha, 工作区是否脏)。

    git 不可用 / 不在仓库中时返回 (None, True) —— 无法 pin 即视为脏，
    因为这正是"三个月后复现不了"的头号根因。
    """
    try:
        rev = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None, True
    if rev.returncode != 0:
        return None, True
    return (rev.stdout.strip() or None), bool(status.stdout.strip())


def tool_versions() -> dict:
    """当前解释器与关键依赖版本。只记录能查到的，查不到就不写。"""
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for pkg in TRACKED_PACKAGES:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            continue
    return out


def load_manifest(run_dir: str | Path) -> dict:
    return json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))


def iter_events(run_dir: str | Path) -> list[dict]:
    """读取事件流。空文件/不存在时返回空列表（旧 run 兼容）。"""
    p = Path(run_dir) / "provenance.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


class RunContext:
    """一次 funnel 阶段运行的溯源上下文。

    典型用法（适配器内）::

        ctx = RunContext.start(runs_root, target_id="NK2R-PDC", stage="generate",
                               config_path="configs/targets/NK2R_peptide.yaml", command=" ".join(sys.argv))
        for rec in adapter.collect():
            ctx.register_artifact(rec.structure_path, design_id=rec.design_id, metrics=rec.metrics)
        ctx.seal()
    """

    def __init__(self, run_dir: str | Path, manifest: dict) -> None:
        self.run_dir = Path(run_dir)
        self.manifest_path = self.run_dir / "manifest.json"
        self.provenance_path = self.run_dir / "provenance.jsonl"
        self.manifest = manifest
        self._sealed = (self.run_dir / SEAL_MARKER).exists()

    # ── 构造 ──────────────────────────────────────────────────────────────

    @classmethod
    def start(
        cls,
        root: str | Path,
        *,
        target_id: str,
        stage: str,
        config_path: str | Path | None = None,
        command: str | None = None,
        seed: int | None = None,
        host: str | None = None,
        scheduler_job_id: str | None = None,
        config_hash: str | None = None,
        repo_root: str | Path | None = None,
        run_id: str | None = None,
        code_rev: str | None = None,
        code_dirty: bool | None = None,
    ) -> "RunContext":
        """开一次新 run：建目录、写初始 manifest（started_at，ended_at 留给 seal）。

        code_rev / code_dirty 可手工覆盖：HPC 上常常拿不到 git 仓库（只同步了代码快照），
        此时由提交方自己 pin 版本号，比让 manifest 留空强。
        """
        rev, dirty = git_state(repo_root or Path.cwd())
        if code_rev is not None:
            rev = code_rev
        if code_dirty is not None:
            dirty = code_dirty
        if run_id is None:
            token = STAGE_TOKENS.get(stage, stage[:4])
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
            run_id = f"{token}-{stamp}-{rev or 'norev'}"

        run_dir = Path(root) / target_id / run_id
        for sub in ("inputs", "artifacts", "logs", "review"):
            (run_dir / sub).mkdir(parents=True, exist_ok=True)

        manifest = {
            "run_id": run_id,
            "stage": stage,
            "target_id": target_id,
            "config_path": str(config_path) if config_path else None,
            "config_hash": config_hash,
            "code_rev": rev,
            "code_dirty": dirty,
            "started_at": _now(),
            "ended_at": None,
            "host": host or platform.node(),
            "scheduler_job_id": scheduler_job_id,
            "command": command,
            "env_lock": "env.lock.txt",
            "tool_versions": tool_versions(),
            "seed": seed,
            "inputs": [],
            "artifacts": [],
        }
        ctx = cls(run_dir, manifest)
        ctx._write_manifest()
        return ctx

    @classmethod
    def open(cls, run_dir: str | Path) -> "RunContext":
        """续跑/复核已有 run。"""
        return cls(Path(run_dir), load_manifest(run_dir))

    # ── 不变式 (4)：封存 ───────────────────────────────────────────────────

    @property
    def sealed(self) -> bool:
        return self._sealed

    def _assert_writable(self) -> None:
        if self._sealed:
            raise RuntimeError(
                f"run {self.manifest['run_id']} 已封存，禁止再写入；"
                f"如需追加产物请开新 run（溯源要求只追加不改）"
            )

    def seal(self) -> None:
        """封存：写 ended_at + SEAL 标记，此后 register_artifact 一律拒绝。"""
        self.manifest["ended_at"] = _now()
        self._write_manifest()
        (self.run_dir / SEAL_MARKER).write_text(self.manifest["ended_at"], encoding="utf-8")
        self._sealed = True
        self._chmod_tree_readonly()

    def _chmod_tree_readonly(self) -> None:
        """尽力而为：Windows 对目录只读位不强制，真正保证来自 _assert_writable + R9 哈希对账。"""
        try:
            for p in self.run_dir.rglob("*"):
                if p.is_file():
                    os.chmod(p, stat.S_IREAD)
        except OSError:
            pass

    # ── 登记 ──────────────────────────────────────────────────────────────

    def _write_manifest(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_event(self, event: dict) -> dict:
        with self.provenance_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def _rel(self, path: str | Path) -> str:
        p = Path(path)
        try:
            return str(p.resolve().relative_to(self.run_dir.resolve()))
        except ValueError:
            return str(p.resolve())

    def snapshot_input(self, path: str | Path) -> dict:
        """把输入文件复制进 inputs/ 并登记。输入快照化，避免事后源文件变了说不清。"""
        self._assert_writable()
        src = Path(path)
        dest = self.run_dir / "inputs" / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        entry = {"path": self._rel(dest), "sha256": sha256_file(dest)}
        self.manifest["inputs"].append(entry)
        self._write_manifest()
        self._append_event({
            "ts": _now(), "run_id": self.manifest["run_id"], "stage": self.manifest["stage"],
            "action": "input_snapshot", "artifact": entry["path"], "sha256": entry["sha256"],
        })
        return entry

    def register_artifact(
        self,
        path: str | Path,
        design_id: str | None = None,
        metrics: dict | None = None,
        kind: str | None = None,
    ) -> dict:
        """登记一个产物：算哈希 + 追加事件流 + 更新 manifest。"""
        self._assert_writable()
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"产物不存在，无法登记: {p}")
        entry = {
            "path": self._rel(p),
            "sha256": sha256_file(p),
            "design_id": design_id,
            "kind": kind,
        }
        if metrics:
            entry["metrics"] = metrics
        self.manifest["artifacts"].append(entry)
        self._write_manifest()
        self._append_event({
            "ts": _now(), "run_id": self.manifest["run_id"], "stage": self.manifest["stage"],
            "action": "artifact_written", "artifact": entry["path"],
            "sha256": entry["sha256"], "design_id": design_id, "metrics": metrics,
        })
        return entry

    def write_env_lock(self) -> Path:
        """写 env.lock.txt。刻意不调 pip freeze（跨 env/HPC 易失败），只记查得到的版本。"""
        self._assert_writable()
        p = self.run_dir / "env.lock.txt"
        lines = [f"{k}=={v}" for k, v in tool_versions().items()]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.register_artifact(p, kind="env_lock")
        return p

    # ── 对账（reviewer R9 的核心）────────────────────────────────────────

    @property
    def artifact_hashes(self) -> dict[str, str]:
        return {a["path"]: a["sha256"] for a in self.manifest["artifacts"]}

    def verify_artifacts(self) -> list[dict]:
        """重算全部已登记产物的 sha256，返回不一致清单（空列表 = 全部一致）。

        这是"产物被后续阶段覆盖/手工改动"最便宜的 detector。
        """
        problems: list[dict] = []
        for rel, expected in self.artifact_hashes.items():
            p = self.run_dir / rel if not Path(rel).is_absolute() else Path(rel)
            if not p.exists():
                problems.append({"path": rel, "reason": "missing", "expected": expected, "actual": None})
                continue
            actual = sha256_file(p)
            if actual != expected:
                problems.append({"path": rel, "reason": "hash_mismatch", "expected": expected, "actual": actual})
        return problems
