"""Operational diagnostics and transparent stress tests for a station snapshot."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.valenbisi import (
    CRITICAL_STATUSES,
    VALENCIA_CENTER,
    classify_station_status,
    enrich_station_frame,
    summarize_zones,
)


def _pairwise_haversine_km(latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    latitude_radians = np.radians(latitudes)[:, None]
    longitude_radians = np.radians(longitudes)[:, None]
    delta_latitude = latitude_radians.T - latitude_radians
    delta_longitude = longitude_radians.T - longitude_radians
    haversine_a = (
        np.sin(delta_latitude / 2) ** 2
        + np.cos(latitude_radians)
        * np.cos(latitude_radians.T)
        * np.sin(delta_longitude / 2) ** 2
    )
    return 6371.0 * 2 * np.arctan2(np.sqrt(haversine_a), np.sqrt(1 - haversine_a))


def _min_max(values: np.ndarray) -> np.ndarray:
    minimum = float(np.nanmin(values))
    maximum = float(np.nanmax(values))
    if math.isclose(minimum, maximum):
        return np.zeros_like(values, dtype=float)
    return (values - minimum) / (maximum - minimum)


def add_local_risk_context(stations: pd.DataFrame, neighbors: int = 4) -> pd.DataFrame:
    """Add local exposure, isolation and a snapshot-level risk score.

    The score is only a prioritisation heuristic for the observed snapshot. It does
    not estimate probability of failure or future demand.
    """
    data = stations.copy().reset_index(drop=True)
    station_count = len(data)
    if station_count == 0:
        for column in [
            "neighbor_bike_ratio",
            "neighbor_imbalance",
            "neighbor_critical_share",
            "nearest_neighbor_km",
            "local_pressure",
            "isolation_score",
            "station_risk_score",
            "risk_band",
        ]:
            data[column] = pd.Series(dtype="float64" if column != "risk_band" else "object")
        return data

    required = {"latitude", "longitude", "bike_ratio", "imbalance", "priority_score", "status"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"stations is missing required columns: {sorted(missing)}")

    if station_count == 1:
        data["neighbor_bike_ratio"] = data["bike_ratio"]
        data["neighbor_imbalance"] = data["imbalance"]
        data["neighbor_critical_share"] = data["status"].isin(CRITICAL_STATUSES).astype(float)
        data["nearest_neighbor_km"] = 0.0
    else:
        neighbor_count = max(1, min(int(neighbors), station_count - 1))
        distances = _pairwise_haversine_km(
            data["latitude"].to_numpy(float),
            data["longitude"].to_numpy(float),
        )
        np.fill_diagonal(distances, np.inf)
        nearest = np.argpartition(distances, kth=neighbor_count - 1, axis=1)[:, :neighbor_count]
        data["neighbor_bike_ratio"] = data["bike_ratio"].to_numpy(float)[nearest].mean(axis=1)
        data["neighbor_imbalance"] = data["imbalance"].to_numpy(float)[nearest].mean(axis=1)
        critical = data["status"].isin(CRITICAL_STATUSES).to_numpy(float)
        data["neighbor_critical_share"] = critical[nearest].mean(axis=1)
        data["nearest_neighbor_km"] = distances[np.arange(station_count)[:, None], nearest].min(axis=1)

    data["isolation_score"] = _min_max(data["nearest_neighbor_km"].to_numpy(float))
    data["local_pressure"] = (
        0.60 * data["neighbor_critical_share"] + 0.40 * data["neighbor_imbalance"]
    ).clip(0, 1)
    data["station_risk_score"] = (
        100
        * (
            0.55 * (data["priority_score"] / 100)
            + 0.25 * data["local_pressure"]
            + 0.12 * data["isolation_score"]
            + 0.08 * data["imbalance"]
        )
    ).clip(0, 100)
    data.loc[~data["operational"], "station_risk_score"] = 100.0
    data["station_risk_score"] = data["station_risk_score"].round(1)
    data["risk_band"] = pd.cut(
        data["station_risk_score"],
        bins=[-0.01, 35, 55, 75, 100],
        labels=["bajo", "moderado", "alto", "crítico"],
    ).astype(str)
    return data


def assess_snapshot_quality(stations: pd.DataFrame) -> pd.DataFrame:
    """Return transparent quality checks for the currently loaded station snapshot."""
    required_columns = {
        "station_id",
        "name",
        "latitude",
        "longitude",
        "capacity",
        "free_bikes",
        "empty_slots",
    }
    missing_columns = required_columns - set(stations.columns)
    if missing_columns:
        raise ValueError(f"stations is missing required columns: {sorted(missing_columns)}")

    coordinate_valid = stations["latitude"].between(39.35, 39.60) & stations["longitude"].between(
        -0.55,
        -0.15,
    )
    inventory_exceeds_capacity = (stations["free_bikes"] + stations["empty_slots"]) > stations["capacity"]
    checks = [
        ("Estaciones cargadas", int(len(stations)), "informativo"),
        ("IDs duplicados", int(stations["station_id"].duplicated().sum()), "revisar"),
        ("Nombres vacíos", int(stations["name"].fillna("").str.strip().eq("").sum()), "revisar"),
        ("Coordenadas fuera del área esperada", int((~coordinate_valid).sum()), "revisar"),
        ("Capacidad no positiva", int((stations["capacity"] <= 0).sum()), "revisar"),
        ("Inventario por encima de capacidad", int(inventory_exceeds_capacity.sum()), "revisar"),
        ("Estaciones no operativas", int((~stations["operational"]).sum()), "observación"),
    ]
    report = pd.DataFrame(checks, columns=["check", "count", "type"])
    report["status"] = np.where(
        (report["type"] == "revisar") & (report["count"] > 0),
        "revisar",
        "ok",
    )
    return report


def summarize_operational_zones(stations: pd.DataFrame) -> pd.DataFrame:
    """Extend KMeans zone summaries with local snapshot risk diagnostics."""
    required = {"zone_id", "zone", "station_risk_score", "local_pressure", "isolation_score", "status"}
    missing = required - set(stations.columns)
    if missing:
        raise ValueError(f"stations is missing required columns: {sorted(missing)}")

    base = summarize_zones(stations)
    diagnostics = (
        stations.assign(is_critical=stations["status"].isin(CRITICAL_STATUSES))
        .groupby("zone_id", as_index=False)
        .agg(
            mean_station_risk=("station_risk_score", "mean"),
            max_station_risk=("station_risk_score", "max"),
            critical_share=("is_critical", "mean"),
            mean_local_pressure=("local_pressure", "mean"),
            mean_isolation_score=("isolation_score", "mean"),
        )
    )
    result = base.merge(diagnostics, on="zone_id", how="left", validate="one_to_one")
    for column in ["mean_station_risk", "max_station_risk", "critical_share", "mean_local_pressure"]:
        result[column] = result[column].round(3)
    return result.sort_values(
        ["mean_station_risk", "critical_stations"],
        ascending=False,
    ).reset_index(drop=True)


def _distance_to_center_km(stations: pd.DataFrame) -> np.ndarray:
    latitudes = np.radians(stations["latitude"].to_numpy(float))
    longitudes = np.radians(stations["longitude"].to_numpy(float))
    center_latitude = math.radians(VALENCIA_CENTER[0])
    center_longitude = math.radians(VALENCIA_CENTER[1])
    delta_latitude = latitudes - center_latitude
    delta_longitude = longitudes - center_longitude
    haversine_a = (
        np.sin(delta_latitude / 2) ** 2
        + math.cos(center_latitude) * np.cos(latitudes) * np.sin(delta_longitude / 2) ** 2
    )
    return 6371.0 * 2 * np.arctan2(np.sqrt(haversine_a), np.sqrt(1 - haversine_a))


def _allocate_bikes(total: int, capacities: np.ndarray) -> np.ndarray:
    """Distribute an integer total proportionally without exceeding station capacity."""
    if total <= 0 or capacities.sum() <= 0:
        return np.zeros(len(capacities), dtype=int)
    ideal = total * capacities / capacities.sum()
    allocation = np.minimum(np.floor(ideal).astype(int), capacities.astype(int))
    remaining = int(total - allocation.sum())
    for index in np.argsort(-(ideal - allocation)):
        if remaining == 0:
            break
        available = int(capacities[index] - allocation[index])
        if available > 0:
            allocation[index] += 1
            remaining -= 1
    return allocation


def simulate_commute_stress(
    stations: pd.DataFrame,
    *,
    direction: str,
    shock_ratio: float,
    core_radius_km: float,
    min_units: int,
    min_ratio: float,
) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    """Conserve bikes while moving a modeled commuting shock between core and periphery.

    This is a deterministic what-if stress test. It is not a demand forecast and it
    does not use historical trips.
    """
    if direction not in {"to_core", "from_core"}:
        raise ValueError("direction must be 'to_core' or 'from_core'")
    if not 0 <= shock_ratio <= 0.50:
        raise ValueError("shock_ratio must be between 0 and 0.50")
    if core_radius_km <= 0:
        raise ValueError("core_radius_km must be positive")

    baseline = stations.copy().reset_index(drop=True)
    data = baseline.copy()
    data["distance_to_center_km"] = _distance_to_center_km(data)
    core_mask = data["distance_to_center_km"] <= core_radius_km
    if direction == "to_core":
        origin_mask, destination_mask = ~core_mask, core_mask
    else:
        origin_mask, destination_mask = core_mask, ~core_mask
    origin_mask &= data["operational"]
    destination_mask &= data["operational"]

    origin_positions = np.flatnonzero(origin_mask.to_numpy())
    destination_positions = np.flatnonzero(destination_mask.to_numpy())
    departures = np.zeros(len(data), dtype=int)
    arrivals = np.zeros(len(data), dtype=int)

    if len(origin_positions) and len(destination_positions):
        requested = np.floor(data.loc[origin_mask, "free_bikes"].to_numpy(float) * shock_ratio).astype(int)
        departures[origin_positions] = requested
        bikes_shifted = int(requested.sum())
        destination_capacity = data.loc[destination_mask, "empty_slots"].to_numpy(int)
        bikes_shifted = min(bikes_shifted, int(destination_capacity.sum()))
        if bikes_shifted < departures.sum():
            departures[:] = 0
            scaled = _allocate_bikes(bikes_shifted, data.loc[origin_mask, "free_bikes"].to_numpy(int))
            departures[origin_positions] = scaled
        arrivals[destination_positions] = _allocate_bikes(bikes_shifted, destination_capacity)
    else:
        bikes_shifted = 0

    data["free_bikes"] = data["free_bikes"].to_numpy(int) - departures + arrivals
    data["empty_slots"] = data["capacity"].to_numpy(int) - data["free_bikes"].to_numpy(int)
    simulated = classify_station_status(
        enrich_station_frame(data),
        min_units=min_units,
        min_ratio=min_ratio,
    )
    simulated["distance_to_center_km"] = data["distance_to_center_km"]
    baseline_critical = baseline["status"].isin(CRITICAL_STATUSES)
    simulated_critical = simulated["status"].isin(CRITICAL_STATUSES)
    label = "Flujo hacia el centro" if direction == "to_core" else "Flujo desde el centro"
    summary: dict[str, float | int | str] = {
        "scenario": label,
        "direction": direction,
        "shock_ratio": shock_ratio,
        "core_radius_km": core_radius_km,
        "bikes_shifted": bikes_shifted,
        "baseline_critical_stations": int(baseline_critical.sum()),
        "scenario_critical_stations": int(simulated_critical.sum()),
        "newly_critical_stations": int((~baseline_critical & simulated_critical).sum()),
        "resolved_critical_stations": int((baseline_critical & ~simulated_critical).sum()),
    }
    return simulated, summary
