import base64
import io
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from snsphd.viz import phd_style

matplotlib.use("Agg")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")


colors, swatches = phd_style(jupyterStyle=True, data_width=0.7)

# ---------------------------------------------------------------------------
# VNA endpoints
# ---------------------------------------------------------------------------


@app.get("/api/vna/folders")
def vna_folders():
    folders = sorted(
        d.name
        for d in DATA_DIR.iterdir()
        if d.is_dir() and re.match(r"CH\d+_CH\d+", d.name)
    )
    return folders


@app.get("/api/vna/files")
def vna_files(folder: str):
    path = DATA_DIR / folder
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")
    files = sorted(
        f.name
        for f in path.iterdir()
        if f.suffix.lower() == ".csv" and f.stem.endswith("_C")
    )
    return files


@app.get("/api/vna/sparams")
def vna_sparams(folder: str, file: str):
    path = DATA_DIR / folder / file
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    header_row = _find_vna_header(path)
    if header_row is None:
        raise HTTPException(status_code=422, detail="Could not parse VNA header")
    cols = [c.strip() for c in header_row.split(",")]
    sparams = []
    for col in cols:
        m = re.match(r"(S\d+)\(REAL\)", col)
        if m:
            sparams.append(m.group(1))
    return sparams


# ---------------------------------------------------------------------------
# Pulse endpoints
# ---------------------------------------------------------------------------


@app.get("/api/pulse/subfolders")
def pulse_subfolders():
    folders = sorted(
        d.name for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith("Pulse_")
    )
    return folders


@app.get("/api/pulse/files")
def pulse_files(subfolder: str):
    path = DATA_DIR / subfolder
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Subfolder not found")
    files = sorted(f.name for f in path.iterdir() if f.suffix.lower() == ".csv")
    return files


# ---------------------------------------------------------------------------
# Shared constants and models
# ---------------------------------------------------------------------------

PALETTE = [
    "#a6cee3",
    "#1f78b4",
    "#b2df8a",
    "#33a02c",
    "#fb9a99",
    "#e31a1c",
    "#fdbf6f",
    "#ff7f00",
    "#cab2d6",
    "#6a3d9a",
    "#ffff99",
    "#b15928",
]

CHANNEL_LABELS = {
    "C1": "Raw Original",
    "C2": "Raw Transmission",
    "C3": "Raw Adjacent Transmission",
    "C4": "Raw Adjacent Reflection",
    "C5": "Avg Original",
    "C6": "Avg Transmission",
    "C7": "Avg Adjacent Transmission",
    "C8": "Avg Adjacent Reflection",
}


class VnaLine(BaseModel):
    folder: str
    file: str
    sparam: str


class PulseLine(BaseModel):
    subfolder: str
    file: str
    channel: str


class PlotRequest(BaseModel):
    type: str  # "vna" or "pulse"
    lines: list[dict]
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None


class MeasureRequest(BaseModel):
    type: str
    lines: list[dict]
    measure_a: int  # index into lines
    measure_b: int
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None


# ---------------------------------------------------------------------------
# Plot endpoint
# ---------------------------------------------------------------------------


@app.post("/api/plot")
def plot(req: PlotRequest):
    if req.type not in ("vna", "pulse"):
        raise HTTPException(status_code=400, detail="type must be 'vna' or 'pulse'")
    fig, _ax, _pulse_data = _build_figure(
        req.type, req.lines, req.x_min, req.x_max, req.y_min, req.y_max
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


# ---------------------------------------------------------------------------
# Measure endpoint
# ---------------------------------------------------------------------------


@app.post("/api/measure")
def measure(req: MeasureRequest):
    if req.type != "pulse":
        raise HTTPException(
            status_code=400, detail="Measure only supported for pulse mode"
        )
    n = len(req.lines)
    if req.measure_a >= n or req.measure_b >= n:
        raise HTTPException(status_code=400, detail="Line index out of range")

    fig, ax, pulse_data = _build_figure(
        req.type, req.lines, req.x_min, req.x_max, req.y_min, req.y_max
    )

    amp_a = pulse_data[req.measure_a]
    amp_b = pulse_data[req.measure_b]

    peak_a = float(amp_a[np.argmax(np.abs(amp_a))])
    peak_b = float(amp_b[np.argmax(np.abs(amp_b))])

    if peak_b == 0:
        raise HTTPException(
            status_code=422, detail="Line B has zero amplitude — cannot compute ratio"
        )

    ratio = abs(peak_a) / abs(peak_b)
    db = float(20.0 * np.log10(ratio)) if ratio > 0 else float("-inf")

    # Draw horizontal lines at the signed peaks, matching line colors
    color_a = PALETTE[req.measure_a % len(PALETTE)]
    color_b = PALETTE[req.measure_b % len(PALETTE)]

    ax.axhline(peak_a, color=color_a, linestyle="--", linewidth=1.2, alpha=0.8)
    ax.axhline(peak_b, color=color_b, linestyle="--", linewidth=1.2, alpha=0.8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    image_b64 = base64.b64encode(buf.read()).decode()

    return {"db": db, "max_a": peak_a, "max_b": peak_b, "image": image_b64}


# ---------------------------------------------------------------------------
# Shared figure builder
# ---------------------------------------------------------------------------


def _build_figure(
    req_type: str,
    lines_dicts: list[dict],
    x_min: float | None = None,
    x_max: float | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> tuple[plt.Figure, plt.Axes, list[np.ndarray]]:
    """Build the matplotlib figure. Returns (fig, ax, amp_arrays) where amp_arrays
    contains the amplitude array for each pulse line (empty list for VNA)."""
    fig, ax = plt.subplots(figsize=(10, 6))
    amp_arrays: list[np.ndarray] = []

    if req_type == "vna":
        ax.set_xscale("log")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("|S| (dB)")
        ax.set_title("VNA S-Parameter Comparison")
        for i, line_dict in enumerate(lines_dicts):
            line = VnaLine(**line_dict)
            df = _load_vna(line.folder, line.file)
            freq_mhz = pd.to_numeric(df["Freq(Hz)"], errors="coerce") / 1e6
            real_col = f"{line.sparam}(REAL)"
            imag_col = f"{line.sparam}(IMAG)"
            if real_col not in df.columns:
                raise HTTPException(status_code=422, detail=f"{real_col} not in file")
            real = pd.to_numeric(df[real_col], errors="coerce")
            imag = pd.to_numeric(df[imag_col], errors="coerce")
            mask = freq_mhz.notna() & real.notna() & imag.notna()
            mag = np.sqrt(real[mask] ** 2 + imag[mask] ** 2)
            mag_db = 20 * np.log10(mag.clip(lower=1e-12))
            ax.plot(freq_mhz[mask], mag_db, color=PALETTE[i % len(PALETTE)])
    else:
        ax.set_xlabel("Time (ns)")
        ax.set_ylabel("Amplitude (V)")
        ax.set_title("Pulse Comparison")
        for i, line_dict in enumerate(lines_dicts):
            line = PulseLine(**line_dict)
            df = _load_pulse(line.subfolder, line.file)
            col_idx = int(line.channel[1])  # C1→1, C2→2, …
            time_num = pd.to_numeric(df.iloc[:, 0], errors="coerce")
            amp_num = pd.to_numeric(df.iloc[:, col_idx], errors="coerce")
            mask = time_num.notna() & amp_num.notna()
            t = np.asarray(time_num[mask].values, dtype=float) * 1e9
            a = np.asarray(amp_num[mask].values, dtype=float)
            ax.plot(t, a, color=PALETTE[i % len(PALETTE)])
            amp_arrays.append(a)

    ax.grid(True, alpha=0.3)
    if x_min is not None or x_max is not None:
        ax.set_xlim(left=x_min, right=x_max)
    if y_min is not None or y_max is not None:
        ax.set_ylim(bottom=y_min, top=y_max)
    fig.tight_layout()
    return fig, ax, amp_arrays


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_vna_header(path: Path) -> str | None:
    with open(path, encoding="utf-8", errors="replace") as f:
        found_begin = False
        for line in f:
            line = line.rstrip("\n")
            if not found_begin:
                if line.strip() == "BEGIN CH1_DATA":
                    found_begin = True
                continue
            return line
    return None


def _load_vna(folder: str, file: str) -> pd.DataFrame:
    path = DATA_DIR / folder / file
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {folder}/{file}")
    header_line_idx = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.strip() == "BEGIN CH1_DATA":
                header_line_idx = i + 1
                break
    if header_line_idx is None:
        raise HTTPException(status_code=422, detail=f"No BEGIN CH1_DATA in {file}")
    df = pd.read_csv(path, skiprows=header_line_idx, on_bad_lines="skip")
    return df


def _load_pulse(subfolder: str, file: str) -> pd.DataFrame:
    path = DATA_DIR / subfolder / file
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"File not found: {subfolder}/{file}"
        )
    col_names = ["time", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]
    df = pd.read_csv(path, header=None, names=col_names)
    return df


# ---------------------------------------------------------------------------
# Static frontend (production — only when dist/ exists)
# In dev, Vite runs separately and proxies /api to this server.
# ---------------------------------------------------------------------------

_DIST = Path("dist")
if _DIST.is_dir():
    # Serve static assets normally
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    # SPA catch-all: any unmatched route returns index.html
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        candidate = _DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
