# -*- coding: utf-8 -*-
"""Impresion del PM Brief a PDF.

El brief se compone con su PROPIO template (snapshot/brief.py) y aqui solo se
imprime. Se usa el motor de un navegador headless porque es lo que hay en la
maquina y porque es exactamente lo que hacen weasyprint o wkhtmltopdf por
dentro: paginar CSS. No se "captura" el HTML del informe --eso es justo lo que
SPEC 11 prohibe--; se imprime un documento pensado para papel.

Si no hay navegador, el brief queda en HTML y se dice. No se inventa un PDF.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

CANDIDATOS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def motor() -> str | None:
    for c in CANDIDATOS:
        if os.path.isfile(c):
            return c
    for n in ("chrome", "msedge", "chromium"):
        p = shutil.which(n)
        if p:
            return p
    return None


def imprimir(html_path: str, pdf_path: str, timeout: int = 120) -> tuple[bool, str]:
    """Imprime `html_path` en `pdf_path`. Devuelve (ok, detalle)."""
    exe = motor()
    if not exe:
        return False, "no hay navegador headless en la máquina"
    perfil = tempfile.mkdtemp(prefix="brief-")
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    base = [exe, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer", f"--user-data-dir={perfil}",
            "--virtual-time-budget=4000",
            f"--print-to-pdf={os.path.abspath(pdf_path)}", url]
    try:
        r = subprocess.run(base, capture_output=True, timeout=timeout)
        if not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) < 1000:
            # algunas versiones no aceptan --headless=new
            base[1] = "--headless"
            r = subprocess.run(base, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "el navegador no respondió a tiempo"
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
    if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 1000:
        return True, os.path.basename(exe)
    err = (r.stderr or b"").decode("utf-8", "ignore")[-200:]
    return False, f"el navegador no produjo PDF. {err}"


def paginas(pdf_path: str) -> int | None:
    """Cuantas paginas tiene el PDF realmente, leidas del archivo."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf_path).pages)
    except Exception:                                        # noqa: BLE001
        return None
