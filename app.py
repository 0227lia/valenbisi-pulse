"""Interactive operational dashboard for the Valenbisi snapshot decision model."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.operations import (
    add_local_risk_context,
    assess_snapshot_quality,
    simulate_commute_stress,
    summarize_operational_zones,
)
from src.optimization import optimize_rebalancing
from src.valenbisi import (
    CRITICAL_STATUSES,
    VALENCIA_CENTER,
    assign_zones,
    classify_station_status,
    load_valenbisi_data,
    nearest_stations,
    status_counts,
)

COLORS = {
    "ink": "#172033",
    "muted": "#64748B",
    "grid": "#DCE3EA",
    "teal": "#0F766E",
    "coral": "#E85D4A",
    "gold": "#D97706",
    "blue": "#2563EB",
    "slate": "#94A3B8",
}
RISK_COLORS = {
    "bajo": COLORS["slate"],
    "moderado": COLORS["blue"],
    "alto": COLORS["gold"],
    "crítico": COLORS["coral"],
}
STATUS_COLORS = {
    "Equilibrada": COLORS["teal"],
    "Desequilibrada": COLORS["gold"],
    "Sin bicis": COLORS["coral"],
    "Sin anclajes": "#7C3AED",
    "Critica mixta": COLORS["ink"],
    "Revisar": COLORS["blue"],
}


@st.cache_data(ttl=180, show_spinner=False)
def load_snapshot(
    prefer_live: bool,
    min_units: int,
    min_ratio: float,
    n_clusters: int,
    neighbors: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    stations, source = load_valenbisi_data(prefer_live=prefer_live)
    stations = classify_station_status(stations, min_units=min_units, min_ratio=min_ratio)
    stations = assign_zones(stations, n_clusters=n_clusters)
    stations = add_local_risk_context(stations, neighbors=neighbors)
    zones = summarize_operational_zones(stations)
    quality = assess_snapshot_quality(stations)
    return stations, zones, quality, source


def base_layout(title: str | None = None) -> dict[str, object]:
    layout: dict[str, object] = {
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": {"family": "Arial, sans-serif", "color": COLORS["ink"]},
        "margin": {"l": 12, "r": 12, "t": 44 if title else 18, "b": 12},
        "legend": {"orientation": "h", "y": -0.17},
        "xaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
        "yaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
    }
    if title:
        layout["title"] = {"text": title, "font": {"size": 18, "color": COLORS["ink"]}}
    return layout


def risk_map(stations: pd.DataFrame, title: str | None = None) -> go.Figure:
    fig = px.scatter_map(
        stations,
        lat="latitude",
        lon="longitude",
        color="risk_band",
        size="station_risk_score",
        size_max=28,
        color_discrete_map=RISK_COLORS,
        category_orders={"risk_band": ["crítico", "alto", "moderado", "bajo"]},
        hover_name="name",
        hover_data={
            "status": True,
            "free_bikes": True,
            "empty_slots": True,
            "capacity": True,
            "station_risk_score": ":.1f",
            "local_pressure": ":.0%",
            "nearest_neighbor_km": ":.2f",
            "latitude": False,
            "longitude": False,
            "risk_band": False,
        },
        zoom=12,
        height=520,
    )
    fig.update_traces(marker={"opacity": 0.9})
    fig.update_layout(**base_layout(title))
    fig.update_layout(map_style="carto-positron", legend_title_text="Riesgo")
    return fig


def risk_scatter(stations: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        stations,
        x="local_pressure",
        y="station_risk_score",
        size="capacity",
        color="risk_band",
        color_discrete_map=RISK_COLORS,
        category_orders={"risk_band": ["crítico", "alto", "moderado", "bajo"]},
        hover_name="name",
        hover_data={
            "status": True,
            "priority_score": ":.1f",
            "isolation_score": ":.2f",
            "neighbor_critical_share": ":.0%",
        },
        size_max=44,
    )
    fig.add_vline(x=0.5, line_color=COLORS["grid"], line_dash="dot")
    fig.add_hline(y=75, line_color=COLORS["grid"], line_dash="dot")
    fig.update_layout(**base_layout())
    fig.update_xaxes(title="Presión local del vecindario", tickformat=".0%")
    fig.update_yaxes(title="Score de riesgo de snapshot", range=[0, 105])
    return fig


def zone_chart(zones: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        zones,
        x="critical_share",
        y="mean_station_risk",
        size="capacity",
        color="mean_local_pressure",
        color_continuous_scale="YlOrRd",
        hover_name="zone",
        hover_data={
            "stations": True,
            "critical_stations": True,
            "max_station_risk": ":.1f",
            "mean_isolation_score": ":.2f",
        },
        size_max=50,
    )
    fig.update_layout(**base_layout())
    fig.update_xaxes(title="Proporción de estaciones críticas", tickformat=".0%")
    fig.update_yaxes(title="Riesgo medio de estación", range=[0, 105])
    return fig


def status_chart(stations: pd.DataFrame) -> go.Figure:
    counts = status_counts(stations)
    fig = px.bar(
        counts,
        x="status",
        y="stations",
        color="status",
        color_discrete_map=STATUS_COLORS,
        text="stations",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(**base_layout())
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title=None)
    fig.update_yaxes(title="Estaciones", rangemode="tozero")
    return fig


def plan_map(stations: pd.DataFrame, plan: pd.DataFrame) -> go.Figure:
    fig = risk_map(stations)
    coordinates = stations.set_index("station_id")[["latitude", "longitude"]]
    for _, movement in plan.iterrows():
        origin = coordinates.loc[movement["origin_id"]]
        destination = coordinates.loc[movement["destination_id"]]
        fig.add_trace(
            go.Scattermap(
                lat=[origin["latitude"], destination["latitude"]],
                lon=[origin["longitude"], destination["longitude"]],
                mode="lines",
                line={"width": 2, "color": COLORS["teal"]},
                opacity=0.62,
                showlegend=False,
                hovertemplate=(
                    f"{movement['origin']} -> {movement['destination']}<br>"
                    f"{int(movement['bikes_to_move'])} bicicletas | "
                    f"{movement['distance_km']:.2f} km<extra></extra>"
                ),
            )
        )
    fig.update_layout(legend_title_text="Riesgo de estación")
    return fig


def scenario_transition_frame(baseline: pd.DataFrame, simulated: pd.DataFrame) -> pd.DataFrame:
    frame = baseline[["station_id", "name", "status", "free_bikes", "empty_slots"]].merge(
        simulated[["station_id", "status", "free_bikes", "empty_slots"]],
        on="station_id",
        suffixes=("_base", "_scenario"),
        validate="one_to_one",
    )
    frame["delta_bikes"] = frame["free_bikes_scenario"] - frame["free_bikes_base"]
    frame["status_changed"] = frame["status_base"] != frame["status_scenario"]
    return frame.sort_values(["status_changed", "delta_bikes"], ascending=[False, True])


def station_table(stations: pd.DataFrame) -> pd.DataFrame:
    return stations[
        [
            "name",
            "status",
            "risk_band",
            "station_risk_score",
            "local_pressure",
            "free_bikes",
            "empty_slots",
            "capacity",
        ]
    ].rename(
        columns={
            "name": "Estación",
            "status": "Estado",
            "risk_band": "Banda de riesgo",
            "station_risk_score": "Riesgo",
            "local_pressure": "Presión local",
            "free_bikes": "Bicis",
            "empty_slots": "Anclajes",
            "capacity": "Capacidad",
        }
    )


def main() -> None:
    st.set_page_config(
        page_title="Valenbisi Pulse",
        page_icon=":material/directions_bike:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {max-width: 1480px; padding-top: 1.25rem; padding-bottom: 2rem;}
        h1, h2, h3 {letter-spacing: 0 !important; color: #172033;}
        [data-testid="stMetric"] {
            background: #F8FAFC; border: 1px solid #DCE3EA; padding: 0.7rem; border-radius: 6px;
        }
        [data-testid="stSidebar"] {background: #F8FAFC;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Snapshot y riesgo")
        prefer_live = st.toggle("Consultar API en vivo", value=False)
        min_units = st.slider("Mínimo operativo", min_value=0, max_value=6, value=2)
        min_ratio = st.slider("Umbral crítico por capacidad", 0.05, 0.30, 0.10, step=0.01)
        n_clusters = st.slider("Zonas KMeans", min_value=4, max_value=12, value=7)
        neighbors = st.slider("Vecinos para riesgo local", min_value=2, max_value=8, value=4)
        st.divider()
        st.header("Plan de redistribución")
        max_distance = st.slider("Distancia máxima (km)", 0.5, 5.0, 2.5, step=0.25)
        target_ratio = st.slider("Ratio objetivo de bicicletas", 0.25, 0.75, 0.50, step=0.05)
        trigger_ratio = st.slider("Umbral de elegibilidad", 0.10, 0.40, 0.25, step=0.05)
        st.divider()
        st.header("Prueba de estrés")
        stress_ratio = st.slider("Intensidad del flujo", 0.05, 0.35, 0.15, step=0.05)
        core_radius = st.slider("Radio del centro (km)", 0.5, 4.0, 2.0, step=0.25)

    stations, zones, quality, source = load_snapshot(
        prefer_live,
        min_units,
        min_ratio,
        n_clusters,
        neighbors,
    )
    plan, plan_summary = optimize_rebalancing(
        stations,
        max_distance_km=max_distance,
        target_ratio=target_ratio,
        trigger_ratio=trigger_ratio,
    )

    st.title("Valenbisi Pulse")
    st.caption("Centro de control para riesgo, redistribución y pruebas de estrés sobre un snapshot de red")
    if prefer_live:
        st.info(f"Fuente activa: {source}. Los resultados cambian cuando cambia el snapshot.")
    else:
        st.caption(f"Fuente activa: {source}. La muestra está incluida para una demostración reproducible.")

    critical = stations["status"].isin(CRITICAL_STATUSES)
    metrics = st.columns(4)
    metrics[0].metric("Estaciones", len(stations))
    metrics[1].metric("Críticas", int(critical.sum()))
    metrics[2].metric("Riesgo alto o crítico", int(stations["risk_band"].isin(["alto", "crítico"]).sum()))
    metrics[3].metric("Controles de calidad", int((quality["status"] == "revisar").sum()))

    tabs = st.tabs(["Centro", "Riesgo local", "Plan óptimo", "Estrés", "Buscador", "Datos"])

    with tabs[0]:
        left, right = st.columns([1.45, 1])
        with left:
            st.plotly_chart(
                risk_map(stations),
                use_container_width=True,
                key="control_risk_map",
            )
        with right:
            st.plotly_chart(
                status_chart(stations),
                use_container_width=True,
                key="control_status_chart",
            )
            st.dataframe(
                station_table(stations.nlargest(12, "station_risk_score")),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Riesgo": st.column_config.NumberColumn(format="%.1f"),
                    "Presión local": st.column_config.ProgressColumn(
                        format="%.0f%%",
                        min_value=0,
                        max_value=1,
                    ),
                },
            )

    with tabs[1]:
        left, right = st.columns([1.1, 0.9])
        with left:
            st.plotly_chart(
                risk_scatter(stations),
                use_container_width=True,
                key="local_risk_scatter",
            )
        with right:
            st.plotly_chart(
                zone_chart(zones),
                use_container_width=True,
                key="zone_risk_chart",
            )
        zone_table = zones[
            [
                "zone",
                "stations",
                "critical_stations",
                "critical_share",
                "mean_station_risk",
                "max_station_risk",
                "suggested_action",
            ]
        ].rename(
            columns={
                "zone": "Zona",
                "stations": "Estaciones",
                "critical_stations": "Críticas",
                "critical_share": "Proporción crítica",
                "mean_station_risk": "Riesgo medio",
                "max_station_risk": "Riesgo máximo",
                "suggested_action": "Acción",
            }
        )
        st.dataframe(
            zone_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Proporción crítica": st.column_config.ProgressColumn(
                    format="%.0f%%",
                    min_value=0,
                    max_value=1,
                )
            },
        )

    with tabs[2]:
        plan_metrics = st.columns(4)
        plan_metrics[0].metric("Bicis asignadas", plan_summary.bikes_moved)
        plan_metrics[1].metric("Necesidad cubierta", f"{plan_summary.service_share:.1%}")
        plan_metrics[2].metric("Necesidad no cubierta", plan_summary.unmet_need)
        plan_metrics[3].metric("Transporte", f"{plan_summary.transport_km_bikes:.1f} bici-km")
        left, right = st.columns([1.25, 0.75])
        with left:
            st.plotly_chart(
                plan_map(stations, plan),
                use_container_width=True,
                key="minimum_cost_plan_map",
            )
        with right:
            st.metric("Arcos elegibles", plan_summary.eligible_arcs)
            st.metric("Orígenes elegibles", plan_summary.eligible_sources)
            st.metric("Destinos elegibles", plan_summary.eligible_destinations)
            st.metric("Oferta modelada", plan_summary.total_supply)
            st.metric("Necesidad modelada", plan_summary.total_need)
        if plan.empty:
            st.warning("No hay arcos elegibles con los parámetros actuales.")
        else:
            plan_view = plan.rename(
                columns={
                    "origin": "Origen",
                    "destination": "Destino",
                    "distance_km": "Distancia (km)",
                    "bikes_to_move": "Bicis a mover",
                    "transport_km_bikes": "Bici-km",
                    "destination_risk_score": "Riesgo destino",
                }
            )[
                ["Origen", "Destino", "Distancia (km)", "Bicis a mover", "Bici-km", "Riesgo destino"]
            ]
            st.dataframe(
                plan_view,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Distancia (km)": st.column_config.NumberColumn(format="%.2f"),
                    "Bici-km": st.column_config.NumberColumn(format="%.2f"),
                    "Riesgo destino": st.column_config.NumberColumn(format="%.1f"),
                },
            )
            st.download_button(
                "Descargar plan de coste mínimo (CSV)",
                plan.to_csv(index=False).encode("utf-8"),
                file_name="valenbisi_minimum_cost_plan.csv",
                mime="text/csv",
            )

    with tabs[3]:
        scenario_label = st.radio(
            "Dirección simulada",
            ["Flujo hacia el centro", "Flujo desde el centro"],
            horizontal=True,
        )
        direction = "to_core" if scenario_label == "Flujo hacia el centro" else "from_core"
        simulated, stress_summary = simulate_commute_stress(
            stations,
            direction=direction,
            shock_ratio=stress_ratio,
            core_radius_km=core_radius,
            min_units=min_units,
            min_ratio=min_ratio,
        )
        stress_metrics = st.columns(4)
        stress_metrics[0].metric("Bicis desplazadas", int(stress_summary["bikes_shifted"]))
        stress_metrics[1].metric("Críticas base", int(stress_summary["baseline_critical_stations"]))
        stress_metrics[2].metric("Críticas simuladas", int(stress_summary["scenario_critical_stations"]))
        stress_metrics[3].metric("Nuevas críticas", int(stress_summary["newly_critical_stations"]))
        left, right = st.columns([1.25, 0.75])
        with left:
            st.plotly_chart(
                risk_map(add_local_risk_context(simulated, neighbors=neighbors)),
                use_container_width=True,
                key="stress_risk_map",
            )
        with right:
            transitions = scenario_transition_frame(stations, simulated)
            changes = transitions.loc[transitions["status_changed"] | transitions["delta_bikes"].ne(0)].copy()
            changes = changes.rename(
                columns={
                    "name": "Estación",
                    "status_base": "Estado base",
                    "status_scenario": "Estado simulado",
                    "free_bikes_base": "Bicis base",
                    "free_bikes_scenario": "Bicis simuladas",
                    "delta_bikes": "Cambio bicis",
                }
            )
            st.dataframe(
                changes.head(18),
                use_container_width=True,
                hide_index=True,
            )
        st.caption(
            "Prueba determinista que conserva bicicletas al moverlas entre centro y periferia. No usa "
            "histórico de viajes ni representa una predicción de demanda."
        )

    with tabs[4]:
        first, second, third = st.columns([1, 1, 1])
        with first:
            latitude = st.number_input("Latitud", value=float(VALENCIA_CENTER[0]), format="%.6f")
        with second:
            longitude = st.number_input("Longitud", value=float(VALENCIA_CENTER[1]), format="%.6f")
        with third:
            mode_label = st.radio("Necesidad", ["Coger bici", "Devolver bici"], horizontal=True)
        mode = "return" if mode_label == "Devolver bici" else "take"
        nearby = nearest_stations(stations, latitude, longitude, mode=mode, min_available=1, top_n=10)
        if nearby.empty:
            st.warning("No se han encontrado estaciones con disponibilidad para esta necesidad.")
        else:
            nearby_view = nearby[
                [
                    "name",
                    "address",
                    "free_bikes",
                    "empty_slots",
                    "distance_km",
                    "status",
                    "station_risk_score",
                ]
            ].rename(
                columns={
                    "name": "Estación",
                    "address": "Dirección",
                    "free_bikes": "Bicis",
                    "empty_slots": "Anclajes",
                    "distance_km": "Distancia (km)",
                    "status": "Estado",
                    "station_risk_score": "Riesgo",
                }
            )
            st.dataframe(
                nearby_view,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Distancia (km)": st.column_config.NumberColumn(format="%.2f"),
                    "Riesgo": st.column_config.NumberColumn(format="%.1f"),
                },
            )

    with tabs[5]:
        quality_view = quality.rename(
            columns={
                "check": "Control",
                "count": "Registros",
                "type": "Tipo",
                "status": "Estado",
            }
        )
        left, right = st.columns([0.75, 1.25])
        with left:
            st.dataframe(quality_view, use_container_width=True, hide_index=True)
        with right:
            st.markdown(
                """
                **Interpretación responsable**

                El riesgo combina prioridad operativa del snapshot, presión del vecindario, aislamiento y
                desequilibrio. El solver asigna bicicletas por distancia geodésica mínima dentro de las
                restricciones configuradas y penaliza la necesidad no cubierta.

                No se modelan rutas de vehículos, tráfico, capacidad de furgonetas, costes, demanda histórica,
                eventos ni la viabilidad operativa de ejecutar los movimientos. Las zonas KMeans son
                agrupaciones analíticas, no barrios administrativos.
                """
            )
        st.dataframe(station_table(stations), use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar snapshot enriquecido (CSV)",
            stations.to_csv(index=False).encode("utf-8"),
            file_name="valenbisi_snapshot_enriched.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
