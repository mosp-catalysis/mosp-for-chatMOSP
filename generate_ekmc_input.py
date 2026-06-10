#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EKMC（环境 KMC）一键式全流程脚本

模拟团簇在反应气氛中的【动态形貌】。流程参照 kmc_standalone.py 的“一键式”设计：

    读取 JSON  ->  生成 EKMC 输入文件  ->  调用 wine 运行 EKMC-main.exe  ->  自动绘图

用法:
    python generate_ekmc_input.py --json <config.json> [--out-dir <run_dir>] [--xyz <ini.xyz>]

说明:
    - --out-dir 为本次运行的工作目录。脚本会在其下创建 EKMC-INPUT 与
      EKMC-OUTPUT 子目录（EKMC-main.exe 以相对路径 EKMC-INPUT、
      EKMC-OUTPUT 读写），并以 --out-dir 作为 wine 的工作目录运行引擎。
    - EKMC 需要初始结构。若提供 --xyz，则复制到 EKMC-INPUT/ini.xyz（引擎使用）
      和任务根 ini.xyz（用户可见）；若 JSON 中已配置或引擎自行生成网格，则可省略。
    - 绘图复用 utils/postprocess_ekmc.py（剥离主流程后的重绘模块）。
      图像输出到任务根目录；若需重绘可单独运行该脚本。
"""

import os
import sys
import json
import shutil
import argparse
import subprocess

import numpy as np


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_EXE = os.path.join(SCRIPT_DIR, 'engine', 'EKMC-main.exe')
ENGINE_DIR = os.path.join(SCRIPT_DIR, 'engine')

# EKMC-main.exe 硬编码的相对读写目录（引擎 cwd 下直接 EKMC-INPUT / EKMC-OUTPUT）
INPUT_SUBDIR = 'EKMC-INPUT'
OUTPUT_SUBDIR = 'EKMC-OUTPUT'


def str2zero(inp):
    """如果输入是字符串，返回 0。"""
    if isinstance(inp, str):
        return 0
    return inp


# ============================================================
# 1. 生成 EKMC 输入文件
# ============================================================

def writeEkmcInp(values, output_dir):
    """
    生成 EKMC 输入文件 (input.txt / LI.txt / species.txt / events.txt)。

    Args:
        values: 从 JSON 读取的参数字典（须含 'EKMC' 段）
        output_dir: EKMC-INPUT 目录路径

    Returns:
        bool: 成功返回 True
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        if 'EKMC' not in values:
            print("❌ JSON 缺少 'EKMC' 段")
            return False
        kmc_values = values['EKMC']
        print(f"EKMC parameters: {kmc_values}")

        # 1) input.txt
        input_file = os.path.join(output_dir, 'input.txt')
        with open(input_file, 'w') as f_ini:
            f_ini.write(f"Temperature: {values['Temperature']}\n")
            f_ini.write(f"Pressure: {values['Pressure']}\n")
            f_ini.write(f"Element: {values['Element']}\n")
            f_ini.write(f"Crystal_Structure: {values['Crystal structure']}\n")
            f_ini.write(f"Lattice_Constant: {values['Lattice constant']}\n")
            f_ini.write(f"Dimensions: {kmc_values['dim_x']} {kmc_values['dim_y']} {kmc_values['dim_z']}\n")
            f_ini.write(f"Num_Species: {kmc_values['nspecies']}\n")
            f_ini.write(f"Num_Events: {kmc_values['nevents']}\n")
            f_ini.write(f"Num_Steps: {kmc_values['nLoop']}\n")
            f_ini.write(f"Record_Interval: {kmc_values['record_int']}\n")
            f_ini.write(f"E_Bond: {kmc_values['E_bond']}\n")
            f_ini.write(f"E_Cohesive_Base: {kmc_values['Ecoh_U0']}\n")
            f_ini.write(f"E_Cohesive_Exp1: {kmc_values['Ecoh_A1']} {kmc_values['Ecoh_t1']}\n")
            f_ini.write(f"E_Cohesive_Exp2: {kmc_values['Ecoh_A2']} {kmc_values['Ecoh_t2']}\n")
        print(f"✓ Generated {input_file}")

        # 2) LI.txt (相互作用矩阵)
        li_file = os.path.join(output_dir, 'LI.txt')
        li = np.array(kmc_values["li"]).astype(np.float32)
        np.savetxt(li_file, li, fmt="%.3f", delimiter="\t")
        print(f"✓ Generated {li_file}")

        # 3) species.txt
        species_file = os.path.join(output_dir, 'species.txt')
        with open(species_file, 'w') as s_ini:
            for n in range(kmc_values['nspecies']):
                spe_dict = json.loads(kmc_values[f"s{n+1}"])
                s_ini.write(f"ID: {n+1}\n")
                s_ini.write(f"Name: {spe_dict['name']}\n")
                s_ini.write(f"is_twosite: {spe_dict['is_twosite']}\n")
                s_ini.write(f"mass: {spe_dict['mass']}\n")
                s_ini.write(f"S_gas0: {spe_dict['S_gas']}\n")
                s_ini.write(f"S_ads: {spe_dict['S_ads']}\n")
                s_ini.write(f"sticking: {spe_dict['sticking'][0]} {spe_dict['sticking'][1]}\n")
                s_ini.write(f"E_ads_para: {spe_dict['E_ads_para'][0]} {spe_dict['E_ads_para'][1]} {spe_dict['E_ads_para'][2]}\n")
                s_ini.write(f"Ea_diff: {spe_dict['Ea_diff']}\n")
                s_ini.write(f"PP_ratio: {float(spe_dict['PP_ratio'])*0.01}\n")
                s_ini.write("\n")
        print(f"✓ Generated {species_file}")

        # 4) events.txt
        type_alias = {"Adsorption": "ads", "Desorption": "des", "Diffusion": "diff"}
        events_file = os.path.join(output_dir, 'events.txt')
        with open(events_file, 'w') as e_ini:
            for n in range(kmc_values['nevents']):
                evt_dict = json.loads(kmc_values[f"e{n+1}"])
                e_ini.write(f"ID: {n+1}\n")
                e_ini.write(f"Name: {evt_dict['name']}\n")
                e_ini.write(f"event_type: {type_alias[evt_dict['type']]}\n")
                e_ini.write(f"is_twosite: {evt_dict['is_twosite']}\n")
                e_ini.write("cov_before: "
                            f"{str2zero(evt_dict['cov_before'][0])} "
                            f"{str2zero(evt_dict['cov_before'][1])}\n")
                e_ini.write("cov_after: "
                            f"{str2zero(evt_dict['cov_after'][0])} "
                            f"{str2zero(evt_dict['cov_after'][1])}\n")
                e_ini.write("\n")
        print(f"✓ Generated {events_file}")

        print(f"\n✅ EKMC input files generated in: {output_dir}")
        return True

    except Exception as e:
        print(f'❌ Error in writeEkmcInp: {e}')
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 2. 运行 EKMC 引擎 (wine)
# ============================================================

def run_ekmc_engine(run_dir):
    """
    在 run_dir 下通过 wine 运行 EKMC-main.exe。
    引擎以相对路径读 data/EKMC-INPUT、写 data/EKMC-OUTPUT，故 cwd 设为 run_dir。
    日志写入 run_dir/run.log。
    """
    if not os.path.isfile(ENGINE_EXE):
        print(f"❌ Engine not found: {ENGINE_EXE}")
        return False

    env = os.environ.copy()
    env["PATH"] = ENGINE_DIR + os.pathsep + env.get("PATH", "")

    print(f"\n▶ Running EKMC engine via wine (cwd={run_dir}) ...")
    try:
        result = subprocess.run(
            ["wine", ENGINE_EXE],
            cwd=run_dir,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            env=env,
        )
    except FileNotFoundError:
        print("❌ 'wine' not found. Please install wine to run EKMC-main.exe.")
        return False

    log_text = result.stdout
    if result.stderr:
        log_text += "\n[stderr]\n" + result.stderr
    with open(os.path.join(run_dir, 'run.log'), 'w', encoding='utf-8') as f:
        f.write(log_text)

    if result.returncode != 0:
        print(f"❌ EKMC-main.exe failed (exit code {result.returncode}). See run.log")
        return False
    print("✓ EKMC engine finished.")
    return True


# ============================================================
# 3. 标题信息（金属/温度/压强/分压/团簇尺寸/步数）
# ============================================================

def compose_title(values):
    """根据 JSON 参数拼出图像标题信息。"""
    kmc = values.get('EKMC', {})
    metal = values.get('Element', '')
    temp = values.get('Temperature', '')
    press = values.get('Pressure', '')
    steps = kmc.get('nLoop', '')

    # 分压：从各 species 的 PP_ratio 读取
    pp_parts = []
    try:
        for n in range(int(kmc.get('nspecies', 0))):
            spe = json.loads(kmc[f"s{n+1}"])
            pp_parts.append(f"{spe.get('name', f's{n+1}')}{spe.get('PP_ratio', '')}%")
    except Exception:
        pass
    pp = " ".join(pp_parts)

    # 团簇尺寸：EKMC 用网格维度 dim_x×dim_y×dim_z 表征
    dims = f"{kmc.get('dim_x','')}x{kmc.get('dim_y','')}x{kmc.get('dim_z','')}"

    parts = [p for p in [metal, pp, f"{temp}K", f"{press}Pa",
                         f"grid{dims}", f"{steps}steps-EKMC"] if p and p not in ('K', 'Pa')]
    return " ".join(parts)


# ============================================================
# 主流程
# ============================================================

def run_full_flow(config_file, out_dir, xyz_file=None):
    with open(config_file, 'r') as f:
        values = json.load(f)

    input_dir = os.path.join(out_dir, INPUT_SUBDIR)
    output_dir = os.path.join(out_dir, OUTPUT_SUBDIR)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # 1) 生成输入
    print("[1/3] Generating EKMC input files ...")
    if not writeEkmcInp(values, input_dir):
        return False

    # EKMC 需要初始结构
    # 复制 input.json 到任务根（用户可见，参照 KMC；同路径则跳过）
    src_json = os.path.abspath(config_file)
    dst_json = os.path.abspath(os.path.join(out_dir, 'input.json'))
    if src_json != dst_json:
        shutil.copy2(config_file, os.path.join(out_dir, 'input.json'))
        print(f"✓ Copied input.json -> {os.path.join(out_dir, 'input.json')}")

    if xyz_file:
        if not os.path.isfile(xyz_file):
            print(f"❌ --xyz file not found: {xyz_file}")
            return False
        # 引擎需要的一份放进 EKMC-INPUT/
        shutil.copy2(xyz_file, os.path.join(input_dir, 'ini.xyz'))
        print(f"✓ Copied initial structure -> {os.path.join(input_dir, 'ini.xyz')}")
        # 任务根也放一份（用户可见，参照 KMC；同路径则跳过）
        src_xyz = os.path.abspath(xyz_file)
        dst_xyz = os.path.abspath(os.path.join(out_dir, 'ini.xyz'))
        if src_xyz != dst_xyz:
            shutil.copy2(xyz_file, os.path.join(out_dir, 'ini.xyz'))
            print(f"✓ Copied initial structure -> {os.path.join(out_dir, 'ini.xyz')}")

    # 2) 运行引擎
    print("\n[2/3] Running EKMC engine ...")
    if not run_ekmc_engine(out_dir):
        return False

    # 3) 绘图（复用 utils/postprocess_ekmc.py）
    print("\n[3/3] Plotting EKMC results ...")
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'utils'))
    from postprocess_ekmc import replot  # noqa: E402
    title = compose_title(values)
    # 数据从 EKMC-OUTPUT 读取，图像写到任务根
    ok = replot(output_dir, img_dir=out_dir, title=title)
    if not ok:
        print("⚠ Plotting reported missing output files; check the EKMC run.")
        return False

    print(f"\n🎉 EKMC full flow complete!\n  Run dir:   {out_dir}\n  Images:    {out_dir}\n  Raw data:  {output_dir}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EKMC one-stop pipeline: JSON -> input -> wine engine -> plots.")
    parser.add_argument('--json', '-j', required=True, help='Path to EKMC config JSON.')
    parser.add_argument('--out-dir', '-o', default='.',
                        help='Run directory; EKMC-INPUT & EKMC-OUTPUT are created under it.')
    parser.add_argument('--xyz', default=None,
                        help='Initial structure (.xyz). EKMC requires an initial structure, '
                             'e.g. from an MSR run.')
    args = parser.parse_args()

    print(f"Reading config from: {args.json}")
    success = run_full_flow(args.json, args.out_dir, args.xyz)
    sys.exit(0 if success else 1)
