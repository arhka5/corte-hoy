"""Genera el sitio estático de Corte Hoy a partir de cortes.json.

    python site/build.py --data out/cortes.json --out public [--base-url URL]

Una página por distrito existe siempre ("Corte de luz hoy en Los Olivos"),
aunque no haya cortes: así quien busca su distrito encuentra la respuesta,
también cuando la respuesta es "no hay cortes programados".
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import og

HERE = Path(__file__).resolve().parent
LIMA = timezone(timedelta(hours=-5))
BASE_URL = "https://cortehoy.toca.pe"
CONTACTO = "3b3n3z3r333@gmail.com"  # único medio de contacto público
ADSENSE = "ca-pub-6522291453297769"  # anuncios automáticos de AdSense (cuenta del dominio toca.pe)

EMPRESAS = {
    "pluz": {"nombre": "Pluz Energía", "zona": "Lima norte, Lima centro y Callao",
             "url": "https://www.pluz.pe/es/ayuda/enterate-de-los-cortes-de-luz-programados.html"},
    "luzdelsur": {"nombre": "Luz del Sur", "zona": "Lima sur y este",
                  "url": "https://www.luzdelsur.pe/es/corteluz"},
    "hidrandina": {"nombre": "Hidrandina", "zona": "La Libertad, Áncash y Cajamarca",
                   "url": "https://aplicaciones.distriluz.com.pe/Apps/Visits/Home/CortesProgramados"},
}
# Página por empresa (/pluz/, /luz-del-sur/, /hidrandina/), sin fecha en el título como la portada.
EMPRESAS_PAGINA = {
    "pluz": {"slug": "pluz", "titulo": "Corte de luz Pluz hoy (ex Enel, Edelnor): horarios por distrito",
             "h1": "Cortes de luz de Pluz hoy",
             "intro": "Pluz Energía Perú es la distribuidora de Lima norte, Lima centro, el Callao y el norte chico "
                      "(Huacho, Huaral, Barranca). Antes se llamaba Enel Distribución Perú y, antes, Edelnor: si "
                      "buscas «corte de luz Enel» o «Edelnor», es la misma empresa. Publica cada semana un PDF con "
                      "sus cortes programados por mantenimiento, con las calles y manzanas afectadas."},
    "luzdelsur": {"slug": "luz-del-sur", "titulo": "Corte de luz Luz del Sur hoy: horarios por distrito",
                  "h1": "Cortes de luz de Luz del Sur hoy",
                  "intro": "Luz del Sur es la distribuidora de Lima sur y este (Surco, San Juan de Miraflores, Villa "
                           "El Salvador, Ate, La Molina, Chorrillos y más). Publica solo los cortes del día, por "
                           "distrito y con horario, sin las calles: para saber si incluye tu casa, consulta con tu "
                           "número de suministro en su web."},
    "hidrandina": {"slug": "hidrandina", "titulo": "Corte de luz Hidrandina hoy: La Libertad, Áncash y Cajamarca",
                   "h1": "Cortes de luz de Hidrandina hoy",
                   "intro": "Hidrandina (grupo Distriluz) es la distribuidora de La Libertad, Áncash y Cajamarca: "
                            "Trujillo, Chimbote, Huaraz, Cajamarca y alrededores. Publica sus cortes programados "
                            "con fecha, horario y los sectores afectados."},
}
SEDAPAL = {"nombre": "Sedapal", "zona": "Lima y Callao",
           "url": "https://sedapal.maps.arcgis.com/apps/webappviewer/index.html?id=32603d5182d846f69bd4cb6703d66e88",
           "fono": "(01) 317-8000"}
# Norte chico: el agua no es de Sedapal (EPS de Huacho, Huaral, Barranca…), sin página de agua.
SIN_SEDAPAL = {"huacho", "hualmay", "huaral", "chancay", "barranca", "huaura", "santa-maria"}
LIMA_REGION = "Lima y Callao"
# Regiones fuera de Lima: página propia (/region/<slug>/) y distritos con la región en la URL
# (/distrito/trujillo-la-libertad/), porque hay nombres repetidos (Independencia en Lima y en Huaraz).
REGIONES = {
    "La Libertad": {"slug": "la-libertad", "ciudades": "Trujillo", "empresas": "Hidrandina"},
    "Áncash": {"slug": "ancash", "ciudades": "Chimbote y Huaraz", "empresas": "Hidrandina"},
    "Cajamarca": {"slug": "cajamarca", "ciudades": "Cajamarca", "empresas": "Hidrandina"},
}
ALIAS_PROVINCIA = {"banos-del-inca": "los-banos-del-inca"}

# Distritos con página fija (Lima Metropolitana, Callao y norte chico atendido por Pluz).
DISTRITOS = [
    "Ancón", "Ate", "Barranco", "Breña", "Carabayllo", "Chaclacayo", "Chorrillos", "Cieneguilla", "Comas",
    "El Agustino", "Independencia", "Jesús María", "La Molina", "La Victoria", "Lima Cercado", "Lince",
    "Los Olivos", "Lurigancho", "Lurín", "Magdalena del Mar", "Miraflores", "Pachacámac", "Pucusana",
    "Pueblo Libre", "Puente Piedra", "Punta Hermosa", "Punta Negra", "Rímac", "San Bartolo", "San Borja",
    "San Isidro", "San Juan de Lurigancho", "San Juan de Miraflores", "San Luis", "San Martín de Porres",
    "San Miguel", "Santa Anita", "Santa María del Mar", "Santa Rosa", "Santiago de Surco", "Surquillo",
    "Villa El Salvador", "Villa María del Triunfo",
    "Callao", "Bellavista", "Carmen de la Legua", "La Perla", "La Punta", "Mi Perú", "Ventanilla",
    "Huacho", "Hualmay", "Huaral", "Chancay", "Barranca", "Huaura", "Santa María",
]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes(t).lower()).strip("-")


CANON = {slug(d): d for d in DISTRITOS}
ALIAS = {"cercado-de-lima": "lima-cercado", "lima": "lima-cercado", "cercado": "lima-cercado",
         "surco": "santiago-de-surco", "magdalena": "magdalena-del-mar", "sjl": "san-juan-de-lurigancho",
         "smp": "san-martin-de-porres",
         # Luz del Sur escribe el distrito con su capital: "LURIGANCHO-CHOSICA"
         "lurigancho-chosica": "lurigancho", "chosica": "lurigancho"}
MAX_HISTORIAL = 15  # cortes recientes que se muestran por distrito


def distrito(nombre_fuente: str) -> tuple[str, str]:
    """'SAN MARTÍN DE PORRES' -> ('san-martin-de-porres', 'San Martín de Porres')."""
    s = ALIAS.get(slug(nombre_fuente), slug(nombre_fuente))
    if s in CANON:
        return s, CANON[s]
    minus = {"de", "del", "la", "las", "los", "el", "y"}
    bonito = " ".join(w.lower() if i and w.lower() in minus else w.capitalize()
                      for i, w in enumerate(nombre_fuente.lower().split()))
    return s, bonito


def region_de(c: dict) -> str:
    return c.get("region") if c["empresa"] not in ("pluz", "luzdelsur") and c.get("region") else LIMA_REGION


def distrito_en(nombre_fuente: str, region: str) -> tuple[str, str]:
    """Lima: el distrito tal cual. Otra región: 'trujillo-la-libertad', para no chocar con Lima."""
    s, nombre = distrito(nombre_fuente)
    if region == LIMA_REGION:
        return s, nombre
    return f"{ALIAS_PROVINCIA.get(s, s)}-{REGIONES[region]['slug']}", nombre


def fecha_txt(iso: str, hoy: date) -> str:
    d = date.fromisoformat(iso)
    if d == hoy:
        return f"Hoy, {DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    if d == hoy + timedelta(days=1):
        return f"Mañana, {DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def fecha_abs(iso: str) -> str:
    """'Domingo 1 de noviembre' (sin 'hoy'/'mañana': para mensajes e imágenes que se ven después)."""
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def titulo_dia(iso: str, hoy: date) -> str:
    """Como lo busca la gente (y como titulan RPP o El Comercio): con 'hoy'/'mañana' y la fecha."""
    d = date.fromisoformat(iso)
    cuando = {hoy: "hoy ", hoy + timedelta(days=1): "mañana "}.get(d, "el ")
    return f"Corte de luz {cuando}{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} en Lima y Callao"


def zonas_txt(t: str) -> str:
    """Texto de la fuente en mayúsculas -> legible, sin inventar nada."""
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    abrev = {"CDRA": "cdra.", "CDRAS": "cdras.", "MZ": "Mz.", "LT": "Lt.", "JR": "Jr.", "AV": "Av.",
             "PSJE": "Psje.", "URB": "Urb.", "CALLE": "calle"}
    menores = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "CON", "EN"}

    def palabra(w: str, primera: bool) -> str:
        m = re.fullmatch(r"([A-ZÁÉÍÓÚÑÜ]+)\.?(,?)", w)
        if not m:
            return w  # números, códigos (SED1373), manzanas: tal cual
        base, coma = m.groups()
        if base in abrev:
            return abrev[base].capitalize() + coma if primera else abrev[base] + coma
        if base in menores and not primera:
            return base.lower() + coma
        return (base.capitalize() if len(base) > 2 else base) + coma
    return " ".join(palabra(w, i == 0) for i, w in enumerate(t.split()))


def construir(datos: dict, out: Path, base_url: str) -> dict:
    ahora = datetime.now(LIMA)
    hoy = ahora.date()
    base_url = base_url.rstrip("/")
    def fecha_larga(iso: str) -> str:
        """'el lunes 2 de noviembre': sin 'hoy'/'mañana', para mensajes que se reenvían y se leen después."""
        d = date.fromisoformat(iso)
        return f"el {DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"

    def preparar(c: dict) -> dict:
        region = region_de(c)
        ds = [distrito_en(d, region) for d in c["distritos"]]
        return {**c, "region": region, "ds": [{"slug": s, "nombre": n} for s, n in ds],
                "distritos_txt": " y ".join(n for _, n in ds),
                "fecha_txt": fecha_txt(c["fecha"], hoy), "fecha_larga": fecha_larga(c["fecha"]),
                "fecha_abs": fecha_abs(c["fecha"]),
                "zonas_txt": zonas_txt(c.get("zonas", "")),
                "empresa_txt": EMPRESAS[c["empresa"]]["nombre"]}

    def es_agua(c: dict) -> bool:
        return c.get("servicio") == "agua"

    def preparar_agua(c: dict) -> dict:
        ds = [distrito(d) for d in c["distritos"]]
        hasta = ""
        if c.get("fecha_fin"):
            f = date.fromisoformat(c["fecha_fin"])
            hasta = f" del {DIAS[f.weekday()]} {f.day}"
        return {**c, "region": LIMA_REGION, "ds": [{"slug": s, "nombre": n} for s, n in ds],
                "distritos_txt": " y ".join(n for _, n in ds),
                "fecha_txt": fecha_txt(c["fecha"], hoy), "fecha_abs": fecha_abs(c["fecha"]), "hasta_txt": hasta,
                "zonas_txt": zonas_txt(c.get("zonas", "")), "empresa_txt": SEDAPAL["nombre"]}

    # Agua (Sedapal) va en sus propias páginas (/agua/…): la luz sigue igual
    agua = [preparar_agua(c) for c in datos.get("cortes", []) if es_agua(c) and c["fecha"] >= hoy.isoformat()]
    agua_pasados = [preparar_agua(c) for c in datos.get("historial", []) if es_agua(c) and c["fecha"] < hoy.isoformat()]
    cortes = [preparar(c) for c in datos.get("cortes", []) if not es_agua(c) and c["fecha"] >= hoy.isoformat()]
    pasados = [preparar(c) for c in datos.get("historial", []) if not es_agua(c) and c["fecha"] < hoy.isoformat()]
    agua.sort(key=lambda c: (c["fecha"], c["inicio"], c["ds"][0]["nombre"]))
    agua_distrito = defaultdict(list)
    for c in agua:
        for d in c["ds"]:
            agua_distrito[d["slug"]].append(c)
    agua_historial = defaultdict(list)
    for c in sorted(agua_pasados, key=lambda c: (c["fecha"], c["inicio"]), reverse=True):
        for d in c["ds"]:
            agua_historial[d["slug"]].append(c)
    por_distrito = defaultdict(list)
    for c in cortes:
        for d in c["ds"]:
            por_distrito[d["slug"]].append(c)
    historial_distrito = defaultdict(list)
    for c in sorted(pasados, key=lambda c: (c["fecha"], c["inicio"]), reverse=True):
        for d in c["ds"]:
            historial_distrito[d["slug"]].append(c)
    nombres = dict(CANON)
    region_distrito = {s: LIMA_REGION for s in CANON}
    # también los distritos que solo están en el historial: su página no desaparece de un día para otro
    for c in cortes + pasados:
        for d in c["ds"]:
            nombres.setdefault(d["slug"], d["nombre"])
            region_distrito.setdefault(d["slug"], c["region"])
    cortes.sort(key=lambda c: (c["fecha"], c["inicio"], c["ds"][0]["nombre"]))
    # Portada, /manana/ y /dia/ son de Lima y Callao; cada región tiene su página
    por_dia = defaultdict(list)
    for c in cortes:
        if c["region"] == LIMA_REGION:
            por_dia[c["fecha"]].append(c)
    orden_region = [LIMA_REGION, *REGIONES]

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    css = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", (HERE / "static" / "estilos.css").read_text(encoding="utf-8"),
                                     flags=re.S))
    generado = datetime.fromisoformat(datos.get("generatedAt") or ahora.isoformat())
    env.globals.update(
        css=css, url=lambda p: p, abs=lambda p: base_url + p, empresas=EMPRESAS, contacto=CONTACTO, adsense=ADSENSE,
        hoy=hoy.isoformat(), anio=hoy.year,
        actualizado_txt=f"{generado.day} de {MESES[generado.month - 1]}, {generado:%H:%M}",
        distritos_menu=sorted(({"slug": s, "nombre": n, "n": len(por_distrito.get(s, [])), "region": region_distrito[s]}
                               for s, n in nombres.items()),
                              key=lambda d: (orden_region.index(d["region"]), sin_tildes(d["nombre"]))),
        regiones=[{"nombre": r, **v} for r, v in REGIONES.items()], lima_region=LIMA_REGION,
        fuentes=datos.get("sources", {}), sedapal=SEDAPAL,
        empresas_pagina=[{"k": k, "slug": v["slug"], "nombre": EMPRESAS[k]["nombre"]} for k, v in EMPRESAS_PAGINA.items()],
    )

    def resumen_agua(s: str) -> dict:
        """Recuadro "¿Y el agua?" de la página de luz del distrito."""
        lista = agua_distrito.get(s, [])
        return {"hoy": sum(1 for c in lista if c["fecha"] == hoy.isoformat()), "proximo": lista[0] if lista else None,
                "existe": s in CANON and s not in SIN_SEDAPAL or s in agua_distrito}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    paginas = []

    def escribir(path: str, plantilla: str, imagen: tuple | None = None, **ctx):
        """imagen = (título, dato, nota, hay_corte): vista previa propia para WhatsApp/Facebook en /og/."""
        if imagen:
            nombre = path.strip("/").replace("/", "-") or "portada"
            og.imagen(out / "og" / f"{nombre}.png", *imagen)
            ctx["og_imagen"] = f"/og/{nombre}.png"
        html = env.get_template(plantilla).render(path=path, canonical=base_url + path, **ctx)
        destino = out / path.strip("/") / "index.html" if path.endswith("/") else out / path.strip("/")
        if out.resolve() not in destino.resolve().parents:
            raise RuntimeError(f"ruta fuera del sitio: {path}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
        if ctx.get("indexable", True):
            paginas.append(path)

    dias = [{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": por_dia[f]} for f in sorted(por_dia)]
    hoy_n = len(por_dia.get(hoy.isoformat(), []))
    distritos_hoy = sorted({d["nombre"] for c in por_dia.get(hoy.isoformat(), []) for d in c["ds"]})

    def distritos_del_dia(fecha: date) -> list[dict]:
        vistos = {d["slug"]: d for c in por_dia.get(fecha.isoformat(), []) for d in c["ds"]}
        return sorted(vistos.values(), key=lambda d: sin_tildes(d["nombre"]))
    # la fecha en el título responde "¿para hoy?" en el resultado de Google (el build corre 00:05 Lima)
    hoy_txt = f"{hoy.day} de {MESES[hoy.month - 1]}"
    manana = distritos_del_dia(hoy + timedelta(days=1))
    manana_n = len(por_dia.get((hoy + timedelta(days=1)).isoformat(), []))
    escribir("/", "portada.html", indexable=True,
             # Sin fecha: Google no recrawlea la portada a diario y mostraba "hoy 30 de octubre" días después
             # (CTR 1.1 % -> 0.5 % tras ponerla, Search Console 6-nov). Los distritos sí la llevan y convierten bien.
             titulo="Cortes de luz programados hoy en Lima y Callao: horarios por distrito",
             descripcion=(f"Hoy hay {hoy_n} {'corte programado' if hoy_n == 1 else 'cortes programados'} de luz en Lima"
                          + (f": {', '.join(distritos_hoy[:4])}" if distritos_hoy else "")
                          + ". Horarios y calles por distrito, de Pluz y Luz del Sur." if hoy_n else
                          "Hoy no hay cortes de luz programados publicados en Lima y Callao."
                          + (f" Mañana hay {manana_n} en {', '.join(d['nombre'] for d in manana[:3])}." if manana_n else
                             " Revisa los próximos días por distrito.")
                          + " Horarios y calles, de Pluz y Luz del Sur."),
             dias=dias, hoy_n=hoy_n, total=len(cortes),
             agua_hoy=[c for c in agua if c["fecha"] == hoy.isoformat()],
             distritos_hoy=distritos_del_dia(hoy), distritos_manana=distritos_del_dia(hoy + timedelta(days=1)),
             otras=[{"nombre": r, **v, "n": sum(1 for c in cortes if c["region"] == r)} for r, v in REGIONES.items()],
             imagen=("Cortes de luz hoy en Lima y Callao",
                     f"{fecha_abs(hoy.isoformat())}: {hoy_n} {'corte' if hoy_n == 1 else 'cortes'}" if hoy_n else
                     f"{fecha_abs(hoy.isoformat())}: sin cortes programados",
                     "cortehoy.toca.pe · Horarios y calles por distrito", hoy_n > 0))

    # Regiones fuera de Lima: "Cortes de luz programados hoy 1 de noviembre en La Libertad (Trujillo)"
    for r, info in REGIONES.items():
        lista_r = [c for c in cortes if c["region"] == r]
        dias_r = defaultdict(list)
        for c in lista_r:
            dias_r[c["fecha"]].append(c)

        def distritos_r(fecha: date) -> list[dict]:
            vistos = {d["slug"]: d for c in dias_r.get(fecha.isoformat(), []) for d in c["ds"]}
            return sorted(vistos.values(), key=lambda d: sin_tildes(d["nombre"]))
        hoy_r = dias_r.get(hoy.isoformat(), [])
        nombres_hoy = [d["nombre"] for d in distritos_r(hoy)]
        desc = (f"Hoy hay {len(hoy_r)} {'corte programado' if len(hoy_r) == 1 else 'cortes programados'} de luz en {r}: "
                + ", ".join(nombres_hoy[:4]) + f". Horarios y sectores afectados, de {info['empresas']}." if hoy_r else
                f"Cortes de luz programados en {r} ({info['ciudades']}): {len(lista_r)} en los próximos días, con "
                f"horarios y sectores afectados, de {info['empresas']}." if lista_r else
                f"Hoy no hay cortes de luz programados publicados en {r}. Datos de {info['empresas']}, revisados cada 2 horas.")
        escribir(f"/region/{info['slug']}/", "region.html", indexable=True,
                 titulo=f"Cortes de luz programados hoy {hoy_txt} en {r} ({info['ciudades']})",
                 descripcion=desc[:160], region=r, info=info,
                 dias=[{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": dias_r[f]} for f in sorted(dias_r)],
                 hoy_n=len(hoy_r), distritos_hoy=distritos_r(hoy),
                 distritos_manana=distritos_r(hoy + timedelta(days=1)),
                 distritos_region=[d for d in env.globals["distritos_menu"] if d["region"] == r],
                 imagen=(f"Cortes de luz en {r}",
                         f"{fecha_abs(hoy.isoformat())}: {len(hoy_r)} {'corte' if len(hoy_r) == 1 else 'cortes'}" if hoy_r else
                         f"{len(lista_r)} en los próximos días" if lista_r else "Sin cortes programados",
                         f"cortehoy.toca.pe · {info['ciudades']} y alrededores", bool(hoy_r or lista_r)))

    # Páginas por fecha: /manana/ (URL fija que acumula posicionamiento para "corte de luz mañana") y
    # /dia/AAAA-MM-DD/ ("corte de luz 3 de noviembre"). Las fechas pasadas siguen DIAS del historial (noindex).
    por_dia_pasado = defaultdict(list)
    for c in sorted(pasados, key=lambda c: (c["inicio"], c["ds"][0]["nombre"])):
        if c["region"] == LIMA_REGION:
            por_dia_pasado[c["fecha"]].append(c)
    fechas = sorted(set(por_dia) | set(por_dia_pasado))

    def pagina_dia(path: str, f: str, indexable: bool, titulo_fijo: str = ""):
        lista = por_dia.get(f) or por_dia_pasado.get(f, [])
        dist = sorted({d["slug"]: d for c in lista for d in c["ds"]}.values(), key=lambda d: sin_tildes(d["nombre"]))
        nombres_d = [d["nombre"] for d in dist]
        i = fechas.index(f) if f in fechas else None
        titulo = titulo_dia(f, hoy)
        if not lista:
            desc = f"{titulo}: no hay cortes de luz programados publicados por Pluz ni Luz del Sur (por ahora)."
        else:
            desc = (f"{len(lista)} {'corte programado' if len(lista) == 1 else 'cortes programados'}: "
                    + ", ".join(nombres_d[:5]) + (" y más" if len(nombres_d) > 5 else "")
                    + ". Horarios y calles afectadas, de Pluz y Luz del Sur.")
        escribir(path, "dia.html", indexable=indexable,
                 titulo=titulo_fijo or titulo + (": distritos y horarios" if lista else ""),
                 descripcion=desc[:160], h1=titulo, fecha=f, fecha_txt=fecha_txt(f, hoy),
                 fecha_larga=fecha_larga(f), cortes=lista,
                 distritos=dist, pasado=f < hoy.isoformat(),
                 imagen=(f"Corte de luz {fecha_larga(f)} en Lima",
                         f"{len(lista)} {'corte' if len(lista) == 1 else 'cortes'} en {len(dist)} "
                         f"{'distrito' if len(dist) == 1 else 'distritos'}" if lista else "Sin cortes programados",
                         "cortehoy.toca.pe · Horarios y calles por distrito", bool(lista)),
                 anterior=fechas[i - 1] if i else None, siguiente=fechas[i + 1] if i is not None and i + 1 < len(fechas) else None)

    # /manana/ sin fecha en el título (Google no la recrawlea a diario) y como lo pregunta la gente:
    # "mañana habrá corte de luz", "habrá corte de luz mañana" (Search Console 6-nov)
    pagina_dia("/manana/", (hoy + timedelta(days=1)).isoformat(), True,
               "¿Habrá corte de luz mañana? Cortes programados en Lima y Callao")
    for f in fechas:
        pagina_dia(f"/dia/{f}/", f, f >= hoy.isoformat())
    for s, nombre in nombres.items():
        lista = por_distrito.get(s, [])
        recientes = historial_distrito.get(s, [])
        hoy_d = [c for c in lista if c["fecha"] == hoy.isoformat()]
        dias_d = [{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": [c for c in lista if c["fecha"] == f]}
                  for f in sorted({c["fecha"] for c in lista})]
        ultimo = f" Último corte: {recientes[0]['fecha_txt'].lower()}." if recientes else ""
        region = region_distrito[s]
        en_lima = region == LIMA_REGION
        empresas_r = "Pluz y Luz del Sur" if en_lima else REGIONES[region]["empresas"]
        lugar = nombre if en_lima else f"{nombre} ({region})"
        if hoy_d:
            # fecha completa, no "hoy": la vista previa queda pegada al mensaje y se lee después
            dato_img = (f"{hoy_d[0]['fecha_abs']} · {hoy_d[0]['inicio']} a {hoy_d[0]['fin']}"
                        + (f" (+{len(hoy_d) - 1})" if len(hoy_d) > 1 else ""))
        elif lista:
            dato_img = f"Próximo: {lista[0]['fecha_abs']} · {lista[0]['inicio']} a {lista[0]['fin']}"
        else:
            dato_img = "Sin cortes programados"
        if hoy_d:
            desc = (f"Hoy hay {len(hoy_d)} {'corte de luz programado' if len(hoy_d) == 1 else 'cortes de luz programados'} en {lugar}: "
                    + ", ".join(f"de {c['inicio']} a {c['fin']}" for c in hoy_d[:3]) + ". Calles afectadas y próximos cortes.")
        elif lista:
            desc = (f"Hoy no hay cortes de luz programados en {lugar}. Próximo corte: {dias_d[0]['fecha_txt'].lower()}, "
                    f"de {lista[0]['inicio']} a {lista[0]['fin']}. Calles afectadas.")
        else:
            desc = (f"No hay cortes de luz programados publicados para {lugar} en los próximos días.{ultimo} "
                    f"Datos de {empresas_r}, actualizados cada 2 horas.")
        escribir(f"/distrito/{s}/", "distrito.html", indexable=True,
                 titulo=f"Corte de luz hoy {hoy_txt} en {lugar}: horarios y calles", descripcion=desc[:160],
                 nombre=nombre, region=region, info_region=None if en_lima else REGIONES[region],
                 dias=dias_d, hoy_d=hoy_d, recientes=recientes[:MAX_HISTORIAL], n_recientes=len(recientes),
                 agua=resumen_agua(s) if en_lima else None, slug=s,
                 tab_agua=f"/agua/distrito/{s}/" if en_lima and resumen_agua(s)["existe"] else None,
                 imagen=(f"Corte de luz en {nombre}", dato_img,
                         "cortehoy.toca.pe · Horarios y calles" + ("" if en_lima else f" · {region}"), bool(hoy_d or lista)))

    # Agua (Sedapal): /agua/ y /agua/distrito/<slug>/, con la misma lógica que la luz
    agua_slugs = {s for s in CANON if s not in SIN_SEDAPAL} | set(agua_distrito) | set(agua_historial)
    nombres_agua = {s: CANON.get(s) or (agua_distrito.get(s) or agua_historial.get(s))[0]["ds"][0]["nombre"]
                    for s in agua_slugs}
    for c in agua + agua_pasados:  # el nombre bonito del distrito que trae el corte
        for d in c["ds"]:
            nombres_agua[d["slug"]] = CANON.get(d["slug"], d["nombre"])
    distritos_agua = sorted(({"slug": s, "nombre": n, "n": len(agua_distrito.get(s, []))} for s, n in nombres_agua.items()),
                            key=lambda d: sin_tildes(d["nombre"]))
    env.globals["distritos_agua"] = distritos_agua  # selector del encabezado en las páginas de agua
    agua_por_dia = defaultdict(list)
    for c in agua:
        agua_por_dia[c["fecha"]].append(c)
    agua_dias = [{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": agua_por_dia[f]} for f in sorted(agua_por_dia)]
    agua_hoy = agua_por_dia.get(hoy.isoformat(), [])

    def distritos_agua_dia(fecha: date) -> list[dict]:
        vistos = {d["slug"]: d for c in agua_por_dia.get(fecha.isoformat(), []) for d in c["ds"]}
        return sorted(vistos.values(), key=lambda d: sin_tildes(d["nombre"]))
    nombres_hoy_agua = [d["nombre"] for d in distritos_agua_dia(hoy)]
    n_imprev = sum(1 for c in agua_hoy if c["tipo"] == "imprevista")
    escribir("/agua/", "agua.html", indexable=True,
             titulo="Corte de agua hoy en Lima y Callao (Sedapal): distritos y horarios",
             descripcion=((f"Hoy hay {len(agua_hoy)} {'corte de agua' if len(agua_hoy) == 1 else 'cortes de agua'} de Sedapal: "
                           + ", ".join(nombres_hoy_agua[:4]) + (" y más" if len(nombres_hoy_agua) > 4 else "")
                           + ". Horarios y zonas afectadas por distrito.") if agua_hoy else
                          f"Hoy no hay cortes de agua de Sedapal registrados en Lima y Callao. {len(agua)} programados "
                          "en los próximos días, con horarios y zonas por distrito.")[:160],
             dias=agua_dias, hoy_n=len(agua_hoy), n_imprev=n_imprev, seccion="agua",
             distritos_hoy=distritos_agua_dia(hoy), distritos_manana=distritos_agua_dia(hoy + timedelta(days=1)),
             distritos_agua=distritos_agua,
             imagen=("Cortes de agua hoy en Lima y Callao",
                     f"{fecha_abs(hoy.isoformat())}: {len(agua_hoy)} {'corte' if len(agua_hoy) == 1 else 'cortes'}" if agua_hoy else
                     f"{fecha_abs(hoy.isoformat())}: sin cortes de agua",
                     "cortehoy.toca.pe/agua · Horarios y zonas por distrito", bool(agua_hoy)))
    for s, nombre in nombres_agua.items():
        lista = agua_distrito.get(s, [])
        recientes = agua_historial.get(s, [])
        hoy_d = [c for c in lista if c["fecha"] == hoy.isoformat()]
        dias_d = [{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": [c for c in lista if c["fecha"] == f]}
                  for f in sorted({c["fecha"] for c in lista})]
        if hoy_d:
            desc = (f"Hoy hay {len(hoy_d)} {'corte de agua' if len(hoy_d) == 1 else 'cortes de agua'} en {nombre}: "
                    + ", ".join(f"de {c['inicio']} a {c['fin']}" for c in hoy_d[:3]) + ". Zonas afectadas, de Sedapal.")
            dato_img = f"{hoy_d[0]['fecha_abs']} · {hoy_d[0]['inicio']} a {hoy_d[0]['fin']}" + (
                f" (+{len(hoy_d) - 1})" if len(hoy_d) > 1 else "")
        elif lista:
            desc = (f"Hoy no hay cortes de agua en {nombre}. Próximo: {dias_d[0]['fecha_txt'].lower()}, de "
                    f"{lista[0]['inicio']} a {lista[0]['fin']}. Zonas afectadas, de Sedapal.")
            dato_img = f"Próximo: {lista[0]['fecha_abs']} · {lista[0]['inicio']} a {lista[0]['fin']}"
        else:
            desc = (f"No hay cortes de agua de Sedapal registrados en {nombre} para hoy ni los próximos días. "
                    "Revisado cada 2 horas.")
            dato_img = "Sin cortes de agua"
        escribir(f"/agua/distrito/{s}/", "agua_distrito.html", indexable=True,
                 titulo=f"Corte de agua hoy {hoy_txt} en {nombre}: horarios y zonas", descripcion=desc[:160],
                 nombre=nombre, slug=s, luz=s in nombres, dias=dias_d, hoy_d=hoy_d, seccion="agua",
                 tab_luz=f"/distrito/{s}/" if s in nombres else None,
                 recientes=recientes[:MAX_HISTORIAL], n_recientes=len(recientes),
                 luz_hoy=sum(1 for c in por_distrito.get(s, []) if c["fecha"] == hoy.isoformat()),
                 imagen=(f"Corte de agua en {nombre}", dato_img, "cortehoy.toca.pe · Horarios y zonas", bool(hoy_d or lista)))
    # Una página por empresa: la gente busca "corte de luz pluz hoy", "corte de luz enel hoy", "edelnor corte
    # de luz", "luz del sur corte de luz hoy…" (46 búsquedas, 169 impresiones y 0 clics en Search Console, 6-nov)
    for k, info in EMPRESAS_PAGINA.items():
        e = EMPRESAS[k]
        lista_e = [c for c in cortes if c["empresa"] == k]
        dias_e = defaultdict(list)
        for c in lista_e:
            dias_e[c["fecha"]].append(c)

        def distritos_e(fecha: date) -> list[dict]:
            vistos = {d["slug"]: d for c in dias_e.get(fecha.isoformat(), []) for d in c["ds"]}
            return sorted(vistos.values(), key=lambda d: sin_tildes(d["nombre"]))
        hoy_e = dias_e.get(hoy.isoformat(), [])
        atendidos = sorted({d["slug"]: d for c in lista_e + [c for c in pasados if c["empresa"] == k]
                            for d in c["ds"]}.values(), key=lambda d: sin_tildes(d["nombre"]))
        nombres_e = [d["nombre"] for d in distritos_e(hoy)]
        desc = ((f"Hoy hay {len(hoy_e)} {'corte programado' if len(hoy_e) == 1 else 'cortes programados'} de "
                 f"{e['nombre']}: " + ", ".join(nombres_e[:4]) + (" y más" if len(nombres_e) > 4 else "") + ".")
                if hoy_e else f"Hoy no hay cortes programados de {e['nombre']}. "
                + (f"{len(lista_e)} en los próximos días." if lista_e else "Revisa los próximos días."))
        for extra in (f" Horarios y calles por distrito ({e['zona']}).", " Horarios y calles por distrito."):
            if len(desc + extra) <= 160:
                desc += extra
                break
        escribir(f"/{info['slug']}/", "empresa.html", indexable=True, titulo=info["titulo"], descripcion=desc[:160],
                 e=e, info=info, k=k, hoy_n=len(hoy_e), total=len(lista_e),
                 dias=[{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": dias_e[f]} for f in sorted(dias_e)],
                 distritos_hoy=distritos_e(hoy), distritos_manana=distritos_e(hoy + timedelta(days=1)),
                 atendidos=atendidos,
                 imagen=(f"Cortes de luz {e['nombre']}",
                         f"{fecha_abs(hoy.isoformat())}: {len(hoy_e)} {'corte' if len(hoy_e) == 1 else 'cortes'}" if hoy_e else
                         f"{len(lista_e)} en los próximos días" if lista_e else "Sin cortes programados",
                         f"cortehoy.toca.pe · {e['zona']}", bool(hoy_e or lista_e)))

    escribir("/acerca/", "acerca.html", indexable=True, titulo="Acerca de Corte Hoy",
             descripcion="De dónde salen los cortes programados de luz que publica Corte Hoy y cada cuánto se actualizan.")
    (out / "404.html").write_text(env.get_template("404.html").render(
        path="/404.html", canonical=base_url + "/404.html", titulo="Página no encontrada", descripcion=""),
        encoding="utf-8")
    for f in (HERE / "static").rglob("*"):
        if f.is_file() and f.name != "estilos.css":
            dest = out / f.relative_to(HERE / "static")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    hoy_iso = hoy.isoformat()
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{base_url}{p}</loc><lastmod>{hoy_iso}</lastmod></url>" for p in paginas)
        + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8")
    return {"cortes": len(cortes), "paginas": len(paginas), "hoy": hoy_n, "historial": len(pasados)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="public")
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    datos = json.loads(Path(args.data).read_text(encoding="utf-8"))
    r = construir(datos, Path(args.out), args.base_url)
    print(f"{r['cortes']} cortes desde hoy ({r['hoy']} hoy) · {r['historial']} en el historial · {r['paginas']} páginas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
