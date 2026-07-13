from __future__ import annotations

import numpy as np
import pandas as pd

from src.operations import (
    add_local_risk_context,
    assess_snapshot_quality,
    simulate_commute_stress,
    summarize_operational_zones,
)
from src.optimization import optimize_rebalancing
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


def test_local_risk_context_is_bounded_and_deterministic() -> None:
    stations = make_frame(
        [
            {"station_id": "a", "latitude": 39.47, "longitude": -0.37, "free_bikes": 0, "slots": 10},
            {"station_id": "b", "latitude": 39.471, "longitude": -0.371, "free_bikes": 10, "slots": 10},
            {"station_id": "c", "latitude": 39.48, "longitude": -0.38, "free_bikes": 5, "slots": 10},
        ]
    )
    stations["empty_slots"] = stations["slots"] - stations["free_bikes"]
    stations = classify_station_status(enrich_station_frame(stations))

    first = add_local_risk_context(stations, neighbors=2)
    second = add_local_risk_context(stations, neighbors=2)

    assert first["station_risk_score"].between(0, 100).all()
    assert set(first["risk_band"]).issubset({"bajo", "moderado", "alto", "crítico"})
    assert np.allclose(first["station_risk_score"], second["station_risk_score"])


def test_snapshot_quality_surfaces_duplicate_and_invalid_coordinates() -> None:
    stations = make_frame(
        [
            {"station_id": "same", "latitude": 39.47, "longitude": -0.37, "slots": 10},
            {"station_id": "same", "latitude": 41.0, "longitude": -0.37, "slots": 10},
        ]
    )
    report = assess_snapshot_quality(stations)
    counts = report.set_index("check")["count"].to_dict()

    assert counts["IDs duplicados"] == 1
    assert counts["Coordenadas fuera del área esperada"] == 1


def test_minimum_cost_plan_conserves_supply_and_serves_eligible_destination() -> None:
    stations = make_frame(
        [
            {
                "station_id": "source",
                "name": "Origen",
                "latitude": 39.4700,
                "longitude": -0.3700,
                "free_bikes": 10,
                "empty_slots": 0,
                "slots": 10,
            },
            {
                "station_id": "destination",
                "name": "Destino",
                "latitude": 39.4710,
                "longitude": -0.3710,
                "free_bikes": 0,
                "empty_slots": 10,
                "slots": 10,
            },
            {
                "station_id": "support",
                "name": "Apoyo",
                "latitude": 39.4720,
                "longitude": -0.3720,
                "free_bikes": 5,
                "empty_slots": 5,
                "slots": 10,
            },
        ]
    )
    stations = classify_station_status(stations)
    stations = add_local_risk_context(stations, neighbors=2)

    plan, summary = optimize_rebalancing(
        stations,
        max_distance_km=1.0,
        target_ratio=0.5,
        trigger_ratio=0.25,
    )

    assert len(plan) == 1
    assert plan.loc[0, "origin"] == "Origen"
    assert plan.loc[0, "destination"] == "Destino"
    assert plan.loc[0, "bikes_to_move"] == 5
    assert summary.bikes_moved == 5
    assert summary.unmet_need == 0


def test_commute_stress_conserves_bikes_and_capacity() -> None:
    stations = make_frame(
        [
            {
                "station_id": "core",
                "latitude": 39.4699,
                "longitude": -0.3763,
                "free_bikes": 2,
                "empty_slots": 8,
                "slots": 10,
            },
            {
                "station_id": "outer-a",
                "latitude": 39.5000,
                "longitude": -0.4100,
                "free_bikes": 10,
                "empty_slots": 0,
                "slots": 10,
            },
            {
                "station_id": "outer-b",
                "latitude": 39.5050,
                "longitude": -0.4150,
                "free_bikes": 8,
                "empty_slots": 2,
                "slots": 10,
            },
        ]
    )
    stations = classify_station_status(stations)
    simulated, summary = simulate_commute_stress(
        stations,
        direction="to_core",
        shock_ratio=0.20,
        core_radius_km=1.0,
        min_units=2,
        min_ratio=0.10,
    )

    assert summary["bikes_shifted"] > 0
    assert simulated["free_bikes"].sum() == stations["free_bikes"].sum()
    assert (simulated["free_bikes"] >= 0).all()
    assert (simulated["free_bikes"] <= simulated["capacity"]).all()


def test_operational_zone_summary_exposes_risk_metrics() -> None:
    stations = make_frame(
        [
            {"station_id": "a", "latitude": 39.45, "longitude": -0.41, "slots": 10},
            {"station_id": "b", "latitude": 39.451, "longitude": -0.409, "slots": 10},
            {"station_id": "c", "latitude": 39.49, "longitude": -0.32, "slots": 10},
            {"station_id": "d", "latitude": 39.491, "longitude": -0.321, "slots": 10},
        ]
    )
    stations = add_local_risk_context(classify_station_status(assign_zones(stations, n_clusters=2)))

    zones = summarize_operational_zones(stations)

    assert len(zones) == 2
    assert {"mean_station_risk", "critical_share", "mean_local_pressure"}.issubset(zones.columns)
