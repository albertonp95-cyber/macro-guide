# -*- coding: utf-8 -*-
"""Salida del snapshot: HTML de una pagina y markdown para archivo.

El HTML es autocontenido (sin CSS ni JS externos), imprimible y legible en
movil. Es un documento, no un panel de trading.
"""

from __future__ import annotations

import html
import re

import numpy as np

import config
from snapshot.build import (MACRO_PILARES, TECNICO_PILARES,
                            fecha_larga, fecha_corta, minus)


# --------------------------------------------------------------- utilidades
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def es_num(s: str) -> str:
    """Convencion mexicana: punto decimal y coma de millares, igual que la
    terminal de Bloomberg y la banca en Mexico. El punto decimal es lo que ya
    produce Python, asi que no hay que tocar los decimales; solo se agrupan los
    millares de la parte entera cuando el numero es de cuatro cifras o mas.
    No agrupa años ni cuentas de dias (evita convertir 2026 en 2,026)."""
    def _grp(m: "re.Match") -> str:
        entero = m.group(0)
        return f"{int(entero):,}" if len(entero) > 4 else entero
    # Solo enteros de 5+ cifras sueltos (precios, miles de millones), nunca
    # los que van pegados a un punto decimal ni dentro de una fecha.
    return re.sub(r"(?<![\d.,])\d{5,}(?![\d.,])", _grp, s)


def _cap(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def p_str(p: float) -> str:
    return "—" if not np.isfinite(p) else f"p{p:.0f}"


def lvl_str(v: float) -> str:
    return "—" if not np.isfinite(v) else es_num(f"{v:.0f}")


def delta_pts(v: float) -> str:
    return "—" if not np.isfinite(v) else es_num(f"{v:+.0f}")


def puntos(v: float) -> str:
    if not np.isfinite(v):
        return "—"
    return f"{delta_pts(v)} {'punto' if abs(round(v)) == 1 else 'puntos'}"


def flecha(v: float, umbral: float = 3.0) -> str:
    if not np.isfinite(v):
        return "·"
    if v >= umbral:
        return "▲"
    if v <= -umbral:
        return "▼"
    return "·"


CSS = """
/* SPEC-4P 28: por debajo de 640px la tabla deja de ser util --cinco columnas no
   caben-- y cada tema pasa a ser una tarjeta. Mismo contenido, otra caja. */
@media (max-width:640px){
  .pguide,.pguide thead,.pguide tbody,.pguide tr,.pguide td{display:block;width:100%}
  .pguide thead{display:none}
  .pguide tr{border:1px solid var(--rule);margin-bottom:10px;padding:9px 11px}
  .pguide td{border:0;padding:3px 0}
  .pguide td.gc{font-weight:600;font-size:15px;border-bottom:1px solid var(--rule);
    padding-bottom:5px;margin-bottom:4px}
  .pguide td[data-l]::before{content:attr(data-l);display:block;
    font:600 9px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;
    color:var(--faint);margin-bottom:1px}
  .pguide .thk{display:none}
}

/* ---- cuarta pasada: jerarquia de la guia de decision ---- */
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  padding:6px 0;margin-bottom:10px}
  text-transform:uppercase;color:var(--faint);margin-bottom:3px}
  text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.pguide .riesgo{display:block;font-size:11px;color:#8a6d1f;margin-top:3px}
/* SPEC-4P 11: los drivers son el TERCER nivel de la fila. Tienen que poder
   consultarse sin competir con el sesgo, la conviccion ni la expresion. */
.pguide .expr{display:block;font-size:12.5px;line-height:1.35;color:var(--ink)}
.pguide .expsrc{display:block;font-size:10px;line-height:1.3;color:var(--faint);
  margin-top:3px;letter-spacing:.01em}
@media (max-width:640px){
}

:root{
  --paper:#fbfaf8; --ink:#1b1a17; --muted:#6d685f; --faint:#8f8a80;
  --rule:#e2ddd4; --rule-soft:#efebe4;
  --adv:#9c3d34; --fav:#37624a; --neu:#8a857b;
  --band:#eae5db;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-variant-numeric:tabular-nums;-webkit-text-size-adjust:100%}
.doc{max-width:960px;margin:0 auto;padding:38px 26px 64px}

.eyebrow{font:600 10.5px/1 -apple-system,Segoe UI,sans-serif;letter-spacing:.16em;
  text-transform:uppercase;color:var(--faint)}
h1{font:400 30px/1.2 Georgia,"Times New Roman",serif;margin:.35em 0 .18em}
.meta{color:var(--muted);font-size:12.5px;margin:0 0 30px}

section{margin:0 0 38px}
h2{font:600 10.5px/1 -apple-system,Segoe UI,sans-serif;letter-spacing:.15em;
  text-transform:uppercase;color:var(--faint);
  border-bottom:1px solid var(--rule);padding-bottom:7px;margin:0 0 18px}
.note{font-size:12px;color:var(--faint);margin:10px 0 0;line-height:1.5}

/* ---------- 1. titular ---------- */
.headline{font:400 21px/1.42 Georgia,"Times New Roman",serif;margin:0 0 8px}
.headline .state{font-weight:700}
.sub{color:var(--muted);font-size:13.5px;margin:0}

/* ---------- puntuacion de toma de riesgo ---------- */
.score{display:flex;gap:24px;align-items:center;border:1px solid var(--rule);
  background:#fff;border-radius:3px;padding:16px 19px;margin:16px 0 0}
.score .n{font:400 46px/1 Georgia,serif;white-space:nowrap}
.score .n small{font:400 13px/1 -apple-system,sans-serif;color:var(--faint)}
.score .who{flex:1;min-width:0}
.score .lab{font:600 10px/1 -apple-system,sans-serif;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin-bottom:7px}
.tally{display:flex;height:8px;border-radius:1px;overflow:hidden;margin:0 0 6px}
.tally i{display:block;height:8px}
.tally .f{background:var(--fav)} .tally .c{background:var(--adv)} .tally .z{background:var(--band)}
.tallyleg{font-size:12px;color:var(--muted)}
.tallyleg b{font-weight:600}
.tallyleg .raw{display:block;margin-top:5px;color:var(--faint);font-size:11.5px;line-height:1.5}

/* ---------- contradiccion de alto perfil (seccion 4) ---------- */
.contra{border:1px solid #e3c9c5;background:#fdf7f6;border-radius:3px;
  padding:14px 16px;margin:0 0 10px;break-inside:avoid}
.contra .ck{font:600 10px/1 -apple-system,sans-serif;letter-spacing:.14em;
  text-transform:uppercase;color:var(--adv);margin:0 0 8px}
.contra .ct{font-size:14px;line-height:1.5;margin:0}
.contra .ct b{font-weight:600}
.contra .cq2{font-size:12.5px;color:var(--muted);line-height:1.5;margin:11px 0 0}
.contra .cq2 b{color:var(--ink)}
.contra .co{font-size:12.5px;color:var(--muted);line-height:1.5;
  margin:9px 0 0;padding:9px 11px;background:#fff;border-radius:2px}
.contra .co b{color:var(--ink)}
.cmas{font-size:11.5px;color:var(--faint);margin:0 0 14px;line-height:1.5}

/* ---------- lo esencial ---------- */
.key{margin:20px 0 0;padding:0;list-style:none}
.key li{position:relative;padding:0 0 0 18px;margin:0 0 11px;font-size:14.5px;line-height:1.55}
.key li:last-child{margin:0}
.key li::before{content:"";position:absolute;left:0;top:.62em;width:6px;height:6px;
  border-radius:50%;background:var(--neu)}

/* ---------- la conclusion: inclinacion por clase, con conviccion ---------- */
.tens{font-size:13.5px;color:var(--muted);line-height:1.55;margin:16px 0 0;
  padding-left:13px;border-left:2px solid var(--rule)}
.inc-h{font:600 10px/1 -apple-system,sans-serif;letter-spacing:.13em;text-transform:uppercase;
  color:var(--faint);margin:24px 0 10px}
.concl{border-top:1px solid var(--rule)}
.crow{padding:10px 0;border-bottom:1px solid var(--rule-soft)}
.crow:last-child{border-bottom:0}
.cl{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 9px}
.cl .cname{font-weight:600;font-size:14px;min-width:172px}
.cl .cd{font-weight:600;font-size:14px;text-transform:uppercase;letter-spacing:.02em}
.cl .cd.neu{color:#a9a294;font-weight:600}
.cl .cv{font-size:11px;color:var(--faint);display:inline-flex;align-items:center;gap:5px;
  white-space:nowrap}
.cl .cv .meter i{height:9px;width:4px}
.cl .cv.c3{color:var(--fav)} .cl .cv.c3 .meter i.on{background:var(--fav)}
.cl .cv.c2 .meter i.on{background:var(--neu)}
.cl .cv.c1{color:#8a6d1f} .cl .cv.c1 .meter i.on{background:#c8a94e}
.cr{font-size:12.5px;color:var(--muted);line-height:1.5;margin:3px 0 0}

/* ---------- LA NOTA (research) ---------- */
#lectura{margin:20px 0 0}
#lectura>h2{font:600 15px/1.3 Georgia,"Times New Roman",serif;text-transform:none;
  letter-spacing:0;color:var(--ink);border-bottom:1px solid var(--rule);
  padding-bottom:6px;margin:30px 0 14px}
/* caja de conclusiones */
.concl-box{border:1px solid var(--rule);background:#fff;border-radius:4px;
  padding:16px 20px;margin:4px 0 0}
.concl-box .cb-t{font:600 10px/1 -apple-system,Segoe UI,sans-serif;letter-spacing:.15em;
  text-transform:uppercase;color:var(--faint);margin:0 0 10px}
.cb{margin:0;padding:0;list-style:none}
.cb li{position:relative;padding:0 0 0 18px;margin:0 0 10px;font-size:14.5px;line-height:1.5}
.cb li:last-child{margin:0}
.cb li::before{content:"";position:absolute;left:0;top:.6em;width:6px;height:6px;
  border-radius:50%;background:var(--neu)}
.cb li:last-child{font-weight:500}
.cb li:last-child::before{background:var(--ink)}
/* prosa */
.evid p{font-size:14px;line-height:1.62;margin:0 0 12px}
.evid p:last-child{margin:0}
/* gráfico */
.grafico{margin:16px 0 0}
.grafico svg{width:100%;height:auto;display:block}
.grafico .gax{font:400 9px/1 -apple-system,sans-serif;fill:var(--faint)}
.grafico .gnow{font:700 11px/1 -apple-system,sans-serif;fill:var(--ink)}
.grafico figcaption{font-size:11px;color:var(--faint);margin:6px 0 0;line-height:1.5}
.grafico .gk{margin-right:10px;white-space:nowrap}
.grafico .gk i{display:inline-block;width:14px;height:0;vertical-align:middle;margin-right:4px}
.grafico .gk .kr{border-top:2px solid var(--ink)}
.grafico .gk .kc{border-top:2px dashed var(--muted)}
/* tabla de posicionamiento */
.posic{width:100%;border-collapse:collapse;font-size:13px}
.posic th{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.05em;text-transform:uppercase;
  color:var(--faint);text-align:left;padding:0 8px 7px;border-bottom:1px solid var(--rule);white-space:nowrap}
.posic td{padding:9px 8px;border-bottom:1px solid var(--rule-soft);vertical-align:baseline}
.posic tr:last-child td{border-bottom:0}
.posic .pc{font-weight:600;white-space:nowrap}
.posic .sig{font-size:12.5px}
.posic .sig.s2{font-weight:600} .posic .sig.s0{color:var(--faint)}
.posic .cv{font-size:11px;text-transform:uppercase;letter-spacing:.03em}
.posic .cv.c3{color:var(--fav)} .posic .cv.c2{color:var(--muted)} .posic .cv.c1{color:#8a6d1f}
.posic .ineu{color:#a9a294;font-weight:400}
.posic .pa b{font-weight:600}
.posic .pm .ant{color:var(--faint);font-size:12px}
.posic .chgm{color:var(--adv);margin-left:4px;font-weight:700}
/* rejilla de posicionamiento de la lectura */
.pgrid{width:100%;border-collapse:collapse;font-size:13px}
.pgrid th{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.05em;text-transform:uppercase;
  color:var(--faint);text-align:left;padding:0 10px 8px;border-bottom:1px solid var(--rule);white-space:nowrap}
.pgrid td{padding:11px 10px;border-bottom:1px solid var(--rule-soft);vertical-align:middle}
.pgrid tr:last-child td{border-bottom:0}
.pgrid .gc{font-weight:600;white-space:nowrap}
.pgrid .thpos .thk{display:block;font-weight:400;text-transform:none;letter-spacing:0;
  color:var(--faint);font-size:9px;margin-top:2px}
.pgrid .gbar{width:38%;min-width:150px}
.pgrid .trk{position:relative;display:block;height:16px}
.pgrid .trk .axl{position:absolute;left:8%;right:8%;top:50%;height:2px;transform:translateY(-50%);
  background:var(--rule);border-radius:2px}
.pgrid .trk .tk{position:absolute;top:50%;width:1px;height:7px;transform:translate(-50%,-50%);
  background:var(--rule-soft)}
.pgrid .trk .mk{position:absolute;top:50%;width:11px;height:11px;border-radius:50%;
  transform:translate(-50%,-50%)}
.pgrid .trk .mk.cu{border:1.5px solid var(--bg)}
.pgrid .trk .mk.cu.fav{background:var(--fav)} .pgrid .trk .mk.cu.adv{background:var(--adv)}
.pgrid .trk .mk.cu.neu{background:var(--muted)}
.pgrid .trk .mk.pv{width:9px;height:9px;background:transparent;border:1.5px solid var(--faint);opacity:.75}
.pgrid .get .etq{font-size:12px;color:var(--muted)}
.pgrid .get .ineu{font-size:12px;color:#a9a294}
.pgrid .gdt{white-space:nowrap}
.pgrid .gdt .pd{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:3px;
  border:1px solid var(--faint)}
.pgrid .gdt .pd.on{background:var(--ink);border-color:var(--ink)}
.pgrid .gnt{color:var(--muted);font-size:11.5px;font-style:italic;line-height:1.35}
/* ---------------- fase 2: guia de decision ---------------- */
  color:var(--faint);padding:8px 12px;border-bottom:1px solid var(--rule-soft);background:var(--bg-soft,transparent)}
  text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.t-ok{color:var(--fav);font-weight:600}
.t-warn{color:#8a6d1f;font-weight:600}
.t-adv{color:var(--adv);font-weight:600}
.t-neu{color:var(--muted)}
/* positioning guide */
.pguide{width:100%;border-collapse:collapse;font-size:12.5px}
.pguide th{font:600 9px/1.3 -apple-system,sans-serif;letter-spacing:.05em;text-transform:uppercase;
  color:var(--faint);text-align:left;padding:0 9px 8px;border-bottom:1px solid var(--rule);white-space:nowrap}
.pguide td{padding:10px 9px;border-bottom:1px solid var(--rule-soft);vertical-align:middle}
.pguide tr:last-child td{border-bottom:0}
.pguide .gc{font-weight:600;white-space:nowrap}
.pguide .thpos .thk{display:block;font-weight:400;text-transform:none;letter-spacing:0;
  color:var(--faint);font-size:8.5px;margin-top:2px}
.pguide .gbar{width:22%;min-width:130px}
.pguide .etq2{display:block;font-size:11.5px;color:var(--muted);margin-top:3px}
.pguide .trk{position:relative;display:block;height:14px}
.pguide .trk .axl{position:absolute;left:8%;right:8%;top:50%;height:2px;transform:translateY(-50%);
  background:var(--rule);border-radius:2px}
.pguide .trk .tk{position:absolute;top:50%;width:1px;height:6px;transform:translate(-50%,-50%);
  background:var(--rule-soft)}
.pguide .trk .mk{position:absolute;top:50%;width:10px;height:10px;border-radius:50%;transform:translate(-50%,-50%)}
.pguide .trk .mk.cu{border:1.5px solid var(--bg)}
.pguide .trk .mk.cu.fav{background:var(--fav)} .pguide .trk .mk.cu.adv{background:var(--adv)}
.pguide .trk .mk.cu.neu{background:var(--muted)}
.pguide .trk .mk.pv{width:8px;height:8px;background:transparent;border:1.5px solid var(--faint);opacity:.75}
.pguide .cv{font-size:10.5px;text-transform:uppercase;letter-spacing:.03em}
.pguide .cv.c3{color:var(--fav)} .pguide .cv.c2{color:var(--muted)} .pguide .cv.c1{color:#8a6d1f}
.pguide .ineu{color:#a9a294}
.pguide .hz{font-size:11.5px;white-space:nowrap;color:var(--muted)}
.pguide .tdif{display:block;font-size:10px;color:#8a6d1f;margin-top:3px;white-space:nowrap}
/* `td.fav` y no `.fav`: el marcador de la pista lleva tambien la clase
   `fav` como color, y este min-width lo convertia en una elipse de 150 px. */
.pguide td.fav,.pguide td.evi{font-size:11.5px;color:var(--muted);
  line-height:1.35;min-width:150px}
.pguide .gnota{display:block;font-size:10.5px;font-style:italic;color:var(--faint);margin-top:3px}
/* regimen vs tactico */
.rt{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 6px}
@media(max-width:620px){.rt{grid-template-columns:1fr}}
.rt-b{border:1px solid var(--rule-soft);border-radius:3px;padding:11px 13px}
.rt-b.setup-on{border-color:#c8a94e}
.rt-h{font:600 9px/1.3 -apple-system,sans-serif;letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint);margin-bottom:6px}
.rt-p{font-size:13px;line-height:1.5;margin:0 0 5px}
.rt-s{font-size:11.5px;color:var(--muted);margin:0;line-height:1.45}
.cregi{color:#8a6d1f;text-transform:none;letter-spacing:0;font-weight:400}
/* decision triggers */
.tg{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:720px){.tg{grid-template-columns:1fr}}
.tg-b{border:1px solid var(--rule-soft);border-radius:3px;padding:10px 12px}
.tg-h{font:600 9px/1.3 -apple-system,sans-serif;letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint);margin-bottom:7px}
.tg-confirma .tg-h{color:var(--fav)} .tg-invalida .tg-h{color:var(--adv)}
.tg-tactico .tg-h{color:#8a6d1f}
.tg-l{list-style:none;margin:0;padding:0}
.tg-l li{font-size:12px;line-height:1.5;padding:5px 0;border-bottom:1px solid var(--rule-soft)}
.tg-l li:last-child{border-bottom:0}
.tg-none{color:var(--faint);font-style:italic}
.tg-v{font-weight:600}
.tg-a{color:var(--muted)}
.tg-c{display:block;color:var(--ink)}
.tg-e{display:block;color:var(--muted)}
.tg-m{display:block;font-size:10.5px;color:var(--faint);margin-top:2px}
.tg-m.bad{color:var(--adv)}
/* what changed / mandato */
.wc{margin:0;padding:0 0 0 18px;font-size:13px;line-height:1.55}
.wc li{margin:3px 0}
.mand{width:100%;border-collapse:collapse;font-size:12px}
.mand th{font:600 9px/1.3 -apple-system,sans-serif;letter-spacing:.05em;text-transform:uppercase;
  color:var(--faint);text-align:left;padding:0 9px 7px;border-bottom:1px solid var(--rule)}
.mand td{padding:8px 9px;border-bottom:1px solid var(--rule-soft);color:var(--muted)}
.mand .mc{font-weight:600;color:var(--ink);white-space:nowrap}
.mand tr:last-child td{border-bottom:0}
.clima{font:400 19px/1.4 Georgia,"Times New Roman",serif;margin:0 0 4px}
.clima b{font-weight:700}
.lbl{font:600 10px/1 -apple-system,Segoe UI,sans-serif;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin:20px 0 8px}
.incl{border-top:1px solid var(--rule-soft)}
.lin{padding:8px 0;border-bottom:1px solid var(--rule-soft)}
.lin:last-child{border-bottom:0}
.lin .l1{font-size:14px;line-height:1.4}
.lin .l1 .lc{font-weight:600}
.lin .l1 b{font-weight:600}
.lin .l1 .cv{font-size:11px;text-transform:uppercase;letter-spacing:.03em}
.lin .l1 .cv.c3{color:var(--fav)} .lin .l1 .cv.c2{color:var(--muted)} .lin .l1 .cv.c1{color:#8a6d1f}
.lin .l1 .ineu{color:#a9a294;font-weight:600}
.lin .l2{font-size:12.5px;color:var(--muted);line-height:1.45;margin-top:2px}

/* distribución de convicción (tablero) */
.distrib{margin:8px 0 0}
.dcrow{display:grid;grid-template-columns:60px 1fr 34px;gap:8px;align-items:center;
  font-size:12px;padding:2px 0}
.dcbar{background:var(--band);border-radius:1px;height:9px}
.dcbar i{display:block;height:9px;border-radius:1px}
.dcbar i.c3{background:var(--fav)} .dcbar i.c2{background:var(--neu)}
.dcbar i.c1{background:#c8a94e} .dcbar i.cn{background:#cfc8bc}
.dcn{text-align:right;color:var(--muted)}
.dspark{margin:8px 0 0;font-size:11px;color:var(--faint);display:flex;align-items:flex-end;
  gap:2px;flex-wrap:wrap}
.dspark i{display:inline-block;width:5px;background:var(--fav);border-radius:1px;opacity:.75}

.camb{margin:0;padding:0;list-style:none}
.camb li{position:relative;padding:5px 0 5px 20px;font-size:13.5px;line-height:1.45}
.camb li::before{position:absolute;left:0;top:5px;font-size:11px;font-weight:700}
.camb li.up::before{content:"▲";color:var(--fav)}
.camb li.dn::before{content:"▼";color:var(--adv)}
.camb li.mv::before{content:"→";color:var(--muted)}
.camb li.mas{color:var(--faint);font-style:italic}
.camb li.mas::before{content:""}
.camb b{font-weight:600}
.camb-none{font-size:13.5px;color:var(--muted);margin:0}
.rompe{font-size:13.5px;line-height:1.5;margin:18px 0 0;padding:11px 13px;
  background:#fdf7f6;border:1px solid #e3c9c5;border-radius:3px}
.rompe b{color:var(--adv);font-weight:600}
.afuerte{font-size:13px;line-height:1.5;margin:12px 0 0;padding:10px 13px;
  background:#f6faf7;border:1px solid #cfdcd3;border-radius:3px;color:var(--muted)}
.afuerte b{color:var(--fav);font-weight:600}
.anlist{margin:8px 0 0;padding:0 0 0 18px}
.anlist li{margin:2px 0;color:var(--ink)}
.anlist b{color:var(--ink);font-weight:600}
.adisc{font-size:12.5px;line-height:1.5;margin:6px 0 0;color:var(--muted);font-style:italic}

/* ---------- barra de percentil ---------- */
.bar{position:relative;height:7px;background:var(--band);border-radius:1px;margin:9px 0 3px}
.bar i{position:absolute;top:-3px;width:2px;height:13px;background:var(--ink);border-radius:1px}
.bar i.adv{background:var(--adv)} .bar i.fav{background:var(--fav)}
.bar u{position:absolute;top:0;width:1px;height:7px;background:#cfc8bc}
.scale{display:flex;justify-content:space-between;font-size:10px;color:var(--faint)}

/* ---------- 2. ejes ---------- */
.axes{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.axis{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:15px 17px}
.axis h3{font:600 14px/1.2 -apple-system,Segoe UI,sans-serif;margin:0 0 2px}
.axis .sub2{font-size:12px;color:var(--faint);margin:0 0 13px}
.axis .big{font:400 33px/1 Georgia,serif;display:flex;align-items:baseline;gap:7px}
.axis .big small{font:400 12.5px/1 -apple-system,sans-serif;color:var(--faint)}
.axis .rowk{display:flex;justify-content:space-between;gap:10px;
  font-size:12.5px;padding:5px 0;border-top:1px solid var(--rule-soft)}
.axis .rowk span:first-child{color:var(--muted)}
.axis .pil{font-size:11.5px;color:var(--faint);margin:11px 0 0;line-height:1.45}

/* ---------- 3. de donde sale cada inclinacion ---------- */
.meter{display:inline-flex;gap:2px}
.meter i{width:5px;height:12px;border-radius:1px;background:var(--band)}
.meter i.on{background:var(--neu)}
.deriv{width:100%;border-collapse:collapse;font-size:12.5px}
.deriv th{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.05em;
  text-transform:uppercase;color:var(--faint);text-align:left;padding:0 8px 7px;
  border-bottom:1px solid var(--rule);white-space:nowrap}
.deriv td{padding:9px 8px;border-bottom:1px solid var(--rule-soft);vertical-align:top;
  line-height:1.4}
.deriv tr:last-child td{border-bottom:0}
.deriv td.cl2{font-weight:600;white-space:nowrap}
.deriv td.lm{color:var(--muted);font-size:12px}
.deriv .lim{color:var(--adv)}
.deriv .cv{font-weight:600}
.deriv .cv.c3{color:var(--fav)} .deriv .cv.c2{color:var(--muted)}
.deriv .cv.c1{color:#8a6d1f}
.pos-det{margin:10px 0 0}
.pos-det summary{font-size:12px;color:var(--muted);cursor:pointer;padding:6px 0}
.pos-det table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 0}
.pos-det td{padding:8px 6px;border-bottom:1px solid var(--rule-soft);vertical-align:top}
.pos-det td:nth-child(2),.pos-det td:nth-child(3){text-align:center;white-space:nowrap}
.pos-det tr:last-child td{border-bottom:0}
.pos-det .dh{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.09em;
  text-transform:uppercase;color:var(--faint)}

/* ---------- analogos historicos ---------- */
.warnbox{border:1px solid #ddcda0;background:#fdfaf0;border-radius:3px;padding:12px 15px;
  font-size:12.5px;color:#6d685f;line-height:1.55;margin:0 0 16px}
.warnbox b{color:#8a6d1f}
.ana{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:13px 16px;
  margin:0 0 10px;break-inside:avoid}
.ana-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.ana-f{font:600 15px/1.2 Georgia,serif}
.ana-q{font-size:11.5px;color:var(--faint)}
.ana-q .tagq{display:inline-block;font:600 9px/1.6 -apple-system,sans-serif;letter-spacing:.06em;
  text-transform:uppercase;padding:0 6px;border-radius:2px;border:1px solid var(--rule-soft);margin-left:6px}
.ana-q .tagq.q1{color:var(--fav);border-color:#cfdcd3;background:#f6faf7}
.ana-q .tagq.q2{color:#8a6d1f;border-color:#ddcda0;background:#fdfaf0}
.ana-q .tagq.q3{color:var(--faint)}
.ana-fwd{display:grid;grid-template-columns:repeat(3,1fr);gap:10px 18px;margin:10px 0 0;max-width:380px}
.ana-fwd .h{font:600 9px/1.3 -apple-system,sans-serif;letter-spacing:.08em;text-transform:uppercase;
  color:var(--faint);margin-bottom:2px}
.ana-fwd .val{font-size:15px;font-weight:600}
.ana-fwd .pos{color:var(--fav)} .ana-fwd .neg{color:var(--adv)}
.ana-lab{font-size:10.5px;color:var(--faint)}
.nomatch{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:16px 18px;font-size:13.5px}
.nomatch b{font-weight:600}
/* aviso fuerte: mismo peso visual que "no es un pronostico" */
.warnbox.hard{border-color:#e3c9c5;background:#fdf7f6}
.warnbox.hard b{color:var(--adv)}
.warnbox ul{margin:7px 0 0;padding-left:17px}
.warnbox li{margin:0 0 4px}
.cover{font-size:11.5px;color:var(--faint);line-height:1.55;margin:0 0 14px}
.cover b{color:var(--muted);font-weight:600}
/* en que se parece y en que no */
.simt{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 0}
.simt th{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.05em;text-transform:uppercase;
  color:var(--faint);text-align:left;padding:0 8px 7px;border-bottom:1px solid var(--rule)}
.simt td{padding:8px;border-bottom:1px solid var(--rule-soft);vertical-align:top;line-height:1.4}
.simt tr:last-child td{border-bottom:0}
.simt td.f{font-weight:600;white-space:nowrap}
.simt .ok{color:var(--fav)} .simt .no{color:var(--adv)}
.simt .g{color:var(--faint);font-size:11px}
/* matriz analogo x activo */
.amx{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 0}
.amx th{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.04em;text-transform:uppercase;
  color:var(--faint);text-align:right;padding:0 7px 7px;border-bottom:1px solid var(--rule);white-space:nowrap}
.amx th:first-child{text-align:left}
.amx td{padding:8px 7px;border-bottom:1px solid var(--rule-soft);text-align:right;
  font-weight:600;white-space:nowrap}
.amx td.cl{text-align:left;font-weight:400}
.amx td.cl b{font-weight:600}
.amx .amq{display:block;font-size:10.5px;font-weight:400;color:var(--faint);margin-top:2px}
.amx .dotq{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--neu);
  margin-right:4px;vertical-align:1px}
.amx .dotq.q1{background:var(--fav)} .amx .dotq.q2{background:#c8a94e}
.amx td.pos{color:var(--fav)} .amx td.neg{color:var(--adv)}
.amx td.vol{color:var(--muted);border-left:1px solid var(--rule-soft)}
.amx th:last-child{border-left:1px solid var(--rule-soft)}
.amx tr:last-child td{border-bottom:0}
/* agrupacion por analogo: solo separa entre grupos, no entre horizontes */
.amx td{border-bottom:0}
.amx tr.grp td{border-top:1px solid var(--rule-soft)}
.amx tbody tr:first-child td{border-top:0}
.amx td.cl{vertical-align:top;padding-top:9px}
.amx td.hz{text-align:right;font-weight:400;color:var(--faint);font-size:11px}
/* dispersion visual */
.disp{margin:8px 0 0}
.dscale{position:relative;height:12px;margin:0 120px 3px 104px;font-size:10px;color:var(--faint)}
.dscale .l{position:absolute;left:0}
.dscale .m{position:absolute;left:50%;transform:translateX(-50%)}
.dscale .r{position:absolute;right:0}
.drow{display:grid;grid-template-columns:64px 32px 1fr 120px;align-items:center;gap:0 8px;
  padding:2px 0}
.drow.g0{padding-top:7px}
.drow.gl{padding-bottom:7px;border-bottom:1px solid var(--rule-soft)}
.drow:last-child{border-bottom:0}
.drow.vol{grid-template-columns:64px 32px 1fr;color:var(--muted)}
.dhz{font-size:10px;color:var(--faint);text-align:right}
.dlab{font-weight:600;font-size:12px}
.dbar{position:relative;height:8px;background:var(--band);border-radius:1px}
.dbar .zero{position:absolute;left:50%;top:-2px;width:1px;height:12px;background:#c1b9aa}
.dbar .seg{position:absolute;top:1px;height:6px;background:#cdc6b9;border-radius:1px}
.dbar .mk{position:absolute;top:-2px;width:3px;height:12px;border-radius:1px}
.dbar .mk.pos{background:var(--fav)} .dbar .mk.neg{background:var(--adv)}
.dnum{font-size:12px;text-align:right;white-space:nowrap}
.dnum b.pos{color:var(--fav)} .dnum b.neg{color:var(--adv)}
.dnum .rr{color:var(--faint);font-size:11px}
.promt{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 0}
.promt th{font:600 9.5px/1.3 -apple-system,sans-serif;letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint);text-align:right;padding:0 8px 7px;border-bottom:1px solid var(--rule)}
.promt th:first-child{text-align:left}
.promt td{padding:8px 8px;border-bottom:1px solid var(--rule-soft);text-align:right;
  font-weight:600;white-space:nowrap}
.promt td.cl{text-align:left;font-weight:400}
.promt td.pos{color:var(--fav)} .promt td.neg{color:var(--adv)}
.promt td.vol{color:var(--muted);border-left:1px solid var(--rule-soft)}
.promt th:last-child{border-left:1px solid var(--rule-soft)}
.promt tr:last-child td{border-bottom:0}
.promt .rng{display:block;font-size:10px;font-weight:400;color:var(--faint);margin-top:2px}

/* ---------- guia "como leer" ---------- */
.howto{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:15px 18px;
  margin:0 0 22px}
.howto .ht{font:600 10px/1 -apple-system,sans-serif;letter-spacing:.13em;text-transform:uppercase;
  color:var(--faint);margin:0 0 11px}
.howto dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 12px}
.howto dt{font-weight:600;font-size:12.5px;white-space:nowrap}
.howto dd{margin:0;font-size:12.5px;color:var(--muted);line-height:1.5}
.howto .key{margin:12px 0 0;padding:11px 0 0;border-top:1px solid var(--rule-soft);
  font-size:12px;color:var(--muted);line-height:1.7;list-style:none}
.howto .key b{color:var(--ink);font-weight:600}
.howto .eg{margin:12px 0 0;padding:10px 12px;background:#f6f2ea;border-radius:2px;
  font-size:12.5px;color:var(--muted);line-height:1.5}
.howto .eg b{color:var(--ink)}

/* ---------- 4. tablero ---------- */
.pillar{margin:0 0 26px;break-inside:avoid;page-break-inside:avoid}
.phead{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:2px}
.phead h3{font:600 14.5px/1.3 -apple-system,Segoe UI,sans-serif;margin:0}
.phead .pscore{font-size:12.5px;color:var(--muted);white-space:nowrap}
.phead .pscore b{font-weight:600;color:var(--ink)}
.pdesc{font-size:11.5px;color:var(--faint);margin:5px 0 8px}
.tag{display:inline-block;font:600 9.5px/1.5 -apple-system,sans-serif;letter-spacing:.08em;
  text-transform:uppercase;padding:1px 6px;border-radius:2px;border:1px solid var(--rule);
  color:var(--muted);background:#fff;vertical-align:1px;white-space:nowrap}
.tag.adv{color:var(--adv);border-color:#e3c9c5} .tag.fav{color:var(--fav);border-color:#c9dbcf}

.votes{margin:5px 0 0;display:flex;flex-wrap:wrap;align-items:center;gap:4px 5px}
.vg{font:600 8.5px/1.6 -apple-system,sans-serif;letter-spacing:.08em;text-transform:uppercase;
  color:var(--faint);margin-right:1px}
.vg:not(:first-child){margin-left:6px}
.chip{display:inline-block;font:600 9.5px/1.6 -apple-system,sans-serif;letter-spacing:.02em;
  padding:0 5px;border-radius:2px;border:1px solid var(--rule-soft);
  color:var(--muted);background:#fff;white-space:nowrap}
.chip.up{color:var(--fav);border-color:#cfdcd3;background:#f6faf7}
.chip.dn{color:var(--adv);border-color:#e6cdc9;background:#fcf7f6}

.thead,.row{display:grid;grid-template-columns:1fr 98px 168px 104px;
  gap:10px;align-items:center}
.thead{font:600 9.5px/1 -apple-system,sans-serif;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);padding:8px 0 6px;border-bottom:1px solid var(--rule-soft)}
.thead span:not(:first-child),.row .num{text-align:right}
.row{padding:8px 0;border-bottom:1px solid var(--rule-soft);font-size:13px}
.row:last-child{border-bottom:0}
.row .name{line-height:1.35}
.row .name .src{display:block;font-size:10.5px;color:var(--faint);margin-top:3px}
.row .num{white-space:nowrap}
.row .pcell{display:block;text-align:right}
.row .pwrap{display:flex;align-items:center;gap:8px;justify-content:flex-end;width:100%}
/* extremos del rango de 5 anos, bajo la barra */
.row .pext{display:flex;justify-content:space-between;font-size:9.5px;color:var(--faint);
  margin-top:2px;padding-right:38px}
/* cambio 1m y 3m juntos en una sola columna */
.row .chg{text-align:right}
.row .ch{display:block;white-space:nowrap}
.row .ch i{font-style:normal;color:var(--faint);font-size:9.5px;margin-right:5px}
.row .pcell .mini{position:relative;flex:1;height:5px;background:var(--band);border-radius:1px;
  min-width:52px;max-width:74px}
.row .pcell .mini i{position:absolute;top:-2.5px;width:2px;height:10px;background:var(--neu)}
.row .pcell .mini i.adv{background:var(--adv)} .row .pcell .mini i.fav{background:var(--fav)}
.row .pcell .mini u{position:absolute;top:0;width:1px;height:5px;background:#cfc8bc}
.row .pcell .pv{width:30px;text-align:right;color:var(--muted);font-size:12px}
.row.ext{background:#fff;box-shadow:inset 3px 0 0 var(--neu);padding-left:9px;margin-left:-12px;
  padding-right:3px}
.row.ext.adv{box-shadow:inset 3px 0 0 var(--adv)}
.row.ext.fav{box-shadow:inset 3px 0 0 var(--fav)}
.cap{display:none}
.stale{color:var(--faint);font-size:10.5px}

/* ---------- 5. divergencias ---------- */
.dv{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:13px 15px;
  margin:0 0 11px;break-inside:avoid}
.dv .t{font-size:13.5px;margin:0 0 3px}
.dv .t b{font-weight:600}
.dv .d{font-size:11.5px;color:var(--faint);margin:0}
.dv .gapbar{position:relative;height:6px;background:var(--band);border-radius:1px;margin:10px 0 5px}
.dv .gapbar .seg{position:absolute;top:0;height:6px;background:#cdc6b9}
.dv .gapbar i{position:absolute;top:-3px;width:2px;height:12px}
.dv .gapbar i.lo{background:var(--adv)} .dv .gapbar i.hi{background:var(--fav)}
/* divergencia DENTRO de un pilar */
.dvi{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:13px 15px;
  margin:0 0 11px;break-inside:avoid}
.dvi .p{font:600 9.5px/1.5 -apple-system,sans-serif;letter-spacing:.09em;
  text-transform:uppercase;color:var(--faint);margin:0 0 7px}
.dvi .p .off{color:#8a6d1f;border:1px solid #ddcda0;background:#fdfaf0;border-radius:2px;
  padding:0 5px;margin-left:6px;letter-spacing:.04em}
.dvi .pair{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px}
.dvi .side .w{font-size:12.5px;line-height:1.35}
.dvi .side .v{font-size:12px;color:var(--muted);margin-top:2px}
.dvi .side.hi .w b{color:var(--fav)} .dvi .side.lo .w b{color:var(--adv)}
.dvi .d{font-size:11.5px;color:var(--faint);margin:9px 0 0}
.aligned{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:13px 15px;
  font-size:13.5px}
.aligned p{margin:0 0 6px} .aligned p:last-child{margin:0;color:var(--faint);font-size:11.5px}
h4{font:600 10.5px/1 -apple-system,sans-serif;letter-spacing:.13em;text-transform:uppercase;
  color:var(--faint);margin:24px 0 10px}
.ex{display:grid;grid-template-columns:1fr 92px 62px 128px;gap:10px;font-size:12.5px;
  padding:6px 0;border-bottom:1px solid var(--rule-soft);align-items:baseline}
.ex span:nth-child(2),.ex span:nth-child(3){text-align:right}
.ex .w{color:var(--faint);font-size:11.5px;text-align:right}
.ex.adv strong{color:var(--adv);font-weight:600}
.ex.fav strong{color:var(--fav);font-weight:600}

/* ---------- 6. documentos ---------- */
.ctr{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:13px 15px;
  margin:0 0 10px;break-inside:avoid}
.ctr .k{font:600 9.5px/1.5 -apple-system,sans-serif;letter-spacing:.09em;text-transform:uppercase}
.ctr.comp{box-shadow:inset 3px 0 0 var(--neu)} .ctr.comp .k{color:var(--muted)}
.ctr.res{box-shadow:inset 3px 0 0 var(--adv)} .ctr.res .k{color:var(--adv)}
.ctr .q{font-size:13.5px;margin:6px 0 7px}
.ctr .verd{font-size:12.5px;margin:0 0 7px;padding:7px 10px;background:#f6f2ea;border-radius:2px}
.ctr .n{font-size:11.5px;color:var(--faint);line-height:1.5}
.ctr .n b{color:var(--muted);font-weight:600}
/* titulares (feed estilo MLIV) */
.hl{display:grid;grid-template-columns:76px 1fr;gap:12px;padding:9px 0;
  border-bottom:1px solid var(--rule-soft);align-items:baseline}
.hl:last-of-type{border-bottom:0}
.hl-d{font-size:11.5px;color:var(--faint);font-variant-numeric:tabular-nums}
.hl-t{font-size:13.5px;line-height:1.45}
.hl-s{display:block;font-size:11px;color:var(--faint);margin-top:2px}
.hl-s a{color:var(--muted)}
.doc-item{border:1px solid var(--rule);background:#fff;border-radius:3px;padding:14px 16px;
  margin:0 0 12px;break-inside:avoid}
.doc-h{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
.doc-h b{font-size:13.5px;font-weight:600}
.doc-m{font-size:11.5px;color:var(--faint)}
.age{display:inline-block;font:600 9px/1.6 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;padding:0 5px;border-radius:2px;border:1px solid var(--rule);
  color:var(--muted)}
.age.semana{color:#8a6d1f;border-color:#ddcda0;background:#fdfaf0}
.tesis{font-size:12.5px;color:var(--muted);margin:7px 0 0;line-height:1.5}
.says-h{font:600 9px/1.4 -apple-system,sans-serif;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin:13px 0 5px}
.says-h.infer-h{color:#9a8f6f}
.aporta{font-size:12.5px;margin:9px 0 0;padding:0 0 0 12px;border-left:2px solid var(--fav);
  list-style:none}
.aporta li{margin:0 0 6px}.aporta li:last-child{margin:0}
.says{font-size:12.5px;margin:0;padding:0 0 0 12px;border-left:2px solid var(--rule);
  list-style:none}
.says li{margin:0 0 6px}
.says li:last-child{margin:0}
.says .ref{color:var(--faint);font-size:10.5px}
.infer{font-size:12.5px;font-style:italic;color:var(--muted);margin:0;
  padding:0 0 0 12px;border-left:2px dashed #d5cec1;list-style:none}
.infer li{margin:0 0 6px}
.infer li:last-child{margin:0}
.legend{font-size:11.5px;color:var(--faint);margin:0 0 16px;line-height:1.55}

/* ---------- comprobaciones de la ejecucion ---------- */
.checks{border:1px solid var(--rule);background:#fff;border-radius:3px;
  padding:14px 16px;margin:34px 0 0}
.checks .ct{font:600 10px/1 -apple-system,sans-serif;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin:0 0 4px}
.checks .ci{font-size:11.5px;color:var(--faint);line-height:1.5;margin:0 0 10px}
.chk{display:grid;grid-template-columns:22px 1fr 1.15fr;gap:4px 10px;
  padding:7px 0;border-top:1px solid var(--rule-soft);font-size:12.5px;align-items:baseline}
.chk .s{font-size:11px;text-align:center}
.chk .s.ok{color:#a9a294} .chk .s.aviso{color:#c8a94e} .chk .s.nd{color:var(--faint)}
.chk .l{color:var(--muted)}
.chk .v{color:var(--ink)}
.chk .n{grid-column:3/4;font-size:11px;color:var(--faint);line-height:1.45;margin-top:-2px}

/* ---------- pie ---------- */
footer{border-top:1px solid var(--rule);margin-top:44px;padding-top:16px;
  font-size:11.5px;color:var(--faint);line-height:1.6}
footer h5{font:600 10px/1 -apple-system,sans-serif;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);margin:0 0 7px}
footer ol{margin:0;padding-left:17px} footer li{margin:0 0 5px}

/* ---------- movil ---------- */
@media (max-width:660px){
  /* 26 px por lado se comen el 13 % del ancho útil de un teléfono. */
  .doc{padding:24px 12px 44px}
  h1{font-size:25px}
  .axes{grid-template-columns:1fr}
  .postrow{grid-template-columns:1fr;gap:3px 0;padding:14px 0}
  .postrow .pr{margin-top:2px}
  .score{flex-direction:column;align-items:flex-start;gap:12px}
  .score .who{width:100%}
  .cls{grid-template-columns:1fr;gap:7px}
  .cls .dir{text-align:left}
  .cls .cnt{text-align:left}
  .thead{display:none}
  /* Dos columnas, no cuatro: a 375px las cuatro dejaban la barra de percentil
     en 30px y los numeros partidos. */
  .row{grid-template-columns:1fr 1fr;gap:10px 16px;padding:12px 0}
  .row .name{grid-column:1/-1;font-size:13.5px}
  .row .num{text-align:left}
  .row .pcell{display:block;text-align:left}
  .row .pwrap{justify-content:flex-start;gap:7px}
  .row .pcell .mini{min-width:46px;max-width:none}
  .row .pcell .pv{width:auto;text-align:left}
  .row .pext{padding-right:0}
  .row .chg{text-align:left}
  .row.ext{margin-left:-10px;padding-left:8px}
  .ex{grid-template-columns:1fr 78px;gap:4px 10px}
  .ex span:nth-child(3){text-align:left;color:var(--faint)}
  .ex .w{text-align:left}
  .dvi .pair{grid-template-columns:1fr;gap:9px}
  .chk{grid-template-columns:18px 1fr;gap:2px 8px}
  .chk .v{grid-column:2/3}
  .chk .n{grid-column:2/3}
  .dscale{margin:0 84px 3px 78px}
  .drow{grid-template-columns:44px 26px 1fr 84px}
  .drow.vol{grid-template-columns:44px 26px 1fr}
}

/* ---------- causa comun (nota bajo la tabla de inclinaciones) ---------- */
.causa{font-size:12.5px;line-height:1.5;margin:10px 0 0;padding:9px 12px;
  background:#f6f2ea;border-radius:3px;color:var(--muted)}
.causa b{color:var(--ink);font-weight:600}

/* ---------- 2 · que cambio desde el anterior ---------- */
.chg-none{border:1px solid var(--rule);background:#fff;border-radius:3px;
  padding:13px 15px;font-size:13.5px;color:var(--muted)}
.chg-list{margin:0;padding:0;list-style:none}
.chg-list li{position:relative;padding:9px 0 9px 22px;border-bottom:1px solid var(--rule-soft);
  font-size:13.5px;line-height:1.5}
.chg-list li:last-child{border-bottom:0}
.chg-list li::before{position:absolute;left:0;top:9px;font-size:11px;font-weight:700}
.chg-list li.up::before{content:"▲";color:var(--fav)}
.chg-list li.dn::before{content:"▼";color:var(--adv)}
.chg-list li.mv::before{content:"→";color:var(--muted)}
.chg-list li.nw::before{content:"＋";color:var(--muted)}
.chg-list li.gn::before{content:"·";color:var(--faint)}
.chg-list b{font-weight:600}
.chg-de{color:var(--faint)}

/* ---------- tablero de auditoria (plegable) ---------- */
.tablero{border:1px solid var(--rule);border-radius:4px;background:#fff;margin:34px 0 0}
.tablero>summary{cursor:pointer;list-style:none;padding:15px 18px;
  font:600 12px/1.35 -apple-system,Segoe UI,sans-serif;color:var(--ink)}
.tablero>summary::-webkit-details-marker{display:none}
.tablero>summary .tt{display:block;font:600 10.5px/1 -apple-system,sans-serif;
  letter-spacing:.15em;text-transform:uppercase;color:var(--faint);margin-bottom:5px}
.tablero>summary .th{font-size:13.5px;font-weight:400;color:var(--muted)}
.tablero>summary::after{content:"▸  desplegar";float:right;font-weight:400;
  color:var(--faint);font-size:11.5px;letter-spacing:.02em}
.tablero[open]>summary::after{content:"▾  plegar"}
.tablero[open]>summary{border-bottom:1px solid var(--rule)}
.tablero .tab-in{padding:8px 18px 20px}
/* colapso explicito: no dependemos del estilo de agente de usuario, que varia
   entre navegadores y clientes de correo. En impresion se revierte (mas abajo). */
.tablero:not([open])>.tab-in{display:none}
.tab-sub{font:600 10.5px/1 -apple-system,Segoe UI,sans-serif;letter-spacing:.15em;
  text-transform:uppercase;color:var(--faint);border-bottom:1px solid var(--rule);
  padding:22px 0 7px;margin:0 0 16px}
.tab-sub:first-child{padding-top:6px}
.metod{margin:0;padding-left:18px;font-size:12.5px;color:var(--muted);line-height:1.6}
.metod li{margin:0 0 6px} .metod b{color:var(--ink);font-weight:600}
.tablero .checks{margin-top:8px}

/* ---------- impresion: el tablero SIEMPRE expandido ---------- */
@media print{
  body{background:#fff;font-size:10.5pt}
  .doc{max-width:none;padding:0}
  .axis,.dv,.aligned,.ctr,.doc-item,.score,.row.ext{background:#fff}
  section{page-break-inside:auto}
  h2{page-break-after:avoid}
  a{text-decoration:none;color:inherit}
  @page{margin:16mm 14mm}
  /* details plegado oculta a sus hijos; en impresion se fuerzan visibles */
  .tablero>*{display:block !important}
  .tablero>summary::after{content:"" !important}
  details.pos-det>*{display:block !important}
}

/* =====================================================================
   QUINTA PASADA — el HTML como espacio de trabajo
   Seis secciones, navegacion fija y divulgacion por capas. Sigue siendo
   tipografia y reglas finas: ni tarjetas de colores ni gauges.
   ===================================================================== */
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0,0,0,0);white-space:nowrap;border:0}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
/* --- navegacion --- */
/* En móvil la barra lateral no se dibuja --su índice lo sustituye el
   desplegable-- pero el conmutador de vista SÍ: es un control, no un índice. */
.nv{display:block;position:static;width:auto;height:auto;padding:0;border:0;
  background:none}
.nv > *:not(.vw){display:none}
.nv .vw{margin:16px 0 0}
.nv-m{margin:14px 0 6px;display:flex;align-items:center;gap:8px}
.nv-m label{font:600 10px/1 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  color:var(--faint)}
.nv-m select{font:inherit;font-size:13px;padding:5px 7px;border:1px solid var(--rule);
  background:#fff;color:var(--ink);border-radius:2px}
@media (min-width:1100px){
  .doc{max-width:none;padding-left:0}
  .nv{display:block;position:fixed;top:0;left:0;width:196px;height:100vh;
    padding:22px 16px;border-right:1px solid var(--rule);background:var(--bg);
    overflow-y:auto;z-index:20}
  /* Misma especificidad que la regla móvil y más abajo en la hoja: con
     `.nv > *` a secas, `:not(.vw)` pesaba más y el índice no volvía. */
  .nv > *:not(.vw){display:block}
  .nv .vw{margin:0 0 16px;width:100%}
  .nv .vw-b{flex:1;padding:6px 4px;font-size:9.5px}
  .nv-m{display:none}
  .cuerpo,header,footer{max-width:940px;margin-left:236px;margin-right:auto}
  .nv-d{font:600 9.5px/1.2 var(--sans);letter-spacing:.09em;color:var(--faint)}
  .nv-p{font:700 17px/1.15 var(--sans);letter-spacing:-.01em;margin-top:5px}
  .nv-s{font:400 11px/1.3 var(--sans);color:var(--muted);margin-bottom:17px}
  .nv-g{margin-bottom:13px}
  .nv-t{display:block;font:600 8.5px/1.2 var(--sans);letter-spacing:.09em;
    text-transform:uppercase;color:var(--faint);margin-bottom:4px}
  .nv a{display:block;font:400 12.5px/1.6 var(--sans);color:var(--muted);
    text-decoration:none;padding:1px 0 1px 8px;border-left:2px solid transparent}
  .nv a:hover{color:var(--ink)}
  .nv a.on{color:var(--ink);font-weight:600;border-left-color:var(--ink)}
}
/* --- secciones --- */
.sx{padding:26px 0 8px;border-top:1px solid var(--rule);scroll-margin-top:18px}
.sx:first-of-type{border-top:0;padding-top:10px}
.sx-h{font:600 12px/1.2 var(--sans);letter-spacing:.11em;text-transform:uppercase;
  color:var(--ink);margin:0 0 14px;padding:0;border:0;display:flex;
  align-items:baseline;gap:9px}
.sx-n{font-size:10px;color:var(--faint);letter-spacing:.06em}
.sx-s{font:600 10px/1.2 var(--sans);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin:20px 0 7px;padding-bottom:3px;
  border-bottom:1px solid var(--rule)}
details.mas{margin:9px 0 4px;border-top:1px solid var(--rule)}
details.mas>summary{cursor:pointer;list-style:none;padding:7px 0;
  font:600 10.5px/1.2 var(--sans);letter-spacing:.05em;color:var(--muted)}
details.mas>summary::-webkit-details-marker{display:none}
details.mas>summary::before{content:"▸ ";color:var(--faint)}
details.mas[open]>summary::before{content:"▾ "}
details.mas>summary:hover{color:var(--ink)}
/* --- cockpit --- */
.cockpit{display:grid;grid-template-columns:1.05fr .95fr;gap:28px;align-items:start}
.ck-post{font:700 40px/1.02 var(--sans);letter-spacing:-.02em}
.ck-sub{font:400 15px/1.4 var(--sans);color:var(--muted);margin-top:5px}
.ck-regs{display:flex;gap:20px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  padding:6px 0;margin:11px 0}
.ck-regs b{font-weight:600;color:var(--ink)}
/* SEMANTIC-PASS 31 · los cuatro calificadores, cada uno con su nombre. */
.ck-q{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:9px 0 0;
  font-size:13px;align-items:baseline}
.ck-qk{font:600 9px/1.6 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  color:var(--faint)}
.ck-qv{color:var(--ink)}
.ck-res{display:block;font-size:11.5px;color:var(--muted);line-height:1.45;
  margin-top:2px}
/* SEMANTIC-PASS 31 · qué empuja y qué frena, por su nombre. */
.pq{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:11px 0 0;
  padding-top:9px;border-top:1px solid var(--rule);font-size:12.5px}
.pq-t{grid-column:1/3;font:600 9px/1.4 var(--sans);letter-spacing:.07em;
  text-transform:uppercase;color:var(--faint)}
.pq-k{font:600 9px/1.6 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  white-space:nowrap}
.pq-a{color:var(--fav)} .pq-f{color:var(--adv)}
.pq-v{color:var(--ink);line-height:1.45}
/* SPEC-7P 1: la transicion de regimen a medio confirmar, dicha donde se ve
   el par etiqueta+percentil. */
.ck-regs .trn{display:block;font-size:11px;color:var(--warn,#8a6d1f);
  line-height:1.35;margin-top:2px;font-weight:400}
.ck-take{border-left:3px solid var(--ink);padding:7px 0 7px 12px;margin:0 0 11px}
.ck-take .k,.ck-cam .k{display:block;font:600 9px/1.2 var(--sans);letter-spacing:.07em;
  text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.ck-take p{margin:0;font-size:14.5px;line-height:1.5}
.ck-cam ul{margin:0;padding:0;list-style:none}
.ck-cam li{font-size:12.5px;line-height:1.5;padding:1px 0}
.ck-cam li.nada{color:var(--muted)}
.ck-cam .fl{color:var(--faint);margin-right:5px}
.ck-cam a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--rule)}
.ck-t{border:1px solid var(--rule);padding:8px 11px;margin-top:9px}
.ck-t .k{display:block;font:600 9px/1.2 var(--sans);letter-spacing:.07em;
  text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.ck-t .v{font-size:13px;line-height:1.45}
.ck-t .vs{color:var(--faint);margin:0 7px}
.ck-t .dur,.ck-t .porq{color:var(--faint);font-style:normal}
.ck-t a.ev{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--rule)}
/* --- fuerzas --- */
.fz{margin:0 0 4px}
.fz-h{font:600 9px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  color:var(--faint);margin-bottom:5px}
/* Rejilla y no SVG: el texto mide lo que mide y la columna se ajusta sola.
   Con las coordenadas fijas del SVG, «Cond. monetarias» se salia de su carril
   y se imprimia encima de la nota. */
.fz-g{display:grid;grid-template-columns:auto auto minmax(80px,1fr) auto;
  gap:6px 10px;align-items:center}
.fz-r{display:contents}
.fz-l{font:400 11.5px/1.3 var(--sans);color:var(--ink)}
.fz-v{font:600 11px/1.3 var(--sans);color:var(--muted);text-align:right;
  font-variant-numeric:tabular-nums}
.fz-b{position:relative;height:9px;min-width:60px}
.fz-b::before{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;
  width:1px;background:var(--rule)}
.fz-b i{position:absolute;top:0;height:9px;opacity:.82}
.fz-b i.fav{background:var(--fav)}
.fz-b i.adv{background:var(--adv)}
.fz-b i.neu{background:var(--neu)}
/* §8 · el significado, a la derecha: «85» no dice si es bueno. */
.fz-s{font:600 9px/1.3 var(--sans);color:var(--muted);letter-spacing:.03em;
  white-space:nowrap}
.fz-cap{font:400 9.5px/1.45 var(--sans);color:var(--faint);margin:8px 0 0}
/* En pantalla estrecha la lectura se va a su propia línea antes que apretar
   la barra hasta que deje de decir nada. */
@media (max-width: 560px){
  .fz-g{grid-template-columns:auto auto minmax(70px,1fr)}
  .fz-s{grid-column:1 / -1;margin:-2px 0 4px}
}
/* --- bloques de interpretacion --- */
.interp{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}
.ib{border-top:2px solid var(--ink);padding-top:7px}
.ib-h{font:600 9.5px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  display:flex;justify-content:space-between;gap:6px}
.ib-e{color:var(--muted);font-weight:400;letter-spacing:0;text-transform:none}
.ib p{margin:5px 0 4px;font-size:12.5px;line-height:1.45}
.ib-n{font-size:11.5px;color:var(--muted)}
.ib-n b{color:var(--ink);font-size:14px}
details.narr{margin-top:12px}
/* --- matriz de posicionamiento, accionable (punto 5) ---
   Una rejilla, no una tabla: cada fila es un <details> que se abre en el
   detalle del tema. Las columnas se declaran una vez y la cabecera y las filas
   comparten la misma plantilla, para que sigan alineadas al desplegar. */
.mx{margin-bottom:6px}
.mx-h,.mxr>summary{display:grid;align-items:center;gap:10px;
  grid-template-columns:minmax(120px,1.1fr) minmax(64px,auto) minmax(110px,2fr)
                        minmax(64px,auto) minmax(84px,auto)}
.mx-h{font:600 9px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  color:var(--faint);padding:0 4px 5px;border-bottom:1px solid var(--rule)}
.mxr{border-bottom:1px solid var(--rule)}
/* §17 · núcleo y overlay, separados: el núcleo decide qué se tiene, el overlay
   cómo se tiene. Juntos, la vista de divisa se lee como una asignación. */
.mx-gr{font:600 9px/1.4 var(--sans);letter-spacing:.08em;text-transform:uppercase;
  color:var(--faint);margin:14px 0 3px;padding:0 4px}
.mx-gr:first-child{margin-top:6px}
.mx-gr em{font-style:normal;text-transform:none;letter-spacing:0;font-weight:400}
.mxr>summary{padding:7px 4px;font-size:12px;cursor:pointer;list-style:none}
.mxr>summary::-webkit-details-marker{display:none}
.mxr>summary:hover{background:var(--hov,rgba(0,0,0,.02))}
.mxr>summary:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.mx-n{font-weight:600}
.mx-n::after{content:"›";color:var(--faint);margin-left:6px;
  display:inline-block;transition:transform .12s}
.mxr[open] .mx-n::after{transform:rotate(90deg)}
.mx-i,.mx-d{color:var(--faint);font-size:10.5px}
.mx-i{text-align:right}
.mx-i.on,.mx-d.on{color:var(--ink);font-weight:600}
.mx-b{position:relative;height:18px;min-width:110px}
.mx-ax{position:absolute;left:0;right:0;top:50%;height:1px;background:var(--rule)}
.mx-p{position:absolute;top:50%;width:9px;height:9px;border-radius:50%;
  transform:translate(-50%,-50%)}
.mx-p.fav{background:var(--fav)} .mx-p.adv{background:var(--adv)}
.mx-p.neu{background:var(--neu)}
.mx-s{font-weight:600;text-align:right;font-size:11.5px}
/* En escritorio la convicción ya vive en el detalle: la tarjeta es móvil. */
.mx-cv{display:none}
@media (max-width: 720px){ .mx-cv{display:block} }
/* el detalle de tema: UN componente, reutilizable (punto 6) */
.td{display:grid;grid-template-columns:minmax(96px,auto) 1fr;gap:4px 14px;
  padding:4px 4px 14px 4px;font-size:12px}
.td-k{font:600 9px/1.5 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint)}
.td-v{line-height:1.45}
.drvs{display:block;font-size:10.5px;color:var(--faint);margin-top:3px}
a.drv{color:var(--muted);border-bottom:1px dotted var(--rule);text-decoration:none}
a.drv:hover,a.drv:focus{color:var(--ink);border-bottom-color:var(--ink)}
.tmark{font:600 8.5px/1.4 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  padding:1px 5px;border-radius:2px;white-space:nowrap}
.tm-cand{color:#8a6d1f;border:1px solid #d9c98f;background:#fdf8e9}
.ck-regs .tmark{margin-left:7px}
/* 8 · el regimen en tres renglones: confirmado, candidato y cuanto le
   falta. En una linea corrida los tres se leian como uno solo. */
.rg{display:block}
.rg-l{display:block;font-weight:400}
.rg-c{color:var(--warn,#8a6d1f)}
.rg-n{font-size:11px;color:var(--muted)}
.rg-r{display:block;font-size:11px;line-height:1.5;color:var(--muted);
  margin-top:5px;padding-left:10px;border-left:2px solid var(--rule);
  max-width:52ch}
.ck-cam-t{float:right;font-size:10.5px;color:var(--muted)}
.ck-cam .mas-cam a{color:var(--muted);font-size:11px}
/* registro de cambios por categoria (punto 11) */
.cr{display:grid;gap:10px;margin:8px 0 4px}
.cr-g{display:grid;grid-template-columns:minmax(120px,auto) 1fr;gap:4px 14px}
.cr-k{font:600 9px/1.7 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint)}
.cr-l{margin:0;padding-left:15px;font-size:12px;line-height:1.6}
.cr-l a{color:var(--ink)}
/* ============== CROSS-ASSET TAPE (SEMANTIC-PASS 13-21, 38-39) =============
   Small multiples con el mismo eje de tiempo. Gráficos de research: una línea,
   una referencia en 100 y la banda del modelo debajo. Sin degradados, sin
   sombras, sin iconos. */
.tp{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 22px;
  margin:10px 0 4px}
.tp-p{margin:0}
.tp-h{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin-bottom:3px}
.tp-t{font:600 12.5px var(--sans)}
.tp-s{font-size:10px;color:var(--faint)}
.tp-n{font-size:10.5px;color:var(--muted);margin-left:auto}
.tp-n+.tp-n{margin-left:0}
.tp-n b{color:var(--ink);font-weight:600}
.tp-l{fill:none;stroke:var(--ink);stroke-width:1.2}
.tp-100{stroke:var(--rule);stroke-dasharray:2 3}
/* SEMANTIC-PASS 12 · que mide cada fuerza, en la capa PM */
.pc-d{margin:6px 0 10px}
.pc-hd,.pc-f{display:grid;grid-template-columns:1.1fr 1.6fr .9fr 1.8fr;gap:4px 12px}
.pc-hd{font:600 8.5px/1.5 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint);padding-bottom:4px;border-bottom:1px solid var(--rule)}
.pc-f{padding:7px 0;border-bottom:1px solid var(--rule-soft);font-size:11.5px;
  line-height:1.4}
.pc-f:last-child{border-bottom:0}
.pc-n{font-weight:600;color:var(--ink)}
.pc-q,.pc-i{color:var(--muted)}
.pc-h b{font-size:13px}
.pc-h .f-fav{color:var(--fav);font-weight:600}
.pc-h .f-adv{color:var(--adv);font-weight:600}
.pc-h .f-neu{color:var(--muted)}
.pc-ctx{display:block;font-weight:400;font-size:10px;color:var(--faint)}
@media (max-width: 720px){
  .pc-hd{display:none}
  .pc-f{grid-template-columns:1fr;gap:2px}
  .pc-n{font-size:12.5px}
  .pc-q::before{content:"Qué mide: ";color:var(--faint)}
  .pc-i::before{content:"Por qué importa: ";color:var(--faint)}
}
.tp-q{stroke:var(--rule);stroke-width:.5;opacity:.6}
/* El eje es HTML, no <text> dentro del SVG: ahi compartia caja con la banda y
   la pisaba en cuanto la fuente del sistema renderizaba algo mas alto de lo
   previsto --como pasa en Safari--. Fuera del dibujo, mide lo que mide. */
.tp-ax{display:flex;justify-content:space-between;font-size:8.5px;
  color:var(--faint);margin:2px 0 0;line-height:1.3}
.tp-bp{fill:var(--fav);opacity:.75} .tp-bd{fill:var(--adv);opacity:.75}
.tp-b0{fill:var(--neu);opacity:.55}
.tp-leg{font-size:10.5px;color:var(--muted);line-height:1.6;margin:2px 0 0}
.tp-k{display:inline-block;width:15px;height:8px;margin-right:2px;
  vertical-align:-1px}
.tp-k.tp-bp{background:var(--fav)} .tp-k.tp-bd{background:var(--adv)}
.tp-k.tp-b0{background:var(--neu)}
.tp-nd{font-size:11px;color:var(--adv);border:1px dashed var(--rule);
  padding:9px;margin:0}
.tp-nd-t{font:400 8px var(--sans);fill:var(--faint)}
.tp-av{font-size:10px;color:var(--muted);margin:3px 0 0;line-height:1.4}
/* El grid es del bloque y las filas son `display:contents`: asi las dos
   columnas se comparten --los valores quedan alineados entre filas-- y la del
   rotulo la dimensiona el texto mas largo. Con un ancho fijo de 160 px, «Sin
   movimiento apreciable» media 182 y se imprimia encima del valor. */
.tp-sum{display:grid;grid-template-columns:max-content 1fr;gap:3px 14px;
  margin:8px 0 12px;padding:9px 0;border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule);font-size:12px}
.tp-r{display:contents}
@media (max-width: 720px){
  .tp-sum{grid-template-columns:1fr;gap:0}
  .tp-rv{margin-bottom:5px}
}
.tp-rk{font:600 9px/1.6 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint);white-space:nowrap}
.tp-rv{color:var(--ink)}
/* §37 · en móvil, apilados a ancho completo. Nunca siete líneas en un eje. */
@media (max-width: 720px){ .tp{grid-template-columns:1fr;gap:14px} }
/* D2 c · el hallazgo sobre voces independientes: una conclusión, no una nota */
.hallazgo{border-left:3px solid var(--warn,#8a6d1f);padding:8px 0 8px 12px;
  margin:12px 0 0}
.hallazgo .k{display:block;font:600 9px/1.2 var(--sans);letter-spacing:.07em;
  text-transform:uppercase;color:var(--warn,#8a6d1f);margin-bottom:3px}
.hallazgo p{margin:0;font-size:13px;line-height:1.5}
/* D2 a · las tres escalas, una vez, al cerrar la primera vista */
.escalas{font-size:11px;line-height:1.6;color:var(--muted);margin:16px 0 0;
  border-top:1px solid var(--rule);padding-top:9px}
.escalas b{color:var(--ink);font-weight:600}

/* ===================== VISTA PM / VISTA COMPLETA (19-21, 33) ==============
   UN solo documento. La vista no duplica DOM ni recorta datos: pone un
   atributo en <html> y el CSS decide que se muestra. Al volver a la completa
   esta todo donde estaba, porque nunca se fue. */
.vw{display:flex;gap:0;margin:0 0 14px;border:1px solid var(--rule);
  border-radius:3px;overflow:hidden;width:fit-content}
.vw-b{font:600 10.5px/1 var(--sans);letter-spacing:.04em;padding:7px 12px;
  background:transparent;border:0;color:var(--muted);cursor:pointer}
.vw-b+.vw-b{border-left:1px solid var(--rule)}
.vw-b[aria-pressed="true"]{background:var(--ink);color:var(--bg,#fff)}
.vw-b:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
html[data-view="pm"] .solo-full{display:none !important}
/* El aviso de que hay mas debajo: en vista PM, al final del cuerpo. */
.vw-mas{display:none;margin:18px 0 0;padding:11px 13px;border:1px dashed var(--rule);
  font-size:12px;color:var(--muted)}
html[data-view="pm"] .vw-mas{display:block}
.vw-mas button{font:inherit;color:var(--ink);background:none;border:0;padding:0;
  text-decoration:underline;cursor:pointer}

/* ===================== MOVIL (25-27) =====================================
   La vista PM en movil reordena: primero la respuesta, despues la evidencia.
   No se oculta nada que no estuviera ya plegado en escritorio. */
@media (max-width: 720px) {
  html[data-view="pm"] .cockpit{display:flex;flex-direction:column}
  html[data-view="pm"] .ck-l{order:1} html[data-view="pm"] .ck-r{order:2}
  /* 26 · el posicionamiento se lee como tarjetas: el nombre y el sesgo arriba,
     el carril debajo a lo ancho. Los drivers ya viven dentro del desplegable. */
  .mx-h{display:none}
  .mxr>summary{grid-template-columns:1fr auto;gap:4px 10px;padding:9px 4px}
  .mxr>summary .mx-i{grid-row:2;grid-column:1;text-align:left}
  .mxr>summary .mx-b{grid-row:3;grid-column:1/3;min-width:0}
  .mxr>summary .mx-d{grid-row:2;grid-column:2;text-align:right}
  .mxr>summary .mx-s{grid-row:1;grid-column:2}
  /* 26 · la tarjeta dice sesgo, convicción y timing sin desplegar. */
  .mxr>summary .mx-cv{grid-row:4;grid-column:1/3;font-size:10.5px;
    color:var(--muted)}
  .td{grid-template-columns:1fr;gap:1px 0}
  .td-k{margin-top:7px}
}
.hm-c{display:none;gap:0;margin:0 0 7px;border:1px solid var(--rule);
  border-radius:3px;overflow:hidden;width:fit-content}
.hm-b{font:600 10px/1 var(--sans);padding:6px 11px;background:transparent;
  border:0;color:var(--muted);cursor:pointer}
.hm-b+.hm-b{border-left:1px solid var(--rule)}
.hm-b[aria-pressed="true"]{background:var(--ink);color:var(--bg,#fff)}
.hm-b:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.hm-w[data-meses="6"] .hm [data-i]:not([data-i="0"]):not([data-i="1"]):not([data-i="2"]):not([data-i="3"]):not([data-i="4"]):not([data-i="5"]){display:none}
/* «doce meses» son doce: la columna mas antigua es el punto de anclaje de
   la serie, no un mes mas. */
.hm-w[data-meses="12"] .hm [data-i="12"]{display:none}
/* 27 · el control solo aparece donde hace falta elegir: en movil. */
@media (max-width: 720px){ .hm-c{display:flex} }
.hm td[tabindex]:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.hm-say{font-size:11.5px;color:var(--muted);margin:5px 0 0;min-height:1.3em}
/* dentro del detalle, cada matiz en su renglón: si no, el timing, la marca
   y la nota del general salen pegados en una sola línea. */
.td-v .tdif{display:block;margin-top:3px}
/* --- proximidad --- */
.px{margin:14px 0 6px}
.px-h{font:600 9px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  color:var(--faint);margin-bottom:5px}
.px-g{display:grid;grid-template-columns:max-content minmax(70px,1fr) max-content;
  gap:7px 12px;align-items:center;margin:2px 0 6px}
.px-r{display:contents}
.px-l{font:400 11px/1.3 var(--sans);color:var(--ink)}
.px-b{position:relative;height:9px;background:var(--rule-soft,#eee9e0)}
.px-b i{position:absolute;left:0;top:0;height:9px;opacity:.8}
.px-b i.fav{background:var(--fav)} .px-b i.adv{background:var(--adv)}
.px-b i.warn{background:var(--warn,#8a6d1f)} .px-b i.neu{background:var(--neu)}
.px-v{font:400 10px/1.3 var(--sans);color:var(--muted);white-space:nowrap}
/* --- heatmap --- */
.hm-w{overflow-x:auto}
table.hm{border-collapse:collapse;font-size:11px}
.hm th{font:600 9px var(--sans);color:var(--faint);padding:2px 4px;
  text-align:center;font-weight:600;border:0}
.hm th[scope=row]{text-align:left;white-space:nowrap;padding-right:9px;
  color:var(--ink);font-size:11px}
.hm td{width:26px;height:19px;border:1px solid #fff;text-align:center}
.hm-f{background:var(--fav)} .hm-a{background:var(--adv)} .hm-n{background:var(--neu)}
.hm-x{background:#f2ede4;color:var(--faint)}
.hm td.k1{opacity:.34} .hm td.k2{opacity:.62} .hm td.k3{opacity:1}
.hm td.k0{opacity:.22}
/* --- linea de regimen --- */
.tl-b{display:flex;height:15px;border:1px solid var(--rule)}
.tl-b span{display:block}
.tl-f{background:var(--fav);opacity:.75} .tl-a{background:var(--adv);opacity:.75}
.tl-n{background:var(--neu);opacity:.55}
.tl-x{font-size:11.5px;color:var(--muted);margin:6px 0 0}
.tl-x em{color:var(--faint);font-style:normal}
/* --- QA --- */
.qa-s{border:1px solid var(--rule);border-left:3px solid var(--neu);padding:10px 13px}
.qa-s.qa-o{border-left-color:var(--fav)} .qa-s.qa-w{border-left-color:var(--warn)}
.qa-s.qa-e{border-left-color:var(--adv)}
.qa-n-e b{color:var(--adv)}
.qa-e{font:600 14px/1.2 var(--sans)}
.qa-c{display:flex;gap:17px;font-size:12px;color:var(--muted);margin-top:4px}
.qa-c b{color:var(--ink);font-size:14px}
.qa-d{margin-top:7px}
.qa-d>summary{cursor:pointer;font:600 10.5px var(--sans);color:var(--muted)}
.qa-l{margin:6px 0 0;padding:0;list-style:none;font-size:12px;line-height:1.5}
.qa-l li{display:grid;grid-template-columns:52px 1fr auto;gap:4px 9px;
  align-items:baseline;padding:5px 0;border-top:1px solid var(--rule)}
.qa-l a{color:var(--ink)}
.qa-v{color:var(--muted);font-size:11px;text-align:right}
/* la accion, en su propio renglon bajo el nombre: un aviso que no dice que
   hacer con el solo consigue que se deje de leer la seccion (punto 17). */
.qa-q{grid-column:2/4;color:var(--muted);font-size:11px;line-height:1.45}
.qa-t{font-weight:600}
.qa-ver{color:var(--ink);font-size:11px;white-space:nowrap}
.qa-b{font:600 8.5px/1.5 var(--sans);letter-spacing:.07em;text-align:center;
  border-radius:2px;padding:1px 0}
.qa-b-error{color:#fff;background:var(--adv)}
.qa-b-aviso{color:#6b5410;background:#f6ecc9}
.qa-b-info{color:var(--muted);border:1px solid var(--rule)}
/* --- filtro --- */
.flt{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:4px 0 12px}
.flt input,.flt select,.flt button{font:inherit;font-size:12.5px;padding:5px 8px;
  border:1px solid var(--rule);background:#fff;color:var(--ink);border-radius:2px}
.flt input{min-width:180px}
.flt button{cursor:pointer;color:var(--muted)}
.flt button:hover{color:var(--ink)}
.flt-n{font-size:11.5px;color:var(--faint)}
.pillar.oculto,.row.oculto{display:none}
/* --- responsive --- */
@media (max-width:900px){
  .cockpit{grid-template-columns:1fr;gap:18px}
  .interp{grid-template-columns:1fr;gap:14px}
  .ck-post{font-size:32px}
}
@media (max-width:640px){
  .ck-post{font-size:28px}
  .mx-i,.mx-d{display:none}
  .hm td{width:20px;height:17px}
}

/* --- pilares plegados (5P 25) --- */
details.pillar{border:1px solid var(--rule);margin-bottom:9px;background:#fff}
details.pillar>summary{cursor:pointer;list-style:none;padding:10px 13px;
  display:grid;grid-template-columns:1.6fr auto auto;gap:4px 12px;align-items:baseline}
details.pillar>summary::-webkit-details-marker{display:none}
details.pillar>summary::after{content:"B8";grid-column:3;grid-row:1;
  color:var(--faint);justify-self:end}
details.pillar[open]>summary::after{content:"BE"}
.ph-n{font:600 14px/1.25 var(--sans);grid-column:1}
.ph-s{grid-column:2;white-space:nowrap;font-size:13px}
.ph-s b{font-size:17px}
.ph-d{grid-column:2;font-size:11px;color:var(--muted);white-space:nowrap}
.ph-v{grid-column:1;font-size:11px;color:var(--muted)}
.ph-l{grid-column:1/-1;font-size:11px;color:var(--faint)}
details.pillar .pdesc,details.pillar .thead,details.pillar .row{padding-left:13px;
  padding-right:13px}
@media (max-width:640px){
  details.pillar>summary{grid-template-columns:1fr auto}
  .ph-d,.ph-v,.ph-l{grid-column:1/-1}
}
"""

# JS minimo, como CONSTANTE: dentro de la f-string de la plantilla sus llaves
# se leerian como campos de sustitucion.
JS = r'''<script>
/* ============ VISTA PM / COMPLETA, enlaces compartibles y anclas ==========
   Puntos 19-24 y 32-33. Sin framework y sin duplicar DOM: la vista es un
   atributo en <html>. Tres fuentes, en este orden de prioridad:
     1 · ?view=pm|full en la URL, que es lo que hace el enlace compartible
     2 · lo que el lector eligio la ultima vez (localStorage)
     3 · VISTA PM, que es el valor por defecto
   Si localStorage esta bloqueado, el paso 2 se cae solo y queda el 3: el
   documento tiene que abrirse igual en una ventana privada. */
(function () {
  var CLAVE = 'mg-vista', root = document.documentElement;
  function leer() {
    try { return localStorage.getItem(CLAVE); } catch (e) { return null; }
  }
  function guardar(v) {
    try { localStorage.setItem(CLAVE, v); } catch (e) { /* bloqueado: da igual */ }
  }
  function deUrl() {
    try {
      var m = /[?&]view=(pm|full)/.exec(location.search);
      return m ? m[1] : null;
    } catch (e) { return null; }
  }
  function pinta(v) {
    root.setAttribute('data-view', v);
    var bs = document.querySelectorAll('.vw-b');
    for (var i = 0; i < bs.length; i++) {
      bs[i].setAttribute('aria-pressed',
        bs[i].getAttribute('data-view') === v ? 'true' : 'false');
    }
  }
  function pon(v, recordar) {
    pinta(v);
    if (recordar) {
      guardar(v);
      try {
        var u = new URL(location.href);
        u.searchParams.set('view', v);
        history.replaceState(null, '', u.toString());
      } catch (e) { /* file:// sin URL API: no pasa nada */ }
    }
  }
  /* `abrir` se expone para poder comprobar el comportamiento de las anclas
     sin depender de que el entorno permita cambiar el hash. */
  window.mgVista = { pon: pon, abrir: abrirDestino,
    actual: function () { return root.getAttribute('data-view'); } };
  pinta(deUrl() || leer() || 'pm');
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.vw-b, [data-ir-full]');
    if (!b) return;
    pon(b.getAttribute('data-view') || 'full', true);
  });

  /* Punto 24: un ancla a un tema tiene que ABRIR ese tema, no solo desplazarse
     hasta el. Y si lo que se enlaza vive en la vista completa, se cambia de
     vista: el enlace que manda un colega tiene que funcionar tal cual. */
  function abre(el) {
    while (el && el !== document.body) {
      if (el.tagName === 'DETAILS') el.open = true;
      el = el.parentElement;
    }
  }
  function abrirDestino(sel) {
    if (!sel || sel.length < 2) return false;
    var el;
    try { el = document.querySelector(sel); } catch (e) { return false; }
    if (!el) return false;
    if (el.closest('.solo-full') && root.getAttribute('data-view') === 'pm') {
      pon('full', false);
    }
    abre(el);
    setTimeout(function () { el.scrollIntoView({ block: 'start' }); }, 0);
    return true;
  }
  function vePorHash() { abrirDestino(location.hash); }
  /* 27 · el corte del mapa de calor. Las celdas no se borran: se ocultan,
     asi que «doce meses» sigue siendo cierto y el lector puede verlas. */
  var hmw = document.querySelector('.hm-w');
  if (hmw) {
    var mesesPorDefecto = (window.matchMedia
      && window.matchMedia('(max-width: 720px)').matches) ? '6' : '12';
    var ponMeses = function (m) {
      hmw.setAttribute('data-meses', m);
      var bs = document.querySelectorAll('.hm-b');
      for (var i = 0; i < bs.length; i++) {
        bs[i].setAttribute('aria-pressed',
          bs[i].getAttribute('data-meses') === m ? 'true' : 'false');
      }
    };
    ponMeses(mesesPorDefecto);
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('.hm-b');
      if (b) ponMeses(b.getAttribute('data-meses'));
    });
  }

  /* 28 · nada esencial solo en hover: la celda del mapa de calor dice lo suyo
     al enfocarla con el teclado o al tocarla. */
  var say = document.querySelector('.hm-say');
  if (say) {
    var dice = function (ev) {
      var td = ev.target.closest && ev.target.closest('[data-say]');
      if (td) say.textContent = td.getAttribute('data-say');
    };
    document.addEventListener('focusin', dice);
    document.addEventListener('click', dice);
  }

  document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (!a || a.classList.contains('vw-b')) return;
    /* Sin preventDefault: el navegador salta por su cuenta y esto añade lo que
       el salto no hace --cambiar de vista, abrir el desplegable que contiene
       el destino--. En un documento servido como data: el salto nativo está
       bloqueado y esto es lo único que funciona. */
    abrirDestino(a.getAttribute('href'));
  });

  window.addEventListener('hashchange', vePorHash);
  /* Con el hash puesto de entrada hay que esperar a que el documento este
     parseado: el navegador salta al ancla por su cuenta, pero abrir el
     <details> que la contiene es cosa nuestra, y a mitad del parseo ese nodo
     todavia no existe. */
  if (location.hash) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        setTimeout(vePorHash, 0);
      });
    } else {
      setTimeout(vePorHash, 0);
    }
  }
})();

/* Ayudantes minimos, sin dependencias: resaltar la seccion visible, el salto
   del selector movil y el filtro local de indicadores. Si el JS no corre, el
   documento sigue completo y navegable: los enlaces son anclas normales. */
(function () {
  var secs = [].slice.call(document.querySelectorAll('section.sx'));
  var links = [].slice.call(document.querySelectorAll('.nv a[data-sec]'));
  if (secs.length && links.length && 'IntersectionObserver' in window) {
    var obs = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        var id = e.target.id.replace('sec-', '');
        links.forEach(function (a) {
          a.classList.toggle('on', a.getAttribute('data-sec') === id);
          if (a.getAttribute('data-sec') === id) a.setAttribute('aria-current', 'true');
          else a.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-15% 0px -70% 0px' });
    secs.forEach(function (x) { obs.observe(x); });
  }
  var sel = document.getElementById('nv-sel');
  if (sel) sel.addEventListener('change', function () {
    /* Por el mismo camino que un ancla: si la sección elegida vive en la vista
       completa, se cambia de vista en vez de saltar a un bloque oculto. */
    if (window.mgVista && window.mgVista.abrir) {
      window.mgVista.abrir('#' + sel.value);
    } else {
      var el = document.getElementById(sel.value);
      if (el) el.scrollIntoView();
    }
  });

  var q = document.getElementById('flt-q'), fp = document.getElementById('flt-p'),
      fe = document.getElementById('flt-e'), fx = document.getElementById('flt-x'),
      fn = document.getElementById('flt-n');
  if (!q) return;
  var pilares = [].slice.call(document.querySelectorAll('#pilares .pillar'));
  function filtra() {
    var t = (q.value || '').toLowerCase().trim(),
        p = fp.value, e = fe.value, n = 0;
    pilares.forEach(function (pil) {
      var okPil = !p || pil.getAttribute('data-pilar') === p, vistas = 0;
      [].slice.call(pil.querySelectorAll('.row')).forEach(function (r) {
        var txt = (r.getAttribute('data-buscar') || '').toLowerCase();
        var est = r.getAttribute('data-estado') || '';
        var ext = r.getAttribute('data-extremo') === '1';
        var okT = !t || txt.indexOf(t) >= 0;
        var okE = !e || (e === 'extremo' ? ext : est === e);
        var ver = okPil && okT && okE;
        r.classList.toggle('oculto', !ver);
        if (ver) { vistas++; n++; }
      });
      pil.classList.toggle('oculto', vistas === 0);
      if (vistas > 0 && (t || e) && pil.tagName === 'DETAILS') pil.open = true;
    });
    fn.textContent = (t || p || e) ? (n + ' indicadores') : '';
  }
  [q, fp, fe].forEach(function (el) { el.addEventListener('input', filtra); });
  fx.addEventListener('click', function () {
    q.value = ''; fp.value = ''; fe.value = ''; filtra();
  });
})();
</script>'''



# ------------------------------------------------------------ componentes
def _bar(p: float, lectura: str, mini: bool = False) -> str:
    cls = "adv" if lectura == "adverso" else ("fav" if lectura == "favorable" else "")
    ticks = (f'<u style="left:{config.EXTREME_LOW}%"></u>'
             f'<u style="left:{config.EXTREME_HIGH}%"></u>')
    tag, klass = ("span", "mini") if mini else ("div", "bar")
    if not np.isfinite(p):
        return f'<{tag} class="{klass}">{ticks}</{tag}>'
    pos = min(max(p, 0.6), 99.4)
    return (f'<{tag} class="{klass}">{ticks}'
            f'<i class="{cls}" style="left:{pos:.1f}%"></i></{tag}>')


def _score_block(r: dict, s: dict) -> str:
    """Puntuacion de toma de riesgo, con el recuento que la sostiene.

    El recuento se da en SENALES INDEPENDIENTES, no en indicadores: cuatro
    filas que miden lo mismo son una senal, no cuatro votos. El recuento crudo
    sigue estando, debajo, como detalle -- pero no es el titular, porque
    contar indicadores exagera cualquier mayoria.
    """
    if r.get("disponible"):
        ef, ec, ez = r["e_favor"], r["e_contra"], r["e_neutral"]
        tot = max(ef + ec + ez, 1e-9)
        wf, wc = 100.0 * ef / tot, 100.0 * ec / tot
        wz = max(0.0, 100.0 - wf - wc)
        titular = (f'De los <b>{s["n_clusters"]} grupos independientes</b> del tablero, '
                   f'<b>≈{ef:.1f}</b> favorecen tomar riesgo · <b>≈{ez:.1f}</b> '
                   f'neutrales · <b>≈{ec:.1f}</b> en contra.')
        crudo = (f'<span class="raw">En bruto son {r["n_favor"]} indicadores a favor, '
                 f'{r["n_neutral"]} neutrales y {r["n_contra"]} en contra, de '
                 f'{r["n_total"]} — pero esos {r["n_total"]} son '
                 f'{s["n_clusters"]} grupos que se mueven juntos, y contarlos uno a uno '
                 f'exagera la mayoría.</span>')
    else:
        n = r["n_total"] or 1
        wf, wc = 100.0 * r["n_favor"] / n, 100.0 * r["n_contra"] / n
        wz = max(0.0, 100.0 - wf - wc)
        titular = (f'<b>{r["n_favor"]}</b> indicadores favorecen tomar riesgo · '
                   f'<b>{r["n_neutral"]}</b> neutrales · <b>{r["n_contra"]}</b> en '
                   f'contra, de {r["n_total"]}.')
        crudo = ('<span class="raw">Sin historia suficiente para agrupar los '
                 'indicadores por correlación: el recuento va en indicadores, no en '
                 'grupos independientes.</span>')
    return f"""
    <div class="score">
      <div class="n">{lvl_str(r['score'])}<small> / 100</small></div>
      <div class="who">
        <div class="lab">Puntuación de toma de riesgo</div>
        <div class="tally">
          <i class="f" style="width:{wf:.1f}%"></i>
          <i class="z" style="width:{wz:.1f}%"></i>
          <i class="c" style="width:{wc:.1f}%"></i>
        </div>
        <div class="tallyleg">{titular}
          Percentil histórico {p_str(r['hist_pct'])[1:]};
          {flecha(r['d3m'])} {puntos(r['d3m'])} en 3 meses.
          {crudo}</div>
      </div>
    </div>"""


def _dias(n) -> str:
    return "1 día" if n == 1 else f"{n} días"


def _lista_es(xs: list[str]) -> str:
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " y " + xs[-1]


def _contra_block(cs: list[dict]) -> str:
    """UNA contradicción destacada, la del indicador más extremo, en la 4.

    Vive aquí y no en la 1 porque una contradicción es exactamente eso: señales
    que no coinciden, igual que una divergencia. En la conclusión ya está
    incorporada como convicción; repetirla arriba era enunciar y desmentir en la
    misma pantalla.

    Dos párrafos, no una lista por clase. La versión por clase repetía "el dólar
    se fortalecería en contra de la lectura general", que es la definición de
    contradecir: no informaba. Una sola frase para toda la contradicción, y que
    diga algo que no se deduzca del enunciado.
    """
    if not cs:
        return ('<h4>Contradicción de alto perfil (0)</h4>'
                '<div class="aligned"><p>Ningún indicador en extremo —fuera de p5 o '
                'p95— apunta en contra de la inclinación de su propia clase.</p></div>')
    c = cs[0]
    n = c["n_frentes"]
    clases = _lista_es([fr["clase_label"].lower() for fr in c["frentes"]])
    if c.get("cap") == "baja":
        efecto = (" Las deja en confianza baja." if n > 1 else " La deja en confianza baja.")
    elif c.get("cap") == "media":
        efecto = " No deja pasar de confianza media a esas dimensiones."
    else:
        efecto = (" Lleva tanto en su extremo que ya está absorbido: apunta en contra, "
                  "pero ya no rebaja la confianza —ver la lectura—.")
    resto = ""
    if len(cs) > 1:
        otros = _lista_es([f'{esc(x["label"])} en {p_str(x["pct"])}'
                           for x in cs[1:]])
        resto = (f'<p class="cmas">Hay {len(cs) - 1} extremo'
                 f'{"s" if len(cs) - 1 != 1 else ""} más apuntando contra su clase '
                 f'({otros}). No se detallan: ya están reflejados en la confianza '
                 f'de su dimensión.</p>')
    return f"""
    <h4>Contradicción de alto perfil (1 de {len(cs)})</h4>
    <div class="contra">
      <div class="ck">El indicador más extremo del tablero va por su cuenta</div>
      <p class="ct"><b>{esc(c['label'])}</b>, en <b>{p_str(c['pct'])}</b>
        ({es_num(esc(c['valor']))}), contradice la lectura de
        <b>{n} clase{'s' if n != 1 else ''}</b>: {esc(clases)}.{efecto}</p>
      <p class="cq2"><b>Qué implicaría si tiene razón:</b> {esc(c['implica'])}.</p>
      <p class="co"><b>Qué habría que ver:</b> {esc(c['observar'])}.</p>
    </div>{resto}"""


def _esencial_block(linea: str) -> str:
    """Una línea. Si ocupa más, la sección 1 deja de ser esencial."""
    if not linea:
        return ""
    return f'<p class="tens">{es_num(esc(linea))}</p>'


_CONV_N = {"alta": 3, "media": 2, "baja": 1}


def _causa_nota(n: dict) -> str:
    """La causa común: un extremo que toca a 2+ clases se dice UNA vez, no una
    por fila. Y si el extremo ya está absorbido por antigüedad, lo dice: esa
    frase —«lleva 12 semanas en p99 sin que la tendencia se rompa»— es en sí una
    lectura útil, no un tecnicismo."""
    clases = _lista_es([c.lower() for c in n["clases"]])
    sem = int(round(n["semanas"])) if n.get("semanas") == n.get("semanas") else 0
    viejo = (n.get("peso") or 1.0) < 1.0
    if n["cap"] is not None:
        cuerpo = f"rebaja la convicción de {clases}"
        cola = (f" — y lleva unas {sem} semanas en {p_str(n['pct'])} sin que la "
                f"tendencia se rompa, así que pesa menos de lo que pesaría recién "
                f"llegado" if viejo else "")
    else:
        cuerpo = f"apunta en contra de {clases}"
        cola = (f", pero lleva unas {sem} semanas en {p_str(n['pct'])} sin que la "
                f"tendencia se rompa: ya absorbido, ya no les rebaja la convicción "
                f"—se anota, no manda—")
    return (f'<p class="causa"><b>{esc(n["label"])}</b> ({p_str(n["pct"])}) '
            f'{esc(cuerpo)}{esc(cola)}. El desarrollo, en «dónde discrepan».</p>')


def _inclinaciones_tabla(postura: list[dict], notas: list[dict]) -> str:
    """LA conclusión del documento: una inclinación por clase, con convicción.

    Dos líneas por clase y nada más — una de conclusión, una de razón PROPIA. La
    contradicción no va al lado con el mismo peso: ya está DENTRO, en la
    convicción; y si un mismo extremo rebaja a varias clases, se dice UNA vez en
    la nota de abajo, no cuatro veces en la tabla. Si la evidencia no alcanzaba
    para una dirección, aquí pone «neutral», que también es una conclusión.
    """
    orden = {"alta": 0, "media": 1, "baja": 2, None: 3}
    filas = []
    for p in sorted(postura, key=lambda x: (orden.get(x.get("conviccion"), 3),
                                            x["label"])):
        conv = p.get("conviccion")
        if conv:
            dir_html = (f'<b class="cd">{esc(p["direccion"])}</b>'
                        f'<span class="cv c{_CONV_N[conv]}">{_meter(_CONV_N[conv])}'
                        f'convicción {conv}</span>')
        else:
            dir_html = '<b class="cd neu">neutral</b>'
        razon = f'<div class="cr">{es_num(esc(p["razon"]))}</div>' if p.get("razon") else ""
        filas.append(
            f'<div class="crow"><div class="cl">'
            f'<span class="cname">{esc(p["label"])}</span>{dir_html}</div>{razon}</div>')
    notas_html = "".join(_causa_nota(n) for n in notas)
    return (f'<div class="inc-h">Inclinación por dimensión de posicionamiento</div>'
            f'<div class="concl">{"".join(filas)}</div>'
            f'{notas_html}'
            f'<p class="note">Dirección, no cuánto. Cómo se decide la convicción y de '
            f'dónde sale cada inclinación, en el tablero de auditoría (más abajo).</p>')


def _axis_card(e: dict) -> str:
    hp = e["hist_pct"]
    lect = ("favorable" if (np.isfinite(hp) and hp >= 60) else
            "adverso" if (np.isfinite(hp) and hp <= 40) else "neutral")
    pil = ", ".join(lbl for _k, lbl in e["pillars"])
    desde = e["hist_since"].year if e["hist_since"] is not None else "—"
    return f"""
    <div class="axis">
      <h3>{esc(e['label'])}</h3>
      <p class="sub2">{esc(e['sub'])} · {esc(e['low'])} ↔ {esc(e['high'])}</p>
      <div class="big">{lvl_str(e['level'])}<small>/ 100</small></div>
      {_bar(hp, lect)}
      <div class="scale"><span>0</span><span>percentil histórico</span><span>100</span></div>
      <div class="rowk"><span>Percentil histórico</span>
        <span><b>{p_str(hp)}</b> desde {desde}</span></div>
      <div class="rowk"><span>Cambio a 1 mes</span>
        <span>{flecha(e['d1m'])} {puntos(e['d1m'])}</span></div>
      <div class="rowk"><span>Cambio a 3 meses</span>
        <span>{flecha(e['d3m'])} {puntos(e['d3m'])}</span></div>
      <p class="pil">Agrega: {esc(pil)}.</p>
    </div>"""


def _chips(votos: dict) -> str:
    """Siglas de las clases de activo que defiende la señal. ▲ a favor, ▼ en
    contra. Cada una lleva su nombre completo como etiqueta emergente."""
    if not votos:
        return ""
    favor, contra = [], []
    for ck in config.ASSET_CLASSES:
        v = votos.get(ck, 0)
        if not v:
            continue
        meta = config.ASSET_CLASSES[ck]
        titulo = f'{meta["label"]}: {"a favor" if v > 0 else "en contra"}'
        chip = (f'<span class="chip {"up" if v > 0 else "dn"}" '
                f'title="{esc(titulo)}" aria-label="{esc(titulo)}">'
                f'{esc(meta["short"])} {"▲" if v > 0 else "▼"}</span>')
        (favor if v > 0 else contra).append(chip)
    partes = []
    if favor:
        partes.append(f'<span class="vg">favorece</span>{"".join(favor)}')
    if contra:
        partes.append(f'<span class="vg">en contra</span>{"".join(contra)}')
    return f'<div class="votes">{" ".join(partes)}</div>'


def _row(f: dict) -> str:
    ext_cls, k = "", ""
    if f["extremo"]:
        k = "fav" if f["extremo_tipo"] == "favorable" else "adv"
        ext_cls = f" ext {k}"
        etiqueta = f"extremo {f['extremo_tipo']}"
    else:
        lect = f["lectura"]
        k = "adv" if lect == "adverso" else ("fav" if lect == "favorable" else "")
        etiqueta = lect
    tag = f' <span class="tag {k}">{esc(etiqueta)}</span>'
    stale = ""
    if f["edad"] is not None and f["edad"] > 40:
        stale = f' · dato de {fecha_corta(f["dato_de"])}'
    chips = _chips(f["votos"])
    ext = ""
    if f.get("rmin") not in (None, "—") and f.get("rmax") not in (None, "—"):
        ext = (f'<span class="pext"><span>{es_num(esc(f["rmin"]))}</span>'
               f'<span>{es_num(esc(f["rmax"]))}</span></span>')
    return f"""
      <div class="row{ext_cls}" id="ind-{esc(f['key'])}"
           data-buscar="{esc(f['label'])} {esc(config.SHORT.get(f['key'], ''))} {esc(f['src'])}"
           data-estado="{esc(f['lectura'])}" data-extremo="{1 if f['extremo'] else 0}">
        <div class="name">{esc(f['label'])}{tag}
          <span class="src">{esc(f['src'])}{stale}</span>
          {chips}</div>
        <div class="num"><span class="cap">Valor</span>{es_num(esc(f['valor']))}</div>
        <div class="pcell"><span class="cap">Percentil 5 años</span>
          <span class="pwrap">{_bar(f['pct'], f['lectura'], mini=True)}<span
            class="pv">{p_str(f['pct'])}</span></span>{ext}</div>
        <div class="chg"><span class="cap">Cambio</span>
          <span class="ch"><i>1m</i>{es_num(esc(f['d1m']))}</span>
          <span class="ch"><i>3m</i>{es_num(esc(f['d3m']))}</span></div>
      </div>"""


def _meter(n: int) -> str:
    return ('<span class="meter">'
            + "".join(f'<i class="{"on" if i < n else ""}"></i>' for i in range(3))
            + "</span>")


def _pilares_signal_html(s: dict) -> str:
    """Cuantos indicadores tiene cada pilar y cuanta informacion distinta hay
    dentro. Es lo que explica que un pilar con diez filas no pese diez veces
    mas que uno con cuatro."""
    pp = s.get("por_pilar") or {}
    if not pp or not s.get("disponible"):
        return ""
    filas = "".join(
        f'<tr><td>{esc(config.PILLARS[k]["label"])}</td>'
        f'<td>{v["n"]}</td><td>≈{v["e"]:.1f}</td>'
        f'<td style="color:var(--faint)">'
        f'{"casi toda repetida" if v["n"] and v["e"] / v["n"] < 0.45 else ""}</td></tr>'
        for k, v in pp.items() if v["n"])
    grupo = ""
    if s.get("grupo_mayor"):
        grupo = (f'<p class="note">El grupo más grande de indicadores que se mueven '
                 f'como uno solo son {len(s["grupo_mayor"])}: '
                 f'{esc("; ".join(s["grupo_mayor"]))}.</p>')
    return f"""
    <details class="pos-det"><summary>Ver cuánta información distinta aporta cada pilar</summary>
    <table><tbody>
      <tr><td class="dh">Pilar</td><td class="dh">Indicadores</td>
        <td class="dh">Grupos indep.</td><td class="dh"></td></tr>
      {filas}
    </tbody></table>
    <p class="note">Los indicadores se agrupan por correlación; los que se mueven
       juntos cuentan como una sola señal. Estas cifras <b>no suman</b> al total del
       documento: los pilares también se solapan entre sí, y esa parte compartida no
       es de ninguno en exclusiva. Nada de esto corrige el tablero — el voto de cada
       indicador sigue contando igual; sirve para saber cuánto vale una mayoría.</p>
    {grupo}
    </details>"""


def _redundancia_html(red: list[dict]) -> str:
    if not red:
        return ""
    items = "".join(
        f'<li><b>{esc(r["pilar_label"])}</b> pone el {r["share_n"]:.0f}% de los '
        f'indicadores que votan sobre <b>{esc(r["clase_label"].lower())}</b> '
        f'({r["n"]} de {r["n_total"]}) y solo el {r["share_e"]:.0f}% de la '
        f'información independiente: quitarlo entero apenas cambiaría el recuento.</li>'
        for r in red)
    return (f'<div class="warnbox"><b>Un pilar manda en el recuento sin aportar '
            f'información nueva.</b><ul>{items}</ul>La inclinación de esa clase se '
            f'apoya en muchas filas que dicen lo mismo. No se corrige nada: se avisa '
            f'para que la mayoría se lea por lo que es.</div>')


def _divergencia_intra(d: dict) -> str:
    off = ("" if d["en_eje"] else
           '<span class="off">no entra en ningún eje</span>')
    return f"""
    <div class="dvi">
      <div class="p">{esc(d['pilar_label'])}{off}</div>
      <div class="pair">
        <div class="side hi"><div class="w"><b>{esc(d['alto_label'])}</b> · favorable</div>
          <div class="v">{es_num(esc(d['alto_valor']))} · {p_str(d['alto_pct'])}
            en su rango de 5 años</div></div>
        <div class="side lo"><div class="w"><b>{esc(d['bajo_label'])}</b> · adverso</div>
          <div class="v">{es_num(esc(d['bajo_valor']))} · {p_str(d['bajo_pct'])}
            en su rango de 5 años</div></div>
      </div>
      <p class="d">Separados por {d['gap']:.0f} puntos de lectura · {esc(d['duracion'])}
        (desde el {esc(fecha_larga(d['desde']))})
        {f"· {d['pares_pilar']} pares en contradicción dentro de este pilar"
          if d.get("pares_pilar", 1) > 1 else ""}</p>
    </div>"""


_MOTIVO = {
    "mayoría invertida": "contados como señales distintas, la mayoría se invierte",
    "empate efectivo":   "empate en voces independientes",
    "voto dividido":     "el voto se reparte o es demasiado flojo",
}


def _rumbo_txt(p: dict) -> str:
    if p.get("rumbo") != "contra" or not p.get("rumbo_eje"):
        return ""
    v = "cayó" if (p.get("rumbo_d") or 0) < 0 else "subió"
    return (f"el {config.AXES[p['rumbo_eje']]['label'].lower()} {v} "
            f"{abs(p.get('rumbo_d') or 0):.0f} pts en un mes")


def _limita_md(p: dict) -> str:
    """Qué, exactamente, impidió que esta clase tuviera más convicción."""
    if p.get("conv_motivo"):
        return _MOTIVO[p["conv_motivo"]]
    if _rumbo_txt(p):
        return _rumbo_txt(p)
    if p.get("contra_cap") and p.get("contra_label"):
        cola = ", reciente" if p.get("contra_reciente") else ""
        return (f"{p['contra_label']} en p{p['contra_pct']:.0f}, "
                f"en extremo y al contrario{cola}")
    if p.get("div_pilares"):
        a, b = p["div_pilares"]
        return f"{a.lower()} y {b.lower()} no coinciden sobre esta clase"
    if p.get("pilar_incoh"):
        return f"{p['pilar_incoh'].lower()} sin lectura unificada"
    if p.get("conviccion") in ("baja", "media"):
        return (f"≈{p['e_contra']:.1f} voces independientes en contra frente a "
                f"≈{p['e_favor']:.1f}")
    return "nada: las voces independientes apuntan a lo mismo"


def _limita(p: dict) -> str:
    if p.get("conv_motivo"):
        return esc(_MOTIVO[p["conv_motivo"]])
    if _rumbo_txt(p):
        return esc(_rumbo_txt(p))
    if p.get("contra_cap") and p.get("contra_label"):
        # Si el extremo que limita es RECIENTE se dice: por diseño pesa mas
        # recien llegado, y el lector tiene que poder distinguir un susto de un
        # regimen (SPEC 7.1).
        cola = ", reciente" if p.get("contra_reciente") else ""
        return (f'<span class="lim">{esc(p["contra_label"])}</span> en '
                f'p{p["contra_pct"]:.0f}, en extremo y al contrario{cola}')
    if p.get("div_pilares"):
        a, b = p["div_pilares"]
        return f'{esc(a.lower())} y {esc(b.lower())} no coinciden sobre esta clase'
    if p.get("pilar_incoh"):
        return f'{esc(p["pilar_incoh"].lower())} sin lectura unificada'
    if p.get("conviccion") in ("baja", "media"):
        return (f'≈{p["e_contra"]:.1f} voces independientes en contra frente a '
                f'≈{p["e_favor"]:.1f}')
    return '<span style="color:var(--faint)">nada: las voces apuntan a lo mismo</span>'


def _distribucion_html(dist: dict) -> str:
    """La distribución de convicciones de los últimos 6 meses: la comprobación de
    que la escala funciona. Si «alta» no aparece nunca o aparece siempre, está
    mal calibrada, y aquí se ve."""
    co = (dist or {}).get("conteo") or {}
    tot = sum(co.values())
    if not tot:
        return ""
    orden = [("alta", "c3"), ("media", "c2"), ("baja", "c1"), ("neutral", "cn")]
    barras = "".join(
        f'<div class="dcrow"><span class="dcl">{k}</span>'
        f'<span class="dcbar"><i class="{cls}" style="width:{100 * co.get(k, 0) / tot:.1f}%"></i></span>'
        f'<span class="dcn">{co.get(k, 0)}</span></div>' for k, cls in orden)
    ps = dist.get("por_sem") or []
    spark = "".join(f'<i style="height:{3 + 4 * n}px" title="{n}"></i>' for n in ps)
    return (f'<details class="pos-det"><summary>Ver la distribución de convicción de los '
            f'últimos 6 meses</summary>'
            f'<div class="distrib">{barras}</div>'
            f'<div class="dspark">altas por semana: {spark}</div>'
            f'<p class="note">{dist.get("semanas", 0)} semanas muestreadas. Que «alta» '
            f'aparezca a veces —y no siempre, ni nunca— es señal de que la escala '
            f'distingue. Aproximada: reutiliza los grupos de correlación de hoy e ignora '
            f'las divergencias entre pilares.</p></details>')


def _postura_html(postura: list[dict]) -> str:
    """De dónde sale cada inclinación: el rastro completo, en la sección 3.

    La conclusión ya se dio en la 1. Aquí está lo que hay detrás, para poder
    discutirla: recuento crudo, recuento efectivo y qué limitó la convicción.
    """
    orden = {"alta": 0, "media": 1, "baja": 2, None: 3}
    filas = []
    for p in sorted(postura, key=lambda x: (orden.get(x.get("conviccion"), 3),
                                            x["label"])):
        cn = _CONV_N.get(p.get("conviccion"))
        conv_html = (f'<span class="cv c{cn}">{p["conviccion"]}</span>' if cn
                     else '<span style="color:#a9a294">—</span>')
        direccion = (esc(p["direccion"]) if p["dir_tipo"] != "neutral"
                     else '<span style="color:#a9a294">neutral</span>')
        filas.append(
            f'<tr><td class="cl2">{esc(p["label"])}</td>'
            f'<td>{direccion}</td><td>{conv_html}</td>'
            f'<td>{p["n_a"]} / {p["n_c"]}</td>'
            f'<td>≈{p["e_favor"]:.1f} / ≈{p["e_contra"]:.1f}</td>'
            f'<td class="lm">{_limita(p)}</td></tr>')

    det = []
    for p in postura:
        drv = "; ".join(p["drivers"]) if p["drivers"] else "—"
        det.append(f'<tr><td>{esc(p["label"])}</td>'
                   f'<td style="color:var(--faint)">{esc(drv)}</td></tr>')
    return f"""
    <div style="overflow-x:auto"><table class="deriv">
      <thead><tr><th>Clase</th><th>Inclinación</th>
        <th>{config.CONVICCION_PM}</th>
        <th title="Indicadores que sostienen esa inclinación / que la contradicen">Indicadores</th>
        <th title="Los mismos votos contados por grupo de correlación: un grupo, una voz">Voces indep.</th>
        <th>Qué limita la {config.CONVICCION_PM.lower()}</th></tr></thead>
      <tbody>{"".join(filas)}</tbody></table></div>
    <p class="note">«Indicadores» es el recuento crudo; «voces indep.», los mismos
       votos agrupados por correlación. La convicción se decide sobre los segundos, que
       es lo que evita que cuatro filas del mismo pilar parezcan cuatro argumentos.</p>
    <details class="pos-det"><summary>Ver qué indicadores pesan más en cada inclinación</summary>
    <table><tbody>
      <tr><td class="dh">Clase</td><td class="dh">Indicadores que más pesan</td></tr>
      {"".join(det)}
    </tbody></table></details>"""


_MESES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep",
                "oct", "nov", "dic"]


def _fwd_val(v: float) -> str:
    if not np.isfinite(v):
        return '<span class="val">—</span>'
    cls = "pos" if v >= 0 else "neg"
    return f'<span class="val {cls}">{v:+.1f}%</span>'


def _analogos_html(a: dict) -> str:
    if a.get("ventana_corta"):
        m = a.get("muestra") or {}
        vent = (f'{m["anos"]:.1f} años elegibles ({m["desde"].year}–{m["hasta"].year}, '
                f'{m["n"]} fechas)' if m.get("anos") else "ventana no disponible")
        return (f'<div class="warnbox"><b>Ventana de comparación limitada: {vent}.</b> '
                f'El universo de análogos empieza cuando existen los siete pilares y '
                f'termina doce meses antes de la fecha, que es lo que hace falta para '
                f'saber qué pasó después. En esta fecha eso deja una ventana demasiado '
                f'corta: los análogos no son informativos y no se publican resultados, '
                f'ni medias ni rangos.</div>')
    warn = ('<div class="warnbox"><b>Un análogo no es un pronóstico.</b> Que el estado de '
            'hoy se parezca al de otras fechas no dice qué va a pasar; solo muestra qué '
            'pasó entonces, y el desenlace fue distinto cada vez. Sirve de contexto, no '
            'de predicción.</div>')

    if not a.get("disponible"):
        return warn + ('<div class="nomatch">Todavía no hay suficiente historia con los '
                       'siete pilares para buscar análogos.</div>')

    if a.get("sin_analogos"):
        return warn + _cobertura_html(a) + (
            f'<div class="nomatch"><b>Sin análogos cercanos.</b> El estado de hoy no se '
            f'parece lo suficiente a ninguna fecha del pasado: el más cercano difiere en '
            f'{a["nearest"]:.0f} puntos por fuerza, por encima del umbral de '
            f'{a["umbral"]:.0f}. Mostrar las cinco fechas menos malas confundiría más que '
            f'ayudar, así que no se muestran. Un estado inusual suele serlo por algo.</div>')

    H = a["horizonte"]
    cols = a["columnas"]

    def _ret(v):
        if not np.isfinite(v):
            return '<td>—</td>'
        return f'<td class="{"pos" if v >= 0 else "neg"}">{v:+.0f}%</td>'

    # --- matriz: cada analogo con sus tres horizontes, todos los activos + vol
    hs = a["horizontes"]
    th = "".join(f'<th title="{esc(et)}">{esc(sh)}</th>' for _c, sh, et in cols)
    DOT = {"fuerte": "q1", "ok": "q1", "otro": "q2", "sd": "q3", "no": "q3"}
    tr = []
    for x in a["lista"]:
        d = x["fecha"]
        env = f'{x["env"]:.2f}σ' if np.isfinite(x["env"]) else "—"
        for i, m in enumerate(hs):
            rets = "".join(_ret(x["ret"][m][c]) for c, _sh, _et in cols)
            v = x["vol"][m]
            vol = f'{v:.0f}%' if np.isfinite(v) else "—"
            cabeza = (
                f'<td class="cl" rowspan="{len(hs)}"><b>{_MESES_CORTO[d.month - 1]} '
                f'{d.year}</b>'
                f'<span class="amq"><span class="dotq {DOT.get(x["etiqueta_k"], "q3")}">'
                f'</span>{esc(x["etiqueta"])}</span>'
                f'<span class="amq">dinámica {x["dist"]:.1f} ({esc(x["calidad"])}) · '
                f'entorno {env} ({esc(x["env_calidad"])})</span></td>'
                if i == 0 else "")
            clase = ' class="grp"' if i == 0 else ""
            tr.append(f'<tr{clase}>{cabeza}<td class="hz">{m}m</td>{rets}'
                      f'<td class="vol">{vol}</td></tr>')
    matriz = (f'<h4>Qué pasó después de cada análogo</h4>'
              f'<div style="overflow-x:auto"><table class="amx">'
              f'<thead><tr><th>Análogo</th><th>Ventana</th>{th}<th>Vol.</th></tr></thead>'
              f'<tbody>{"".join(tr)}</tbody></table></div>'
              f'<p class="ana-lab"><b>Dinámica</b>: diferencia media por pilar, en puntos '
              f'de percentil, incluyendo hacia dónde venía moviéndose cada uno. Mide si el '
              f'mercado se <em>comportaba</em> igual. <b>Entorno</b>: diferencia media en '
              f'desviaciones típicas sobre {a["env_n"]} variables de nivel —tasa real, '
              f'inflación, tasa de referencia, curva, balance de la Fed{", valuación" if a["env_n"] > 5 else ""}—. '
              f'Mide si el <em>mundo</em> era el mismo. Un análogo puede acertar en la '
              f'primera y fallar en la segunda: entonces es contexto, no guía.'
              + (f' Sin dato de {esc(", ".join(a["env_faltan"]).lower())}, así que el '
                 f'entorno va con {a["env_n"]} de {len(config.ENV_VARS)} variables.'
                 if a.get("env_faltan") else "") + '</p>')

    # --- en que se parece y en que no
    sim = []
    for x in a["lista"]:
        d = x["fecha"]
        ig = "; ".join(f'{esc(lbl.lower())} <span class="g">({g:.0f})</span>'
                       for lbl, g in x["iguales"])
        di = "; ".join(f'{esc(lbl.lower())} <span class="g">({g:.0f})</span>'
                       for lbl, g in x["distintos"])
        sim.append(f'<tr><td class="f">{_MESES_CORTO[d.month - 1]} {d.year}</td>'
                   f'<td><span class="ok">≈</span> {ig}</td>'
                   f'<td><span class="no">≠</span> {di}</td></tr>')
    parecido = (f'<h4>En qué se parece cada análogo y en qué no</h4>'
                f'<div style="overflow-x:auto"><table class="simt"><thead><tr>'
                f'<th>Análogo</th><th>Se parece en</th><th>Se aleja en</th>'
                f'</tr></thead><tbody>{"".join(sim)}</tbody></table></div>'
                f'<p class="ana-lab">Entre paréntesis, los puntos de diferencia en ese '
                f'pilar. Un análogo que coincide en seis pilares y es el opuesto en el '
                f'séptimo no es un análogo: es una coincidencia parcial, y conviene '
                f'poder verlo.</p>')

    cover = _cobertura_html(a)
    if a.get("nulo"):
        # NULO HONESTO: las fechas siguen, la media no. Un desenlace concreto
        # con su fecha informa; una media de una sola observacion disfrazada de
        # cinco, no.
        return warn + cover + _nulo_html(a) + matriz + parecido

    # --- trayectoria media: como se fue formando el promedio a 3/6/12 meses
    trh = "".join(f'<th title="{esc(et)}">{esc(sh)}</th>' for _c, sh, et in cols)
    trrows = []
    for f in a["trayectoria"]:
        celdas = "".join(_ret(f["valores"][c]["media"]) for c, _sh, _et in cols)
        vm = f["vol"]["media"]
        volc = f'{vm:.0f}%' if np.isfinite(vm) else "—"
        trrows.append(f'<tr><td class="cl">{f["horizonte"]} meses</td>{celdas}'
                      f'<td class="vol">{volc}</td></tr>')
    tray = (f'<h4>Rendimiento medio de los {a["n"]} análogos por horizonte</h4>'
            f'<div style="overflow-x:auto"><table class="amx">'
            f'<thead><tr><th>Ventana</th>{trh}<th>Vol.</th></tr></thead>'
            f'<tbody>{"".join(trrows)}</tbody></table></div>')

    # --- promedio con rango VISUAL (min — media — max), escala comun
    S = a["escala"]

    def _barra(st):
        if not (st["media"] == st["media"]):
            return '<div class="dbar"></div>', "—"
        lo = max(0.0, min(100.0, (st["min"] + S) / (2 * S) * 100))
        hi = max(0.0, min(100.0, (st["max"] + S) / (2 * S) * 100))
        me = max(0.0, min(100.0, (st["media"] + S) / (2 * S) * 100))
        seg = (f'<span class="seg" style="left:{lo:.1f}%;width:{max(hi - lo, 0.6):.1f}%"></span>'
               f'<span class="mk {"pos" if st["media"] >= 0 else "neg"}" style="left:{me:.1f}%"></span>')
        num = (f'<b class="{"pos" if st["media"] >= 0 else "neg"}">{st["media"]:+.0f}%</b> '
               f'<span class="rr">{st["min"]:+.0f} a {st["max"]:+.0f}</span>')
        return f'<div class="dbar"><span class="zero"></span>{seg}</div>', num

    # Un grupo por clase, con una barra por horizonte: se ve como se abre el
    # abanico segun se aleja el plazo.
    por_h = {f["horizonte"]: f for f in a["trayectoria"]}
    drows = []
    for r in a["promedio"]:
        for i, m in enumerate(hs):
            st = por_h[m]["valores"][r["clave"]]
            barra, num = _barra(st)
            lab = (f'<span class="dlab" title="{esc(r["etiqueta"])}">{esc(r["sigla"])}</span>'
                   if i == 0 else '<span class="dlab"></span>')
            cls = "drow" + (" g0" if i == 0 else "") + (" gl" if i == len(hs) - 1 else "")
            drows.append(f'<div class="{cls}">{lab}<span class="dhz">{m}m</span>'
                         f'{barra}<span class="dnum">{num}</span></div>')
    vrows = []
    for i, m in enumerate(hs):
        pv = por_h[m]["vol"]
        vn = (f'{pv["media"]:.0f}% <span class="rr">{pv["min"]:.0f} a {pv["max"]:.0f}</span>'
              if pv["media"] == pv["media"] else "—")
        lab = '<span class="dlab">Vol. S&amp;P</span>' if i == 0 else '<span class="dlab"></span>'
        cls = "drow vol" + (" g0" if i == 0 else "") + (" gl" if i == len(hs) - 1 else "")
        vrows.append(f'<div class="{cls}">{lab}<span class="dhz">{m}m</span>'
                     f'<span class="dnum">{vn}</span></div>')

    leyenda = " · ".join(f'<b>{esc(sh)}</b> {esc(et)}' for _c, sh, et in cols)
    disp = (f'<h4>Dispersión del resultado, por horizonte</h4>'
            f'<div class="disp"><div class="dscale"><span class="l">−{S:.0f}%</span>'
            f'<span class="m">0</span><span class="r">+{S:.0f}%</span></div>'
            f'{"".join(drows)}{"".join(vrows)}</div>'
            f'<p class="ana-lab">La barra va del <b>peor</b> al <b>mejor</b> de los '
            f'{a["n"]} desenlaces; el punto es la <b>media</b>. Cuanto más larga, más '
            f'dispersión (menos fiable la media): fíjate en cómo se abre el abanico al '
            f'alejarse el plazo. {leyenda}. Vol. S&amp;P: volatilidad realizada anualizada '
            f'del S&amp;P. No es un pronóstico.'
            + (f' <b>Ojo:</b> {a["n_otro_mundo"]} de los {a["n"]} análogos se comportaban '
               f'igual pero en otro entorno; la media los incluye a todos, así que léela '
               f'con eso delante.' if a.get("n_otro_mundo") else "") + '</p>')

    return warn + cover + matriz + parecido + tray + disp


def _cobertura_html(a: dict) -> str:
    """De cuántas fechas y cuántos mundos distintos sale todo esto. Sin este
    párrafo, cinco análogos parecen salir de una muestra grande."""
    m = a.get("muestra")
    if not m:
        return ""
    eps = ""
    if a.get("n_episodios"):
        eps = (f', y las {a["n"]} fechas de abajo caen en '
               f'<b>{a["n_episodios"]} episodios distintos</b>')
    return (f'<p class="cover">De dónde sale la búsqueda: <b>{m["n"]:,} fechas</b> '
            f'elegibles ({fecha_corta(m["desde"])} a {fecha_corta(m["hasta"])}, unos '
            f'<b>{m["anos"]:.0f} años</b>) — todas las que tienen doce meses de futuro '
            f'por delante, que es lo que hace falta para poder decir qué pasó después. '
            f'Esos {m["anos"]:.0f} años no son {m["anos"]:.0f} años de situaciones '
            f'distintas: contienen <b>{m["episodios"]} entornos macro diferentes</b>'
            f'{eps}. Con tan pocos regímenes de verdad distintos, cualquier promedio '
            f'histórico descansa sobre menos observaciones de las que parece.</p>')


def _nulo_html(a: dict) -> str:
    razones = "".join(f"<li>{esc(r)}</li>" for r in a.get("nulo_razon", []))
    return (f'<div class="warnbox hard"><b>Sin análogos comparables.</b> El estado '
            f'actual no tiene precedentes suficientemente independientes en la historia '
            f'disponible. No se publican la media ni las barras de dispersión: saldría '
            f'un número con apariencia de muestra y cuerpo de una sola observación. '
            f'Por qué:<ul>{razones}</ul>'
            f'Las fechas sí se quedan. Un desenlace concreto, con su fecha y su '
            f'contexto, sigue informando; el promedio de todos ellos, no.</div>')


_CHK_SIM = {"ok": "✓", "aviso": "!", "nd": "?"}


def _checks_block(rows: list[dict]) -> str:
    """Las comprobaciones de ESTA ejecucion, siempre presentes.

    Discreto a proposito: no es contenido, es el pie de garantia del resto. Si
    algo no se pudo calcular se declara aqui, porque una comprobacion ausente
    se confunde con una comprobacion pasada."""
    if not rows:
        return ""
    items = []
    for r in rows:
        nota = (f'<span class="n">{es_num(esc(r["nota"]))}</span>'
                if r.get("nota") else "")
        sev = r.get("sev") or r["estado"]
        items.append(
            f'<div class="chk" id="chk-{_slug(r["label"])}">'
            f'<span class="s {r["estado"]}">'
            f'{_CHK_SIM.get(r["estado"], "·")}</span>'
            f'<span class="l">{esc(r["label"])}</span>'
            + (f'<span class="qa-b qa-b-{sev}">{esc(config.QA_SEV_TXT[sev])}</span>'
               if sev in ("error", "aviso", "info") else "")
            + f'<span class="v">{es_num(esc(r["valor"]))}</span>{nota}</div>')
    return f"""
    <div class="checks">
      <div class="ct">Comprobaciones de esta ejecución</div>
      <p class="ci">Se ejecutan cada vez que se genera el documento y se imprimen
        siempre, salgan como salgan. Ninguna corrige nada por detrás: informan de
        dónde puede fallar lo de arriba. <b>✓</b> pasó · <b>!</b> hay algo que mirar ·
        <b>?</b> no se pudo calcular.</p>
      {"".join(items)}
    </div>"""


def _leyenda_siglas() -> str:
    return " · ".join(f'<b>{esc(m["short"])}</b> {esc(m["label"].lower())}'
                      for m in config.ASSET_CLASSES.values())


def _howto_block(snap: dict) -> str:
    """Guía de lectura con un ejemplo vivo, para que nadie tenga que adivinar
    qué significan valor, percentil y las siglas."""
    ej = ""
    exs = snap.get("extremos") or []
    if exs:
        e = exs[0]
        comp = ("no había estado tan alto en cinco años" if e["pct"] >= 50
                else "no había estado tan bajo en cinco años")
        ej = (f'<p class="eg"><b>Ejemplo.</b> «{esc(e["label"])}» marca '
              f'{es_num(esc(e["valor"]))} (el valor). Su percentil es '
              f'{p_str(e["pct"])}: {comp}. Y lleva {esc(e["duracion"])} en ese extremo. '
              f'Las siglas de colores dicen a qué activo ayuda esa señal.</p>')
    return f"""
    <div class="howto">
      <div class="ht">Cómo leer cada fila</div>
      <dl>
        <dt>Valor</dt><dd>el dato en sus propias unidades: un %, un nivel, unos puntos.</dd>
        <dt>Percentil a 5 años</dt><dd>qué tan alto o bajo está frente a su propia
          historia reciente. <b>p50</b> es lo normal; <b>p100</b>, más alto que en ningún
          momento de los últimos cinco años; <b>p0</b>, el mínimo. La barrita lo dibuja,
          con marcas tenues en p10 y p90 (las zonas de extremo), y debajo van los
          <b>valores mínimo y máximo</b> de esos cinco años, para saber entre qué números
          se mueve. {esc(config.METODOLOGIA_PERCENTIL['corta'])}
          {esc(config.METODOLOGIA_PERCENTIL['ejes'])}</dd>
        <dt>Cambio</dt><dd>cuánto se movió el dato en el último mes (1m) y en los últimos
          tres (3m), uno debajo del otro.</dd>
        <dt>Etiqueta</dt><dd><i>favorable</i>, <i>adverso</i> o <i>extremo</i>: si eso
          ayuda o no a tomar riesgo, y si está fuera de lo normal.</dd>
        <dt>Siglas ▲ ▼</dt><dd>a qué dimensión de posicionamiento ayuda la señal (▲ a favor, ▼ en
          contra). Pasa el cursor por cada una para ver el nombre completo.</dd>
      </dl>
      <p class="key">{_leyenda_siglas()}.</p>
      {ej}
    </div>"""


def _pillar_block(p: dict) -> str:
    lect = p["lectura"]
    k = "adv" if lect == "adverso" else ("fav" if lect == "favorable" else "")
    eje = p["eje"] or "contexto · no entra en ningún eje"
    score = "—" if not np.isfinite(p["score"]) else f"{p['score']:.0f}"
    faltan = "" if p["n_datos"] == p["n_total"] else f' · {p["n_datos"]}/{p["n_total"]} con dato'
    e = p.get("senales_e")
    sig = ""
    if e is not None and p["n_datos"]:
        sig = (f' · {p["n_datos"]} indicadores que valen por '
               f'<b title="Indicadores agrupados por correlación: los que se mueven '
               f'juntos cuentan como una sola señal">≈{e:.1f} señales '
               f'independientes</b>')
    rows = "".join(_row(f) for f in p["filas"])
    # SPEC-5P 25 y 26: el pilar se pliega. El resumen responde las cuatro cosas
    # que se preguntan antes de abrirlo --nivel, direccion, cambio e
    # independencia-- y nombra a los que mandan. Abierto, la seccion de research
    # medía mas de dos mil lineas y habia que recorrerla entera para ver un
    # indicador.
    lead = " · ".join(config.SHORT.get(f["key"], f["label"])
                      for f in p["filas"][:3])
    voces = (f'{p["n_datos"]} indicadores → ≈{e:.1f} voces independientes'
             if (e is not None and p["n_datos"]) else f'{p["n_datos"]} indicadores')
    return f"""
    <details class="pillar" data-pilar="{esc(p['key'])}">
      <summary>
        <span class="ph-n">{esc(p['label'])}</span>
        <span class="ph-s"><b>{score}</b>/100 <span class="tag {k}">{esc(lect)}</span></span>
        <span class="ph-d">{flecha(p['d3m'])} {delta_pts(p['d3m'])} en 3m</span>
        <span class="ph-v">{esc(voces)}</span>
        <span class="ph-l">{esc(lead)}</span>
      </summary>
      <p class="pdesc">{esc(p['desc'])} <em>{esc(eje)}</em>{faltan}{sig}</p>
      <div class="thead"><span>Indicador</span><span>Valor</span>
        <span>Percentil a 5 años · mín–máx</span><span>Cambio</span></div>
      {rows}
    </details>"""


def _divergence(d: dict) -> str:
    lo, hi = d["bajo_score"], d["alto_score"]
    seg = f'<span class="seg" style="left:{lo:.1f}%;width:{(hi - lo):.1f}%"></span>'
    return f"""
    <div class="dv">
      <p class="t"><b>{esc(d['alto_label'])}</b> dice favorable ({p_str(hi)})
        pero <b>{esc(d['bajo_label'])}</b> dice adverso ({p_str(lo)})</p>
      <div class="gapbar">{seg}<i class="lo" style="left:{lo:.1f}%"></i>
        <i class="hi" style="left:{hi:.1f}%"></i></div>
      <p class="d">Brecha de {d['gap']:.0f} puntos · {esc(d['duracion'])}
        (desde el {esc(fecha_larga(d['desde']))})</p>
    </div>"""


def _extreme(e: dict) -> str:
    k = "fav" if e["tipo"] == "favorable" else "adv"
    return f"""
      <div class="ex {k}">
        <span><strong>{esc(e['label'])}</strong> <span class="stale">· {esc(e['pilar'])}</span></span>
        <span>{es_num(esc(e['valor']))}</span>
        <span>{p_str(e['pct'])}</span>
        <span class="w">{esc(e['duracion'])}, desde {esc(fecha_corta(e['desde']))}</span>
      </div>"""


def _edad_badge(frescura: str, edad: int) -> str:
    dias = "1 día" if edad == 1 else f"{edad} días"
    if frescura == "reciente":
        return f'<span class="age">{dias}</span>'
    return f'<span class="age semana">{dias}</span>'


def _titular(h: dict) -> str:
    url = h.get("url")
    fuente = esc(h["fuente"])
    if url:
        fuente = f'<a href="{esc(url)}" target="_blank" rel="noopener">{fuente}</a>'
    return f"""
      <div class="hl">
        <span class="hl-d">{esc(fecha_corta(h['fecha_ts']))}</span>
        <span class="hl-t">{esc(h['texto'])}
          <span class="hl-s">{fuente} · {esc(h['tipo_label'])}</span></span>
      </div>"""


def _contraste(c: dict) -> str:
    f = c["fila"]
    resuelto = c["postura"] == "resuelve"
    k = "res" if resuelto else "comp"
    kicker = "Choque: pesa más un criterio" if resuelto else "Otra lectura del mismo indicador"
    veredicto = ""
    if resuelto and c.get("veredicto"):
        veredicto = (f'<p class="verd"><b>Se queda con:</b> {esc(c["veredicto"])}</p>')
    return f"""
    <div class="ctr {k}">
      <div class="k">{kicker}</div>
      <p class="q">{esc(c['texto'])}</p>
      {veredicto}
      <p class="n">Indicador: <b>{esc(f['label'])}</b> — {es_num(esc(f['valor']))},
        percentil {p_str(f['pct'])[1:]} a 5 años, hoy se lee como {esc(f['lectura'])}.
        Fuente: <b>{esc(c['fuente'])}</b>, {esc(fecha_corta(c['fecha_ts']))}
        ({_dias(c['edad'])}).</p>
    </div>"""


def _documento(d: dict) -> str:
    aporta = "".join(f"<li>{esc(x)}</li>" for x in d.get("aporta", []))
    bloque_ap = f'<ul class="aporta">{aporta}</ul>' if aporta else ""
    dice = "".join(
        f'<li>{esc(x["texto"])}'
        + (f' <span class="ref">[{esc(x["ref"])}]</span>' if x.get("ref") else "")
        + "</li>"
        for x in d.get("dice", []))
    bloque_dice = (f'<div class="says-h">Lo que dice, textual</div>'
                   f'<ul class="says">{dice}</ul>') if dice else ""
    infiero = "".join(f"<li>{esc(x)}</li>" for x in d.get("infiero", []))
    bloque_inf = (f'<div class="says-h infer-h">Lectura propia, no del documento</div>'
                  f'<ul class="infer">{infiero}</ul>') if infiero else ""
    origen = d.get("ruta") or d.get("url") or "—"
    return f"""
    <div class="doc-item">
      <div class="doc-h">
        <b>{esc(d['titulo'])}</b>
        <span class="doc-m">{esc(d['fuente'])}
          {('· ' + esc(d['autor'])) if d.get('autor') else ''} ·
          {esc(fecha_corta(d['fecha_ts']))} · {esc(d['tipo_label'])}
          {_edad_badge(d['frescura'], d['edad'])}</span>
      </div>
      <p class="tesis">{esc(d['tesis'])}</p>
      {bloque_ap}
      {bloque_dice}
      {bloque_inf}
      <p class="doc-m" style="margin-top:10px">Origen: {esc(origen)}</p>
    </div>"""


def _cambios_html(c: dict) -> str:
    """Que cambio desde el anterior. SOLO lo que cambio -- no un resumen de todo.
    Si no cambio nada, lo dice en una linea: eso tambien es informacion, y es la
    lectura mas comun de un documento semanal."""
    if not c.get("disponible"):
        return ('<div class="chg-none">Es el primer snapshot con memoria: no hay uno '
                'anterior con el que compararlo. Desde la próxima ejecución, aquí '
                'aparecerá solo lo que haya cambiado.</div>')
    prev = fecha_larga(c["fecha_prev"]) if c.get("fecha_prev") else "el anterior"
    if not c.get("algo"):
        return (f'<div class="chg-none"><b>Sin cambios de inclinación ni de convicción '
                f'desde {esc(prev)}.</b> Ninguna clase cambió de dirección, ningún '
                f'indicador entró o salió de extremo y ninguna divergencia nació o murió. '
                f'Que no cambie nada también es información —y es la lectura más común.</div>')
    items = []
    for d in c["dir_cambios"]:
        items.append(f'<li class="mv"><b>{esc(d["clase"])}</b>: '
                     f'<span class="chg-de">{esc(d["de"])}</span> → '
                     f'<b>{esc(d["a"])}</b></li>')
    for d in c["conv_cambios"]:
        cls = "up" if d["subio"] else "dn"
        de, a = d["de"] or "neutral", d["a"] or "neutral"
        items.append(f'<li class="{cls}"><b>{esc(d["clase"])}</b>: convicción '
                     f'<span class="chg-de">{esc(de)}</span> → <b>{esc(a)}</b></li>')
    for e in c["entraron"]:
        items.append(f'<li class="nw"><b>{esc(e["label"])}</b> entró en extremo '
                     f'{esc(e["tipo"])} ({p_str(e["pct"])})</li>')
    for e in c["salieron"]:
        items.append(f'<li class="gn">{esc(e["label"])} salió de su extremo</li>')
    for d in c["div_nac"]:
        items.append(f'<li class="nw">Nueva divergencia: {esc(d)}</li>')
    for d in c["div_mur"]:
        items.append(f'<li class="gn">Se cerró la divergencia: {esc(d)}</li>')
    for p in c["pil_mov"]:
        cls = "up" if p["delta"] > 0 else "dn"
        dlt = es_num("{:+.0f}".format(p["delta"]))
        de0 = es_num("{:.0f}".format(p["de"]))
        a0 = es_num("{:.0f}".format(p["a"]))
        items.append(f'<li class="{cls}"><b>{esc(p["pilar"])}</b> se movió '
                     f'{dlt} puntos ({de0}→{a0})</li>')
    for tit in c["docs_nuevos"]:
        items.append(f'<li class="nw">Nueva fuente: {esc(tit)}</li>')
    intro = (f'<p class="note" style="margin:0 0 10px">Cambios desde {esc(prev)}. '
             f'Solo lo que se movió.</p>')
    return intro + f'<ul class="chg-list">{"".join(items)}</ul>'


def _fuentes_lectura(reg: dict) -> str:
    """En la LECTURA, solo lo que la fuente APORTA que el tablero no ve: la
    lectura doble de un indicador (contrastes) y una linea de tesis por
    documento. El texto completo, las citas y lo inferido van al tablero."""
    rel = reg["contrastes"]
    partes = []
    if rel:
        partes.append("".join(_contraste(c) for c in rel))
    cards = []
    for d in reg["documentos"]:
        aporta = "".join(f"<li>{esc(x)}</li>" for x in d.get("aporta", []))
        ap = f'<ul class="aporta">{aporta}</ul>' if aporta else ""
        cards.append(
            f'<div class="doc-item"><div class="doc-h"><b>{esc(d["titulo"])}</b>'
            f'<span class="doc-m">{esc(d["fuente"])} · {esc(fecha_corta(d["fecha_ts"]))} '
            f'{_edad_badge(d["frescura"], d["edad"])}</span></div>'
            f'<p class="tesis">{esc(d["tesis"])}</p>{ap}</div>')
    if not rel and not cards:
        return ('<div class="aligned"><p>No hay fuentes vigentes hoy —las de más de dos '
                'semanas no se muestran—. El registro completo, en el tablero.</p></div>')
    if cards:
        partes.append('<h4>Qué aporta cada análisis</h4>' + "".join(cards))
    return "".join(partes)


def _fuentes_completas(reg: dict) -> str:
    """En el TABLERO, el rastro entero: titulares y el texto completo de cada
    documento con sus citas y lo inferido."""
    bloques = []
    if reg["n_titulares"]:
        bloques.append('<h4>Titulares recientes</h4>'
                       + "".join(_titular(h) for h in reg["titulares"]))
    if reg["total"]:
        bloques.append('<h4>Análisis y research, texto completo</h4>'
                       + "".join(_documento(d) for d in reg["documentos"]))
    if not bloques:
        return ('<div class="aligned"><p>Sin fuentes vigentes. Se pegan en '
                '<code>docs/registro.json</code>.</p></div>')
    return "".join(bloques)


# ------------------------------------------------- LA NOTA (research)
def _conclusiones_html(bullets: list[str]) -> str:
    if not bullets:
        return ""
    li = "".join(f"<li>{es_num(esc(b))}</li>" for b in bullets)
    return (f'<div class="concl-box"><div class="cb-t">En síntesis</div>'
            f'<ul class="cb">{li}</ul></div>')


def _evidencia_html(paras: list[str]) -> str:
    if not paras:
        return ""
    ps = "".join(f"<p>{es_num(esc(p))}</p>" for p in paras)
    return f'<div class="evid">{ps}</div>'


def _grafico_svg(serie: dict) -> str:
    """La puntuación de riesgo y de ciclo en el tiempo, con franjas de
    favorable / neutral / adverso. SVG inline, sin dependencias. Es el gráfico
    más importante: pone el número de hoy en el contexto de cinco años."""
    S = (serie or {}).get("series") or {}
    rr = S.get("riesgo") or []
    cc = S.get("ciclo") or []
    if len(rr) < 6:
        return ""
    W, H = 720, 250
    ml, mr, mt, mb = 8, 40, 22, 20
    pw, ph = W - ml - mr, H - mt - mb
    t0 = rr[0][0].toordinal()
    t1 = rr[-1][0].toordinal()
    span = max(t1 - t0, 1)

    def X(d):
        return ml + pw * (d.toordinal() - t0) / span

    def Y(v):
        return mt + ph * (1 - max(0.0, min(100.0, v)) / 100.0)

    # franjas
    bands = (f'<rect x="{ml}" y="{Y(100):.1f}" width="{pw}" height="{Y(60) - Y(100):.1f}" fill="var(--fav)" opacity="0.08"/>'
             f'<rect x="{ml}" y="{Y(60):.1f}" width="{pw}" height="{Y(40) - Y(60):.1f}" fill="var(--neu)" opacity="0.06"/>'
             f'<rect x="{ml}" y="{Y(40):.1f}" width="{pw}" height="{Y(0) - Y(40):.1f}" fill="var(--adv)" opacity="0.07"/>')
    # lineas guia y etiquetas y
    ylab = "".join(
        f'<line x1="{ml}" y1="{Y(v):.1f}" x2="{ml + pw}" y2="{Y(v):.1f}" '
        f'stroke="var(--rule-soft)" stroke-width="0.5"/>'
        f'<text x="{ml + pw + 5}" y="{Y(v) + 3:.1f}" class="gax">{v}</text>'
        for v in (0, 40, 60, 100))
    # marcas de año
    import pandas as _pd
    years = sorted({d.year for d, _ in rr})
    xlab = ""
    for y in years:
        dd = _pd.Timestamp(year=y, month=1, day=1)
        if dd.toordinal() < t0:
            continue
        x = X(dd)
        xlab += (f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt + ph}" '
                 f'stroke="var(--rule-soft)" stroke-width="0.5"/>'
                 f'<text x="{x:.1f}" y="{H - 6}" class="gax" text-anchor="middle">{y}</text>')

    def poly(pts):
        return " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in pts)

    ln_ciclo = (f'<polyline points="{poly(cc)}" fill="none" stroke="var(--muted)" '
                f'stroke-width="1.3" stroke-dasharray="4 3" opacity="0.8"/>') if len(cc) >= 6 else ""
    ln_riesgo = (f'<polyline points="{poly(rr)}" fill="none" stroke="var(--ink)" '
                 f'stroke-width="1.8"/>')
    # punto final
    dr, vr = rr[-1]
    dot = (f'<circle cx="{X(dr):.1f}" cy="{Y(vr):.1f}" r="3" fill="var(--ink)"/>'
           f'<text x="{X(dr) - 6:.1f}" y="{Y(vr) - 6:.1f}" class="gnow" text-anchor="end">{vr:.0f}</text>')
    if cc:
        dcy, vcy = cc[-1]
        dot += (f'<circle cx="{X(dcy):.1f}" cy="{Y(vcy):.1f}" r="2.5" fill="var(--muted)"/>')
    return (f'<figure class="grafico"><svg viewBox="0 0 {W} {H}" '
            f'preserveAspectRatio="xMidYMid meet" role="img" '
            f'aria-label="Puntuación de riesgo y de ciclo, cinco años">'
            f'{bands}{ylab}{xlab}{ln_ciclo}{ln_riesgo}{dot}</svg>'
            f'<figcaption><span class="gk"><i class="kr"></i> riesgo</span>'
            f'<span class="gk"><i class="kc"></i> ciclo</span> · '
            f'nivel 0–100 (100 = favorable a activos de riesgo); franjas '
            f'favorable / neutral / adverso · cinco años</figcaption></figure>')


_SIG = {"++": ("s2", "fav"), "+": ("s1", "fav"), "~": ("sx", "neu"),
        "-": ("s1", "adv"), "--": ("s2", "adv"), "0": ("s0", "neu")}


def _senal_cell(v: str) -> str:
    txt, mark = (v.split("|", 1) + ["0"])[:2]
    peso, _c = _SIG.get(mark, ("s0", "neu"))
    return f'<span class="sig {peso}">{esc(txt)}</span>'


def _pgrid_bar(paso: int, paso_ant) -> str:
    """El carril de posición: cinco pasos de adverso (izq) a favorable (der),
    con la marca de hoy (●, coloreada) y la del mes anterior (○, gris) si cambió,
    sobre la misma línea."""
    def L(s):  # % desde la izquierda para un paso en [-2, +2]
        return 8 + (s + 2) / 4 * 84
    ticks = "".join(f'<i class="tk" style="left:{L(s):.1f}%"></i>' for s in (-2, -1, 0, 1, 2))
    prev = ""
    if paso_ant is not None and paso_ant != paso:
        prev = (f'<span class="mk pv" style="left:{L(paso_ant):.1f}%" '
                f'title="mes anterior"></span>')
    c = "fav" if paso > 0 else "adv" if paso < 0 else "neu"
    cur = f'<span class="mk cu {c}" style="left:{L(paso):.1f}%"></span>'
    return f'<span class="trk"><i class="axl"></i>{ticks}{prev}{cur}</span>'


def _pgrid_dots(conv) -> str:
    n = {"alta": 3, "media": 2, "baja": 1}.get(conv, 0)
    return "".join(f'<span class="pd{" on" if i < n else ""}"></span>' for i in range(3))


def _posicionamiento_grid_html(rows: list[dict]) -> str:
    """La rejilla de la lectura: el ojo escanea la columna de posiciones en
    vertical sin leer palabras. La señal técnica y la macro no salen como texto
    -- cuando coinciden son ruido; cuando discrepan, va en la nota."""
    tr = []
    for r in rows:
        et = ('<span class="ineu">neutral</span>' if r["dir_tipo"] == "neutral"
              else f'<span class="etq">{esc(r.get("etiqueta") or r["dir_actual"])}</span>')
        nota = r.get("nota") or ""
        nota_h = f'<span class="gnota">{es_num(esc(nota))}</span>' if nota else ""
        conv = r.get("conv_actual")
        tr.append(
            f'<tr><td class="gc">{esc(r["label"])}</td>'
            f'<td class="gbar">{_pgrid_bar(r["paso"], r.get("paso_ant"))}</td>'
            f'<td class="get">{et}</td>'
            f'<td class="gdt" title="convicción {conv or "—"}">{_pgrid_dots(conv)}</td>'
            f'<td class="gnt">{nota_h}</td></tr>')
    return (f'<div style="overflow-x:auto"><table class="pgrid">'
            f'<thead><tr><th>Clase</th>'
            f'<th class="thpos">posición <span class="thk">adverso ◄&nbsp;&nbsp;► favorable '
            f'· ● hoy · ○ mes ant.</span></th>'
            f'<th>sesgo</th><th>convicción</th><th>nota</th></tr></thead>'
            f'<tbody>{"".join(tr)}</tbody></table></div>')


def _posicionamiento_html(rows: list[dict]) -> str:
    """La versión completa, en el tablero: señales técnicas y macro por separado,
    inclinación, convicción y mes anterior en texto. Es la tabla de la que sale
    la rejilla de arriba."""
    tr = []
    for r in rows:
        cn = _CONV_N.get(r.get("conv_actual"))
        # La celda dice inclinación y convicción. Cuando la inclinación YA es
        # neutral, repetir «neutral» detrás no añade nada: la convicción de una
        # clase sin dirección no existe, y la celda salía «neutral neutral».
        act = (f'<b>{esc(r["dir_actual"])}</b>'
               + (f' <span class="cv c{cn}">{r["conv_actual"]}</span>' if cn else
                  ' <span class="ineu">sin convicción que medir</span>'
                  if r["dir_tipo"] == "neutral" else ''))
        cna = _CONV_N.get(r.get("conv_ant"))
        if r.get("dir_ant") in (None, "—"):
            ant = '<span class="ant">—</span>'
        else:
            ant = (f'<span class="ant">{esc(r["dir_ant"])}'
                   + (f' {r["conv_ant"]}' if cna else "") + '</span>')
        mark = ('<span class="chgm" title="cambió">•</span>' if r.get("cambio") else "")
        tr.append(
            f'<tr><td class="pc">{esc(r["label"])}</td>'
            f'<td>{_senal_cell(r["tecnico"])}</td>'
            f'<td>{_senal_cell(r["macro"])}</td>'
            f'<td class="pa">{act}</td>'
            f'<td class="pm">{ant}{mark}</td></tr>')
    return (f'<div style="overflow-x:auto"><table class="posic">'
            f'<thead><tr><th>Dimensión</th><th>Señales técnicas</th>'
            f'<th>Señales macro</th><th>Inclinación actual</th><th>Mes anterior</th>'
            f'</tr></thead><tbody>{"".join(tr)}</tbody></table></div>')


# --------------------------------------------------------- LA LECTURA (corta)
def _clima_linea(snap: dict) -> str:
    """Una línea. Estado, percentil, movimiento y de dónde viene el movimiento."""
    t, r = snap["titular"], snap["riesgo"]
    d1, d3 = r.get("d1m"), r.get("d3m")
    use1 = (not np.isfinite(d3)) or (np.isfinite(d1) and abs(d1) >= abs(d3))
    d = d1 if use1 else d3
    per = "un mes" if use1 else "tres meses"
    if not np.isfinite(d) or abs(d) < 3:
        cola = "estable"
    else:
        causa = snap.get("clima_causa") or []
        por = f", por {_lista_es(causa)}" if causa else ""
        cola = (f'{"deteriorándose" if d < 0 else "mejorando"}: '
                f'{es_num("{:+.0f}".format(d))} puntos en {per}{por}')
    return (f'<p class="clima">Riesgo <b>{esc(t["estado"] or "—")}</b> '
            f'({p_str(t["hist_pct"])}), {esc(cola)}.</p>')


def _lectura_inclinaciones(postura: list[dict]) -> str:
    """Siete entradas de dos líneas: la conclusión (clase · dirección ·
    convicción) y, debajo, la EVIDENCIA (indicadores concretos con su nivel, y
    lo que limita la convicción cuando no es alta)."""
    orden = {"alta": 0, "media": 1, "baja": 2, None: 3}
    filas = []
    for p in sorted(postura, key=lambda x: (orden.get(x.get("conviccion"), 3),
                                            x["label"])):
        conv = p.get("conviccion")
        if conv:
            concl = (f'<span class="lc">{esc(p["label"])}</span> · '
                     f'<b>{esc(p["direccion"])}</b> · '
                     f'<span class="cv c{_CONV_N[conv]}">{conv}</span>')
        else:
            concl = (f'<span class="lc">{esc(p["label"])}</span> · '
                     f'<span class="ineu">neutral</span>')
        filas.append(f'<div class="lin"><div class="l1">{concl}</div>'
                     f'<div class="l2">{es_num(esc(p["razon"]))}</div></div>')
    return f'<div class="incl">{"".join(filas)}</div>'


def _cambios_corto(snap: dict) -> str:
    """Máximo cuatro líneas: solo cambios de dirección o de convicción. Si no
    cambió nada, una línea diciéndolo."""
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        return '<p class="camb-none">Primer snapshot con memoria: nada con que comparar.</p>'
    prev = fecha_larga(c["fecha_prev"]) if c.get("fecha_prev") else "el anterior"
    def _por(d):
        return f' — {es_num(esc(d["por"]))}' if d.get("por") else ""
    items = []
    for d in c.get("dir_cambios", []):
        items.append(f'<li class="mv"><b>{esc(d["clase"])}</b>: {esc(d["de"])} → '
                     f'<b>{esc(d["a"])}</b>{_por(d)}</li>')
    for d in c.get("conv_cambios", []):
        cls = "up" if d["subio"] else "dn"
        items.append(f'<li class="{cls}"><b>{esc(d["clase"])}</b>: convicción '
                     f'{esc(d["de"] or "neutral")} → <b>{esc(d["a"] or "neutral")}</b>'
                     f'{_por(d)}</li>')
    if not items:
        return (f'<p class="camb-none">Sin cambios de inclinación ni de convicción '
                f'desde {esc(prev)}.</p>')
    extra = ""
    if len(items) > 4:
        extra = (f'<li class="mas">y {len(items) - 4} '
                 f'cambio{"s" if len(items) - 4 != 1 else ""} más — en el tablero</li>')
        items = items[:4]
    return f'<ul class="camb">{"".join(items)}{extra}</ul>'


def _rompe_bloque(snap: dict) -> str:
    """Dos líneas: el indicador o condición concreta que voltearía la lectura,
    con su número."""
    cs = snap.get("contradicciones") or []
    if cs:
        c = cs[0]
        cond = ""
        if c.get("umbral") and c.get("sentido"):
            s = c["sentido"].replace("volver ", "")
            cond = f' Deja de tensar {esc(s)} {es_num(esc(c["umbral"]))}.'
        return (f'<p class="rompe"><b>Qué rompería esta lectura.</b> '
                f'{esc(c["label"])}, hoy {es_num(esc(c["valor"]))} '
                f'({p_str(c["pct"])}).{cond}</p>')
    exs = snap.get("extremos") or []
    if exs:
        e = exs[0]
        return (f'<p class="rompe"><b>Qué rompería esta lectura.</b> '
                f'{esc(e["label"])} saliendo de su extremo, hoy '
                f'{es_num(esc(e["valor"]))} ({p_str(e["pct"])}).</p>')
    return ('<p class="rompe"><b>Qué rompería esta lectura.</b> Ningún indicador '
            'aislado la domina hoy; la giraría un cambio de rumbo del eje de riesgo.</p>')


# Las clases que se resumen en la lectura, y sus nombres para la discrepancia.
_ANALOG_LECT = ["rv", "dur", "oro"]
# Los nombres salen de la misma tabla que la matriz: un tema no puede llamarse
# de dos maneras en el mismo documento (SEMANTIC-PASS 40).
_ANALOG_NOMBRE = dict(
    {k: config.dimension_breve(k) for k in ("rv", "dur", "oro", "mp", "cicl", "usd")},
    ig="Grado de inversión", hy="Alto rendimiento")
def _analog_cons(a: dict) -> dict:
    return {c["clave"]: c for c in ((a or {}).get("consistencia") or [])}


def _consist_desc(c: dict) -> str:
    """La consistencia direccional primero; la magnitud, como rango, después.
    Con muestras pequeñas el signo es más estable que la media."""
    n, nu, nd = c["n"], c["n_up"], c["n_dn"]
    rng = (f'({es_num("{:+.0f}".format(c["min"]))} % a '
           f'{es_num("{:+.0f}".format(c["max"]))} %)')
    if not c["patron"]:
        return f"sin patrón consistente (subió en {nu} de {n}, cayó en {nd})"
    if nu == n:
        return f"subió en {n} de {n} episodios {rng}"
    if nd == n:
        return f"cayó en {n} de {n} episodios {rng}"
    if nu >= nd:
        return f"{nu} de {n} al alza {rng}"
    return f"{nd} de {n} a la baja {rng}"


def _analog_disc_frase(snap: dict) -> str:
    """REDACCIÓN, no decisión. Quién discrepa y por qué lo decide la capa
    DecisionState (snapshot/decision.py); aquí solo se escribe la frase, y se
    combinan las clases que comparten lectura y sentido."""
    ds = snap.get("decision")
    casos = list(getattr(ds, "analogos", {}).get("discrepancias") or []) if ds else []
    if not casos:
        return ""
    if len(casos) == 1:
        d = casos[0]
        verbo = "subió" if d.signo > 0 else "cayó"
        return (f"Los análogos discrepan en {d.nombre}: nuestra lectura es "
                f"{es_num(d.lectura)} y en episodios parecidos {verbo}.")
    from itertools import groupby
    casos.sort(key=lambda d: (d.lectura, d.signo))
    partes = []
    for (lect, sg), grp in groupby(casos, key=lambda d: (d.lectura, d.signo)):
        nombres = [g.nombre for g in grp]
        plural = len(nombres) > 1
        verbo = ("subieron" if plural else "subió") if sg > 0 else ("cayeron" if plural else "cayó")
        amb = "ambos" if len(nombres) == 2 else "todos" if len(nombres) > 2 else ""
        pre = f"en {amb} " if amb else ""
        partes.append(f"en {_lista_es(nombres)}, {pre}nuestra lectura es {es_num(lect)} y en "
                      f"episodios parecidos {verbo}")
    return "Los análogos discrepan: " + "; ".join(partes) + "."


def _analog_causa(a: dict) -> str:
    return a.get("causa_txt") or (a.get("nulo_razon") or [""])[0]


def _analog_ventana(a: dict) -> str:
    """La ventana de análogos elegibles REAL, tomada del dato -- nunca una
    constante. El universo empieza cuando los siete pilares (y sus deltas)
    existen, y termina doce meses antes de la fecha, que es lo que hace falta
    para saber «qué pasó después». No es la historia del panel: en 2008 son 2.5
    años (2005-2007), no 21."""
    m = a.get("muestra") or {}
    anos, desde, hasta = m.get("anos"), m.get("desde"), m.get("hasta")
    if not (anos and desde is not None and hasta is not None):
        return "la ventana analizada"
    return (f"los {es_num(f'{anos:.1f}')} años analizados "
            f"({desde.year}–{hasta.year})")


def _analog_inusual_txt(a: dict, n: int) -> tuple[str, str]:
    """(cuerpo, cola) del estado inusual, en texto plano. Ninguno comparable por
    dinámica lejana se dice distinto que pocos por entorno."""
    causa = _analog_causa(a)
    con_causa = f", {es_num(causa)}" if causa else ""
    if n == 0:
        if a.get("motivo") == "dinamica":
            det = (f"sin episodios comparables en {_analog_ventana(a)} — el comportamiento de los "
                   f"mercados no tiene precedente cercano (el más parecido difiere "
                   f"{a.get('nearest', 0):.0f} puntos por fuerza)")
        else:
            det = f"sin episodios comparables en {_analog_ventana(a)}{con_causa}"
        return det, ""
    pl = "episodio comparable" if n == 1 else "episodios comparables"
    return (f"solo {n} {pl} en {_analog_ventana(a)}{con_causa}",
            " Un solo desenlace no es muestra; las fechas están en el tablero.")


def _analogos_lectura_html(snap: dict) -> str:
    """Consistencia direccional por clase, no un promedio; y cuando hay pocos
    comparables, el estado inusual con su causa, que informa más que cualquier
    media forzada."""
    a = snap.get("analogos") or {}
    if not a.get("disponible"):
        return ""
    if a.get("ventana_corta"):
        # No es que hoy sea raro: es que NO HAY CON QUE COMPARAR. Se dice arriba
        # y no se publica ningún resultado -- ni medias, ni rangos.
        return (f'<p class="afuerte"><b>Ventana de comparación limitada:</b> '
                f'{_analog_ventana(a)}. Los análogos no son informativos en esta '
                f'fecha y no se publican resultados.</p>')
    if a.get("sin_analogos") or a.get("inusual"):
        n = 0 if a.get("sin_analogos") else a.get("n_comparables", 0)
        det, cola = _analog_inusual_txt(a, n)
        return f'<p class="afuerte"><b>Estado inusual:</b> {det}{cola}</p>'
    cons = _analog_cons(a)
    n, H = a.get("n_comparables", 0), a.get("horizonte", 12)
    lis = []
    for clave in _ANALOG_LECT:
        c = cons.get(clave)
        if c:
            lis.append(f'<li><b>{esc(_ANALOG_NOMBRE[clave])}:</b> {es_num(_consist_desc(c))}</li>')
    if not lis:
        return ""
    out = (f'<div class="afuerte"><b>Análogos: {n} episodios comparables (≥12 meses entre '
           f'sí), a {H} meses.</b> No es un pronóstico: es lo que pasó entonces, y cada vez '
           f'fue distinto.<ul class="anlist">{"".join(lis)}</ul></div>')
    frase = _analog_disc_frase(snap)
    if frase:
        out += f'<p class="adisc">{es_num(esc(frase))}</p>'
    return out




# ============================================================================
# FASE 2 - GUIA DE DECISION (SPEC 4.2). Todo sale del DecisionState: aqui no se
# decide nada, solo se escribe.
# ============================================================================

_HZ_ES = {"tactical": "táctico", "intermediate": "intermedio", "estructural": "estructural",
          "—": "—", "sin dato": "sin dato"}
_TIMING_CLS = {"confirmado": "t-ok", "favorable": "t-ok", "paciente": "t-warn",
               "esperar": "t-warn", "extendido": "t-warn", "contrario": "t-adv",
               "reversion": "t-adv", "neutral": "t-neu"}


def _guia(snap):
    ds = snap.get("decision")
    return (getattr(ds, "guia", {}) or {}) if ds else {}


def _estado_ciclo(nivel) -> str:
    """El eje de ciclo no pasa por la maquina de estados (esa gobierna el eje de
    riesgo): su etiqueta sale de su propio nivel, con las palabras que ya declara
    la configuracion del eje."""
    spec = config.AXES["ciclo"]
    if nivel is None or not np.isfinite(nivel):
        return "sin dato"
    if nivel >= 55:
        return spec["high"]
    if nivel <= 45:
        return spec["low"]
    return "neutral"


def _cap_es(t: str) -> str:
    return (t[0].upper() + t[1:]) if t else t


def _dur_corta(detalle: str) -> str:
    """La duracion que ya trae el detalle, sin repetir los niveles.

    El orden de la alternancia importa: con «semana» delante, la expresion casa
    el singular dentro de «semanas» y el texto sale «4 semana».
    """
    m = re.search(r"(\d+\s+(?:semanas|semana|meses|mes|años|año|días|día))", detalle or "")
    return m.group(1) if m else ""


def _posicion_guide_html(snap: dict) -> str:
    """3) Positioning Guide (SPEC 4.2). Contenido dinámico, nada hardcodeado."""
    from snapshot import decision as _d
    g = _guia(snap)
    temas = g.get("temas") or []
    if not temas:
        return ""
    pos = {r["key"]: r for r in (snap.get("posicionamiento") or [])}
    tr = []
    for t in temas:
        r = pos.get(t["key"], {})
        rail = _pgrid_bar(r.get("paso", t.get("paso", 0)), r.get("paso_ant"))
        cn = _CONV_N.get(t.get("conviccion"))
        conv = (f'<span class="cv c{cn}">{t["conviccion"]}</span>' if cn
                else '<span class="ineu">—</span>')
        # La columna dice la señal tactica que APLICA a este tema. Casi siempre
        # es la del tablero; cuando el tema tiene evidencia tactica propia que
        # dice otra cosa, se escribe el contraste entero.
        #
        # SEMANTIC-PASS 40: con el vocabulario de `senal_txt`, el mismo que la
        # capa PM. Esta tabla se quedo diciendo «Acompaña con reservas» y «el
        # global:» cuando la matriz de arriba ya decia «mayormente a favor»:
        # es el mismo campo, y dos nombres en el mismo documento se leen como
        # dos cosas distintas.
        tt, reserva = _d.senal_txt(t.get("timing"), t.get("senal_detalle"))
        tim = (f'<span class="{_TIMING_CLS.get(t.get("timing"), "t-neu")}">'
               f'{esc(tt)}</span>')
        if reserva:
            tim += f'<span class="tdif">Reserva: {es_num(esc(reserva))}</span>'
        if t.get("timing_override"):
            gl = _d.senal_txt(t.get("timing_global"), g.get("senal_detalle"))[0]
            tim += (f'<span class="tdif" title="{esc(t.get("timing_nota") or "")}">'
                    f'en el conjunto del tablero: {esc(gl)}</span>')
        nota = r.get("nota") or ""
        # SPEC 3.1: si no hay evidencia del propio pilar, la fila lo dice. Que la
        # sostenga solo la familia común es una propiedad de la inclinación, no
        # una carencia del formato.
        if t.get("sin_evidencia_propia"):
            conv += '<span class="tdif">sin evidencia propia del tema</span>'
        # SPEC-4P 15: el horizonte dominante va en la cabecera; en la fila solo
        # se anota el que se sale. Una columna con «intermedio» siete veces es
        # ruido con forma de dato.
        if t["horizonte"] != g.get("horizonte_dominante"):
            conv += (f'<span class="tdif">horizonte '
                     f'{esc(_HZ_ES.get(t["horizonte"], t["horizonte"]))}</span>')
        tr.append(
            f'<tr><td class="gc">{esc(t["label"])}</td>'
            f'<td class="gbar" data-l="Postura">{rail}'
            f'<span class="etq2">{esc(t.get("sesgo") or t["postura"])}</span></td>'
            f'<td class="gdt" data-l="{esc(config.CONVICCION_PM)}">{conv}</td>'
            f'<td class="gtim" data-l="{esc(config.SENAL_ETIQUETA)}">{tim}</td>'
            f'<td class="fav" data-l="Expresión preferida">{_expr_html(t.get("favorecer"))}'
            + (f'<span class="gnota">{es_num(esc(nota))}</span>' if nota else "")
            + (f'<span class="riesgo">Evitar: '
               f'{esc((t.get("evitar") or {}).get("text") or "")}</span>'
               if t.get("evitar_util") else "")
            + '</td></tr>')
    fam = g.get("familia") or {}
    nota_fam = ""
    if fam.get("existe"):
        nota_fam = (f'<div class="hallazgo"><span class="k">Voces independientes'
                    f'</span><p>{es_num(esc(fam["texto"]))} Son inclinaciones '
                    f'distintas apoyadas en la misma evidencia: <b>no suman '
                    f'{len(temas)} confirmaciones independientes.</b></p></div>')
    return (f'<div style="overflow-x:auto"><table class="pguide">'
            f'<thead><tr><th>Tema</th>'
            f'<th class="thpos">Postura <span class="thk">adverso ◄&nbsp;&nbsp;► favorable '
            f'· ● hoy · ○ mes ant.</span></th>'
            f'<th>{esc(config.CONVICCION_PM)}</th>'
            f'<th>{esc(config.SENAL_ETIQUETA)}</th>'
            f'<th>Expresión preferida</th></tr></thead>'
            f'<tbody>{"".join(tr)}</tbody></table></div>'
            f'<p class="note">La señal táctica de una fila es la del tablero '
            f'salvo que la fila diga otra cosa: cuando el tema tiene evidencia '
            f'táctica propia que apunta distinto, debajo se escribe qué dice el '
            f'conjunto. Una fila sin esa línea sigue a la general.</p>{nota_fam}')


def _expr_html(e, con_fuente: bool = True) -> str:
    """Una expresión se publica CON su procedencia. Sin señales que la sostengan
    no se publica: «—».

    La procedencia se escribe UNA vez por fila, bajo «Favorecer». En «Evitar» es
    la misma evidencia leída del otro lado, y repetirla convertía la columna en
    ruido: el mismo paréntesis diez veces en la tabla."""
    if not isinstance(e, dict) or not e.get("supported_by"):
        return '<span class="ineu">—</span>'
    if not con_fuente:
        return f'<span class="expr">{esc(e["text"])}</span>'
    apo = ", ".join(e.get("supported_labels") or [])
    return (f'<span class="expr" title="Se apoya en: {esc(apo)} · convicción '
            f'{esc(str(e.get("confidence") or "—"))}">{esc(e["text"])}</span>'
            f'<span class="expsrc">{esc(apo)}</span>')


def _regimen_tactico_html(snap: dict) -> str:
    """4) Régimen dominante vs setup táctico. Una condición contraria NO es un
    cambio de régimen, y el documento tiene que decirlo así."""
    g = _guia(snap)
    if not g:
        return ""
    pg = snap.get("postura_general") or {}
    setup = g.get("setup") or {}
    hz = g.get("horizontes_lectura") or {}
    path = g.get("path") or {}

    linea_hz = " · ".join(
        f'<b>{_HZ_ES.get(k, k)}</b>: {esc(v["lectura"])}'
        + (f' <em>({lvl_str(v["nivel"])})</em>' if v.get("nivel") is not None else "")
        for k, v in hz.items())

    if path.get("disponible") and path.get("meses"):
        pth = (f'{esc(path["postura"])} · {path["meses"]} '
               f'{"mes" if path["meses"] == 1 else "meses"} · {esc(path["estado"])}')
    elif path.get("disponible"):
        pth = f'{esc(path.get("postura", "—"))} · sin cambio en los últimos 18 meses'
    else:
        pth = "no disponible"

    cls = "setup-on" if setup.get("existe") else "setup-off"
    # SPEC-2P 9: la señal que acompaña al régimen y la que va en su contra no
    # se llaman igual, porque no se usan igual.
    titulo_bloque = setup.get("clase_titulo") or "Señal táctica"
    contra = (' <span class="cregi">va contra el régimen</span>'
              if setup.get("contra_regimen") else "")
    return (f'<div class="rt">'
            f'<div class="rt-b"><div class="rt-h">Régimen dominante</div>'
            f'<p class="rt-p"><b>{esc(pg.get("palabra", "—"))}</b>, '
            f'{esc(config.CONVICCION_PM.lower())} '
            f'{esc(pg.get("conviccion", "—"))}. {linea_hz}.</p>'
            f'<p class="rt-s">Persistencia: {pth}</p></div>'
            f'<div class="rt-b {cls}"><div class="rt-h">{esc(titulo_bloque)}{contra}</div>'
            f'<p class="rt-p"><b>{esc(setup.get("titulo", "—"))}</b>: '
            f'{es_num(esc(setup.get("texto", "")))}.</p>'
            f'<p class="rt-s">{esc(setup.get("clase_nota") or "")} Una condición '
            f'táctica contraria no cambia el régimen; cambia el momento de '
            f'actuar.</p></div></div>')


_TRIG_TIT = {"confirma": "Confirma", "debilita": "Debilita",
             "invalida": "Invalida / revierte", "tactico": "Oportunidad táctica"}


def _triggers_html(snap: dict) -> str:
    """5) Decision triggers: los cuatro bloques, con alcanzabilidad (SPEC 6)."""
    g = _guia(snap)
    trg = g.get("triggers") or {}
    if not trg:
        return ""
    blo = []
    for b in ("confirma", "debilita", "invalida", "tactico"):
        items = trg.get(b) or []
        if not items:
            li = '<li class="tg-none">sin disparador identificado hoy</li>'
        else:
            li = ""
            for t in items:
                alc = t.get("alcance") or ""
                mal = (t.get("alcanzable") is False)
                ya = t.get("ya")
                li += (f'<li><span class="tg-v">{es_num(esc(t["variable"]))}</span> '
                       f'<span class="tg-a">{es_num(esc(str(t["actual"])))}</span> '
                       f'<span class="tg-c">{es_num(esc(t["condicion"]))}</span>'
                       f'<span class="tg-e">→ {es_num(esc(t["efecto"]))}</span>'
                       f'<span class="tg-m{" bad" if mal else ""}">'
                       f'{_HZ_ES.get(t.get("horizonte"), "")} · '
                       f'confirmación {esc(t.get("persistencia", "—"))} · '
                       f'{esc(alc)}{" · ya activado" if ya else ""}</span></li>')
        blo.append(f'<div class="tg-b tg-{b}"><div class="tg-h">{_TRIG_TIT[b]}</div>'
                   f'<ul class="tg-l">{li}</ul></div>')
    return f'<div class="tg">{"".join(blo)}</div>'


def _what_changed_html(snap: dict) -> str:
    """6) What changed: cambios que afectan DECISIONES, no numéricos."""
    g = _guia(snap)
    wc = g.get("what_changed") or []
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        return ('<p class="note">No hay snapshot previo con el que comparar: '
                'esta sección aparece a partir del segundo.</p>')
    if not wc:
        return ('<p class="note">Sin cambios que afecten a una decisión desde '
                f'{esc(fecha_larga(c["fecha_prev"]))}. Que no cambie nada también '
                'es información.</p>')
    return ('<ul class="wc">'
            + "".join(f'<li>{es_num(esc(x))}</li>' for x in wc[:6])
            + '</ul>')


def _mandate_html() -> str:
    """7) Mandate translation: tabla FIJA y metodológica (SPEC 9). No se genera
    por snapshot, no se personaliza, no cambia con los datos."""
    tr = "".join(
        f'<tr><td class="mc">{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>'
        for a, b, c in config.MANDATE_TRANSLATION)
    return (f'<div style="overflow-x:auto"><table class="mand">'
            f'<thead><tr><th>Señal</th><th>Growth / oportunista</th>'
            f'<th>Preservación de capital</th></tr></thead>'
            f'<tbody>{tr}</tbody></table></div>'
            f'<p class="note">Tabla de referencia, fija: no se genera por snapshot '
            f'ni se personaliza. El modelo produce la señal; el mandato decide '
            f'cuánto riesgo se asigna. No son pesos de cartera.</p>')


def _cluster_html(snap: dict) -> str:
    """SPEC 10: métrica PARALELA, solo auditoría. No decide nada."""
    g = _guia(snap)
    cs = g.get("cluster_score") or []
    if not cs:
        return ""
    tr = "".join(
        f'<tr><td class="cl2">{esc(c["label"])}</td>'
        f'<td>{c["crudo"]:+d}</td><td>{c["cluster"]:+.0f}</td>'
        f'<td>{c["n_grupos"]}</td>'
        f'<td>{"sí" if c["cambiaria"] else "no"}</td></tr>' for c in cs)
    n = sum(1 for c in cs if c["cambiaria"])
    return (f'<div style="overflow-x:auto"><table class="deriv">'
            f'<thead><tr><th>Clase</th>'
            f'<th title="Un indicador, un voto">Voto crudo</th>'
            f'<th title="Un grupo de correlación, un voto">Voto por cluster</th>'
            f'<th>Grupos</th><th>¿Cambiaría la dirección?</th></tr></thead>'
            f'<tbody>{tr}</tbody></table></div>'
            f'<p class="note">Métrica <b>paralela</b>, solo para comparar los dos '
            f'sistemas de recuento. <b>No decide nada</b>: la dirección publicada '
            f'sigue saliendo del voto por indicador. Hoy diferirían {n} de '
            f'{len(cs)} temas. Aviso al leerla: el voto por cluster es un signo '
            f'crudo y <b>no pasa por el filtro de convicción</b>, así que casi '
            f'toda diferencia es «neutral → dirección», no un cambio de lado. '
            f'En 224 tema-fechas entre 2011 y 2025 no hubo ni un solo giro '
            f'mas↔menos.</p>')



def _expr_md(e, con_fuente: bool = True) -> str:
    """La expresión con su procedencia, en Markdown. Sin señales que la apoyen
    no hay expresión, y la procedencia se escribe una sola vez por fila."""
    if not isinstance(e, dict) or not e.get("supported_by"):
        return "—"
    if not con_fuente:
        return e["text"]
    apo = ", ".join(e.get("supported_labels") or [])
    return f"{e['text']} *({apo})*"


def _md_guia(snap, A):
    """Las secciones de la guia de decision, en el archivo Markdown. Mismo
    DecisionState que el HTML: no puede decir nada distinto."""
    g = _guia(snap)
    if not g:
        return
    ds = snap["decision"]
    t = snap["titular"]
    pg = snap.get("postura_general") or {}
    ten = snap.get("tension_principal")
    riesgo, ciclo = ds.ejes.get("riesgo"), ds.ejes.get("ciclo")

    A("**Investment Decision Guide**")
    A("")
    # SPEC-2P 5: la tensión DOMINANTE es estructural y encabeza; el indicador
    # que más contradice es un dato suelto que la ilustra. El .md dice las dos,
    # igual que el HTML: no pueden contar cosas distintas.
    dom = snap.get("tension_dominante")
    ind = ten or snap.get("tension_contexto")
    A(f"| Régimen de riesgo | Régimen de ciclo | Postura | Convicción | Timing | "
      f"Horizonte | {config.TENSION_DOMINANTE} | {config.TENSION_INDICADOR} |")
    A("|---|---|---|---|---|---|---|---|")
    _trn = t.get("transicion_txt")
    A(f"| {t['estado']} ({p_str(riesgo.hist_pct)}{'; ' + _trn if _trn else ''}) "
      f"| {_estado_ciclo(ciclo.nivel)} ({lvl_str(ciclo.nivel)}/100) "
      f"| **{pg.get('palabra','—')}** | {pg.get('conviccion','—')} "
      f"| {config.timing_frase(g.get('timing'))} "
      f"| {_HZ_ES.get(g.get('horizonte_dominante'),'—')} "
      f"| {es_num(dom['texto']) + ' (' + es_num(dom['detalle']) + ')' if dom else 'sin tensión dominante'} "
      f"| {es_num(config.SHORT.get(ind['key'], ind['label'])) + ' ' + p_str(ind['pct']) if ind else 'ninguno en extremo persistente'} |")
    A("")
    A("*La tensión dominante es una contradicción estructural entre bloques; el "
      "indicador que más contradice es un dato suelto que la ilustra. No son lo "
      "mismo y no se deduce uno del otro.*")
    A("")


def _md_guia_tablas(snap, A):
    g = _guia(snap)
    if not g:
        return
    # --- positioning guide
    temas = g.get("temas") or []
    if temas:
        A("## Guía de posicionamiento")
        A("")
        A("| Tema | Postura | Convicción | Timing | Horizonte | Favorecer | "
          "Evitar / reducir |")
        A("|---|---|---|---|---|---|---|")
        for t in temas:
            tt = config.timing_frase(t.get("timing"))
            if t.get("timing_override"):
                gl = config.TIMING_CABEZA.get(t.get("timing_global"), "—").lower()
                tt += f" (el global: {gl})"
            cv = t.get("conviccion") or "—"
            if t.get("sin_evidencia_propia"):
                cv += " · sin evidencia propia del tema"
            A(f"| {t['label']} | {t['postura']} | {cv} "
              f"| {tt} | {_HZ_ES.get(t['horizonte'], t['horizonte'])} "
              f"| {_expr_md(t.get('favorecer'))} "
              f"| {_expr_md(t.get('evitar'), con_fuente=False)} |")
        A("")
        fam = g.get("familia") or {}
        if fam.get("existe"):
            A(f"**{es_num(fam['texto'])}** Son inclinaciones distintas apoyadas en "
              f"la misma evidencia: no suman {len(temas)} confirmaciones "
              f"independientes.")
            A("")
        A("*Postura, convicción y timing son tres dimensiones distintas. El timing se "
          "deriva solo de indicadores de horizonte táctico y el que manda es el global: "
          "un tema solo lleva el suyo («propio») cuando tiene evidencia táctica que lo "
          "sostenga. «Favorecer» es una expresión relativa dentro del tema, no una orden "
          "de compra, y se publica con las señales que la apoyan: sin ninguna no se "
          "publica. Aquí no hay pesos de cartera.*")
        A("")

    # --- regimen vs tactico
    setup = g.get("setup") or {}
    hz = g.get("horizontes_lectura") or {}
    path = g.get("path") or {}
    A("## Régimen y táctica")
    A("")
    A(f"- **Régimen dominante:** {(snap.get('postura_general') or {}).get('palabra','—')}, "
      f"confianza {(snap.get('postura_general') or {}).get('conviccion','—')}. "
      + " · ".join(f"{_HZ_ES.get(k,k)}: {v['lectura']}"
                   + (f" ({v['nivel']:.0f})" if v.get("nivel") is not None else "")
                   for k, v in hz.items()) + ".")
    if path.get("disponible"):
        dur = (f"{path['meses']} {'mes' if path['meses']==1 else 'meses'}"
               if path.get("meses") else "sin cambio en 18 meses")
        A(f"- **Persistencia:** {path['postura']} · {dur} · {path['estado']}.")
    else:
        A("- **Persistencia:** no disponible.")
    A(f"- **{setup.get('clase_titulo') or 'Señal táctica'}:** {setup.get('titulo','—')}"
      + (f" — {es_num(setup.get('texto',''))}" if setup.get("texto") else "") + ".")
    A("- *Una condición táctica contraria no cambia el régimen; cambia el momento de actuar.*")
    A("")

    # --- triggers
    trg = g.get("triggers") or {}
    if trg:
        A("## Disparadores de decisión")
        A("")
        for b, tit in (("confirma", "Confirma"), ("debilita", "Debilita"),
                       ("invalida", "Invalida / revierte"),
                       ("tactico", "Oportunidad táctica")):
            A(f"**{tit}**")
            A("")
            items = trg.get(b) or []
            if not items:
                A("- sin disparador identificado hoy")
            for x in items:
                alc = x.get("alcance") or ""
                mal = ""
                A(f"- {es_num(x['variable'])} (hoy {es_num(str(x['actual']))}) "
                  f"{es_num(x['condicion'])} → {es_num(x['efecto'])} "
                  f"· {_HZ_ES.get(x.get('horizonte'),'')} "
                  f"· confirmación {x.get('persistencia','—')} · {alc}{mal}")
            A("")

    # --- what changed
    A("## Qué cambió")
    A("")
    wc = g.get("what_changed") or []
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        A("No hay snapshot previo con el que comparar.")
    elif not wc:
        A(f"Sin cambios que afecten a una decisión desde {fecha_larga(c['fecha_prev'])}.")
    else:
        for x in wc[:6]:
            A(f"- {es_num(x)}")
    A("")


def _md_mandato(A):
    A("## Traducción por mandato")
    A("")
    A("| Señal | Growth / oportunista | Preservación de capital |")
    A("|---|---|---|")
    for a, b, c in config.MANDATE_TRANSLATION:
        A(f"| {a} | {b} | {c} |")
    A("")
    A("*Tabla de referencia, fija: no se genera por snapshot ni se personaliza. El modelo "
      "produce la señal; el mandato decide cuánto riesgo se asigna. No son pesos de cartera.*")
    A("")

# ------------------------------------------------------------------- HTML
# ===========================================================================
# QUINTA PASADA — EL HTML COMO ESPACIO DE TRABAJO
# ===========================================================================
# El PDF se lee; el HTML se usa. Lo que sigue no anade informacion: reordena la
# que ya hay en seis secciones y la revela por capas, para que nadie tenga que
# recorrer 42 indicadores para saber que piensa el modelo hoy.
#
# Ninguna de estas funciones decide nada. Todas leen del DecisionState.

# Cada seccion declara si esta en la VISTA PM o solo en la COMPLETA. Es un
# atributo del indice, no una copia: el documento es uno y las dos vistas son
# dos presentaciones del mismo DOM (punto 33).
_SECCIONES = [
    ("ahora", "Ahora", "decisión", True),
    ("posicionamiento", "Posicionamiento", "decisión", True),
    ("vigilar", "Qué vigilar", "decisión", True),
    ("historia", "Historia", "contexto", True),
    ("research", "Research", "research", False),
    ("auditoria", "Auditoría", "auditoría", False),
]


def _filtro_html() -> str:
    """Filtro local de los 42 indicadores. Client-side, sin backend y discreto:
    esto es un informe, no una terminal."""
    ops = "".join(f'<option value="{k}">{esc(v["label"])}</option>'
                  for k, v in config.PILLARS.items())
    return (f'<div class="flt" role="search">'
            f'<label class="sr" for="flt-q">Buscar indicador</label>'
            f'<input id="flt-q" type="search" placeholder="Buscar indicador…" '
            f'autocomplete="off">'
            f'<label class="sr" for="flt-p">Pilar</label>'
            f'<select id="flt-p"><option value="">Todos los pilares</option>{ops}</select>'
            f'<label class="sr" for="flt-e">Estado</label>'
            f'<select id="flt-e"><option value="">Cualquier estado</option>'
            f'<option value="favorable">Favorable</option>'
            f'<option value="adverso">Adverso</option>'
            f'<option value="extremo">En extremo</option></select>'
            f'<button type="button" id="flt-x" class="flt-x">Limpiar</button>'
            f'<span id="flt-n" class="flt-n" aria-live="polite"></span></div>')


def _nav_html(snap: dict) -> str:
    """Navegacion lateral fija. Discreta: es un indice, no una aplicacion."""
    from snapshot import decision as _d
    pg = snap.get("postura_general") or {}
    g = _guia(snap)
    tim = _d.senal_txt(g.get("timing"), g.get("senal_detalle"))[0]
    grupos: dict[str, list] = {}
    for sid, lab, fam, pm in _SECCIONES:
        grupos.setdefault(fam, []).append((sid, lab, pm))
    bloques = ""
    for fam, items in grupos.items():
        solo = " solo-full" if not any(pm for _s, _l, pm in items) else ""
        li = "".join(f'<a href="#sec-{sid}" data-sec="{sid}"'
                     f'{"" if pm else " class='solo-full'"}>{esc(lab)}</a>'
                     for sid, lab, pm in items)
        bloques += (f'<div class="nv-g{solo}"><span class="nv-t">{esc(fam)}</span>'
                    f'{li}</div>')
    # El sufijo va escrito, no lo pone el JS: esas secciones pertenecen a la
    # vista completa en los dos modos, y elegirlas cambia de vista.
    opciones = "".join(
        f'<option value="sec-{sid}"{"" if pm else " data-full='1'"}>'
        f'{esc(lab)}{"" if pm else " — vista completa"}</option>'
        for sid, lab, _f, pm in _SECCIONES)
    return (f'<nav class="nv" aria-label="Secciones del informe">'
            f'{_conmutador_html()}'
            f'<div class="nv-d">{esc(fecha_corta(snap["asof"]).upper())}</div>'
            f'<div class="nv-p">{esc((pg.get("palabra") or "—").upper())}</div>'
            f'<div class="nv-s">{esc(pg.get("conviccion", "—"))} · {esc(tim.lower())}</div>'
            f'{bloques}</nav>'
            f'<div class="nv-m"><label for="nv-sel">Secciones</label>'
            f'<select id="nv-sel" aria-label="Ir a una sección">{opciones}</select></div>')


def _conmutador_html() -> str:
    """VISTA PM / VISTA COMPLETA (puntos 19-21, 32).

    Dos botones, no un enlace: cambian el estado de la pagina, no navegan.
    `aria-pressed` dice cual esta puesto, y el foco se ve. El documento abre en
    VISTA PM; la completa esta a un clic y no se pierde nada al volver, porque
    no se duplica ni se borra nada: solo se oculta por CSS.
    """
    return (
        '<div class="vw" role="group" aria-label="Modo de vista">'
        '<button type="button" class="vw-b" data-view="pm" aria-pressed="true">'
        'Vista PM</button>'
        '<button type="button" class="vw-b" data-view="full" aria-pressed="false">'
        'Vista completa</button>'
        '</div>')


def _fuerzas_svg(snap: dict) -> str:
    """Que fuerzas sostienen el regimen y cuales lo frenan.

    Son los MISMOS niveles de pilar que ya publica el tablero, en la misma
    escala orientada 0-100 con 50 = neutral. No se compone nada nuevo: se ponen
    uno debajo de otro para que se vea de un vistazo quien empuja y quien frena,
    que es la pregunta que hoy exige leer siete filas de una tabla.

    POR QUE NO ES UN SVG. Lo fue, y por eso se rompio: con el nombre, la nota y
    la lectura colocados por coordenada dentro de un viewBox fijo, la fila
    entera depende de cuanto mida un texto. "Cond. monetarias" no cabia en su
    carril y salia "41Cond. monetarias" encima de la nota, ademas de cortada
    por la izquierda. Ensanchar el viewBox solo mueve el punto de rotura al
    siguiente nombre largo, o a la primera maquina con otra fuente --y esto es
    un HTML autocontenido que se abre en ordenadores que no conozco--.

    En una rejilla CSS el texto mide lo que mide y las columnas se ajustan.
    Como efecto secundario, el nombre, la nota y la lectura pasan a ser texto
    de verdad: un lector de pantalla lee "Credito 87 Apoya riesgo" sin
    necesidad de que nadie escriba un `aria-label` paralelo que se desincronice.
    Lo unico que sigue siendo dibujo es la barra, que es lo unico que de verdad
    lo es.
    """
    pil = [p for p in snap.get("tablero", []) if np.isfinite(p.get("score", np.nan))]
    if not pil:
        return ""
    pil = sorted(pil, key=lambda p: -p["score"])
    filas = ""
    for p in pil:
        v = float(p["score"])
        cls = ("fav" if p["lectura"] == "favorable"
               else "adv" if p["lectura"] == "adverso" else "neu")
        # La pista es el rango +-50 puntos a todo lo ancho, asi que un punto es
        # un uno por ciento y la barra sale de la mitad hacia su lado.
        if v >= 50:
            geo = f'left:50%;width:{v - 50:.1f}%'
        else:
            geo = f'right:50%;width:{50 - v:.1f}%'
        # §8 y §10: nadie debería tener que deducir si 85 es bueno o malo.
        sig = config.LECTURA_PM.get(p["lectura"], p["lectura"])
        ctx_ = "" if p.get("eje") else ' · contexto'
        filas += (f'<div class="fz-r">'
                  f'<span class="fz-l">'
                  f'{esc(config.PILAR_BREVE.get(p["key"], p["label"]))}</span>'
                  f'<span class="fz-v">{v:.0f}</span>'
                  f'<span class="fz-b"><i class="{cls}" style="{geo}"></i></span>'
                  f'<span class="fz-s">{esc(sig)}{esc(ctx_)}</span></div>')
    return (f'<figure class="fz"><figcaption class="fz-h">Qué está impulsando '
            f'el régimen</figcaption><div class="fz-g">{filas}</div>'
            f'<p class="fz-cap">La marca central es 50, neutral; cuanto más a '
            f'la derecha, más favorable para tomar riesgo.</p></figure>')


def _pilares_contexto_html(snap: dict) -> str:
    """QUE MIDE / QUE DICE HOY / POR QUE IMPORTA, pilar a pilar (SEM-PASS 12).

    El grafico de fuerzas dice «Condiciones monetarias 40, frena riesgo» y da
    por sabido que el lector sabe que hay dentro de ese 40 y por que deberia
    importarle. Las tres columnas ya existen en `config.PILLARS` --desc,
    lectura del dia, importa-- y hasta ahora solo se publicaban en Research,
    que es justo donde el lector que necesita la definicion no va a mirar.

    Va en la capa PM, plegado: quien ya sabe lo que mide cada pilar no lo abre.
    """
    pil = [p for p in snap.get("tablero", [])
           if np.isfinite(p.get("score", np.nan))]
    if not pil:
        return ""
    filas = ""
    for p in sorted(pil, key=lambda p: -p["score"]):
        meta = config.PILLARS.get(p["key"], {})
        sig = config.LECTURA_PM.get(p["lectura"], p["lectura"])
        cls = ("f-fav" if p["lectura"] == "favorable"
               else "f-adv" if p["lectura"] == "adverso" else "f-neu")
        ctx_ = ("" if p.get("eje") else
                '<span class="pc-ctx">no vota dirección; es contexto</span>')
        filas += (
            f'<div class="pc-f">'
            f'<div class="pc-n">{esc(config.PILAR_NOMBRE.get(p["key"], p["label"]))}'
            f'{ctx_}</div>'
            f'<div class="pc-q">{esc(meta.get("desc") or "")}</div>'
            f'<div class="pc-h"><b>{p["score"]:.0f}</b>/100 · '
            f'<span class="{cls}">{esc(sig)}</span></div>'
            f'<div class="pc-i">{esc(meta.get("importa") or "")}</div>'
            f'</div>')
    return (f'<details class="mas pc-d"><summary>Qué mide cada fuerza y por qué '
            f'importa</summary>'
            f'<div class="pc-hd"><span>Fuerza</span><span>Qué mide</span>'
            f'<span>Qué dice hoy</span><span>Por qué importa</span></div>'
            f'<div class="pc">{filas}</div></details>')


def _pilar_corto(label: str) -> str:
    """El pilar, sin la coletilla: en una barra no cabe «y condiciones...»."""
    return label.split(" y ")[0]


def _cockpit_html(snap: dict) -> str:
    """Seccion 01 — AHORA. Lo que el modelo piensa, sin scroll."""
    g = _guia(snap)
    pg = snap.get("postura_general") or {}
    ds = snap["decision"]
    t = snap["titular"]
    riesgo, ciclo = ds.ejes.get("riesgo"), ds.ejes.get("ciclo")
    hz = _HZ_ES.get(g.get("horizonte_dominante"), "—")

    # SEMANTIC-PASS 31: la vista abre con la conclusión y sus cuatro
    # calificadores, cada uno con su nombre. Antes eran varias cifras sin
    # explicar y una palabra --«timing»-- que no decía de qué momento hablaba.
    from snapshot import decision as _d
    sen, reserva = _d.senal_txt(g.get("timing"), g.get("senal_detalle"))
    izq = (f'<div class="ck-post">{esc((pg.get("palabra") or "—").upper())}</div>'
           f'<div class="ck-q">'
           f'<span class="ck-qk">{esc(config.CONVICCION_PM)}</span>'
           f'<span class="ck-qv">{esc(pg.get("conviccion", "—"))}</span>'
           f'<span class="ck-qk">Horizonte</span>'
           f'<span class="ck-qv">{esc(hz)}</span>'
           f'<span class="ck-qk">{esc(config.SENAL_ETIQUETA)}</span>'
           f'<span class="ck-qv"><span class="'
           f'{_TIMING_CLS.get(g.get("timing"), "t-neu")}">{esc(sen)}</span>'
           + (f'<span class="ck-res">{es_num(esc(reserva))}</span>' if reserva else "")
           + f'</span></div>'
           f'<div class="ck-regs">'
           + _regimen_html(t, riesgo)
           + f'<span><b>Ciclo</b> {esc(_estado_ciclo(ciclo.nivel)) if ciclo else "—"} '
           f'<em>{lvl_str(ciclo.nivel) if ciclo else "—"}/100</em></span></div>'
           + _porque_html(snap))
    bl = g.get("bottom_line") or ""
    if bl:
        izq += (f'<div class="ck-take"><span class="k">'
                f'{esc(config.TITULOS["takeaway"])}</span><p>{es_num(esc(bl))}</p></div>')
    izq += _cambios_cockpit(snap)

    dom = snap.get("tension_dominante")
    if dom:
        et = dom.get("etiqueta") or config.TENSION_DOMINANTE
        dur = _dur_corta(dom.get("detalle") or "")
        dtxt = (f'{esc(_cap_es(dom["alto_label"]))} <b>{dom["alto_score"]:.0f}</b>'
                f'<span class="vs">↔</span>'
                f'{esc(_cap_es(dom["bajo_label"]))} <b>{dom["bajo_score"]:.0f}</b>'
                + (f'<em class="dur"> · {esc(dur)}</em>' if dur else "")
                + (f'<em class="porq"> {esc(dom["por_que"])}</em>'
                   if dom.get("por_que") else ""))
    else:
        et, dtxt = config.TENSION_DOMINANTE, '<em>sin tensión dominante</em>'
    ind = snap.get("tension_principal") or snap.get("tension_contexto")
    if ind:
        ctxt = "" if snap.get("tension_principal") else ' <em>(contexto)</em>'
        itxt = (f'<a href="#ind-{esc(ind["key"])}" class="ev">'
                f'{es_num(esc(config.SHORT.get(ind["key"], ind["label"])))}</a> '
                f'<b>{es_num(esc(str(ind["valor"])))}</b> '
                f'<em>· {p_str(ind["pct"])}</em>{ctxt}')
    else:
        itxt = '<em>ninguno en extremo persistente</em>'
    der = (f'{_fuerzas_svg(snap)}{_pilares_contexto_html(snap)}'
           f'<div class="ck-t"><span class="k">{esc(et)}</span>'
           f'<span class="v">{dtxt}</span></div>'
           f'<div class="ck-t"><span class="k">{esc(config.TENSION_INDICADOR)}</span>'
           f'<span class="v">{itxt}</span></div>')
    return (f'<div class="cockpit"><div class="ck-l">{izq}</div>'
            f'<div class="ck-r">{der}</div></div>')


def _cambios_registro_html(snap: dict) -> str:
    """El registro completo de cambios, ESTRUCTURADO POR CATEGORIA (punto 11).

    La comparacion larga sigue estando entera debajo; esto es su indice. Una
    lista plana de doce lineas obliga a leerlas todas para saber si alguna es
    de postura; agrupadas, se ve de un vistazo que se movio y que no. Cada
    entrada conserva el ancla a lo que cambio.
    """
    g = _guia(snap)
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        return ('<p class="note">Es el primer snapshot con memoria: no hay uno '
                'anterior con el que compararlo.</p>')
    refs = {x["texto"]: x["ancla"] for x in (g.get("what_changed_ref") or [])}
    por_ind = {d["label"]: d["key"] for d in config.INDICATORS}

    def li(txt, ancla=None):
        a = ancla or refs.get(txt)
        cuerpo = (f'<a href="{esc(a)}">{es_num(esc(txt))}</a>' if a
                  else es_num(esc(txt)))
        return f"<li>{cuerpo}</li>"

    # Tres categorias, las del punto 11: lo que decide, lo que lo señala y lo
    # que lo puede cambiar. Una lista plana obliga a leerla entera para saber
    # si alguna linea era de postura.
    decisiones, senales, trg = [], [], []
    for d in (c.get("dir_cambios") or []):
        decisiones.append(li(f"{d['clase']}: la inclinación pasa de {d['de']} "
                             f"a {d['a']}"))
    for d in (c.get("conv_cambios") or []):
        decisiones.append(li(f"{'↑ ' if d.get('subio') else '↓ '}{d['clase']}: "
                             f"confianza {d['de'] or 'neutral'} → "
                             f"{d['a'] or 'neutral'}"))
    if c.get("estado_de") and c["estado_de"] != c.get("estado_a"):
        decisiones.append(li(f"el régimen pasa de «{c['estado_de']}» a "
                             f"«{c['estado_a']}»", "#sec-ahora"))
    for e in (c.get("entraron") or []):
        senales.append(li(f"nuevo extremo: {e['label']}",
                          f"#ind-{por_ind.get(e['label'], '')}"))
    for e in (c.get("salieron") or []):
        senales.append(li(f"{e['label']} sale de su extremo",
                          f"#ind-{por_ind.get(e['label'], '')}"))
    for m in (c.get("pil_mov") or []):
        senales.append(li(f"{m['pilar']}: {m['de']:.0f} → {m['a']:.0f} "
                          f"({m['delta']:+.0f})", "#sec-auditoria"))
    for d in (c.get("div_nac") or []):
        senales.append(li(f"nueva divergencia: {d}", "#sec-vigilar"))
    for d in (c.get("div_mur") or []):
        senales.append(li(f"se cierra: {d}", "#sec-vigilar"))
    for bloque, items in ((_guia(snap).get("triggers") or {})).items():
        if bloque == "descartados":
            continue
        for x in items:
            if x.get("ya"):
                trg.append(li(f"activo: {x.get('variable')} "
                              f"({x.get('condicion')})",
                              f"#ind-{x.get('key', '')}"))
    cats = [(k, v) for k, v in (("Decisiones", decisiones), ("Señales", senales),
                                ("Disparadores", trg)) if v]
    docs = c.get("docs_nuevos") or []
    if docs:
        cats.append(("Fuentes nuevas", [li(d, "#sec-research") for d in docs]))
    if not cats:
        return (f'<p class="note">↔ Nada que afecte a una decisión desde '
                f'{esc(fecha_corta(c["fecha_prev"]))}. Que no cambie nada también '
                f'es información.</p>')
    bloques = "".join(
        f'<div class="cr-g"><span class="cr-k">{esc(k)}</span>'
        f'<ul class="cr-l">{"".join(items)}</ul></div>' for k, items in cats)
    return (f'<p class="note">Desde {esc(fecha_corta(c["fecha_prev"]))}, '
            f'por categoría.</p><div class="cr">{bloques}</div>')


def _cambios_cockpit(snap: dict) -> str:
    """«Que cambio» como HERRAMIENTA DE NAVEGACION (punto 10).

    Tres como maximo: es lo que cabe leer antes de decidir si merece la pena
    seguir, y los tres son los que mas mueven una decision porque la lista
    llega ya ordenada. Cada uno lleva a lo que cambio --el tema, el indicador,
    la seccion-- en vez de mandar siempre al mismo sitio. El registro completo
    queda a un clic, en Historia.
    """
    g = _guia(snap)
    refs = g.get("what_changed_ref") or []
    wc = g.get("what_changed") or []
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        cuerpo = '<li class="nada">Sin snapshot anterior con el que comparar.</li>'
    elif not wc:
        cuerpo = (f'<li class="nada">↔ Sin cambios que afecten una decisión desde '
                  f'{esc(fecha_corta(c["fecha_prev"]))}.</li>')
    else:
        if not refs:
            refs = [dict(texto=x, ancla="#sec-historia") for x in wc]
        cuerpo = ""
        for x in refs[:3]:
            flecha = "!" if x["texto"].lower().startswith(("nueva", "nuevo")) else "→"
            cuerpo += (f'<li><span class="fl">{flecha}</span>'
                       f'<a href="{esc(x["ancla"])}">{es_num(esc(x["texto"]))}</a></li>')
        if len(refs) > 3:
            cuerpo += (f'<li class="mas-cam"><a href="#cambios-registro">'
                       f'y {len(refs) - 3} más, en el registro completo</a></li>')
    pie = (f'<a class="ck-cam-t" href="#cambios-registro">registro completo</a>'
           if c.get("disponible") else "")
    return (f'<div class="ck-cam"><span class="k">{esc(config.TITULOS["cambios"])}'
            f'</span>{pie}<ul>{cuerpo}</ul></div>')


def _clases_es(n) -> str:
    """«una clase», no «1 clases»."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "varias clases"
    return "una clase" if n == 1 else f"{n} clases"


def _interp_html(snap: dict) -> str:
    """Tres bloques de interpretacion, y la narrativa completa detras de un
    desplegable. El texto largo no desaparece: deja de ser lo primero."""
    c = snap.get("composites") or {}
    tec, mac = c.get("tecnico") or {}, c.get("macro") or {}
    ind = snap.get("tension_principal") or snap.get("tension_contexto")
    def blk(k, estado, frase, cifras):
        return (f'<div class="ib"><div class="ib-h">{esc(k)}'
                f'<span class="ib-e">{esc(estado)}</span></div>'
                f'<p>{es_num(esc(frase))}</p>'
                f'<div class="ib-n">{cifras}</div></div>')
    b1 = blk("Mercado", tec.get("lect", "—"),
             f'{tec.get("fav", 0)} de {tec.get("n", 0)} señales de tendencia, '
             f'volatilidad y crédito apuntan al mismo lado.',
             f'<b>{lvl_str(tec.get("nivel", float("nan")))}</b> compuesto técnico')
    # D2 d: la palabra que explicaba la conviccion. La relacion macro/tecnico ya
    # la calcula `_relacion()`; al comprimir la prosa en tarjetas se perdio, y
    # con ella el porque de que la conviccion sea media y no alta.
    rel = c.get("relacion")
    b2 = blk("Macro",
             mac.get("lect", "—") + (f' · {config.RELACION_TXT[rel].split(" al ")[0]}'
                                     if rel in config.RELACION_TXT else ""),
             f'{mac.get("fav", 0)} de {mac.get("n", 0)} señales de '
             f'{config.pilar_prosa("crecimiento")} y {config.pilar_prosa("liquidez")} acompañan'
             + (f'; {config.RELACION_GLOSA[rel]}.'
                if rel in config.RELACION_GLOSA else '.'),
             f'<b>{lvl_str(mac.get("nivel", float("nan")))}</b> compuesto macro')
    if ind:
        # Si el que contradice sale de un pilar de contexto, se dice: la cabecera
        # ya lo marca asi y los dos sitios tienen que contar lo mismo.
        es_ctx = not snap.get("tension_principal")
        b3 = blk("Restricción principal", "en contra, como contexto" if es_ctx else "en contra",
                 f'{config.SHORT.get(ind["key"], ind["label"])} contradice la '
                 f'inclinación de {_clases_es(ind.get("n_frentes"))}'
                 + (', y es una fuerza de contexto: no vota dirección.'
                    if es_ctx else '.'),
                 f'<b>{es_num(esc(str(ind["valor"])))}</b> · {p_str(ind["pct"])}')
    else:
        b3 = blk("Restricción principal", "ninguna",
                 "Ningún indicador persistente contradice la lectura.", "")
    largo = "".join(f"<p>{es_num(esc(x))}</p>" for x in (snap.get("evidencia") or []))
    coh = _guia(snap).get("coherencia")
    if coh:
        largo += f'<p>{es_num(esc(coh))}</p>'
    det = (f'<details class="narr"><summary>Ver explicación completa</summary>'
           f'<div class="prosa">{largo}</div></details>') if largo else ""
    return f'<div class="interp">{b1}{b2}{b3}</div>{det}'


def _drivers_html(e) -> str:
    """Los apoyos de una expresion, ENLAZADOS a su indicador crudo (punto 16).

    El lector que pregunta «¿por que duracion corta?» no quiere el nombre del
    driver: quiere el dato. El enlace lleva a la fila del tablero, que es donde
    vive el valor, el percentil y la ventana.
    """
    if not isinstance(e, dict):
        return ""
    keys = e.get("supported_by") or []
    labs = e.get("supported_labels") or []
    if not keys:
        return ""
    trozos = []
    for k, lab in zip(keys, labs or keys):
        trozos.append(f'<a class="drv" href="#ind-{esc(k)}">{es_num(esc(lab))}</a>')
    return f'<span class="drvs">Drivers: {", ".join(trozos)}</span>'


def _tema_detalle_html(snap: dict, t: dict) -> str:
    """EL componente de detalle de un tema (punto 6). Uno solo, reutilizable.

    Lo consume la matriz al desplegar una fila, y cualquier sitio que en
    adelante necesite contar un tema entero. Habia dos renderizados distintos
    de la misma informacion --la matriz y la guia-- y mantener los dos en
    sincronia era cuestion de tiempo.
    """
    g = _guia(snap)
    pos = {r["key"]: r for r in (snap.get("posicionamiento") or [])}
    r = pos.get(t["key"], {})
    cn = _CONV_N.get(t.get("conviccion"))
    conv = (f'<span class="cv c{cn}">{esc(t["conviccion"])}</span>' if cn
            else '<span class="ineu">—</span>')
    fav = t.get("favorecer") or {}
    # SEMANTIC-PASS 12: cinco preguntas llanas, en su orden. Qué lado, cuánta
    # evidencia, si el corto plazo acompaña, cómo se expresa, y qué lo cambiaría.
    ck = t.get("key")
    if ck == "usd":
        # §14-17: el dólar no se decide como una clase más. Se dice qué hace y
        # qué implica para una cartera con base en dólar.
        est = config.USD_ESTADO.get(t.get("dir_tipo") or "neutral", "Neutral")
        imp = config.USD_IMPLICACION.get(t.get("dir_tipo") or "neutral", "")
        filas = [("Entorno del dólar", f'<b>{esc(est)}</b>'),
                 (config.CONVICCION_PM, conv),
                 ("Implicación",
                  f'{esc(imp)}<span class="drvs">{esc(config.USD_NOTA)}</span>')]
    else:
        filas = [("Sesgo", f'<b>{esc(t.get("sesgo") or t.get("postura") or "—")}</b>'),
                 (config.CONVICCION_PM, conv)]
    filas += [(config.SENAL_ETIQUETA, _timing_html(t, g)),
              ("Horizonte", esc(_HZ_ES.get(t.get("horizonte"),
                                           t.get("horizonte") or "—")))]
    if ck != "usd":
        filas.append(("Expresión",
                      _expr_html(fav, con_fuente=False) + _drivers_html(fav)))
    # §5: el disparador que afecta a ESTE tema, con su valor de hoy y su umbral.
    # Es el siguiente eslabon de la cadena: tema -> driver/disparador -> dato.
    disp = _trigger_de_tema(snap, t["key"])
    if disp:
        filas.append(("Qué cambiaría la lectura", disp))
    # §6: el estado anterior, cuando lo hay. Sin el, una fila no dice si lo que
    # se lee es nuevo.
    if r.get("dir_ant") and r.get("dir_ant") != "—":
        prev = esc(str(r["dir_ant"]))
        if r.get("conv_ant"):
            prev += f' <span class="ant">{esc(str(r["conv_ant"]))}</span>'
        filas.append(("Mes anterior", prev))
    if t.get("evitar_util"):
        # «Riesgo» se leía como el riesgo de la lectura. Es qué evitar: la
        # exposición que sobra SI la lectura es correcta.
        # §33: «Evitar» suena a orden. Es el lado menos favorecido.
        filas.append((config.EVITAR_ETIQUETA,
                      esc((t.get("evitar") or {}).get("text") or "")
                      + f'<span class="drvs">{esc(config.EVITAR_GLOSA)}</span>'))
    if t.get("sin_evidencia_propia"):
        filas.append(("Aviso", "no hay evidencia del pilar propio del tema; "
                               "se sostiene en la familia común"))
    if r.get("nota"):
        filas.append(("Nota", es_num(esc(r["nota"]))))
    cuerpo = "".join(f'<div class="td-k">{esc(k)}</div><div class="td-v">{v}</div>'
                     for k, v in filas)
    return f'<div class="td">{cuerpo}</div>'


def _porque_html(snap: dict) -> str:
    """POR QUÉ: qué empuja y qué frena, por su nombre (SEMANTIC-PASS 31).

    Es la misma información que el gráfico de fuerzas, dicha en dos renglones.
    El gráfico da la magnitud; esto da la lista, que es lo que se retiene.
    """
    ap, fr = [], []
    for pil in (snap.get("tablero") or []):
        nom = config.PILAR_NOMBRE.get(pil["key"], pil["label"])
        if not pil.get("eje"):
            continue                      # los de contexto no empujan ni frenan
        if pil["lectura"] == "favorable":
            ap.append(nom)
        elif pil["lectura"] == "adverso":
            fr.append(nom)
    if not ap and not fr:
        return ""
    fila = ""
    if ap:
        fila += (f'<span class="pq-k pq-a">Apoyan riesgo</span>'
                 f'<span class="pq-v">{esc(" · ".join(ap))}</span>')
    if fr:
        fila += (f'<span class="pq-k pq-f">Frenan</span>'
                 f'<span class="pq-v">{esc(" · ".join(fr))}</span>')
    return f'<div class="pq"><span class="pq-t">Por qué</span>{fila}</div>'


def _regimen_html(t: dict, riesgo) -> str:
    """El regimen de riesgo, confirmado y candidato (HTML-POLISH 8).

    Sin las dos palabras, «neutral · p75» se lee como que p75 es neutral, y no
    lo es: el regimen lleva histeresis y esta a medio confirmar un cambio. Es
    una transicion de estado, no una contradiccion, y asi se escribe.
    """
    pct = f'<em>{p_str(riesgo.hist_pct)}</em>' if riesgo else ""
    tr = t.get("transicion") or {}
    if not t.get("transicion_txt"):
        return f'<span><b>Riesgo</b> {esc(t.get("estado") or "-")} {pct}</span>'
    faltan = max(0, int(tr.get("dias_requeridos") or 0) - int(tr.get("dias") or 0))
    conf = ("hoy se confirma" if faltan == 0 else
            "1 día hábil restante" if faltan == 1 else
            f"{faltan} días hábiles restantes")
    fin = (f'<span class="rg-l rg-n">Confirmación: {esc(conf)}</span>'
           if tr.get("confirmando")
           else f'<span class="rg-l rg-n">{esc(t.get("transicion_txt"))}</span>')
    # La regla, dicha entera: «3 días restantes» no se entiende sin saber qué
    # tiene que aguantar esos días ni qué pasa si un día no aguanta.
    if t.get("transicion_regla"):
        fin += f'<span class="rg-r">{esc(t["transicion_regla"])}</span>'
    return (f'<span class="rg"><b>Régimen de riesgo</b>'
            f'<span class="rg-l">Confirmado: <b>{esc(t.get("estado") or "-")}</b> '
            f'{pct}</span>'
            f'<span class="rg-l rg-c">→ Candidato: '
            f'<b>{esc(tr.get("destino") or "-")}</b></span>{fin}</span>')


def _trigger_de_tema(snap: dict, ck: str) -> str:
    """El disparador publicado que afecta a este tema, con valor y umbral.

    Se lee del estado --no se busca ni se recalcula-- y enlaza con el indicador
    crudo, que es donde termina la cadena.
    """
    g = _guia(snap)
    for bloque, items in (g.get("triggers") or {}).items():
        if bloque == "descartados":
            continue
        for x in items:
            if x.get("affected_theme") != ck:
                continue
            umb = x.get("condicion") or "—"
            return (f'<a class="drv" href="#ind-{esc(x.get("key") or "")}">'
                    f'{es_num(esc(x.get("variable") or ""))}</a> '
                    f'<b>{es_num(esc(str(x.get("actual") or "—")))}</b> '
                    f'<span class="ant">→ {es_num(esc(umb))}</span>'
                    + (f'<span class="drvs">{es_num(esc(x.get("efecto") or ""))}</span>'
                       if x.get("efecto") else ""))
    return ""


def _timing_html(t: dict, g: dict) -> str:
    """La señal táctica del tema, con su reserva.

    SEMANTIC-PASS 9: aqui ya no se escribe «· global» ni «· propio del tema».
    Que una fila herede la señal del tablero es el caso normal y marcarlo en
    cada fila solo anade una palabra que el lector tiene que aprender; cuando
    la fila SI calcula la suya y sale distinta, lo que importa no es la
    etiqueta sino el contraste, y ese se escribe entero.
    """
    from snapshot import decision as _d
    est, reserva = _d.senal_txt(t.get("timing"), t.get("senal_detalle"))
    cls = _TIMING_CLS.get(t.get("timing"), "t-neu")
    out = f'<span class="{cls}">{esc(est)}</span>'
    if reserva:
        out += f'<span class="tdif">Reserva: {es_num(esc(reserva))}</span>'
    if t.get("timing_override"):
        gl = _d.senal_txt(t.get("timing_global"), g.get("senal_detalle"))[0]
        out += (f'<span class="tdif">en el conjunto del tablero: '
                f'{esc(gl)}</span>')
    return out


def _matriz_html(snap: dict) -> str:
    """La matriz de posicionamiento, ACCIONABLE (punto 5).

    Cada fila es la vista general --nombre, las dos puntas de SU eje, donde cae
    el punto y el sesgo-- y se despliega en el detalle del tema, que a su vez
    enlaza cada driver con su indicador crudo. Esa es la ruta: panorama, tema,
    driver, dato.

    Las puntas salen de `decision.espectro_lados`, la misma regla que usa el
    brief: ordenadas por RIESGO, defensivo a la izquierda. Estaban ordenadas
    por el eje del tema, asi que en duracion, dolar y oro --los tres de beta
    negativa-- el punto caia sobre la etiqueta contraria.
    """
    from snapshot import decision as _d
    g = _guia(snap)
    temas = g.get("temas") or []
    if not temas:
        return ""
    # §17-18: el núcleo decide QUÉ se tiene; el overlay, CÓMO se tiene. Juntos,
    # la vista de divisa se lee como una asignación de cartera, que es justo lo
    # que el dólar no es aquí.
    filas = ""
    grupo_abierto = None
    orden = list(config.TEMAS_ORDEN)
    for t in sorted(temas, key=lambda x: (
            config.DIMENSION_GRUPO.get(x["key"], "núcleo") == "overlay",
            orden.index(x["key"]) if x["key"] in orden else 99)):
        gr = config.DIMENSION_GRUPO.get(t["key"], "núcleo")
        if gr != grupo_abierto:
            glosa = ("qué se tiene" if gr == "núcleo" else "cómo se tiene, no qué")
            filas += (f'<div class="mx-gr">{esc(gr.capitalize())}'
                      f'<em> · {esc(glosa)}</em></div>')
            grupo_abierto = gr
        lados = _d.espectro_lados(t)
        paso = t.get("paso", 0)
        lado = (paso > 0) - (paso < 0)
        fuerza = {"alta": 2.0, "media": 1.35, "baja": 0.75}.get(t.get("conviccion"), 0.0)
        pos = 50 + lado * (fuerza if lado else 0.0) * 22.0
        col = ("fav" if lado > 0 else "adv" if lado < 0 else "neu")
        ci = " on" if lado < 0 else ""
        cd = " on" if lado > 0 else ""
        filas += (
            f'<details class="mxr" id="theme-{esc(t["key"])}">'
            f'<summary>'
            # Punto 24: un ancla que se pueda escribir de memoria en un mensaje.
            # Va DENTRO del summary: un nodo suelto entre <details> y <summary>
            # lo saca el parser fuera del desplegable, y entonces el enlace
            # llega al sitio pero no lo abre.
            + (f'<span class="sr" id="theme-{esc(config.TEMA_ALIAS[t["key"]])}">'
               f'</span>'
               if config.TEMA_ALIAS.get(t["key"], t["key"]) != t["key"] else "")
            + f'<span class="mx-n">'
            f'{esc(config.dimension_breve(t["key"], t["label"]))}</span>'
            f'<span class="mx-i{ci}">{esc(lados["izq"])}</span>'
            f'<span class="mx-b"><span class="mx-ax"></span>'
            f'<span class="mx-p {col}" style="left:{pos:.1f}%" '
            f'title="{esc(t.get("sesgo") or "")}"></span></span>'
            f'<span class="mx-d{cd}">{esc(lados["der"])}</span>'
            f'<span class="mx-s">{esc(t.get("sesgo") or "—")}</span>'
            # SEMANTIC-PASS 40: la linea de resumen decia «acompaña con
            # reservas» --TIMING_CABEZA-- mientras el detalle de la misma fila,
            # dos clics mas abajo, decia «mayormente a favor». Es el mismo
            # campo: una sola forma, la que publica la capa de decision.
            f'<span class="mx-cv">{esc(t.get("conviccion") or "—")} · '
            f'{esc(_d.senal_txt(t.get("timing"), t.get("senal_detalle"))[0])}</span>'
            f'</summary>'
            f'{_tema_detalle_html(snap, t)}</details>')
    return (f'<div class="mx"><div class="mx-h"><span>Dimensión</span>'
            f'<span>Defensivo</span><span></span><span>Pro-riesgo</span>'
            f'<span>Sesgo</span></div>{filas}</div>'
            f'<p class="note">Cada fila se abre en su detalle, y cada driver del '
            f'detalle enlaza con el indicador del que sale.</p>')


def _proximidad_svg(snap: dict) -> str:
    """Que disparadores estan cerca de cumplirse.

    Se usa la distancia ESTANDARIZADA que ya calcula el estado (sigmas del
    propio indicador en su horizonte). Es la unica medida comparable entre
    variables con unidades distintas; comparar puntos porcentuales de un
    diferencial con dolares de liquidez no significaria nada. Los que no la
    tienen --el cruce de banda del eje-- se quedan fuera del grafico y siguen en
    la tabla.

    Rejilla y no SVG, por lo mismo que el grafico de fuerzas: la cifra iba
    anclada al borde derecho de un viewBox fijo y la barra crecia hacia ella,
    asi que la fila mas cercana --la barra mas larga, justo la que mas importa--
    se imprimia por debajo de su propio numero. Ademas el SVG declaraba
    `width:100%` y `height` en pixeles, y con `meet` el dibujo se quedaba a
    tamaño fijo centrado en una caja de 900: de ahi los dos margenes vacios de
    300 px a los lados.
    """
    g = _guia(snap)
    trg = [t for b in ("invalida", "debilita", "confirma", "tactico")
           for t in (g.get("triggers", {}).get(b) or [])
           if t.get("sigmas") is not None and not t.get("ya")]
    if not trg:
        return ""
    trg = sorted(trg, key=lambda t: t["sigmas"])[:6]
    tope = config.TRIGGER_SIGMA_MAX
    filas, resumen = "", []
    for t in trg:
        frac = max(0.03, min(1.0, 1.0 - t["sigmas"] / tope))
        cerca = ("Cerca" if t["sigmas"] <= 1.5 else
                 "Moderado" if t["sigmas"] <= 3.0 else "Lejano")
        cls = {"invalida": "adv", "debilita": "warn",
               "confirma": "fav"}.get(t.get("bloque"), "neu")
        filas += (f'<div class="px-r">'
                  f'<span class="px-l">{esc(t["variable"])}</span>'
                  f'<span class="px-b"><i class="{cls}" '
                  f'style="width:{frac * 100:.1f}%"></i></span>'
                  f'<span class="px-v">{t["sigmas"]:.1f}σ · {cerca}</span></div>')
        resumen.append(f'{t["variable"]} a {t["sigmas"]:.1f} sigmas ({cerca})')
    return (f'<figure class="px"><figcaption class="px-h">Proximidad de los '
            f'disparadores</figcaption><div class="px-g">{filas}</div>'
            f'<p class="note">Barra más larga, más cerca. La distancia va en '
            f'desviaciones típicas del propio indicador, que es lo único '
            f'comparable entre variables con unidades distintas.</p></figure>')


def _heatmap_html(snap: dict) -> str:
    """Doce meses de postura por tema. Responde a «¿esto es nuevo?»."""
    g = _guia(snap)
    hi = g.get("historia") or {}
    if not hi.get("disponible"):
        return ('<p class="note">Posicionamiento histórico no disponible: no hay '
                'suficiente historia de pilares para reconstruirlo.</p>')
    cols = hi["columnas"]
    # Punto 27: las columnas se numeran desde la MAS RECIENTE. En movil se
    # muestran seis y en escritorio las doce; el control cambia el corte sin
    # tocar el DOM --las celdas estan siempre, solo se ocultan-- para que
    # «doce meses» siga siendo verdad en los dos tamaños.
    n = len(cols)
    cab = "".join(f'<th scope="col" data-i="{n - 1 - i}">'
                  f'{esc(_MESES_CORTO[c["fecha"].month - 1])}</th>'
                  for i, c in enumerate(cols))
    filas = ""
    for ck in hi["temas"]:
        lab = config.ASSET_CLASSES.get(ck, {}).get("label", ck)
        celdas = ""
        for i, c in enumerate(cols):
            idx = f' data-i="{n - 1 - i}"'
            v = c["temas"].get(ck)
            if not v:
                celdas += f'<td class="hm-x"{idx} aria-label="sin dato">·</td>'
                continue
            d = v["dir_tipo"]
            cls = {"mas": "hm-f", "menos": "hm-a"}.get(d, "hm-n")
            cn = {"alta": 3, "media": 2, "baja": 1}.get(v["conviccion"], 0)
            et = config.SESGO_PRESENTACION.get(ck, {}).get(d, "Neutral")
            tit = (f'{fecha_corta(c["fecha"])} · {lab}: {et}'
                   + (f' · convicción {v["conviccion"]}' if v["conviccion"] else ""))
            celdas += (f'<td class="{cls} k{cn}"{idx} tabindex="0" '
                       f'title="{esc(tit)}" data-say="{esc(tit)}" '
                       f'aria-label="{esc(tit)}">'
                       f'<span class="sr">{esc(et)}</span></td>')
        filas += f'<tr><th scope="row">{esc(lab)}</th>{celdas}</tr>'
    ctl = ('<div class="hm-c" role="group" aria-label="Meses que se muestran">'
           '<button type="button" class="hm-b" data-meses="6" aria-pressed="false">'
           '6 m</button>'
           '<button type="button" class="hm-b" data-meses="12" aria-pressed="true">'
           '12 m</button></div>')
    return (f'{ctl}<div class="hm-w"><table class="hm">'
            f'<caption class="sr">Postura por tema, mes a mes, en los últimos '
            f'doce meses</caption>'
            f'<thead><tr><th></th>{cab}</tr></thead><tbody>{filas}</tbody></table></div>'
            f'<p class="hm-say" role="status" aria-live="polite">Toca o enfoca '
            f'una celda para leerla.</p>'
            f'<p class="note">Color: el lado que la evidencia favorecía ese mes '
            f'(verde favorable al riesgo del tema, rojo en contra, gris sin '
            f'dirección). La intensidad es la confianza. Reconstruido con la '
            f'misma función que usa la columna «mes anterior»; la señal táctica '
            f'no se reconstruye hacia atrás.</p>')


def _tape_html(snap: dict) -> str:
    """CROSS-ASSET TAPE (SEMANTIC-PASS 13-21). Small multiples, un eje comun.

    Siete paneles, uno por decision de cartera, todos sobre la MISMA ventana de
    doce meses y rebasados a 100 el primer dia: es lo unico que permite trazar
    una vertical y comparar. Debajo de cada precio, la vision historica del
    modelo, sacada de la reconstruccion mensual --no inferida del precio--.

    No es un backtest y lo dice. Poner precio y postura en el mismo eje invita
    a puntuar al modelo a ojo; la nota existe para que esa cuenta no se haga en
    silencio y sin reglas.
    """
    t = snap.get("tape") or {}
    if not t.get("disponible"):
        return ('<p class="note">Cross-Asset Tape no disponible: no hay series '
                'de mercado suficientes en la ventana.</p>')

    res = "".join(f'<div class="tp-r"><span class="tp-rk">{esc(r["k"])}</span>'
                  f'<span class="tp-rv">{esc(r["v"])}</span></div>'
                  for r in (t.get("resumen") or []))
    cab = (f'<div class="tp-sum">{res}</div>' if res else "")

    paneles = ""
    for p in t["paneles"]:
        cifras = ("" if not p["disponible"] else
                  f'<span class="tp-n">3m <b>{p["r3m"]:+.1f} %</b></span>'
                  f'<span class="tp-n">12m <b>{p["r12m"]:+.1f} %</b></span>')
        cuerpo = (_tape_svg(p, t) if p["disponible"] else
                  f'<p class="tp-nd">DATOS NO DISPONIBLES · {esc(p["motivo"])}</p>')
        aviso = (f'<p class="tp-av">{esc(p["aviso"])}</p>'
                 if p.get("aviso") and p["disponible"] else "")
        paneles += (f'<figure class="tp-p" id="tp-{esc(p["id"])}" '
                    f'data-panel="{esc(p["id"])}">'
                    f'<figcaption class="tp-h">'
                    f'<span class="tp-t">{esc(p["titulo"])}</span>'
                    f'<span class="tp-s">{esc(p["nota"])}</span>{cifras}'
                    f'</figcaption>{cuerpo}{aviso}</figure>')

    # La leyenda de la banda se escribe en terminos de la LINEA, no de
    # "acierto": la banda dice hacia que lado se inclinaba el modelo, y el
    # unico lado que el lector puede ver en el panel es el que dibuja la linea.
    leyenda = ('<p class="tp-leg">La banda bajo cada línea es la postura del '
               'modelo ese mes. <span class="tp-k tp-bp"></span> se inclinaba '
               'hacia el lado que hace subir la línea · '
               '<span class="tp-k tp-bd"></span> hacia el contrario · '
               '<span class="tp-k tp-b0"></span> sin inclinación. '
               'Pasa el cursor por la banda para ver el mes y la postura.</p>')

    return (f'{cab}<div class="tp">{paneles}</div>{leyenda}'
            f'<p class="note">Cada línea empieza en 100 el '
            f'{esc(fecha_corta(t["desde"]))} y todas comparten la misma ventana '
            f'y los mismos cortes trimestrales, así que una vertical cae en el '
            f'mismo día en los siete paneles. La banda sale de la misma '
            f'reconstrucción mensual que el mapa de calor, no se infiere del '
            f'precio. <b>El comportamiento del mercado se muestra junto a la '
            f'visión histórica del modelo como contexto. No es una prueba de '
            f'rendimiento.</b></p>')


def _tape_svg(p: dict, t: dict) -> str:
    """Un panel: la linea rebasada y, debajo, la banda de postura del modelo.

    El color de la banda se decide contra `alza` --el lado que expresa que la
    linea suba-- y no contra el lado pro-riesgo del eje. Con TLT dibujado son
    cosas distintas, y pintar de un color "a favor" un mes en que el modelo
    preferia duracion corta seria decir lo contrario de lo que paso.
    """
    pts = p["puntos"]
    if len(pts) < 2:
        return ""
    W, H, BANDA = 300.0, 58.0, 9.0
    vals = [v for _f, v in pts]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    x0 = pts[0][0].value
    span = max(1, pts[-1][0].value - x0)

    def px(f):
        return (f.value - x0) / span * W

    def py(v):
        return H - (v - lo) / (hi - lo) * (H - 6) - 3

    d = " ".join(f'{"M" if i == 0 else "L"}{px(f):.1f},{py(v):.1f}'
                 for i, (f, v) in enumerate(pts))
    cien = (f'<line x1="0" y1="{py(100):.1f}" x2="{W:.0f}" y2="{py(100):.1f}" '
            f'class="tp-100"/>' if lo <= 100 <= hi else "")

    # Cortes trimestrales: los mismos x en los siete paneles.
    rej = "".join(
        f'<line x1="{px(c):.1f}" y1="0" x2="{px(c):.1f}" y2="{H + BANDA + 3:.0f}" '
        f'class="tp-q"/>'
        for c in (t.get("cortes") or []) if 0 < px(c) < W)

    # La banda: un segmento por mes, del lado hacia el que se inclinaba.
    seg = ""
    banda = p.get("banda") or []
    alza = p.get("alza", "mas")
    for i, b in enumerate(banda):
        xa = px(b["fecha"]) if b["fecha"].value >= x0 else 0.0
        xb = px(banda[i + 1]["fecha"]) if i + 1 < len(banda) else W
        if xb <= xa:
            continue
        dt = b.get("dir_tipo")
        cls = ("tp-b0" if dt in (None, "neutral") else
               "tp-bp" if dt == alza else "tp-bd")
        seg += (f'<rect x="{max(0.0, xa):.1f}" y="{H + 3:.1f}" '
                f'width="{min(W, xb) - max(0.0, xa):.1f}" height="{BANDA}" '
                f'class="{cls}"><title>{esc(fecha_corta(b["fecha"]))} · '
                f'{esc(b.get("etiqueta") or "sin dato")}</title></rect>')
    if not banda:
        seg = (f'<text x="0" y="{H + 11:.0f}" class="tp-nd-t">'
               f'Visión histórica del modelo no disponible</text>')

    # El eje de fechas se dibuja FUERA, en HTML. Aqui el SVG acaba justo
    # debajo de la banda.
    alto = H + BANDA + 3
    return (f'<svg viewBox="-2 -2 {W + 4:.0f} {alto + 4:.0f}" width="100%" '
            f'height="{alto + 4:.0f}" role="img" '
            f'aria-label="{esc(p["titulo"])}: {p["r12m"]:+.1f} % en doce meses, '
            f'{p["r3m"]:+.1f} % en tres.">'
            f'{rej}{cien}<path d="{d}" class="tp-l"/>{seg}</svg>'
            f'<p class="tp-ax"><span>{esc(fecha_corta(t["desde"]))}</span>'
            f'<span>{esc(fecha_corta(t["hasta"]))}</span></p>')


def _timeline_html(snap: dict) -> str:
    """Los CAMBIOS de postura, no la serie. Lo que importa es cuándo giró."""
    lr = (_guia(snap).get("linea_regimen") or {})
    if not lr.get("disponible"):
        return ""
    tr = lr["tramos"]
    total = (tr[-1]["hasta"] - tr[0]["desde"]).days or 1
    seg = ""
    for t in tr:
        w = max(4.0, (t["hasta"] - t["desde"]).days / total * 100)
        cls = {"pro-riesgo": "tl-f", "defensiva": "tl-a"}.get(t["palabra"], "tl-n")
        seg += (f'<span class="{cls}" style="width:{w:.1f}%" '
                f'title="{esc(t["palabra"])} desde {esc(fecha_corta(t["desde"]))}">'
                f'<span class="sr">{esc(t["palabra"])}</span></span>')
    hitos = " → ".join(f'{esc(t["palabra"])} <em>{esc(fecha_corta(t["desde"]))}</em>'
                       for t in tr)
    return (f'<div class="tl"><div class="tl-b">{seg}</div>'
            f'<p class="tl-x">{hitos}</p></div>')


# A donde mirar cuando un aviso salta. El aviso que no dice que hacer con el
# solo consigue que se deje de leer la seccion entera (punto 17).
_QA_ACCION = {
    "Pilares con redundancia alta":
        ("revisa si la convicción se apoya en voces repetidas",
         "#sec-auditoria"),
    "Divergencias dentro de un mismo pilar":
        ("el pilar no habla con una sola voz: mira qué indicadores lo parten",
         "#sec-vigilar"),
    "Contradicciones de alto perfil":
        ("hay indicadores en contra de la lectura; están listados con su peso",
         "#sec-vigilar"),
    "Pilares sin lectura unificada":
        ("una clase se apoya en un pilar que no tiene dirección propia",
         "#sec-posicionamiento"),
    "Variables de entorno sin dato":
        ("falta contexto para los análogos; su comparación de entorno es parcial",
         "#sec-historia"),
    "Dirección del eje frente a su etiqueta":
        ("el régimen está confirmando un cambio de banda", "#sec-ahora"),
}


def _qa_status_html(snap: dict) -> str:
    """El semaforo antes de los checks, con SEVERIDAD y con que hacer.

    Tres niveles, no dos (punto 18): un documento que afirma algo falso no se
    lee igual que un mercado que discrepa consigo mismo. Y cada fila dice a
    donde ir (punto 17), porque un aviso sin destino se ignora a la segunda.
    """
    comps = snap.get("comprobaciones") or []
    if not comps:
        return ""
    grupos = {"error": [], "aviso": [], "info": []}
    for c in comps:
        sev = c.get("sev") or ("ok" if c["estado"] == "ok" else "aviso")
        if sev in grupos:
            grupos[sev].append(c)
    ok = sum(1 for c in comps if (c.get("sev") or c["estado"]) == "ok")
    if grupos["error"]:
        est, cls = "Fallido", "qa-e"
    elif grupos["aviso"]:
        est, cls = "Correcto con avisos", "qa-w"
    else:
        est, cls = "Correcto", "qa-o"

    def bloque(sev, titulo):
        filas = grupos[sev]
        if not filas:
            return ""
        lis = ""
        for c in filas:
            acc, dest = _QA_ACCION.get(c["label"], (None, None))
            qué = acc or es_num(esc(str(c.get("nota") or "")))[:150]
            ancla = dest or f'#chk-{_slug(c["label"])}'
            lis += (f'<li><span class="qa-b qa-b-{sev}">{esc(config.QA_SEV_TXT[sev])}'
                    f'</span><span class="qa-t">{esc(c["label"])}</span>'
                    f'<a class="qa-ver" href="{ancla}">Ver problema</a>'
                    f'<span class="qa-q">{qué} '
                    f'<span class="qa-v">{es_num(esc(str(c["valor"])))}</span>'
                    f'</span></li>')
        return f'<ul class="qa-l">{lis}</ul>'

    det = ""
    if grupos["error"] or grupos["aviso"] or grupos["info"]:
        n = len(grupos["error"]) + len(grupos["aviso"])
        etiqueta = (f'{n} que revisar' if n else
                    f'{len(grupos["info"])} de contexto')
        det = (f'<details class="qa-d"{" open" if grupos["error"] else ""}>'
               f'<summary>{esc(etiqueta)}</summary>'
               f'{bloque("error", "Errores")}{bloque("aviso", "Avisos")}'
               f'{bloque("info", "Contexto")}</details>')
    return (f'<div class="qa-s {cls}"><div class="qa-e">{esc(est)}</div>'
            f'<div class="qa-c"><span><b>{ok}</b> correctos</span>'
            + (f'<span class="qa-n-e"><b>{len(grupos["error"])}</b> errores</span>'
               if grupos["error"] else "")
            + f'<span><b>{len(grupos["aviso"])}</b> avisos</span>'
            f'<span><b>{len(grupos["info"])}</b> de contexto</span></div>{det}</div>')


def _estado_json(snap: dict) -> str:
    """El DecisionState canonico, escrito en el documento (HTML-POLISH 1, 34E).

    No lo lee el renderizador --el renderizador ya renderiza del estado-- sino
    quien audita: permite comparar el documento contra el estado por IDENTIDAD
    y no por busqueda de texto, que es lo que pide el test E.
    """
    import json as _json
    from snapshot import decision as _d
    try:
        datos = _json.dumps(_d.estado_canonico(snap), ensure_ascii=False,
                            sort_keys=True, indent=1)
    except Exception as e:                                       # noqa: BLE001
        return f"<!-- estado canónico no serializable: {type(e).__name__} -->"
    # `</script>` dentro de un bloque JSON cerraria la etiqueta antes de tiempo.
    datos = datos.replace("</", "<\\/")
    return ('<script type="application/json" id="decision-state">\n'
            + datos + '\n</script>')


def _slug(t: str) -> str:
    import unicodedata as _u
    t = _u.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40]


def render_html(snap: dict) -> str:
    t = snap["titular"]
    asof = snap["asof"]
    cob = snap["cobertura"]
    desde_ano = t["hist_since"].year if t["hist_since"] is not None else "—"

    axes_html = "".join(_axis_card(e) for e in snap["ejes"])
    n_checks = len(snap.get("comprobaciones") or [])
    n_contra = len(snap.get("contradicciones") or [])
    tablero_html = "".join(_pillar_block(p) for p in snap["tablero"])

    # --- divergencias entre pilares
    divs = snap["divergencias"]
    MAX_DIV = 6
    if divs:
        cuerpo = "".join(_divergence(d) for d in divs[:MAX_DIV])
        if len(divs) > MAX_DIV:
            cuerpo += (f'<p class="note">Y {len(divs) - MAX_DIV} divergencias más '
                       f'por debajo de estas en tamaño de brecha.</p>')
    else:
        cuerpo = f"""
        <div class="aligned">
          <p><b>Señales alineadas.</b> Ningún par de pilares se contradice hoy: no hay
             ninguno por encima de neutral con otro por debajo separados por más de
             {config.DIVERGENCE_GAP} puntos durante al menos
             {config.DIVERGENCE_MINW} semanas.</p>
          <p>Que no haya divergencia no quiere decir que la lectura sea buena, solo que
             es coherente. Los pilares pueden estar de acuerdo en que las cosas van mal.</p>
        </div>"""
    cuerpo = (f'<h4>Entre pilares ({len(divs)})</h4>' + cuerpo)

    # --- divergencias DENTRO de un pilar
    intra = snap["div_intra"]["lista"]
    if intra:
        intra_html = (
            f'<h4>Dentro de un mismo pilar ({len(intra)})</h4>'
            f'<p class="note" style="margin:0 0 12px">Dos indicadores del mismo pilar '
            f'diciendo cosas opuestas. La comparación entre pilares no ve esto, y en '
            f'inflación y posicionamiento —que no entran en ningún eje— no hay ningún '
            f'otro sitio del documento donde aparezca. Se muestra la contradicción más '
            f'amplia de cada pilar.</p>'
            + "".join(_divergencia_intra(d) for d in intra))
    else:
        intra_html = (
            f'<h4>Dentro de un mismo pilar (0)</h4>'
            f'<div class="aligned"><p>Ningún pilar se contradice por dentro: no hay dos '
            f'indicadores del mismo pilar con lecturas opuestas separados por '
            f'{config.DIVERGENCE_INTRA_GAP} puntos o más durante al menos '
            f'{config.DIVERGENCE_INTRA_MINW} semanas.</p></div>')

    # --- extremos
    exs = snap["extremos"]
    MAX_EXT = 14
    if exs:
        partes = []
        for titulo, grupo in (("En extremo adverso", [e for e in exs if e["tipo"] == "adverso"]),
                              ("En extremo favorable", [e for e in exs if e["tipo"] == "favorable"])):
            if not grupo:
                continue
            filas = "".join(_extreme(e) for e in grupo[:MAX_EXT])
            resto = ("" if len(grupo) <= MAX_EXT else
                     f'<p class="note">Y {len(grupo) - MAX_EXT} más.</p>')
            partes.append(f"<h4>{titulo} ({len(grupo)})</h4>{filas}{resto}")
        ext_html = "".join(partes)
    else:
        ext_html = ('<h4>Extremos</h4><div class="aligned"><p>Ningún indicador está fuera '
                    'de su banda p10–p90 a 5 años. Todo se mueve dentro de lo normal '
                    'de los últimos cinco años.</p></div>')

    # --- fuentes: partidas en "lo que aporta" (lectura) y "texto completo" (tablero)
    reg = snap["documentos"]
    descartes = []
    if reg["caducados"]:
        descartes.append(f'{reg["caducados"]} por tener más de dos semanas')
    if reg["futuros"]:
        descartes.append(f'{reg["futuros"]} por ser posteriores a la fecha del snapshot')
    futuros = (f' Se han dejado fuera {" y ".join(descartes)}.' if descartes else "")

    viejos = ""
    if cob["viejos"]:
        lst = "; ".join(f"{esc(l)} ({fecha_corta(d)})" for l, d, _a in cob["viejos"][:6])
        viejos = (f" Datos con más de 40 días de antigüedad, marcados también en el "
                  f"tablero: {lst}.")

    ax_incoh = [f'{esc(e["label"].lower())} (por {esc(", ".join(pp.lower() for pp in e["sin_lectura"]))})'
                for e in snap["ejes"] if e.get("sin_lectura")]
    ejes_incoh = (f' Sin lectura unificada hoy: {"; ".join(ax_incoh)} — el agregado se '
                  f'calcula, pero pesa menos en la convicción.' if ax_incoh else "")

    return f"""<!doctype html>
<html lang="es" data-view="pm">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Snapshot macro y de mercado · {fecha_corta(asof)}</title>
<style>{CSS}</style>
</head>
<body>
<article class="doc">

<header>
  <div class="eyebrow">Snapshot macro y de mercado</div>
  <h1>{esc(fecha_larga(asof))}</h1>
  <p class="meta">Datos al cierre del {esc(fecha_corta(asof))} ·
     {cob['con_dato']} de {cob['total']} indicadores con dato ·
     lectura, no recomendación</p>
</header>

{_nav_html(snap)}

<div class="cuerpo">

<section id="sec-ahora" class="sx" aria-labelledby="h-ahora">
  <h2 class="sx-h" id="h-ahora"><span class="sx-n">01</span> Ahora</h2>
  {_cockpit_html(snap)}
  {_interp_html(snap)}
  <p class="escalas">{config.ESCALAS_CORTA} · <b>contexto</b> marca las
     fuerzas que no votan dirección.</p>
</section>

<section id="sec-posicionamiento" class="sx" aria-labelledby="h-pos">
  <h2 class="sx-h" id="h-pos"><span class="sx-n">02</span> Posicionamiento cross-asset</h2>
  <p class="legend">Cada fila responde una decisión relativa de cartera: cuánta
     beta de renta variable, tramo corto o duración larga, grado de inversión o
     alto rendimiento, defensivo o cíclico, materias primas, oro y dólar.
     <b>No son clases de activo sueltas: son los dos lados de una misma
     decisión</b>, y la fila dice hacia cuál se inclina hoy la lectura.</p>
  {_matriz_html(snap)}
  <p class="note">Cada dimensión usa sus propias etiquetas: «corta» en duración y
     «menor calidad» en crédito son posiciones pro-riesgo, igual que «favorable» en
     renta variable. <b>Sesgo, confianza y señal táctica son tres cosas
     distintas</b>: el sesgo dice el lado, la confianza cuánta evidencia lo
     sostiene y la señal táctica si el corto plazo lo acompaña ahora mismo.</p>
</section>

<section id="sec-vigilar" class="sx" aria-labelledby="h-vig">
  <h2 class="sx-h" id="h-vig"><span class="sx-n">03</span> Qué vigilar</h2>
  {_regimen_tactico_html(snap)}
  {_proximidad_svg(snap)}
  {_triggers_html(snap)}
  <details class="mas solo-full">
    <summary>Cómo se clasifica un disparador</summary>
    <p class="note">El bloque de cada disparador <b>no lo decide la regla que lo
       generó</b>: se simula el cruce del umbral, se rehacen los votos, la postura y
       la convicción con las mismas funciones que producen la lectura publicada, y se
       compara. Solo lo que deja a un tema <b>sin dirección</b> o le <b>da la
       vuelta</b> aparece bajo «Invalida / revierte»; lo que le quita apoyo sin
       cambiarlo de lado aparece bajo «Debilita». Cada disparador trae además el
       horizonte, la confirmación que exige y su <b>alcanzabilidad</b>: la distancia
       al umbral en desviaciones típicas del propio indicador.</p>
  </details>

  <h3 class="sx-s">Qué contradice la lectura</h3>
  <details class="mas">
    <summary>Todas las contradicciones del tablero ({n_contra})</summary>
    <p class="note">La lista completa, sin filtrar por persistencia: incluye
       extremos demasiado recientes para sostener una lectura. Los que sí la
       sostienen son el «indicador en contra» de la cabecera y los disparadores
       de arriba.</p>
    {_contra_block(snap['contradicciones'])}
  </details>
  <details class="mas solo-full">
    <summary>Divergencias entre pilares y dentro de cada pilar</summary>
    {cuerpo}
    {intra_html}
  </details>
  <details class="mas solo-full">
    <summary>Indicadores en extremo</summary>
    {ext_html}
  </details>
</section>

<section id="sec-historia" class="sx" aria-labelledby="h-his">
  <h2 class="sx-h" id="h-his"><span class="sx-n">04</span> Historia</h2>
  <h3 class="sx-s">Trayectoria de los ejes</h3>
  {_grafico_svg(snap.get('serie_puntuacion') or {{}})}

  <h3 class="sx-s" id="cross-asset-tape">Cross-Asset Tape · 12 meses</h3>
  <p class="legend">Qué hicieron los mercados mientras la lectura evolucionaba.
     Responde «¿qué hizo el mercado?»; el mapa de abajo responde «¿qué pensaba
     el modelo?». Son dos preguntas distintas y se miran por separado.</p>
  {_tape_html(snap)}

  <h3 class="sx-s">Evolución de la visión del modelo</h3>
  {_heatmap_html(snap)}
  <details class="mas solo-full">
    <summary>Régimen: cuándo cambió</summary>
    {_timeline_html(snap)}
  </details>
  <h3 class="sx-s">Episodios comparables</h3>
  {_analogos_lectura_html(snap)}
  <details class="mas solo-full">
    <summary>Ver análisis completo de análogos</summary>
    <p class="legend">Las fechas del pasado que más se parecen a hoy, y qué pasó después.
       Dos parecidos: la <b>dinámica</b> (los siete pilares y su trayectoria: si el mercado
       se comportaba igual) y el <b>entorno</b> (niveles absolutos —tasa real, inflación,
       tasa de referencia, curva, balance de la Fed—: si el mundo era el mismo). Una fecha
       puede parecerse en una y no en el otro: entonces es contexto, no guía. Un año de
       separación entre análogos y un año de futuro por delante de cada uno.</p>
    {_analogos_html(snap['analogos'])}
  </details>
  <h3 class="sx-s" id="cambios-registro">Qué cambió desde el anterior, en detalle</h3>
  {_cambios_registro_html(snap)}
  <details class="mas solo-full">
    <summary>Comparación completa con el snapshot anterior</summary>
    {_cambios_html(snap.get('cambios') or {{}})}
  </details>
</section>

<section id="sec-research" class="sx solo-full" aria-labelledby="h-res">
  <h2 class="sx-h" id="h-res"><span class="sx-n">05</span> Research</h2>
  <h3 class="sx-s">Posicionamiento, tabla de trabajo</h3>
  <p class="note">La misma lectura de la sección 02, en formato de tabla, con la
     expresión preferida y su procedencia. Vive aquí y no arriba porque es
     material de trabajo: la decisión se lee en la matriz.</p>
  {_posicion_guide_html(snap)}
  <details class="mas">
    <summary>Cómo leer cada fila</summary>
    {_howto_block(snap)}
  </details>
  {_filtro_html()}
  <div class="pilares" id="pilares">{tablero_html}</div>
  <p class="note">Dentro de cada pilar, ordenados por cuán lejos están de su
     normalidad: primero lo más extremo.</p>

  <h3 class="sx-s">Descomposición de señales por tema</h3>
  <details class="mas" id="tec-macro">
    <summary>Tabla completa, con las señales técnicas y macro por separado</summary>
    {_posicionamiento_html(snap.get('posicionamiento') or [])}
    <p class="note">Señales técnicas: {config.lista_pilares(TECNICO_PILARES)}.
       Señales macro: {config.lista_pilares(MACRO_PILARES)}.
       Cada celda apunta en los términos de la clase.</p>
  </details>

  <h3 class="sx-s">Qué dicen las fuentes</h3>
  <p class="legend">Solo lo que la fuente <b>aporta</b> y el tablero no ve: la lectura
     doble de un indicador y el porqué detrás de un dato. Nada de esto se suma al
     tablero. Solo fuentes vigentes: dos semanas, salvo un documento
     estructural que declare más vida.{futuros}</p>
  {_fuentes_lectura(reg)}

  <h3 class="sx-s">Traducción por mandato</h3>
  <details class="mas">
    <summary>Cómo se lee esta señal según el mandato</summary>
    {_mandate_html()}
  </details>
</section>

<section id="sec-auditoria" class="sx solo-full" aria-labelledby="h-aud">
  <h2 class="sx-h" id="h-aud"><span class="sx-n">06</span> Auditoría</h2>
  {_qa_status_html(snap)}

  <details class="mas">
    <summary>Las {n_checks} comprobaciones</summary>
    {_checks_block(snap.get('comprobaciones') or [])}
  </details>

  <h3 class="sx-s">Ejes con dirección</h3>
  <div class="axes">{axes_html}</div>
  <p class="note">Nivel: media de los percentiles a 5 años de sus indicadores, con 100
     siempre en lo favorable para activos de riesgo. Valor y cambios suavizados sobre
     unos días hábiles.{ejes_incoh}</p>

  <h3 class="sx-s">De dónde sale cada inclinación</h3>
  <p class="legend">El rastro para discutir la conclusión: cuántos indicadores votan a
     cada lado, cuántas <b>voces independientes</b> son en realidad —un grupo de
     indicadores correlacionados cuenta como una— y qué limitó la convicción.
     <b>Alta</b>: las voces apuntan a lo mismo y ningún extremo las contradice.
     <b>Media</b>: mayoría clara con alguna voz en contra, o una divergencia que parte
     la clase. <b>Baja</b>: un indicador en extremo apunta al contrario, o las voces se
     reparten. Cuando no alcanza ni para baja, <b>neutral</b>.
     {esc(config.METODOLOGIA_TXT['conviction_method'])}</p>
  {_score_block(snap['riesgo'], snap['senales'])}
  {_postura_html(snap['postura'])}
  {_distribucion_html(snap.get('distribucion') or {{}})}
  {_pilares_signal_html(snap['senales'])}
  {_redundancia_html(snap['redundancia'])}

  <h3 class="sx-s">Voto por cluster</h3>
  <p class="legend">Métrica <b>paralela</b>. Compara el recuento actual —un indicador,
     un voto— con el potencial —un grupo de correlación, un voto—. Está aquí para poder
     decidir sobre metodología con datos; <b>no decide nada</b> y no toca ninguna
     dirección publicada.</p>
  {_cluster_html(snap)}

  <h3 class="sx-s">Metodología</h3>
  <ol class="metod">
    <li><b>Nada mira al futuro.</b> Los percentiles son de ventana móvil hacia atrás
        (5 años en el tablero, toda la historia en los ejes) y cada serie macro entra en
        la fecha en que se publicó, no en la de su periodo.{viejos}</li>
    <li><b>Percentil alto no es «bueno»: es alto.</b> La etiqueta favorable o adverso
        aplica el signo de cada serie, y es lo único que permite comparar pilares.</li>
    <li><b>Los agregados van suavizados.</b> El nivel de los ejes, la puntuación y todos
        los deltas se calculan contra una ventana de días hábiles, no contra un cierre
        suelto, para que el rumbo no cambie sin que cambie el mercado.</li>
    <li><b>Posicionamiento e inflación no entran en ningún eje, a propósito.</b> La
        inflación, porque su signo depende del régimen; el posicionamiento, porque mejora
        justo cuando todo cae. Fuera, esa tensión se lee como divergencia.</li>
  </ol>

  <h3 class="sx-s">Fuentes, registro completo</h3>
  {_fuentes_completas(reg)}
</section>

<p class="vw-mas">Estás en <b>Vista PM</b>: la lectura y lo que la sostiene.
   El rastro completo —los 42 indicadores, los análogos, la auditoría— está en
   <button type="button" data-ir-full data-view="full">Vista completa</button>,
   y no se ha quitado nada: solo está plegado.</p>

</div>

<footer>
  <p>Fuentes de datos: Federal Reserve Bank of St. Louis (FRED), Yahoo Finance y
     Bloomberg (caché local). Documentos, los citados en el tablero. Documento
     descriptivo, sin recomendación de inversión.</p>
</footer>

</article>
{_estado_json(snap)}
{JS}
</body>
</html>
"""


# --------------------------------------------------------------- markdown
def render_md(snap: dict) -> str:
    asof = snap["asof"]
    cob = snap["cobertura"]
    L: list[str] = []
    A = L.append

    A(f"# Snapshot macro y de mercado — {fecha_larga(asof)}")
    A("")
    A(f"Datos al cierre del {fecha_corta(asof)}. {cob['con_dato']} de {cob['total']} "
      f"indicadores con dato. Lectura, no recomendación.")
    A("")

    orden = {"alta": 0, "media": 1, "baja": 2, None: 3}

    # ============================ LA NOTA ============================
    # En síntesis — la caja de conclusiones
    concl = snap.get("conclusiones") or []
    if concl:
        _md_guia(snap, A)
        A("**En síntesis**")
        A("")
        for b in concl:
            A(f"- {es_num(b)}")
        A("")

    # El peso de la evidencia — la prosa
    evid = snap.get("evidencia") or []
    if evid:
        A("## El peso de la evidencia")
        A("")
        for para in evid:
            A(es_num(para))
            A("")

    # La puntuación en el tiempo (el gráfico vive en la versión HTML)
    er = next((e for e in snap["ejes"] if "riesgo" in e["label"].lower()), None)
    ec = next((e for e in snap["ejes"] if "ciclo" in e["label"].lower()), None)
    if er and ec:
        A(f"*La puntuación en el tiempo (gráfico en la versión HTML): riesgo "
          f"{lvl_str(er['level'])}/100, en {p_str(er['hist_pct'])} de los últimos cinco "
          f"años; ciclo {lvl_str(ec['level'])}/100, en {p_str(ec['hist_pct'])}. "
          f"100 = favorable a activos de riesgo.*")
        A("")

    # Posicionamiento — rejilla: posición, sesgo, convicción, nota
    pos = snap.get("posicionamiento") or []
    if pos:
        def _barra(paso, paso_ant):
            slots = ["·"] * 5
            if paso_ant is not None and paso_ant != paso:
                slots[int(paso_ant) + 2] = "○"
            slots[int(paso) + 2] = "●"
            return "".join(slots)

        def _dots(conv):
            n = {"alta": 3, "media": 2, "baja": 1}.get(conv, 0)
            return ("●" * n + "○" * (3 - n)) if n else "—"

        _md_guia_tablas(snap, A)
        A("## Posicionamiento (detalle)")
        A("")
        A("| Clase | Posición | Sesgo | Convicción | Nota |")
        A("|---|:---:|---|:---:|---|")
        for rp in pos:
            et = ("neutral" if rp["dir_tipo"] == "neutral"
                  else rp.get("etiqueta") or rp["dir_actual"])
            barra = f"`{_barra(rp['paso'], rp.get('paso_ant'))}`"
            nota = es_num(rp["nota"]) if rp.get("nota") else ""
            A(f"| {rp['label']} | {barra} | {et} | {_dots(rp.get('conv_actual'))} | {nota} |")
        A("")
        A("*Posición de adverso (izquierda) a favorable (derecha), en los términos de cada "
          "clase —corta duración e infra dólar son PRO-riesgo—. `●` hoy, `○` mes anterior si "
          "cambió. La nota solo aparece cuando la conclusión no sale de las señales o cuando "
          "técnicas y macro discrepan. La tabla completa con las señales técnicas y macro por "
          "separado está en el tablero.*")
        A("")

    a = snap.get("analogos") or {}
    if a.get("disponible"):
        if a.get("ventana_corta"):
            A(f"**Ventana de comparación limitada:** {_analog_ventana(a)}. Los "
              f"análogos no son informativos en esta fecha y no se publican "
              f"resultados.")
            A("")
        elif a.get("sin_analogos") or a.get("inusual"):
            n = 0 if a.get("sin_analogos") else a.get("n_comparables", 0)
            det, cola = _analog_inusual_txt(a, n)
            A(f"**Estado inusual:** {det}.{cola}")
            A("")
        else:
            cons = _analog_cons(a)
            n, H = a.get("n_comparables", 0), a.get("horizonte", 12)
            lis = [(clave, cons[clave]) for clave in _ANALOG_LECT if clave in cons]
            if lis:
                A(f"**Análogos: {n} episodios comparables (≥12 meses entre sí), a {H} "
                  f"meses.** No es un pronóstico: es lo que pasó entonces, y cada vez fue "
                  f"distinto.")
                A("")
                for clave, c in lis:
                    A(f"- **{_ANALOG_NOMBRE[clave]}:** {es_num(_consist_desc(c))}")
                A("")
                frase = _analog_disc_frase(snap)
                if frase:
                    A(f"*{es_num(frase)}*")
                    A("")

    _md_mandato(A)

    # ============================ EL TABLERO ============================
    A("---")
    A("")
    A("# Tablero de auditoría")
    A("")
    s = snap["senales"]

    A("## Ejes con dirección")
    A("")
    A("| Eje | Nivel | Percentil histórico | 1 mes | 3 meses |")
    A("|---|---:|---:|---:|---:|")
    for e in snap["ejes"]:
        desde = e["hist_since"].year if e["hist_since"] is not None else "—"
        A(f"| **{e['label']}** — {e['sub']} | {lvl_str(e['level'])}/100 | "
          f"{p_str(e['hist_pct'])} (desde {desde}) | {delta_pts(e['d1m'])} | "
          f"{delta_pts(e['d3m'])} |")
    A("")
    incoh = [e for e in snap["ejes"] if e.get("sin_lectura")]
    if incoh:
        A("*Sin lectura unificada hoy: " + "; ".join(
            f"{e['label'].lower()} (por {', '.join(pp.lower() for pp in e['sin_lectura'])})"
            for e in incoh) + " — el agregado se calcula, pero pesa menos en la convicción.*")
        A("")

    A("## Qué cambió desde el anterior, en detalle")
    A("")
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        A("Es el primer snapshot con memoria: no hay uno anterior con el que compararlo.")
    elif not c.get("algo"):
        A(f"**Sin cambios de inclinación ni de convicción desde "
          f"{fecha_larga(c['fecha_prev'])}.** Ninguna clase cambió de dirección, ningún "
          f"indicador entró o salió de extremo y ninguna divergencia nació o murió. Que "
          f"no cambie nada también es información —y es la lectura más común.")
    else:
        A(f"Cambios desde {fecha_larga(c['fecha_prev'])}. Solo lo que se movió.")
        A("")
        for d in c["dir_cambios"]:
            A(f"- **{d['clase']}**: {d['de']} → **{d['a']}**")
        for d in c["conv_cambios"]:
            A(f"- **{d['clase']}**: convicción {d['de'] or 'neutral'} → "
              f"**{d['a'] or 'neutral'}**")
        for e in c["entraron"]:
            A(f"- **{e['label']}** entró en extremo {e['tipo']} ({p_str(e['pct'])})")
        for e in c["salieron"]:
            A(f"- {e['label']} salió de su extremo")
        for d in c["div_nac"]:
            A(f"- Nueva divergencia: {d}")
        for d in c["div_mur"]:
            A(f"- Se cerró la divergencia: {d}")
        for p in c["pil_mov"]:
            A(f"- **{p['pilar']}** se movió {es_num('{:+.0f}'.format(p['delta']))} puntos "
              f"({es_num('{:.0f}'.format(p['de']))}→{es_num('{:.0f}'.format(p['a']))})")
        for tit in c["docs_nuevos"]:
            A(f"- Nueva fuente: {tit}")
    A("")

    A("## Dónde discrepan las señales")
    A("")
    A("Aquí vive todo lo que no coincide. Nada de esto refuta la lectura: ya está "
      "incorporado en la convicción de cada clase.")
    A("")
    cs = snap["contradicciones"]
    A(f"### Contradicción de alto perfil ({'1 de %d' % len(cs) if cs else '0'})")
    A("")
    if cs:
        c = cs[0]
        clases = _lista_es([fr["clase_label"].lower() for fr in c["frentes"]])
        n = c["n_frentes"]
        if c.get("cap") == "baja":
            efecto = (" Las lleva a convicción baja." if n > 1 else
                      " La lleva a convicción baja.")
        elif c.get("cap") == "media":
            efecto = " No deja pasar de convicción media a esas clases."
        else:
            efecto = (" Lleva tanto en su extremo que ya está absorbido: apunta en "
                      "contra, pero ya no rebaja la convicción (ver la lectura).")
        A(f"**{c['label']}**, en {p_str(c['pct'])} ({es_num(c['valor'])}), contradice "
          f"la lectura de {c['n_frentes']} "
          f"clase{'s' if c['n_frentes'] != 1 else ''}: {clases}.{efecto}")
        A("")
        A(f"**Qué implicaría si tiene razón:** {c['implica']}.")
        A("")
        A(f"**Qué habría que ver:** {c['observar']}.")
        A("")
        if len(cs) > 1:
            otros = _lista_es([f"{x['label']} en {p_str(x['pct'])}" for x in cs[1:]])
            A(f"*Hay {len(cs) - 1} extremo{'s' if len(cs) - 1 != 1 else ''} más "
              f"apuntando contra su clase ({otros}). No se detallan: ya están "
              f"reflejados en la convicción de su clase en la lectura.*")
            A("")
    else:
        A("Ningún indicador en extremo apunta en contra de la inclinación de su clase.")
        A("")
    A(f"### Entre pilares ({len(snap['divergencias'])})")
    A("")
    if snap["divergencias"]:
        for d in snap["divergencias"]:
            A(f"- **{d['alto_label']}** favorable ({p_str(d['alto_score'])}) frente a "
              f"**{d['bajo_label']}** adverso ({p_str(d['bajo_score'])}) — brecha de "
              f"{d['gap']:.0f} puntos, {d['duracion']}, desde el {fecha_larga(d['desde'])}.")
    else:
        A("**Señales alineadas.** Ningún par de pilares se contradice hoy. Que no haya "
          "divergencia no quiere decir que la lectura sea buena, solo que es coherente.")
    A("")

    intra = snap["div_intra"]["lista"]
    A(f"### Dentro de un mismo pilar ({len(intra)})")
    A("")
    if intra:
        A("Dos indicadores del mismo pilar diciendo cosas opuestas. La comparación entre "
          "pilares no ve esto, y en inflación y posicionamiento —que no entran en ningún "
          "eje— no hay ningún otro sitio del documento donde aparezca. Se muestra la "
          "contradicción más amplia de cada pilar; en total hay "
          f"{snap['div_intra']['pares']} pares.")
        A("")
        for d in intra:
            fuera = "" if d["en_eje"] else " *(no entra en ningún eje)*"
            A(f"- **{d['pilar_label']}**{fuera}: {d['alto_label']} "
              f"({es_num(d['alto_valor'])}, {p_str(d['alto_pct'])}) se lee favorable "
              f"y {d['bajo_label']} ({es_num(d['bajo_valor'])}, "
              f"{p_str(d['bajo_pct'])}) adverso — {d['gap']:.0f} puntos de diferencia, "
              f"{d['duracion']}, desde el {fecha_larga(d['desde'])}.")
    else:
        A("Ningún pilar se contradice por dentro.")
    A("")

    if snap["extremos"]:
        A(f"### Indicadores en extremo ({len(snap['extremos'])})")
        A("")
        A("| Indicador | Pilar | Valor | p5a | Lectura | Desde |")
        A("|---|---|---:|---:|---|---|")
        for e in snap["extremos"]:
            A(f"| {e['label']} | {e['pilar']} | {es_num(e['valor'])} | {p_str(e['pct'])} | "
              f"{e['tipo']} | {e['duracion']}, desde {fecha_corta(e['desde'])} |")
    else:
        A("### Indicadores en extremo")
        A("")
        A("Ninguno fuera de su banda p10–p90 a 5 años.")
    A("")

    # ---------------- qué dicen las fuentes (aporta) ----------------
    reg = snap["documentos"]
    A("## Qué dicen las fuentes")
    A("")
    A("> Solo lo que la fuente aporta y el tablero no ve: la lectura doble de un "
      "indicador y el porqué detrás de un dato. Nada de esto se suma al tablero. El texto "
      "completo, las citas y lo inferido, en el tablero de auditoría. Solo fuentes de las "
      "últimas dos semanas.")
    A("")
    descartes = []
    if reg["caducados"]:
        descartes.append(f"{reg['caducados']} por tener más de dos semanas")
    if reg["futuros"]:
        descartes.append(f"{reg['futuros']} por ser posteriores a la fecha del snapshot")
    if descartes:
        A(f"*Dejadas fuera: {' y '.join(descartes)}.*")
        A("")
    rel = reg["contrastes"]
    if rel:
        A("**Cómo se lee junto a los indicadores**")
        A("")
        for c in rel:
            f = c["fila"]
            cabeza = ("**Choque, pesa más un criterio.** " if c["postura"] == "resuelve"
                      else "")
            A(f"- {cabeza}{c['texto']}")
            if c["postura"] == "resuelve" and c.get("veredicto"):
                A(f"  - **Se queda con:** {c['veredicto']}")
            A(f"  - Indicador: **{f['label']}** — {es_num(f['valor'])}, "
              f"percentil {p_str(f['pct'])[1:]}, hoy se lee como {f['lectura']}.")
            A(f"  - Fuente: **{c['fuente']}**, {fecha_corta(c['fecha_ts'])} "
              f"({_dias(c['edad'])}).")
        A("")
    if reg["total"]:
        A("**Qué aporta cada análisis**")
        A("")
        for d in reg["documentos"]:
            A(f"- **{d['titulo']}** ({d['fuente']}, {fecha_corta(d['fecha_ts'])}, "
              f"{_dias(d['edad'])}) — {d['tesis']}")
            for x in d.get("aporta", []):
                A(f"  - {x}")
        A("")
    if not rel and not reg["total"]:
        A("Hoy no hay fuentes vigentes. El registro completo, más abajo.")
        A("")

    # ---- de dónde sale cada inclinación
    A("## De dónde sale cada inclinación")
    A("")
    A("«Indicadores» es el recuento crudo; «voces indep.», los mismos votos agrupados por "
      "correlación —un grupo que se mueve junto cuenta como una voz—. La convicción se "
      "decide sobre los segundos. **Alta**: las voces apuntan a lo mismo y ningún extremo "
      "las contradice. **Media**: mayoría clara con alguna voz en contra o una divergencia "
      "que parte la clase. **Baja**: un indicador en extremo apunta al contrario, o las "
      "voces se reparten. Si no alcanza ni para baja, **neutral**.")
    A("")
    A("| Clase | Inclinación | Convicción | Indicadores | Voces indep. | Qué limita la convicción |")
    A("|---|---|---|---:|---:|---|")
    for p in sorted(snap["postura"],
                    key=lambda x: (orden.get(x.get("conviccion"), 3), x["label"])):
        A(f"| {p['label']} | {p['direccion']} | {p.get('conviccion') or '—'} | "
          f"{p['n_a']} / {p['n_c']} | ≈{p['e_favor']:.1f} / ≈{p['e_contra']:.1f} | "
          f"{_limita_md(p)} |")
    A("")
    A("<details><summary>Qué indicadores pesan más en cada inclinación</summary>")
    A("")
    A("| Clase | Indicadores que más pesan |")
    A("|---|---|")
    for p in snap["postura"]:
        drv = "; ".join(p["drivers"]) if p["drivers"] else "—"
        A(f"| {p['label']} | {drv} |")
    A("")
    A("</details>")
    A("")
    # tabla completa de posicionamiento: señales técnicas y macro por separado
    pos = snap.get("posicionamiento") or []
    if pos:
        def _cellmd(v):
            return es_num((str(v).split("|", 1) + [""])[0])
        A("La tabla completa de posicionamiento, con las señales técnicas y macro por "
          "separado —lo que en la lectura se resume en el carril de posición—.")
        A("")
        A("| Dimensión de posicionamiento | Señales técnicas | Señales macro | Inclinación actual | Mes anterior |")
        A("|---|---|---|---|---|")
        for rp in pos:
            act = rp.get("dir_actual") or "—"
            if rp.get("conv_actual"):
                act = f"**{act} ({rp['conv_actual']})**"
            elif rp.get("dir_tipo") == "neutral":
                act = "**neutral**"
            else:
                act = f"**{act}**"
            if rp.get("dir_ant") in (None, "—"):
                ant = "—"
            else:
                ant = rp["dir_ant"] + (f" ({rp['conv_ant']})" if rp.get("conv_ant") else "")
            if rp.get("cambio"):
                ant = f"{ant} •"
            A(f"| {rp['label']} | {_cellmd(rp['tecnico'])} | {_cellmd(rp['macro'])} | "
              f"{act} | {ant} |")
        A("")
        A(f"*Señales técnicas: {config.lista_pilares(TECNICO_PILARES)}. Señales macro: "
          f"{config.lista_pilares(MACRO_PILARES)}. Cada celda apunta en los términos de "
          f"la clase. El • marca las clases que cambiaron respecto al mes anterior.*")
        A("")
    pp = (snap["senales"].get("por_pilar") or {}) if snap["senales"].get("disponible") else {}
    if pp:
        A("| Pilar | Indicadores | Grupos independientes |")
        A("|---|---:|---:|")
        for k, v in pp.items():
            if v["n"]:
                A(f"| {config.PILLARS[k]['label']} | {v['n']} | ≈{v['e']:.1f} |")
        A("")
        if snap["senales"].get("grupo_mayor"):
            g = snap["senales"]["grupo_mayor"]
            A(f"*El grupo más grande que se mueve como uno son {len(g)}: {'; '.join(g)}.*")
            A("")
    for rd in snap["redundancia"]:
        A(f"> **Redundancia alta.** {rd['pilar_label']} pone el {rd['share_n']:.0f}% de "
          f"los indicadores que votan sobre {rd['clase_label'].lower()} "
          f"({rd['n']} de {rd['n_total']}) y solo el {rd['share_e']:.0f}% de las voces: "
          f"quitarlo entero apenas cambiaría el recuento.")
        A("")

    # ---- detalle indicador por indicador
    A("## El detalle, indicador por indicador")
    A("")
    A("Percentil a 5 años: p50 es lo normal, p100 el máximo del lustro, p0 el mínimo. "
      "«Defiende» dice a qué activo ayuda la señal (+ a favor, − en contra): "
      + ", ".join(f"{m['short']} {m['label'].lower()}"
                  for m in config.ASSET_CLASSES.values()) + ".")
    A("")
    for p in snap["tablero"]:
        score = "—" if not np.isfinite(p["score"]) else f"{p['score']:.0f}"
        eje = p["eje"] or "contexto, no entra en ningún eje"
        A(f"### {p['label']} — {score}/100, {p['lectura']} ({delta_pts(p['d3m'])} en 3m)")
        A("")
        e = p.get("senales_e")
        sig = ("" if e is None or not p["n_datos"] else
               f" {p['n_datos']} indicadores que valen por ≈{e:.1f} señales "
               f"independientes.")
        A(f"*{p['desc']} {eje}.{sig}*")
        A("")
        A("| Indicador | Valor | p5a | Rango 5a (mín–máx) | Cambio 1m · 3m | Señal | Defiende |")
        A("|---|---:|---:|---|---|---|---|")
        for f in p["filas"]:
            señal = (f"**extremo {f['extremo_tipo']}**" if f["extremo"] else f["lectura"])
            votos = " ".join(
                f"{config.ASSET_CLASSES[ck]['short']}{'+' if v > 0 else '-'}"
                for ck, v in f["votos"].items() if v) or "—"
            rango = (f"{es_num(f['rmin'])} – {es_num(f['rmax'])}"
                     if f.get("rmin") not in (None, "—") else "—")
            A(f"| {f['label']} | {es_num(f['valor'])} | {p_str(f['pct'])} | {rango} | "
              f"{es_num(f['d1m'])} · {es_num(f['d3m'])} | {señal} | {votos} |")
        A("")

    A("## Análogos históricos")
    A("")
    A("> Un análogo no es un pronóstico: muestra qué pasó tras estados parecidos, y el "
      "desenlace fue distinto cada vez. Contexto, no predicción.")
    A("")
    a = snap["analogos"]

    def _muestra_md(a):
        m = a.get("muestra")
        if not m:
            return
        eps = (f", y las {a['n']} fechas caen en {a['n_episodios']} episodios distintos"
               if a.get("n_episodios") else "")
        A(f"*Muestra: {m['n']:,} fechas elegibles ({fecha_corta(m['desde'])} a "
          f"{fecha_corta(m['hasta'])}, unos {m['anos']:.0f} años) — las que tienen doce "
          f"meses de futuro por delante. Esos {m['anos']:.0f} años contienen "
          f"{m['episodios']} entornos macro distintos{eps}. Con tan pocos regímenes de "
          f"verdad distintos, cualquier promedio histórico descansa sobre menos "
          f"observaciones de las que parece.*")
        A("")

    if not a.get("disponible"):
        A("Todavía no hay suficiente historia con los siete pilares para buscar análogos.")
    elif a.get("sin_analogos"):
        _muestra_md(a)
        A(f"**Sin análogos cercanos.** El estado de hoy no se parece lo suficiente a "
          f"ninguna fecha del pasado: el más cercano difiere en {a['nearest']:.0f} puntos "
          f"por pilar, por encima del umbral de {a['umbral']:.0f}. No se fuerzan cinco "
          f"fechas que confundirían.")
    else:
        cols = a["columnas"]
        H = a["horizonte"]
        hs = a["horizontes"]
        sh_hdr = " | ".join(sh for _c, sh, _et in cols)
        _muestra_md(a)

        if a.get("nulo"):
            A("> **Sin análogos comparables.** El estado actual no tiene precedentes "
              "suficientemente independientes en la historia disponible. No se publican "
              "la media ni la dispersión: saldría un número con apariencia de muestra y "
              "cuerpo de una sola observación. Por qué:")
            A(">")
            for rz in a.get("nulo_razon", []):
                A(f"> - {rz}")
            A(">")
            A("> Las fechas sí se quedan: un desenlace concreto, con su fecha y su "
              "contexto, sigue informando; el promedio de todos ellos, no.")
            A("")

        A("**Qué pasó después de cada análogo** (rendimiento por dimensión de posicionamiento y "
          "volatilidad realizada del S&P, en cada ventana). *Dinámica* mide si el "
          "mercado se comportaba igual; *entorno*, si el mundo era el mismo:")
        A("")
        A(f"| Análogo | Lectura | Dinámica | Entorno | Ventana | {sh_hdr} | Vol. |")
        A("|---|---|---:|---:|---|" + "|".join(["---:"] * (len(cols) + 1)) + "|")
        for x in a["lista"]:
            d = x["fecha"]
            for i, m in enumerate(hs):
                rets = " | ".join(
                    (f"{x['ret'][m][c]:+.0f}%" if x['ret'][m][c] == x['ret'][m][c] else "—")
                    for c, _sh, _et in cols)
                v = x["vol"][m]
                vol = f"{v:.0f}%" if v == v else "—"
                fecha = f"{_MESES_CORTO[d.month - 1]} {d.year}" if i == 0 else ""
                cal = x["etiqueta"] if i == 0 else ""
                din = f"{x['dist']:.1f} ({x['calidad']})" if i == 0 else ""
                env = ((f"{x['env']:.2f}σ ({x['env_calidad']})"
                        if x["env"] == x["env"] else "—") if i == 0 else "")
                A(f"| {fecha} | {cal} | {din} | {env} | {m}m | {rets} | {vol} |")
        A("")
        if a.get("env_faltan"):
            A(f"*Entorno calculado con {a['env_n']} de {len(config.ENV_VARS)} variables: "
              f"sin dato de {', '.join(x.lower() for x in a['env_faltan'])}.*")
            A("")
        A("**En qué se parece cada análogo y en qué no** — entre paréntesis, los puntos "
          "de diferencia en ese pilar:")
        A("")
        A("| Análogo | Se parece en | Se aleja en |")
        A("|---|---|---|")
        for x in a["lista"]:
            d = x["fecha"]
            ig = "; ".join(f"{l.lower()} ({g:.0f})" for l, g in x["iguales"])
            di = "; ".join(f"{l.lower()} ({g:.0f})" for l, g in x["distintos"])
            A(f"| {_MESES_CORTO[d.month - 1]} {d.year} | {ig} | {di} |")
        A("")

    if a.get("disponible") and not a.get("sin_analogos") and not a.get("nulo"):
        cols, H, hs = a["columnas"], a["horizonte"], a["horizontes"]
        A(f"**Media y rango de los {a['n']} análogos, por horizonte** — media con el "
          f"rango (peor a mejor) entre paréntesis:")
        A("")
        por_h = {f["horizonte"]: f for f in a["trayectoria"]}
        A("| Clase | " + " | ".join(f"{m} meses" for m in hs) + " |")
        A("|---|" + "|".join(["---"] * len(hs)) + "|")

        def _cel(st):
            if not (st["media"] == st["media"]):
                return "—"
            return f"{st['media']:+.0f}% ({st['min']:+.0f} a {st['max']:+.0f})"

        for r in a["promedio"]:
            vals = " | ".join(_cel(por_h[m]["valores"][r["clave"]]) for m in hs)
            A(f"| {r['etiqueta']} | {vals} |")
        vv = " | ".join(
            (f"{por_h[m]['vol']['media']:.0f}% ({por_h[m]['vol']['min']:.0f} a "
             f"{por_h[m]['vol']['max']:.0f})" if por_h[m]['vol']['media'] == por_h[m]['vol']['media']
             else "—") for m in hs)
        A(f"| Vol. realizada S&P | {vv} |")
        if a.get("n_otro_mundo"):
            A("")
            A(f"*Ojo: {a['n_otro_mundo']} de los {a['n']} análogos se comportaban igual "
              f"pero en otro entorno. La media los incluye a todos.*")
    A("")

    A("## Cómo leer esto")
    A("")
    A("- **Nada mira al futuro.** Los percentiles son de ventana móvil hacia atrás (5 "
      "años en el tablero, toda la historia en los ejes) y cada serie macro entra en la "
      "fecha en que se publicó, no en la de su periodo.")
    A("- **Percentil alto no es «bueno»: es alto.** La etiqueta favorable o adverso "
      "aplica el signo de cada serie, y es lo único que permite comparar pilares.")
    A("- **Los agregados van suavizados.** El nivel de los ejes, la puntuación y todos "
      "los deltas se calculan contra una ventana de días hábiles, no contra un cierre "
      "suelto, para que el rumbo no cambie sin que cambie el mercado.")
    A("- **Posicionamiento e inflación no entran en ningún eje, a propósito.** La "
      "inflación, porque su signo depende del régimen; el posicionamiento, porque mejora "
      "justo cuando todo cae. Fuera, esa tensión se lee como divergencia.")
    A("")

    A("## Comprobaciones de esta ejecución")
    A("")
    A("Se ejecutan cada vez que se genera el documento y se imprimen siempre, salgan "
      "como salgan. Ninguna corrige nada por detrás: informan de dónde puede fallar lo "
      "de arriba. `OK` pasó · `!` hay algo que mirar · `?` no se pudo calcular.")
    A("")
    A("| | Comprobación | Resultado |")
    A("|---|---|---|")
    marca = {"ok": "OK", "aviso": "!", "nd": "?"}
    for c in snap.get("comprobaciones") or []:
        nota = f" — {es_num(c['nota'])}" if c.get("nota") else ""
        A(f"| `{marca.get(c['estado'], '·')}` | {c['label']} | "
          f"{es_num(c['valor'])}{nota} |")
    A("")

    # ---- fuentes, texto completo (el rastro): titulares + citas + inferido
    A("## Fuentes, texto completo")
    A("")
    if reg["n_titulares"]:
        A("### Titulares recientes")
        A("")
        for h in reg["titulares"]:
            fuente = f"[{h['fuente']}]({h['url']})" if h.get("url") else h["fuente"]
            A(f"- **{fecha_corta(h['fecha_ts'])}** — {h['texto']} "
              f"· {fuente} ({_dias(h['edad'])})")
        A("")
    if reg["total"]:
        A("### Análisis y research")
        A("")
        for d in reg["documentos"]:
            A(f"#### {d['titulo']}")
            A("")
            A(f"{d['fuente']}"
              + (f" · {d['autor']}" if d.get("autor") else "")
              + f" · {fecha_corta(d['fecha_ts'])} · {d['tipo_label']} · "
                f"{_dias(d['edad'])}.")
            A("")
            A(f"{d['tesis']}")
            A("")
            if d.get("dice"):
                A("**Lo que dice, textual:**")
                A("")
                for x in d["dice"]:
                    ref = f" [{x['ref']}]" if x.get("ref") else ""
                    A(f"- {x['texto']}{ref}")
                A("")
            if d.get("infiero"):
                A("**Lectura propia, no del documento:**")
                A("")
                for x in d["infiero"]:
                    A(f"- *{x}*")
                A("")
            A(f"Origen: `{d.get('ruta') or d.get('url') or '—'}`")
            A("")
    if not reg["n_titulares"] and not reg["total"]:
        A("Sin fuentes vigentes.")
        A("")

    A("---")
    A("")
    A("Fuentes de datos: FRED, Yahoo Finance y Bloomberg (caché local). Documento "
      "descriptivo, sin recomendación de inversión.")
    A("")
    return "\n".join(L)


__all__ = ["render_html", "render_md"]
