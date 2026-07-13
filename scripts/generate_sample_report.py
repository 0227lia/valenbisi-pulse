"""Rebuild reproducible operational artifacts from the bundled Valenbisi sample."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operations import (  # noqa: E402
    add_local_risk_context,
    assess_snapshot_quality,
    simulate_commute_stress,
    summarize_operational_zones,
)
from src.optimization import optimize_rebalancing  # noqa: E402
from src.reporting import plot_operations_dashboard, plot_risk_scorecard  # noqa: E402
from src.valenbisi import (  # noqa: E402
    CRITICAL_STATUSES,
    assign_zones,
    classify_station_status,
    load_valenbisi_data,
    recommend_rebalancing,
)


def write_executive_summary(
    stations: pd.DataFrame,
    optimized_plan: pd.DataFrame,
    optimization_summary: dict[str, object],
    stress_scenarios: pd.DataFrame,
    output_path: Path,
) -> None:
    top_risk = stations.nlargest(8, "station_risk_score")
    baseline_critical = int(stations["status"].isin(CRITICAL_STATUSES).sum())
    lines = [
        "# Resumen operativo de muestra",
        "",
        (
            "Este informe se genera desde `data/sample_valenbisi.csv`, una muestra local determinista. "
            "No describe la situación actual de la red y sirve para verificar el pipeline completo."
        ),
        "",
        "## Snapshot",
        "",
        f"- Estaciones: {len(stations)}.",
        f"- Capacidad declarada: {int(stations['capacity'].sum())} plazas.",
        f"- Bicicletas disponibles: {int(stations['free_bikes'].sum())}.",
        f"- Estaciones críticas con los umbrales base: {baseline_critical}.",
        "",
        "## Riesgo de snapshot",
        "",
    ]
    for _, row in top_risk.iterrows():
        lines.append(
            f"- **{row['name']}**: riesgo={row['station_risk_score']:.1f}, estado={row['status']}, "
            f"presión local={row['local_pressure']:.0%}."
        )

    lines.extend(
        [
            "",
            "## Plan de transporte de coste mínimo",
            "",
            f"- Orígenes elegibles: {optimization_summary['eligible_sources']}.",
            f"- Destinos elegibles: {optimization_summary['eligible_destinations']}.",
            f"- Arcos por debajo de la distancia máxima: {optimization_summary['eligible_arcs']}.",
            f"- Bicicletas movidas: {optimization_summary['bikes_moved']} de "
            f"{optimization_summary['total_need']} unidades de necesidad modelada.",
            f"- Cobertura de necesidad modelada: {optimization_summary['service_share']:.1%}.",
            f"- Transporte acumulado: {optimization_summary['transport_km_bikes']:.2f} bici-km.",
            "",
            "## Pruebas de estrés",
            "",
        ]
    )
    for _, row in stress_scenarios.iterrows():
        lines.append(
            f"- {row['scenario']}: se desplazan {int(row['bikes_shifted'])} bicicletas dentro de la red; "
            f"estaciones críticas={int(row['scenario_critical_stations'])} "
            f"(nuevas={int(row['newly_critical_stations'])})."
        )

    lines.extend(
        [
            "",
            "## Límites",
            "",
            (
                "El plan usa distancia en línea recta y una instantánea. No incorpora tráfico, rutas reales, "
                "capacidad de vehículos, demanda histórica, eventos ni costes laborales. Los escenarios de "
                "estrés conservan bicicletas de manera determinista y no son predicciones. Cualquier uso "
                "operativo requiere datos actualizados y validación del operador."
            ),
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    reports_dir = ROOT / "reports"
    figure_dir = reports_dir / "figures"
    reports_dir.mkdir(exist_ok=True)

    stations, source = load_valenbisi_data(prefer_live=False)
    stations = classify_station_status(stations)
    stations = assign_zones(stations, n_clusters=7)
    stations = add_local_risk_context(stations, neighbors=4)
    zones = summarize_operational_zones(stations)
    quality = assess_snapshot_quality(stations)
    optimized_plan, optimization = optimize_rebalancing(stations)
    greedy_plan = recommend_rebalancing(stations)

    stress_rows = []
    for direction in ("to_core", "from_core"):
        _, summary = simulate_commute_stress(
            stations,
            direction=direction,
            shock_ratio=0.15,
            core_radius_km=2.0,
            min_units=2,
            min_ratio=0.10,
        )
        stress_rows.append(summary)
    stress_scenarios = pd.DataFrame(stress_rows)

    summary = {
        "data_source": source,
        "stations": int(len(stations)),
        "total_capacity": int(stations["capacity"].sum()),
        "available_bikes": int(stations["free_bikes"].sum()),
        "free_docks": int(stations["empty_slots"].sum()),
        "critical_stations": int(stations["status"].isin(CRITICAL_STATUSES).sum()),
        "estimated_zones": int(zones["zone_id"].nunique()),
        "quality_checks_requiring_review": int((quality["status"] == "revisar").sum()),
        "minimum_cost_rebalancing": asdict(optimization),
        "scope": "Muestra local determinista; los valores en vivo cambian con cada consulta a la API.",
    }

    (reports_dir / "sample_snapshot.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    stations.to_csv(reports_dir / "sample_station_risk.csv", index=False)
    zones.to_csv(reports_dir / "sample_zone_summary.csv", index=False)
    quality.to_csv(reports_dir / "sample_quality_checks.csv", index=False)
    optimized_plan.to_csv(reports_dir / "sample_rebalancing.csv", index=False)
    greedy_plan.to_csv(reports_dir / "sample_rebalancing_greedy.csv", index=False)
    stress_scenarios.to_csv(reports_dir / "sample_stress_scenarios.csv", index=False)
    write_executive_summary(
        stations,
        optimized_plan,
        asdict(optimization),
        stress_scenarios,
        reports_dir / "executive_summary.md",
    )
    plot_operations_dashboard(stations, zones, optimized_plan, stress_scenarios, figure_dir)
    plot_risk_scorecard(stations, figure_dir)
    print(f"Rebuilt sample report in {reports_dir}")


if __name__ == "__main__":
    main()
