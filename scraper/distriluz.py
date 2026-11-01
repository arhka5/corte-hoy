"""Hidrandina (Grupo Distriluz): cortes programados en La Libertad, Áncash y Cajamarca.

Su página de cortes es HTML de servidor (sin captcha), con una pestaña por región
(#pills-lib, #pills-anc, #pills-caj) y tablas "Fecha y Hora | Distrito | Sectores
involucrados" escritas a mano en un editor: el formato varía entre filas.
    - fechas "Viernes 30.10.2026" o "Viernes 30/10/2026"
    - horas "09.00 a.m.  a  12:00 p.m", "9:00 a.m. a 12:00 m." (m. = mediodía)
    - la celda de fecha puede abarcar varias filas (rowspan) y hay tablas dentro de tablas
Se usa el parser de la biblioteca estándar para no sumar dependencias.
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

from .client import Client

URL = "https://aplicaciones.distriluz.com.pe/Apps/Visits/Home/CortesProgramados"
REGIONES = {"pills-lib": "La Libertad", "pills-anc": "Áncash", "pills-caj": "Cajamarca"}
FECHA = re.compile(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})")
# "09.00 a.m.", "12:00 m." (mediodía), "3:00 p.m", "17:00"
HORA = re.compile(r"(\d{1,2})\s*[.:]\s*(\d{2})\s*(?:([ap])\.?\s*m\b\.?|(m)\b\.?)?", re.I)
# La columna "Distrito" a veces trae "provincia/distrito" ("Huaraz/Pira"), otras "distrito/provincia"
# ("Jesús/Cajamarca") o mezclado ("Chimbote/Santa"): se descarta la parte que es una provincia.
PROVINCIAS = {
    "La Libertad": ["Trujillo", "Ascope", "Bolívar", "Chepén", "Julcán", "Otuzco", "Pacasmayo", "Pataz",
                    "Sánchez Carrión", "Santiago de Chuco", "Gran Chimú", "Virú"],
    "Áncash": ["Huaraz", "Aija", "Antonio Raymondi", "Antonio Raimondi", "Asunción", "Bolognesi", "Carhuaz",
               "Carlos Fermín Fitzcarrald", "Casma", "Corongo", "Huari", "Huarmey", "Huaylas", "Mariscal Luzuriaga",
               "Ocros", "Pallasca", "Pomabamba", "Recuay", "Santa", "Sihuas", "Yungay"],
    "Cajamarca": ["Cajamarca", "Cajabamba", "Celendín", "Chota", "Contumazá", "Cutervo", "Hualgayoc", "Jaén",
                  "San Ignacio", "San Marcos", "San Miguel", "San Pablo", "Santa Cruz"],
}


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").strip()


def distritos_de(celda: str, region: str) -> list[str]:
    provincias = {_norm(p) for p in PROVINCIAS.get(region, [])}
    nombres = []
    for linea in celda.split("\n"):
        partes = [p.strip() for p in linea.split("/") if p.strip()]
        distritos = [p for p in partes if _norm(p) not in provincias] or partes
        for d in distritos:
            nombres += [n.strip() for n in d.split(",") if n.strip()]
    return list(dict.fromkeys(nombres))


class _Filas(HTMLParser):
    """Aplana las tablas de cada pestaña en filas de celdas de texto (con rowspan resuelto)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.filas: list[tuple[str, list[str]]] = []  # (región, celdas)
        self.region = None
        self.celdas_pila: list[list[list]] = []  # por nivel de tabla: celdas de la fila en curso
        self.texto_pila: list[list[str] | None] = []  # celda abierta por nivel
        self.arrastre: dict[int, list] = {}  # rowspan: columna -> [texto, filas que faltan]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and a.get("id") in REGIONES:
            self.region = REGIONES[a["id"]]
            self.arrastre = {}
        elif tag == "table":
            self.celdas_pila.append([])
            self.texto_pila.append(None)
        elif tag == "tr" and self.celdas_pila:
            self.celdas_pila[-1] = []
        elif tag in ("td", "th") and self.celdas_pila:
            self.texto_pila[-1] = []
            self.celdas_pila[-1].append([self.texto_pila[-1], int(a.get("rowspan") or 1), tag])
        elif tag in ("br", "p", "li") and self.texto_pila and self.texto_pila[-1] is not None:
            self.texto_pila[-1].append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.texto_pila:
            self.texto_pila[-1] = None
        elif tag == "tr" and self.celdas_pila and self.region:
            self._cerrar_fila(self.celdas_pila[-1])
            self.celdas_pila[-1] = []
        elif tag == "table" and self.celdas_pila:
            self.celdas_pila.pop()
            self.texto_pila.pop()

    def handle_data(self, data):
        if self.texto_pila and self.texto_pila[-1] is not None:
            self.texto_pila[-1].append(data)

    def _cerrar_fila(self, celdas: list):
        if not celdas or any(c[2] == "th" for c in celdas):
            return
        textos = [limpiar("".join(c[0])) for c in celdas]
        fila, i = [], 0
        for col in range(len(textos) + len(self.arrastre)):
            if col in self.arrastre:
                texto, faltan = self.arrastre[col]
                fila.append(texto)
                if faltan <= 1:
                    del self.arrastre[col]
                else:
                    self.arrastre[col][1] = faltan - 1
            elif i < len(textos):
                if celdas[i][1] > 1:
                    self.arrastre[col] = [textos[i], celdas[i][1] - 1]
                fila.append(textos[i])
                i += 1
        self.filas.append((self.region, fila))


def limpiar(t: str) -> str:
    t = t.replace("\xa0", " ")
    lineas = [re.sub(r"[ \t]+", " ", x).strip() for x in t.split("\n")]
    return "\n".join(x for x in lineas if x)


def _hora(m: re.Match) -> str:
    h, minutos = int(m.group(1)), m.group(2)
    ampm = (m.group(3) or "").lower()
    if ampm == "p" and h < 12:
        h += 12
    elif ampm == "a" and h == 12:
        h = 0
    return f"{h:02d}:{minutos}" if 0 <= h < 24 and int(minutos) < 60 else ""


def fila_a_corte(region: str, fila: list[str]) -> dict | None:
    if len(fila) < 3:
        return None
    fecha_hora, distritos, sectores = fila[0], fila[1], "\n".join(fila[2:])
    f = FECHA.search(fecha_hora)
    if not f or not distritos.strip():
        return None
    resto = fecha_hora[f.end():]
    horas = [h for h in (_hora(m) for m in HORA.finditer(resto)) if h]
    return {
        "empresa": "hidrandina",
        "region": region,
        "fecha": f"{f.group(3)}-{int(f.group(2)):02d}-{int(f.group(1)):02d}",
        "inicio": horas[0] if horas else "",
        "fin": horas[1] if len(horas) > 1 else "",
        "distritos": distritos_de(distritos, region),
        "zonas": re.sub(r"\s*\n\s*", " ", sectores).strip(),
        "fuente": URL,
    }


def parse(html: str) -> list[dict]:
    p = _Filas()
    p.feed(html)
    return [c for c in (fila_a_corte(r, f) for r, f in p.filas) if c]


def scrape(client: Client) -> list[dict]:
    return parse(client.request("GET", URL).text)
