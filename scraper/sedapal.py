"""Sedapal (agua, Lima y Callao): interrupciones del servicio de agua.

Sedapal enlaza desde su portada un mapa público "Consulta de interrupciones" (ArcGIS).
Su capa 1 (Incidencias) del MapServer HEC/SGIO_TOTAL lista las interrupciones activas:
las programadas de los próximos días (limpieza de reservorios, empalmes) y las
imprevistas que registra en el momento (roturas, fugas). Cada una trae distrito,
zonas afectadas (urbanizaciones, A.H., sectores), inicio y fin estimado:
    {"INCIDENCIA": "764474", "TIPO_INCID": "PROGRAMADA", "FEC_DETECCION": "10/11/2026 08:00:00",
     "FEC_ESTIMADA": "10/11/2026 20:00:00", "CAUSA": "LIMPIEZA DE RESERVORIO",
     "MUNICIPALIDAD": "VILLA MARIA DEL TRIUNFO", "AREAS_AFECTADAS": "URBANIZACION-A.H INCA ...; ..."}
No se usa INFOR_WEB (descripción libre): trae nombres del personal de Sedapal.
El servidor manda algunas letras con tilde como "¿" (DESINFECCI¿N): se reparan las conocidas.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .client import Client

SERVICIO = "https://gisprdsdp.sedapal.com.pe/arcgis/rest/services/HEC/SGIO_TOTAL/MapServer/1/query"
PAGINA = "https://sedapal.maps.arcgis.com/apps/webappviewer/index.html?id=32603d5182d846f69bd4cb6703d66e88"
CAMPOS = "INCIDENCIA,TIPO_INCID,FEC_DETECCION,FEC_ESTIMADA,CAUSA,MUNICIPALIDAD,AREAS_AFECTADAS,AGUA"
LIMA = timezone(timedelta(hours=-5))

REPARAR = [(r"CI¿N\b", "CIÓN"), (r"ER¿A", "ERÍA"), (r"SE¿OR", "SEÑOR"), (r"COMIT¿", "COMITÉ"),
           (r"V¿LVULA", "VÁLVULA"), (r"L¿NEA", "LÍNEA"), (r"(?<=[A-Z])¿(?=[A-Z])", "Ñ"), (r"¿", "")]
# Lo que va antes del nombre: "A.H FLOR, LA" -> "A.H LA FLOR"
TIPOS = re.compile(r"^((?:A\.?\s?H\.?|P\.?\s?J\.?|URB\.?|ASOC\.?|COOP\.?|AA\.?HH\.?|PP\.?JJ\.?|CONJ\.?|RES\.?|"
                   r"UPIS|AGR\.?|PROG\.?|COMITE|COMITÉ|SECTOR|APV|C\.?\s?R\.?)\s+)?(.*)$")


def reparar(t: str) -> str:
    for patron, cambio in REPARAR:
        t = re.sub(patron, cambio, t)
    return t


def _fecha_hora(t: str) -> tuple[str, str]:
    """'06/11/2026 07:13:20' -> ('2026-11-06', '07:13')."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})", t or "")
    if not m:
        return "", ""
    d, mes, a, h, mi = m.groups()
    return f"{a}-{int(mes):02d}-{int(d):02d}", f"{int(h):02d}:{mi}"


def _zona(item: str) -> str:
    """'URBANIZACION-P.J FLOR, LA' -> 'P.J LA FLOR'; 'SECTOR-305' -> 'SECTOR 305'."""
    item = re.sub(r"^URBANIZACION-", "", item.strip())
    item = re.sub(r"^SECTOR-", "SECTOR ", item)
    # Nombres al revés, como en un padrón: "A.H CALLER, LAURA" -> "A.H LAURA CALLER", "MAYO, 19 DE" -> "19 DE MAYO"
    m = re.match(r"^([^,]+),\s*([^,]+)$", item)
    if m and len(m.group(2).split()) <= 4:
        tipo, nombre = TIPOS.match(m.group(1)).groups()
        item = f"{tipo or ''}{m.group(2)} {nombre}"
    return re.sub(r"\s+", " ", item).strip()


def zonas(texto: str) -> str:
    vistas = []
    for z in reparar(texto or "").split(";"):
        z = _zona(z)
        if z and z not in vistas:
            vistas.append(z)
    return "; ".join(vistas)


def parse(datos: dict, hoy: str) -> list[dict]:
    """Interrupciones de agua vigentes desde `hoy` (AAAA-MM-DD, Lima)."""
    cortes = []
    for f in datos.get("features") or []:
        a = f.get("attributes") or {}
        if not a.get("AGUA"):
            continue  # solo desagüe: no corta el agua
        f_ini, h_ini = _fecha_hora(a.get("FEC_DETECCION"))
        f_fin, h_fin = _fecha_hora(a.get("FEC_ESTIMADA"))
        if not f_ini or (f_fin and f_fin < hoy):
            continue
        fecha, nota = f_ini, ""
        if f_ini < hoy:  # empezó antes y sigue: se muestra hoy, diciendo desde cuándo
            d = datetime.strptime(f_ini, "%Y-%m-%d")
            fecha, nota = hoy, f"Empezó el {d.day}/{d.month} a las {h_ini}."
        distritos = [reparar(x).strip() for x in (a.get("MUNICIPALIDAD") or "").split(";") if x.strip()]
        if not distritos:
            continue
        cortes.append({
            "empresa": "sedapal",
            "servicio": "agua",
            "ref": str(a.get("INCIDENCIA") or ""),
            "tipo": "imprevista" if (a.get("TIPO_INCID") or "").upper().startswith("IMPREV") else "programada",
            "causa": reparar(a.get("CAUSA") or "").strip().capitalize(),
            "fecha": fecha,
            "inicio": h_ini,
            "fin": h_fin,
            "fecha_fin": f_fin if f_fin and f_fin > fecha else "",
            "nota": nota,
            "distritos": distritos,
            "zonas": zonas(a.get("AREAS_AFECTADAS") or ""),
            "fuente": PAGINA,
        })
    return cortes


def scrape(client: Client) -> list[dict]:
    r = client.request("GET", SERVICIO, params={"where": "1=1", "outFields": CAMPOS, "returnGeometry": "false",
                                                "f": "json"})
    datos = r.json()
    if "error" in datos or "features" not in datos:
        raise RuntimeError(f"Sedapal respondió sin datos: {str(datos)[:200]}")
    return parse(datos, datetime.now(LIMA).date().isoformat())
