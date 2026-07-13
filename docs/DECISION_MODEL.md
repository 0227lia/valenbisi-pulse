# Tarjeta de decisión

## Resumen

Valenbisi Pulse convierte un snapshot público de estaciones en señales de riesgo, controles de calidad, un plan de transporte de coste mínimo y escenarios de estrés. Está pensado para exploración, revisión y demostración técnica.

## Uso previsto

- Priorizar estaciones de un snapshot para inspección o seguimiento.
- Explicar qué componentes elevan la prioridad de una estación.
- Cuantificar déficit cubrible bajo una distancia y ratio objetivo explícitos.
- Ensayar sensibilidad a un flujo centro-periferia que conserva bicicletas.

## Usos no previstos

- Predecir viajes, demanda, ocupación futura o ingresos.
- Despachar vehículos o sustituir una ruta operativa real.
- Tomar decisiones de seguridad, empleo o inversión sin revisión humana.
- Presentar la muestra local como estado actual de Valenbisi.

## Entradas y salidas

| Elemento | Descripción |
|---|---|
| Entrada | Snapshot de estaciones públicas con inventario, capacidad, estado y coordenadas. |
| Riesgo | Heurística de snapshot con contexto k-NN e aislamiento. |
| Plan | LP de transporte con oferta, demanda, arcos de distancia y necesidad no cubierta. |
| Estrés | Flujo determinista entre centro y periferia. |
| Salidas | Dashboard, CSV, JSON, tablas de calidad y figuras estáticas. |

## Evidencia de calidad

- Muestra versionada para ejecución offline y artefactos reproducibles.
- Tests de limpieza, clasificación, KMeans, proximidad, solver, estrés y zonas.
- Semillas fijas donde existe aleatoriedad (`KMeans=42`).
- Ruff, pytest, importación de dashboard y reconstrucción de reportes en CI.

## Riesgos y controles

| Riesgo | Control | Riesgo residual |
|---|---|---|
| Snapshot incompleto | Tabla de calidad visible. | La API puede no exponer todos los estados. |
| Score subjetivo | Fórmula y pesos publicados. | No representa demanda ni consenso operativo. |
| Optimización engañosa | Necesidad no cubierta, distancia máxima y límites explícitos. | No resuelve rutas ni vehículos. |
| Estrés interpretado como forecast | Etiquetas y límites visibles. | Un escenario simple puede parecer realista. |
| Datos obsoletos | Fuente activa visible y muestra separada. | Un snapshot en vivo envejece rápidamente. |

## Revisión antes de uso externo

1. Confirmar que el snapshot tiene fecha, cobertura y calidad suficientes.
2. Acordar umbrales y ratio objetivo con el operador.
3. Incorporar histórico de viajes, tiempos de ruta, capacidad de vehículos y restricciones reales.
4. Revisar el plan con una persona responsable de operaciones antes de ejecutar cualquier movimiento.
