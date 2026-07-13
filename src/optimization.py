"""Minimum-cost transportation plan for a single Valenbisi station snapshot."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from src.valenbisi import haversine_km


@dataclass(frozen=True)
class RebalancingSummary:
    eligible_sources: int
    eligible_destinations: int
    eligible_arcs: int
    total_supply: int
    total_need: int
    bikes_moved: int
    unmet_need: int
    service_share: float
    transport_km_bikes: float
    solver_objective: float


PLAN_COLUMNS = [
    "origin_id",
    "origin",
    "destination_id",
    "destination",
    "distance_km",
    "bikes_to_move",
    "transport_km_bikes",
    "origin_free_bikes",
    "destination_free_bikes",
    "destination_risk_score",
]


def _rebalancing_nodes(
    stations: pd.DataFrame,
    target_ratio: float,
    trigger_ratio: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = stations.loc[stations["operational"]].copy()
    data["target_bikes"] = np.rint(data["capacity"] * target_ratio).astype(int)
    data["movable"] = (data["free_bikes"] - data["target_bikes"]).clip(lower=0).astype(int)
    data["needed"] = (data["target_bikes"] - data["free_bikes"]).clip(lower=0).astype(int)
    sources = data.loc[(data["bike_ratio"] >= 1 - trigger_ratio) & (data["movable"] > 0)].copy()
    destinations = data.loc[(data["bike_ratio"] <= trigger_ratio) & (data["needed"] > 0)].copy()
    return sources.reset_index(drop=True), destinations.reset_index(drop=True)


def optimize_rebalancing(
    stations: pd.DataFrame,
    *,
    max_distance_km: float = 2.5,
    target_ratio: float = 0.50,
    trigger_ratio: float = 0.25,
) -> tuple[pd.DataFrame, RebalancingSummary]:
    """Solve a minimum-distance transportation problem with unmet-need penalties.

    A high but finite penalty is assigned to unmet destination need. The LP first
    serves eligible deficits where possible and then minimises bike-kilometres. It
    uses straight-line distances, not vehicle routing or road-network travel times.
    """
    if max_distance_km <= 0:
        raise ValueError("max_distance_km must be positive")
    if not 0.25 <= target_ratio <= 0.75:
        raise ValueError("target_ratio must be between 0.25 and 0.75")
    if not 0.10 <= trigger_ratio <= 0.40:
        raise ValueError("trigger_ratio must be between 0.10 and 0.40")

    sources, destinations = _rebalancing_nodes(stations, target_ratio, trigger_ratio)
    total_supply = int(sources["movable"].sum()) if not sources.empty else 0
    total_need = int(destinations["needed"].sum()) if not destinations.empty else 0
    empty_summary = RebalancingSummary(
        eligible_sources=len(sources),
        eligible_destinations=len(destinations),
        eligible_arcs=0,
        total_supply=total_supply,
        total_need=total_need,
        bikes_moved=0,
        unmet_need=total_need,
        service_share=0.0,
        transport_km_bikes=0.0,
        solver_objective=0.0,
    )
    if sources.empty or destinations.empty:
        return pd.DataFrame(columns=PLAN_COLUMNS), empty_summary

    arcs: list[tuple[int, int, float]] = []
    for destination_index, destination in destinations.iterrows():
        distances = haversine_km(
            float(destination["latitude"]),
            float(destination["longitude"]),
            sources["latitude"],
            sources["longitude"],
        )
        for source_index, distance in enumerate(distances):
            if distance <= max_distance_km:
                arcs.append((source_index, destination_index, float(distance)))

    if not arcs:
        return pd.DataFrame(columns=PLAN_COLUMNS), empty_summary

    arc_count = len(arcs)
    destination_count = len(destinations)
    risk_multiplier = 1 + destinations.get("station_risk_score", pd.Series(0, index=destinations.index)) / 100
    unmet_penalty = max_distance_km * 20 * risk_multiplier.to_numpy(float)
    objective = np.asarray([arc[2] for arc in arcs] + unmet_penalty.tolist(), dtype=float)

    source_constraints = np.zeros((len(sources), arc_count + destination_count), dtype=float)
    for variable_index, (source_index, _, _) in enumerate(arcs):
        source_constraints[source_index, variable_index] = 1

    destination_constraints = np.zeros((destination_count, arc_count + destination_count), dtype=float)
    for variable_index, (_, destination_index, _) in enumerate(arcs):
        destination_constraints[destination_index, variable_index] = 1
    destination_constraints[:, arc_count:] = np.eye(destination_count)

    result = linprog(
        c=objective,
        A_ub=source_constraints,
        b_ub=sources["movable"].to_numpy(float),
        A_eq=destination_constraints,
        b_eq=destinations["needed"].to_numpy(float),
        bounds=(0, None),
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"Minimum-cost transportation solver failed: {result.message}")

    solution = np.rint(result.x).astype(int)
    plan_rows: list[dict[str, object]] = []
    for variable_index, (source_index, destination_index, distance) in enumerate(arcs):
        moved = int(solution[variable_index])
        if moved <= 0:
            continue
        source = sources.iloc[source_index]
        destination = destinations.iloc[destination_index]
        plan_rows.append(
            {
                "origin_id": source["station_id"],
                "origin": source["name"],
                "destination_id": destination["station_id"],
                "destination": destination["name"],
                "distance_km": round(distance, 3),
                "bikes_to_move": moved,
                "transport_km_bikes": round(distance * moved, 3),
                "origin_free_bikes": int(source["free_bikes"]),
                "destination_free_bikes": int(destination["free_bikes"]),
                "destination_risk_score": float(destination.get("station_risk_score", 0.0)),
            }
        )

    plan = pd.DataFrame(plan_rows, columns=PLAN_COLUMNS).sort_values(
        ["destination_risk_score", "distance_km"],
        ascending=[False, True],
    )
    bikes_moved = int(plan["bikes_to_move"].sum()) if not plan.empty else 0
    unmet_need = int(solution[arc_count:].sum())
    transport_km_bikes = float(plan["transport_km_bikes"].sum()) if not plan.empty else 0.0
    summary = RebalancingSummary(
        eligible_sources=len(sources),
        eligible_destinations=len(destinations),
        eligible_arcs=arc_count,
        total_supply=total_supply,
        total_need=total_need,
        bikes_moved=bikes_moved,
        unmet_need=unmet_need,
        service_share=(bikes_moved / total_need) if total_need else 0.0,
        transport_km_bikes=transport_km_bikes,
        solver_objective=float(result.fun),
    )
    return plan.reset_index(drop=True), summary
