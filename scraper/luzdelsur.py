"""Luz del Sur (Lima sur y este): lista de cortes programados por distrito.

Su página "Conocer qué ocurre con mi servicio" llena la lista con un POST a
CorteLuz/ObtenerCortesDistrito, que responde JSON sin pedir token. Cuando no
hay cortes devuelve {"listado": []}. No conocemos aún el formato de un ítem
con datos, así que se leen los campos de forma tolerante y se guarda el
original para revisarlo.
"""
from __future__ import annotations

import re

from .client import Client

PAGINA = "https://www.luzdelsur.pe/es/corteluz"
ENDPOINT = "https://www.luzdelsur.pe/es/CorteLuz/ObtenerCortesDistrito"


def _campo(item: dict, *claves: str) -> str:
    for k, v in item.items():
        if any(c in k.lower() for c in claves) and isinstance(v, (str, int)):
            return str(v).strip()
    return ""


def _fecha(texto: str) -> str:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def _hora(texto: str) -> str:
    m = re.search(r"(\d{1,2}):(\d{2})", texto)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""


def parse(datos: dict) -> list[dict]:
    listado = (datos.get("datos") or {}).get("listado") or []
    cortes = []
    for item in listado:
        if isinstance(item, str):
            item = {"distrito": item}
        distrito = _campo(item, "distrito", "nombre", "descripcion")
        if not distrito:
            continue
        cortes.append({
            "empresa": "luzdelsur",
            "fecha": _fecha(_campo(item, "fecha", "dia")),
            "inicio": _hora(_campo(item, "inicio", "desde", "horaini")),
            "fin": _hora(_campo(item, "fin", "hasta", "horafin")),
            "distritos": [distrito],
            "zonas": _campo(item, "zona", "sector", "direccion", "detalle"),
            "fuente": PAGINA,
            "original": item,
        })
    return cortes


def scrape(client: Client) -> list[dict]:
    r = client.request("POST", ENDPOINT, headers={"X-Requested-With": "XMLHttpRequest",
                                                   "Content-Type": "application/json; charset=utf-8"})
    datos = r.json()
    if not datos.get("success"):
        raise RuntimeError(f"Luz del Sur respondió sin éxito: {str(datos)[:200]}")
    return parse(datos)
