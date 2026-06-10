#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
author: Sanyang Ye
读取包含位点类型的 XYZ 文件，绘制三维原子结构图
支持静态显示或生成旋转 GIF 动画
用法:
    python paint.py <xyz文件> [--output <静态图文件>] [--gif <动画文件>] [--color-by <element|site_type>]
"""

import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# ---------------------------- 颜色映射（来自第二个片段） ----------------------------
ELE_COLORS = {
    'H': (1.00, 1.00, 1.00),
    'He': (0.80, 0.80, 0.80),
    'Li': (0.851, 1.00, 1.00),
    'Be': (0.761, 1.0, 1.00),
    'B': (1.00, 0.71, 0.71),
    'C': (0.565, 0.565, 0.565),
    'N': (0.188, 0.314, 0.973),
    'O': (1.00, 0.051, 0.051),
    'F': (0.565, 0.878, 0.314),
    'Na': (0.671, 0.361, 0.949),
    'Mg': (0.541, 1.00, 0.00),
    'Al': (0.749, 0.651, 0.651),
    'Si': (0.941, 0.784, 0.627),
    'P': (1.00, 0.502, 0.00),
    'S': (1.00, 1.00, 0.188),
    'Fe': (0.878, 0.400, 0.200),
    'Co': (0.242, 0.242, 0.242),
    'Ni': (0.314, 0.816, 0.314),
    'Cu': (0.784, 0.502, 0.200),
    'Zn': (0.490, 0.502, 0.690),
    'Pd': (0.000, 0.412, 0.522),
    'Ag': (0.753, 0.753, 0.753),
    'Ce': (1.00, 1.00, 0.78),
    'Pt': (0.816, 0.816, 0.878),
    'Au': (0.996, 0.698, 0.2196),
}

TYPE_COLORS = {
    '100': (0.557, 0.714, 0.611),
    '110': (0.851, 0.310, 0.200),
    '111': (0.565, 0.745, 0.878),
    'edge': (0.816, 0.816, 0.878),
    'corner': (0.933, 0.749, 0.427),
    'subsurface': (1.00, 0.78, 0.78),
    'bulk': (0.008, 0.188, 0.200)
}

def get_ele_color(element):
    """返回元素的 RGB 颜色（0-1 范围）"""
    return ELE_COLORS.get(element, (0.816, 0.816, 0.878))

def get_type_color(type_str):
    """返回位点类型的 RGB 颜色"""
    return TYPE_COLORS.get(type_str, (0.816, 0.816, 0.878))


# ---------------------------- NanoParticle 类（简化版） ----------------------------
class NanoParticle:
    def __init__(self, eles, positions, siteTypes=None):
        self.eles = np.array(eles)
        self.positions = np.array(positions)
        self.siteTypes = np.array(siteTypes) if siteTypes is not None else None
        self.colors = np.zeros((len(self.eles), 3))
        self.nAtoms = len(self.eles)

    def setColors(self, coltype):
        """根据 coltype 设置颜色矩阵"""
        self.coltype = coltype
        if coltype == 'element':
            for i, ele in enumerate(self.eles):
                self.colors[i] = get_ele_color(ele)
        elif coltype == 'site_type':
            if self.siteTypes is None:
                raise ValueError("No site types provided.")
            for i, typ in enumerate(self.siteTypes):
                self.colors[i] = get_type_color(typ.strip())
        else:
            raise ValueError(f"Unknown color type: {coltype}")


# ---------------------------- XYZ 文件读取（支持第四列位点类型） ----------------------------
def read_xyz(file_path):
    """
    读取 XYZ 文件，返回元素列表、坐标数组和位点类型列表（如果存在）。
    文件格式：
        第一行：原子数
        第二行：注释（可忽略）
        后续每行：元素 x y z [类型]
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()
    if not lines:
        raise ValueError("Empty file")
    num_atoms = int(lines[0].strip())
    coords = []
    ele = []
    site_types = []
    for line in lines[2:2+num_atoms]:
        parts = line.strip().split()
        if len(parts) < 4:
            continue
        ele.append(parts[0])
        coords.append(list(map(float, parts[1:4])))
        if len(parts) >= 5:
            site_types.append(parts[4])
    if not site_types:
        site_types = None
    return ele, np.array(coords), site_types


# ---------------------------- 辅助：自适应原子尺寸 ----------------------------
def _auto_marker_size(n_atoms):
    """
    根据原子数返回 3D scatter 的 marker 面积 (points^2)。
    原子越少越大，原子越多适当减小，但始终保证最外层原子足够大、彼此紧贴，
    使内部原子被完全遮挡，从而清晰呈现团簇外形。
    """
    if n_atoms <= 0:
        return 200
    if n_atoms <= 200:
        return 320
    if n_atoms <= 1000:
        return 220
    if n_atoms <= 3000:
        return 150
    if n_atoms <= 8000:
        return 90
    return 60


# ---------------------------- 独立图例图片（离散类别） ----------------------------
def save_legend(labels, colors, output_file, title=None):
    """
    为离散类别着色(element / site_type)单独生成一张图例图片(色块 + 标签)。

    结构图/动图本身不带图例;离散类别用图例(而非渐变 colorbar)才符合语义。
    便于将多张结构图与一张统一图例一起展示。

    Args:
        labels: 类别标签列表(如 ['Pt', 'O'] 或 ['100', '111', 'edge'])
        colors: 与 labels 对应的 RGB 颜色列表(0-1 范围)
        output_file: 输出图片路径
        title: 图例标题(可选,如 'Element' / 'Site type')
    """
    from matplotlib.patches import Patch

    handles = [Patch(facecolor=c, edgecolor='k', linewidth=0.5, label=str(l))
               for l, c in zip(labels, colors)]
    n = max(len(handles), 1)
    fig, ax = plt.subplots(figsize=(2.4, 0.45 * n + 0.6))
    ax.axis('off')
    legend = ax.legend(handles=handles, loc='center', frameon=True,
                       fontsize=12, title=title, handlelength=1.2)
    if title:
        legend.get_title().set_fontsize(13)
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Legend saved to {output_file}")


# ---------------------------- 独立 colorbar 图片（连续数值） ----------------------------
def save_colorbar(cmap, vmin, vmax, label, output_file, orientation='vertical'):
    """
    单独生成一张 colorbar 图片（结构图/动图本身不再附带 colorbar）。
    便于将多张结构图与一张统一 colorbar 一起展示。
    """
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    if orientation == 'vertical':
        fig, ax = plt.subplots(figsize=(1.4, 6))
        cbar = fig.colorbar(sm, cax=ax, orientation='vertical')
    else:
        fig, ax = plt.subplots(figsize=(6, 1.4))
        cbar = fig.colorbar(sm, cax=ax, orientation='horizontal')
    cbar.set_label(label, fontsize=14)
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Colorbar saved to {output_file}")


# ---------------------------- 绘图函数（支持 GIF） ----------------------------
def plot_structure(particle, color_by='element', output_file=None, gif_file=None, xyz_file=None):
    """
    使用 matplotlib 绘制三维原子结构
    particle: NanoParticle 对象
    color_by: 颜色依据（'element' 或 'site_type'）
    output_file: 若提供，则保存静态图像到该文件
    gif_file: 若提供，则生成旋转 GIF 动画保存到该文件
    xyz_file: XYZ文件路径，用于提取标题（可选）
    """
    particle.setColors(color_by)
    colors = particle.colors

    # ========== 标题生成（健壮版） ==========
    title = None
    
    if xyz_file:
        try:
            import os
            file_dir = os.path.dirname(os.path.abspath(xyz_file))
            parent_dir = os.path.basename(file_dir)
            
            if parent_dir and parent_dir.strip():
                # 尝试解析任务格式：Metal_Gas1_pp_Gas2_pp_TempK_PressPa_RRadius
                parts = parent_dir.split('_')
                
                # 验证格式：至少5个部分，且温度部分包含'K'
                if len(parts) >= 5 and 'K' in parts[3]:
                    metal = parts[0]
                    # 气体分压：保留原始格式并添加%符号
                    gases = ' '.join([f"{p}%" for p in parts[1:3]])
                    temp = parts[3]
                    # 压强：如果只是数字则添加Pa单位
                    pressure = parts[4] if len(parts) > 4 else ''
                    if pressure and pressure.replace('.', '').isdigit():
                        pressure = f"{pressure}Pa"
                    # 半径：保留R前缀，添加Å单位
                    radius = parts[5] if len(parts) > 5 else ''
                    if radius:
                        radius = f"{radius}Å"
                    
                    # 构建标题，包含压强和团簇尺寸
                    title_parts = [metal]
                    if pressure:
                        title_parts.append(pressure)
                    title_parts.extend([gases, temp])
                    if radius:
                        title_parts.append(radius)
                    title = ' '.join(title_parts) + ' Structure'
                else:
                    # 格式不匹配，使用父目录名（去掉下划线）
                    title = parent_dir.replace('_', ' ')
        except Exception as e:
            # 发生异常，打印警告并使用默认标题
            print(f"Warning: Failed to extract title from path: {e}")
            title = None
    
    # 最终fallback：使用默认标题
    if title is None:
        title = 'Atomic Structure'

    # 公共数据
    x = particle.positions[:, 0]
    y = particle.positions[:, 1]
    z = particle.positions[:, 2]

    # 计算坐标范围（用于等比例视图）
    max_range = np.array([x.max()-x.min(), y.max()-y.min(), z.max()-z.min()]).max() / 2.0
    mid_x = (x.max()+x.min()) * 0.5
    mid_y = (y.max()+y.min()) * 0.5
    mid_z = (z.max()+z.min()) * 0.5

    # 计算原子绘制尺寸：随原子数自适应，保证最外层原子足够大、彼此紧贴、
    # 不透明（看不到内部原子），从而清晰呈现团簇外形。
    marker_size = _auto_marker_size(particle.nAtoms)

    def _render(ax, azim):
        """在给定坐标轴上绘制不透明大尺寸原子（按深度排序消除穿插）。"""
        # 依据当前视角的进深对原子排序，先画后方再画前方，避免后方原子盖住前方。
        rad = np.deg2rad(azim)
        depth = x * np.cos(rad) + y * np.sin(rad)
        order = np.argsort(depth)
        ax.scatter(
            x[order], y[order], z[order],
            c=colors[order],
            s=marker_size,
            edgecolors='k',
            linewidth=0.4,
            alpha=1.0,            # 完全不透明，遮住内部原子
            depthshade=False,     # 关闭自动暗化，保持配色一致
        )
        ax.set_xlabel('X (Å)')
        ax.set_ylabel('Y (Å)')
        ax.set_zlabel('Z (Å)')
        ax.set_title(title)
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)
        try:
            ax.set_box_aspect((1, 1, 1))   # 等比例，避免拉伸变形
        except Exception:
            pass
        ax.view_init(elev=30, azim=azim)

    if gif_file:
        # 生成旋转 GIF
        try:
            import imageio
        except ImportError:
            print("Error: imageio is required to create GIF. Please install it (pip install imageio).")
            sys.exit(1)

        angles = range(0, 360, 10)  # 每10度一帧，共36帧（更小体积、更快）
        frames = []
        for angle in angles:
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')
            _render(ax, angle)
            fig.canvas.draw()
            buffer = fig.canvas.buffer_rgba()
            img = np.asarray(buffer)[:, :, :3]   # 丢弃 alpha 通道
            frames.append(img)
            plt.close(fig)

        imageio.mimsave(gif_file, frames, fps=10)
        print(f"GIF saved to {gif_file}")
    else:
        # 静态显示或保存静态图像
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        _render(ax, 30)

        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"Image saved to {output_file}")
            # 离散类别着色:单独生成图例图片(色块+标签),便于多图统一展示
            import os
            base, _ = os.path.splitext(output_file)
            if color_by == 'element':
                cats = list(dict.fromkeys(particle.eles.tolist()))
                legend_labels = cats
                legend_title = 'Element'
                # MSR 自动检测：若存在 site_type 且 element↔site_type 一一对应，
                # 图例标签改用 site_type（MSR 伪元素场景）
                if particle.siteTypes is not None:
                    e2t = {}
                    mapping_ok = True
                    for e, t in zip(particle.eles, particle.siteTypes):
                        t = t.strip()
                        if e in e2t and e2t[e] != t:
                            mapping_ok = False
                            break
                        e2t[e] = t
                    if mapping_ok:
                        legend_labels = [e2t.get(c, c) for c in cats]
                        legend_title = 'Site type'
                save_legend(legend_labels, [get_ele_color(c) for c in cats],
                            base + '_legend.png', title=legend_title)
            elif color_by == 'site_type' and particle.siteTypes is not None:
                cats = list(dict.fromkeys(s.strip() for s in particle.siteTypes))
                save_legend(cats, [get_type_color(c) for c in cats],
                            base + '_legend.png', title='Site type')
        else:
            plt.show()


# ---------------------------- 主程序 ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Visualize XYZ atomic structure with site types")
    parser.add_argument('xyz_file', help="Path to XYZ file (with optional site type in column 5)")
    parser.add_argument('--output', '-o', help="Output static image file (e.g., structure.png)")
    parser.add_argument('--gif', help="Output rotating GIF file (e.g., rotation.gif)")
    parser.add_argument('--color-by', '-c', choices=['element', 'site_type'],
                        default='element', help="Color by element or site type")
    args = parser.parse_args()

    # 读取文件
    eles, positions, site_types = read_xyz(args.xyz_file)

    # 创建粒子对象
    particle = NanoParticle(eles, positions, siteTypes=site_types)

    # 绘图（静态或 GIF）
    plot_structure(particle, color_by=args.color_by, output_file=args.output, gif_file=args.gif, xyz_file=args.xyz_file)


if __name__ == "__main__":
    main()