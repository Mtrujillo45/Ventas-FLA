#!/usr/bin/env python3
"""
compute.py — Motor de cálculo del informe de Cierre Mensual (Mompossina, Shopify).

Toda la aritmética vive AQUÍ, no en el modelo. Lee las respuestas crudas (JSON)
de las consultas ShopifyQL, arma el desglose financiero (subtotal / IVA / envío /
descuentos / devoluciones / total), la serie diaria y el ranking de productos, y
PARCHEA el dashboard fuente (dashboard/cierre-mensual.html) entre marcadores.

Uso:
  python3 compute.py \
      --totals totals.json \
      --daily daily.json \
      --products products.json \
      --units units.json \
      --since 2026-07-01 --until 2026-07-31 --label "Julio 2026" \
      --html /ruta/a/dashboard/cierre-mensual.html \
      --now "2026-08-02T09:00:00-05:00"

Cada --totals/--daily/--products/--units es la respuesta CRUDA (tal cual la
devuelve la herramienta run-analytics-query, con sus campos "columns"/"rows")
de la consulta ShopifyQL correspondiente, guardada con Write en un archivo:

  totals.json   FROM sales SHOW orders, gross_sales, discounts, returns,
                net_sales, shipping_charges, taxes, total_sales
                SINCE {since} UNTIL {until}

  daily.json    FROM sales SHOW total_sales TIMESERIES day
                SINCE {since} UNTIL {until}

  products.json FROM sales SHOW gross_sales, net_sales, orders
                GROUP BY product_title ORDER BY gross_sales DESC LIMIT 20
                SINCE {since} UNTIL {until}

  units.json    FROM inventory SHOW inventory_units_sold
                SINCE {since} UNTIL {until}

Convención financiera (confirmada con el usuario):
  - "Ventas brutas"  = gross_sales                (antes de descuentos/devoluciones)
  - "Subtotal"       = net_sales                  (bruto - descuentos - devoluciones, SIN IVA ni envío)
  - "IVA"            = taxes                      (aparte, ya viene separado en ShopifyQL)
  - "Envío"          = shipping_charges            (aparte, separado del IVA)
  - "Ventas totales" = total_sales                (subtotal + IVA + envío = lo cobrado al cliente)
  No se aplica ningún factor 1.19 manual: ShopifyQL ya reporta impuestos y envío
  como columnas independientes, sin importar si la tienda maneja precios con o
  sin IVA incluido en el catálogo.
"""
import json
import argparse
import re


def load_rows(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["rows"]


def load_single_row(path):
    rows = load_rows(path)
    return rows[0] if rows else []


def money(n):
    return "${:,.0f}".format(round(float(n)))


def money_short(n):
    n = float(n)
    if abs(n) >= 1_000_000:
        return "${:,.1f}M".format(n / 1_000_000)
    if abs(n) >= 1_000:
        return "${:,.0f}K".format(n / 1_000)
    return "${:,.0f}".format(n)


def pct(part, whole):
    return (part / whole * 100) if whole else 0.0


def build_kpis(t, units):
    orders, gross, discounts, returns, net, shipping, taxes, total = (
        float(t[0]), float(t[1]), float(t[2]), float(t[3]),
        float(t[4]), float(t[5]), float(t[6]), float(t[7]),
    )
    units_sold = int(float(units[0])) if units else 0

    # ShopifyQL ya devuelve discounts/returns como valores negativos.
    cards = [
        ("Ventas totales", money(total), "Lo cobrado al cliente: subtotal + IVA + envío"),
        ("Subtotal (sin IVA)", money(net), "Venta neta de descuentos y devoluciones, antes de IVA"),
        ("IVA", money(taxes), "Impuesto cobrado, aparte del subtotal y el envío"),
        ("Envío", money(shipping), "Cargos de envío cobrados a los clientes"),
        ("Ventas brutas", money(gross), "Venta de catálogo antes de descuentos y devoluciones"),
        ("Descuentos", "−" + money(abs(discounts)), "Descuentos aplicados durante el mes"),
        ("Devoluciones", "−" + money(abs(returns)), "Valor de productos devueltos en el mes"),
        ("Pedidos pagados", "{:,.0f}".format(orders), "Número de pedidos con pago confirmado"),
        ("Unidades vendidas", "{:,.0f}".format(units_sold), "Unidades de producto despachadas en el mes"),
    ]
    return cards, {
        "orders": orders, "gross": gross, "discounts": discounts, "returns": returns,
        "net": net, "shipping": shipping, "taxes": taxes, "total": total, "units": units_sold,
    }


def kpis_html(cards):
    out = ['  <section class="kpi-grid">']
    for label, value, sub in cards:
        out.append(
            f'    <div class="kpi"><div class="label">{label}</div>'
            f'<div class="value">{value}</div><div class="sub">{sub}</div></div>'
        )
    out.append("  </section>")
    return "\n".join(out)


def build_chart_svg(daily_rows, width=880, height=230):
    pad_l, pad_r, pad_t, pad_b = 46, 16, 22, 34
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    dates = [r[0] for r in daily_rows]
    values = [float(r[1]) for r in daily_rows]
    n = len(values)
    vmax = max(values) if values else 1.0
    vmax_headroom = vmax * 1.15 if vmax > 0 else 1.0

    def x(i):
        return pad_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def y(v):
        return pad_t + plot_h - (plot_h * v / vmax_headroom if vmax_headroom else 0)

    pts = [(x(i), y(v)) for i, v in enumerate(values)]
    path_d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    floor_y = pad_t + plot_h
    area_d = path_d + f" L {pts[-1][0]:.1f},{floor_y:.1f} L {pts[0][0]:.1f},{floor_y:.1f} Z"

    # líneas de referencia horizontales (4 niveles)
    grid_lines = []
    for i in range(4):
        gy = pad_t + plot_h * i / 3
        grid_lines.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width - pad_r}" y2="{gy:.1f}" class="chart-grid"/>')

    # etiquetas de eje X: cada ~5 días para no saturar
    step = max(1, n // 6)
    x_labels = []
    for i in range(0, n, step):
        day_num = dates[i][-2:] if dates[i] else str(i + 1)
        x_labels.append(f'<text x="{x(i):.1f}" y="{height - 10}" class="chart-axis">{int(day_num)}</text>')
    if (n - 1) % step != 0:
        day_num = dates[-1][-2:]
        x_labels.append(f'<text x="{x(n-1):.1f}" y="{height - 10}" class="chart-axis">{int(day_num)}</text>')

    # marcar pico y último día
    peak_i = max(range(n), key=lambda i: values[i]) if n else 0
    markers = []
    if n:
        px, py = pts[peak_i]
        markers.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" class="chart-dot chart-dot-peak"/>')
        markers.append(f'<text x="{px:.1f}" y="{py - 10:.1f}" class="chart-point-label chart-point-label-peak">{money_short(values[peak_i])}</text>')

        lx, ly = pts[-1]
        markers.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" class="chart-dot"/>')
        label_y = ly - 10 if peak_i != n - 1 else ly + 18
        markers.append(f'<text x="{lx:.1f}" y="{label_y:.1f}" class="chart-point-label" text-anchor="end">{money_short(values[-1])}</text>')

    svg = f'''  <svg viewBox="0 0 {width} {height}" class="daily-chart" role="img" aria-label="Ventas totales por día del mes">
    <defs>
      <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--series-1)" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="var(--series-1)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    {"".join(grid_lines)}
    <path d="{area_d}" fill="url(#areaFill)" stroke="none"/>
    <path d="{path_d}" fill="none" class="chart-line"/>
    {"".join(markers)}
    {"".join(x_labels)}
  </svg>'''
    return svg


def build_products_html(rows, gross_total):
    rows = rows[:20]
    max_gross = max((float(r[1]) for r in rows), default=1.0) or 1.0
    out = ['  <div class="hbar-list">']
    for i, r in enumerate(rows, start=1):
        name, gross, net, orders = r[0], float(r[1]), float(r[2]), int(float(r[3]))
        width_pct = gross / max_gross * 100
        share = pct(gross, gross_total)
        out.append(
            '    <div class="hbar-row">'
            f'<div class="hbar-rank">{i}</div>'
            f'<div class="hbar-name">{name}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{width_pct:.1f}%"></div></div>'
            f'<div class="hbar-value">{money(gross)}<span class="units">{orders:,} pedidos · {share:.1f}%</span></div>'
            "</div>"
        )
    out.append("  </div>")
    return "\n".join(out)


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
    ap.add_argument("--totals", required=True)
    ap.add_argument("--daily", required=True)
    ap.add_argument("--products", required=True)
    ap.add_argument("--units", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--html")
    ap.add_argument("--now", required=True)
    args = ap.parse_args()

    t = load_single_row(args.totals)
    daily_rows = load_rows(args.daily)
    product_rows = load_rows(args.products)
    units_row = load_single_row(args.units)

    cards, totals = build_kpis(t, units_row)
    kpi_block = kpis_html(cards)
    chart_block = build_chart_svg(daily_rows)
    products_block = build_products_html(product_rows, totals["gross"])

    print(f"Periodo: {args.since} a {args.until} ({args.label})")
    print(f"Pedidos pagados: {totals['orders']:,.0f}  |  Unidades: {totals['units']:,.0f}")
    print(f"Ventas brutas: {money(totals['gross'])}  |  Descuentos: -{money(abs(totals['discounts']))}  |  Devoluciones: -{money(abs(totals['returns']))}")
    print(f"Subtotal (sin IVA): {money(totals['net'])}  |  IVA: {money(totals['taxes'])}  |  Envío: {money(totals['shipping'])}")
    print(f"VENTAS TOTALES (con IVA y envío): {money(totals['total'])}")
    print(f"Días con datos en la serie diaria: {len(daily_rows)}")
    print(f"Productos en el ranking: {len(product_rows)}")
    if product_rows:
        top = product_rows[0]
        print(f"Producto #1: {top[0]} — {money(float(top[1]))} ({pct(float(top[1]), totals['gross']):.1f}% de la venta bruta)")

    if args.html:
        # El dashboard ya no tiene sección de Top 20 productos (removida a pedido
        # del usuario) -> no se parchea el marcador PRODUCTS, solo KPIS y CHART.
        patch_html(args.html, {"KPIS": kpi_block, "CHART": chart_block}, args.now, args.label)
        print(f"HTML actualizado: {args.html}")
    else:
        print("\n--- KPIs ---\n" + kpi_block)
        print("\n--- Chart ---\n" + chart_block)
        print("\n--- Products ---\n" + products_block)


if __name__ == "__main__":
    main()
