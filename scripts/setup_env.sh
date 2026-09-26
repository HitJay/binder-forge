#!/usr/bin/env bash
# binder-forge 环境搭建(Windows 原生实测路径, 2026-09-25 验证)
# 各工具依赖互相冲突, 一工具一 env。WSL2 路径见 docs/env_setup.md。
set -euo pipefail

PY313="C:/Users/Jay/.workbuddy/binaries/python/versions/3.13.12/python.exe"
ENVS="C:/Users/Jay/.workbuddy/binaries/python/envs"

# ---- 1. 编排层(已完成) ----
# "$ENVS/default/Scripts/python.exe" -m pip install -e .
# "$ENVS/default/Scripts/forge.exe" --help

# ---- 2. boltz 验证环境(torch 必须走 PyPI; download.pytorch.org 本网络不可达) ----
# "$PY313" -m venv "$ENVS/boltz"
# "$ENVS/boltz/Scripts/python.exe" -m pip install torch   # PyPI 轮子自带 CUDA, 支持 sm_120
# "$ENVS/boltz/Scripts/python.exe" -m pip install boltz
# 验证: "$ENVS/boltz/Scripts/python.exe" -c "import torch; print(torch.cuda.is_available())"

# ---- 3. 设计管线源码(已克隆到 external/) ----
# git clone --depth 1 https://github.com/HannesStark/boltzgen external/boltzgen
# git clone --depth 1 https://github.com/martinpacesa/BindCraft external/BindCraft
# git clone --depth 1 --recursive https://github.com/RosettaCommons/RFantibody external/RFantibody

# ---- 4. BoltzGen(PyPI 可装, 建议独立 venv 避免与 boltz 依赖互踩) ----
# "$PY313" -m venv "$ENVS/boltzgen"
# "$ENVS/boltzgen/Scripts/python.exe" -m pip install torch boltzgen
# 模型权重需另行下载(见 external/boltzgen/README.md)

# ---- 5. mmseqs2(NKA 相似度官方口径) ----
# 注意: GitHub release CDN (objects.githubusercontent.com) 本网络 502,
# 需开 VPN/代理后重试, 或在 WSL 内 apt install mmseqs2。
# 兜底: src/binder_forge/filters/similarity.py 的 Biopython 近似口径(已通过 2025 获奖序列回归)
# curl -L -o external/bin/mmseqs-win64.zip \
#   https://github.com/soedinglab/MMseqs2/releases/download/18-8cc5c/mmseqs-win64.zip

# ---- 6. BindCraft / RFantibody: 无 Windows 原生路径 ----
# PyRosetta 无 Windows 版 -> 必须 WSL2 或 Linux 服务器, 步骤见 docs/env_setup.md
# PyRosetta 需学术许可: https://els2.comotion.uw.edu/product/pyrosetta

# ---- 7. 代理提示 ----
# 若需走 VPN: export HTTPS_PROXY=http://127.0.0.1:<port>
# 柠檬树等客户端的本地端口请在主界面"系统代理/端口设置"中查看后告知或自行设置

echo "各步骤已注释, 按需逐段执行; 当前状态见 docs/env_setup.md"
