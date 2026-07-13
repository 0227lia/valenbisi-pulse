# Metodología

## 1. Alcance

Valenbisi Pulse es una herramienta de apoyo para una **fotografía operativa** de una red de bicicleta compartida. Analiza disponibilidad, anclajes, riesgo local y posibles movimientos dentro de un snapshot. No es un modelo de demanda, forecasting, ruteo de vehículos ni optimización de turnos.

## 2. Datos y trazabilidad

La aplicación puede consultar `https://api.citybik.es/v2/networks/valenbisi`. Si no se solicita o la red no responde, usa `data/sample_valenbisi.csv`, un snapshot local versionado para pruebas y demostración.

Cada estación aporta identificador, nombre, coordenadas, bicicletas disponibles, anclajes libres, capacidad y banderas de operación. No se procesan datos personales. Los datos en vivo cambian tras cada consulta y no se versionan automáticamente.

## 3. Preparación y calidad

La limpieza normaliza textos, convierte tipos, reconcilia capacidad declarada con inventario visible y elimina coordenadas inválidas. Se publica una tabla de controles:

- IDs duplicados;
- nombres vacíos;
- coordenadas fuera del área esperada de Valencia;
- capacidad no positiva;
- inventario que supera la capacidad;
- estaciones no operativas.

Los controles son alertas de calidad, no una certificación de que los datos de origen sean correctos.

## 4. Clasificación operativa

Para cada estación se calculan:

```text
bike_ratio = bicicletas disponibles / capacidad
dock_ratio = anclajes libres / capacidad
imbalance = 2 * abs(bike_ratio - 0,5)
```

La estación se etiqueta como `Sin bicis`, `Sin anclajes`, `Critica mixta`, `Revisar`, `Equilibrada` o `Desequilibrada` según umbral absoluto, umbral relativo y operación. El score base combina profundidad del déficit, desequilibrio y capacidad; su finalidad es ordenar revisión.

## 5. Riesgo local

Se construye una vecindad de `k` estaciones por distancia geodésica. Para cada estación se agregan ratio de bicicletas, desequilibrio y proporción crítica de sus vecinas, además de la distancia a la vecina más cercana.

```text
local_pressure = 0,60 * critical_share_kNN + 0,40 * mean_imbalance_kNN
risk = 100 * (0,55 * priority_score/100 + 0,25 * local_pressure
              + 0,12 * isolation_score + 0,08 * imbalance)
```

Las estaciones no operativas se fijan en riesgo 100. El score es un índice de **riesgo del snapshot**: no es probabilidad calibrada de fallo ni predicción de demanda.

## 6. Zonas analíticas

Las coordenadas se proyectan localmente a kilómetros y se agrupan con `KMeans`, `random_state=42`. Cada zona resume capacidad, proporción crítica, presión local y riesgo. No coincide necesariamente con barrios o distritos municipales.

## 7. Transporte de coste mínimo

El plan establece un objetivo de bicicletas por estación `target = round(capacidad * ratio_objetivo)`. Son orígenes las estaciones con ratio alto y excedente respecto a ese objetivo; son destinos las estaciones con ratio bajo y déficit.

Para cada arco elegible `i -> j` por debajo de la distancia máxima se define una variable `x_ij`. Se añade una variable `u_j` de necesidad no cubierta para cada destino y se resuelve:

```text
min sum(d_ij * x_ij) + sum(lambda_j * u_j)
sujeto a  sum_j x_ij <= excedente_i
           sum_i x_ij + u_j = deficit_j
           x_ij, u_j >= 0
```

`lambda_j = 20 * distancia_maxima * (1 + riesgo_j/100)` hace costoso dejar sin cobertura un destino más riesgoso. El problema se resuelve con HiGHS mediante `scipy.optimize.linprog`. La matriz de transporte produce soluciones enteras para estas ofertas y demandas; se validan como unidades de bicicleta.

El coste es distancia en línea recta por bicicleta (`bici-km`), no longitud de ruta, tiempo ni coste financiero.

## 8. Pruebas de estrés

Las pruebas `Flujo hacia el centro` y `Flujo desde el centro` separan las estaciones por un radio configurable respecto al centro de Valencia. En las estaciones de origen se solicita una fracción de bicicletas disponibles; la misma cantidad se reparte en estaciones destino según anclajes libres.

La simulación conserva bicicletas, no supera capacidad y recalcula el estado resultante. No utiliza histórico, estimación de intención de viaje, eventos o meteorología: es un escenario determinista de sensibilidad, no un pronóstico.

## 9. Reproducibilidad

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest
python scripts/generate_sample_report.py
streamlit run app.py
```

La CI ejecuta lint, tests, importación del dashboard y reconstrucción de la muestra sin conexión.

## 10. Limitaciones

- No hay serie temporal ni demanda observada.
- Los estados pueden cambiar segundos después de la consulta.
- No se modelan rutas, tráfico, vehículos, coste laboral, turnos ni restricciones legales.
- Los umbrales y pesos son parámetros analíticos debatibles.
- Una recomendación de movimiento requiere validación del operador antes de ejecutarse.
