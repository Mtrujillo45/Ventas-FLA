#!/usr/bin/env python3
"""
compute.py — Motor de cálculo del dashboard Presupuesto vs. Real (Mompossina).

Toda la aritmética vive AQUÍ, no en el modelo: clasificación de pedidos de
Shopify (Online vs. Showroom), agregación de mayoristas, ritmo/proyección,
semáforo y acumulado del periodo. El script arma el objeto `DATA` completo y
PARCHEA dashboards/presupuesto-vs-real.html entre los marcadores
<!-- DATA_START --> / <!-- DATA_END -->. El HTML renderiza todo lo cuantitativo
(KPIs, barras, ticket, gráfico de ritmo, proyecciones, semáforo, tablas) por
JS a partir de ese único objeto — este script nunca toca el resto del HTML.

El resumen ejecutivo y las notas narrativas del footer SÍ se editan a mano
(con Edit) en cada corrida, informados por el resumen que este script imprime
en stdout — eso es narrativa, no aritmética.

Regla de clasificación Online vs. Showroom (confirmada con el usuario,
2026-09-07 — ver commit que introdujo este script):
  - sourceName == "web"                        -> Online (tienda online)
  - sourceName == "shopify_draft_order":
      - tags contiene alguna de REDES_TAGS      -> Online (Redes propias:
        ventas manuales por WhatsApp/Instagram, SIEMPRE llevan el tag
        "REDES SOCIALES" — confirmado sobre ~100 pedidos de muestra, sin
        excepciones)
      - si no                                   -> Showroom (venta en punto
        físico: pago con Bold/QR/efectivo/transferencia en el local). El tag
        "SHOWROOM" NO es confiable como filtro — se aplica manualmente y con
        frecuencia se omite (2 de 4 pedidos de showroom del 7-sep-2026 no lo
        tenían). No usar `tags contains SHOWROOM` como regla.
      - orden en $0 (saldo de bono, regalo, pago UGC, etc.) -> excluida, no
        es venta de producto.
  - cualquier otro sourceName (marketplace sincronizado, ej. Falabella)
    -> Online, igual que antes.
  - Se excluyen pedidos de prueba (`test`) y con `displayFinancialStatus`
    fuera de {PAID, PARTIALLY_PAID, PARTIALLY_REFUNDED, REFUNDED} (p.ej.
    PENDING sin confirmar).

Uso:
  python3 compute.py \
      --plan plan_2026_2027.json \
      --month 2026-09 \
      --shopify-orders sep_orders_raw.json \
      --wholesale wholesale.json \
      --now "2026-09-07T14:27:12-05:00" \
      --html ../../../dashboards/presupuesto-vs-real.html
      [--prior-real-value 0 --prior-real-units 0]

--shopify-orders: array JSON crudo de pedidos, tal cual lo devuelve
  SHOPIFY_GRAPH_QL_QUERY (paginado) con estos campos por pedido:
  id, name, createdAt, tags, sourceName, test, displayFinancialStatus,
  currentSubtotalPriceSet.shopMoney.amount,
  lineItems.edges[].node.currentQuantity
  Alternativa --shopify-summary (usar cuando traer el JSON crudo completo al
  disco local no sea práctico, p.ej. si se calculó en un sandbox aparte):
  JSON ya agregado {"online":{"value","units","orders"},
  "showroom":{...}, "daily":{"YYYY-MM-DD":valor combinado,...},
  "excluded":[...]}. Si se usa este camino, la agregación debe replicar
  EXACTAMENTE `classify_shopify_order()` de este archivo — cópiala tal cual,
  no la reescribas de memoria.

--wholesale: lista de facturas ya extraídas de Google Drive (National/Intl):
  [{"channel":"nacional"|"internacional","date":"2026-09-07","value":123,
    "units":10,"invoice":"RFEL...","partner":"...","note":"..."}, ...]
  Una nota de crédito sin unidades despachadas usa "units": 0.

--prior-real-value / --prior-real-units: suma de venta/unidades REAL de los
  meses del periodo Sep-Dic ya cerrados antes de --month (0 en septiembre,
  el mes 1). Necesario para el acumulado (YTD) en meses futuros.

--extraordinary (opcional): facturas del mes que NO son venta recurrente de
  producto por canal — colaboraciones/co-branding, paquetes puntuales,
  patrocinios (ej. RFEL8320, pago único de Consorcio Licores de la Sabana /
  FLA por una propuesta de co-branding con Aguardiente Antioqueño, sin
  unidades de producto). Se muestran en una sección aparte del dashboard,
  claramente marcada como "fuera del presupuesto" — NUNCA se suman a
  channels, total, runrate, ytd ni al semáforo. Formato:
  [{"date":"2026-09-07","invoice":"RFEL8320","partner":"...",
    "description":"...","value":64250000,"note":"..."}, ...]
  El criterio para decidir si una factura va aquí en vez de a --wholesale:
  ¿tiene unidades de producto vendido y un canal claro (nacional/
  internacional)? Si no — si es un monto fijo por un servicio/colaboración/
  patrocinio — va en --extraordinary, no en --wholesale.
"""
import json
import argparse
import re
import datetime

MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_ES_LARGO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                   "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
REDES_TAGS = {"redes sociales", "melonn", "melonn-entregado"}
VALID_STATUS = {"PAID", "PARTIALLY_PAID", "PARTIALLY_REFUNDED", "REFUNDED"}


def classify_shopify_order(o):
    """Devuelve 'online', 'showroom' o None (excluida). Ver docstring del módulo."""
    if o.get("test"):
        return None
    if o.get("displayFinancialStatus") not in VALID_STATUS:
        return None
    value = float(o["currentSubtotalPriceSet"]["shopMoney"]["amount"])
    if value <= 0:
        return None
    src = o.get("sourceName")
    if src == "shopify_draft_order":
        tags = [t.lower() for t in (o.get("tags") or [])]
        if any(t in REDES_TAGS for t in tags):
            return "online"
        return "showroom"
    return "online"


def bogota_date(created_at_utc_iso):
    dt_utc = datetime.datetime.fromisoformat(created_at_utc_iso.replace("Z", "+00:00"))
    dt_bog = dt_utc - datetime.timedelta(hours=5)
    return dt_bog.date()


def aggregate_shopify(orders):
    buckets = {
        "online": {"value": 0.0, "units": 0, "orders": 0},
        "showroom": {"value": 0.0, "units": 0, "orders": 0},
    }
    daily = {}
    excluded = []
    for o in orders:
        bucket = classify_shopify_order(o)
        if bucket is None:
            excluded.append(o.get("name"))
            continue
        value = float(o["currentSubtotalPriceSet"]["shopMoney"]["amount"])
        units = sum(int(e["node"]["currentQuantity"]) for e in o["lineItems"]["edges"])
        buckets[bucket]["value"] += value
        buckets[bucket]["units"] += units
        buckets[bucket]["orders"] += 1
        day = bogota_date(o["createdAt"])
        daily[day] = daily.get(day, 0.0) + value
    return buckets, daily, excluded


def load_shopify_summary(path):
    """Carga un resumen YA agregado (online/showroom/daily/excluded), producido
    replicando `classify_shopify_order` sobre los pedidos crudos (p.ej. en un
    sandbox aparte cuando no es práctico traer el JSON crudo completo al disco
    local — ver SKILL.md, paso 2). `daily` trae fechas "YYYY-MM-DD"; se
    convierten aquí a `datetime.date` para que build_daily() las procese igual
    que si vinieran de aggregate_shopify()."""
    with open(path, encoding="utf-8") as f:
        summary = json.load(f)
    buckets = {
        "online": summary["online"],
        "showroom": summary["showroom"],
    }
    daily = {datetime.date.fromisoformat(k): v for k, v in summary["daily"].items()}
    excluded = summary.get("excluded", [])
    return buckets, daily, excluded


def aggregate_wholesale(entries):
    buckets = {
        "nacional": {"value": 0.0, "units": 0, "orders": 0},
        "internacional": {"value": 0.0, "units": 0, "orders": 0},
    }
    for e in entries:
        ch = e["channel"]
        buckets[ch]["value"] += float(e["value"])
        buckets[ch]["units"] += int(e.get("units", 0))
        buckets[ch]["orders"] += 1
    return buckets


def stoplight(pct):
    return "verde" if pct >= 100 else ("amarillo" if pct >= 85 else "rojo")


def money_short(n):
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000:
        return f"{sign}${n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{sign}${n / 1_000:.0f}K"
    return f"{sign}${n:.0f}"


def build_channels(plan_month, real):
    channel_order = ["online", "showroom", "nacional", "internacional"]
    labels = {"online": "Online", "showroom": "Showroom", "nacional": "May. nacionales", "internacional": "May. internacionales"}
    channels = []
    for key in channel_order:
        budget = plan_month["channels"][key]
        r = real.get(key, {"value": 0.0, "units": 0, "orders": 0})
        budget_value, budget_units = budget["budgetValue"], budget["budgetUnits"]
        real_value, real_units, orders = r["value"], r["units"], r["orders"]
        days_elapsed, days_in_month = plan_month["_daysElapsed"], plan_month["daysInMonth"]
        expected_frac = days_elapsed / days_in_month
        pct_value = real_value / budget_value * 100 if budget_value else 0.0
        pct_units = real_units / budget_units * 100 if budget_units else 0.0
        pace_value = real_value / (budget_value * expected_frac) * 100 if budget_value and expected_frac else 0.0
        pace_units = real_units / (budget_units * expected_frac) * 100 if budget_units and expected_frac else 0.0
        ticket_real = (real_value / real_units) if real_units else None
        ticket_plan = plan_month["_ticketPlan"][key]
        ticket_delta = ((ticket_real / ticket_plan) - 1) * 100 if ticket_real is not None else None
        channels.append({
            "key": key, "label": labels[key],
            "budgetValue": budget_value, "realValue": real_value, "pctValue": pct_value,
            "budgetUnits": budget_units, "realUnits": real_units, "pctUnits": pct_units,
            "paceValue": pace_value, "paceUnits": pace_units,
            "ticketReal": ticket_real, "ticketPlan": ticket_plan, "ticketDelta": ticket_delta,
            "orders": orders,
            "semaforoValue": stoplight(pace_value), "semaforoUnits": stoplight(pace_units),
        })
    return channels


def build_total(channels):
    budget_value = sum(c["budgetValue"] for c in channels)
    real_value = sum(c["realValue"] for c in channels)
    budget_units = sum(c["budgetUnits"] for c in channels)
    real_units = sum(c["realUnits"] for c in channels)
    pct_value = real_value / budget_value * 100 if budget_value else 0.0
    pct_units = real_units / budget_units * 100 if budget_units else 0.0
    ticket_prom = real_value / real_units if real_units else 0.0
    # ritmo total: ponderado por meta (misma matemática que por canal, sumado)
    weighted_needed_value = sum(c["budgetValue"] for c in channels)
    weighted_needed_units = sum(c["budgetUnits"] for c in channels)
    return {
        "budgetValue": budget_value, "realValue": real_value, "pctValue": pct_value,
        "budgetUnits": budget_units, "realUnits": real_units, "pctUnits": pct_units,
        "ticketProm": ticket_prom,
        "paceValue": None, "paceUnits": None,  # se llenan luego (necesitan days_elapsed/daysInMonth)
    }


def build_runrate(channels_by_key, daily, plan_month):
    days_elapsed, days_in_month = plan_month["_daysElapsed"], plan_month["daysInMonth"]
    online, showroom = channels_by_key["online"], channels_by_key["showroom"]

    def rr(ch):
        daily_rate = ch["realValue"] / days_elapsed if days_elapsed else 0.0
        needed_rate = ch["budgetValue"] / days_in_month
        pace_pct = daily_rate / needed_rate * 100 if needed_rate else 0.0
        projection = daily_rate * days_in_month
        projection_pct = projection / ch["budgetValue"] * 100 if ch["budgetValue"] else 0.0
        return daily_rate, needed_rate, pace_pct, projection, projection_pct

    o_rate, o_needed, o_pace, o_proj, o_proj_pct = rr(online)
    s_rate, s_needed, s_pace, s_proj, s_proj_pct = rr(showroom)
    floor_value = o_proj + s_proj + channels_by_key["nacional"]["realValue"] + channels_by_key["internacional"]["realValue"]
    total_budget = sum(c["budgetValue"] for c in channels_by_key.values())
    floor_pct = floor_value / total_budget * 100 if total_budget else 0.0
    return {
        "daysElapsed": days_elapsed, "daysInMonth": days_in_month,
        "onlineDailyRate": o_rate, "onlineNeededRate": o_needed, "onlinePacePct": o_pace,
        "onlineProjection": o_proj, "onlineProjectionPct": o_proj_pct,
        "showroomDailyRate": s_rate, "showroomNeededRate": s_needed, "showroomPacePct": s_pace,
        "showroomProjection": s_proj, "showroomProjectionPct": s_proj_pct,
        "floorValue": floor_value, "floorPct": floor_pct,
    }


def build_daily(daily_by_date, plan_month, month_key):
    days_elapsed, days_in_month = plan_month["_daysElapsed"], plan_month["daysInMonth"]
    year, month = (int(x) for x in month_key.split("-"))
    dates, values = [], []
    for d in range(1, days_elapsed + 1):
        day = datetime.date(year, month, d)
        dates.append(f"{d} {MESES_ES[month - 1]}")
        values.append(daily_by_date.get(day, 0.0))
    online_budget = plan_month["channels"]["online"]["budgetValue"]
    showroom_budget = plan_month["channels"]["showroom"]["budgetValue"]
    needed_daily = (online_budget + showroom_budget) / days_in_month
    return {"dates": dates, "propioReal": values, "neededDaily": needed_daily}


def build_ytd(plan, month_key, total_real_value, total_real_units, prior_real_value, prior_real_units, plan_month):
    days_elapsed, days_in_month = plan_month["_daysElapsed"], plan_month["daysInMonth"]
    idx = plan["period_order"].index(month_key)
    prior_months_budget_value = sum(plan["months"][m]["_budgetValueTotal"] for m in plan["period_order"][:idx])
    prior_months_budget_units = sum(plan["months"][m]["_budgetUnitsTotal"] for m in plan["period_order"][:idx])
    remaining_months = plan["period_order"][idx + 1:]
    remaining_budget_value = sum(plan["months"][m]["_budgetValueTotal"] for m in remaining_months)

    current_budget_value = plan_month["_budgetValueTotal"]
    current_budget_units = plan_month["_budgetUnitsTotal"]
    expected_value = prior_months_budget_value + current_budget_value * days_elapsed / days_in_month
    expected_units = prior_months_budget_units + current_budget_units * days_elapsed / days_in_month

    ytd_real_value = prior_real_value + total_real_value
    ytd_real_units = prior_real_units + total_real_units
    pace_value = ytd_real_value / expected_value * 100 if expected_value else 0.0
    pace_units = ytd_real_units / expected_units * 100 if expected_units else 0.0

    # Método 1: real acumulado + resto del mes en curso presupuestado + resto de meses futuros tal cual
    proj1 = ytd_real_value + current_budget_value * (1 - days_elapsed / days_in_month) + remaining_budget_value
    proj1_pct = proj1 / plan["plan_total_value"] * 100

    return {
        "realValue": ytd_real_value, "realUnits": ytd_real_units,
        "expectedValue": expected_value, "expectedUnits": expected_units,
        "paceValue": pace_value, "paceUnits": pace_units,
        "planTotal": plan["plan_total_value"], "planTotalUnits": plan["plan_total_units"],
        "proj1": proj1, "proj1Pct": proj1_pct,
        # proj2 se completa en build_proj2 (necesita el ritmo diario propio + backlog mayorista total del periodo)
    }


def build_proj2(plan, runrate, plan_total_value):
    total_days_period = sum(plan["months"][m]["daysInMonth"] for m in plan["period_order"])
    wholesale_backlog_total = sum(
        plan["months"][m]["channels"]["nacional"]["budgetValue"] + plan["months"][m]["channels"]["internacional"]["budgetValue"]
        for m in plan["period_order"]
    )
    combined_daily_rate = runrate["onlineDailyRate"] + runrate["showroomDailyRate"]
    proj2 = combined_daily_rate * total_days_period + wholesale_backlog_total
    proj2_pct = proj2 / plan_total_value * 100
    return proj2, proj2_pct, wholesale_backlog_total


def build_runrate_svg(dates, values, needed_daily, width=880, height=230):
    pad_l, pad_r, pad_t, pad_b = 50, 20, 22, 34
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vmax = max(max(values, default=0.0), needed_daily) * 1.15 or 1.0
    n = len(values)

    def x(i):
        return pad_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def y(v):
        return pad_t + plot_h - (plot_h * v / vmax)

    grid = []
    for i in range(4):
        level = vmax * (1 - i / 3)
        gy = pad_t + plot_h * i / 3
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" y2="{gy:.1f}" class="chart-grid-line"/>')
        grid.append(f'<text x="{pad_l - 8}" y="{gy + 3:.1f}" class="chart-axis-label-y">{money_short(level)}</text>')

    pts = [(x(i), y(v)) for i, v in enumerate(values)]
    path_d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    floor_y = pad_t + plot_h
    area_d = path_d + f" L {pts[-1][0]:.1f},{floor_y:.1f} L {pts[0][0]:.1f},{floor_y:.1f} Z"
    needed_y = y(needed_daily)
    needed_line = f'<line x1="{pad_l}" y1="{needed_y:.1f}" x2="{pad_l + plot_w}" y2="{needed_y:.1f}" class="rr-line-needed"/>'

    markers = []
    for i, (px, py) in enumerate(pts):
        markers.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" class="rr-dot"/>')
        markers.append(f'<text x="{px:.1f}" y="{py - 10:.1f}" class="rr-point-label">{money_short(values[i])}</text>')

    x_labels = [f'<text x="{px:.1f}" y="{height - 8}" class="chart-axis-label">{dates[i]}</text>' for i, (px, _) in enumerate(pts)]

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="svg-chart daily-chart" role="img" '
        'aria-label="Ritmo diario canal propio: venta real vs ritmo necesario">'
        '<defs><linearGradient id="rrAreaFill" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="var(--series-1)" stop-opacity="0.28"/>'
        '<stop offset="100%" stop-color="var(--series-1)" stop-opacity="0"/></linearGradient></defs>'
        + "".join(grid) + needed_line
        + f'<path d="{area_d}" fill="url(#rrAreaFill)" stroke="none"/>'
        + f'<path d="{path_d}" class="rr-line-real"/>'
        + "".join(markers) + "".join(x_labels)
        + "</svg>"
    )
    return svg


def patch_html(path, data_js):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    pattern = r"<!-- DATA_START -->.*?<!-- DATA_END -->"
    wrapped = f"<!-- DATA_START -->\n{data_js}\n<!-- DATA_END -->"
    new_html, count = re.subn(pattern, wrapped, html, count=1, flags=re.S)
    if count == 0:
        raise SystemExit("ERROR: no se encontró el marcador DATA_START/DATA_END en el HTML.")
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--month", required=True, help="YYYY-MM, debe existir en plan.months")
    ap.add_argument("--shopify-orders", help="JSON crudo de pedidos (paginado). Alternativa: --shopify-summary")
    ap.add_argument("--shopify-summary", help="JSON ya agregado {online,showroom,daily,excluded}. Alternativa: --shopify-orders")
    ap.add_argument("--wholesale", required=True)
    ap.add_argument("--extraordinary", help="JSON opcional: facturas fuera del presupuesto (co-branding, colaboraciones) — ver docstring")
    ap.add_argument("--now", required=True, help="ISO timestamp con offset, hora Bogotá")
    ap.add_argument("--prior-real-value", type=float, default=0.0)
    ap.add_argument("--prior-real-units", type=float, default=0.0)
    ap.add_argument("--html")
    args = ap.parse_args()

    if bool(args.shopify_orders) == bool(args.shopify_summary):
        raise SystemExit("ERROR: pasa exactamente uno de --shopify-orders o --shopify-summary.")

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    with open(args.wholesale, encoding="utf-8") as f:
        wholesale_entries = json.load(f)
    extraordinary_entries = []
    if args.extraordinary:
        with open(args.extraordinary, encoding="utf-8") as f:
            extraordinary_entries = json.load(f)

    now = datetime.datetime.fromisoformat(args.now)
    plan_month = dict(plan["months"][args.month])
    plan_month["_daysElapsed"] = now.day
    plan_month["_budgetValueTotal"] = sum(c["budgetValue"] for c in plan_month["channels"].values())
    plan_month["_budgetUnitsTotal"] = sum(c["budgetUnits"] for c in plan_month["channels"].values())
    plan_month["_ticketPlan"] = plan["ticket_plan"]
    # los meses del plan usados por build_ytd/build_proj2 también necesitan estos totales precomputados
    for mkey, m in plan["months"].items():
        m["_budgetValueTotal"] = sum(c["budgetValue"] for c in m["channels"].values())
        m["_budgetUnitsTotal"] = sum(c["budgetUnits"] for c in m["channels"].values())

    if args.shopify_orders:
        with open(args.shopify_orders, encoding="utf-8") as f:
            shopify_orders = json.load(f)
        shopify_buckets, daily_by_date, excluded = aggregate_shopify(shopify_orders)
    else:
        shopify_buckets, daily_by_date, excluded = load_shopify_summary(args.shopify_summary)
    wholesale_buckets = aggregate_wholesale(wholesale_entries)
    real = {**shopify_buckets, **wholesale_buckets}

    channels = build_channels(plan_month, real)
    channels_by_key = {c["key"]: c for c in channels}

    total = build_total(channels)
    expected_frac = plan_month["_daysElapsed"] / plan_month["daysInMonth"]
    total["paceValue"] = total["realValue"] / (total["budgetValue"] * expected_frac) * 100 if total["budgetValue"] and expected_frac else 0.0
    total["paceUnits"] = total["realUnits"] / (total["budgetUnits"] * expected_frac) * 100 if total["budgetUnits"] and expected_frac else 0.0

    runrate = build_runrate(channels_by_key, daily_by_date, plan_month)
    daily = build_daily(daily_by_date, plan_month, args.month)
    ytd = build_ytd(plan, args.month, total["realValue"], total["realUnits"], args.prior_real_value, args.prior_real_units, plan_month)
    proj2, proj2_pct, wholesale_backlog_total = build_proj2(plan, runrate, plan["plan_total_value"])
    ytd["proj2"], ytd["proj2Pct"] = proj2, proj2_pct

    pct_elapsed = plan_month["_daysElapsed"] / plan_month["daysInMonth"] * 100
    month_idx = plan["period_order"].index(args.month) + 1
    month_total = len(plan["period_order"])

    data = {
        "meta": {
            "period": plan_month["label"],
            "cutoff": f'{now.day} {MESES_ES[now.month-1]} {now.year}, {now.strftime("%H:%M")} hora Bogotá',
            "daysElapsed": plan_month["_daysElapsed"], "daysInMonth": plan_month["daysInMonth"],
            "pctElapsed": pct_elapsed, "monthIndex": month_idx, "monthTotal": month_total,
            "monthLabel": MESES_ES_LARGO[now.month - 1],
        },
        "total": total,
        "channels": channels,
        "runrate": runrate,
        "daily": daily,
        "ytd": ytd,
        "extraordinary": {
            "items": extraordinary_entries,
            "total": sum(float(e["value"]) for e in extraordinary_entries),
        },
    }

    print(f"=== Presupuesto vs. Real — {plan_month['label']} (corte {data['meta']['cutoff']}) ===")
    print(f"Día {plan_month['_daysElapsed']} de {plan_month['daysInMonth']} ({pct_elapsed:.1f}% transcurrido)")
    print(f"Pedidos excluidos de Shopify ({len(excluded)}): {excluded}")
    print()
    for c in channels:
        ticket_txt = f"ticket {money_short(c['ticketReal'])}" if c["ticketReal"] else "sin ventas"
        print(f"{c['label']:22s} real {money_short(c['realValue']):>8s} / meta {money_short(c['budgetValue']):>8s} "
              f"({c['pctValue']:5.1f}% mes, ritmo {c['paceValue']:6.1f}% {c['semaforoValue']:>8s}) · "
              f"{c['realUnits']:4d}/{c['budgetUnits']:4d} und · {c['orders']:3d} pedidos · {ticket_txt}")
    print()
    print(f"TOTAL: real {money_short(total['realValue'])} / meta {money_short(total['budgetValue'])} "
          f"({total['pctValue']:.1f}% del mes, ritmo {total['paceValue']:.1f}%)")
    print(f"Proyección de cierre (piso, congela mayoristas): {money_short(runrate['floorValue'])} ({runrate['floorPct']:.1f}% de la meta del mes)")
    print(f"Acumulado del periodo: real {money_short(ytd['realValue'])} vs. esperado {money_short(ytd['expectedValue'])} ({ytd['paceValue']:.1f}%)")
    print(f"Proyección método 1 (real + resto del plan tal cual): {money_short(ytd['proj1'])} ({ytd['proj1Pct']:.1f}% de ${plan['plan_total_value']/1e6:.1f}M)")
    print(f"Proyección método 2 (ritmo propio plano + backlog mayorista {money_short(wholesale_backlog_total)}): {money_short(ytd['proj2'])} ({ytd['proj2Pct']:.1f}%)")
    red = [c["label"] for c in channels if c["semaforoValue"] == "rojo" or c["semaforoUnits"] == "rojo"]
    print(f"Canales en rojo: {red or 'ninguno'}")
    if extraordinary_entries:
        print(f"Facturación fuera del presupuesto ({len(extraordinary_entries)}, NO incluida arriba): "
              f"{money_short(data['extraordinary']['total'])} — " +
              ", ".join(f"{e.get('invoice','?')} {e.get('partner','')} {money_short(e['value'])}" for e in extraordinary_entries))

    if args.html:
        data_js = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";"
        patch_html(args.html, data_js)

        runrate_svg = build_runrate_svg(daily["dates"], daily["propioReal"], daily["neededDaily"])
        with open(args.html, encoding="utf-8") as f:
            html = f.read()
        html, n = re.subn(r"<!-- RUNRATE_SVG_START -->.*?<!-- RUNRATE_SVG_END -->",
                           f"<!-- RUNRATE_SVG_START -->\n{runrate_svg}\n<!-- RUNRATE_SVG_END -->",
                           html, count=1, flags=re.S)
        if n == 0:
            raise SystemExit("ERROR: no se encontró el marcador RUNRATE_SVG_START/END en el HTML.")
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nHTML actualizado: {args.html}")
    else:
        print("\n(--html no indicado, no se parcheó ningún archivo)")


if __name__ == "__main__":
    main()
