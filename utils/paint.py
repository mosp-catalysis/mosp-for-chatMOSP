#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
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


# ---------------------------- 绘图函数（支持 GIF） ----------------------------
def plot_structure(particle, color_by='element', output_file=None, gif_file=None):
    """
    使用 matplotlib 绘制三维原子结构
    particle: NanoParticle 对象
    color_by: 颜色依据（'element' 或 'site_type'）
    output_file: 若提供，则保存静态图像到该文件
    gif_file: 若提供，则生成旋转 GIF 动画保存到该文件
    """
    particle.setColors(color_by)
    colors = particle.colors

    # 公共数据
    x = particle.positions[:, 0]
    y = particle.positions[:, 1]
    z = particle.positions[:, 2]

    # 计算坐标范围（用于等比例视图）
    max_range = np.array([x.max()-x.min(), y.max()-y.min(), z.max()-z.min()]).max() / 2.0
    mid_x = (x.max()+x.min()) * 0.5
    mid_y = (y.max()+y.min()) * 0.5
    mid_z = (z.max()+z.min()) * 0.5

    if gif_file:
        # 生成旋转 GIF
        try:
            import imageio
        except ImportError:
            print("Error: imageio is required to create GIF. Please install it (pip install imageio).")
            sys.exit(1)

        angles = range(0, 360, 5)  # 每5度一帧，共72帧
        frames = []
        for angle in angles:
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')
            # 绘制原子（原子大小 120，比原来 80 大 1.5 倍）
            ax.scatter(x, y, z, c=colors, s=120, edgecolors='k', linewidth=0.5)
            ax.set_xlabel('X (Å)')
            ax.set_ylabel('Y (Å)')
            ax.set_zlabel('Z (Å)')
            ax.set_title(f'Atomic Structure (colored by {color_by})')
            # 设置等比例坐标范围
            ax.set_xlim(mid_x - max_range, mid_x + max_range)
            ax.set_ylim(mid_y - max_range, mid_y + max_range)
            ax.set_zlim(mid_z - max_range, mid_z + max_range)
            # 设置视角：固定仰角30°，方位角不断变化
            ax.view_init(elev=30, azim=angle)
            # 保存当前帧到内存
            fig.canvas.draw()
            # 获取图像数据：使用 buffer_rgba() 获得 RGBA 格式，然后转换为 RGB
            buffer = fig.canvas.buffer_rgba()
            img = np.asarray(buffer)          # shape (height, width, 4)
            img = img[:, :, :3]               # 丢弃 alpha 通道，保留 RGB
            frames.append(img)
            plt.close(fig)  # 关闭图形释放内存

        # 保存 GIF
        imageio.mimsave(gif_file, frames, fps=10)
        print(f"GIF saved to {gif_file}")
    else:
        # 静态显示或保存静态图像
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        # 原子大小 120
        ax.scatter(x, y, z, c=colors, s=120, edgecolors='k', linewidth=0.5)
        ax.set_xlabel('X (Å)')
        ax.set_ylabel('Y (Å)')
        ax.set_zlabel('Z (Å)')
        ax.set_title(f'Atomic Structure (colored by {color_by})')
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)

        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"Image saved to {output_file}")
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
    plot_structure(particle, color_by=args.color_by, output_file=args.output, gif_file=args.gif)


if __name__ == "__main__":
    main()