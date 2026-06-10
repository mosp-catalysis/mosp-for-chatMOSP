#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
author: Sanyang Ye

EKMC 重新绘图工具 (replot-only)

本脚本已从主流程中剥离，仅用于「当一键脚本产出的图像不满意时重新绘图」。
正常的 EKMC 全流程请使用根目录的 generate_ekmc_input.py（读取 JSON -> 生成输入
-> wine 运行 EKMC -> 自动绘图）。

从 EKMC 输出文件中读取数据并生成：
  1. 覆盖度随时间变化图 (coverage.png)
  2. 事件统计图 (events.png)
  3. 原子迁移分析图 (migration.png)
  4. 最终结构可视化（参考 utils/paint.py 风格：大尺寸不透明原子 + 旋转 GIF）
     - structure_element.png / .gif  (按元素着色)
     - structure_cov.png     / .gif  (按 Coverage 着色)
     - structure_cn.png      / .gif  (按 CN 着色)
     - structure_gcn.png     / .gif  (按 GCN 着色)
     结构图/动图本身不带 colorbar，连续着色另外单独生成 *_colorbar.png。

用法:
  python utils/postprocess_ekmc.py <ekmc_output_dir> [--title "标题信息"]

  ekmc_output_dir 即包含 rec_cov.data / rec_event.data / final_stru.xyz 的目录。
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# 复用 paint.py 的渲染辅助（大尺寸不透明原子 + 独立 colorbar）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paint import _auto_marker_size, save_colorbar, save_legend  # noqa: E402


# ============================================================
# 垃圾原子检测与过滤
# ============================================================

def detect_garbage(stru):
    """Detect garbage atoms in final_stru.xyz caused by Fortran uninitialized memory.

    Criteria (coordinate-independent):
      - CN \u2209 [0, 12] (FCC, inclusive bounds)
      - GCN \u2209 [0, 12]
      - cov \u2260 0 or 1 (tolerance \u00b10.1)

    Returns (garbage_indices, count).
    """
    cn = np.asarray(stru['cn'], dtype=float)
    gcn = np.asarray(stru['gcn'], dtype=float)
    cov = np.asarray(stru['cov'], dtype=float)

    bad = np.where(
        (cn < 0) | (cn > 12) |
        (gcn < 0) | (gcn > 12) |
        ((np.abs(cov) > 0.1) & (np.abs(cov - 1) > 0.1))
    )[0]
    return bad, len(bad)


def filter_garbage(stru):
    """Remove garbage atoms. Returns a filtered copy; original is untouched."""
    bad, n = detect_garbage(stru)
    if n == 0:
        return stru
    keep = np.ones(stru['natoms'], dtype=bool)
    keep[bad] = False
    return {
        'natoms': int(keep.sum()),
        'eles': stru['eles'][keep],
        'positions': stru['positions'][keep],
        'cov': stru['cov'][keep] if stru['cov'] is not None else None,
        'cn':  stru['cn'][keep]  if stru['cn']  is not None else None,
        'gcn': stru['gcn'][keep] if stru['gcn'] is not None else None,
    }


def set_plot_style():
    """统一设置 matplotlib 样式"""
    plt.rcParams.update({
        'lines.linewidth': 2,
        'axes.linewidth': 1.5,
        'axes.labelsize': 14,
        'axes.titlesize': 15,
        'legend.fontsize': 12,
        'legend.frameon': False,
        'xtick.labelsize': 12,
        'xtick.major.width': 1.5,
        'ytick.labelsize': 12,
        'ytick.major.width': 1.5,
        'figure.dpi': 150,
        'savefig.dpi': 150,
        'savefig.bbox': 'tight',
    })


FORMATTER = ticker.ScalarFormatter(useMathText=True)
FORMATTER.set_powerlimits((-2, 2))


# ============================================================
# EKMC 输出文件解析
# ============================================================

def read_rec_cov(filepath):
    cov = pd.read_csv(filepath, sep=r'\s+')
    if 'nSurfs' in cov.columns:
        cov = cov.drop('nSurfs', axis=1)
    cov = cov.set_index('Time')
    print(f"  rec_cov.data: {len(cov)} rows, species={list(cov.columns[1:])}")
    return cov


def read_rec_event(filepath):
    event = pd.read_csv(filepath, sep=r'\s+')
    print(f"  rec_event.data: {len(event)} rows, events={list(event.columns[2:])}")
    return event


def read_final_stru(filepath):
    with open(filepath, 'r') as f:
        natoms = int(f.readline().strip())
    df = pd.read_csv(filepath, sep=r'\s+', skiprows=1)
    print(f"  final_stru.xyz: {natoms} atoms, columns={list(df.columns)}")
    return {
        'natoms': natoms,
        'eles': df['ele'].values,
        'positions': df[['x', 'y', 'z']].values,
        'cov': df['cov'].values if 'cov' in df.columns else None,
        'cn': df['cn'].values if 'cn' in df.columns else None,
        'gcn': df['gcn'].values if 'gcn' in df.columns else None,
    }


def read_migration_infos(filepath):
    mig = pd.read_fwf(filepath)
    mig.columns = [c.strip() for c in mig.columns]
    print(f"  migration_infos.data: {len(mig)} migration events")
    return mig


# ============================================================
# 1. 覆盖度图
# ============================================================

def plot_coverage(cov_df, output_path, title=None):
    fig, ax = plt.subplots(figsize=(8, 5))
    species_cols = [c for c in cov_df.columns if c != 'Steps']
    cov_df[species_cols].plot(ax=ax, marker='', linewidth=2)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Coverage')
    ax.set_title(_compose_title('Surface Coverage vs Time', title))
    ax.grid(linestyle='--', alpha=0.5)
    ax.xaxis.set_major_formatter(FORMATTER)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    print(f"  Saved: {output_path}")


# ============================================================
# 2. 事件统计图
# ============================================================

def plot_events(event_df, output_path, title=None):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    event_cols = [c for c in event_df.columns if c not in ('Time', 'Steps')]

    ax = axes[0]
    for col in event_cols:
        ax.plot(event_df['Steps'], event_df[col], label=col, linewidth=2)
    ax.set_xlabel('Steps')
    ax.set_ylabel('Cumulative Count')
    ax.set_title('Event Counts vs Steps')
    ax.legend(fontsize=9)
    ax.grid(linestyle='--', alpha=0.5)
    ax.xaxis.set_major_formatter(FORMATTER)

    ax = axes[1]
    final_counts = event_df[event_cols].iloc[-1].values
    log_counts = np.log10(final_counts + 1)
    colors = plt.cm.Set2(np.linspace(0, 1, len(event_cols)))
    bars = ax.barh(event_cols, log_counts, color=colors, edgecolor='gray', linewidth=0.5)
    ax.set_xlabel('lg(counts + 1)')
    ax.set_title('Final Event Statistics')
    for bar, count in zip(bars, final_counts):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f'{int(count)}', va='center', fontsize=9)

    if title:
        fig.suptitle(title, fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    print(f"  Saved: {output_path}")


# ============================================================
# 3. 原子迁移分析图
# ============================================================

def plot_migration(mig_df, output_path, title=None):
    if len(mig_df) == 0:
        print("  No migration events, skipping migration plot")
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    ax = axes[0, 0]
    ax.hist(mig_df['Ea (eV)'], bins=30, color='steelblue', edgecolor='white', alpha=0.8)
    ax.axvline(mig_df['Ea (eV)'].mean(), color='red', linestyle='--',
               label=f"Mean = {mig_df['Ea (eV)'].mean():.3f} eV")
    ax.set_xlabel('Activation Energy Ea (eV)')
    ax.set_ylabel('Frequency')
    ax.set_title('Migration Barrier Distribution')
    ax.legend(fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    ax = axes[0, 1]
    ax.hist(mig_df['dE (eV)'], bins=30, color='darkorange', edgecolor='white', alpha=0.8)
    ax.axvline(mig_df['dE (eV)'].mean(), color='red', linestyle='--',
               label=f"Mean = {mig_df['dE (eV)'].mean():.3f} eV")
    ax.axvline(0, color='gray', linestyle=':', alpha=0.5)
    ax.set_xlabel('Energy Change dE (eV)')
    ax.set_ylabel('Frequency')
    ax.set_title('Migration Energy Change')
    ax.legend(fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    ax = axes[1, 0]
    ax.scatter(mig_df['cn_before'], mig_df['cn_after'],
               c=mig_df['dE (eV)'], cmap='coolwarm', alpha=0.6,
               edgecolors='gray', linewidth=0.2)
    min_cn = min(mig_df['cn_before'].min(), mig_df['cn_after'].min()) - 0.5
    max_cn = max(mig_df['cn_before'].max(), mig_df['cn_after'].max()) + 0.5
    ax.plot([min_cn, max_cn], [min_cn, max_cn], 'k--', alpha=0.3)
    ax.set_xlabel('CN Before')
    ax.set_ylabel('CN After')
    ax.set_title('CN Change During Migration')
    cbar = plt.colorbar(ax.collections[0], ax=ax)
    cbar.set_label('dE (eV)')

    ax = axes[1, 1]
    ax.scatter(mig_df['gcn_before'], mig_df['gcn_after'],
               c=mig_df['dE (eV)'], cmap='coolwarm', alpha=0.6,
               edgecolors='gray', linewidth=0.2)
    min_gcn = min(mig_df['gcn_before'].min(), mig_df['gcn_after'].min()) - 0.5
    max_gcn = max(mig_df['gcn_before'].max(), mig_df['gcn_after'].max()) + 0.5
    ax.plot([min_gcn, max_gcn], [min_gcn, max_gcn], 'k--', alpha=0.3)
    ax.set_xlabel('GCN Before')
    ax.set_ylabel('GCN After')
    ax.set_title('GCN Change During Migration')
    cbar = plt.colorbar(ax.collections[0], ax=ax)
    cbar.set_label('dE (eV)')

    if title:
        fig.suptitle(title, fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    print(f"  Saved: {output_path}")


# ============================================================
# 4. 最终结构可视化（参考 paint.py：大尺寸不透明原子）
# ============================================================

# 元素配色（来自 paint.py 风格）
ELE_COLORS = {
    'Pt': (0.816, 0.816, 0.878), 'Pd': (0.000, 0.412, 0.522),
    'Cu': (0.784, 0.502, 0.200), 'Au': (0.996, 0.698, 0.2196),
    'Ag': (0.753, 0.753, 0.753), 'Rh': (0.490, 0.502, 0.690),
    'Ni': (0.314, 0.816, 0.314), 'Ir': (0.180, 0.310, 0.310),
    'Fe': (0.878, 0.400, 0.200), 'Co': (0.242, 0.242, 0.242),
    'O': (1.00, 0.051, 0.051), 'C': (0.565, 0.565, 0.565),
    'N': (0.188, 0.314, 0.973), 'H': (1.00, 1.00, 1.00),
    'S': (1.00, 1.00, 0.188),
}

CONTINUOUS_CMAPS = {
    'cn':  {'label': 'CN',       'cmap': plt.cm.viridis},
    'gcn': {'label': 'GCN',      'cmap': plt.cm.plasma},
}

# CN / GCN 固定量程（FCC 体系原子最大配位数 = 12）
FIXED_RANGE_CMAPS = {
    'cn':  {'label': 'CN',  'cmap': plt.cm.viridis, 'vmin': 0, 'vmax': 12},
    'gcn': {'label': 'GCN', 'cmap': plt.cm.plasma,  'vmin': 0, 'vmax': 12},
}

# 覆盖度离散配色：灰 = 未覆盖(0), 红 = 覆盖(1)
COV_DISCRETE = {0: '#d9d9d9', 1: '#e31a1c'}


def _compose_title(base, info):
    """把任务信息附加到标题中。"""
    if info:
        return f"{info}\n{base}"
    return base


def _resolve_colors(stru, color_by):
    """返回 (colors[N,3 or 4], cmap, vmin, vmax, label)。
    cov 用离散双色（灰=0, 红=1），cn/gcn 用固定量程 [0, 12]。"""
    if color_by == 'cov':
        values = np.asarray(stru['cov'], dtype=float)
        colors = np.array([COV_DISCRETE.get(int(round(float(v))), '#000000')
                           for v in values])
        return colors, None, None, None, None
    cfg = FIXED_RANGE_CMAPS[color_by]
    values = np.asarray(stru[color_by], dtype=float)
    vmin, vmax = cfg['vmin'], cfg['vmax']
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    colors = cfg['cmap'](norm(values))
    return colors, cfg['cmap'], vmin, vmax, cfg['label']


def plot_structure(stru, color_by, output_file=None, gif_file=None, title=None):
    """
    参考 paint.py：大尺寸不透明原子 + 按深度排序，清晰呈现团簇外形。
    结构图/动图本身不带 colorbar（连续着色时由调用方单独生成 colorbar 图片）。
    """
    pos = np.asarray(stru['positions'], dtype=float)
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    colors, _, _, _, _ = _resolve_colors(stru, color_by)
    marker_size = _auto_marker_size(stru['natoms'])

    max_range = np.array([x.max() - x.min(), y.max() - y.min(),
                          z.max() - z.min()]).max() / 2.0
    mid_x, mid_y, mid_z = (x.max() + x.min()) * 0.5, (y.max() + y.min()) * 0.5, (z.max() + z.min()) * 0.5

    full_title = _compose_title(f"Structure by {color_by.upper()}", title)

    def _render(ax, azim):
        rad = np.deg2rad(azim)
        depth = x * np.cos(rad) + y * np.sin(rad)
        order = np.argsort(depth)
        ax.scatter(x[order], y[order], z[order], c=colors[order],
                   s=marker_size, edgecolors='k', linewidth=0.4,
                   alpha=1.0, depthshade=False)
        ax.set_xlabel('X (Å)')
        ax.set_ylabel('Y (Å)')
        ax.set_zlabel('Z (Å)')
        ax.set_title(full_title)
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)
        try:
            ax.set_box_aspect((1, 1, 1))
        except Exception:
            pass
        ax.view_init(elev=30, azim=azim)

    if gif_file:
        try:
            import imageio
        except ImportError:
            print("    imageio not installed; skipping GIF")
            return
        frames = []
        for angle in range(0, 360, 10):
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')
            _render(ax, angle)
            fig.canvas.draw()
            img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
            frames.append(img)
            plt.close(fig)
        imageio.mimsave(gif_file, frames, fps=10)
        print(f"    {os.path.basename(gif_file)}")
    else:
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        _render(ax, 30)
        fig.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"    {os.path.basename(output_file)}")


# ============================================================
# 主入口：重新绘图
# ============================================================

def replot(output_dir, img_dir=None, title=None):
    """
    读取已有 EKMC 输出目录中的数据，重新生成全部图像。

    Args:
        output_dir: EKMC 数据目录（含 rec_cov.data 等），用于读取原始数据
        img_dir:    图像输出目录（默认 = output_dir，向后兼容）
        title:      标题信息
    """
    if img_dir is None:
        img_dir = output_dir
    set_plot_style()

    rec_cov_path = os.path.join(output_dir, 'rec_cov.data')
    rec_event_path = os.path.join(output_dir, 'rec_event.data')
    final_stru_path = os.path.join(output_dir, 'final_stru.xyz')
    migration_path = os.path.join(output_dir, 'migration_infos.data')

    for f in [rec_cov_path, rec_event_path, final_stru_path]:
        if not os.path.exists(f):
            print(f"  Missing required file: {f}")
            return False

    print(f"\n{'=' * 60}\nEKMC Replot\n  Dir: {output_dir}\n{'=' * 60}\n")
    print("[1/4] Reading EKMC output files ...")
    cov_df = read_rec_cov(rec_cov_path)
    event_df = read_rec_event(rec_event_path)
    stru = read_final_stru(final_stru_path)
    mig_df = read_migration_infos(migration_path) if os.path.exists(migration_path) else None

    print("\n[2/4] Coverage / Events ...")
    plot_coverage(cov_df, os.path.join(img_dir, 'coverage.png'), title)
    plot_events(event_df, os.path.join(img_dir, 'events.png'), title)

    _, garbage_n = detect_garbage(stru)
    if garbage_n > 0:
        print(f"\n  ⚠ Detected {garbage_n} garbage atoms (anomalous CN/GCN/cov values)")
        print(f"  Cause: EKMC-main.exe writes uninitialized Fortran memory into ini_aligngrid.xyz")
        print(f"  Impact: only affects structure plot colorbar range; coverage/events are unaffected")
        print(f"  Advice: use a grid with dimensions ≥ 3× cluster radius (in \u00c5) to avoid this")
        print(f"  Action: filtered out automatically; plotting with {stru['natoms'] - garbage_n} valid atoms")
        stru = filter_garbage(stru)

    print("\n[3/4] 3D Structure (cov / CN / GCN) ...")
    for color_by in ['cov', 'cn', 'gcn']:
        if color_by != 'cov' and stru[color_by] is None:
            continue
        print(f"  -> {color_by.upper()}")
        plot_structure(stru, color_by,
                       output_file=os.path.join(img_dir, f'structure_{color_by}.png'),
                       title=title)
        plot_structure(stru, color_by,
                       gif_file=os.path.join(img_dir, f'structure_{color_by}.gif'),
                       title=title)

        if color_by == 'cov':
            save_legend(['Bare (0)', 'Covered (1)'],
                        [COV_DISCRETE[0], COV_DISCRETE[1]],
                        os.path.join(img_dir, 'structure_cov_legend.png'),
                        title='Coverage')
        else:
            cfg = FIXED_RANGE_CMAPS[color_by]
            save_colorbar(cfg['cmap'], cfg['vmin'], cfg['vmax'], cfg['label'],
                          os.path.join(img_dir, f'structure_{color_by}_colorbar.png'))

    if mig_df is not None and len(mig_df) > 0:
        print("\n[4/4] Migration Analysis ...")
        plot_migration(mig_df, os.path.join(img_dir, 'migration.png'), title)

    print(f"\n{'=' * 60}\nEKMC replot complete! Files in: {img_dir}/\n{'=' * 60}\n")
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Replot EKMC results from an existing output directory.')
    parser.add_argument('output_dir', nargs='?', default='EKMC-OUTPUT',
                        help='EKMC output directory (contains rec_cov.data etc.)')
    parser.add_argument('--img-dir', default=None,
                        help='Image output directory (default: same as output_dir)')
    parser.add_argument('--title', default=None,
                        help='Extra title info (metal/T/P/pp/size/steps) shown on every figure.')
    args = parser.parse_args()
    ok = replot(args.output_dir, img_dir=args.img_dir, title=args.title)
    sys.exit(0 if ok else 1)
