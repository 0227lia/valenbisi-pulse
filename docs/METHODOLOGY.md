# Metodología

## Objetivo

Valenbisi Pulse convierte una fotografía operativa de la red en tres salidas: estado de cada estación, zonas con desequilibrio y una propuesta limitada de redistribución. No intenta predecir demanda futura ni sustituir la planificación del operador.

## Datos

La aplicación consulta la red `valenbisi` de CityBikes, alimentada por datos abiertos de JCDecaux. Cada registro contiene coordenadas, bicicletas disponibles, anclajes libres, capacidad y estado operativo. Si la API no responde, se utiliza una muestra local incluida exclusivamente para que la demostración sea reproducible.

## Preparación

1. Normalización de nombres, direcciones y tipos numéricos.
2. Reconciliación de capacidad declarada con bicicletas y anclajes observados.
3. Eliminación de registros sin coordenadas válidas.
4. Cálculo de ratios de bicicletas, anclajes e índice de desequilibrio.

## Clasificación operativa

Una estación se marca como crítica cuando queda por debajo del mínimo absoluto o del mínimo relativo configurado. Se distinguen estaciones sin bicicletas, sin anclajes, con ambos problemas o fuera de servicio. El `priority_score` combina profundidad del déficit, desequilibrio y capacidad.

Los pesos son una heurística transparente para ordenar la revisión. No representan costes, demanda esperada ni impacto causal.

## Zonas

Las coordenadas se proyectan de forma local a kilómetros y se agrupan mediante `KMeans` de scikit-learn con semilla fija. Las zonas son agrupaciones analíticas, no barrios administrativos. Cambiar el número de grupos modifica su interpretación.

## Redistribución

El algoritmo identifica estaciones por encima y por debajo de un ratio objetivo. Después asigna bicicletas desde el origen elegible más cercano, respetando distancia máxima, disponibilidad y necesidad. Es una heurística voraz: no incluye tráfico, rutas de vehículos, costes laborales ni demanda futura.

## Validación

Los tests cubren limpieza, clasificación, clustering determinista, búsqueda por proximidad, muestra sin conexión y conservación de unidades en la redistribución. `scripts/generate_sample_report.py` genera resultados reproducibles sobre la muestra local.

## Limitaciones

- La API representa un instante, no una serie temporal.
- La disponibilidad puede cambiar segundos después de la consulta.
- La muestra local no debe usarse para evaluar el estado actual de la red.
- Las recomendaciones requieren validación operativa antes de aplicarse.
- No se modelan demanda, eventos, meteorología, pendientes ni restricciones de circulación.

