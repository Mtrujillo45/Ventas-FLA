#!/usr/bin/env python3
"""Arma el correo del día 1 con la meta del mes por canal ($ y unidades).

Lee la meta de .claude/skills/presupuesto-vs-real/plan_2026_2027.json (la misma
fuente del dashboard Presupuesto vs. Real) y los grupos de equipo.json del
informe por canal. No hace aritmética de negocio más allá de repartir la meta
en días y calcular el ticket implícito (meta $ / meta unidades).

Uso:
  python3 build_budget_mail.py --month 2026-12 --out informes/presupuesto-mes/2026-12

Sale con código 2 si el mes no está en el plan (no se envía nada).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "..", "presupuesto-vs-real", "plan_2026_2027.json")
TEAM = os.path.join(HERE, "..", "informe-canales", "equipo.json")

# Se factura por despachos: no se reparte en "por día".
BY_SHIPMENT = {"internacional"}

INK, MUTED, LINE, PAGE = "#1f1f1e", "#5c5c58", "#e4e2dc", "#f4f3ef"
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def money(v):
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def units(n):
    return f"{n:,.0f}".replace(",", ".")


def pct_change(new, old):
    if not old:
        return ""
    d = (new - old) / old * 100
    sign = "+" if d >= 0 else "−"
    return f"{sign}{abs(d):.0f}%"


def prev_month(plan, month):
    order = plan["period_order"]
    i = order.index(month)
    return order[i - 1] if i > 0 else None


def channel_row(label, cur, prev, days, by_shipment):
    v, u = cur["budgetValue"], cur["budgetUnits"]
    ticket = money(v / u) if u else "—"
    if by_shipment:
        per_day = "Por despachos"
    else:
        per_day = f"{money(v / days)} · {units(round(u / days))} und"
    vs = ""
    if prev:
        vs = f"{pct_change(v, prev['budgetValue'])} vs. meta mes anterior ({money(prev['budgetValue'])})"
    td = f"padding:8px 6px;border-bottom:1px solid {LINE};font-size:14px;color:{INK}"
    return (
        f"<tr><td style=\"{td};font-weight:700\">{label}</td>"
        f"<td style=\"{td};text-align:right;font-weight:700\">{money(v)}</td>"
        f"<td style=\"{td};text-align:right;font-weight:700\">{units(u)}</td>"
        f"<td style=\"{td};text-align:right\">{per_day}</td>"
        f"<td style=\"{td};text-align:right\">{ticket}</td></tr>"
        + (f"<tr><td colspan=\"5\" style=\"padding:2px 6px 8px;font-size:12px;color:{MUTED}\">{vs}</td></tr>" if vs else "")
    )


def build(month, out):
    plan = json.load(open(PLAN, encoding="utf-8"))
    team = json.load(open(TEAM, encoding="utf-8"))
    if month not in plan["months"]:
        print(f"El mes {month} no está en plan_2026_2027.json: no hay meta cargada.", file=sys.stderr)
        sys.exit(2)

    m = plan["months"][month]
    pm = prev_month(plan, month)
    pch = plan["months"][pm]["channels"] if pm else {}
    days = m["daysInMonth"]
    labels = plan["channel_labels"]
    mes = m["label"].split(" ")[0].lower()

    tot_v = sum(c["budgetValue"] for c in m["channels"].values())
    tot_u = sum(c["budgetUnits"] for c in m["channels"].values())

    head = (
        f"<tr><th style=\"text-align:left;padding:6px;font-size:12px;color:{MUTED};font-weight:600\">Canal</th>"
        f"<th style=\"text-align:right;padding:6px;font-size:12px;color:{MUTED};font-weight:600\">Meta $</th>"
        f"<th style=\"text-align:right;padding:6px;font-size:12px;color:{MUTED};font-weight:600\">Meta und</th>"
        f"<th style=\"text-align:right;padding:6px;font-size:12px;color:{MUTED};font-weight:600\">Promedio por día</th>"
        f"<th style=\"text-align:right;padding:6px;font-size:12px;color:{MUTED};font-weight:600\">Ticket</th></tr>"
    )

    sections = []
    for g in team["grupos"]:
        rows = "".join(
            channel_row(labels[c], m["channels"][c], pch.get(c), days, c in BY_SHIPMENT)
            for c in g["canales"]
        )
        gv = sum(m["channels"][c]["budgetValue"] for c in g["canales"])
        gu = sum(m["channels"][c]["budgetUnits"] for c in g["canales"])
        if len(g["canales"]) > 1:
            td = f"padding:8px 6px;font-size:14px;color:{INK};font-weight:700"
            rows += (
                f"<tr><td style=\"{td}\">Total del grupo</td><td style=\"{td};text-align:right\">{money(gv)}</td>"
                f"<td style=\"{td};text-align:right\">{units(gu)}</td><td colspan=\"2\"></td></tr>"
            )
        nombres = " y ".join(r["nombre"] for r in g["responsables"])
        sections.append(
            f"<tr><td style=\"padding:22px 0 6px;border-top:1px solid {LINE}\">"
            f"<div style=\"font-size:17px;font-weight:700;color:{INK}\">{g['titulo']}</div>"
            f"<div style=\"font-size:13px;color:{MUTED};margin:2px 0 10px\">Responsables: {nombres}</div>"
            f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">{head}{rows}</table>"
            f"</td></tr>"
        )

    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{PAGE}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE}"><tr><td align="center" style="padding:20px 12px">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:12px;font-family:{FONT}">
      <tr><td style="padding:24px 20px 0">
        <div style="font-size:12px;color:#8a8a85;text-transform:uppercase;letter-spacing:.04em">Mompossina · Presupuesto del mes por canal</div>
        <div style="font-size:21px;font-weight:700;color:{INK};margin:4px 0 12px">Meta de {m['label']}</div>
        <p style="margin:0 0 6px;font-size:14px;line-height:1.5;color:{INK}">Hola equipo,</p>
        <p style="margin:0 0 6px;font-size:14px;line-height:1.5;color:{INK}">Esta es la meta de {mes} para cada canal. Entre todos: <b>{money(tot_v)}</b> y <b>{units(tot_u)} unidades</b> en {days} días.</p>
        <p style="margin:0 0 4px;font-size:13px;line-height:1.5;color:{MUTED}">Cifras <b>sin IVA</b>. <b>Promedio por día</b> = meta ÷ {days} días; es la referencia del "esperado a la fecha" que verán en el informe de cumplimiento de los lunes y miércoles. <b>Ticket</b> = meta en pesos ÷ meta en unidades. Mayoristas internacionales se factura por despachos, por eso no se reparte por día.</p>
      </td></tr>
      <tr><td style="padding:0 20px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      {''.join(sections)}
      </table></td></tr>
      <tr><td style="padding:18px 20px 24px;font-size:12px;color:#8a8a85">Meta tomada del Plan Estratégico 2026-2027. Correo automático de operaciones@mompossina.com.</td></tr>
    </table>
  </td></tr></table>
</body></html>
"""
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "correo.html"), "w", encoding="utf-8").write(html)
    subject = f"Meta de {mes} por canal — {money(tot_v)} y {units(tot_u)} unidades"
    open(os.path.join(out, "asunto.txt"), "w", encoding="utf-8").write(subject + "\n")
    print(subject)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(a.month, a.out)
