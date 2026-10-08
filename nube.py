# -*- coding: utf-8 -*-
"""Sincroniza con el repositorio PRIVADO de estado.

    python nube.py subir     # manda tu estado local a la nube
    python nube.py bajar     # trae el estado de la nube a esta máquina
    python nube.py ver       # qué hay en cada lado, sin tocar nada

QUÉ VIAJA, Y POR QUÉ NO ESTÁ EN EL REPO PÚBLICO
-----------------------------------------------
Tres cosas que el pipeline no puede regenerar en la nube:

  data/cache/bbg_*.csv   las dos series OAS de la Terminal
  data/historico/*.json  el archivo de estados (guarda sus percentiles)
  docs/registro.json     el registro de research (extractos de terceros)

Sin ellas el pipeline cae al proxy de Moody's y publica OTRA LECTURA del mismo
día: medido el 28/09/2026, crédito 82 en vez de 69 y riesgo p72 en vez de p59.
Dos documentos con la misma fecha y cifras distintas es exactamente lo que este
proyecto lleva pasadas enteras evitando, así que el estado viaja.

QUIÉN ESCRIBE QUÉ
-----------------
La tarea semanal de la nube devuelve `data/historico/` después de cada corrida:
es lo único que ella genera. Las series de la Terminal y el registro de
research los subes tú, y los dos pasos siguen siendo manuales y deliberados.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/albertonp95-cyber/macro-guide-estado.git"

# Qué se sincroniza. `patron` es relativo a la raíz del proyecto.
PARTES = [
    ("data/cache", "bbg_*.csv", "series OAS de la Terminal"),
    ("data/historico", "*.json", "archivo de estados"),
    ("docs", "registro.json", "registro de research"),
]


def _corre(args, cwd=None, callar=False):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and not callar:
        print(f"  ! {' '.join(args[:3])}… -> {r.returncode}")
        if r.stderr:
            print("   ", r.stderr.strip()[:300])
        raise SystemExit(1)
    return r


def _clonar(dest: str) -> None:
    print(f"clonando {REPO.split('/')[-1]}…")
    _corre(["git", "clone", "-q", "--depth", "1", REPO, dest])


def _copiar(origen: str, destino: str, carpeta: str, patron: str) -> int:
    o = os.path.join(origen, carpeta)
    d = os.path.join(destino, carpeta)
    os.makedirs(d, exist_ok=True)
    n = 0
    for f in sorted(glob.glob(os.path.join(o, patron))):
        shutil.copy2(f, os.path.join(d, os.path.basename(f)))
        n += 1
    return n


def ver() -> int:
    tmp = tempfile.mkdtemp(prefix="estado-")
    try:
        _clonar(tmp)
        print(f"\n{'parte':26s} {'aquí':>6s} {'nube':>6s}")
        for carpeta, patron, desc in PARTES:
            a = len(glob.glob(os.path.join(ROOT, carpeta, patron)))
            b = len(glob.glob(os.path.join(tmp, carpeta, patron)))
            marca = "" if a == b else "   <-- difieren"
            print(f"{desc:26s} {a:6d} {b:6d}{marca}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def subir() -> int:
    tmp = tempfile.mkdtemp(prefix="estado-")
    try:
        _clonar(tmp)
        total = 0
        for carpeta, patron, desc in PARTES:
            n = _copiar(ROOT, tmp, carpeta, patron)
            print(f"  {desc}: {n} fichero(s)")
            total += n
        if not total:
            print("no hay nada que subir.")
            return 1
        _corre(["git", "add", "-A"], cwd=tmp)
        if not _corre(["git", "status", "--porcelain"], cwd=tmp).stdout.strip():
            print("\nla nube ya tiene exactamente esto: no hay nada que subir.")
            return 0
        _corre(["git", "-c", "user.name=albertonp95-cyber",
                "-c", "user.email=279798657+albertonp95-cyber@users.noreply.github.com",
                "commit", "-q", "-m", "Estado actualizado desde la máquina local"],
               cwd=tmp)
        _corre(["git", "push", "-q"], cwd=tmp)
        print("\nsubido. La próxima corrida de la nube ya lo usa.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def bajar() -> int:
    tmp = tempfile.mkdtemp(prefix="estado-")
    try:
        _clonar(tmp)
        for carpeta, patron, desc in PARTES:
            n = _copiar(tmp, ROOT, carpeta, patron)
            print(f"  {desc}: {n} fichero(s)")
        print("\nbajado. Ojo: sobrescribe lo que tuvieras aquí.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("accion", choices=("subir", "bajar", "ver"))
    a = ap.parse_args()
    return {"subir": subir, "bajar": bajar, "ver": ver}[a.accion]()


if __name__ == "__main__":
    sys.exit(main())
