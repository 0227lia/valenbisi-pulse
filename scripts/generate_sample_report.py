from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.valenbisi import (  # noqa: E402
    CRITICAL_STATUSES,
    assign_zones,
    classify_station_status,
    load_valenbisi_data,
    recommend_rebalancing,
    summarize_zones,
)


def main() -> None:
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    stations, source = load_valenbisi_data(prefer_live=False)
    stations = classify_station_status(stations)
    stations = assign_zones(stations, n_clusters=7)
    zones = summarize_zones(stations)
    plan = recommend_rebalancing(stations)

    summary = {
        "data_source": source,
        "stations": int(len(stations)),
        "total_capacity": int(stations["capacity"].sum()),
        "available_bikes": int(stations["free_bikes"].sum()),
        "free_docks": int(stations["empty_slots"].sum()),
        "critical_stations": int(stations["status"].isin(CRITICAL_STATUSES).sum()),
        "estimated_zones": int(zones["zone_id"].nunique()),
        "recommended_movements": int(len(plan)),
        "scope": "Muestra local determinista; los valores en vivo cambian con cada consulta a la API.",
    }

    (reports_dir / "sample_snapshot.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    zones.to_csv(reports_dir / "sample_zone_summary.csv", index=False)
    plan.to_csv(reports_dir / "sample_rebalancing.csv", index=False)


if __name__ == "__main__":
    main()
