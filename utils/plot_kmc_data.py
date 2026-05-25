#!/usr/bin/env python3
"""
KMC Plotting Script (Extracted from kmc_standalone.py)
Reads existing KMC output files and generates coverage and TOF plots
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import ticker


# Set global font size (double the default ~10pt to 20pt)
plt.rcParams.update({
    'font.size': 20,
    'axes.labelsize': 20,
    'axes.titlesize': 20,
    'xtick.labelsize': 20,
    'ytick.labelsize': 20,
    'legend.fontsize': 20,
})


# Formatter for axis labels
FORMATTER = ticker.ScalarFormatter(useMathText=True)
FORMATTER.set_powerlimits((-2, 2))


def fail(message: str) -> "NoReturn":
    """Print error message and exit with code 1"""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def read_kmc_info(kmc_dir: Path) -> Dict[str, str]:
    """
    从KMC任务目录读取温度、压强、气体种类、金属种类信息
    
    Args:
        kmc_dir: KMC任务目录路径
    
    Returns:
        字典，包含temperature, pressure, gases, metal
    """
    input_file = kmc_dir / "INPUT" / "input.txt"
    species_file = kmc_dir / "INPUT" / "species.txt"
    xyz_file = kmc_dir / "INPUT" / "ini.xyz"
    
    info = {}
    
    # 读取温度和压强
    if input_file.exists():
        with open(input_file, 'r') as f:
            lines = f.readlines()
            if len(lines) >= 2:
                info['temperature'] = lines[0].split()[0]  # 第1行，第1列
                info['pressure'] = lines[1].split()[0]     # 第2行，第1列
    
    # 读取气体种类
    if species_file.exists():
        gases = []
        with open(species_file, 'r') as f:
            for line in f:
                if line.strip().startswith("Name:"):
                    gas_name = line.split()[1]
                    gases.append(gas_name)
        info['gases'] = " + ".join(gases) if gases else ""
    
    # 读取金属种类
    if xyz_file.exists():
        with open(xyz_file, 'r') as f:
            lines = f.readlines()
            if len(lines) >= 3:
                # 第3行，第1列（第1行是原子数，第2行是空行或注释）
                info['metal'] = lines[2].split()[0]
    
    return info


def require_output_files(output_dir: Path) -> Dict[str, Path]:
    """Require KMC output files to exist"""
    files = {
        "cov": output_dir / "rec_cov.data",
        "event": output_dir / "rec_event.data",
        "site": output_dir / "rec_site_spc.data",
    }
    for name, path in files.items():
        if not path.exists():
            fail(f"{name} output file not found: {path}")
    return files


def load_outputs(output_dir: Path) -> Dict[str, object]:
    """Load KMC output files (rec_cov.data, rec_event.data, rec_site_spc.data)"""
    files = require_output_files(output_dir)
    
    # Read coverage data
    cov = pd.read_csv(files["cov"], sep=r"\s+")
    
    # Read event data
    event = pd.read_csv(files["event"], sep=r"\s+").set_index("Steps")
    
    # Read site data and extract metadata
    with files["site"].open("r", encoding="utf-8") as handle:
        natoms = int(handle.readline().strip())
        nsurf = int(handle.readline().strip())
        total_time = float(handle.readline().strip())
    
    site = pd.read_csv(files["site"], sep=r"\s+", skiprows=3)
    if site.empty:
        fail(f"site output is empty: {files['site']}")
    
    return {
        "cov": cov,
        "event": event,
        "site": site,
        "natoms": natoms,
        "nsurf": nsurf,
        "total_time": total_time,
    }


@dataclass
class ProductInfo:
    """Product information for TOF calculation"""
    name: str
    event_gen_names: List[str] = field(default_factory=list)  # Event names that generate this product
    event_consum_names: List[str] = field(default_factory=list)  # Event names that consume this product


def compute_tof_tables(
    event_df: pd.DataFrame,
    site_df: pd.DataFrame,
    total_time: float,
    nsurf: int,
    products: Sequence[ProductInfo] = None,
    gap: int = 10,
) -> Dict[str, pd.DataFrame]:
    """
    Compute TOF (Turnover Frequency) tables from event data
    
    Args:
        event_df: Event count dataframe from rec_event.data
        site_df: Site dataframe from rec_site_spc.data
        total_time: Total simulation time
        nsurf: Number of surface sites
        products: List of product definitions (if None, auto-detect from event columns)
        gap: Sampling interval for TOF calculation
    
    Returns:
        Dictionary with 'tof' and 'site_tof' dataframes
    """
    if nsurf <= 0:
        fail("surface site count in rec_site_spc.data must be positive")
    if total_time <= 0:
        fail("total time in rec_site_spc.data must be positive")
    
    # If products not specified, auto-detect reaction events
    # Assume the last event column is the main reaction (e.g., CO+O)
    if products is None:
        # Exclude Time and Steps columns to get event names only
        event_names = [col for col in event_df.columns if col not in {"Time", "Steps"}]
        if not event_names:
            fail("No event columns found in rec_event.data")
        
        # Try to identify reaction event (usually named like "CO+O", "Reaction1", etc.)
        reaction_name = None
        for name in event_names:
            if "+" in name or "Reaction" in name.lower():
                reaction_name = name
                break
        
        if reaction_name is None:
            # Use the last event column as reaction
            reaction_name = event_names[-1]
        
        # Create product info using event names (not indices)
        products = [ProductInfo(name=reaction_name, event_gen_names=[reaction_name])]
    
    # Calculate turnover number (TON) for each product
    ton = event_df[["Time"]].copy()
    ton_site = site_df[["cn"]].copy()
    
    for product in products:
        ton[product.name] = 0
        ton_site[product.name] = 0
        
        # Use event names directly to index columns
        for event_name in product.event_gen_names:
            if event_name not in event_df.columns:
                fail(f"product {product.name} references event '{event_name}' not found in rec_event.data")
            ton[product.name] += event_df[event_name]
            
            # For site_df, map event name to site column
            # Site columns follow the same order as events, but start at column 5 (after x,y,z,cn,status)
            event_idx = list(event_df.columns).index(event_name)
            site_col_idx = event_idx - 1 + 5  # Adjust for site_df structure (no Steps column)
            if site_col_idx >= len(site_df.columns):
                fail(f"product {product.name} references event '{event_name}' outside rec_site_spc.data")
            ton_site[product.name] += site_df.iloc[:, site_col_idx]
        
        for event_name in product.event_consum_names:
            if event_name not in event_df.columns:
                fail(f"product {product.name} references event '{event_name}' not found in rec_event.data")
            ton[product.name] -= event_df[event_name]
            
            event_idx = list(event_df.columns).index(event_name)
            site_col_idx = event_idx - 1 + 5
            if site_col_idx >= len(site_df.columns):
                fail(f"product {product.name} references event '{event_name}' outside rec_site_spc.data")
            ton_site[product.name] -= site_df.iloc[:, site_col_idx]
    
    # Sample data at intervals
    interval = max(len(event_df) // gap, 1)
    sub_ton = ton.iloc[::interval].copy()
    diff_ton = sub_ton.diff().iloc[1:].copy()
    
    # Calculate TOF: dTON / dt / nsurf
    # Prepare TOF dataframe with absolute time
    tof = pd.DataFrame()
    tof["Time"] = diff_ton["Time"]  # 时间间隔（用于TOF计算）
    tof["AbsTime"] = sub_ton["Time"].iloc[1:]  # 绝对时间（用于绘图，跳过第一个0）
    tof["Steps"] = sub_ton.index[1:].astype(int)  # 步数（跳过第一个0）
    
    for product in products:
        tof[product.name] = diff_ton[product.name] / diff_ton["Time"] / nsurf
    
    # 重新排列列顺序
    tof = tof[["Steps", "Time", "AbsTime"] + [p.name for p in products]]
    
    # Calculate site-specific TOF
    site_tof = site_df[["x", "y", "z", "cov", "cn", "gcn"]].copy()
    for product in products:
        site_tof[product.name] = ton_site[product.name] / total_time
    
    # Prepare TON export
    ton_export = diff_ton.copy()
    ton_export.insert(0, "Steps", diff_ton.index.astype(int))
    
    return {
        "ton": ton_export,
        "tof": tof,
        "site_tof": site_tof,
    }


def plot_coverage(cov_df: pd.DataFrame, output_path: Path, kmc_info: Dict[str, str] = None) -> None:
    """Plot coverage evolution over time"""
    species_columns = [column for column in cov_df.columns if column not in {"Time", "Steps"}]
    if not species_columns:
        fail("rec_cov.data does not contain coverage columns")
    
    fig, ax = plt.subplots(figsize=(8, 5))
    for column in species_columns:
        ax.plot(cov_df["Time"], cov_df[column], label=column)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Coverage")
    
    # 添加标题
    if kmc_info:
        title = f"{kmc_info.get('metal', '')} {kmc_info.get('gases', '')} {kmc_info.get('temperature', '')}K {kmc_info.get('pressure', '')}Pa"
        ax.set_title(title, fontsize=16)
    
    ax.grid(linestyle="--")
    ax.xaxis.set_major_formatter(FORMATTER)
    y_max = ax.get_ylim()[1]
    ax.set_ylim(bottom=0, top=y_max * 1.15)
    ax.set_xlim(left=0)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def plot_tof(tof_df: pd.DataFrame, output_path: Path, kmc_info: Dict[str, str] = None) -> None:
    """Plot TOF (Turnover Frequency) evolution"""
    product_columns = [column for column in tof_df.columns if column not in {"Steps", "Time", "AbsTime"}]
    if not product_columns:
        fail("TOF table does not contain product columns")
    
    fig, ax = plt.subplots(figsize=(8, 5))
    for column in product_columns:
        ax.plot(
            tof_df["Steps"],
            tof_df[column],
            marker="o",
            markersize=4,
            markerfacecolor="#FFF5E3",
            label=column,
        )
    ax.set_xlabel("Steps")
    ax.set_ylabel("TOF (1/s/site)")
    
    # 添加标题
    if kmc_info:
        title = f"{kmc_info.get('metal', '')} {kmc_info.get('gases', '')} {kmc_info.get('temperature', '')}K {kmc_info.get('pressure', '')}Pa"
        ax.set_title(title, fontsize=16)
    
    ax.grid(linestyle="--")
    ax.yaxis.set_major_formatter(FORMATTER)
    y_max = ax.get_ylim()[1]
    ax.set_ylim(bottom=0, top=y_max * 1.15)
    ax.set_xlim(left=0)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def plot_tof_time(tof_df: pd.DataFrame, output_path: Path, kmc_info: Dict[str, str] = None) -> None:
    """Plot TOF evolution over time"""
    product_columns = [column for column in tof_df.columns if column not in {"Steps", "Time", "AbsTime"}]
    if not product_columns:
        fail("TOF table does not contain product columns")

    fig, ax = plt.subplots(figsize=(8, 5))
    for column in product_columns:
        ax.plot(
            tof_df["AbsTime"],
            tof_df[column],
            marker="o",
            markersize=4,
            markerfacecolor="#FFF5E3",
            label=column,
        )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("TOF (1/s/site)")

    # 添加标题
    if kmc_info:
        title = f"{kmc_info.get('metal', '')} {kmc_info.get('gases', '')} {kmc_info.get('temperature', '')}K {kmc_info.get('pressure', '')}Pa"
        ax.set_title(title, fontsize=16)

    ax.grid(linestyle="--")
    # 为y轴创建独立formatter，避免与x轴共享状态导致科学计数法失效
    y_formatter = ticker.ScalarFormatter(useMathText=True)
    y_formatter.set_powerlimits((-2, 2))
    ax.yaxis.set_major_formatter(y_formatter)
    ax.set_xlim(left=0)
    y_max = ax.get_ylim()[1]
    ax.set_ylim(bottom=0, top=y_max * 1.15)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
def plot_coverage_steps(cov_df: pd.DataFrame, output_path: Path, kmc_info: Dict[str, str] = None) -> None:
    """Plot coverage evolution over steps"""
    species_columns = [column for column in cov_df.columns if column not in {"Time", "Steps"}]
    if not species_columns:
        fail("rec_cov.data does not contain coverage columns")
    
    fig, ax = plt.subplots(figsize=(8, 5))
    for column in species_columns:
        ax.plot(cov_df["Steps"], cov_df[column], label=column)
    ax.set_xlabel("Steps")
    ax.set_ylabel("Coverage")
    
    # 添加标题
    if kmc_info:
        title = f"{kmc_info.get('metal', '')} {kmc_info.get('gases', '')} {kmc_info.get('temperature', '')}K {kmc_info.get('pressure', '')}Pa"
        ax.set_title(title, fontsize=16)
    
    ax.grid(linestyle="--")
    ax.xaxis.set_major_formatter(FORMATTER)
    y_max = ax.get_ylim()[1]
    ax.set_ylim(bottom=0, top=y_max * 1.15)
    ax.set_xlim(left=0)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write dataframe to CSV file"""
    df.to_csv(path, index=False)


def main() -> int:
    """Main function to generate plots from existing KMC output files"""
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1]).resolve()
    else:
        # Default to the example directory
        output_dir = Path("/root/.openclaw/workspace/mosp-for-chatMOSP/OUTPUT/Pt_CO66_O33_850K_150Pa_R40/KMC_20000000steps/OUTPUT")
    
    # Determine plot output directory (parent of output_dir, i.e., KMC task directory)
    plot_dir = output_dir.parent
    
    print(f"\nProcessing KMC data from: {output_dir}")
    print(f"Plots will be saved to: {plot_dir}")
    
    # Load output files
    print("Loading output files...")
    outputs = load_outputs(output_dir)
    print(f"  Loaded coverage data: {len(outputs['cov'])} points")
    print(f"  Loaded event data: {len(outputs['event'])} points")
    print(f"  Surface sites: {outputs['nsurf']}")
    print(f"  Total time: {outputs['total_time']:.4e} s")
    
    # Compute TOF tables
    print("\nComputing TOF tables...")
    tables = compute_tof_tables(
        outputs["event"],
        outputs["site"],
        outputs["total_time"],
        outputs["nsurf"],
    )
    
    # Write CSV files
    print("\nWriting CSV files...")
    write_csv(outputs["cov"], output_dir / "coverage.csv")
    write_csv(tables["tof"], output_dir / "tof.csv")
    write_csv(tables["site_tof"], output_dir / "site_tof.csv")
    print(f"  Coverage CSV: {output_dir / 'coverage.csv'}")
    print(f"  TOF CSV: {output_dir / 'tof.csv'}")
    print(f"  Site TOF CSV: {output_dir / 'site_tof.csv'}")
    
    # Read KMC info for plot titles
    print("\nReading KMC info...")
    kmc_info = read_kmc_info(plot_dir)
    if kmc_info:
        print(f"  Metal: {kmc_info.get('metal', 'N/A')}")
        print(f"  Gases: {kmc_info.get('gases', 'N/A')}")
        print(f"  Temperature: {kmc_info.get('temperature', 'N/A')} K")
        print(f"  Pressure: {kmc_info.get('pressure', 'N/A')} Pa")
    
    # Generate plots (save to KMC task directory, not OUTPUT/)
    print("\nGenerating plots...")
    plot_coverage(outputs["cov"], plot_dir / "coverage.png", kmc_info)
    plot_tof(tables["tof"], plot_dir / "tof.png", kmc_info)
    print(f"  Coverage plot: {plot_dir / 'coverage.png'}")
    print(f"  TOF plot: {plot_dir / 'tof.png'}")
    
    # Generate additional plots
    plot_coverage_steps(outputs["cov"], plot_dir / "coverage_steps.png", kmc_info)
    plot_tof_time(tables["tof"], plot_dir / "tof_time.png", kmc_info)
    print(f"  Coverage (Steps) plot: {plot_dir / 'coverage_steps.png'}")
    print(f"  TOF (Time) plot: {plot_dir / 'tof_time.png'}")
    
    # Print TOF statistics
    print("\n=== TOF Statistics ===")
    product_columns = [col for col in tables["tof"].columns if col not in {"Steps", "Time", "AbsTime"}]
    for product in product_columns:
        tof_values = tables["tof"][product]
        print(f"\n{product}:")
        print(f"  Average TOF: {tof_values.mean():.4e} 1/s/site")
        print(f"  TOF std dev: {tof_values.std():.4e} 1/s/site")
        print(f"  Final TOF: {tof_values.iloc[-1]:.4e} 1/s/site")
        print(f"  Total events: {tables['ton'][product].sum():.0f}")
    
    print("\n✅ All plots and CSV files generated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
