"""Descarga los cortes programados y escribe cortes.json.

    python -m scraper --previous anterior.json --output out/cortes.json

Si una empresa falla, se conservan sus cortes de la corrida anterior (los que
aún no pasaron) para que la web no se quede vacía.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import luzdelsur, pluz
from .client import Client

LIMA = timezone(timedelta(hours=-5))
FUENTES = {"pluz": pluz.scrape, "luzdelsur": luzdelsur.scrape}


def corte_id(c: dict) -> str:
    raw = "|".join([c["empresa"], c["fecha"], c["inicio"], c["fin"], "/".join(c["distritos"]), c["zonas"][:200]])
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous")
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    previo = {}
    if args.previous and Path(args.previous).exists():
        try:
            previo = json.loads(Path(args.previous).read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            previo = {}
    ahora = datetime.now(LIMA)
    hoy = ahora.date().isoformat()
    client = Client()
    cortes, estado = [], {}
    for nombre, scrape in FUENTES.items():
        try:
            nuevos = scrape(client)
            estado[nombre] = {"ok": True, "cortes": len(nuevos), "updatedAt": ahora.isoformat(timespec="seconds")}
        except Exception as exc:  # una empresa caída no detiene a la otra
            traceback.print_exc()
            nuevos = [c for c in previo.get("cortes", []) if c["empresa"] == nombre]
            anterior = (previo.get("sources") or {}).get(nombre, {})
            estado[nombre] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                              "cortes": len(nuevos), "updatedAt": anterior.get("updatedAt")}
        cortes += nuevos

    unicos = {}
    for c in cortes:
        if not c.get("fecha") or c["fecha"] < hoy:
            continue
        c["id"] = corte_id(c)
        unicos[c["id"]] = c
    lista = sorted(unicos.values(), key=lambda c: (c["fecha"], c["inicio"], c["distritos"][0]))
    datos = {"generatedAt": ahora.isoformat(timespec="seconds"), "timezone": "America/Lima",
             "sources": estado, "cortes": lista}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(" · ".join(f"{k}: {'ok' if v['ok'] else 'ERROR'} ({v['cortes']})" for k, v in estado.items())
          + f" · {len(lista)} cortes desde hoy · {client.requests} peticiones")
    return 0 if any(v["ok"] for v in estado.values()) or lista else 1


if __name__ == "__main__":
    sys.exit(main())
