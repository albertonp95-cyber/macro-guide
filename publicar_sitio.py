# -*- coding: utf-8 -*-
"""Arma el índice de `site/` y comprueba lo que hay publicado.

    python publicar_sitio.py              # rehace el índice
    python publicar_sitio.py --verificar  # revisa cada página ya publicada

QUIEN GENERA LAS PAGINAS. `run_snapshot.py`, en la misma pasada en que escribe
la copia interna y a partir del MISMO documento y el MISMO snapshot. Este
script no construye ninguna.

No siempre fue asi, y por eso se dice: antes construia el snapshot por su
cuenta para redactarlo, y lo hacia sin cargar el estado previo. Resultado: la
pagina publicada decia "Sin snapshot anterior con el que comparar" mientras la
interna traia su registro de cambios entero. Dos documentos con la misma fecha
diciendo cosas distintas. La copia publica tiene que ser la interna menos lo
retenido, y la unica forma de garantizarlo es que salga de ella, no de una
reconstruccion paralela.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SITE = os.path.join(ROOT, "site")


def fechas_publicadas() -> list[str]:
    """Las fechas que hay en site/, que es lo que el índice tiene que listar."""
    fs = set()
    for p in glob.glob(os.path.join(SITE, "snapshot-*.html")):
        m = re.search(r"snapshot-(\d{4}-\d{2}-\d{2})\.html$", os.path.basename(p))
        if m:
            fs.add(m.group(1))
    return sorted(fs)


def _verificar(fechas: list[str]) -> int:
    """Relee cada página publicada y busca lo que no podía salir.

    Es una comprobación de lo que HAY EN DISCO, no de lo que el generador cree
    haber escrito: si alguien edita un fichero de site/ a mano, o queda una
    página de una versión anterior del redactor, aquí se ve.
    """
    from snapshot import build, data, indicators, publicar
    print("Cargando datos...")
    macro, _ = data.load_macro()
    px = data.load_prices()
    ctx = build.Context(indicators.build_panel(macro, px), prices=px, macro=macro)
    malas = 0
    for f in fechas:
        ruta = os.path.join(SITE, f"snapshot-{f}.html")
        with open(ruta, encoding="utf-8") as fh:
            doc = fh.read()
        snap = build.build_snapshot(ctx, f)
        try:
            publicar.verificar(doc, snap)
            print(f"  {f}: limpia")
        except publicar.FugaDeDatos as e:
            print(f"  {f}: FUGA — {e}")
            malas += 1
    return 1 if malas else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true",
                    help="revisa las páginas publicadas en vez de tocar el índice")
    a = ap.parse_args()

    fechas = fechas_publicadas()
    if not fechas:
        print("site/ está vacío. Corre run_snapshot.py primero.")
        return 1

    if a.verificar:
        return _verificar(fechas)

    from snapshot import publicar
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(publicar.indice(fechas))
    # Pages no sirve rutas que empiezan por guion bajo si hay Jekyll; con
    # .nojekyll el sitio se publica tal cual, que es lo que queremos.
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    print(f"índice con {len(fechas)} páginas · {fechas[-1]} la más reciente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
