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

## 📋 系统要求与安装指南

### 基本要求
- **Python 3.8+**
- **Windows/Linux/macOS**
- **至少4GB RAM**，推荐8GB+用于大规模计算
- **10GB磁盘空间**用于存储计算结果

### 🖥️ Windows用户（最简单）
- 可以直接运行`engine/main.exe`
- 无需额外配置

### 🐧 Linux用户（需要Wine）

#### 1. 安装Wine（必需）
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install wine

# 验证安装
wine --version  # 应该显示wine版本

# 如果遇到wine32缺失警告（可选，消除警告）
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install wine32:i386
```

#### 2. Ubuntu 24.04+特殊问题
```bash
# 如果遇到错误: 'https://ppa.launchpadcontent.net/wine/wine-builds/ubuntu noble Release' does not have a Release file

# 解决方案：移除问题仓库，使用官方仓库
sudo apt-add-repository -r 'ppa:wine/wine-builds'
sudo apt update
sudo apt install wine
```

#### 3. 权限配置
```bash
# 确保main.exe可执行
chmod +x engine/main.exe

# 测试运行
wine engine/main.exe --help 2>&1 | head -5
```

### 🍎 macOS用户（需要Wine）
```bash
# 使用Homebrew安装Wine
brew install wine

# 或使用Wine Staging（更稳定）
brew install --cask wine-staging
```

### 🐍 Python环境配置（所有平台）

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

# 3. 安装依赖
pip install numpy pandas matplotlib scipy imageio

# 4. 验证安装
python -c "import numpy, pandas, matplotlib; print('✅ Python依赖安装成功')"
```

### 🔗 与chatMOSP集成配置（重要！）

**问题**：chatMOSP技能期望`chatMOSP/`目录，但本软件安装为`mosp-for-chatMOSP/`

**解决方案**：创建符号链接

```bash
# 在workspace目录中
cd /root/.openclaw/workspace

# 创建符号链接
ln -sf mosp-for-chatMOSP chatMOSP

# 验证
ls -la | grep chatMOSP  # 应该显示: chatMOSP -> mosp-for-chatMOSP
```

**目录结构关系**：
```
workspace/
├── chatMOSP -> mosp-for-chatMOSP/      # 符号链接
├── mosp-for-chatMOSP/                  # 本软件
│   ├── engine/                         # Windows计算引擎
│   ├── examples/                       # 示例文件
│   └── ...
├── chatMOSP-skill/                     # chatMOSP技能
└── skills/                             # OpenClaw技能目录
```

### ✅ 完整安装验证脚本

```bash
#!/bin/bash
# mospsetup-check.sh - MOSP安装验证脚本

echo "🔍 MOSP环境验证检查"
echo "===================="

echo "\n1. Wine检查:"
if command -v wine > /dev/null 2>&1; then
    echo "✅ Wine已安装: $(wine --version 2>/dev/null || echo '版本未知')"
else
    echo "❌ Wine未安装 - Linux/macOS需要Wine运行Windows版MOSP"
    echo "   运行: sudo apt install wine 或 brew install wine"
fi

echo "\n2. Python环境检查:"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Python虚拟环境存在"
    python -c "
import sys
print(f'Python版本: {sys.version}')
try:
    import numpy, pandas, matplotlib, scipy
    print('✅ 核心依赖安装成功')
except ImportError as e:
    print(f'❌ 依赖缺失: {e}')
"
deactivate
else
    echo "⚠️ Python虚拟环境不存在"
    echo "   运行: python3 -m venv venv"
fi

echo "\n3. 计算引擎检查:"
if [ -f "engine/main.exe" ]; then
    echo "✅ main.exe存在"
    ls -la engine/main.exe
    
    # 测试权限
    if [ -x "engine/main.exe" ]; then
        echo "✅ main.exe可执行"
    else
        echo "⚠️ main.exe不可执行，运行: chmod +x engine/main.exe"
    fi
else
    echo "❌ main.exe不存在"
fi

echo "\n4. 符号链接检查（chatMOSP集成）:"
if [ -L "../chatMOSP" ] && [ "$(readlink -f ../chatMOSP)" = "$(pwd)" ]; then
    echo "✅ 符号链接配置正确: chatMOSP -> $(basename $(pwd))"
else
    echo "⚠️ 符号链接未配置或配置错误"
    echo "   运行: cd .. && ln -sf $(basename $(pwd)) chatMOSP"
fi

echo "\n5. 示例文件检查:"
if [ -d "examples" ]; then
    count=$(ls examples/*.xyz 2>/dev/null | wc -l)
    echo "✅ 示例目录存在，包含 $count 个XYZ文件"
else
    echo "❌ 示例目录不存在"
fi

echo "\n🎯 验证完成！"
echo "如果所有检查通过✅，MOSP环境已就绪"
echo "运行测试: python kmc_standalone.py --xyz examples/Au-CO.xyz --json examples/Au-COoxidation.json --out-dir OUTPUT/test"
```

保存为`mospsetup-check.sh`并运行：
```bash
chmod +x mospsetup-check.sh
./mospsetup-check.sh
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

## 🔧 故障排除与常见问题

### 🚨 常见错误及解决方案

#### 1. Wine相关错误
**错误**: `it looks like wine32 is missing`
```bash
# 解决方案：安装32位支持
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install wine32:i386
```

**错误**: `The repository 'https://ppa.launchpadcontent.net/wine/wine-builds/ubuntu noble Release' does not have a Release file`
```bash
# 解决方案：移除问题仓库
sudo apt-add-repository -r 'ppa:wine/wine-builds'
sudo apt update
sudo apt install wine
```

#### 2. Python相关错误
**错误**: `ModuleNotFoundError: No module named 'numpy'`
```bash
# 确保在虚拟环境中
source venv/bin/activate
pip install numpy pandas matplotlib scipy imageio
```

#### 3. 权限错误
**错误**: `Permission denied: 'main.exe'`
```bash
chmod +x engine/main.exe
```

#### 4. 路径错误（chatMOSP集成）
**错误**: `FileNotFoundError: No such file or directory: 'chatMOSP/engine/main.exe'`
```bash
# 确保符号链接正确
cd /root/.openclaw/workspace
ls -la | grep chatMOSP  # 应该显示: chatMOSP -> mosp-for-chatMOSP

# 如果不存在或错误
rm -f chatMOSP
ln -sf mosp-for-chatMOSP chatMOSP
```

#### 5. KMC计算错误
**错误**: `Fortran runtime error: Cannot open file 'INPUT/input.txt'`
```bash
# 确保输出目录存在且可写
mkdir -p OUTPUT/test-run

# 确保有正确的输入文件
cp examples/Au-CO.xyz OUTPUT/test-run/
cp examples/Au-COoxidation.json OUTPUT/test-run/
```

### 🧪 快速诊断脚本

```bash
#!/bin/bash
### 🧪 快速诊断脚本（内联版）

可以直接在终端中运行的诊断脚本：

```bash
echo "🔍 MOSP诊断工具"
echo "================""

# 1. 系统信息
echo "\n1. 系统信息:"
echo "OS: $(uname -s) $(uname -r)"
echo "Python: $(python3 --version 2>/dev/null || echo '未安装')"

# 2. Wine检查
echo "\n2. Wine检查:"
if command -v wine > /dev/null; then
    echo "✅ Wine路径: $(which wine)"
    wine --version 2>/dev/null || echo "⚠️ Wine版本未知"
else
    echo "❌ Wine未安装"
fi

# 3. 目录检查
echo "\n3. 目录结构:"
ls -la | grep -E "^(chatMOSP|mosp-for-chatMOSP)"
if [ -L "chatMOSP" ]; then
    echo "✅ 符号链接: chatMOSP -> $(readlink -f chatMOSP)"
else
    echo "⚠️ chatMOSP不是符号链接"
fi

# 4. 引擎检查
echo "\n4. 计算引擎:"
if [ -f "engine/main.exe" ]; then
    echo "✅ main.exe存在"
    file engine/main.exe
    ls -la engine/main.exe
else
    echo "❌ main.exe不存在"
fi

# 5. Python环境
echo "\n5. Python环境:"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    python -c "
import sys
print(f'Python: {sys.version}')
for pkg in ['numpy', 'pandas', 'matplotlib', 'scipy']:
    try:
        __import__(pkg)
        print(f'✅ {pkg}')
    except:
        print(f'❌ {pkg}')
"
deactivate
else
    echo "⚠️ 虚拟环境不存在"
fi

echo "\n🎯 诊断完成！"
```

### 🐛 已知问题与解决方法

#### 问题: KMC计算速度慢
- **原因**: Wine模拟Windows环境有性能开销
- **解决**: 考虑编译Linux原生版本或使用容器

#### 问题: 内存不足
- **原因**: 大规模KMC计算需要大量内存
- **解决**: 减少模拟步数或使用更高配置服务器

#### 问题: 符号链接不工作
- **原因**: 相对路径问题或权限问题
- **解决**: 使用绝对路径创建符号链接
  ```bash
  ln -sf $(pwd) /root/.openclaw/workspace/chatMOSP
  ```

### 📞 支持与反馈

#### 问题报告
如果您遇到问题，请提供：
1. 完整错误信息
2. 操作系统和版本
3. Wine版本（Linux/macOS）
4. Python版本
5. 运行命令和参数

#### 紧急修复
对于紧急问题，可以：
1. 使用Linux模拟器模式（当Wine不可用时）
2. 手动运行计算脚本
3. 检查日志文件 `OUTPUT/*/run.log`

#### 学术合作
如果您希望：
- 扩展新的金属类型
- 添加新的反应机理
- 优化计算算法
- 开发Linux原生版本

请联系课题组寻求合作机会。

### 引用要求
如果在学术成果中使用本软件，请引用相关MOSP论文。

---

## 📋 版本历史

### v1.0.0 (2026-04-23)
- ✅ 修复Wine安装问题（Ubuntu 24.04兼容）
- ✅ 添加符号链接配置指南
- ✅ 完善故障排除文档
- ✅ 集成内联诊断脚本
- ✅ 验证chatMOSP集成

### 未来计划
- 🔄 开发Linux原生编译版本
- 🔄 添加Docker容器支持
- 🔄 优化Wine性能开销
- 🔄 扩展更多催化剂体系

---

**MOSP Research Group** - 致力于催化反应计算的自动化与优化 🧪✨