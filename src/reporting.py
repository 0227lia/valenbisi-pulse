"""Static, reproducible reporting artifacts for the offline Valenbisi sample."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

INK = "#172033"
MUTED = "#64748B"
GRID = "#DCE3EA"
TEAL = "#0F766E"
CORAL = "#E85D4A"
GOLD = "#D97706"
BLUE = "#2563EB"

RISK_COLORS = {
    "bajo": "#94A3B8",
    "moderado": BLUE,
    "alto": GOLD,
    "crítico": CORAL,
}


def _apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.titlecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.edgecolor": GRID,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _save(fig: plt.Figure, directory: Path, filename: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fig.savefig(directory / filename, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _draw_plan_lines(ax: plt.Axes, stations: pd.DataFrame, plan: pd.DataFrame) -> None:
    if plan.empty:
        return
    coordinates = stations.set_index("station_id")[["longitude", "latitude"]]
    for _, movement in plan.iterrows():
        origin = coordinates.loc[movement["origin_id"]]
        destination = coordinates.loc[movement["destination_id"]]
        ax.annotate(
            "",
            xy=(destination["longitude"], destination["latitude"]),
            xytext=(origin["longitude"], origin["latitude"]),
            arrowprops={"arrowstyle": "->", "color": TEAL, "alpha": 0.65, "linewidth": 1.2},
            zorder=1,
        )


def plot_operations_dashboard(
    stations: pd.DataFrame,
    zones: pd.DataFrame,
    plan: pd.DataFrame,
    stress_scenarios: pd.DataFrame,
    figure_dir: Path,
) -> None:
    _apply_style()
    fig, axes = plt.subplots(2, 2, figsize=(15, 10.5))

    ax = axes[0, 0]
    _draw_plan_lines(ax, stations, plan)
    for risk_band, frame in stations.groupby("risk_band", observed=True):
        ax.scatter(
            frame["longitude"],
            frame["latitude"],
            s=38 + frame["station_risk_score"] * 1.5,
            color=RISK_COLORS[risk_band],
            edgecolor="white",
            linewidth=0.6,
            alpha=0.9,
            label=risk_band.title(),
            zorder=2,
        )
    ax.set_title("Riesgo de estación y red de movimientos óptimos", loc="left")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.legend(frameon=False, ncol=2, fontsize=8)

    ax = axes[0, 1]
    top = stations.nlargest(12, "station_risk_score").sort_values("station_risk_score")
    bars = ax.barh(top["name"], top["station_risk_score"], color=CORAL)
    for bar, pressure in zip(bars, top["local_pressure"], strict=True):
        ax.text(
            bar.get_width() + 1,
            bar.get_y() + bar.get_height() / 2,
            f"presión local {pressure:.0%}",
            va="center",
            color=MUTED,
            fontsize=7.5,
        )
    ax.set_xlim(0, min(105, float(top["station_risk_score"].max()) + 16))
    ax.set_xlabel("Score de riesgo de snapshot")
    ax.set_title("Estaciones que requieren revisión", loc="left")
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)

    ax = axes[1, 0]
    scatter = ax.scatter(
        zones["critical_share"],
        zones["mean_station_risk"],
        s=60 + zones["capacity"] * 2,
        c=zones["mean_local_pressure"],
        cmap="YlOrRd",
        edgecolor="white",
        linewidth=0.7,
        alpha=0.9,
    )
    for _, row in zones.iterrows():
        ax.annotate(
            row["zone"],
            (row["critical_share"], row["mean_station_risk"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Proporción de estaciones críticas")
    ax.set_ylabel("Riesgo medio de estación")
    ax.set_title("Zonas KMeans: exposición y riesgo", loc="left")
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("Presión local media")
    ax.grid(color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)

    ax = axes[1, 1]
    display = stress_scenarios.copy()
    labels = ["Base", *display["scenario"].tolist()]
    critical_values = [
        int(display["baseline_critical_stations"].iloc[0]),
        *display["scenario_critical_stations"],
    ]
    colors = [MUTED, TEAL, GOLD][: len(labels)]
    bars = ax.bar(labels, critical_values, color=colors)
    for bar, value in zip(bars, critical_values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.5, str(value), ha="center", fontsize=9)
    ax.set_ylabel("Estaciones críticas")
    ax.set_title("Pruebas de estrés conservativas", loc="left")
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)

    fig.suptitle(
        "Valenbisi Pulse | panel de operaciones de snapshot",
        x=0.075,
        ha="left",
        fontsize=17,
        weight="bold",
    )
    fig.text(
        0.075,
        0.012,
        (
            "Muestra local reproducible. Riesgo y estrés son diagnósticos de snapshot, "
            "no predicciones de demanda ni rutas reales."
        ),
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    _save(fig, figure_dir, "operations_decision_dashboard.png")


def plot_risk_scorecard(stations: pd.DataFrame, figure_dir: Path) -> None:
    _apply_style()
    top = stations.nlargest(10, "station_risk_score").copy()
    table = pd.DataFrame(
        {
            "Estación": top["name"],
            "Estado": top["status"],
            "Riesgo": top["station_risk_score"].map(lambda value: f"{value:.1f}"),
            "Presión local": top["local_pressure"].map(lambda value: f"{value:.0%}"),
            "Bicis": top["free_bikes"].astype(int),
            "Anclajes": top["empty_slots"].astype(int),
        }
    )
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.axis("off")
    table_plot = ax.table(
        cellText=table.values,
        colLabels=table.columns,
        loc="center",
        cellLoc="left",
        colLoc="left",
        colWidths=[0.34, 0.19, 0.12, 0.16, 0.09, 0.10],
    )
    table_plot.auto_set_font_size(False)
    table_plot.set_fontsize(9)
    table_plot.scale(1, 1.55)
    for (row, _column), cell in table_plot.get_celld().items():
        cell.set_edgecolor("white")
        if row == 0:
            cell.set_facecolor(INK)
            cell.set_text_props(color="white", weight="bold")
        elif row % 2:
            cell.set_facecolor("#F8FAFC")
        else:
            cell.set_facecolor("#EAF4F2")
    ax.set_title("Scorecard de riesgo del snapshot", loc="left", color=INK, pad=14, weight="bold")
    _save(fig, figure_dir, "risk_scorecard.png")
