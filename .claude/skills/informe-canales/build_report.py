#!/usr/bin/env python3
"""
build_report.py — Arma el informe de alertas por canal para el equipo comercial.

Lee el objeto DATA_BUNDLE ya calculado dentro de dashboards/presupuesto-vs-real.html
(lo genera el skill presupuesto-vs-real con compute.py) y produce, en --out:

  tarjetas.html  — una tarjeta por canal/responsables ($ y unidades vs. meta, con
                   la marca de lo esperado a la fecha y el semáforo). render.js le
                   toma un screenshot a cada tarjeta -> online.png, showroom.png,
                   mayoristas.png.
  correo.html    — cuerpo del correo (HTML simple con estilos inline). Las imágenes
                   apuntan a {{IMG_BASE}}/<canal>.png: se reemplaza por la URL raw
                   de GitHub fijada al commit que subió las imágenes (ver SKILL.md).
  asunto.txt     — asunto del correo.
  resumen.json   — los textos y cifras usados (para revisar o reusar).

No hace aritmética de negocio propia: toma real/meta/ritmo/semáforo tal cual del
DATA_BUNDLE. Lo único que calcula es lo que falta por día para cumplir la meta
((meta - real) / días restantes), que es una resta y una división sobre esas cifras.

Uso:
  python3 build_report.py --html dashboards/presupuesto-vs-real.html \
      --team .claude/skills/informe-canales/equipo.json \
      --out informes/canales/2026-10-12 \
      --dashboard-url https://mtrujillo45.github.io/Ventas-FLA/dashboards/presupuesto-vs-real.html
"""
import argparse
import html as html_lib
import json
import os
import re

STATUS = {
    # Paleta de estado fija (dataviz/references/palette.md). Siempre con icono + texto.
    "verde": {"color": "#0ca30c", "track": "#d5efd5", "icon": "✓", "label": "VERDE"},
    "amarillo": {"color": "#fab219", "track": "#fdeccb", "icon": "▲", "label": "AMARILLO"},
    "rojo": {"color": "#d03b3b", "track": "#f5d6d6", "icon": "●", "label": "ROJO"},
}
INK = "#1f1f1e"
INK_2 = "#5c5c58"
INK_3 = "#8a8a85"
BORDER = "#e4e2dc"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def stoplight(pct):
    return "verde" if pct >= 100 else ("amarillo" if pct >= 85 else "rojo")


def money_short(n):
    n = float(n)
    if abs(n) >= 1e6:
        return f"${n / 1e6:,.1f}M"
    if abs(n) >= 1e3:
        return f"${n / 1e3:,.0f}K"
    return f"${n:,.0f}"


def num(n):
    return f"{int(round(n)):,}".replace(",", ".")


def pct(p):
    return f"{p:.1f}%"


def load_bundle(path):
    with open(path, encoding="utf-8") as f:
        h = f.read()
    m = re.search(r"const DATA_BUNDLE = (\{.*?\});\n", h)
    if not m:
        raise SystemExit("No se encontró DATA_BUNDLE en el HTML del dashboard")
    return json.loads(m.group(1))


def needed_per_day(budget, real, days_left):
    if days_left <= 0:
        return None
    return max(budget - real, 0) / days_left


def meter(label, real_txt, budget_txt, pct_month, pace, pct_elapsed, status_key, expected_txt):
    s = STATUS[status_key]
    fill = max(0.0, min(pct_month, 100.0))
    marker = max(0.0, min(pct_elapsed, 100.0))
    return f"""
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">{label}</span>
        <span class="metric-pace">Ritmo <b>{pct(pace)}</b>
          <span class="chip" style="color:{s['color']};border-color:{s['color']}">{s['icon']} {s['label']}</span></span>
      </div>
      <div class="metric-value"><b>{real_txt}</b> <span class="of">de {budget_txt}</span>
        <span class="pct">{pct(pct_month)} de la meta</span></div>
      <div class="track" style="background:{s['track']}">
        <div class="fill" style="width:{fill:.2f}%;background:{s['color']}"></div>
        <div class="marker" style="left:{marker:.2f}%"></div>
      </div>
      <div class="marker-note">Esperado a la fecha: {expected_txt} (línea vertical)</div>
    </div>"""


def channel_block(c, meta, show_title):
    days_left = meta["daysInMonth"] - meta["daysElapsed"]
    pe = meta["pctElapsed"]
    st_v = c.get("semaforoValue") or stoplight(c["paceValue"])
    st_u = c.get("semaforoUnits") or stoplight(c["paceUnits"])
    exp_v = c["budgetValue"] * pe / 100
    exp_u = c["budgetUnits"] * pe / 100
    title = f'<div class="sub-title">{html_lib.escape(c["label"])}</div>' if show_title else ""
    return title + meter("Ventas en pesos", money_short(c["realValue"]), money_short(c["budgetValue"]),
                         c["pctValue"], c["paceValue"], pe, st_v, money_short(exp_v)) + \
        meter("Unidades", num(c["realUnits"]), num(c["budgetUnits"]),
              c["pctUnits"], c["paceUnits"], pe, st_u, num(exp_u))


def summary_text(c, meta):
    """Resumen de 1-2 frases por canal, solo con cifras del DATA_BUNDLE."""
    days_left = meta["daysInMonth"] - meta["daysElapsed"]
    st = c.get("semaforoValue") or stoplight(c["paceValue"])
    parts = [
        f"En {STATUS[st]['label'].lower()}: {money_short(c['realValue'])} de {money_short(c['budgetValue'])} "
        f"({pct(c['pctValue'])} de la meta, ritmo {pct(c['paceValue'])}) y {num(c['realUnits'])} de "
        f"{num(c['budgetUnits'])} unidades (ritmo {pct(c['paceUnits'])})."
    ]
    nv = needed_per_day(c["budgetValue"], c["realValue"], days_left)
    nu = needed_per_day(c["budgetUnits"], c["realUnits"], days_left)
    if nv is None:
        parts.append("Mes cerrado.")
    elif nv == 0:
        parts.append("Meta del mes ya cumplida.")
    else:
        parts.append(f"Para cumplir faltan {money_short(c['budgetValue'] - c['realValue'])}: "
                     f"{money_short(nv)} y {num(nu)} unidades por día en los {days_left} días restantes.")
    return " ".join(parts)


CARD_CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 24px; background: #f4f3ef; font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: {INK}; }}
.card {{ width: 600px; background: #ffffff; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px 22px 16px; margin-bottom: 24px; }}
.card-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }}
.card-title {{ font-size: 20px; font-weight: 700; margin-bottom: 2px; }}
.card-cut {{ font-size: 12px; color: {INK_3}; }}
.owners {{ font-size: 13px; color: {INK_2}; margin-bottom: 14px; }}
.sub-title {{ font-size: 14px; font-weight: 700; margin: 14px 0 2px; padding-top: 12px; border-top: 1px solid {BORDER}; }}
.sub-title:first-of-type {{ border-top: none; padding-top: 0; margin-top: 4px; }}
.metric {{ margin: 10px 0 14px; }}
.metric-head {{ display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: {INK_2}; text-transform: uppercase; letter-spacing: .03em; }}
.metric-pace {{ text-transform: none; letter-spacing: 0; font-size: 13px; color: {INK_2}; }}
.metric-pace b {{ color: {INK}; }}
.chip {{ display: inline-block; margin-left: 6px; padding: 1px 8px; border: 1.5px solid; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .03em; background: #fff; }}
.metric-value {{ font-size: 15px; margin: 4px 0 6px; color: {INK_2}; }}
.metric-value b {{ font-size: 22px; color: {INK}; }}
.metric-value .of {{ color: {INK_2}; }}
.metric-value .pct {{ float: right; font-size: 13px; color: {INK_2}; margin-top: 8px; }}
.track {{ position: relative; height: 12px; border-radius: 6px; overflow: visible; }}
.fill {{ height: 12px; border-radius: 6px; }}
.marker {{ position: absolute; top: -4px; width: 2px; height: 20px; background: {INK}; border-radius: 1px; transform: translateX(-1px); }}
.marker-note {{ font-size: 11px; color: {INK_3}; margin-top: 5px; }}
.need {{ font-size: 13px; color: {INK_2}; background: #f7f6f2; border-radius: 8px; padding: 8px 10px; margin-top: 6px; }}
.need b {{ color: {INK}; }}
"""


def need_line(c, meta):
    days_left = meta["daysInMonth"] - meta["daysElapsed"]
    nv = needed_per_day(c["budgetValue"], c["realValue"], days_left)
    nu = needed_per_day(c["budgetUnits"], c["realUnits"], days_left)
    if nv is None:
        return "Mes cerrado."
    if nv == 0:
        return "Meta del mes cumplida."
    return (f"Para cumplir: <b>{money_short(nv)}/día</b> y <b>{num(nu)} und/día</b> "
            f"en los {days_left} días restantes.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--team", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dashboard-url", default="https://mtrujillo45.github.io/Ventas-FLA/dashboards/presupuesto-vs-real.html")
    args = ap.parse_args()

    bundle = load_bundle(args.html)
    month = bundle["byMonth"][bundle["currentMonthKey"]]
    meta = month["meta"]
    by_key = {c["key"]: c for c in month["channels"]}
    team = json.load(open(args.team, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)

    cut = meta["cutoff"]
    cut_short = " ".join(cut.split(" ")[:2])
    cards, sections, resumen = [], [], {"cutoff": cut, "month": meta["period"], "grupos": []}
    for g in team["grupos"]:
        chans = [by_key[k] for k in g["canales"]]
        names = " y ".join(p["nombre"] for p in g["responsables"])
        body = ""
        for c in chans:
            body += channel_block(c, meta, show_title=len(chans) > 1)
            body += f'<div class="need">{need_line(c, meta)}</div>'
        cards.append(f"""
  <div class="card" id="card-{g['id']}">
    <div class="card-title">{html_lib.escape(g['titulo'])}</div>
    <div class="owners">Responsables: {html_lib.escape(names)} · {meta['period']}, corte {html_lib.escape(cut_short)} (día {meta['daysElapsed']} de {meta['daysInMonth']})</div>
    {body}
  </div>""")
        texts = [(c["label"], summary_text(c, meta)) for c in chans]
        resumen["grupos"].append({"id": g["id"], "titulo": g["titulo"], "responsables": names,
                                  "textos": [{"canal": l, "texto": t} for l, t in texts]})
        st = min((c.get("semaforoValue") or stoplight(c["paceValue"]) for c in chans),
                 key=lambda s: ["rojo", "amarillo", "verde"].index(s))
        s = STATUS[st]
        txt_html = "".join(
            f'<p style="margin:0 0 8px;font-size:14px;line-height:1.5;color:{INK}">'
            f'{"<b>" + html_lib.escape(l) + ":</b> " if len(chans) > 1 else ""}{html_lib.escape(t)}</p>'
            for l, t in texts)
        alt = "; ".join(f"{c['label']}: {money_short(c['realValue'])} de {money_short(c['budgetValue'])}, "
                        f"{num(c['realUnits'])} de {num(c['budgetUnits'])} unidades" for c in chans)
        sections.append(f"""
      <tr><td style="padding:22px 0 6px;border-top:1px solid {BORDER}">
        <div style="font-size:17px;font-weight:700;color:{INK}">{html_lib.escape(g['titulo'])}
          <span style="font-size:12px;font-weight:700;color:{s['color']};border:1.5px solid {s['color']};border-radius:999px;padding:1px 8px;margin-left:6px">{s['icon']} {s['label']}</span></div>
        <div style="font-size:13px;color:{INK_2};margin:2px 0 10px">Responsables: {html_lib.escape(names)}</div>
        {txt_html}
      </td></tr>
      <tr><td style="padding:4px 0 8px"><img src="{{{{IMG_BASE}}}}/{g['id']}.png" width="600" alt="{html_lib.escape(alt)}" style="display:block;width:100%;max-width:600px;height:auto;border:0"></td></tr>""")

    with open(os.path.join(args.out, "tarjetas.html"), "w", encoding="utf-8") as f:
        f.write(f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Tarjetas por canal</title>"
                f"<style>{CARD_CSS}</style></head><body>{''.join(cards)}</body></html>")

    t = month["total"]
    st_t = stoplight(t["paceValue"])
    intro = (f"Así vamos en {meta['monthLabel'].lower()} al corte del {cut.split(',')[0]} "
             f"(día {meta['daysElapsed']} de {meta['daysInMonth']}, {pct(meta['pctElapsed'])} del mes): "
             f"<b>{money_short(t['realValue'])}</b> de {money_short(t['budgetValue'])} "
             f"({pct(t['pctValue'])} de la meta), ritmo <b>{pct(t['paceValue'])}</b> "
             f"<span style='color:{STATUS[st_t]['color']};font-weight:700'>{STATUS[st_t]['icon']} {STATUS[st_t]['label']}</span>.")
    resumen["total"] = {"realValue": t["realValue"], "budgetValue": t["budgetValue"], "paceValue": t["paceValue"]}
    correo = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f3ef">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f3ef"><tr><td align="center" style="padding:20px 12px">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:12px;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
      <tr><td style="padding:24px 20px 0">
        <div style="font-size:12px;color:{INK_3};text-transform:uppercase;letter-spacing:.04em">Mompossina · Presupuesto vs. real por canal</div>
        <div style="font-size:21px;font-weight:700;color:{INK};margin:4px 0 12px">Alertas de cumplimiento — {meta['period']}</div>
        <p style="margin:0 0 6px;font-size:14px;line-height:1.5;color:{INK}">Hola equipo,</p>
        <p style="margin:0 0 6px;font-size:14px;line-height:1.5;color:{INK}">{intro}</p>
        <p style="margin:0 0 4px;font-size:13px;line-height:1.5;color:{INK_2}">El <b>ritmo</b> compara lo vendido contra lo que deberíamos llevar a la fecha (meta × días transcurridos). Semáforo: verde ≥100%, amarillo 85–99%, rojo &lt;85%.</p>
      </td></tr>
      <tr><td style="padding:0 20px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{''.join(sections)}</table></td></tr>
      <tr><td style="padding:14px 20px 24px;font-size:12px;color:{INK_3};line-height:1.5;border-top:1px solid {BORDER}">
        Dashboard completo: <a href="{args.dashboard_url}" style="color:#2a62c9">{args.dashboard_url}</a><br>
        Venta neta sin IVA. Online y Showroom: pedidos de Shopify. Mayoristas: facturas electrónicas del mes (Drive).
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""
    with open(os.path.join(args.out, "correo.html"), "w", encoding="utf-8") as f:
        f.write(correo)
    d = meta["cutoff"].split(" ")
    asunto = f"Ventas vs. meta por canal — corte {d[0]} {d[1]} · ritmo {pct(t['paceValue'])} ({STATUS[st_t]['label'].lower()})"
    with open(os.path.join(args.out, "asunto.txt"), "w", encoding="utf-8") as f:
        f.write(asunto)
    with open(os.path.join(args.out, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(asunto)
    for g in resumen["grupos"]:
        print(f"\n[{g['titulo']}] {g['responsables']}")
        for t_ in g["textos"]:
            print(f"  {t_['canal']}: {t_['texto']}")


if __name__ == "__main__":
    main()
