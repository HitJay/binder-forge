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

echo "== 5. BindCraft(需 PyRosetta 学术许可) =="
mkdir -p "$BINDER_WSL" && cd "$BINDER_WSL"
[ -d BindCraft ] || git clone --depth 1 https://github.com/martinpacesa/BindCraft
# 前置: 到 https://els2.comotion.uw.edu/product/pyrosetta 申请学术许可,
#       下载 PyRosetta .whl 到 ~/binder/, 然后:
#   cd ~/binder/BindCraft && bash install_bindcraft.sh --cuda 12.8 --pkg_manager conda
echo "  (待人工补 PyRosetta 许可后执行 install_bindcraft.sh)"

echo "== 6. RFantibody(VHH 生成) =="
[ -d RFantibody ] || git clone --depth 1 --recursive https://github.com/RosettaCommons/RFantibody
echo "  (按 external/RFantibody/README.md 构建; 官方提供 apptainer 镜像更省事)"

echo "== 7. 在本仓库注册 WSL 环境路径 =="
cat > "$BINDER_WIN/envs_wsl.env" <<EOF
WSL_BOLTZ_PYTHON=$HOME/miniconda/envs/boltz/bin/python
WSL_BOLTZGEN_PYTHON=$HOME/miniconda/envs/boltzgen/bin/python
MMSEQS=$(command -v mmseqs)
EOF
echo "已写入 $BINDER_WIN/envs_wsl.env"

echo "== 完成 =="
echo "冒烟: conda activate boltz && boltz predict <yaml>"
