# MOSP for chatMOSP

MOSP (Materials Optimization Simulation Platform) for chatMOSP - 专为chatMOSP对话系统优化的催化反应计算平台，特别专注于金属团簇的结构生成（MSR）和动力学模拟（KMC）。

## 🧪 功能特点

### 1. 团簇结构生成（MSR）
- 生成金属纳米团簇（Pt, Au, Cu, Fe等）
- 支持不同对称性和尺寸
- 输出标准XYZ格式文件

### 2. 动力学蒙特卡洛模拟（KMC）
- 表面反应动力学模拟
- 支持CO氧化、水汽变换等反应
- 计算TOF（周转频率）和表面覆盖度

### 3. 可视化工具
- 生成团簇结构图
- 反应动力学可视化
- 数据分析和绘图

## 📋 系统要求

### 基本要求
- **Python 3.8+**
- **Windows/Linux/macOS**

### Windows用户
- 可以直接运行`engine/main.exe`

### Linux/macOS用户
- 需要安装Wine来运行Windows可执行文件：
  ```bash
  # Ubuntu/Debian
  sudo apt update
  sudo apt install wine
  
  # macOS (使用Homebrew)
  brew install wine
  ```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行示例
```bash
# 使用示例文件运行KMC模拟
python kmc_standalone.py \
  --xyz examples/Au-CO.xyz \
  --json examples/Au-COoxidation.json \
  --out-dir my_first_run
```

### 3. 查看结果
结果将保存在`my_first_run/`目录中，包含：
- `coverage.png` - 表面覆盖度随时间变化
- `tof.png` - TOF随时间变化
- `coverage.csv` - 原始数据
- `tof.csv` - 原始数据

## 📁 目录结构

```
mosp-software/
├── engine/                 # 计算引擎（Windows可执行文件）
│   ├── main.exe           # KMC主程序
│   └── *.dll              # 依赖库
├── examples/              # 示例文件
│   ├── *.xyz             # 结构文件
│   └── *.json            # 输入参数文件
├── utils/                 # 工具脚本
│   ├── msr.py            # MSR计算工具
│   └── paint.py          # 可视化工具
├── kmc_standalone.py      # 主入口脚本
├── requirements.txt       # Python依赖
├── LICENSE.txt           # 软件许可证
└── README.md             # 本文件
```

## 🔧 详细使用指南

### 运行MSR计算
```bash
python utils/msr.py --help
```

### 自定义输入文件
1. 准备结构文件（.xyz格式）
2. 准备参数文件（.json格式）
3. 运行模拟：
   ```bash
   python kmc_standalone.py --xyz your_structure.xyz --json your_params.json --out-dir run_name
   ```

### 可视化结果
```bash
# 使用paint.py生成动画
python utils/paint.py --input run_name/OUTPUT/ --output animation.gif
```

## 📊 支持的金属和反应

### 支持的金属
- Pt（铂）、Au（金）、Cu（铜）
- Fe（铁）、Pd（钯）、Rh（铑）、Ru（钌）

### 支持的反应
1. **CO氧化**：CO + ½O₂ → CO₂
2. **水汽变换反应**：CO + H₂O → CO₂ + H₂
3. **自定义反应**：可以通过修改JSON文件定义

## 🤝 与chatMOSP集成

本版本MOSP专门为chatMOSP对话系统优化，支持：

### 对话式控制
- 通过自然语言对话控制计算
- 自动参数验证和修正
- 智能命令解析

### 简化接口
- 统一的对话接口格式
- 自动错误处理和反馈
- 实时计算状态报告

### 集成特性
- 专为chatMOSP设计的API接口
- 标准化的输入/输出格式（便于对话解析）
- 友好的错误消息（适合对话回复）

**相关对话接口**：请查看 [chatMOSP](https://github.com/mosp-catalysis/chatMOSP) 仓库

## 📄 许可证

本软件使用**学术非商业许可证**，详见[LICENSE.txt](LICENSE.txt)。

**主要条款**：
- ✅ 允许学术研究使用
- ✅ 允许教学使用
- ✅ 允许与chatMOSP集成使用
- ✅ 允许非商业的科学计算
- ❌ 禁止商业用途
- ❌ 禁止未经授权的再分发
- ❌ 禁止脱离chatMOSP环境单独分发

## 🙏 致谢

感谢MOSP课题组的所有贡献者，以及支持本项目的科研基金。

## 📞 支持与反馈

### 问题报告
如果您遇到问题：
1. 检查`requirements.txt`中的依赖是否已安装
2. 确保系统满足Wine要求（Linux/macOS）
3. 查看示例文件是否正常工作

### 学术合作
如果您希望：
- 扩展新的金属类型
- 添加新的反应机理
- 优化计算算法

请联系课题组寻求合作机会。

### 引用要求
如果在学术成果中使用本软件，请引用相关MOSP论文。

---

**MOSP Research Group** - 致力于催化反应计算的自动化与优化 🧪✨