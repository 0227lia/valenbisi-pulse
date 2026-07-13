# Datos

## Muestra reproducible

`sample_valenbisi.csv` es una captura local de 30 estaciones con campos de inventario, capacidad, coordenadas y estado. Sirve para ejecutar tests, generar figuras y validar el pipeline sin red.

No debe interpretarse como el estado actual de Valenbisi. La fecha incluida pertenece al snapshot y no se actualiza automáticamente.

## Fuente en vivo

La aplicación puede consultar la red [Valenbisi en CityBikes](https://api.citybik.es/v2/networks/valenbisi). Esa respuesta es volátil y no se guarda como parte de los commits. La API identifica a JCDecaux como proveedor de la red.

## Privacidad y reutilización

El proyecto usa información agregada de estaciones, sin datos personales. Revisa los términos de la fuente antes de redistribuir una captura o utilizarla fuera del propósito de análisis.
