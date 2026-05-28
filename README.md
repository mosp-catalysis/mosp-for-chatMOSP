# MOSP for chatMOSP

MOSP (Multiscale Operando Simulation Package) for chatMOSP — a catalytic reaction computation platform optimized for the chatMOSP conversational interface, specializing in metal nanoparticle structure generation (MSR) and kinetic Monte Carlo simulation (KMC).

## Features

### 1. Nanoparticle Structure Generation (MSR)
- Generate metal nanoclusters (Pt, Au, Cu, Pd, Fe, etc.)
- Support different symmetries and sizes via Wulff construction
- Output standard XYZ format files

### 2. Kinetic Monte Carlo Simulation (KMC)
- Surface reaction kinetics simulation
- Support CO oxidation, water-gas shift reaction, etc.
- Compute TOF (turnover frequency) and surface coverage

### 3. Visualization Tools
- Generate nanoparticle structure images (static + rotation GIF)
- Reaction kinetics visualization
- Data analysis and plotting

## System Requirements & Installation

### Prerequisites
- **Python 3.8+**
- **Windows/Linux/macOS**
- **4 GB RAM minimum**, 8 GB+ recommended for large-scale calculations
- **10 GB disk space** for computation results

### Windows Users (Simplest)
- Run `engine/main.exe` directly — no additional configuration needed

### Linux Users (Wine Required)

```bash
# Install Wine (required)
sudo apt update && sudo apt install wine

# Verify
wine --version

# Make engine executable
chmod +x engine/main.exe

# Test
wine engine/main.exe --help 2>&1 | head -5
```

### macOS Users (Wine Required)

```bash
brew install wine
```

### Python Environment (All Platforms)

**⚠️ Ubuntu/Debian users (Python 3.12+):** pip is blocked by PEP 668 from installing system-wide.
Use a virtual environment — the installer will do this automatically, or manually:

```bash
# Install python3-venv (required for virtual environment)
sudo apt-get install -y python3-venv

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate   # Linux/macOS

# Install dependencies (inside venv, PEP 668 does not apply)
pip install -r requirements.txt
```

**Or run the installer which handles everything automatically:**

```bash
bash install.sh
source venv/bin/activate   # activate after installation
```

### chatMOSP Integration

```bash
# Create symlink for chatMOSP skills
cd /root/.openclaw/workspace
ln -sf mosp-for-chatMOSP chatMOSP
```

## Quick Start

```bash
# KMC simulation with example files
python kmc_standalone.py \
  --xyz MOSP_database/Au-CO.xyz \
  --json MOSP_database/Au-COoxidation.json \
  --out-dir my_first_run

# MSR structure generation
python3 utils/msr.py input.json OUTPUT_DIR/

# Visualization
python3 utils/paint.py cluster.xyz --output structure.png
python3 utils/paint.py cluster.xyz --gif rotation.gif
```

## Directory Structure

```
mosp-for-chatMOSP/
├── engine/                 # Computation engine (Windows executables)
│   ├── main.exe            # KMC engine
│   └── *.dll               # Dependencies
├── MOSP_database/          # Parameter database (JSON + XYZ files)
├── utils/                  # Python utility scripts
│   ├── msr.py              # MSR structure generator
│   ├── paint.py            # Visualization (static + rotation GIF)
│   └── plot_kmc_data.py    # KMC result plotting
├── kmc_standalone.py       # KMC entry script
├── requirements.txt        # Python dependencies
├── install.sh              # Installation script
└── LICENSE                 # GNU GPL v3
```

## Supported Metals & Reactions

### Metals
Pt, Au, Cu, Pd, Fe, PdCu, and extensible via MOSP_database

### Reactions
- **CO oxidation**: CO + ½O₂ → CO₂
- **Water-gas shift reaction**: CO + H₂O → CO₂ + H₂
- **H₂ dissociation**: H₂ → 2H
- Custom reactions via JSON parameter files

## chatMOSP Integration

This version of MOSP is specifically optimized for the [chatMOSP](https://github.com/mosp-catalysis/chatMOSP) conversational interface. See that repository for natural-language control skills.

## Citation

If you use this software in academic work, please cite:

Ying L, Zhu B,* Gao Y,* "MOSP: A user-interface package for simulating metal nanoparticle's structure and reactivity under operando conditions." *J. Chem. Phys.* **2024**, *161*, 114702. [DOI: 10.1063/5.0226023](https://doi.org/10.1063/5.0226023)

## License

This software is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

This is a derivative work of [MOSP](https://github.com/MOSP-catalysis/MOSP) by Yi Gao's Group, also licensed under GPL v3.

## Contact

**Yi Gao's Group** — [https://www.x-mol.com/groups/gao_yi](https://www.x-mol.com/groups/gao_yi)
