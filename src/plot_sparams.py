#!/usr/bin/env python3
"""Plot S-parameters from Keysight CSV files.

Usage:
  uv run plot_sparams.py                        # load default plot_sparams.yaml
  uv run plot_sparams.py config.yaml            # load a specific YAML config
  uv run plot_sparams.py S12 file1.csv S21 file2.csv ...   # inline param/file pairs
"""

import sys
import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yaml

# Project root is one level up from this script's directory (src/)
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "plot_sparams.yaml"


def resolve_path(filepath: str) -> Path:
    """Resolve a path, falling back to project root if not found as-is."""
    p = Path(filepath)
    if p.exists():
        return p
    from_root = PROJECT_ROOT / filepath
    if from_root.exists():
        return from_root
    raise FileNotFoundError(
        f"File not found: '{filepath}' (also tried '{from_root}')"
    )


def load_sparam_csv(filepath: str) -> pd.DataFrame:
    """Load a Keysight S-parameter CSV, skipping comment/section header lines."""
    filepath = resolve_path(filepath)
    with open(filepath) as f:
        lines = f.readlines()

    # Find header row (starts with "Freq") and optional footer (e.g. "END")
    header_idx = next(
        i for i, line in enumerate(lines) if line.strip().startswith("Freq")
    )
    footer_idx = next(
        (i for i in range(header_idx + 1, len(lines))
         if not lines[i].strip() or not lines[i][0].lstrip("-").lstrip(".")[0:1].isdigit()),
        len(lines),
    )
    nrows = footer_idx - header_idx - 1  # exclude header itself

    df = pd.read_csv(filepath, skiprows=header_idx, nrows=nrows)
    df.columns = [c.strip() for c in df.columns]
    return df


def compute_magnitude_db(df: pd.DataFrame, param: str) -> pd.Series:
    """Convert REAL/IMAG columns for a given S-param key to magnitude in dB."""
    real_col = f"{param}(REAL)"
    imag_col = f"{param}(IMAG)"
    if real_col not in df.columns or imag_col not in df.columns:
        available = sorted(
            {re.match(r"(S\d+)", c).group(1) for c in df.columns if re.match(r"S\d+", c)}
        )
        raise ValueError(
            f"Parameter '{param}' not found. Available: {available}"
        )
    magnitude = np.sqrt(df[real_col] ** 2 + df[imag_col] ** 2)
    return 20 * np.log10(magnitude.clip(lower=1e-12))


def plot_from_entries(entries: list[dict]) -> None:
    """Plot multiple file+param pairs on a single axes.

    Each entry: {"file": str, "param": str, "label": str (optional)}
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for entry in entries:
        filepath = entry["file"]
        param = entry["param"].upper()
        label = entry.get("label") or f"{Path(filepath).stem} {param}"

        df = load_sparam_csv(filepath)
        freq_ghz = df["Freq(Hz)"] / 1e9
        mag_db = compute_magnitude_db(df, param)
        ax.plot(freq_ghz, mag_db, label=label)

    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("|S| (dB)")
    ax.set_title("S-Parameters")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def load_yaml_config(path: Path) -> list[dict]:
    """Load entries from a YAML config file."""
    with open(path) as f:
        config = yaml.safe_load(f)
    entries = config.get("plots", [])
    if not entries:
        raise ValueError(f"No 'plots' entries found in {path}")
    return entries


def parse_inline_pairs(args: list[str]) -> list[dict]:
    """Parse alternating param/file pairs from CLI args: S12 file1.csv S21 file2.csv ..."""
    if len(args) % 2 != 0:
        raise ValueError(
            "Inline args must be alternating param/file pairs: S12 file1.csv S21 file2.csv ..."
        )
    return [
        {"param": args[i], "file": args[i + 1]}
        for i in range(0, len(args), 2)
    ]


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        # No args: load default YAML
        if not DEFAULT_CONFIG.exists():
            print(f"No arguments given and no default config found at '{DEFAULT_CONFIG}'.")
            print("Create plot_sparams.yaml in the project root, or pass args directly.")
            print()
            print("Usage:")
            print("  uv run plot_sparams.py                          # uses plot_sparams.yaml")
            print("  uv run plot_sparams.py config.yaml              # uses a specific YAML")
            print("  uv run plot_sparams.py S12 file1.csv S21 file2.csv ...")
            sys.exit(1)
        entries = load_yaml_config(DEFAULT_CONFIG)
    elif len(args) == 1 and args[0].endswith(".yaml"):
        # Single .yaml arg: treat as config file
        entries = load_yaml_config(resolve_path(args[0]))
    else:
        # Alternating param/file pairs
        entries = parse_inline_pairs(args)

    plot_from_entries(entries)
