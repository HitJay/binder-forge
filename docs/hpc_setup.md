# HPC 建库清单（本机停止折腾，重活上超算）

> 决策：2026-09-26。本机（Windows + RTX 5060 8GB）不再尝试跑 GPU 管线，
> 仅保留**编排/分析**职能；生成与复折全部上 HPC（国家超算广州中心为长江杯协办方，可询问参赛算力）。

## 1. 环境模块（Linux + NVIDIA，优先用容器/模块）

```bash
# 方式 A：conda（节点有网时）
module load cuda/12.8 gcc/11
wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda
source $HOME/miniconda/etc/profile.d/conda.sh

# 方式 B：容器（推荐，多节点一致性最好）
# apptainer pull docker://...   # 各工具官方镜像/或自建
```

## 2. 按工具建环境（一工具一 env，依赖互冲）

| 环境 | 安装 | 用途 |
|---|---|---|
| `boltz` | `pip install torch --index-url .../cu128 && pip install boltz` | Boltz-2 复折验证（i_pTM/i_PAE/pLDDT + affinity）|
| `boltzgen` | `pip install torch && pip install boltzgen` + 权重下载 | 生成：多肽 / nanobody / minibinder |
| `bindcraft` | `bash install_bindcraft.sh --cuda 12.8 --pkg_manager conda`（需 PyRosetta 许可）| 生成：minibinder |
| `rfantibody` | 按 README 构建（提供 apptainer 镜像）| 生成：VHH（需表位 hotspot）|
| `mmseqs2` | `conda install -c bioconda mmseqs2` | PDC 相似度官方口径 |
| `colabdesign`(可选) | `pip install colabdesign` | AF2 系复折/幻觉 |

## 3. 目录与仓库同步

```bash
git clone git@github.com:HitJay/binder-forge.git
cd binder-forge
# 数据与权重放 $SCRATCH 或 $WORK（勿放 $HOME 配额小的分区）
export BINDER_DATA=$SCRATCH/binder/data
export BINDER_WEIGHTS=$SCRATCH/binder/weights
```

## 4. Slurm 作业模板（以 BoltzGen 批量生成 + Boltz-2 复折为例）

```bash
#!/bin/bash
#SBATCH -J boltzgen-pp
#SBATCH -p gpu
#SBATCH -N 1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=16
#SBATCH -t 24:00:00
#SBATCH -o logs/%j.out

module load cuda/12.8
source $HOME/miniconda/etc/profile.d/conda.sh
conda activate boltzgen

# 1) 生成：按 pipeline_mix 配额产出候选池
boltzgen run configs/targets/NK2R_peptide.yaml --out $SCRATCH/binder/runs/NK2R/gen1

# 2) 复折：与官方同口径(AF3 优先, Boltz-2 交叉)
conda activate boltz
boltz predict $SCRATCH/binder/runs/NK2R/gen1 --out $SCRATCH/binder/runs/NK2R/refold1 --recycling_steps 3

# 3) 回 Windows 侧编排层做 filter/rank（本机即可）
```

## 5. 算力预算（来自调研估算，按每靶点计）

| 阶段 | 规模 | A100 时数 |
|---|---|---|
| BoltzGen 生成 | 20,000 条 × ~45 s | ~250 GPU·h |
| BindCraft 轨迹 | 3,000 条 × ~20 min | ~1,000 GPU·h |
| 复折验证 | 5,000 条 × 2 模型 × ~3 min | ~500 GPU·h |

建议先跑小预算冒烟（生成 200 条 → 复折 20 条）验证端到端链路，再放大。

## 6. 交接状态

- ✅ 编排层代码、校准分析、过滤配置、相似度检查器：本地已完成并推送
- ⏳ 待 HPC：三条生成管线环境、AF3/Boltz-2 复折、端到端冒烟
- 🔑 待人工：PyRosetta 学术许可（BindCraft）
