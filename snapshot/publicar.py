# -*- coding: utf-8 -*-
"""PUBLICACION — la copia publica del snapshot, con los datos de Bloomberg fuera.

POR QUE EXISTE
--------------
`snapshot/bloomberg.py` lo dice desde el primer dia: Bloomberg no limita
consultar datos DENTRO de la terminal, pero si extraerlos a ficheros o
plataformas externas. Una pagina publica en GitHub es exactamente una
plataforma externa, asi que el documento que se publica NO puede llevar los
valores de las series que vienen de la terminal.

QUE SE RETIENE, Y COMO SE DECIDE
--------------------------------
No hay lista escrita a mano. Se retiene todo indicador cuyo `src` en
`config.INDICATORS` nombre a Bloomberg --hoy cuatro: los dos OAS, su prima y la
compensacion del credito--. Si manana alguien añade una quinta serie de
terminal, sale retenida sola. Una lista a mano se habria quedado corta en la
primera ampliacion, y el fallo habria sido silencioso.

QUE **NO** SE RETIENE, Y POR QUE
--------------------------------
  - El NOMBRE del indicador y la atribucion a Bloomberg. Citar la fuente no es
    redistribuirla; ocultar que el pilar de credito se apoya en cuatro series
    que no se publican seria peor que decirlo.
  - Los COMPUESTOS de pilar. Un nivel de pilar es un agregado de cinco
    indicadores de fuentes distintas, no una serie de Bloomberg servida con
    otro nombre. La linea esta en el dato individual.
  - La LECTURA. El documento publico dice lo mismo que el privado: misma
    postura, misma conviccion, mismas conclusiones. No se recalcula nada sin
    esas series, porque entonces habria dos documentos con la misma fecha
    diciendo cosas distintas, que es el problema que este proyecto lleva
    pasadas enteras evitando.

COMO SE GARANTIZA
-----------------
La redaccion se hace sobre el DOCUMENTO RENDERIZADO, no sobre los datos, por la
misma razon que `consistencia` y `semantica` trabajan ahi: lo que hay que
garantizar es lo que el lector puede leer. Y despues se VERIFICA: `verificar()`
recorre el documento redactado y revienta si sobrevive un ticker o un valor
cerca del nombre de su serie. Si revienta, no se publica nada.
"""

from __future__ import annotations

import html as _html
import os
import re

import config

# Marca visible en la copia publica. El lector tiene que saber que esta viendo
# un documento con algo fuera, y que.
MARCA = "dato retenido"
AVISO_HTML = (
    '<p class="pub-av"><b>Copia pública.</b> Este documento es idéntico al '
    'original salvo en un punto: los valores de {n} indicadores que provienen '
    'de una terminal Bloomberg ({lista}) se han retenido, porque su licencia '
    'permite consultarlos en la terminal pero no redistribuirlos fuera de ella. '
    'Las filas siguen ahí, con su nombre y su fuente; lo que no aparece es la '
    'cifra. <b>La lectura no cambia</b>: postura, confianza y conclusiones son '
    'las mismas que en la copia interna, calculadas con todos los indicadores.'
    '</p>')


def retenidas() -> list[dict]:
    """Los indicadores que no pueden salir, DERIVADOS de `src`."""
    return [i for i in config.INDICATORS
            if "bloomberg" in (i.get("src") or "").lower()]


def _nombres(key: str, label: str) -> list[str]:
    """Las formas con las que el documento puede nombrar a esa serie."""
    fs = {label, config.SHORT.get(key, "")}
    return sorted((f for f in fs if f), key=len, reverse=True)


def _tickers() -> list[str]:
    """Los codigos de terminal que aparecen en la atribucion de fuente."""
    out = set()
    for i in retenidas():
        for tk in re.findall(r"\b[A-Z][A-Z0-9]{4,}\b", i.get("src") or ""):
            out.add(tk)
    return sorted(out)


def _filas(snap: dict) -> dict:
    """key -> la fila del tablero, que es de donde salen los valores impresos."""
    out = {}
    for pil in (snap.get("tablero") or []):
        for f in pil.get("filas", []):
            out[f["key"]] = f
    return out


# ------------------------------------------------------------------ redaccion
def _redacta_fila(doc: str, key: str) -> str:
    """Vacia las celdas de valor, percentil y cambio de UNA fila.

    Se trabaja sobre el bloque de la fila --de su `id` al siguiente `<div
    class="row"`-- para no tocar nada de al lado. El percentil se va entero,
    marcador incluido: la posicion del punto en la barra es el percentil, y
    dejarla seria publicar el dato en forma de pixel.
    """
    i = doc.find(f'id="ind-{key}"')
    if i < 0:
        return doc
    ini = doc.rfind('<div class="row', 0, i + 1)
    fin = doc.find('<div class="row', i + 1)
    if fin < 0:
        fin = doc.find("</section>", i)
    bloque = doc[ini:fin]
    b = bloque

    # el buscador lleva el ticker dentro
    b = re.sub(r'(data-buscar=")([^"]*)(")',
               lambda m: m.group(1) + _limpia_texto(m.group(2)) + m.group(3), b)
    # la atribucion de fuente: se queda Bloomberg, se va el codigo
    b = re.sub(r'(<span class="src">)([^<]*)(</span>)',
               lambda m: f'{m.group(1)}{_limpia_texto(m.group(2))} · {MARCA}{m.group(3)}', b)
    # valor
    b = re.sub(r'(<div class="num"><span class="cap">[^<]*</span>)[^<]*(</div>)',
               r'\1<span class="pub-x">—</span>\2', b)
    # percentil: la celda entera, barra incluida
    b = re.sub(r'<div class="pcell">.*?</div>',
               '<div class="pcell"><span class="cap">Percentil 5 años</span>'
               f'<span class="pub-x">{MARCA}</span></div>', b, flags=re.S)
    # cambios
    b = re.sub(r'<div class="chg">.*?</div>\s*</div>',
               '<div class="chg"><span class="cap">Cambio</span>'
               f'<span class="pub-x">{MARCA}</span></div></div>', b, flags=re.S)
    return doc[:ini] + b + doc[fin:]


def _limpia_texto(t: str) -> str:
    """Quita los codigos de terminal de un texto suelto."""
    for tk in _tickers():
        t = t.replace(tk, "").replace("  ", " ")
    return t.strip(" ·")


def _redacta_prosa(doc: str, nombres: list[str]) -> str:
    """«HY OAS en 2.66 pp» -> «HY OAS (dato retenido)».

    Acotado por puntuacion y por longitud: la prosa cita el valor justo detras
    del nombre, y todo lo que se busca es ese trozo. Lo que quede fuera lo caza
    `_scrub_cerca()`, y lo que se le escape a los dos, `verificar()`.
    """
    for nom in nombres:
        doc = re.sub(re.escape(nom) + r"\s+en\s+[^,;.<)]{1,40}",
                     f"{nom} ({MARCA})", doc)
    return doc


_PCT = re.compile(r"\bp\d{1,3}\b|percentil\s+\d{1,3}")


def _scrub_cerca(doc: str, nombres: list[str], num: str,
                 ventana: int = 240) -> str:
    """Borra el valor de UNA serie alla donde aparezca junto a su nombre.

    Las plantillas que citan un indicador son varias --la prosa, la lista de
    extremos, la nota que enlaza una pieza de research-- y cada una lo escribe
    a su manera. Perseguirlas una a una es una carrera que se pierde en cuanto
    alguien añade la cuarta. Lo que no cambia es la regla: el numero impreso de
    esa serie no puede estar cerca de su nombre. Asi que se busca el NOMBRE y
    se limpia su entorno, sea cual sea la plantilla.

    Solo se toca el valor EXACTO que publica el tablero para esa serie, y los
    percentiles de esa misma ventana. Un numero cualquiera que pase por ahi no
    se toca: no es dato de esta serie.
    """
    if not num:
        return doc
    for nom in nombres:
        pos = 0
        for _ in range(200):                      # cota: no es un while suelto
            i = doc.find(nom, pos)
            if i < 0:
                break
            a, b = i + len(nom), min(len(doc), i + len(nom) + ventana)
            trozo = doc[a:b]
            if num in trozo:
                trozo = trozo.replace(num, MARCA)
                trozo = _PCT.sub(MARCA, trozo)
                doc = doc[:a] + trozo + doc[b:]
            pos = i + len(nom)
    return doc


_CARD = re.compile(r'<div class="doc-item">.*?Origen:.*?</p>\s*</div>', re.S)


def documentos_retenidos(snap: dict) -> list[dict]:
    """Las fichas de research que tampoco pueden salir.

    La capa documental resume piezas de terceros. Las de fuente publica --una
    columna del FT con enlace, una nota de prensa-- son cita normal y se
    quedan. Las de Bloomberg no: son analitica propietaria de la terminal
    --"el diferencial de alto rendimiento excluyendo el 5 % mas ancho baja a
    187 pb"-- y publicarla es la misma extraccion que este modulo evita con
    las series, solo que en prosa.
    """
    reg = snap.get("documentos") or {}
    return [d for d in (reg.get("documentos") or [])
            if "bloomberg" in (d.get("fuente") or "").lower()]


def _retira_documentos(doc: str, fichas: list[dict]) -> str:
    """Quita la ficha entera, y DICE que se quito. No se borra en silencio."""
    if not fichas:
        return doc
    titulos = {d.get("titulo") or "" for d in fichas}

    def _quita(m):
        bloque = m.group(0)
        if any(t and _html.escape(t, quote=True) in bloque for t in titulos):
            return ('<div class="doc-item"><p class="tesis pub-x">Ficha de '
                    'research retenida en la copia pública: la fuente es '
                    'Bloomberg y sus cifras no pueden redistribuirse fuera de '
                    'la terminal.</p></div>')
        return bloque

    return _CARD.sub(_quita, doc)


def redactar(doc: str, snap: dict) -> tuple[str, list[dict]]:
    """El documento publico, y el informe de lo que se retuvo."""
    fuera = retenidas()
    if not fuera:
        return doc, []
    filas = _filas(snap)
    informe = []
    for ind in fuera:
        k, lab = ind["key"], ind["label"]
        crudo = str((filas.get(k) or {}).get("valor") or "")
        m = re.search(r"[+-]?\d+(?:[.,]\d+)?", crudo)
        doc = _redacta_fila(doc, k)
        doc = _redacta_prosa(doc, _nombres(k, lab))
        doc = _scrub_cerca(doc, _nombres(k, lab), m.group(0) if m else "")
        informe.append(dict(key=k, label=lab, src=ind.get("src") or "",
                            valor=crudo))
    # las fichas de research de fuente Bloomberg
    fichas = documentos_retenidos(snap)
    doc = _retira_documentos(doc, fichas)
    for d in fichas:
        informe.append(dict(key=d.get("id") or "", label=d.get("titulo") or "",
                            src=d.get("fuente") or "", valor="ficha completa"))

    # y los codigos de terminal, donde hayan quedado
    for tk in _tickers():
        doc = doc.replace(tk, "")

    # y las coletillas que deja el borrado: «dato retenido pp», «... a 5 años»
    doc = re.sub(re.escape(MARCA) + r"\s*(pp|pb|%|x)\b", MARCA, doc)
    doc = re.sub(re.escape(MARCA) + r"\s+a\s+\d+\s+años", MARCA, doc)
    doc = re.sub(r"(" + re.escape(MARCA) + r")(,?\s+" + re.escape(MARCA) + r")+",
                 r"\1", doc)

    aviso = AVISO_HTML.format(
        n=len(fuera),
        lista=_html.escape(", ".join(config.SHORT.get(i["key"], i["label"])
                                     for i in fuera)))
    # justo debajo de la cabecera, antes de nada que se pueda leer como dato
    doc = doc.replace("</header>", "</header>\n" + aviso, 1)
    doc = doc.replace("</style>", _CSS + "</style>", 1)
    return doc, informe


_CSS = """
.pub-av{border:1px solid var(--rule);border-left:3px solid var(--warn,#8a6d1f);
  padding:10px 13px;margin:14px 0 4px;font-size:12px;line-height:1.55;
  color:var(--muted)}
.pub-av b{color:var(--ink)}
.pub-x{color:var(--faint);font-style:italic;font-size:11px}
"""


# ---------------------------------------------------------------- verificacion
class FugaDeDatos(RuntimeError):
    """Algo que no podia salir, salio. No se publica."""


def verificar(doc: str, snap: dict) -> None:
    """La ultima palabra. Si encuentra una fuga, se aborta la publicacion.

    Dos comprobaciones, las dos sobre el documento ya redactado:
      1. ningun codigo de terminal, en ningun sitio;
      2. ningun valor impreso de una serie retenida a menos de 200 caracteres
         de cualquiera de los nombres de esa serie. La ventana importa: «2.66»
         puede ser legitimamente el valor de otro indicador, y lo que convierte
         un numero en dato de Bloomberg es aparecer al lado de su nombre.
    """
    malas = []
    for tk in _tickers():
        if tk in doc:
            malas.append(f"el ticker {tk} sigue en el documento")
    filas = _filas(snap)
    for ind in retenidas():
        k = ind["key"]
        crudo = str((filas.get(k) or {}).get("valor") or "")
        m = re.search(r"[+-]?\d+(?:[.,]\d+)?", crudo)
        if not m:
            continue
        num = m.group(0)
        for nom in _nombres(k, ind["label"]):
            for pos in (x.start() for x in re.finditer(re.escape(nom), doc)):
                ventana = doc[max(0, pos - 200):pos + 200]
                if num in ventana:
                    malas.append(f"«{num}» sigue junto a «{nom}» ({k})")
                    break
    # 3. ni una linea de las fichas de research retenidas
    for d in documentos_retenidos(snap):
        for x in (d.get("dice") or []):
            t = (x.get("texto") or "")[:60]
            if t and _html.escape(t, quote=True) in doc:
                malas.append(f"sobrevive un extracto de «{d.get('titulo')}»")
                break
    if malas:
        raise FugaDeDatos("la copia pública conserva datos retenidos: "
                          + "; ".join(sorted(set(malas))))


# -------------------------------------------------------------------- el sitio
def _fecha_es(f: str) -> str:
    a, m, d = f.split("-")
    return f"{d}/{m}/{a}"


def indice(fechas: list[str], titulo: str = "Snapshot macro y de mercado") -> str:
    """El indice del sitio. Sin dependencias: una lista de fechas y su enlace."""
    filas = "".join(
        f'<li><a href="snapshot-{f}.html"><b>{_fecha_es(f)}</b>'
        f'<span>snapshot-{f}.html</span></a></li>'
        for f in sorted(fechas, reverse=True))
    n = len(retenidas())
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html.escape(titulo)}</title>
<style>
:root{{--ink:#1b1a17;--muted:#5a564e;--faint:#8b857a;--rule:#ddd8cf;--bg:#fbfaf7}}
*{{box-sizing:border-box}}
body{{margin:0;padding:48px 16px;background:var(--bg);color:var(--ink);
  font:400 15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
main{{max-width:640px;margin:0 auto}}
h1{{font-size:24px;letter-spacing:-.01em;margin:0 0 6px}}
.sub{{color:var(--muted);font-size:13px;margin:0 0 28px}}
ul{{list-style:none;padding:0;margin:0;border-top:1px solid var(--rule)}}
li{{border-bottom:1px solid var(--rule)}}
a{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
  padding:13px 2px;color:var(--ink);text-decoration:none}}
a:hover{{background:#fff}}
a span{{color:var(--faint);font-size:11px;font-family:ui-monospace,monospace}}
.nota{{margin-top:26px;font-size:12px;line-height:1.6;color:var(--muted);
  border-left:3px solid var(--rule);padding-left:12px}}
</style></head>
<body><main>
<h1>{_html.escape(titulo)}</h1>
<p class="sub">Una lectura del estado macro y de mercado. No es un modelo, no
   optimiza y no propone pesos de cartera: ordena la evidencia y dice qué
   sostiene y qué contradice cada inclinación.</p>
<ul>{filas}</ul>
<p class="nota"><b>Copia pública.</b> Los valores de {n} indicadores que
   provienen de una terminal Bloomberg están retenidos en estas páginas: su
   licencia permite consultarlos en la terminal, no redistribuirlos fuera. Las
   filas siguen presentes, con su nombre y su fuente, y la lectura publicada es
   la misma que la interna —se calcula con todos los indicadores—.</p>
</main></body></html>
"""


def publicar(doc: str, snap: dict, destino: str, fecha: str) -> list[dict]:
    """Redacta, VERIFICA y solo entonces escribe. En ese orden."""
    pub, informe = redactar(doc, snap)
    verificar(pub, snap)
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, f"snapshot-{fecha}.html")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(pub)
    return informe
