from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

CITYBIKES_URL = "https://api.citybik.es/v2/networks/valenbisi"
VALENCIA_CENTER = (39.4699075, -0.3762881)
FALLBACK_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_valenbisi.csv"
CRITICAL_STATUSES = frozenset({"Sin bicis", "Sin anclajes", "Critica mixta", "Revisar"})


def _to_int(value: object, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: object, default: float = np.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def repair_text(value: object) -> str:
    """Repair common mojibake from some Windows terminals while leaving clean UTF-8 alone."""
    text = "" if value is None else str(value)
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_station_name(value: object) -> str:
    text = repair_text(value).strip().strip("_")
    text = text.replace("_", " ")
    return " ".join(text.split()).title()


def fetch_citybikes_payload(timeout: int = 12) -> dict:
    request = urllib.request.Request(
        CITYBIKES_URL,
        headers={"User-Agent": "valenbisi-pulse-edm/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def stations_to_frame(stations: Iterable[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for station in stations:
        extra = station.get("extra") or {}
        free_bikes = _to_int(station.get("free_bikes"))
        empty_slots = _to_int(station.get("empty_slots"))
        declared_slots = _to_int(extra.get("slots"), free_bikes + empty_slots)
        capacity = max(declared_slots, free_bikes + empty_slots)

        rows.append(
            {
                "station_id": station.get("id", ""),
                "uid": str(extra.get("uid", "")),
                "name": clean_station_name(station.get("name")),
                "address": repair_text(extra.get("address", "")),
                "latitude": _to_float(station.get("latitude")),
                "longitude": _to_float(station.get("longitude")),
                "free_bikes": free_bikes,
                "empty_slots": empty_slots,
                "slots": capacity,
                "renting": bool(extra.get("renting", True)),
                "returning": bool(extra.get("returning", True)),
                "last_updated": extra.get("last_updated", ""),
                "timestamp": station.get("timestamp", ""),
            }
        )

    return enrich_station_frame(pd.DataFrame(rows))


def enrich_station_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    required = [
        "station_id",
        "uid",
        "name",
        "address",
        "latitude",
        "longitude",
        "free_bikes",
        "empty_slots",
        "slots",
        "renting",
        "returning",
        "last_updated",
        "timestamp",
    ]
    for column in required:
        if column not in df.columns:
            df[column] = (
                "" if column in {"station_id", "uid", "name", "address", "last_updated", "timestamp"} else 0
            )

    df["name"] = df["name"].map(clean_station_name)
    df["address"] = df["address"].map(repair_text)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["free_bikes"] = pd.to_numeric(df["free_bikes"], errors="coerce").fillna(0).astype(int)
    df["empty_slots"] = pd.to_numeric(df["empty_slots"], errors="coerce").fillna(0).astype(int)
    df["slots"] = pd.to_numeric(df["slots"], errors="coerce").fillna(0).astype(int)
    df["slots"] = np.maximum(df["slots"], df["free_bikes"] + df["empty_slots"])
    df["capacity"] = df["slots"].astype(int)

    safe_capacity = df["capacity"].replace(0, np.nan)
    df["bike_ratio"] = (df["free_bikes"] / safe_capacity).fillna(0).clip(0, 1)
    df["dock_ratio"] = (df["empty_slots"] / safe_capacity).fillna(0).clip(0, 1)
    df["imbalance"] = ((df["bike_ratio"] - 0.5).abs() * 2).clip(0, 1)
    df["operational"] = df["renting"].astype(bool) & df["returning"].astype(bool) & (df["capacity"] > 0)
    df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    return df


def load_valenbisi_data(prefer_live: bool = True) -> tuple[pd.DataFrame, str]:
    if prefer_live:
        try:
            payload = fetch_citybikes_payload()
            network = payload.get("network", {})
            stations = network.get("stations", [])
            if stations:
                return stations_to_frame(stations), "CityBikes API / JCDecaux Open Licence"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass

    fallback = pd.read_csv(FALLBACK_PATH)
    return enrich_station_frame(fallback), "muestra local incluida en data/sample_valenbisi.csv"


def classify_station_status(df: pd.DataFrame, min_units: int = 2, min_ratio: float = 0.10) -> pd.DataFrame:
    df = df.copy()
    min_ratio = max(float(min_ratio), 0.01)

    bike_critical = (df["free_bikes"] <= min_units) | (df["bike_ratio"] <= min_ratio)
    dock_critical = (df["empty_slots"] <= min_units) | (df["dock_ratio"] <= min_ratio)
    not_operational = ~df["operational"]

    df["status"] = np.select(
        [
            not_operational,
            bike_critical & dock_critical,
            bike_critical,
            dock_critical,
            df["imbalance"] <= 0.25,
        ],
        [
            "Revisar",
            "Critica mixta",
            "Sin bicis",
            "Sin anclajes",
            "Equilibrada",
        ],
        default="Desequilibrada",
    )
    df["recommended_action"] = np.select(
        [
            not_operational,
            bike_critical & dock_critical,
            bike_critical,
            dock_critical,
            df["imbalance"] <= 0.25,
        ],
        [
            "Revisar estado",
            "Comprobar estacion",
            "Enviar bicicletas",
            "Retirar bicicletas",
            "Sin accion urgente",
        ],
        default="Monitorizar",
    )

    unit_depth = np.maximum(
        np.maximum(0, min_units - df["free_bikes"]) / max(min_units, 1),
        np.maximum(0, min_units - df["empty_slots"]) / max(min_units, 1),
    )
    ratio_depth = np.maximum(
        np.maximum(0, min_ratio - df["bike_ratio"]) / min_ratio,
        np.maximum(0, min_ratio - df["dock_ratio"]) / min_ratio,
    )
    critical_depth = np.maximum(unit_depth, ratio_depth).clip(0, 1)
    median_capacity = max(float(df["capacity"].median()), 1.0)
    capacity_weight = (df["capacity"] / median_capacity).clip(0, 2) / 2
    df["priority_score"] = (
        100 * (0.45 * critical_depth + 0.35 * df["imbalance"] + 0.20 * capacity_weight)
    ).clip(0, 100)
    df.loc[not_operational, "priority_score"] = 100
    df["priority_score"] = df["priority_score"].round(1)
    return df


def project_latlon(
    latitudes: Iterable[float],
    longitudes: Iterable[float],
    origin: tuple[float, float] | None = None,
) -> np.ndarray:
    lat = np.asarray(latitudes, dtype=float)
    lon = np.asarray(longitudes, dtype=float)
    lat0, lon0 = origin or (float(np.nanmean(lat)), float(np.nanmean(lon)))
    x = (lon - lon0) * 111.32 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 110.57
    return np.column_stack([x, y])


def assign_zones(df: pd.DataFrame, n_clusters: int = 7) -> pd.DataFrame:
    clustered = df.copy()
    if clustered.empty:
        clustered["zone_id"] = pd.Series(dtype="int64")
        clustered["zone"] = pd.Series(dtype="object")
        return clustered

    points = project_latlon(clustered["latitude"], clustered["longitude"], VALENCIA_CENTER)
    cluster_count = int(max(1, min(n_clusters, len(clustered))))
    model = KMeans(n_clusters=cluster_count, n_init=10, random_state=42)
    clustered["zone_id"] = model.fit_predict(points) + 1
    clustered["zone"] = "Zona " + clustered["zone_id"].astype(str)
    return clustered


def summarize_zones(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["zone_id", "zone"], as_index=False)
        .agg(
            stations=("station_id", "count"),
            free_bikes=("free_bikes", "sum"),
            empty_slots=("empty_slots", "sum"),
            capacity=("capacity", "sum"),
            priority_score=("priority_score", "mean"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
        .sort_values("zone_id")
    )
    safe_capacity = grouped["capacity"].replace(0, np.nan)
    grouped["bike_ratio"] = (grouped["free_bikes"] / safe_capacity).fillna(0)
    grouped["dock_ratio"] = (grouped["empty_slots"] / safe_capacity).fillna(0)
    grouped["imbalance"] = ((grouped["bike_ratio"] - 0.5).abs() * 2).clip(0, 1)
    critical_by_zone = (
        df.assign(is_critical=df["status"].isin(CRITICAL_STATUSES))
        .groupby("zone_id")["is_critical"]
        .sum()
        .astype(int)
    )
    grouped["critical_stations"] = grouped["zone_id"].map(critical_by_zone).fillna(0).astype(int)
    grouped["suggested_action"] = np.select(
        [
            grouped["bike_ratio"] <= 0.20,
            grouped["dock_ratio"] <= 0.20,
            grouped["imbalance"] <= 0.25,
        ],
        [
            "Enviar bicicletas",
            "Liberar anclajes",
            "Mantener",
        ],
        default="Monitorizar",
    )
    grouped["priority_score"] = grouped["priority_score"].round(1)
    grouped["bike_ratio"] = grouped["bike_ratio"].round(3)
    grouped["dock_ratio"] = grouped["dock_ratio"].round(3)
    return grouped.sort_values(["priority_score", "critical_stations"], ascending=False).reset_index(
        drop=True
    )


def haversine_km(lat1: float, lon1: float, lat2: Iterable[float], lon2: Iterable[float]) -> np.ndarray:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = np.radians(np.asarray(lat2, dtype=float))
    lon2_rad = np.radians(np.asarray(lon2, dtype=float))
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    return 6371.0 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def nearest_stations(
    df: pd.DataFrame,
    latitude: float,
    longitude: float,
    mode: str = "take",
    min_available: int = 1,
    top_n: int = 8,
) -> pd.DataFrame:
    data = df.copy()
    if mode == "return":
        data = data[(data["empty_slots"] >= min_available) & data["returning"]]
        availability_column = "empty_slots"
    else:
        data = data[(data["free_bikes"] >= min_available) & data["renting"]]
        availability_column = "free_bikes"

    data = data.copy()
    data["distance_km"] = haversine_km(latitude, longitude, data["latitude"], data["longitude"])
    return (
        data.sort_values(["distance_km", availability_column], ascending=[True, False])
        .head(top_n)
        .reset_index(drop=True)
    )


def recommend_rebalancing(
    df: pd.DataFrame,
    max_distance_km: float = 2.5,
    target_ratio: float = 0.50,
    top_n: int = 20,
) -> pd.DataFrame:
    target_ratio = float(np.clip(target_ratio, 0.25, 0.75))
    data = df[df["operational"]].copy()
    data["target_bikes"] = (data["capacity"] * target_ratio).round().astype(int)

    sources = data[
        (data["free_bikes"] > data["target_bikes"]) & (data["dock_ratio"] <= 0.20) & (data["free_bikes"] >= 3)
    ].copy()
    destinations = data[
        (data["free_bikes"] < data["target_bikes"])
        & (data["bike_ratio"] <= 0.20)
        & (data["empty_slots"] >= 3)
    ].copy()

    sources["movable"] = (sources["free_bikes"] - sources["target_bikes"]).clip(lower=0).astype(int)
    destinations["needed"] = (
        (destinations["target_bikes"] - destinations["free_bikes"]).clip(lower=0).astype(int)
    )
    sources = (
        sources[sources["movable"] > 0].sort_values("priority_score", ascending=False).reset_index(drop=True)
    )
    destinations = (
        destinations[destinations["needed"] > 0]
        .sort_values("priority_score", ascending=False)
        .reset_index(drop=True)
    )

    columns = [
        "origin",
        "destination",
        "distance_km",
        "bikes_to_move",
        "origin_free_bikes",
        "destination_free_bikes",
        "destination_empty_slots",
        "impact",
    ]
    if sources.empty or destinations.empty:
        return pd.DataFrame(columns=columns)

    movable = sources["movable"].to_numpy().astype(int)
    needed = destinations["needed"].to_numpy().astype(int)
    plans: list[dict] = []

    for destination_index, destination in destinations.iterrows():
        if needed[destination_index] <= 0:
            continue
        distances = haversine_km(
            destination["latitude"],
            destination["longitude"],
            sources["latitude"],
            sources["longitude"],
        )
        for source_index in np.argsort(distances):
            if len(plans) >= top_n:
                break
            if movable[source_index] <= 0 or distances[source_index] > max_distance_km:
                continue
            bikes_to_move = int(min(movable[source_index], needed[destination_index]))
            if bikes_to_move <= 0:
                continue
            source = sources.iloc[source_index]
            plans.append(
                {
                    "origin": source["name"],
                    "destination": destination["name"],
                    "distance_km": round(float(distances[source_index]), 2),
                    "bikes_to_move": bikes_to_move,
                    "origin_free_bikes": int(source["free_bikes"]),
                    "destination_free_bikes": int(destination["free_bikes"]),
                    "destination_empty_slots": int(destination["empty_slots"]),
                    "impact": f"{bikes_to_move} bicis -> {destination['name']}",
                }
            )
            movable[source_index] -= bikes_to_move
            needed[destination_index] -= bikes_to_move
            if needed[destination_index] <= 0:
                break
        if len(plans) >= top_n:
            break

    return pd.DataFrame(plans, columns=columns)


def status_counts(df: pd.DataFrame) -> pd.DataFrame:
    order = ["Equilibrada", "Desequilibrada", "Sin bicis", "Sin anclajes", "Critica mixta", "Revisar"]
    counts = df["status"].value_counts().reindex(order).fillna(0).astype(int)
    return counts.rename_axis("status").reset_index(name="stations")
