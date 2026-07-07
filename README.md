# Valenbisi Pulse

Aplicacion interactiva de Data Science para diagnosticar y mejorar la disponibilidad de Valenbisi en Valencia.

## Problema urbano

En los sistemas de bicicleta compartida no basta con tener muchas bicicletas en total. Si una estacion esta vacia, nadie puede iniciar viaje. Si esta llena, nadie puede devolver la bici. Esto genera frustracion, recorridos innecesarios y peor uso del espacio publico.

Valenbisi Pulse ayuda a responder tres preguntas:

1. Que estaciones estan ahora mismo en situacion critica?
2. Que zonas urbanas concentran desequilibrios?
3. Que movimientos de redistribucion deberia priorizar un operador municipal?

## Datos abiertos

La app usa la API abierta de CityBikes para la red `valenbisi`, alimentada por datos abiertos de JCDecaux:

- API: https://api.citybik.es/v2/networks/valenbisi
- Licencia indicada por la API: JCDecaux Open Licence

Tambien se incluye una muestra local en `data/sample_valenbisi.csv` para que la app siga funcionando si la API no responde durante la demo.

## Metodologia DS

La aplicacion aplica un pipeline reproducible:

1. **Ingestion de datos**: descarga estaciones, coordenadas, bicicletas disponibles, anclajes libres y capacidad.
2. **Limpieza**: normaliza nombres, direcciones, tipos numericos y capacidad real.
3. **Feature engineering**:
   - ratio de bicicletas disponibles
   - ratio de anclajes libres
   - indice de desequilibrio
   - estado operativo de la estacion
4. **Clasificacion de riesgo**: etiqueta estaciones como equilibradas, sin bicis, sin anclajes, critica mixta o a revisar.
5. **Clustering geoespacial**: agrupa estaciones en zonas urbanas usando k-means implementado con NumPy sobre coordenadas proyectadas.
6. **Scoring multicriterio**: calcula una prioridad de 0 a 100 combinando criticidad, desequilibrio y capacidad.
7. **Recomendacion de redistribucion**: propone traslados desde estaciones con exceso de bicis hacia estaciones con deficit, limitando distancia maxima.

## Funcionalidades

- Mapa interactivo de estaciones por estado.
- Tabla de estaciones prioritarias.
- Clustering de zonas urbanas con accion sugerida.
- Plan descargable de redistribucion en CSV.
- Buscador de estaciones cercanas para coger o devolver una bici.
- Parametros ajustables para simular politicas municipales.

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Si `python` no esta en el PATH, usa el Python de tu entorno o Anaconda.

## Despliegue en Streamlit Community Cloud

1. Crea un repositorio en GitHub y sube estos archivos.
2. Entra en https://streamlit.io/cloud.
3. Selecciona **New app**.
4. Elige tu repositorio, rama principal y `app.py` como archivo de entrada.
5. Pulsa **Deploy**.
6. Copia la URL generada y pegala en la entrega como "Link to the online app".


## Estructura

```text
.
├── app.py
├── requirements.txt
├── data/
│   └── sample_valenbisi.csv
├── docs/
│   └── video_script.md
├── artifacts/
│   └── demo_valenbisi_pulse.mp4
└── src/
    └── valenbisi.py
```
