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
import pathlib
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
    # `google-chrome` y `chromium-browser` son los nombres que usan las
    # distribuciones Linux --y los runners de GitHub-- donde no hay chrome.exe.
    # Sin ellos, el mismo codigo que imprime en Windows no encontraba navegador
    # en la nube y el PDF se quedaba sin generar.
    for n in ("chrome", "msedge", "chromium", "google-chrome",
              "google-chrome-stable", "chromium-browser"):
        p = shutil.which(n)
        if p:
            return p
    return None


def imprimir(html_path: str, pdf_path: str, timeout: int = 180) -> tuple[bool, str]:
    """Imprime `html_path` en `pdf_path`. Devuelve (ok, detalle).

    DOS INTENTOS, y el segundo tambien cuando el primero SE CUELGA. Antes el
    reintento con `--headless` clasico solo ocurria si el primero terminaba sin
    dejar fichero; si se quedaba colgado, el timeout devolvia "el navegador no
    respondio a tiempo" y no se probaba nada mas. Es exactamente lo que pasaba
    en el runner de GitHub, donde `--headless=new` no vuelve.

    Y lo que diga el navegador SE DEVUELVE. Descartar su stderr convertia cada
    fallo en una adivinanza: "no respondio a tiempo" no dice si falta una
    biblioteca, si no hay sitio en /dev/shm o si el perfil no se pudo crear.
    """
    exe = motor()
    if not exe:
        return False, "no hay navegador headless en la máquina"
    salida = os.path.abspath(pdf_path)
    # `Path.as_uri()` y no "file:///" + ruta. En Windows la ruta absoluta
    # empieza por `C:` y concatenar daba una URL valida; en Linux empieza por
    # `/` y salia `file:////home/...` con CUATRO barras. Chrome no carga esa
    # pagina y se queda esperando para siempre --no da error--, que es como se
    # manifesto en el runner: el navegador imprimia cualquier otra cosa en un
    # segundo y este documento colgaba a los 180. Ademas `as_uri` escapa los
    # espacios, que esta ruta tiene.
    url = pathlib.Path(html_path).resolve().as_uri()

    def intento(modo: str) -> tuple[bool, str]:
        perfil = tempfile.mkdtemp(prefix="semanal-")
        # SIN `--virtual-time-budget`. El tiempo virtual solo avanza cuando la
        # pagina esta ociosa, y con los siete SVG del Tape nunca alcanzaba el
        # presupuesto: Chrome no salia jamas. En el runner de GitHub costo
        # cuatro corridas descubrirlo, porque una pagina trivial SI termina y
        # el navegador parecia roto. El documento no carga nada asincrono, asi
        # que no hay nada que esperar.
        #
        # Y sin `--no-zygote`, que mantiene vivo el proceso despues de imprimir
        # y convierte cualquier espera en una espera infinita.
        cmd = [exe, modo, "--disable-gpu", "--no-sandbox",
               # El contenedor de CI da un /dev/shm diminuto.
               "--disable-dev-shm-usage", "--hide-scrollbars",
               "--no-first-run", "--no-default-browser-check",
               "--no-pdf-header-footer", f"--user-data-dir={perfil}",
               f"--print-to-pdf={salida}", url]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout)
            err = (r.stderr or b"").decode("utf-8", "ignore").strip()
        except subprocess.TimeoutExpired:
            return False, f"{modo}: no respondió en {timeout} s"
        except Exception as e:                               # noqa: BLE001
            return False, f"{modo}: {type(e).__name__}: {e}"
        finally:
            shutil.rmtree(perfil, ignore_errors=True)
        if os.path.isfile(salida) and os.path.getsize(salida) > 1000:
            return True, os.path.basename(exe)
        return False, f"{modo}: sin PDF. {err[-300:]}"

    ok, det = intento("--headless=new")
    if ok:
        return True, det
    ok2, det2 = intento("--headless")
    if ok2:
        return True, det2
    return False, f"{det} | {det2}"


def paginas(pdf_path: str) -> int | None:
    """Cuantas paginas tiene el PDF realmente, leidas del archivo."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf_path).pages)
    except Exception:                                        # noqa: BLE001
        return None
