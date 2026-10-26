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

HERE = Path(__file__).resolve().parent
LIMA = timezone(timedelta(hours=-5))
BASE_URL = "https://cortehoy.toca.pe"
REPO = "https://github.com/arhka5/corte-hoy"
ADSENSE = "ca-pub-6522291453297769"  # anuncios automáticos de AdSense (cuenta del dominio toca.pe)

EMPRESAS = {
    "pluz": {"nombre": "Pluz Energía", "zona": "Lima norte, Lima centro y Callao",
             "url": "https://www.pluz.pe/es/ayuda/enterate-de-los-cortes-de-luz-programados.html"},
    "luzdelsur": {"nombre": "Luz del Sur", "zona": "Lima sur y este",
                  "url": "https://www.luzdelsur.pe/es/corteluz"},
}

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
ALIAS = {"cercado-de-lima": "lima-cercado", "lima": "lima-cercado", "surco": "santiago-de-surco",
         "magdalena": "magdalena-del-mar", "sjl": "san-juan-de-lurigancho", "smp": "san-martin-de-porres"}


def distrito(nombre_fuente: str) -> tuple[str, str]:
    """'SAN MARTÍN DE PORRES' -> ('san-martin-de-porres', 'San Martín de Porres')."""
    s = ALIAS.get(slug(nombre_fuente), slug(nombre_fuente))
    if s in CANON:
        return s, CANON[s]
    minus = {"de", "del", "la", "las", "los", "el", "y"}
    bonito = " ".join(w.lower() if i and w.lower() in minus else w.capitalize()
                      for i, w in enumerate(nombre_fuente.lower().split()))
    return s, bonito


def fecha_txt(iso: str, hoy: date) -> str:
    d = date.fromisoformat(iso)
    if d == hoy:
        return f"Hoy, {DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    if d == hoy + timedelta(days=1):
        return f"Mañana, {DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


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
    cortes = []
    for c in datos.get("cortes", []):
        if c["fecha"] < hoy.isoformat():
            continue
        ds = [distrito(d) for d in c["distritos"]]
        cortes.append({**c, "ds": [{"slug": s, "nombre": n} for s, n in ds],
                       "distritos_txt": " y ".join(n for _, n in ds),
                       "fecha_txt": fecha_txt(c["fecha"], hoy), "zonas_txt": zonas_txt(c.get("zonas", "")),
                       "empresa_txt": EMPRESAS[c["empresa"]]["nombre"]})
    por_distrito = defaultdict(list)
    for c in cortes:
        for d in c["ds"]:
            por_distrito[d["slug"]].append(c)
    nombres = dict(CANON)
    for c in cortes:
        for d in c["ds"]:
            nombres.setdefault(d["slug"], d["nombre"])
    cortes.sort(key=lambda c: (c["fecha"], c["inicio"], c["ds"][0]["nombre"]))
    por_dia = defaultdict(list)
    for c in cortes:
        por_dia[c["fecha"]].append(c)

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    css = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", (HERE / "static" / "estilos.css").read_text(encoding="utf-8"),
                                     flags=re.S))
    generado = datetime.fromisoformat(datos.get("generatedAt") or ahora.isoformat())
    env.globals.update(
        css=css, url=lambda p: p, abs=lambda p: base_url + p, empresas=EMPRESAS, repo=REPO, adsense=ADSENSE,
        hoy=hoy.isoformat(), anio=hoy.year,
        actualizado_txt=f"{generado.day} de {MESES[generado.month - 1]}, {generado:%H:%M}",
        distritos_menu=sorted(({"slug": s, "nombre": n, "n": len(por_distrito.get(s, []))}
                               for s, n in nombres.items()), key=lambda d: sin_tildes(d["nombre"])),
        fuentes=datos.get("sources", {}),
    )
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    paginas = []

    def escribir(path: str, plantilla: str, **ctx):
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
    escribir("/", "portada.html", indexable=True,
             titulo=f"Corte de luz hoy en Lima y Callao: cortes programados {hoy.year}",
             descripcion=(f"Hoy hay {hoy_n} {'corte programado' if hoy_n == 1 else 'cortes programados'} de luz en Lima"
                          + (f": {', '.join(distritos_hoy[:4])}" if distritos_hoy else "")
                          + ". Horarios y calles por distrito, de Pluz y Luz del Sur." if hoy_n else
                          "Hoy no hay cortes de luz programados publicados en Lima y Callao. Revisa los próximos días "
                          "por distrito, con horarios y calles, de Pluz y Luz del Sur."),
             dias=dias, hoy_n=hoy_n, total=len(cortes))
    for s, nombre in nombres.items():
        lista = por_distrito.get(s, [])
        hoy_d = [c for c in lista if c["fecha"] == hoy.isoformat()]
        dias_d = [{"fecha": f, "fecha_txt": fecha_txt(f, hoy), "cortes": [c for c in lista if c["fecha"] == f]}
                  for f in sorted({c["fecha"] for c in lista})]
        if hoy_d:
            desc = (f"Hoy hay {len(hoy_d)} {'corte' if len(hoy_d) == 1 else 'cortes'} de luz programados en {nombre}: "
                    + ", ".join(f"de {c['inicio']} a {c['fin']}" for c in hoy_d[:3]) + ". Calles afectadas y próximos cortes.")
        elif lista:
            desc = (f"Hoy no hay cortes de luz programados en {nombre}. Próximo corte: {dias_d[0]['fecha_txt'].lower()}, "
                    f"de {lista[0]['inicio']} a {lista[0]['fin']}. Calles afectadas.")
        else:
            desc = (f"No hay cortes de luz programados publicados para {nombre} en los próximos días. "
                    "Datos de Pluz y Luz del Sur, actualizados cada 6 horas.")
        escribir(f"/distrito/{s}/", "distrito.html", indexable=True,
                 titulo=f"Corte de luz hoy en {nombre}: horarios y calles", descripcion=desc[:160],
                 nombre=nombre, dias=dias_d, hoy_d=hoy_d)
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
    return {"cortes": len(cortes), "paginas": len(paginas), "hoy": hoy_n}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="public")
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    datos = json.loads(Path(args.data).read_text(encoding="utf-8"))
    r = construir(datos, Path(args.out), args.base_url)
    print(f"{r['cortes']} cortes desde hoy ({r['hoy']} hoy) · {r['paginas']} páginas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
