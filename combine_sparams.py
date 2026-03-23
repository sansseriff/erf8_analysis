"""
Create _C files from base VNA CSV files with duplicate columns removed (keep first occurrence).

For CH1_CH3 files missing S24 (where a duplicate S34 was saved instead):
- the duplicate S34 is dropped
- S24 is filled in from S42 (valid by reciprocity for passive networks)
- S24 is inserted in the canonical position: between S14 and S34
"""

import re
import pandas as pd
from pathlib import Path
from io import StringIO


def parse_vna_csv(filepath: Path) -> tuple[list[str], str, pd.DataFrame]:
    header_lines = []
    section_name = None
    col_header = None
    data_lines = []

    with open(filepath) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("!") or line.strip() == "":
                header_lines.append(line)
            elif line.startswith("BEGIN "):
                section_name = line[len("BEGIN "):]
            elif line.startswith("END"):
                break
            elif col_header is None:
                col_header = line
            else:
                data_lines.append(line)

    raw = "\n".join([col_header] + data_lines)
    df = pd.read_csv(StringIO(raw))
    return header_lines, section_name, df


def write_vna_csv(filepath: Path, header_lines: list[str], section_name: str, df: pd.DataFrame):
    with open(filepath, "w") as f:
        for line in header_lines:
            f.write(line + "\n")
        f.write(f"BEGIN {section_name}\n")
        f.write(",".join(df.columns) + "\n")
        for _, row in df.iterrows():
            parts = []
            for val in row:
                if pd.isna(val):
                    parts.append("")
                else:
                    parts.append(str(val))
            f.write(",".join(parts) + "\n")
        f.write("END\n")


def fix_s24_from_s42(df: pd.DataFrame) -> pd.DataFrame:
    """
    For files where S24 is absent and a duplicate S34 was recorded instead:
    insert S24(REAL) and S24(IMAG) copied from S42, placed between S14(IMAG) and S34(REAL).
    """
    cols = list(df.columns)
    if "S24(REAL)" in cols or "S42(REAL)" not in cols or "S34(REAL)" not in cols:
        return df  # already has S24, or can't fix

    insert_pos = cols.index("S34(REAL)")  # insert just before S34
    df.insert(insert_pos, "S24(REAL)", df["S42(REAL)"].values)
    df.insert(insert_pos + 1, "S24(IMAG)", df["S42(IMAG)"].values)
    return df


def process_folder(folder: Path):
    print(f"\nProcessing {folder.name}/")
    base_files = [f for f in sorted(folder.glob("*.csv"))
                  if not f.stem.endswith("2") and not f.stem.endswith("_C")]

    for base_path in base_files:
        out_path = base_path.with_name(base_path.stem + "_C" + base_path.suffix)
        header, section, df = parse_vna_csv(base_path)

        # Drop columns pandas auto-renamed due to duplicates (e.g. S34(REAL).1)
        df = df[[c for c in df.columns if not re.search(r'\.\d+$', c)]]

        # Fill missing S24 from S42 (valid by reciprocity for passive networks)
        had_s24 = "S24(REAL)" in df.columns
        df = fix_s24_from_s42(df)
        note = "" if had_s24 else " [S24 filled from S42]"

        write_vna_csv(out_path, header, section, df)
        note = "" if had_s24 else " [S24 filled from S42]"
        print(f"  {base_path.name} -> {out_path.name}  ({len(df)} rows, {len(df.columns)} cols){note}")


if __name__ == "__main__":
    data_dir = Path(__file__).parent / "data"
    for folder_name in ["CH1_CH2", "CH1_CH3", "CH3_CH4"]:
        process_folder(data_dir / folder_name)
    print("\nDone.")
