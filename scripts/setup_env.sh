#!/usr/bin/env bash
# 三条设计管线 + 两家验证器的独立环境安装(Linux + NVIDIA GPU)
# 各工具依赖互相冲突(AF2 系 vs Boltz 系), 必须一工具一 env。
set -euo pipefail
mkdir -p external

# ---- 1. BoltzGen (生成; nanobody-anything 协议对口 VHH 赛题) ----
# git clone https://github.com/HannesStark/boltzgen external/boltzgen
# conda create -n boltzgen python=3.11 -y
# conda run -n boltzgen pip install -e external/boltzgen
# 权重下载见其官方文档(模型权重需另行 download)

# ---- 2. BindCraft (生成; minibinder 主力) ----
# git clone https://github.com/martinpacesa/BindCraft external/BindCraft
# conda env create -n bindcraft -f external/BindCraft/environment.yml
# 注意: BindCraft 依赖 AF2 权重 + PyRosetta(需学术许可)

# ---- 3. RFantibody (生成; VHH 需指定表位 hotspot) ----
# git clone --recursive https://github.com/RosettaCommons/RFantibody external/RFantibody
# 按其 README 构建(RFdiffusion/ProteinMPNN/RF2 微调权重)

# ---- 4. 验证器: Boltz-2 + Chai-1(开源交叉验证) ----
# conda create -n boltz python=3.11 -y && conda run -n boltz pip install boltz -U
# conda create -n chai python=3.11 -y  && conda run -n chai pip install chai_lab

# ---- 5. 本 repo 编排层 ----
# conda env create -f environment.yml && conda activate binder-forge
# pip install -e .

echo "请按注释逐步执行; 各工具权重与许可(PyRosetta)需单独处理"
