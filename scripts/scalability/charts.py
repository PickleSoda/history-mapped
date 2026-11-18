"""Charts for docs/architecture/scalability.md from bench.py's results CSV.

    .venv/bin/python scripts/scalability/charts.py output/scalability/results.csv \
        output/scalability/prod-calibration.csv docs/architecture/scalability

Server sizes are ordered, so they take the one-hue ordinal ramp (blue, light =
small, dark = large; checked with the dataviz skill's validator, --ordinal).
Each line is labeled at its right end and a legend sits above. Every panel in a
figure shares one log scale, so panels compare directly; there are no dual axes.
Past today's 641k entities a light band marks the synthetic (copied) datasets.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter, NullLocator  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BAND = "#f3f2ee"
TIER_COLORS = {"S": "#86b6ef", "M": "#3987e5", "L": "#1c5cab", "XL": "#0d366b",
               "S-do": "#86b6ef", "M-do": "#3987e5"}
TIER_NAMES = {"S": "S  1 vCPU / 2 GB", "M": "M  2 vCPU / 4 GB", "L": "L  4 vCPU / 8 GB", "XL": "XL  8 vCPU / 16 GB",
              "S-do": "S  1 vCPU / 2 GB at droplet speed", "M-do": "M  2 vCPU / 4 GB at droplet speed"}
FULL_SPEED = ["S", "M", "L", "XL"]
DROPLET = ["S-do", "M-do"]
TODAY = 641_473  # entities on 2026-11-18
X_TICKS = [36_000, 100_000, 300_000, 1_000_000, 2_500_000]
LOG_TICKS = [0.1, 0.3, 1, 3, 10, 30, 100, 300, 1_000, 3_000, 10_000, 30_000, 100_000, 300_000]

QUERY_TITLES = {
    "list_europe_1600": "“Notable here” list, Europe 1600",
    "list_world_-50": "“Notable here” list, world 50 BCE",
    "search_ro": "Search “ro” (prefix)",
    "search_rome": "Search “rome”",
    "search_charles": "Search “charles” (fuzzy)",
    "tags": "Tag list with counts",
    "entity_detail": "Entity page",
    "tile_z0": "Map tile, whole world (z0)",
    "tile_z6": "Map tile, Italy (z6)",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "axes.titlesize": 9.5,
    "axes.titleweight": "bold",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


# ── data ───────────────────────────────────────────────────────────────────

def load(path: str) -> list[dict]:
    return list(csv.DictReader(open(path, newline="")))


def series(rows, query: str, mode: str, tiers, field: str = "ms") -> dict[str, list[tuple[int, float]]]:
    """{tier: [(entities, value), ...]} sorted by entities; timeouts skipped."""
    out = defaultdict(list)
    for r in rows:
        if r["tier"] in tiers and r["query"] == query and r["mode"] == mode and r[field] not in ("", "nan"):
            value = float(r[field])
            if not math.isnan(value):
                out[r["tier"]].append((int(r["entities"]), value))
    return {t: sorted(v) for t, v in out.items()}


def load_prod(path: str) -> dict[str, float]:
    """query -> warm ms measured on the production droplet (calibrate.py --parse)."""
    out = {}
    for line in open(path):
        name, _cold, warm = line.strip().split(",")
        out[name] = float(warm)
    return out


# ── formatting ─────────────────────────────────────────────────────────────

def entity_fmt(x, _pos=None) -> str:
    if x >= 1_000_000:
        return f"{x / 1_000_000:g}M"
    if x >= 1_000:
        return f"{x / 1_000:g}k"
    return f"{x:g}"


def ms_fmt(y, _pos=None) -> str:
    if y >= 1000:
        return f"{y / 1000:g} s"
    return f"{y:g} ms"


def style_axes(ax, yfmt=ms_fmt, log_y: bool = True) -> None:
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(X_TICKS))
    ax.xaxis.set_major_formatter(FuncFormatter(entity_fmt))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    if log_y:
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(FixedLocator(LOG_TICKS))
        ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(yfmt))
    ax.grid(True, which="major", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0, labelsize=8)
    ax.axvspan(TODAY * 1.0, 4_000_000, color=BAND, zorder=0, linewidth=0)
    ax.axvline(TODAY, color=AXIS, linewidth=0.8, zorder=1)
    ax.set_xlim(30_000, 3_400_000)


def log_limits(values: list[float], pad: float = 1.6) -> tuple[float, float]:
    lo, hi = min(values), max(values)
    return lo / pad, hi * pad


def plot_tiers(ax, data, tiers) -> list[tuple[str, float, float]]:
    ends = []
    for tier in tiers:
        if tier not in data:
            continue
        xs, ys = zip(*data[tier])
        ax.plot(xs, ys, color=TIER_COLORS[tier], linewidth=2, marker="o", markersize=4.5,
                markeredgecolor=SURFACE, markeredgewidth=1.2, solid_capstyle="round", zorder=3)
        ends.append((tier.removesuffix("-do"), xs[-1], ys[-1]))
    return ends


def label_ends(fig, ax, ends, min_px: float = 11.0) -> None:
    """Direct labels at the right end of each line, pushed apart vertically."""
    if not ends:
        return
    fig.canvas.draw()
    pts = sorted(((ax.transData.transform((x, y))[1], name, x, y) for name, x, y in ends))
    placed: list[float] = []
    for py, *_ in pts:
        placed.append(max(py, placed[-1] + min_px) if placed else py)
    # Re-centre so the block sits on the lines' mean height, not drifting upwards.
    shift = (sum(p for p, *_ in pts) - sum(placed)) / len(placed)
    placed = [p + shift for p in placed]
    for (py, name, x, y), target in zip(pts, placed):
        ax.annotate(name, (x, y), xytext=(6, (target - py) * 72 / fig.dpi), textcoords="offset points",
                    va="center", fontsize=8, color=INK_2, fontweight="bold")


def legend(fig, tiers, y: float, extra: list | None = None) -> None:
    handles = [plt.Line2D([], [], color=TIER_COLORS[t], linewidth=2, marker="o", markersize=4.5,
                          markeredgecolor=SURFACE) for t in tiers]
    names = [TIER_NAMES[t] for t in tiers]
    for handle, name in extra or []:
        handles.append(handle)
        names.append(name)
    fig.legend(handles, names, loc="upper left", ncol=len(names), frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.005, y), labelcolor=INK_2, handlelength=1.8, columnspacing=1.6)


def top(fig, inches: float) -> float:
    """Figure-fraction y that sits `inches` below the top edge."""
    return 1 - inches / fig.get_figheight()


def header(fig, title: str, subtitle: str) -> None:
    fig.text(0.012, top(fig, 0.08), title, fontsize=12.5, fontweight="bold", color=INK, va="top")
    fig.text(0.012, top(fig, 0.36), subtitle, fontsize=9, color=INK_2, va="top")


# ── figures ────────────────────────────────────────────────────────────────

def small_multiples(rows, mode: str, tiers, title: str, subtitle: str, out: Path,
                    prod: dict[str, float] | None = None) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(10.5, 9.0), sharey=True)
    panels = []
    values = []
    for ax, (query, qtitle) in zip(axes.flat, QUERY_TITLES.items()):
        style_axes(ax)
        data = series(rows, query, mode, tiers)
        values += [y for pts in data.values() for _, y in pts]
        ends = plot_tiers(ax, data, tiers)
        if prod and query in prod:
            ax.plot([TODAY], [prod[query]], marker="D", markersize=6.5, markerfacecolor=SURFACE,
                    markeredgecolor=INK, markeredgewidth=1.4, linestyle="none", zorder=4)
            values.append(prod[query])
        ax.set_title(qtitle, loc="left", pad=6)
        panels.append((ax, ends))
    axes[0][0].set_ylim(*log_limits(values))
    for ax in axes[:, 0]:
        ax.set_ylabel("database time per request", fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("entities in the atlas", fontsize=8)
    axes[0][0].annotate("today", (TODAY, 0), xycoords=("data", "axes fraction"), xytext=(-3, 3),
                        textcoords="offset points", fontsize=7.5, color=MUTED, va="bottom", ha="right")
    axes[0][0].annotate("synthetic copies", (1_500_000, 0), xycoords=("data", "axes fraction"),
                        xytext=(0, 3), textcoords="offset points", fontsize=7.5, color=MUTED, va="bottom",
                        ha="center")
    header(fig, title, subtitle)
    extra = None
    if prod:
        extra = [(plt.Line2D([], [], marker="D", markersize=6.5, markerfacecolor=SURFACE, markeredgecolor=INK,
                             markeredgewidth=1.4, linestyle="none"), "the live droplet, measured")]
    legend(fig, tiers, y=top(fig, 0.6), extra=extra)
    fig.tight_layout(rect=(0, 0, 1, top(fig, 0.9)), h_pad=1.6)
    for ax, ends in panels:
        label_ends(fig, ax, ends)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def two_panel(rows, query: str, mode: str, field: str, title: str, subtitle: str, out: Path,
              yfmt=ms_fmt, ylabel: str = "") -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3), sharey=True)
    values = []
    panels = []
    for ax, tiers, ptitle in ((axes[0], FULL_SPEED, "Full-speed cores (benchmark host)"),
                              (axes[1], DROPLET, "Droplet-speed cores (calibrated to the live droplet)")):
        style_axes(ax, yfmt=yfmt)
        data = series(rows, query, mode, tiers, field)
        values += [y for pts in data.values() for _, y in pts]
        panels.append((ax, plot_tiers(ax, data, tiers)))
        ax.set_title(ptitle, loc="left", pad=6)
        ax.set_xlabel("entities in the atlas", fontsize=8)
    axes[0].set_ylim(*log_limits(values, pad=1.4))
    axes[0].set_ylabel(ylabel, fontsize=8)
    header(fig, title, subtitle)
    legend(fig, FULL_SPEED, y=top(fig, 0.6))
    fig.tight_layout(rect=(0, 0, 1, top(fig, 0.9)))
    for ax, ends in panels:
        label_ends(fig, ax, ends)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def db_size(rows, out: Path) -> None:
    sizes = sorted({(int(r["entities"]), int(r["db_bytes"])) for r in rows})
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    style_axes(ax, yfmt=lambda y, _p=None: f"{y / 1e9:g} GB" if y >= 1e9 else f"{y / 1e6:g} MB")
    ax.yaxis.set_major_locator(FixedLocator([3e8, 1e9, 3e9, 1e10, 3e10]))
    xs, ys = zip(*sizes)
    ax.plot(xs, ys, color="#2a78d6", linewidth=2, marker="o", markersize=4.5, markeredgecolor=SURFACE,
            markeredgewidth=1.2, zorder=3)
    for x, y in (sizes[0], sizes[-1]):
        ax.annotate(f"{y / 1e9:.1f} GB" if y >= 1e9 else f"{y / 1e6:.0f} MB", (x, y), xytext=(0, 9),
                    textcoords="offset points", ha="center", fontsize=8, color=INK_2)
    ax.set_ylim(2e8, 3e10)
    ax.set_xlabel("entities in the atlas", fontsize=8)
    header(fig, "Database size", "On disk, with indexes and the tile table: about 5-6 KB per entity.")
    fig.tight_layout(rect=(0, 0, 1, top(fig, 0.65)))
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main() -> None:
    rows = load(sys.argv[1])
    prod = load_prod(sys.argv[2])
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    small_multiples(rows, "warm", FULL_SPEED, "Warm requests: data already in memory",
                    "Median of four repeats. Full-speed cores; four server sizes.", out / "latency-warm.png")
    small_multiples(rows, "cold", FULL_SPEED, "Cold requests: first request after a restart",
                    "Postgres restarted and its files dropped from the OS cache, so every page comes from disk.",
                    out / "latency-cold.png")
    small_multiples(rows, "mixed", FULL_SPEED, "Mixed traffic: every request in turn",
                    "Round-robin over all requests, so they compete for the cache. Full-speed cores.",
                    out / "latency-mixed.png")
    # Only the 1 vCPU tier: a CPU quota is shared by the container, so on the
    # 2 vCPU droplet-speed tier one query borrows the second vCPU's share and
    # runs about twice as fast as on a real 2 vCPU droplet. Aggregate measures
    # (throughput, parallel refresh) are not affected.
    small_multiples(rows, "warm", ["S-do"], "Warm requests at droplet speed, 1 vCPU / 2 GB",
                    "CPU cut to one sixth of a host core, which reproduces the droplet. Diamonds: the live droplet "
                    "at 641k.", out / "latency-droplet.png", prod=prod)
    two_panel(rows, "all_read", "throughput", "qps", "Throughput with eight concurrent clients",
              "Requests per second over 30 s, a random mix of all requests.", out / "throughput.png",
              yfmt=lambda y, _p=None: f"{y:g}", ylabel="requests per second")
    two_panel(rows, "all_read", "throughput", "p95", "Slowest 5 % of requests under that load",
              "95th-percentile database time per request during the throughput run.", out / "p95-under-load.png",
              ylabel="p95 database time")
    two_panel(rows, "tiles_refresh", "cold", "ms", "Tile-table refresh",
              "REFRESH MATERIALIZED VIEW CONCURRENTLY tiles.atlas_features, from a cold cache.",
              out / "tile-refresh.png", ylabel="refresh time")
    db_size(rows, out / "db-size.png")


if __name__ == "__main__":
    main()
