# Guion para vídeo demo: Valenbisi Pulse

Duración objetivo: 4 minutos y 30 segundos.

## 0:00 - 0:30 | Presentación

Hola, soy [tu nombre] y este es Valenbisi Pulse, un centro de control de Ciencia de Datos para analizar una fotografía operativa de Valenbisi en Valencia.

El problema no es solo cuántas bicicletas hay en total: una estación vacía impide empezar un viaje y una estación llena impide terminarlo. La aplicación transforma ese snapshot en riesgo explicable, controles de calidad, un plan de redistribución y pruebas de estrés.

## 0:30 - 1:00 | Datos y alcance

La aplicación puede consultar CityBikes, que expone la red de Valenbisi, y también incluye una muestra local para que todo pueda reproducirse sin conexión.

Cada estación aporta posición, bicicletas, anclajes, capacidad y estado operativo. Es importante ser honesto: no tengo histórico de viajes, así que no presento predicciones de demanda. Todo el análisis es sobre el snapshot cargado.

## 1:00 - 1:50 | Metodología

Primero aplico controles de calidad: duplicados, nombres vacíos, coordenadas fuera del área esperada, capacidad e inventario.

Después calculo ratios de bicicletas y anclajes, desequilibrio y un estado operativo. Sobre eso añado un score de riesgo que combina prioridad de estación, presión del vecindario mediante k vecinos cercanos, aislamiento y desequilibrio.

También agrupo estaciones con KMeans para obtener zonas analíticas. Estas zonas no son barrios administrativos, pero ayudan a pasar de problemas individuales a una visión de área.

Para redistribución formulo un problema de transporte de coste mínimo. El modelo mueve bicicletas desde estaciones con excedente hacia estaciones con déficit, respeta distancia máxima y penaliza la necesidad que no puede cubrirse. El resultado no es una ruta de furgoneta; es un plan de asignación transparente en bici-kilómetros.

## 1:50 - 3:35 | Demo

En el centro de control se ven las métricas del snapshot: estaciones, críticas, riesgo alto y controles de calidad. El mapa colorea la banda de riesgo y el gráfico muestra el reparto de estados.

En Riesgo local vemos qué estaciones combinan presión del entorno y riesgo alto. La segunda visualización compara las zonas KMeans por proporción crítica y riesgo medio.

En Plan óptimo aparecen las rutas de asignación de bicicleta como líneas sobre el mapa. Arriba se muestran bicicletas asignadas, necesidad cubierta, necesidad no cubierta y bici-kilómetros. Puedo modificar distancia máxima, ratio objetivo y umbral de elegibilidad en la barra lateral, y el solver recalcula el resultado.

En Estrés selecciono un flujo hacia o desde el centro. El escenario conserva bicicletas y recalcula estados, pero el propio panel indica que no es forecasting: no afirma que ese flujo vaya a ocurrir.

Por último, el buscador devuelve estaciones cercanas para coger o devolver bici y Datos muestra la calidad del snapshot y sus límites.

## 3:35 - 4:15 | Valor y límites

El valor del proyecto está en separar una señal operacional útil de una promesa exagerada. Se puede inspeccionar por qué una estación aparece arriba, cuánto déficit cubre un plan y qué supuestos se han usado.

Para una implantación real añadiría histórico de viajes, rutas de vehículos, capacidad de furgonetas, tráfico, turnos y restricciones de calle. Esas variables están fuera de este repositorio y se documentan como limitaciones.

## 4:15 - 4:30 | Cierre

En resumen, Valenbisi Pulse convierte datos públicos de estaciones en un sistema reproducible de diagnóstico y apoyo a la decisión, con resultados verificables y límites explícitos.

Gracias.
