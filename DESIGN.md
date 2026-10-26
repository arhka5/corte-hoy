# DESIGN.md: Corte Hoy

Concepto: **aviso de corte**. La pregunta que se responde es "¿me cortan la luz
hoy, a qué hora y en qué calles?", así que la hora va primero y grande.

## Paleta (`site/static/estilos.css`)
| Variable | Valor | Uso |
|---|---|---|
| `--noche` | `#14213d` | Cabecera, títulos, horas |
| `--ambar` | `#ffb703` | **Único acento** (rayo, borde de cada corte, "hoy hay cortes"), siempre con texto oscuro |
| `--papel` | `#f4f5f7` | Fondo frío. Nunca crema |

Prohibido: crema con terracota, degradados decorativos, etiquetas pequeñas en mayúsculas,
emojis, texto inventado sobre los cortes.

## Tipografía (servida desde `site/static/fonts`, OFL)
Barlow Semi Condensed (rótulos, horas, números) y Atkinson Hyperlegible (texto).

## Pieza firma
Cada corte tiene una **barra de 24 h** con la franja rayada en ámbar y una marca
de "ahora". Un script en `base.html` (hora de Lima) pone el estado: "En curso ·
vuelve en…", "Empieza en…" o "Terminó" (atenuado y al final), y el tablero del
inicio dice cuántos están en curso.

## Reglas
- Hora en números tabulares, grande. Distrito como enlace a su página.
- Calles tal como las publica la empresa (solo se pasan de MAYÚSCULAS a legible);
  si pasan de 280 caracteres, se pliegan con "Ver todas las calles".
- Áreas táctiles de 44 px. Las franjas rayadas son las únicas texturas (aviso de obra).
- Cada distrito tiene página siempre, también para decir "no hay cortes".

## Revisar cambios
`ChambaAlToque/herramientas/mirar.py http://127.0.0.1:8797 / /distrito/rimac/`
con un `cortes.json` de prueba (ver `out/prueba.json`).
