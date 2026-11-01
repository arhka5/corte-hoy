"""Imagen de vista previa (og:image, 1200x630) para cada página: es lo que se ve en WhatsApp y Facebook
cuando alguien comparte el enlace, así que dice dónde, cuándo y a qué hora, no un logo genérico.
Usa las mismas fuentes del sitio (Pillow lee WOFF2)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FUENTES = Path(__file__).resolve().parent / "static" / "fonts"
W, H, MARGEN = 1200, 630, 70
NOCHE, AMBAR, BLANCO, SUAVE, VERDE = "#14213d", "#ffb703", "#ffffff", "#aab4c8", "#7ee2b0"


def _fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / f"{nombre}.woff2"), tam)


def _envolver(d: ImageDraw.ImageDraw, texto: str, fuente, ancho: int) -> list[str]:
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if d.textlength(prueba, font=fuente) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + [actual]


def imagen(destino: Path, titulo: str, dato: str, nota: str, hay: bool) -> None:
    """titulo: 'Corte de luz en Lurigancho'; dato: 'Hoy domingo 1 de noviembre · 06:30 a 17:15'
    (el recuadro, ámbar si hay corte, verde si no); nota: línea final pequeña."""
    img = Image.new("RGB", (W, H), NOCHE)
    d = ImageDraw.Draw(img)
    # franja de peligro arriba, como la cabecera del sitio
    for x in range(-40, W, 56):
        d.polygon([(x, 0), (x + 28, 0), (x + 10, 14), (x - 18, 14)], fill=AMBAR)
    # rayo + marca
    d.polygon([(MARGEN + 20, 52), (MARGEN, 92), (MARGEN + 16, 92), (MARGEN + 8, 122), (MARGEN + 34, 80),
               (MARGEN + 18, 80), (MARGEN + 26, 52)], fill=AMBAR)
    d.text((MARGEN + 52, 64), "CORTE", font=_fuente("barlow-800", 44), fill=BLANCO)
    d.text((MARGEN + 52 + d.textlength("CORTE ", font=_fuente("barlow-800", 44)), 64), "HOY",
           font=_fuente("barlow-800", 44), fill=AMBAR)
    # título grande en 1-3 líneas, achicando si no entra
    for tam in (92, 80, 70, 60):
        f_tit = _fuente("barlow-800", tam)
        lineas = _envolver(d, titulo.upper(), f_tit, W - 2 * MARGEN)
        if len(lineas) <= 3:
            break
    y = 150
    for ln in lineas[:3]:
        d.text((MARGEN, y), ln, font=f_tit, fill=BLANCO)
        y += int(tam * 1.02)
    # recuadro con el dato
    f_dato = _fuente("barlow-800", 46)
    dato = dato.upper()
    while d.textlength(dato, font=f_dato) > W - 2 * MARGEN - 60 and f_dato.size > 30:
        f_dato = _fuente("barlow-800", f_dato.size - 2)
    y = max(y + 22, 400)
    alto = f_dato.size + 34
    d.rounded_rectangle((MARGEN, y, MARGEN + d.textlength(dato, font=f_dato) + 52, y + alto), 14, fill="#0d1730")
    d.rectangle((MARGEN, y, MARGEN + 10, y + alto), fill=AMBAR if hay else VERDE)
    d.text((MARGEN + 32, y + 14), dato, font=f_dato, fill=AMBAR if hay else VERDE)
    d.text((MARGEN, H - 70), nota, font=_fuente("atkinson-700", 30), fill=SUAVE)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, optimize=True)
