from __future__ import annotations

import numpy as np
import pandas as pd

from src.valenbisi import (
    CRITICAL_STATUSES,
    assign_zones,
    classify_station_status,
    clean_station_name,
    enrich_station_frame,
    load_valenbisi_data,
    nearest_stations,
    recommend_rebalancing,
)


def make_frame(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "station_id": "",
        "uid": "",
        "name": "",
        "address": "",
        "latitude": 39.47,
        "longitude": -0.37,
        "free_bikes": 0,
        "empty_slots": 0,
        "slots": 0,
        "renting": True,
        "returning": True,
        "last_updated": "",
        "timestamp": "",
    }
    return enrich_station_frame(pd.DataFrame([{**defaults, **row} for row in rows]))


def test_clean_station_name_repairs_spacing_and_case() -> None:
    assert clean_station_name("_AVENIDA_DEL_PUERTO_") == "Avenida Del Puerto"


def test_classify_station_status_covers_main_operational_states() -> None:
    stations = make_frame(
        [
            {"station_id": "empty", "free_bikes": 0, "empty_slots": 10, "slots": 10},
            {"station_id": "full", "free_bikes": 10, "empty_slots": 0, "slots": 10},
            {"station_id": "balanced", "free_bikes": 5, "empty_slots": 5, "slots": 10},
        ]
    )

    classified = classify_station_status(stations, min_units=1, min_ratio=0.10)

    assert classified.set_index("station_id")["status"].to_dict() == {
        "empty": "Sin bicis",
        "full": "Sin anclajes",
        "balanced": "Equilibrada",
    }
    assert set(classified[classified["status"].isin(CRITICAL_STATUSES)]["station_id"]) == {
        "empty",
        "full",
    }


def test_assign_zones_is_deterministic() -> None:
    stations = make_frame(
        [
            {"station_id": "a", "latitude": 39.45, "longitude": -0.41, "slots": 10},
            {"station_id": "b", "latitude": 39.451, "longitude": -0.409, "slots": 10},
            {"station_id": "c", "latitude": 39.49, "longitude": -0.32, "slots": 10},
            {"station_id": "d", "latitude": 39.491, "longitude": -0.321, "slots": 10},
        ]
    )

    first = assign_zones(stations, n_clusters=2)
    second = assign_zones(stations, n_clusters=2)

    assert first["zone_id"].nunique() == 2
    assert np.array_equal(first["zone_id"], second["zone_id"])


def test_nearest_stations_respects_requested_availability() -> None:
    stations = make_frame(
        [
            {
                "station_id": "near-empty",
                "latitude": 39.4701,
                "longitude": -0.3701,
                "free_bikes": 0,
                "empty_slots": 10,
                "slots": 10,
            },
            {
                "station_id": "far-available",
                "latitude": 39.48,
                "longitude": -0.38,
                "free_bikes": 4,
                "empty_slots": 6,
                "slots": 10,
            },
        ]
    )

    result = nearest_stations(stations, 39.47, -0.37, mode="take", min_available=1)

    assert result["station_id"].tolist() == ["far-available"]


def test_rebalancing_moves_only_the_required_bikes() -> None:
    stations = make_frame(
        [
            {
                "station_id": "source",
                "name": "Origen",
                "latitude": 39.4700,
                "longitude": -0.3700,
                "free_bikes": 9,
                "empty_slots": 1,
                "slots": 10,
            },
            {
                "station_id": "destination",
                "name": "Destino",
                "latitude": 39.4710,
                "longitude": -0.3710,
                "free_bikes": 1,
                "empty_slots": 9,
                "slots": 10,
            },
        ]
    )
    stations = classify_station_status(stations)

    plan = recommend_rebalancing(stations, max_distance_km=1.0, target_ratio=0.5)

    assert len(plan) == 1
    assert plan.loc[0, "origin"] == "Origen"
    assert plan.loc[0, "destination"] == "Destino"
    assert plan.loc[0, "bikes_to_move"] == 4


def test_offline_sample_is_available() -> None:
    stations, source = load_valenbisi_data(prefer_live=False)

    assert not stations.empty
    assert "muestra local" in source
