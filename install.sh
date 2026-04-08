#!/bin/bash

# MOSP软件安装脚本
# 版本: 1.0.0

set -e

echo "========================================"
echo "MOSP软件安装程序"
echo "========================================"

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>/dev/null | cut -d' ' -f2)
if [[ -z "$PYTHON_VERSION" ]]; then
    echo "❌ 错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

echo "✅ 检测到Python版本: $PYTHON_VERSION"

# 检查平台
PLATFORM=$(uname)
echo "📱 操作系统: $PLATFORM"

# 检查Wine（Linux/macOS需要）
if [[ "$PLATFORM" == "Linux" ]] || [[ "$PLATFORM" == "Darwin" ]]; then
    if ! command -v wine &> /dev/null; then
        echo "⚠️  警告: 未找到Wine，Linux/macOS需要Wine来运行Windows可执行文件"
        echo "    Linux (Ubuntu/Debian)安装命令: sudo apt install wine"
        echo "    macOS (Homebrew)安装命令: brew install wine"
        echo ""
        echo "⏸️  继续安装Python依赖，但KMC计算需要Wine才能运行"
        read -p "是否继续安装Python依赖？(y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "安装中止"
            exit 1
        fi
    else
        echo "✅ 检测到Wine: $(wine --version)"
    fi
fi

# 安装Python依赖
echo "📦 正在安装Python依赖..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Python依赖安装成功"
else
    echo "❌ Python依赖安装失败"
    echo "   尝试使用: pip3 install -r requirements.txt"
    exit 1
fi

# 验证引擎文件
echo "🔍 验证引擎文件..."
if [ -f "engine/main.exe" ]; then
    echo "✅ 检测到KMC引擎: engine/main.exe"
    
    # 检查DLL文件
    DLL_COUNT=$(ls engine/*.dll 2>/dev/null | wc -l)
    if [ $DLL_COUNT -ge 4 ]; then
        echo "✅ 检测到 $DLL_COUNT 个依赖库文件"
    else
        echo "⚠️  警告: 可能缺少一些DLL文件"
    fi
else
    echo "❌ 错误: 未找到KMC引擎文件 engine/main.exe"
    echo "   当前目录: $(pwd)"
    echo "   引擎路径: engine/main.exe"
    echo "   请确保文件结构正确"
    exit 1
fi

# 验证示例文件
echo "📁 验证示例文件..."
if [ -d "examples" ]; then
    EXAMPLE_COUNT=$(find examples -name "*.xyz" -o -name "*.json" | wc -l)
    if [ $EXAMPLE_COUNT -ge 4 ]; then
        echo "✅ 检测到 $EXAMPLE_COUNT 个示例文件"
    else
        echo "⚠️  警告: 示例文件较少"
    fi
elif [ -d "example" ]; then
    # 兼容旧版本
    EXAMPLE_COUNT=$(find example -name "*.xyz" -o -name "*.json" | wc -l)
    if [ $EXAMPLE_COUNT -ge 4 ]; then
        echo "✅ 检测到 $EXAMPLE_COUNT 个示例文件 (在example目录中)"
    else
        echo "⚠️  警告: 示例文件较少"
    fi
else
    echo "⚠️  警告: 未找到examples或example目录"
    echo "   将创建examples目录"
    mkdir -p examples
fi

# 验证工具脚本
echo "🔧 验证工具脚本..."
TOOLS=("utils/msr.py" "utils/paint.py" "kmc_standalone.py")
ALL_TOOLS_OK=true

for tool in "${TOOLS[@]}"; do
    if [ -f "$tool" ]; then
        echo "  ✅ $tool"
    else
        echo "  ❌ 缺失: $tool"
        ALL_TOOLS_OK=false
    fi
done

if [ "$ALL_TOOLS_OK" = false ]; then
    echo "❌ 错误: 缺少必要的工具脚本"
    echo "   当前目录: $(pwd)"
    echo "   请确保文件结构正确"
    exit 1
fi

# 创建输出目录
mkdir -p OUTPUT 2>/dev/null || true

# 运行简单测试
echo "🧪 运行简单测试..."
if python3 -c "import numpy, pandas, matplotlib, scipy; print('✅ Python库测试通过')" 2>/dev/null; then
    echo "✅ Python环境测试通过"
else
    echo "⚠️  Python环境测试警告"
fi

# 生成使用说明
echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "🎉 MOSP软件已成功安装"
echo ""
echo "📖 使用说明:"
echo "1. 基本KMC模拟:"
echo "   python kmc_standalone.py --xyz examples/Au-CO.xyz --json examples/Au-COoxidation.json --out-dir test_run"
echo ""
echo "2. MSR计算:"
echo "   python utils/msr.py --help"
echo ""
echo "3. 可视化工具:"
echo "   python utils/paint.py --help"
echo ""
echo "4. 更多示例:"
echo "   查看 examples/ 目录"
echo ""
echo "🔗 与OpenClaw技能集成:"
echo "   如需与OpenClaw技能集成，请安装 mosp-openclaw-skills"
echo ""
echo "📄 许可证信息:"
echo "   本软件使用学术非商业许可证，详见 LICENSE.txt"
echo "   请遵守许可证条款，特别是引用要求"
echo ""
echo "💡 提示:"
echo "   - 首次运行可能需要一些时间加载库文件"
echo "   - 输出文件保存在 OUTPUT/ 目录"
echo "   - 如有问题，请查看README.md中的故障排除部分"
echo ""
echo "========================================"

exit 0