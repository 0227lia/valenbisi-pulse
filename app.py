from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.valenbisi import (
    VALENCIA_CENTER,
    assign_zones,
    classify_station_status,
    load_valenbisi_data,
    nearest_stations,
    recommend_rebalancing,
    status_counts,
    summarize_zones,
)


st.set_page_config(
    page_title="Valenbisi Pulse",
    page_icon="V",
    layout="wide",
    initial_sidebar_state="expanded",
)


STATUS_COLORS = {
    "Equilibrada": "#2E7D32",
    "Desequilibrada": "#F9A825",
    "Sin bicis": "#C62828",
    "Sin anclajes": "#6A1B9A",
    "Critica mixta": "#263238",
    "Revisar": "#1565C0",
}


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    .small-note {
        color: #53636f;
        font-size: 0.92rem;
        line-height: 1.35;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=180)
def get_data(prefer_live: bool, min_units: int, min_ratio: float, n_clusters: int) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    stations, source = load_valenbisi_data(prefer_live=prefer_live)
    stations = classify_station_status(stations, min_units=min_units, min_ratio=min_ratio)
    stations = assign_zones(stations, n_clusters=n_clusters)
    zones = summarize_zones(stations)
    return stations, zones, source


def format_ratio(value: float) -> str:
    return f"{value:.0%}"


def station_map(df: pd.DataFrame, title: str) -> go.Figure:
    fig = px.scatter_map(
        df,
        lat="latitude",
        lon="longitude",
        color="status",
        size="priority_score",
        color_discrete_map=STATUS_COLORS,
        hover_name="name",
        hover_data={
            "address": True,
            "free_bikes": True,
            "empty_slots": True,
            "capacity": True,
            "bike_ratio": ":.0%",
            "priority_score": ":.1f",
            "latitude": False,
            "longitude": False,
        },
        zoom=12,
        height=620,
        title=title,
    )
    fig.update_layout(
        map_style="carto-positron",
        margin=dict(l=0, r=0, t=44, b=0),
        legend_title_text="Estado",
    )
    return fig


def zone_map(zones: pd.DataFrame) -> go.Figure:
    fig = px.scatter_map(
        zones,
        lat="latitude",
        lon="longitude",
        size="capacity",
        color="suggested_action",
        hover_name="zone",
        hover_data={
            "stations": True,
            "free_bikes": True,
            "empty_slots": True,
            "bike_ratio": ":.0%",
            "priority_score": ":.1f",
            "latitude": False,
            "longitude": False,
        },
        zoom=12,
        height=480,
        color_discrete_map={
            "Enviar bicicletas": "#C62828",
            "Liberar anclajes": "#6A1B9A",
            "Mantener": "#2E7D32",
            "Monitorizar": "#F9A825",
        },
    )
    fig.update_layout(map_style="carto-positron", margin=dict(l=0, r=0, t=8, b=0), legend_title_text="Accion")
    return fig


def bar_status(counts: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        counts,
        x="status",
        y="stations",
        color="status",
        color_discrete_map=STATUS_COLORS,
        text="stations",
        height=300,
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Estaciones")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


st.title("Valenbisi Pulse")
st.caption("Diagnostico interactivo para mejorar la disponibilidad de bicicletas y anclajes en Valencia.")

with st.sidebar:
    st.header("Parametros")
    prefer_live = st.toggle("Usar datos en vivo", value=True)
    min_units = st.slider("Minimo operativo de bicis/anclajes", min_value=0, max_value=6, value=2)
    min_ratio = st.slider("Umbral critico por capacidad", min_value=0.05, max_value=0.30, value=0.10, step=0.01)
    n_clusters = st.slider("Zonas urbanas estimadas", min_value=4, max_value=12, value=7)
    max_distance = st.slider("Distancia maxima para redistribuir", min_value=0.5, max_value=5.0, value=2.5, step=0.25)
    target_ratio = st.slider("Ratio objetivo de bicicletas", min_value=0.35, max_value=0.65, value=0.50, step=0.05)
    st.markdown(
        '<p class="small-note">Los parametros permiten simular politicas municipales mas estrictas o mas flexibles.</p>',
        unsafe_allow_html=True,
    )


stations, zones, source = get_data(prefer_live, min_units, min_ratio, n_clusters)
critical = stations[stations["status"].isin(["Sin bicis", "Sin anclajes", "Critica mixta", "Revisar"])]
counts = status_counts(stations)

total_bikes = int(stations["free_bikes"].sum())
total_docks = int(stations["empty_slots"].sum())
total_capacity = int(stations["capacity"].sum())
global_ratio = total_bikes / total_capacity if total_capacity else 0

metric_cols = st.columns(5)
metric_cols[0].metric("Estaciones", f"{len(stations):,}".replace(",", "."))
metric_cols[1].metric("Bicis disponibles", f"{total_bikes:,}".replace(",", "."))
metric_cols[2].metric("Anclajes libres", f"{total_docks:,}".replace(",", "."))
metric_cols[3].metric("Estaciones criticas", f"{len(critical):,}".replace(",", "."))
metric_cols[4].metric("Ocupacion global", format_ratio(global_ratio))

st.markdown(
    f'<p class="small-note">Fuente: {source}. La clasificacion se recalcula al cambiar los umbrales del panel lateral.</p>',
    unsafe_allow_html=True,
)

tabs = st.tabs(["Mapa operativo", "Zonas prioritarias", "Redistribucion", "Buscador", "Metodologia"])

with tabs[0]:
    left, right = st.columns([2.1, 1])
    with left:
        status_options = list(STATUS_COLORS.keys())
        selected_status = st.multiselect("Filtrar estado", status_options, default=status_options)
        shown = stations[stations["status"].isin(selected_status)] if selected_status else stations
        st.plotly_chart(station_map(shown, "Estado de estaciones Valenbisi"), use_container_width=True)
    with right:
        st.plotly_chart(bar_status(counts), use_container_width=True)
        top_table = (
            stations.sort_values("priority_score", ascending=False)
            .head(12)[["name", "status", "free_bikes", "empty_slots", "capacity", "priority_score"]]
            .rename(
                columns={
                    "name": "Estacion",
                    "status": "Estado",
                    "free_bikes": "Bicis",
                    "empty_slots": "Anclajes",
                    "capacity": "Capacidad",
                    "priority_score": "Prioridad",
                }
            )
        )
        st.dataframe(top_table, hide_index=True, use_container_width=True)

with tabs[1]:
    st.subheader("Zonas urbanas estimadas por clustering geoespacial")
    zone_left, zone_right = st.columns([1.6, 1])
    with zone_left:
        st.plotly_chart(zone_map(zones), use_container_width=True)
    with zone_right:
        zone_table = zones[
            [
                "zone",
                "stations",
                "free_bikes",
                "empty_slots",
                "bike_ratio",
                "critical_stations",
                "suggested_action",
                "priority_score",
            ]
        ].rename(
            columns={
                "zone": "Zona",
                "stations": "Estaciones",
                "free_bikes": "Bicis",
                "empty_slots": "Anclajes",
                "bike_ratio": "Ocupacion",
                "critical_stations": "Criticas",
                "suggested_action": "Accion",
                "priority_score": "Prioridad",
            }
        )
        st.dataframe(zone_table, hide_index=True, use_container_width=True)

with tabs[2]:
    st.subheader("Plan de redistribucion sugerido")
    plan = recommend_rebalancing(stations, max_distance_km=max_distance, target_ratio=target_ratio)
    if plan.empty:
        st.info("No se han encontrado movimientos claros con los parametros actuales.")
    else:
        plan_view = plan.rename(
            columns={
                "origin": "Origen",
                "destination": "Destino",
                "distance_km": "Distancia km",
                "bikes_to_move": "Bicis a mover",
                "origin_free_bikes": "Bicis en origen",
                "destination_free_bikes": "Bicis en destino",
                "destination_empty_slots": "Anclajes destino",
                "impact": "Impacto",
            }
        )
        st.dataframe(plan_view, hide_index=True, use_container_width=True)
        st.download_button(
            "Descargar plan CSV",
            plan_view.to_csv(index=False).encode("utf-8"),
            file_name="plan_redistribucion_valenbisi.csv",
            mime="text/csv",
        )

with tabs[3]:
    st.subheader("Encontrar estacion cercana")
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        latitude = st.number_input("Latitud", value=float(VALENCIA_CENTER[0]), format="%.6f")
    with col_b:
        longitude = st.number_input("Longitud", value=float(VALENCIA_CENTER[1]), format="%.6f")
    with col_c:
        mode_label = st.radio("Necesidad", ["Coger bici", "Devolver bici"], horizontal=True)
    mode = "return" if mode_label == "Devolver bici" else "take"
    nearest = nearest_stations(stations, latitude, longitude, mode=mode, min_available=1, top_n=10)
    nearest_view = nearest[
        ["name", "address", "free_bikes", "empty_slots", "distance_km", "status"]
    ].rename(
        columns={
            "name": "Estacion",
            "address": "Direccion",
            "free_bikes": "Bicis",
            "empty_slots": "Anclajes",
            "distance_km": "Distancia km",
            "status": "Estado",
        }
    )
    st.dataframe(nearest_view, hide_index=True, use_container_width=True)
    st.plotly_chart(station_map(nearest, "Estaciones cercanas disponibles"), use_container_width=True)

with tabs[4]:
    st.subheader("Metodologia de Data Science")
    st.markdown(
        """
        **Problema urbano.** La disponibilidad de bicicletas compartidas no depende solo del total de bicicletas:
        una estacion puede estar llena y no aceptar devoluciones, o vacia y no permitir iniciar viajes.

        **Datos.** Se usa la API abierta de CityBikes para Valenbisi, alimentada por JCDecaux Open Data.
        Cada estacion aporta coordenadas, capacidad, bicicletas disponibles, anclajes libres y estado operativo.

        **Transformacion.** La aplicacion normaliza textos, calcula capacidad real, ratios de ocupacion,
        desequilibrio y etiquetas operativas segun umbrales configurables.

        **Metodos DS.** Se aplica clustering geoespacial tipo k-means sobre coordenadas proyectadas, scoring
        multicriterio de prioridad y una heuristica de optimizacion para proponer movimientos entre estaciones
        con exceso de bicicletas y estaciones con deficit.

        **Impacto.** La herramienta ayuda a priorizar rutas de redistribucion, detectar zonas problematicas y
        mejorar la experiencia de usuarios que necesitan coger o devolver bicicletas.
        """
    )
