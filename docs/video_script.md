# Guion para video demo - Valenbisi Pulse

Duracion objetivo: 4 minutos 30 segundos. Maximo permitido: 5 minutos.

## 0:00 - 0:25 Presentacion

Hola, soy [tu nombre] y este es mi proyecto de EDM: Valenbisi Pulse, una aplicacion interactiva para analizar el estado de las estaciones de Valenbisi en Valencia y proponer acciones de mejora.

El problema urbano que aborda es sencillo: una estacion puede estar vacia y no permitir coger bici, o estar llena y no permitir devolverla. Eso empeora la movilidad ciclista y hace que el servicio sea menos fiable.

## 0:25 - 0:55 Datos abiertos

La aplicacion usa datos abiertos en tiempo real de la red Valenbisi a traves de CityBikes, que expone informacion procedente de JCDecaux Open Data.

Para cada estacion tengo coordenadas, bicicletas disponibles, anclajes libres, capacidad total y estado operativo. Tambien he incluido una muestra local para que la app siga funcionando si la API falla durante la demo.

## 0:55 - 1:45 Metodologia DS

La metodologia tiene varias fases.

Primero, hago ingestion y limpieza de datos: normalizo nombres, direcciones, coordenadas y campos numericos.

Despues creo variables derivadas: ratio de bicicletas, ratio de anclajes, indice de desequilibrio y estado de cada estacion.

Luego calculo una puntuacion de prioridad de 0 a 100. Esta puntuacion combina tres factores: la criticidad de la estacion, el desequilibrio respecto a un estado ideal y la capacidad de la estacion, porque no es igual fallar en una estacion pequena que en una estacion grande.

Tambien aplico clustering geoespacial tipo k-means para agrupar estaciones en zonas urbanas y analizar problemas por area, no solo estacion por estacion.

Por ultimo, la app genera recomendaciones de redistribucion: detecta estaciones con exceso de bicicletas y estaciones con deficit, y propone movimientos dentro de una distancia maxima.

## 1:45 - 3:40 Demo de la app

En la pantalla principal vemos las metricas globales: numero de estaciones, bicicletas disponibles, anclajes libres, estaciones criticas y ocupacion global.

En el primer mapa, cada estacion aparece coloreada segun su estado. Podemos filtrar por estaciones sin bicis, sin anclajes o desequilibradas. A la derecha aparece un ranking de estaciones con mayor prioridad.

Ahora voy a la pestana de zonas prioritarias. Aqui se ven las zonas urbanas generadas por clustering. La tabla resume bicicletas, anclajes, ocupacion y accion recomendada. Esto es util para que un operador no tenga que mirar cientos de puntos sueltos.

En la pestana de redistribucion, la aplicacion propone movimientos concretos. Por ejemplo, retirar bicicletas de una estacion llena y llevarlas a otra donde faltan bicicletas. El usuario puede cambiar la distancia maxima y el ratio objetivo para simular distintas politicas.

En el buscador, introduzco una ubicacion y la app devuelve estaciones cercanas para coger o devolver bici. Esto muestra tambien un beneficio directo para usuarios finales.

## 3:40 - 4:25 Beneficios

Los beneficios principales son tres.

Primero, mejora la experiencia ciudadana, porque ayuda a reducir estaciones vacias o llenas.

Segundo, ayuda a la toma de decisiones operativas, porque prioriza donde actuar y que movimientos realizar.

Tercero, permite explorar escenarios: cambiando los umbrales se puede ver como cambia el numero de estaciones criticas o las rutas de redistribucion.

## 4:25 - 4:45 Cierre

En resumen, Valenbisi Pulse convierte datos abiertos de movilidad en una herramienta practica de diagnostico y recomendacion para una ciudad mas eficiente y sostenible.

Gracias.

## Consejos para grabarlo

- Graba pantalla y voz con OBS, Zoom, PowerPoint o Loom.
- No intentes explicarlo todo: sigue el guion y ensena solo las pestanas clave.
- Si vas justo de tiempo, salta el buscador y centra la demo en mapa, zonas y redistribucion.
- Puedes decir "equipo individual" al inicio si el profesor lo pide.
