# Corte Hoy

Cortes de luz programados en Lima y Callao, por día y por distrito: https://cortehoy.toca.pe

Junta los avisos de mantenimiento de **Pluz Energía** (PDF semanal) y **Luz del Sur**
(consulta de su web) en páginas estáticas, una por distrito. GitHub Actions las
regenera cada 6 horas y las publica en GitHub Pages.

## Correr en local

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m scraper --output out/cortes.json
.venv/Scripts/python site/build.py --data out/cortes.json --out public --base-url http://127.0.0.1:8000
.venv/Scripts/python -m pytest -q scraper/tests site
```

## Qué no incluye

Cortes de agua: Sedapal no publica sus cortes programados como lista en su web.
Cortes por fallas: no se anuncian.

## Fuentes y respeto

Una petición por segundo, con un User-Agent que dice quiénes somos. Se copia el
texto del aviso tal como lo publica la empresa y se enlaza al original.
¿Un error? Escribe a 3b3n3z3r333@gmail.com.
