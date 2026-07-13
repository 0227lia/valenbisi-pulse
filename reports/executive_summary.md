# Resumen operativo de muestra

Este informe se genera desde `data/sample_valenbisi.csv`, una muestra local determinista. No describe la situación actual de la red y sirve para verificar el pipeline completo.

## Snapshot

- Estaciones: 30.
- Capacidad declarada: 624 plazas.
- Bicicletas disponibles: 226.
- Estaciones críticas con los umbrales base: 21.

## Riesgo de snapshot

- **Hospital Nueva Fe**: riesgo=88.2, estado=Sin bicis, presión local=77%.
- **Avenida Peris Y Valero**: riesgo=87.1, estado=Sin anclajes, presión local=97%.
- **Colon Ii**: riesgo=84.5, estado=Sin bicis, presión local=99%.
- **Cirilo Amoros**: riesgo=82.6, estado=Sin bicis, presión local=98%.
- **Colon I**: riesgo=82.6, estado=Sin bicis, presión local=98%.
- **Avenida De Los Naranjos**: riesgo=80.6, estado=Sin bicis, presión local=70%.
- **Avenida Blasco Ibanez 3**: riesgo=80.2, estado=Sin bicis, presión local=99%.
- **Calle Juan Xxiii**: riesgo=79.5, estado=Sin anclajes, presión local=75%.

## Plan de transporte de coste mínimo

- Orígenes elegibles: 7.
- Destinos elegibles: 14.
- Arcos por debajo de la distancia máxima: 49.
- Bicicletas movidas: 53 de 152 unidades de necesidad modelada.
- Cobertura de necesidad modelada: 34.9%.
- Transporte acumulado: 91.28 bici-km.

## Pruebas de estrés

- Flujo hacia el centro: se desplazan 15 bicicletas dentro de la red; estaciones críticas=15 (nuevas=0).
- Flujo desde el centro: se desplazan 9 bicicletas dentro de la red; estaciones críticas=17 (nuevas=0).

## Límites

El plan usa distancia en línea recta y una instantánea. No incorpora tráfico, rutas reales, capacidad de vehículos, demanda histórica, eventos ni costes laborales. Los escenarios de estrés conservan bicicletas de manera determinista y no son predicciones. Cualquier uso operativo requiere datos actualizados y validación del operador.
