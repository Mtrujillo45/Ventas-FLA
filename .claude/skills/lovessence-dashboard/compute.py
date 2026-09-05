#!/usr/bin/env python3
"""
compute.py — Motor de cálculo del dashboard de LOVESSENCE (Mompossina, Shopify).

Toda la aritmética vive AQUÍ, no en el modelo (mismo principio que cierre-mensual
y monitor-medellin). Lee JSON agregados ya armados por el modelo a partir de las
consultas a Shopify (ver SKILL.md para las queries exactas), calcula KPIs,
rankings, alertas de inventario y la tabla de cohortes, y PARCHEA el dashboard
fuente (dashboards/lovessence.html) entre marcadores.

Uso:
  python3 compute.py \
      --skus skus.json --kpis kpis.json --cities cities.json \
      --traffic traffic.json --cohort cohort.json \
      --html /ruta/a/dashboards/lovessence.html \
      --now "2026-09-05T18:00:00-05:00"

Formato de cada JSON de entrada:

  skus.json    Lista de objetos, uno por SKU/variante de la colección:
               {"product": str, "talla": str, "sku": str, "price": num,
                "units": int, "gross": num, "net": num, "orders": int,
                "stock": int}

  kpis.json    {"since": str, "until_label": str,
                "orders_lovessence": int, "orders_store": int,
                "aov_lovessence_order": num, "aov_store_order": num,
                "customers_new": int, "customers_existing": int,
                "customers_noaccount": int}
               (gross/net/units/stock del total se derivan de skus.json)

  cities.json  Lista ordenada desc por orders:
               {"city": str, "orders": int, "total": num}

  traffic.json Lista ordenada desc por orders:
               {"source": str, "orders": int}

  cohort.json  {"cohorts": [{"label": str, "new_customers": int,
                              "r30": num|null, "r60": num|null, "r90": num|null,
                              "flag": str|null}, ...],
                "lifetime_repurchase_rate": num,
                "trailing90_repurchase_rate": num,
                "median_days_2nd": num, "mean_days_2nd": num,
                "campaign_note": str}

Umbrales de alerta de inventario (stock ABSOLUTO, no velocidad — con <2 días de
datos la velocidad es demasiado ruidosa para estimar cobertura por SKU; ver nota
en SKILL.md sobre cuándo pasar a cobertura por velocidad):
  stock == 0        -> "sin inventario" (crítico)
  0 < stock <= 5    -> "stock crítico"
  5 < stock <= 15   -> "vigilar"
  stock > 15        -> "saludable"
"""
import json
import argparse
import re
from collections import OrderedDict


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def money(n):
    return "${:,.0f}".format(round(float(n)))


def money_short(n):
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000:
        return f"{sign}${n / 1_000_000:,.1f}M"
    if n >= 1_000:
        return f"{sign}${n / 1_000:,.0f}K"
    return f"{sign}${n:,.0f}"


def pct(part, whole):
    return (part / whole * 100) if whole else 0.0


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------- inventory

def stock_badge(stock):
    if stock <= 0:
        return "sin inventario", "critical"
    if stock <= 5:
        return "stock crítico", "critical"
    if stock <= 15:
        return "vigilar", "warning"
    return "saludable", "good"


def group_by_product(skus):
    groups = OrderedDict()
    for s in skus:
        groups.setdefault(s["product"], []).append(s)
    return groups


# ---------------------------------------------------------------- KPIs

def build_kpis(skus, kpis):
    total_units = sum(s["units"] for s in skus)
    total_gross = sum(s["gross"] for s in skus)
    total_net = sum(s["net"] for s in skus)

    orders_l = kpis["orders_lovessence"]
    orders_s = kpis["orders_store"]
    aov_l = kpis["aov_lovessence_order"]
    aov_s = kpis["aov_store_order"]

    c_new = kpis["customers_new"]
    c_exist = kpis["customers_existing"]
    c_identified = c_new + c_exist
    exist_share = pct(c_exist, c_identified)

    cards = [
        ("Pedidos con LOVESSENCE", f"{orders_l:,}",
         f"{pct(orders_l, orders_s):.1f}% de los {orders_s:,} pedidos de la tienda en el período"),
        ("Unidades vendidas", f"{total_units:,}",
         f"en {len(skus)} SKUs / {len(group_by_product(skus))} referencias"),
        ("Ingresos netos", money_short(total_net),
         f"bruto {money_short(total_gross)} · línea de producto, sin envío"),
        ("Ticket promedio", money(aov_l),
         f"vs. {money(aov_s)} promedio general de la tienda (mismo período)"),
        ("Clientes ya existentes", f"{exist_share:.1f}%",
         f"{c_exist} de {c_identified} compradores identificados ya habían comprado antes"),
        ("Clientes nuevos", f"{100 - exist_share:.1f}%",
         f"{c_new} compradores cuya primera compra fue LOVESSENCE"),
    ]
    return cards, {"total_units": total_units, "total_gross": total_gross, "total_net": total_net,
                    "c_identified": c_identified}


def kpis_html(cards):
    out = ['  <section class="kpi-grid">']
    for label, value, sub in cards:
        out.append(
            f'    <div class="kpi"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div><div class="sub">{esc(sub)}</div></div>'
        )
    out.append("  </section>")
    return "\n".join(out)


# ---------------------------------------------------------------- product ranking

def build_products_html(skus):
    groups = group_by_product(skus)
    rows = []
    for name, items in groups.items():
        gross = sum(i["gross"] for i in items)
        units = sum(i["units"] for i in items)
        stock = sum(i["stock"] for i in items)
        rows.append((name, gross, units, stock))
    rows.sort(key=lambda r: r[1], reverse=True)
    max_gross = max((r[1] for r in rows), default=1) or 1

    out = ['  <div class="hbar-list">']
    for i, (name, gross, units, stock) in enumerate(rows, start=1):
        width_pct = gross / max_gross * 100
        out.append(
            '    <div class="hbar-row">'
            f'<div class="hbar-rank">{i}</div>'
            f'<div class="hbar-name">{esc(name)}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{width_pct:.1f}%"></div></div>'
            f'<div class="hbar-value">{money_short(gross)}<span class="units">{units} uds</span></div>'
            "</div>"
        )
    out.append("  </div>")
    return "\n".join(out)


# ---------------------------------------------------------------- SKU table + alerts

def build_sku_table_html(skus):
    groups = group_by_product(skus)
    out = ['  <table>', '    <thead><tr>',
           '<th>Talla</th><th>SKU</th><th class="num">Precio</th>',
           '<th class="num">Uds. vendidas</th><th class="num">Ingresos</th>',
           '<th class="num">Stock disponible</th><th>Estado</th>',
           '</tr></thead>', '    <tbody>']
    for product, items in groups.items():
        p_units = sum(i["units"] for i in items)
        p_stock = sum(i["stock"] for i in items)
        out.append(
            f'      <tr class="group-row"><td colspan="7">{esc(product)}'
            f'<span class="group-total">{p_units} uds vendidas · {p_stock} en stock</span></td></tr>'
        )
        for it in items:
            label, cls = stock_badge(it["stock"])
            out.append(
                "      <tr>"
                f'<td class="talla">{esc(it["talla"])}</td>'
                f'<td class="sku-code">{esc(it["sku"])}</td>'
                f'<td class="num">{money(it["price"])}</td>'
                f'<td class="num">{it["units"]}</td>'
                f'<td class="num">{money(it["gross"])}</td>'
                f'<td class="num">{it["stock"]}</td>'
                f'<td><span class="badge {cls}">{label}</span></td>'
                "</tr>"
            )
    out.append("    </tbody>")
    out.append("  </table>")
    return "\n".join(out)


def build_alerts_html(skus, campaign_note=None):
    sold_out = [s for s in skus if s["stock"] == 0]
    critical = [s for s in skus if 0 < s["stock"] <= 5]
    high_velocity = sorted([s for s in skus if s["units"] >= 8], key=lambda s: -s["units"])

    def sku_line(s):
        return f'{esc(s["product"])} — talla {esc(s["talla"])} ({esc(s["sku"])})'

    out = ['  <div class="callout-grid">']

    if sold_out:
        items = "".join(f"<li>{sku_line(s)}</li>" for s in sold_out)
        out.append(
            '    <div class="callout critical"><div class="dot"></div><div>'
            f'<b>{len(sold_out)} talla(s) sin inventario disponible</b>'
            f'No se pueden vender hasta reponer: <ul>{items}</ul></div></div>'
        )
    if critical:
        items = "".join(f"<li>{sku_line(s)} — quedan {s['stock']}</li>" for s in critical)
        out.append(
            '    <div class="callout critical"><div class="dot"></div><div>'
            f'<b>{len(critical)} talla(s) en stock crítico (≤5 unidades)</b>'
            f'<ul>{items}</ul></div></div>'
        )
    if high_velocity:
        items = "".join(
            f"<li>{sku_line(s)} — {s['units']} uds vendidas, quedan {s['stock']}</li>"
            for s in high_velocity[:5]
        )
        out.append(
            '    <div class="callout info"><div class="dot"></div><div>'
            "<b>Mayor tracción desde el lanzamiento</b>"
            f"Vender rápido con pocos días de historial: <ul>{items}</ul></div></div>"
        )
    if campaign_note:
        out.append(
            '    <div class="callout info"><div class="dot"></div><div>'
            f"<b>Nota de contexto</b>{esc(campaign_note)}</div></div>"
        )
    out.append("  </div>")
    return "\n".join(out)


# ---------------------------------------------------------------- customers / traffic / cities

def build_customers_html(kpis):
    c_new = kpis["customers_new"]
    c_exist = kpis["customers_existing"]
    c_noacc = kpis.get("customers_noaccount", 0)
    total = c_new + c_exist
    exist_pct = pct(c_exist, total)
    new_pct = 100 - exist_pct
    extra = f' · {c_noacc} sin cuenta (excluidos)' if c_noacc else ""
    return f'''  <div class="comp-block" style="margin-bottom:0">
    <div class="comp-title"><span>Ya eran clientes vs. primera compra</span><span>{total} identificados{extra}</span></div>
    <div class="stack">
      <div class="seg-1" style="width:{exist_pct:.1f}%">{exist_pct:.1f}%</div>
      <div class="seg-2" style="width:{new_pct:.1f}%">{new_pct:.1f}%</div>
    </div>
    <div class="legend">
      <span><i style="background:var(--series-1)"></i>Ya eran clientes ({c_exist})</span>
      <span><i style="background:var(--series-2)"></i>Primera compra ({c_new})</span>
    </div>
  </div>'''


def build_traffic_html(traffic):
    total = sum(t["orders"] for t in traffic) or 1
    max_orders = max((t["orders"] for t in traffic), default=1) or 1
    out = ['  <div class="hbar-list">']
    for t in traffic:
        width_pct = t["orders"] / max_orders * 100
        share = pct(t["orders"], total)
        out.append(
            '    <div class="hbar-row traffic-row">'
            f'<div class="hbar-name">{esc(t["source"])}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{width_pct:.1f}%"></div></div>'
            f'<div class="hbar-value">{t["orders"]} pedidos<span class="units">{share:.1f}%</span></div>'
            "</div>"
        )
    out.append("  </div>")
    return "\n".join(out)


def build_cities_html(cities):
    out = ['  <table>', '    <thead><tr>',
           '<th>#</th><th>Ciudad</th><th class="num">Pedidos</th>',
           '<th class="num">Valor total</th><th class="num">Ticket promedio</th>',
           '</tr></thead>', '    <tbody>']
    for i, c in enumerate(cities, start=1):
        aov = c["total"] / c["orders"] if c["orders"] else 0
        out.append(
            "      <tr>"
            f'<td class="num">{i}</td>'
            f'<td>{esc(c["city"])}</td>'
            f'<td class="num">{c["orders"]}</td>'
            f'<td class="num">{money(c["total"])}</td>'
            f'<td class="num">{money(aov)}</td>'
            "</tr>"
        )
    out.append("    </tbody>")
    out.append("  </table>")
    return "\n".join(out)


# ---------------------------------------------------------------- cohort

def cohort_cell(v):
    if v is None:
        return '<td class="num cohort-pending">pendiente</td>'
    intensity = min(max(v / 25.0, 0.06), 1.0)  # 25% ~= tope visual de la escala
    style = f"background:color-mix(in srgb, var(--series-1) {intensity*100:.0f}%, var(--surface-1))"
    return f'<td class="num cohort-cell" style="{style}">{v:.1f}%</td>'


def build_cohort_html(cohort):
    cards = [
        ("Tasa de recompra histórica", f"{cohort['lifetime_repurchase_rate']:.1f}%",
         "% de todos los clientes (2021–hoy) que han comprado más de una vez"),
        ("Recompra en ventana reciente", f"{cohort['trailing90_repurchase_rate']:.1f}%",
         "% de compradores de los últimos 90 días que ya eran clientes antes"),
        ("Tiempo entre 1ª y 2ª compra", f"{cohort['median_days_2nd']:.0f} días",
         f"mediana histórica (promedio {cohort['mean_days_2nd']:.0f} días, con cola larga)"),
    ]
    kpi_html = ['  <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr)">']
    for label, value, sub in cards:
        kpi_html.append(
            f'    <div class="kpi"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div><div class="sub">{esc(sub)}</div></div>'
        )
    kpi_html.append("  </div>")

    table = ['  <table>', '    <thead><tr>',
             '<th>Cohorte (mes de 1ª compra)</th><th class="num">Nuevos clientes</th>',
             '<th class="num">Recompra ≤30d</th><th class="num">≤60d</th><th class="num">≤90d</th>',
             '</tr></thead>', '    <tbody>']
    for c in cohort["cohorts"]:
        flag = f' <span class="badge flat">{esc(c["flag"])}</span>' if c.get("flag") else ""
        table.append(
            "      <tr>"
            f'<td>{esc(c["label"])}{flag}</td>'
            f'<td class="num">{c["new_customers"]:,}</td>'
            f'{cohort_cell(c["r30"])}{cohort_cell(c["r60"])}{cohort_cell(c["r90"])}'
            "</tr>"
        )
    table.append("    </tbody>")
    table.append("  </table>")

    note = f'  <p class="section-sub" style="margin-top:14px">{esc(cohort["campaign_note"])}</p>' if cohort.get("campaign_note") else ""

    return "\n".join(kpi_html) + "\n" + "\n".join(table) + ("\n" + note if note else "")


# ---------------------------------------------------------------- patch

def patch_html(path, replacements, now, label):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    original = html

    html = re.sub(r'const GENERATED_AT = "[^"]*";', f'const GENERATED_AT = "{now}";', html, count=1)
    html = re.sub(r'const PERIOD_LABEL = "[^"]*";', f'const PERIOD_LABEL = "{label}";', html, count=1)

    for marker, block in replacements.items():
        pattern = rf'<!-- {marker}_START -->.*?<!-- {marker}_END -->'
        wrapped = f'<!-- {marker}_START -->\n{block}\n  <!-- {marker}_END -->'
        new_html, count = re.subn(pattern, wrapped, html, count=1, flags=re.S)
        if count == 0:
            raise SystemExit(f"ERROR: no se encontró el marcador {marker}_START/{marker}_END en el HTML.")
        html = new_html

    if html == original:
        raise SystemExit("ERROR: no se aplicó ningún cambio — revisa los marcadores del HTML.")

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skus", required=True)
    ap.add_argument("--kpis", required=True)
    ap.add_argument("--cities", required=True)
    ap.add_argument("--traffic", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--html")
    ap.add_argument("--now", required=True)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    skus = load(args.skus)
    kpis = load(args.kpis)
    cities = load(args.cities)
    traffic = load(args.traffic)
    cohort = load(args.cohort)

    cards, totals = build_kpis(skus, kpis)
    kpi_block = kpis_html(cards)
    products_block = build_products_html(skus)
    skutable_block = build_sku_table_html(skus)
    alerts_block = build_alerts_html(skus, kpis.get("campaign_note"))
    customers_block = build_customers_html(kpis)
    traffic_block = build_traffic_html(traffic)
    cities_block = build_cities_html(cities)
    cohort_block = build_cohort_html(cohort)

    print(f"Pedidos LOVESSENCE: {kpis['orders_lovessence']:,} de {kpis['orders_store']:,} de la tienda")
    print(f"Unidades: {totals['total_units']:,} | Ingresos netos: {money(totals['total_net'])} (bruto {money(totals['total_gross'])})")
    print(f"Clientes identificados: {totals['c_identified']} | ya existentes: {kpis['customers_existing']} | nuevos: {kpis['customers_new']}")
    sold_out = sum(1 for s in skus if s["stock"] == 0)
    critical = sum(1 for s in skus if 0 < s["stock"] <= 5)
    print(f"SKUs sin inventario: {sold_out} | SKUs en stock crítico: {critical}")
    print(f"Tasa de recompra histórica de la tienda: {cohort['lifetime_repurchase_rate']:.1f}%")

    if args.html:
        patch_html(args.html, {
            "KPIS": kpi_block,
            "PRODUCTS": products_block,
            "SKUTABLE": skutable_block,
            "ALERTS": alerts_block,
            "CUSTOMERS": customers_block,
            "TRAFFIC": traffic_block,
            "CITIES": cities_block,
            "COHORT": cohort_block,
        }, args.now, args.label)
        print(f"HTML actualizado: {args.html}")


if __name__ == "__main__":
    main()
