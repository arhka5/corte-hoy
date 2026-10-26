"""Pluz Energía (ex Enel distribución, Lima norte y Callao): cortes programados.

Pluz publica un PDF por semana ("Cortes programados - 19.10 al 25.10.pdf")
enlazado desde su página de ayuda. El PDF es texto: un encabezado por día,
luego "DISTRITO HH:MM – HH:MM" y debajo las calles y manzanas afectadas.
"""
from __future__ import annotations

import io
import re
from datetime import date
from urllib.parse import urljoin

import pdfplumber

from .client import Client

PAGINA = "https://www.pluz.pe/es/ayuda/enterate-de-los-cortes-de-luz-programados.html"
DIA = re.compile(r"^(LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+(\d{2})-(\d{2})-(\d{4})")
CABECERA = re.compile(r"^(.+?)\s+(\d{1,2}:\d{2})\s*[–\-]\s*(\d{1,2}:\d{2})\s*$")


def enlaces_pdf(html: str) -> list[str]:
    """PDFs de cortes enlazados en la página (normalmente la semana actual y la siguiente)."""
    hrefs = re.findall(r'href="([^"]+\.pdf)"', html, re.I)
    return list(dict.fromkeys(urljoin(PAGINA, h) for h in hrefs if "corte" in h.lower()))


def _hora(h: str) -> str:
    hh, mm = h.split(":")
    return f"{int(hh):02d}:{mm}"


def parse_pdf(contenido: bytes, url: str) -> list[dict]:
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        lineas = [l.strip() for p in pdf.pages for l in (p.extract_text() or "").splitlines() if l.strip()]
    cortes, fecha, actual = [], None, None
    for linea in lineas:
        m = DIA.match(linea)
        if m:
            fecha = date(int(m.group(4)), int(m.group(3)), int(m.group(2))).isoformat()
            actual = None
            continue
        m = CABECERA.match(linea)
        if m and fecha and not re.search(r"\d", m.group(1)):
            actual = {
                "empresa": "pluz",
                "fecha": fecha,
                "inicio": _hora(m.group(2)),
                "fin": _hora(m.group(3)),
                # "SAN MARTÍN DE PORRES / LOS OLIVOS": el corte toca los dos distritos
                "distritos": [d.strip() for d in m.group(1).split("/") if d.strip()],
                "zonas": "",
                "fuente": url,
            }
            cortes.append(actual)
        elif actual is not None:
            actual["zonas"] = f"{actual['zonas']} {linea}".strip()
    return cortes


def scrape(client: Client) -> list[dict]:
    pagina = client.request("GET", PAGINA).text
    pdfs = enlaces_pdf(pagina)
    if not pdfs:
        raise RuntimeError("No se encontraron PDFs de cortes en la página de Pluz (¿cambió el sitio?)")
    cortes = []
    for url in pdfs:
        cortes += parse_pdf(client.request("GET", url).content, url)
    return cortes
