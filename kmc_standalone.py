from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import ticker


ENGINE_EXECUTABLE = "main.exe"
ENGINE_DLLS = [
    "libgcc_s_seh-1.dll",
    "libgfortran-5.dll",
    "libquadmath-0.dll",
    "libwinpthread-1.dll",
]
ENGINE_PAYLOAD = [ENGINE_EXECUTABLE] + ENGINE_DLLS
TYPE_ALIAS = {
    "Adsorption": "ads",
    "Desorption": "des",
    "Diffusion": "diff",
    "Reaction": "rec",
}
FORMATTER = ticker.ScalarFormatter(useMathText=True)
FORMATTER.set_powerlimits((-2, 2))


@dataclass
class ProductInfo:
    index: int
    name: str
    event_gen: List[int] = field(default_factory=list)
    event_consum: List[int] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run MOSP KMC independently from a .xyz structure and an existing "
            "MOSP JSON file, then export PNG/CSV outputs."
        )
    )
    parser.add_argument("--xyz", required=True, help="Path to the input .xyz file.")
    parser.add_argument("--json", required=True, help="Path to the MOSP JSON file.")
    parser.add_argument(
        "--out-dir",
        required=True,
        help=(
            "Run directory name or path. Relative paths are created under "
            "standalone_kmc/runs/."
        ),
    )
    return parser.parse_args()


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"Error: {message}")


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        fail(f"{label} not found: {path}")
    return path


def normalize_run_dir(raw_out_dir: str, runs_root: Path) -> Path:
    candidate = Path(raw_out_dir)
    if not candidate.is_absolute():
        candidate = runs_root / candidate
    resolved_runs_root = runs_root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate != resolved_runs_root and resolved_runs_root not in resolved_candidate.parents:
        fail(f"--out-dir must stay inside {resolved_runs_root}")
    return resolved_candidate


def validate_xyz(xyz_path: Path) -> None:
    with xyz_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline().strip()
    try:
        natoms = int(first_line)
    except ValueError as exc:
        raise SystemExit(f"Error: invalid xyz atom count in {xyz_path}: {first_line}") from exc
    if natoms <= 0:
        fail(f"xyz atom count must be positive: {xyz_path}")


def load_json_input(json_path: Path) -> Dict[str, object]:
    with json_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "KMC" not in data:
        fail(f"missing 'KMC' section in {json_path}")
    return data


def parse_json_blob(raw_blob: object, label: str) -> Dict[str, object]:
    if not isinstance(raw_blob, str):
        fail(f"{label} must be a JSON string")
    try:
        parsed = json.loads(raw_blob)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: failed to parse {label}: {exc}") from exc
    if not isinstance(parsed, dict):
        fail(f"{label} must decode to a JSON object")
    return parsed


def parse_positive_int(value: object, label: str, allow_zero: bool = False) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Error: invalid integer for {label}: {value}") from exc
    if allow_zero:
        if parsed < 0:
            fail(f"{label} must be >= 0")
    elif parsed <= 0:
        fail(f"{label} must be > 0")
    return parsed


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Error: invalid number for {label}: {value}") from exc


def rebuild_product_events(products: Sequence[ProductInfo], events: Sequence[Dict[str, object]]) -> None:
    product_lookup = {product.index: product for product in products}
    for event_id, event in enumerate(events, start=1):
        cov_before = event.get("cov_before", [])
        cov_after = event.get("cov_after", [])
        if not isinstance(cov_before, list) or not isinstance(cov_after, list):
            fail(f"event e{event_id} must contain list cov_before/cov_after")
        for cov in cov_before:
            if isinstance(cov, str) and cov.startswith("p"):
                product_idx = parse_positive_int(cov[1:], f"event e{event_id} product reference")
                if product_idx not in product_lookup:
                    fail(f"event e{event_id} references missing product {cov}")
                product_lookup[product_idx].event_consum.append(event_id)
        for cov in cov_after:
            if isinstance(cov, str) and cov.startswith("p"):
                product_idx = parse_positive_int(cov[1:], f"event e{event_id} product reference")
                if product_idx not in product_lookup:
                    fail(f"event e{event_id} references missing product {cov}")
                product_lookup[product_idx].event_gen.append(event_id)


def parse_kmc_sections(data: Dict[str, object]) -> Dict[str, object]:
    required_top_level = [
        "Element",
        "Lattice constant",
        "Crystal structure",
        "Pressure",
        "Temperature",
    ]
    for key in required_top_level:
        if key not in data:
            fail(f"missing top-level field '{key}'")

    kmc = data["KMC"]
    if not isinstance(kmc, dict):
        fail("'KMC' must be a JSON object")

    nspecies = parse_positive_int(kmc.get("nspecies"), "KMC.nspecies")
    nproducts = parse_positive_int(kmc.get("nproducts"), "KMC.nproducts", allow_zero=True)
    nevents = parse_positive_int(kmc.get("nevents"), "KMC.nevents")

    species = []
    for idx in range(1, nspecies + 1):
        key = f"s{idx}"
        if key not in kmc:
            fail(f"missing KMC field '{key}'")
        species.append(parse_json_blob(kmc[key], key))

    products: List[ProductInfo] = []
    for idx in range(1, nproducts + 1):
        key = f"p{idx}"
        if key not in kmc:
            fail(f"missing KMC field '{key}'")
        product_blob = parse_json_blob(kmc[key], key)
        product_name = str(product_blob.get("name") or product_blob.get("default_name") or key)
        products.append(ProductInfo(index=idx, name=product_name))

    events = []
    for idx in range(1, nevents + 1):
        key = f"e{idx}"
        if key not in kmc:
            fail(f"missing KMC field '{key}'")
        events.append(parse_json_blob(kmc[key], key))

    li = kmc.get("li")
    if not isinstance(li, list) or len(li) != nspecies:
        fail("KMC.li must be an nspecies x nspecies matrix")
    for row_idx, row in enumerate(li, start=1):
        if not isinstance(row, list) or len(row) != nspecies:
            fail(f"KMC.li row {row_idx} must contain {nspecies} values")
        for col_idx, value in enumerate(row, start=1):
            parse_float(value, f"KMC.li[{row_idx}][{col_idx}]")

    rebuild_product_events(products, events)

    return {
        "top_level": data,
        "kmc": kmc,
        "nspecies": nspecies,
        "nproducts": nproducts,
        "nevents": nevents,
        "species": species,
        "products": products,
        "events": events,
    }


def compute_bond_length(data: Dict[str, object]) -> float:
    lattice_constant = parse_float(data["Lattice constant"], "Lattice constant")
    crystal = str(data["Crystal structure"]).strip().upper()
    if crystal == "FCC":
        bond_length = 1.45 / 2 * lattice_constant
    elif crystal == "BCC":
        bond_length = 1.75 / 2 * lattice_constant
    else:
        fail(f"unsupported crystal structure: {data['Crystal structure']}")
    return (int(bond_length * 10) + 1) / 10.0


def reset_run_directory(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["INPUT"]:  # 只删除INPUT目录，OUTPUT目录保留作为临时目录
        target = out_dir / name
        if target.exists():
            try:
                shutil.rmtree(target)
            except PermissionError as exc:
                raise SystemExit(
                    "Error: failed to reset run directory because files are still in use. "
                    f"Choose another --out-dir or stop the process using {out_dir}."
                ) from exc
    for name in [
        ENGINE_EXECUTABLE,
        *ENGINE_DLLS,
        "run.log",
        "coverage.csv",
        "tof.csv",
        "site_tof.csv",
        "coverage.png",
        "tof.png",
        "rec_cov.data",
        "rec_event.data",
        "rec_site_spc.data",  # 添加KMC原始输出文件
    ]:
        target = out_dir / name
        if target.exists():
            try:
                target.unlink()
            except PermissionError as exc:
                raise SystemExit(
                    "Error: failed to reset run directory because files are still in use. "
                    f"Choose another --out-dir or stop the process using {out_dir}."
                ) from exc
    (out_dir / "INPUT").mkdir()
    (out_dir / "OUTPUT").mkdir()


def validate_engine_payload(engine_dir: Path) -> None:
    missing = [name for name in ENGINE_PAYLOAD if not (engine_dir / name).is_file()]
    if missing:
        fail(f"engine payload missing from {engine_dir}: {', '.join(missing)}")


def stringify_cov(value: object) -> str:
    if isinstance(value, str):
        return "0"
    return str(value)


def write_input_files(parsed: Dict[str, object], xyz_path: Path, out_dir: Path) -> None:
    data = parsed["top_level"]
    kmc = parsed["kmc"]
    nspecies = parsed["nspecies"]
    products: Sequence[ProductInfo] = parsed["products"]
    events: Sequence[Dict[str, object]] = parsed["events"]

    shutil.copy2(xyz_path, out_dir / "INPUT" / "ini.xyz")

    input_path = out_dir / "INPUT" / "input.txt"
    with input_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{data['Temperature']}\t\t ! Temperature (K)\n")
        handle.write(f"{data['Pressure']}\t\t ! Pressure (Pa)\n")
        handle.write(f"{compute_bond_length(data)}\t\t ! Bond length (A)\n")
        handle.write(f"{parsed['nspecies']}\t\t ! Num of species\n")
        handle.write(f"{parsed['nevents']}\t\t ! Num of events\n")
        handle.write(f"{parsed['nproducts']}\t\t ! Num of products\n")
        handle.write(f"{kmc['nLoop']}\t\t ! Num of steps\n")
        handle.write(f"{kmc['record_int']}\t\t ! record inteval\n")

    li_array = np.asarray(kmc["li"], dtype=np.float32)
    np.savetxt(out_dir / "INPUT" / "LI.txt", li_array, fmt="%.3f", delimiter="\t")

    with (out_dir / "INPUT" / "species.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for idx in range(1, nspecies + 1):
            specie = parsed["species"][idx - 1]
            name = str(specie.get("name") or specie.get("default_name") or f"Specie{idx}")
            sticking = specie.get("sticking", [1.0, 1.0])
            if not isinstance(sticking, list) or len(sticking) != 2:
                fail(f"s{idx}.sticking must contain 2 values")
            e_ads_para = specie.get("E_ads_para", [0.0, 0.0, 0.0])
            if not isinstance(e_ads_para, list) or len(e_ads_para) != 3:
                fail(f"s{idx}.E_ads_para must contain 3 values")
            handle.write(f"ID: {idx}\n")
            handle.write(f"Name: {name}\n")
            handle.write(f"is_twosite: {bool(specie.get('is_twosite', False))}\n")
            handle.write(f"mass: {parse_float(specie.get('mass', 0.0), f's{idx}.mass')}\n")
            handle.write(f"S_gas0: {parse_float(specie.get('S_gas', 0.0), f's{idx}.S_gas')}\n")
            handle.write(f"S_ads: {parse_float(specie.get('S_ads', 0.0), f's{idx}.S_ads')}\n")
            handle.write(
                "sticking: "
                f"{parse_float(sticking[0], f's{idx}.sticking[0]')} "
                f"{parse_float(sticking[1], f's{idx}.sticking[1]')}\n"
            )
            handle.write(
                "E_ads_para: "
                f"{parse_float(e_ads_para[0], f's{idx}.E_ads_para[0]')} "
                f"{parse_float(e_ads_para[1], f's{idx}.E_ads_para[1]')} "
                f"{parse_float(e_ads_para[2], f's{idx}.E_ads_para[2]')}\n"
            )
            handle.write(f"Ea_diff: {parse_float(specie.get('Ea_diff', 0.0), f's{idx}.Ea_diff')}\n")
            pp_ratio = parse_float(specie.get("PP_ratio", 0.0), f"s{idx}.PP_ratio") * 0.01
            handle.write(f"PP_ratio: {pp_ratio}\n")
            handle.write("\n")

    with (out_dir / "INPUT" / "products.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for product in products:
            handle.write(f"ID: {product.index}\n")
            handle.write(f"Name: {product.name}\n")
            handle.write(f"num_gen: {len(product.event_gen)}\n")
            handle.write("event_gen: ")
            handle.write(" ".join(str(event_id) for event_id in product.event_gen) if product.event_gen else "0")
            handle.write("\n")
            handle.write(f"num_consum: {len(product.event_consum)}\n")
            handle.write("event_consum: ")
            handle.write(
                " ".join(str(event_id) for event_id in product.event_consum)
                if product.event_consum
                else "0"
            )
            handle.write("\n\n")

    with (out_dir / "INPUT" / "events.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for idx, event in enumerate(events, start=1):
            event_type = str(event.get("type", "Reaction"))
            if event_type not in TYPE_ALIAS:
                fail(f"e{idx}.type is unsupported: {event_type}")
            cov_before = event.get("cov_before", [0, 0])
            cov_after = event.get("cov_after", [0, 0])
            if not isinstance(cov_before, list) or len(cov_before) != 2:
                fail(f"e{idx}.cov_before must contain 2 values")
            if not isinstance(cov_after, list) or len(cov_after) != 2:
                fail(f"e{idx}.cov_after must contain 2 values")
            handle.write(f"ID: {idx}\n")
            handle.write(f"Name: {str(event.get('name') or event_type)}\n")
            handle.write(f"event_type: {TYPE_ALIAS[event_type]}\n")
            handle.write(f"is_twosite: {bool(event.get('is_twosite', False))}\n")
            handle.write(
                "cov_before: "
                f"{stringify_cov(cov_before[0])} {stringify_cov(cov_before[1])}\n"
            )
            handle.write(
                "cov_after: "
                f"{stringify_cov(cov_after[0])} {stringify_cov(cov_after[1])}\n"
            )
            if event_type == "Reaction":
                bep_para = event.get("BEP_para", [0.0, 0.0])
                if not isinstance(bep_para, list) or len(bep_para) != 2:
                    fail(f"e{idx}.BEP_para must contain 2 values")
                handle.write(
                    "BEP_para: "
                    f"{parse_float(bep_para[0], f'e{idx}.BEP_para[0]')} "
                    f"{parse_float(bep_para[1], f'e{idx}.BEP_para[1]')}\n"
                )
            handle.write("\n")


def run_engine(engine_dir: Path, out_dir: Path) -> None:
    exe_path = engine_dir / ENGINE_EXECUTABLE
    env = os.environ.copy()
    env.update({"PATH": str(engine_dir) + ";" + env.get("PATH", "")})
    result = subprocess.run(
        ["wine", str(exe_path)],
        cwd=str(out_dir),
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        env=env,
    )
    log_text = result.stdout
    if result.stderr:
        log_text += "\n[stderr]\n" + result.stderr
    (out_dir / "run.log").write_text(log_text, encoding="utf-8")
    
    # 将输出文件从OUTPUT目录移动到根目录
    output_dir = out_dir / "OUTPUT"
    if output_dir.exists():
        for output_file in output_dir.iterdir():
            if output_file.is_file():
                shutil.move(str(output_file), str(out_dir / output_file.name))
        # 删除空的OUTPUT目录
        try:
            output_dir.rmdir()
        except OSError:
            pass  # 如果目录不为空，保留它
    
    if result.returncode != 0:
        fail(f"main.exe failed with exit code {result.returncode}. See {out_dir / 'run.log'}")


def require_output_files(output_dir: Path) -> Dict[str, Path]:
    required = {
        "cov": output_dir / "rec_cov.data",
        "event": output_dir / "rec_event.data",
        "site": output_dir / "rec_site_spc.data",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        fail("missing KMC output files: " + ", ".join(missing))
    return required


def load_outputs(output_dir: Path) -> Dict[str, object]:
    files = require_output_files(output_dir)
    cov = pd.read_csv(files["cov"], sep=r"\s+")
    event = pd.read_csv(files["event"], sep=r"\s+").set_index("Steps")

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


def compute_tof_tables(
    event_df: pd.DataFrame,
    site_df: pd.DataFrame,
    products: Sequence[ProductInfo],
    total_time: float,
    nsurf: int,
    gap: int = 10,
) -> Dict[str, pd.DataFrame]:
    if nsurf <= 0:
        fail("surface site count in rec_site_spc.data must be positive")
    if total_time <= 0:
        fail("total time in rec_site_spc.data must be positive")

    ton = event_df[["Time"]].copy()
    ton_site = site_df[["cn"]].copy()

    for product in products:
        ton[product.name] = 0
        ton_site[product.name] = 0
        for event_id in product.event_gen:
            if event_id >= len(event_df.columns):
                fail(f"product {product.name} references event id {event_id} outside rec_event.data")
            site_col_idx = event_id + 5
            if site_col_idx >= len(site_df.columns):
                fail(f"product {product.name} references event id {event_id} outside rec_site_spc.data")
            ton[product.name] += event_df.iloc[:, event_id]
            ton_site[product.name] += site_df.iloc[:, site_col_idx]
        for event_id in product.event_consum:
            if event_id >= len(event_df.columns):
                fail(f"product {product.name} references event id {event_id} outside rec_event.data")
            site_col_idx = event_id + 5
            if site_col_idx >= len(site_df.columns):
                fail(f"product {product.name} references event id {event_id} outside rec_site_spc.data")
            ton[product.name] -= event_df.iloc[:, event_id]
            ton_site[product.name] -= site_df.iloc[:, site_col_idx]

    interval = max(len(event_df) // gap, 1)
    sub_ton = ton.iloc[::interval].copy()
    diff_ton = sub_ton.diff().iloc[1:].copy()

    tof = diff_ton[["Time"]].copy()
    for product in products:
        tof[product.name] = diff_ton[product.name] / diff_ton["Time"] / nsurf

    tof.insert(0, "Steps", diff_ton.index.astype(int))

    site_tof = site_df[["x", "y", "z", "cov", "cn", "gcn"]].copy()
    for product in products:
        site_tof[product.name] = ton_site[product.name] / total_time

    ton_export = diff_ton.copy()
    ton_export.insert(0, "Steps", diff_ton.index.astype(int))
    return {
        "ton": ton_export,
        "tof": tof,
        "site_tof": site_tof,
    }


def plot_coverage(cov_df: pd.DataFrame, output_path: Path) -> None:
    species_columns = [column for column in cov_df.columns if column not in {"Time", "Steps"}]
    if not species_columns:
        fail("rec_cov.data does not contain coverage columns")

    fig, ax = plt.subplots(figsize=(8, 5))
    for column in species_columns:
        ax.plot(cov_df["Time"], cov_df[column], label=column)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Coverage")
    ax.grid(linestyle="--")
    ax.xaxis.set_major_formatter(FORMATTER)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def plot_tof(tof_df: pd.DataFrame, output_path: Path) -> None:
    product_columns = [column for column in tof_df.columns if column not in {"Steps", "Time"}]
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
    ax.grid(linestyle="--")
    ax.yaxis.set_major_formatter(FORMATTER)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    runs_root = script_dir / "OUTPUT"
    engine_dir = script_dir / "engine"

    xyz_path = require_file(Path(args.xyz).resolve(), "xyz file")
    json_path = require_file(Path(args.json).resolve(), "json file")
    validate_xyz(xyz_path)

    parsed = parse_kmc_sections(load_json_input(json_path))
    out_dir = normalize_run_dir(args.out_dir, runs_root)

    reset_run_directory(out_dir)
    validate_engine_payload(engine_dir)
    write_input_files(parsed, xyz_path, out_dir)
    run_engine(engine_dir, out_dir)

    outputs = load_outputs(out_dir)
    tables = compute_tof_tables(
        outputs["event"],
        outputs["site"],
        parsed["products"],
        outputs["total_time"],
        outputs["nsurf"],
    )

    write_csv(outputs["cov"], out_dir / "coverage.csv")
    write_csv(tables["tof"], out_dir / "tof.csv")
    write_csv(tables["site_tof"], out_dir / "site_tof.csv")

    plot_coverage(outputs["cov"], out_dir / "coverage.png")
    plot_tof(tables["tof"], out_dir / "tof.png")

    print(f"Run completed: {out_dir}")
    print(f"Coverage plot: {out_dir / 'coverage.png'}")
    print(f"TOF plot: {out_dir / 'tof.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
