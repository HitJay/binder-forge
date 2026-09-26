# 环境搭建状态与指南

> 本机：Windows 11 + RTX 5060 (8 GB, Blackwell sm_120, CUDA 12.9 驱动) + 297 GB 可用磁盘
> 更新时间：2026-09-25（含网络踩坑记录）

## 状态总览

| 组件 | 用途 | 状态 | 说明 |
|---|---|---|---|
| 编排层 (venv `envs/default`) | funnel 编排 + `forge` CLI | ✅ 可用 | `pip install -e .` 完成，CLI 六命令就绪 |
| NKA 相似度检查 | PDC 规则过滤 | ✅ 可用 | `filters/similarity.py`，回归测试 6/6（`tests/test_similarity.py`）|
| torch cu128 + boltz (venv `envs/boltz`) | Boltz-2 复折验证 | 🔄 收尾中 | 见下方"网络踩坑" |
| boltzgen | 生成管线 C（多肽/nanobody） | 📦 已克隆 | `external/boltzgen`，`pip install boltzgen`（PyPI, py≥3.11） |
| BindCraft | 生成管线 B | 📦 已克隆 | `external/BindCraft`；**PyRosetta 无 Windows 版** → WSL2/Linux |
| RFantibody | 生成管线 A（VHH） | 📦 已克隆 | `external/RFantibody`；RFdiffusion 栈 → WSL2/Linux |
| mmseqs2 | NKA 相似度官方口径 | ⚠️ 下载受阻 | GitHub release CDN 不可达（见下）；Biopython 近似口径已兜底 |
| AF3 | 官方预筛同款验证 | 🌐 用网页版 | AlphaFold Server 免装本地 |

## ⚠️ 网络踩坑实录（重要，复用价值高）

1. **PyPI 官方源的 Windows torch 轮子是 CPU 版**（`2.14.0+cpu`）——CUDA 版只在 download.pytorch.org。
2. **download.pytorch.org 本网络不可达**（挂 4.4 小时无响应）。
3. **GitHub release CDN（objects.githubusercontent.com）间歇性 502**——git clone 正常（走 github.com），
   但 release 资产下载失败；mmseqs2 即受此影响。
4. **可用替代**：阿里云镜像 `https://mirrors.aliyun.com/pytorch-wheels/cu128/`（扁平文件列表，
   非 pip index，需直接下载 whl 文件）：

```bash
# CUDA torch 正确安装姿势(已验证可达)
curl -L -o torch-2.11.0+cu128-cp313-cp313-win_amd64.whl \
  "https://mirrors.aliyun.com/pytorch-wheels/cu128/torch-2.11.0%2Bcu128-cp313-cp313-win_amd64.whl"
C:/Users/Jay/.workbuddy/binaries/python/envs/boltz/Scripts/python.exe \
  -m pip install --force-reinstall --no-deps torch-2.11.0+cu128-cp313-cp313-win_amd64.whl
# 注意 --no-deps: 避免 pip 回 PyPI 拉 CPU 版依赖覆盖
```

5. **VPN（柠檬树）**：本地代理端口未知（已探测 7890/7897/10809/10808/1080/8889/2080/33210 均无监听）。
   如需使用请在客户端"系统代理/端口设置"查看后 `export HTTPS_PROXY=http://127.0.0.1:<port>`。
6. **WSL**：沙箱安全策略拦截 wsl.exe（程序黑名单），需用户手动在 PowerShell 执行。

## 本机 Windows 原生路径（已完成）

```bash
# 编排层
cd binder-forge
C:/Users/Jay/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install -e .
forge --help

# boltz 验证环境
python -m venv C:/Users/Jay/.workbuddy/binaries/python/envs/boltz
.../envs/boltz/Scripts/python.exe -m pip install torch        # ⚠️ 得到 CPU 版, 需按上方替换 CUDA 轮子
.../envs/boltz/Scripts/python.exe -m pip install boltz
```

## BindCraft / RFantibody：WSL2 路径（需用户手动执行一次）

```powershell
wsl --install -d Ubuntu        # 首次安装需重启
```

```bash
# WSL Ubuntu 内:
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && bash ~/miniconda.sh -b -p ~/miniconda
export PATH=~/miniconda/bin:$PATH

# BindCraft (需先申请 PyRosetta 学术许可: https://els2.comotion.uw.edu/product/pyrosetta)
git clone https://github.com/martinpacesa/BindCraft && cd BindCraft
bash install_bindcraft.sh --cuda 12.8 --pkg_manager conda

# RFantibody
git clone --recursive https://github.com/RosettaCommons/RFantibody   # 按 README 构建(提供 apptainer 镜像)
```

## 算力现实与扩容路径

- **8 GB VRAM 能做什么**：Boltz-2 复折（GPCR+肽 ~500 aa OK）、BoltzGen 肽/小 miniprotein 生成、optimize loop 轻量打分。
- **8 GB 不够做什么**：BindCraft 大靶点轨迹、大批量 RFdiffusion。
- **扩容选项**：① 国家超算广州中心（长江杯协办方，报名时询问参赛算力）② AutoDL/矩池云 A100 按时租用
  ③ Anthropic×Adaptyv 竞赛的 $250K Modal 算力额度（若申请到）。

## 验收清单

- [x] `forge --help` 六命令可见
- [x] NKA 相似度检查回归测试 6/6 通过
- [ ] `torch.cuda.is_available() == True`（CUDA 轮子安装后验证）
- [ ] boltz predict 冒烟测试（短肽+NK2R 小体系）
- [ ] （WSL）BindCraft example target 跑通
- [ ] （WSL）RFantibody example 跑通
