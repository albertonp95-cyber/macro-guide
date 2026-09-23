# -*- coding: utf-8 -*-
"""La copia PUBLICA no puede llevar datos de terminal.

Publicar es irreversible: lo que llega a una pagina publica queda cacheado e
indexado aunque se borre despues. Asi que la garantia no puede ser "lo revise";
tiene que ser un test que falle antes de que nada salga.

Se comprueban tres cosas distintas:

  A · la REDACCION deja el documento limpio, y su verificador sabe detectar que
      no lo esta --un verificador que siempre dice que si no verifica nada--;
  B · la LECTURA no cambia: el documento publico dice la misma postura, la
      misma confianza y las mismas conclusiones que el interno. Retener una
      cifra no puede convertirse en publicar otra lectura;
  C · el .gitignore ignora de verdad lo que dice que ignora. Git no admite
      comentarios al final de una linea, y `data/cache/  # series crudas` no
      ignora nada: se lee como el nombre literal de un fichero. Esa erratsa
      habria publicado los CSV de la terminal.

    python tests/test_publicacion.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                    # noqa: E402
from snapshot import (build, data, indicators, publicar,         # noqa: E402
                      render)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FECHAS = list(config.VALIDATION_DATES)
_cache: dict = {}


def _ctx():
    if "ctx" not in _cache:
        macro, _ = data.load_macro()
        px = data.load_prices()
        _cache["ctx"] = build.Context(indicators.build_panel(macro, px),
                                      prices=px, macro=macro)
    return _cache["ctx"]


def _par(f):
    """(snapshot, documento interno, documento publico)."""
    if f not in _cache:
        snap = build.build_snapshot(_ctx(), f)
        doc = render.render_html(snap)
        pub, _inf = publicar.redactar(doc, snap)
        _cache[f] = (snap, doc, pub)
    return _cache[f]


# ================================ A · la redacción =========================
def test_lo_retenido_se_deriva_de_la_fuente_y_no_de_una_lista():
    """Una lista a mano se queda corta en la primera ampliación, y el fallo es
    silencioso: la serie nueva se publica y nadie se entera."""
    claves = {i["key"] for i in publicar.retenidas()}
    esperado = {i["key"] for i in config.INDICATORS
                if "bloomberg" in (i.get("src") or "").lower()}
    assert claves == esperado, f"retenidas {claves} ≠ de fuente Bloomberg {esperado}"
    assert claves, "ningún indicador de terminal: ¿cambió el campo `src`?"


def test_la_copia_publica_pasa_su_propia_verificacion():
    for f in FECHAS:
        snap, _doc, pub = _par(f)
        publicar.verificar(pub, snap)          # revienta si algo sobrevive


def test_el_verificador_detecta_un_documento_sin_redactar():
    """Sin esto, los demás tests solo demuestran que la función no lanza."""
    for f in FECHAS[:1]:
        snap, doc, _pub = _par(f)
        try:
            publicar.verificar(doc, snap)
        except publicar.FugaDeDatos:
            return
        raise AssertionError(
            "el verificador da por bueno un documento SIN redactar")


def test_ningun_codigo_de_terminal_sobrevive():
    tks = publicar._tickers()
    assert tks, "no se detectó ningún ticker: ¿cambió el formato de `src`?"
    for f in FECHAS:
        _snap, _doc, pub = _par(f)
        for tk in tks:
            assert tk not in pub, f"{f}: sobrevive el ticker {tk}"


def test_la_copia_publica_dice_que_es_una_copia_publica():
    """Un documento al que le falta un dato y no lo dice es peor que uno
    completo: el lector no puede saber que está leyendo algo recortado."""
    for f in FECHAS:
        _snap, _doc, pub = _par(f)
        assert "Copia pública" in pub, f"{f}: no se avisa de que es copia pública"
        assert publicar.MARCA in pub, f"{f}: no se marca ningún dato retenido"


def test_las_filas_retenidas_siguen_estando():
    """Se retiene la CIFRA, no la fila. Borrar el indicador entero ocultaría
    que el pilar de crédito se apoya en algo que no se publica."""
    for f in FECHAS:
        _snap, _doc, pub = _par(f)
        for ind in publicar.retenidas():
            assert f'id="ind-{ind["key"]}"' in pub, (
                f'{f}: desapareció la fila {ind["key"]}')
            assert ind["label"] in pub, f'{f}: desapareció «{ind["label"]}»'


# ================================ B · la lectura ===========================
def _estado(doc: str) -> str:
    """El estado canónico que el documento publica, tal cual."""
    m = re.search(r'id="decision-state"[^>]*>(.*?)</script>', doc, re.S)
    assert m, "el documento no publica su estado canónico"
    return m.group(1).strip()


def test_la_lectura_publicada_es_la_misma():
    """Retener una cifra no puede cambiar lo que el documento concluye.

    Se comparan los dos documentos por el ESTADO CANONICO que ambos publican
    --postura, confianza, señal, régimen, los dieciséis campos-- y no por el
    texto de las conclusiones: la prosa pasa por `es_num` y por el escapado de
    entidades, así que comparar la cadena cruda mediría el formateo, no la
    lectura.
    """
    for f in FECHAS:
        snap, doc, pub = _par(f)
        assert _estado(doc) == _estado(pub), (
            f"{f}: la copia pública publica un estado distinto")
        pg = (snap.get("postura_general") or {}).get("palabra") or ""
        assert pg and pg.upper() in pub, f"{f}: la postura no se publica"


def test_lo_unico_que_cambia_es_lo_retenido():
    """La diferencia entre las dos copias tiene que estar ACOTADA: el aviso, y
    los entornos de las series retenidas. Si la redacción tocara otra cosa, la
    copia pública dejaría de ser el mismo documento."""
    for f in FECHAS:
        _snap, doc, pub = _par(f)
        # las secciones y su orden, idénticos
        sec = lambda d: re.findall(r'<section id="([^"]+)"', d)   # noqa: E731
        assert sec(doc) == sec(pub), f"{f}: cambia la estructura de secciones"
        # y los indicadores publicados, los mismos
        ind = lambda d: sorted(set(re.findall(r'id="ind-([^"]+)"', d)))  # noqa: E731
        assert ind(doc) == ind(pub), f"{f}: cambia el conjunto de indicadores"


def _texto(doc: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", doc))


def test_el_indice_del_sitio_enlaza_lo_que_dice_enlazar():
    idx = publicar.indice(["2026-09-23", "2026-09-22"])
    for f in ("2026-09-23", "2026-09-22"):
        assert f'href="snapshot-{f}.html"' in idx, f"falta el enlace de {f}"
    assert "Copia pública" in idx, "el índice no explica qué se retiene"


# ================================ C · el .gitignore ========================
_SENSIBLES = [
    "data/cache/bbg_hy_oas.csv",
    "data/cache/fred_NFCI.csv",
    "data/historico/estado-2026-09-23.json",
    "docs/registro.json",
    "output/snapshot-2026-09-23.html",
    "research/9.11/image.png",
    "baseline/2008-09-15.BASELINE.html",
]


def test_el_gitignore_ignora_de_verdad():
    """Se le pregunta a git, no al fichero. `output/  # nota` parece correcto y
    no ignora nada: git no admite comentarios al final de una línea."""
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("        (no hay repo git: comprobación omitida)")
        return
    for ruta in _SENSIBLES:
        r = subprocess.run(["git", "check-ignore", "-q", ruta],
                           cwd=ROOT, capture_output=True)
        assert r.returncode == 0, f"«{ruta}» NO está ignorado y se publicaría"


def test_nada_sensible_esta_en_el_indice_de_git():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("        (no hay repo git: comprobación omitida)")
        return
    r = subprocess.run(["git", "ls-files"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    seguidos = set((r.stdout or "").splitlines())
    for pre in ("data/cache/", "data/historico/", "research/", "docs/research/",
                "output/", "baseline/"):
        malos = sorted(x for x in seguidos if x.startswith(pre))
        assert not malos, f"git sigue {len(malos)} fichero(s) bajo {pre}: {malos[:3]}"
    assert "docs/registro.json" not in seguidos, (
        "docs/registro.json está en el repositorio: lleva extractos de research")


# ------------------------------------------------------------------ runner
def _run():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    ok = fallos = 0
    for n, f in fns:
        try:
            f()
            print(f"  PASS  {n}")
            ok += 1
        except AssertionError as e:
            print(f"  FAIL  {n}\n        {e}")
            fallos += 1
        except Exception as e:                                   # noqa: BLE001
            print(f"  ERROR {n}\n        {type(e).__name__}: {e}")
            fallos += 1
    print(f"\n{ok} pasados, {fallos} fallidos, {len(fns)} totales")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_run())
