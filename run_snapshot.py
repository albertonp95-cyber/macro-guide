# -*- coding: utf-8 -*-
"""Genera el snapshot macro y de mercado.

    python run_snapshot.py                    # hoy
    python run_snapshot.py --fecha 2020-03-16 # una fecha historica
    python run_snapshot.py --validar          # las cuatro fechas de control
    python run_snapshot.py --force            # ignora la cache y vuelve a bajar

Escribe en output/. Nunca escribe fuera de este proyecto.
"""

from __future__ import annotations

import argparse
import os
import sys

import config
from snapshot import brief, build, consistencia, data, historico, indicators, pdf, render

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)


def _cargar(force: bool):
    print("Cargando datos...")
    macro, _last_ref = data.load_macro(force=force)
    px = data.load_prices(force=force)
    panel = indicators.build_panel(macro, px)
    print(f"  panel: {panel.shape[1]} indicadores, "
          f"{panel.index[0].date()} a {panel.index[-1].date()}")
    # `macro` va tambien: de ahi salen las variables de entorno que no son
    # indicadores del tablero (tasa de referencia, balance de la Fed).
    return build.Context(panel, prices=px, macro=macro)


def _escribir(ctx, fecha, etiqueta: str | None = None,
              persistir: bool = False) -> str:
    # Solo el snapshot REAL compara con el anterior y guarda su estado. Las
    # fechas de control no ensucian la memoria ni se comparan entre si.
    previo = historico.cargar_previo(fecha if fecha else ctx.panel.index[-1]) if persistir else None
    snap = build.build_snapshot(ctx, fecha, previo=previo)
    stamp = snap["asof"].strftime("%Y-%m-%d")
    base = f"snapshot-{stamp}"
    html_path = os.path.join(OUT, base + ".html")
    md_path = os.path.join(OUT, base + ".md")

    # El brief primero: su comparacion con el HTML entra en el propio tablero de
    # auditoria del HTML, asi que este se compone en dos pasadas.
    brief_html, plog = brief.render_brief(snap)
    html_pasada1 = render.render_html(snap)
    snap["consistencia"] = consistencia.comparar(snap, html_pasada1, brief_html)
    # Los dos documentos YA RENDERIZADOS entran al QA semantico (SPEC-2P 11):
    # cinco de las ocho comprobaciones miran lo que el documento AFIRMA, y sin
    # el documento se quedarian en "sin datos" para siempre.
    snap["_html_doc"], snap["_brief_doc"] = html_pasada1, brief_html
    snap["comprobaciones"] = build._comprobaciones(snap)

    html_doc = render.render_html(snap)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render.render_md(snap))
    # ---- OUTPUT 2: PM Brief (SPEC 11). Misma ejecucion, mismo DecisionState.
    brief_path = os.path.join(OUT, base + "-brief.html")
    pdf_path = os.path.join(OUT, base + "-brief.pdf")
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(brief_html)
    ok, det = pdf.imprimir(brief_path, pdf_path)
    snap["brief_log"] = plog
    snap["brief_pdf"] = (pdf_path if ok else None)
    snap["brief_paginas"] = pdf.paginas(pdf_path) if ok else None

    if persistir:
        historico.guardar(snap)

    t = snap["titular"]
    pref = f"[{etiqueta}] " if etiqueta else ""
    cmb = snap.get("cambios") or {}
    ncmb = ("sin anterior" if not cmb.get("disponible")
            else "sin cambios" if not cmb.get("algo") else "con cambios")
    print(f"  {pref}{stamp}: {t['estado']} (percentil "
          f"{t['hist_pct']:.0f}), {t['duracion']} | "
          f"{len(snap['divergencias'])} divergencias, "
          f"{len(snap['extremos'])} extremos | {ncmb}")
    print(f"    -> {os.path.relpath(html_path, ROOT)}")
    if snap.get("brief_pdf"):
        print(f"    -> {os.path.relpath(snap['brief_pdf'], ROOT)} "
              f"({snap.get('brief_paginas')} págs · {det})")
    else:
        print(f"    -> brief en HTML, sin PDF: {det}")
    c = snap["consistencia"]
    print(f"    {'OK ' if c['ok'] else '!! '}{consistencia.informe(c)}")
    return html_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Snapshot macro y de mercado")
    ap.add_argument("--fecha", default=None, help="AAAA-MM-DD (por defecto, hoy)")
    ap.add_argument("--validar", action="store_true",
                    help="genera las cuatro fechas de control")
    ap.add_argument("--force", action="store_true", help="fuerza la descarga")
    args = ap.parse_args()

    ctx = _cargar(args.force)

    if args.validar:
        print("\nFechas de control:")
        for d in config.VALIDATION_DATES:
            _escribir(ctx, d, etiqueta="control")
        print()

    fecha = args.fecha or ctx.panel.index[-1]
    print("\nSnapshot:")
    ultimo = _escribir(ctx, fecha, persistir=True)

    # copia estable, para enlazar siempre al mismo sitio
    with open(ultimo, encoding="utf-8") as f:
        contenido = f.read()
    with open(os.path.join(OUT, "snapshot.html"), "w", encoding="utf-8") as f:
        f.write(contenido)
    return 0


if __name__ == "__main__":
    sys.exit(main())
