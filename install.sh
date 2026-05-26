#!/bin/bash
# MOSP for chatMOSP — Installation Script
# License: GNU GPL v3

set -e

echo "========================================"
echo "MOSP for chatMOSP — Installation"
echo "========================================"

# Check Python
PYTHON_VERSION=$(python3 --version 2>/dev/null | cut -d' ' -f2)
if [[ -z "$PYTHON_VERSION" ]]; then
    echo "ERROR: Python 3.8+ not found. Please install Python first."
    exit 1
fi
echo "Python: $PYTHON_VERSION"

# Check platform & Wine
PLATFORM=$(uname)
if [[ "$PLATFORM" == "Linux" ]] || [[ "$PLATFORM" == "Darwin" ]]; then
    if ! command -v wine &> /dev/null; then
        echo "WARNING: Wine not found. KMC requires Wine on Linux/macOS."
        echo "  Install: sudo apt install wine (Ubuntu) or brew install wine (macOS)"
    else
        echo "Wine: $(wine --version 2>/dev/null || echo 'detected')"
    fi
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt || pip3 install -r requirements.txt

# Verify engine
if [ -f "engine/main.exe" ]; then
    echo "KMC engine: OK (engine/main.exe)"
else
    echo "ERROR: engine/main.exe not found"
    exit 1
fi

# Verify utilities
for tool in utils/msr.py utils/paint.py utils/plot_kmc_data.py kmc_standalone.py; do
    if [ -f "$tool" ]; then
        echo "  OK: $tool"
    else
        echo "  MISSING: $tool"
    fi
done

# Verify MOSP_database
if [ -d "MOSP_database" ]; then
    DB_COUNT=$(find MOSP_database -name "*.json" | wc -l)
    echo "MOSP_database: $DB_COUNT parameter files"
else
    echo "WARNING: MOSP_database/ not found"
fi

mkdir -p OUTPUT 2>/dev/null || true

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "Quick start:"
echo "  python kmc_standalone.py --xyz MOSP_database/Au-CO.xyz --json MOSP_database/Au-COoxidation.json --out-dir test_run"
echo ""
echo "License: GNU GPL v3 — see LICENSE file"
echo "Citation: Ying L, Zhu B,* Gao Y,* J. Chem. Phys. 2024, 161, 114702"
echo ""

exit 0
