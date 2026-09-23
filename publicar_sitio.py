# -*- coding: utf-8 -*-
"""Genera `site/` — la copia PUBLICA del tablero, lista para GitHub Pages.

    python publicar_sitio.py                      # todas las fechas de output/
    python publicar_sitio.py --fecha 2026-09-23   # una
    python publicar_sitio.py --verificar          # no escribe; solo comprueba

QUE HACE, EN ESTE ORDEN
-----------------------
  1. construye el snapshot y lo renderiza, igual que `run_snapshot.py`;
  2. lo REDACTA con `snapshot.publicar`: fuera los valores de las series de
     terminal y las fichas de research de fuente Bloomberg;
  3. lo VERIFICA: si sobrevive un ticker, un valor junto a su nombre o un
     extracto de una ficha retenida, revienta y NO escribe nada;
  4. solo entonces escribe `site/snapshot-FECHA.html` y el indice.

El paso 3 no es decorativo. Publicar es irreversible --lo que llega a una
pagina publica queda cacheado e indexado aunque se borre despues-- asi que la
comprobacion va ANTES del disco, no despues.

El sitio nunca lleva los PDF del brief: redactar un PDF con garantias es otro
problema, y publicar uno sin redactar seria justo lo que este modulo evita.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from snapshot import build, data, indicators, publicar, render   # noqa: E402

SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "output")


def fechas_disponibles() -> list[str]:
    """Las fechas ya generadas en output/, que son las que se han publicado."""
    fs = set()
    for p in glob.glob(os.path.join(OUT, "snapshot-*.html")):
        m = re.search(r"snapshot-(\d{4}-\d{2}-\d{2})\.html$", os.path.basename(p))
        if m:
            fs.add(m.group(1))
    return sorted(fs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", action="append",
                    help="fecha concreta; se puede repetir")
    ap.add_argument("--verificar", action="store_true",
                    help="comprueba la redacción sin escribir nada")
    a = ap.parse_args()

    fechas = a.fecha or fechas_disponibles()
    if not fechas:
        print("No hay snapshots en output/. Corre run_snapshot.py primero.")
        return 1

    print("Cargando datos...")
    macro, _ = data.load_macro()
    px = data.load_prices()
    ctx = build.Context(indicators.build_panel(macro, px), prices=px, macro=macro)

    retenido: dict[str, int] = {}
    hechas: list[str] = []
    for f in fechas:
        snap = build.build_snapshot(ctx, f)
        doc = render.render_html(snap)
        pub, informe = publicar.redactar(doc, snap)
        try:
            publicar.verificar(pub, snap)
        except publicar.FugaDeDatos as e:
            print(f"  {f}: ABORTADO — {e}")
            return 2
        for r in informe:
            retenido[f'{r["label"]} ({r["src"]})'] = \
                retenido.get(f'{r["label"]} ({r["src"]})', 0) + 1
        if not a.verificar:
            os.makedirs(SITE, exist_ok=True)
            with open(os.path.join(SITE, f"snapshot-{f}.html"), "w",
                      encoding="utf-8") as fh:
                fh.write(pub)
        hechas.append(f)
        print(f"  {f}: ok · {len(informe)} elementos retenidos")

    if not a.verificar:
        # El índice lista TODO lo que hay en site/, no solo lo generado en esta
        # pasada. Con `--fecha`, escribir solo `hechas` borraba del índice las
        # páginas de las semanas anteriores, que seguían ahí y dejaban de tener
        # enlace: es justo lo que hace la publicación semanal.
        publicadas = sorted({
            m.group(1) for p in glob.glob(os.path.join(SITE, "snapshot-*.html"))
            for m in [re.search(r"snapshot-(\d{4}-\d{2}-\d{2})\.html$",
                                os.path.basename(p))] if m})
        with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(publicar.indice(sorted(publicadas)))
        # Pages no sirve rutas que empiezan por guion bajo si hay Jekyll; con
        # .nojekyll el sitio se publica tal cual, que es lo que queremos.
        open(os.path.join(SITE, ".nojekyll"), "w").close()

    print(f"\n{len(hechas)} páginas · destino {'(solo verificación)' if a.verificar else SITE}")
    print("Retenido en todas ellas:")
    for k, n in sorted(retenido.items()):
        print(f"  {n:2d}×  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
