"""Luz del Sur (Lima sur y este): lista de cortes programados por distrito.

Su página "Conocer qué ocurre con mi servicio" llena la lista con un POST a
CorteLuz/ObtenerCortesDistrito, que responde JSON sin pedir token. Solo trae
los cortes de HOY, por distrito y sin calles:
    {"listado": [{"distrito": "LURIGANCHO-CHOSICA", "horario": "06:30 AM a 05:15 PM"}]}
Cuando no hay cortes devuelve {"listado": []}. Los campos se leen de forma
tolerante (por si cambian de nombre) y se guarda el original.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .client import Client

PAGINA = "https://www.luzdelsur.pe/es/corteluz"
ENDPOINT = "https://www.luzdelsur.pe/es/CorteLuz/ObtenerCortesDistrito"
LIMA = timezone(timedelta(hours=-5))


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


# la "M" es obligatoria: en "12:00 a 13:00" la "a" no es "AM"
HORA = r"(\d{1,2}):(\d{2})(?:\s*([AaPp])\.?\s*[Mm]\.?)?"


def _hora(texto: str) -> str:
    """'9:00' -> '09:00'; '05:15 PM' -> '17:15'; '12:00 AM' -> '00:00'."""
    m = re.search(HORA, texto)
    if not m:
        return ""
    h, minutos, ampm = int(m.group(1)), m.group(2), (m.group(3) or "").lower()
    if ampm == "p" and h < 12:
        h += 12
    elif ampm == "a" and h == 12:
        h = 0
    return f"{h:02d}:{minutos}"


def _horario(texto: str) -> tuple[str, str]:
    """'06:30 AM a 05:15 PM' -> ('06:30', '17:15')."""
    horas = [m.group(0) for m in re.finditer(HORA, texto)]
    return (_hora(horas[0]) if horas else "", _hora(horas[1]) if len(horas) > 1 else "")


def parse(datos: dict, hoy: str) -> list[dict]:
    """`hoy` (AAAA-MM-DD, Lima) es la fecha cuando el ítem no trae una: la lista es la de hoy."""
    listado = (datos.get("datos") or {}).get("listado") or []
    cortes = []
    for item in listado:
        if isinstance(item, str):
            item = {"distrito": item}
        distrito = _campo(item, "distrito", "nombre", "descripcion")
        if not distrito:
            continue
        inicio = _hora(_campo(item, "inicio", "desde", "horaini"))
        fin = _hora(_campo(item, "fin", "hasta", "horafin"))
        if not inicio and not fin:
            inicio, fin = _horario(_campo(item, "horario", "hora"))
        cortes.append({
            "empresa": "luzdelsur",
            "fecha": _fecha(_campo(item, "fecha", "dia")) or hoy,
            "inicio": inicio,
            "fin": fin,
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
    return parse(datos, datetime.now(LIMA).date().isoformat())
