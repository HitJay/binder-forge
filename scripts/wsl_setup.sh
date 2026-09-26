#!/usr/bin/env bash
# ============================================================
# WSL Ubuntu 内一键搭建 binder-forge 全链路(Linux 原生版)
# 用法: 在 WSL Ubuntu 终端里执行
#   bash /mnt/c/Users/Jay/WorkBuddy/深度调研/binder-forge/scripts/wsl_setup.sh
#
# 前提:
#   - Windows 驱动 >= 515(本机 576.49 ✓), WSL2 默认已支持 GPU 直通
#   - 仓库本身放在 Windows 侧 /mnt/c/..., WSL 直接读写, 无需复制
# ============================================================
set -euo pipefail

BINDER_WIN="/mnt/c/Users/Jay/WorkBuddy/深度调研/binder-forge"
BINDER_WSL="$HOME/binder"
PT="--index-url https://download.pytorch.org/whl/cu128"   # Linux 有真正的 CUDA 轮子

echo "== 0. GPU 检查 =="
nvidia-smi || { echo "WSL 内未识别 GPU: 在 Windows PowerShell 执行 wsl --update 并确认驱动 >= 515"; exit 1; }

echo "== 1. Miniconda =="
if ! command -v conda >/dev/null; then
  wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O "$HOME/miniconda.sh"
  bash "$HOME/miniconda.sh" -b -p "$HOME/miniconda"
fi
# shellcheck disable=SC1091
source "$HOME/miniconda/etc/profile.d/conda.sh"

echo "== 2. 环境: boltz(复折验证) =="
conda create -y -n boltz python=3.12
conda activate boltz
pip install $PT torch
pip install boltz
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA 不可用, 检查驱动/WSL GPU 直通"
print("boltz env CUDA OK:", torch.cuda.get_device_name(0))
PY

echo "== 3. 环境: boltzgen(生成: 多肽/nanobody/minibinder) =="
conda create -y -n boltzgen python=3.12
conda activate boltzgen
pip install $PT torch
pip install boltzgen
# 权重下载命令见 external/boltzgen/README.md(需联网下载 checkpoint)
python -c "import boltzgen; print('boltzgen import ok')"

echo "== 4. mmseqs2(PDC 相似度官方口径) =="
sudo apt-get update -qq && sudo apt-get install -y -qq mmseqs2
mmseqs version

echo "== 5. Rosetta 系工具: 默认跳过(项目策略: Rosetta-free) =="
# ⚠️ BindCraft / RFantibody 依赖 PyRosetta, 商业使用需 UW 付费授权。
# 项目默认栈坚持 Rosetta-free(公司内可直接复用), 这里默认不安装。
# 确需使用(学术期, 已取得许可)时显式加 --with-rosetta:
if [[ "${1:-}" == "--with-rosetta" ]]; then
  mkdir -p "$BINDER_WSL" && cd "$BINDER_WSL"
  [ -d BindCraft ] || git clone --depth 1 https://github.com/martinpacesa/BindCraft
  [ -d RFantibody ] || git clone --depth 1 --recursive https://github.com/RosettaCommons/RFantibody
  echo "  已克隆 BindCraft / RFantibody; 需自行放入 PyRosetta .whl 后执行 install_bindcraft.sh"
  echo "  并注意: 产出设计会被标记为 toolchain_license=pyrosetta-dependent"
else
  echo "  跳过(默认)。如需: bash $0 --with-rosetta"
fi

echo "== 7. 在本仓库注册 WSL 环境路径 =="
cat > "$BINDER_WIN/envs_wsl.env" <<EOF
WSL_BOLTZ_PYTHON=$HOME/miniconda/envs/boltz/bin/python
WSL_BOLTZGEN_PYTHON=$HOME/miniconda/envs/boltzgen/bin/python
MMSEQS=$(command -v mmseqs)
EOF
echo "已写入 $BINDER_WIN/envs_wsl.env"

echo "== 完成 =="
echo "冒烟: conda activate boltz && boltz predict <yaml>"
