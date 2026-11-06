# Corte Hoy

Cortes de luz programados en Lima y Callao, por día y por distrito: https://cortehoy.toca.pe

Junta los avisos de mantenimiento de **Pluz Energía** (PDF semanal) y **Luz del Sur**
(consulta de su web), y los cortes de agua de **Sedapal** (mapa de interrupciones), en páginas estáticas, una por distrito. GitHub Actions las
regenera cada 2 horas y las publica en GitHub Pages.

## Correr en local

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m scraper --output out/cortes.json
.venv/Scripts/python site/build.py --data out/cortes.json --out public --base-url http://127.0.0.1:8000
.venv/Scripts/python -m pytest -q scraper/tests site
```

## Qué no incluye

Cortes de luz por fallas: no se anuncian. Cortes de agua fuera de Lima y Callao.

## Agua (Sedapal)

`scraper/sedapal.py` lee la capa "Incidencias" del mapa público de interrupciones de Sedapal
(ArcGIS, `HEC/SGIO_TOTAL/MapServer/1`): programadas e imprevistas, con distrito, zonas, horario y
causa. No se publica el campo INFOR_WEB (trae nombres del personal). Páginas: `/agua/` y
`/agua/distrito/<slug>/`, enlazadas con la página de luz del mismo distrito.

## Fuentes y respeto

Una petición por segundo, con un User-Agent que dice quiénes somos. Se copia el
texto del aviso tal como lo publica la empresa y se enlaza al original.
¿Un error? Escribe a 3b3n3z3r333@gmail.com.
