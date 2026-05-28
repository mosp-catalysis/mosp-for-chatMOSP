#!/bin/bash
# MOSP for chatMOSP — Installation Script
# License: GNU GPL v3
#
# This script handles:
# - System dependency installation (python3-venv, wine64)
# - Python virtual environment creation (bypasses PEP 668)
# - KMC engine verification
# - MOSP tool verification

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect platform
PLATFORM=$(uname)

# Check Python
PYTHON_VERSION=$(python3 --version 2>/dev/null | cut -d' ' -f2)
if [[ -z "$PYTHON_VERSION" ]]; then
    error "Python 3.8+ not found. Please install Python first."
    exit 1
fi
info "Python: $PYTHON_VERSION"

# =====================================================
# Phase 1: System Dependencies
# =====================================================
info "[1/3] Checking system dependencies..."

# Install python3-venv (required for virtual environment creation)
if [[ "$PLATFORM" == "Linux" ]]; then
    # Get distro info
    if command -v apt-get &>/dev/null; then
        MISSING_DEPS=""

        # Check python3-venv (needed for python3 -m venv)
        if ! dpkg -l python3-venv &>/dev/null 2>&1 && ! python3 -m venv --help &>/dev/null 2>&1; then
            MISSING_DEPS="$MISSING_DEPS python3-venv"
        fi

        # Check wine64 (needed for KMC engine)
        WINE_INSTALLED=false
        if command -v wine64 &>/dev/null || command -v wine &>/dev/null; then
            WINE_INSTALLED=true
        fi

        if [ -n "$MISSING_DEPS" ]; then
            info "Installing system dependencies:$MISSING_DEPS"
            sudo apt-get update -qq
            # shellcheck disable=SC2086
            sudo apt-get install -y $MISSING_DEPS
        fi

        # Install Wine if not present
        if [ "$WINE_INSTALLED" = false ]; then
            info "Installing Wine for KMC engine..."
            sudo dpkg --add-architecture i386 2>/dev/null || true
            sudo apt-get install -y wine64 wine32
        fi

        # Verify python3-venv now available
        if ! python3 -m venv --help &>/dev/null 2>&1; then
            error "python3-venv installation failed or python3 -m venv unavailable."
            exit 1
        fi
    elif command -v brew &>/dev/null; then
        # macOS via Homebrew — skip python3-venv (brew manages it), install wine
        if ! command -v wine &>/dev/null && ! command -v wine64 &>/dev/null; then
            info "Installing Wine via Homebrew..."
            brew install wine
        fi
    fi
fi

# =====================================================
# Phase 2: Python Virtual Environment
# =====================================================
info "[2/3] Setting up Python virtual environment..."

VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    info "Virtual environment created at ./$VENV_DIR"
else
    info "Virtual environment already exists at ./$VENV_DIR"
fi

# Activate venv (source inside script for subprocess)
source "$VENV_DIR/bin/activate"

# Upgrade pip first
pip install --upgrade pip -q

# Install Python dependencies
pip install -r requirements.txt -q

# =====================================================
# Phase 3: Verify Installation
# =====================================================
info "[3/3] Verifying installation..."

# Verify engine
ENGINE_PATH="engine/main.exe"
if [ -f "$ENGINE_PATH" ]; then
    chmod +x "$ENGINE_PATH"
    info "KMC engine: OK ($ENGINE_PATH)"

    # Test Wine with engine (optional, non-fatal)
    if command -v wine64 &>/dev/null; then
        if wine64 "$ENGINE_PATH" --help 2>&1 | head -1 &>/dev/null; then
            info "KMC engine runs via Wine64: OK"
        elif command -v wine &>/dev/null; then
            if wine "$ENGINE_PATH" --help 2>&1 | head -1 &>/dev/null; then
                info "KMC engine runs via Wine: OK"
            fi
        else
            warn "Wine not found — KMC engine will not run. Install wine64/wine32 to enable KMC."
        fi
    else
        # Double-check both wine64 and wine
        if command -v wine &>/dev/null; then
            if wine "$ENGINE_PATH" --help 2>&1 | head -1 &>/dev/null; then
                info "KMC engine runs via Wine: OK"
            fi
        else
            warn "Wine not found — KMC engine will not run. Install wine64/wine32 to enable KMC."
        fi
    fi
else
    error "$ENGINE_PATH not found"
    exit 1
fi

# Verify utilities
for tool in utils/msr.py utils/paint.py utils/plot_kmc_data.py kmc_standalone.py; do
    if [ -f "$tool" ]; then
        info "  Tool OK: $tool"
    else
        warn "  Tool MISSING: $tool"
    fi
done

# Verify MOSP_database
if [ -d "MOSP_database" ]; then
    DB_COUNT=$(find MOSP_database -name "*.json" | wc -l)
    info "MOSP_database: $DB_COUNT parameter files"
else
    warn "MOSP_database/ not found"
fi

mkdir -p OUTPUT 2>/dev/null || true

# Deactivate venv (restore original environment)
deactivate 2>/dev/null || true

echo ""
echo "========================================"
echo "✅ Installation complete!"
echo "========================================"
echo ""
echo "Quick start (activate venv first):"
echo "  source $VENV_DIR/bin/activate"
echo "  python kmc_standalone.py --xyz MOSP_database/Au-CO.xyz \\"
echo "    --json MOSP_database/Au-COoxidation.json \\"
echo "    --out-dir test_run"
echo ""
echo "License: GNU GPL v3 — see LICENSE file"
echo "Citation: Ying L, Zhu B,* Gao Y,* J. Chem. Phys. 2024, 161, 114702"
echo ""

exit 0
