#!/usr/bin/env python3
"""
compute.py — Motor de cálculo del dashboard Flujo de Caja (Mompossina).

Toda la aritmética vive AQUÍ, no en el modelo — mismo principio que
presupuesto-vs-real, lovessence-dashboard y cierre-mensual. El script arma
el objeto `DATA` completo y PARCHEA dashboards/flujo-caja.html entre los
marcadores <!-- DATA_START --> / <!-- DATA_END --> (más
<!-- TRAJECTORY_SVG_START/END --> para el gráfico de trayectoria de caja,
generado en Python como SVG inline, sin dependencias externas).

## Fuentes de datos y cómo se combinan (confirmado con el usuario, 2026-09-08)

1. **Trayectoria de 16 meses (Sep-26 a Dic-27)** = la hoja "Flujo de Caja"
   del Plan Estratégico 2026-2027 (Dropbox), extraída completa a
   `plan_flujo_caja.json` (estático, no se vuelve a leer el Excel cada
   corrida salvo que el usuario avise de un ajuste al plan). Caja inicial
   $1,018M (banco $41M + fiducuenta $977M), supuestos de cobro/pago del
   propio plan (online/showroom/nacional 100% mismo mes, exportaciones
   80%/20% con 1 mes de rezago, producción 2 meses de anticipo, IVA en el
   mes real del bimestre).

2. **Ajuste con venta real del mes en curso** — para NO doblar venta ya
   facturada con lo que el plan proyectaba (pedido explícito del usuario,
   cruzando contra el dashboard `presupuesto-vs-real`): se compara el real
   de Online/Showroom/Nacional/Internacional del mes en curso contra el
   presupuesto de ese canal para ese mes:
   - Online y Showroom: si van por delante del ritmo esperado, se usa la
     proyección de cierre por ritmo diario (`runrate.onlineProjection` /
     `showroomProjection`, ya calculada por `presupuesto-vs-real`) en vez
     del presupuesto plano del plan — mismo Método usado allí.
   - Nacional e Internacional (mayoristas): "Método 1" — no se proyecta por
     ritmo (venta lumpy, por factura) — se usa real + resto del presupuesto
     tal cual, o sea el presupuesto del plan si real no lo ha superado
     todavía. Por eso normalmente NO generan ajuste hasta que el canal ya
     superó su meta del mes.
   El delta resultante (típicamente sólo por Online/Showroom) se suma al
   saldo de caja de TODOS los meses desde el actual en adelante (un único
   ajuste de nivel, no un re-forecast mes a mes de todo el periodo) —
   ver `build_trajectory()`.
   Cobros extraordinarios (ej. facturación FLA fuera de presupuesto) NO se
   mezclan en este ajuste — se muestran aparte, marcados para conciliar
   contra el supuesto de "cobros pendientes de agosto" que ya trae el plan,
   porque no hay forma confiable de saber si ya estaban baked-in sin
   confirmación contable.

3. **CxP real (obligaciones próximas)** = ledger completo de
   `CONTROL DE PAGOS 2026.xlsx` (Google Drive), filtrado a filas con
   "TOTAL PEND*PAGO" > 0 (columna M) — es decir, lo que de verdad sigue
   pendiente de pago hoy, con su fecha de vencimiento real (columna N). Se
   muestra APARTE de la trayectoria de 16 meses (no se resta del saldo mes
   a mes) porque el ledger sólo captura lo pendiente, no el total gastado
   del mes (lo ya pagado no aparece) — mezclarlo subestimaría el gasto
   real. Sirve para la vista táctica "qué se vence y cuándo" y para el
   colchón de caja libre (ver abajo).

## Alertas (confirmado con el usuario, 2026-09-08 — dos capas independientes)

- **Piso dinámico**: alerta si el saldo ajustado con venta real cae por
  debajo de lo que el plan proyectaba para ese mismo mes — mide desviación
  vs. el propio modelo del usuario. Sólo aplica al mes en curso (los meses
  futuros no tienen aún ajuste real, así que por construcción son iguales
  al plan — no se puede alertar contra sí mismo).
- **Colchón fijo**: `--cushion-months` (default 6) × Personal+Admin fijo
  mensual ($60.30M según el plan) = mínimo estructural de sobrevivencia.
  Alerta si el saldo (plan o ajustado) cae por debajo en cualquier mes.
- **Excedente**: caja libre = saldo del mes − colchón fijo − obligaciones
  conocidas de los próximos ~60 días (para el mes en curso, suma real del
  ledger de CxP con vencimiento ≤ hoy+60d; para meses futuros, se usa el
  total de "Pagos" que el propio plan proyecta para ese mes como proxy,
  ya que no hay ledger real tan adelante). Se marca excedente cuando la
  caja libre supera 1x el colchón fijo (doble colchón: el estructural más
  otro tanto por encima de las obligaciones conocidas). Este criterio es
  una propuesta inicial — el usuario puede ajustar el múltiplo.

Uso:
  python3 compute.py \
      --plan-cashflow plan_flujo_caja.json \
      --ventas-mes ventas_mes.json \
      --cxp cxp_pendientes.json \
      --now "2026-09-08T21:40:00-05:00" \
      --cushion-months 6 \
      --html ../../../dashboards/flujo-caja.html
"""
import json
import argparse
import re
import datetime

MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_ES_LARGO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                   "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

CXP_CATEGORY_LABELS = {
    "PRODUCCION": "Producción",
    "GASTOS PERSONAL": "Personal",
    "GASTOS ADMINISTRATIVOS": "Administrativos",
    "MERCADEO Y VENTAS": "Mercadeo y Ventas",
}

BUCKET_DEFS = [
    ("vencida", "Vencida", None, -1),
    ("0-7", "0-7 días", 0, 7),
    ("8-30", "8-30 días", 8, 30),
    ("31-60", "31-60 días", 31, 60),
    ("61-90", "61-90 días", 61, 90),
    ("90+", "Más de 90 días", 91, None),
]


def month_label(key):
    y, m = key.split("-")
    return f"{MESES_ES_LARGO[int(m) - 1]} {y}"


def money_short(n):
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000:
        return f"{sign}${n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{sign}${n / 1_000:.0f}K"
    return f"{sign}${n:.0f}"


def build_trajectory(plan, ventas_mes, current_month, cxp_rows, cutoff_date, cushion_value):
    months = plan["months"]
    idx_current = months.index(current_month)

    # ---- 1. delta de nivel por venta real del mes en curso ----
    ch_by_key = {c["key"]: c for c in ventas_mes["channels"]}
    rr = ventas_mes["runrate"]

    def metodo1(real, budget):
        return real + max(budget - real, 0.0)

    online_proj = rr["onlineProjection"]
    showroom_proj = rr["showroomProjection"]
    nacional_proj = metodo1(ch_by_key["nacional"]["realValue"], ch_by_key["nacional"]["budgetValue"])
    internacional_proj = metodo1(ch_by_key["internacional"]["realValue"], ch_by_key["internacional"]["budgetValue"])

    plan_cobros_current = (
        plan["cobros"]["online"][idx_current] + plan["cobros"]["showroom"][idx_current]
        + plan["cobros"]["nacional"][idx_current]
        + plan["cobros"]["exportaciones_80"][idx_current]
    )
    ajustado_cobros_current = online_proj + showroom_proj + nacional_proj + internacional_proj * 0.8
    # (el 20% de exportaciones con rezago a 1 mes se recalcula igual si internacional_proj cambia,
    #  pero como metodo1 no se mueve del presupuesto salvo que el canal ya lo supere, en la práctica
    #  sólo Online/Showroom generan delta — ver docstring del módulo)
    delta_nivel = ajustado_cobros_current - plan_cobros_current

    online_delta = online_proj - plan["cobros"]["online"][idx_current]
    showroom_delta = showroom_proj - plan["cobros"]["showroom"][idx_current]
    nacional_delta = nacional_proj - plan["cobros"]["nacional"][idx_current]
    internacional_delta = internacional_proj - (plan["cobros"]["exportaciones_80"][idx_current] / 0.8 if plan["cobros"]["exportaciones_80"][idx_current] else 0)

    # ---- 2. obligaciones próximas 60 días (mes en curso: ledger real; futuro: proxy del plan) ----
    horizon_60 = cutoff_date + datetime.timedelta(days=60)
    cxp_next60 = sum(
        r["pendiente"] for r in cxp_rows
        if datetime.date.fromisoformat(r["fecha_pago"][:10]) <= horizon_60
    )

    # ---- 3. construir fila por mes ----
    rows = []
    for i, mkey in enumerate(plan["_month_keys"]):
        saldo_final_plan = plan["saldo_final"][i]
        saldo_final_ajustado = saldo_final_plan + (delta_nivel if i >= idx_current else 0.0)
        pagos_total = plan["pagos"]["total"][i]
        if i == idx_current:
            obligaciones_60d = cxp_next60
        else:
            obligaciones_60d = pagos_total
        caja_libre = saldo_final_ajustado - cushion_value - obligaciones_60d
        alerta_colchon = saldo_final_ajustado < cushion_value
        alerta_piso = (i == idx_current) and (saldo_final_ajustado < saldo_final_plan)
        alerta_excedente = caja_libre > cushion_value
        rows.append({
            "key": mkey, "label": month_label(mkey),
            "isCurrent": i == idx_current, "hasRealData": i == idx_current,
            "saldoInicialPlan": plan["saldo_inicial"][i],
            "cobrosPlan": plan["cobros"]["total"][i],
            "cobrosAjustado": plan["cobros"]["total"][i] + (delta_nivel if i == idx_current else 0.0),
            "pagosPlan": pagos_total,
            "saldoFinalPlan": saldo_final_plan,
            "saldoFinalAjustado": saldo_final_ajustado,
            "colchonFijo": cushion_value,
            "obligaciones60d": obligaciones_60d,
            "cajaLibre": caja_libre,
            "alertaColchon": alerta_colchon,
            "alertaPiso": alerta_piso,
            "alertaExcedente": alerta_excedente,
        })

    detalle_ajuste = {
        "online": online_delta, "showroom": showroom_delta,
        "nacional": nacional_delta, "internacional": internacional_delta,
        "total": delta_nivel,
    }
    return rows, detalle_ajuste, cxp_next60


def build_cxp(cxp_rows, cutoff_date):
    total = sum(r["pendiente"] for r in cxp_rows)
    buckets = []
    for key, label, lo, hi in BUCKET_DEFS:
        if key == "vencida":
            items = [r for r in cxp_rows if datetime.date.fromisoformat(r["fecha_pago"][:10]) < cutoff_date]
        else:
            items = [
                r for r in cxp_rows
                if (datetime.date.fromisoformat(r["fecha_pago"][:10]) - cutoff_date).days >= lo
                and (hi is None or (datetime.date.fromisoformat(r["fecha_pago"][:10]) - cutoff_date).days <= hi)
            ]
        buckets.append({
            "key": key, "label": label,
            "total": sum(r["pendiente"] for r in items),
            "count": len(items),
        })

    by_cat = {}
    for r in cxp_rows:
        cat = r["categoria"] or "OTROS"
        by_cat.setdefault(cat, {"key": cat, "label": CXP_CATEGORY_LABELS.get(cat, cat.title()), "total": 0.0, "count": 0})
        by_cat[cat]["total"] += r["pendiente"]
        by_cat[cat]["count"] += 1
    by_category = sorted(by_cat.values(), key=lambda x: -x["total"])
    for c in by_category:
        c["pct"] = c["total"] / total * 100 if total else 0.0

    by_prov = {}
    for r in cxp_rows:
        emp = r["empresa"] or "?"
        by_prov.setdefault(emp, {"empresa": emp, "total": 0.0, "count": 0})
        by_prov[emp]["total"] += r["pendiente"]
        by_prov[emp]["count"] += 1
    top_proveedores = sorted(by_prov.values(), key=lambda x: -x["total"])[:10]

    vencidas = sorted(
        [r for r in cxp_rows if datetime.date.fromisoformat(r["fecha_pago"][:10]) < cutoff_date],
        key=lambda r: r["fecha_pago"]
    )
    proximos30 = sorted(
        [r for r in cxp_rows if 0 <= (datetime.date.fromisoformat(r["fecha_pago"][:10]) - cutoff_date).days <= 30],
        key=lambda r: r["fecha_pago"]
    )

    return {
        "total": total, "buckets": buckets, "byCategory": by_category,
        "topProveedores": top_proveedores, "vencidas": vencidas, "proximos30": proximos30,
        "vencidaTotal": sum(r["pendiente"] for r in vencidas),
    }


def build_trajectory_svg(rows, width=920, height=280):
    pad_l, pad_r, pad_t, pad_b = 56, 20, 22, 30
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(rows)
    plan_vals = [r["saldoFinalPlan"] for r in rows]
    adj_vals = [r["saldoFinalAjustado"] for r in rows]
    cushion = rows[0]["colchonFijo"]
    vmax = max(max(plan_vals), max(adj_vals)) * 1.1
    vmin = min(0, cushion) * 0.9

    def x(i):
        return pad_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def y(v):
        return pad_t + plot_h - (plot_h * (v - vmin) / (vmax - vmin))

    grid = []
    for i in range(5):
        level = vmin + (vmax - vmin) * (1 - i / 4)
        gy = pad_t + plot_h * i / 4
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" y2="{gy:.1f}" class="chart-grid-line"/>')
        grid.append(f'<text x="{pad_l - 8}" y="{gy + 3:.1f}" class="chart-axis-label-y">{money_short(level)}</text>')

    cushion_y = y(cushion)
    cushion_line = f'<line x1="{pad_l}" y1="{cushion_y:.1f}" x2="{pad_l + plot_w}" y2="{cushion_y:.1f}" class="rr-line-needed"/>'
    cushion_label = f'<text x="{pad_l + 6}" y="{cushion_y - 6:.1f}" class="chart-axis-label" text-anchor="start">Colchón fijo {money_short(cushion)}</text>'

    def line_path(vals):
        pts = [(x(i), y(v)) for i, v in enumerate(vals)]
        return "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts), pts

    plan_path, plan_pts = line_path(plan_vals)
    adj_path, adj_pts = line_path(adj_vals)

    markers = [f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" class="rr-dot"/>' for px, py in adj_pts]
    x_labels = []
    for i, (px, _) in enumerate(plan_pts):
        lbl = rows[i]["label"].split(" ")[0][:3] + " " + rows[i]["label"].split(" ")[1][2:]
        x_labels.append(f'<text x="{px:.1f}" y="{height - 6}" class="chart-axis-label">{lbl}</text>')

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="svg-chart traj-chart" role="img" '
        'aria-label="Trayectoria de caja proyectada, plan original vs. ajustado con venta real">'
        + "".join(grid) + cushion_line + cushion_label
        + f'<path d="{plan_path}" class="traj-line-plan"/>'
        + f'<path d="{adj_path}" class="rr-line-real"/>'
        + "".join(markers) + "".join(x_labels)
        + "</svg>"
    )
    return svg


def patch_block(html, start_marker, end_marker, content):
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    wrapped = f"{start_marker}\n{content}\n{end_marker}"
    new_html, count = re.subn(pattern, wrapped, html, count=1, flags=re.S)
    if count == 0:
        raise SystemExit(f"ERROR: no se encontró el marcador {start_marker}/{end_marker} en el HTML.")
    return new_html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-cashflow", required=True)
    ap.add_argument("--ventas-mes", required=True)
    ap.add_argument("--cxp", required=True)
    ap.add_argument("--now", required=True)
    ap.add_argument("--cushion-months", type=float, default=6.0)
    ap.add_argument("--html")
    ap.add_argument("--saldo-real", type=float, default=None,
                     help="Saldo real de banco+fiducuenta confirmado por el usuario a la fecha --now. "
                          "Si se pasa, reemplaza el saldo ajustado del mes en curso (marcado como REAL en vez de proyectado).")
    args = ap.parse_args()

    with open(args.plan_cashflow, encoding="utf-8") as f:
        plan_raw = json.load(f)
    plan = dict(plan_raw)
    plan["_month_keys"] = plan_raw["months"]
    with open(args.ventas_mes, encoding="utf-8") as f:
        ventas_mes = json.load(f)
    with open(args.cxp, encoding="utf-8") as f:
        cxp_rows = json.load(f)

    now = datetime.datetime.fromisoformat(args.now)
    cutoff_date = now.date()
    current_month = f"{now.year:04d}-{now.month:02d}"
    if current_month not in plan["_month_keys"]:
        raise SystemExit(f"ERROR: {current_month} no está en plan_flujo_caja.json (rango {plan['_month_keys'][0]}..{plan['_month_keys'][-1]}).")

    personal_admin_monthly = plan["pagos"]["personal_admin"][0]
    cushion_value = args.cushion_months * personal_admin_monthly

    rows, detalle_ajuste, cxp_next60 = build_trajectory(plan, ventas_mes, current_month, cxp_rows, cutoff_date, cushion_value)
    cxp = build_cxp(cxp_rows, cutoff_date)

    idx_current = plan["_month_keys"].index(current_month)
    current_row = rows[idx_current]
    saldo_real_confirmado = args.saldo_real is not None
    if saldo_real_confirmado:
        current_row["esReal"] = True
        # recalcular offset hacia adelante con el saldo real confirmado (reemplaza el ajuste por venta real)
        offset = args.saldo_real - (plan["saldo_final"][idx_current])
        for j in range(idx_current, len(rows)):
            rows[j]["saldoFinalAjustado"] = plan["saldo_final"][j] + offset
            rows[j]["cajaLibre"] = rows[j]["saldoFinalAjustado"] - rows[j]["colchonFijo"] - rows[j]["obligaciones60d"]
            rows[j]["alertaColchon"] = rows[j]["saldoFinalAjustado"] < rows[j]["colchonFijo"]
            rows[j]["alertaExcedente"] = rows[j]["cajaLibre"] > rows[j]["colchonFijo"]
        current_row["alertaPiso"] = args.saldo_real < plan["saldo_final"][idx_current]
    else:
        current_row["esReal"] = False

    piso_minimo_idx = min(range(len(rows)), key=lambda i: rows[i]["saldoFinalAjustado"])
    piso_minimo = rows[piso_minimo_idx]

    # Nota: "excedente" NO se lista aquí factura a factura — con la trayectoria tan holgada del
    # plan, casi todos los meses califican, y una lista de 15 alertas "info" repetidas le resta
    # señal a las alertas que sí importan (colchón/piso/vencidas). La caja libre por mes queda en
    # `trajectory[].cajaLibre`/`alertaExcedente` para que el HTML la muestre como panel de
    # tendencia aparte, con un resumen de cuántos meses y el rango de caja libre.
    alerts = []
    for r in rows:
        if r["alertaColchon"]:
            alerts.append({"tipo": "colchon", "severidad": "rojo", "mes": r["label"],
                            "texto": f"{r['label']}: saldo proyectado {money_short(r['saldoFinalAjustado'])} por debajo del colchón fijo de {money_short(r['colchonFijo'])} (6 meses de Personal+Admin)."})
        if r["alertaPiso"]:
            alerts.append({"tipo": "piso", "severidad": "amarillo", "mes": r["label"],
                            "texto": f"{r['label']}: saldo ajustado {money_short(r['saldoFinalAjustado'])} por debajo de lo que el plan proyectaba ({money_short(r['saldoFinalPlan'])})."})
    if cxp["vencidaTotal"] > 0:
        alerts.insert(0, {"tipo": "vencida", "severidad": "rojo", "mes": current_row["label"],
                           "texto": f"{len(cxp['vencidas'])} factura(s) vencida(s) por {money_short(cxp['vencidaTotal'])} — ver detalle en Cuentas por Pagar."})

    data = {
        "meta": {
            "now": f'{now.day} {MESES_ES[now.month-1]} {now.year}, {now.strftime("%H:%M")} hora Bogotá',
            "currentMonth": current_month, "currentMonthLabel": month_label(current_month),
            "salesCutoff": ventas_mes["meta"]["cutoff"],
            "cushionMonths": args.cushion_months,
        },
        "cushion": {"months": args.cushion_months, "personalAdminMonthly": personal_admin_monthly, "value": cushion_value},
        "kpis": {
            "saldoActual": current_row["saldoFinalAjustado"],
            "saldoActualEsReal": saldo_real_confirmado,
            "saldoPlanOriginal": plan["saldo_final"][idx_current],
            "deltaVsPlan": current_row["saldoFinalAjustado"] - plan["saldo_final"][idx_current],
            "pisoMinimoPeriodo": piso_minimo["saldoFinalAjustado"], "pisoMinimoMes": piso_minimo["label"],
            "cxpPendienteTotal": cxp["total"], "cxpVencida": cxp["vencidaTotal"],
            "cajaLibreHoy": current_row["cajaLibre"],
        },
        "trajectory": rows,
        "detalleAjuste": detalle_ajuste,
        "ventasMes": ventas_mes,
        "cxp": cxp,
        "alerts": alerts,
    }

    print(f"=== Flujo de Caja Mompossina — corte {data['meta']['now']} ===")
    print(f"Mes en curso: {data['meta']['currentMonthLabel']}")
    print(f"Saldo ajustado hoy: {money_short(current_row['saldoFinalAjustado'])} "
          f"({'REAL confirmado' if saldo_real_confirmado else 'proyectado, sin saldo real confirmado'}) "
          f"vs. plan original {money_short(plan['saldo_final'][idx_current])} "
          f"(delta {money_short(current_row['saldoFinalAjustado'] - plan['saldo_final'][idx_current])})")
    print(f"Ajuste por venta real: online {money_short(detalle_ajuste['online'])}, showroom {money_short(detalle_ajuste['showroom'])}, "
          f"nacional {money_short(detalle_ajuste['nacional'])}, internacional {money_short(detalle_ajuste['internacional'])}")
    print(f"Colchón fijo ({args.cushion_months} meses Personal+Admin): {money_short(cushion_value)}")
    print(f"Piso mínimo del periodo: {money_short(piso_minimo['saldoFinalAjustado'])} en {piso_minimo['label']}")
    print(f"CxP pendiente total: {money_short(cxp['total'])} ({len(cxp_rows)} facturas) — vencida: {money_short(cxp['vencidaTotal'])}")
    print(f"CxP próximos 60 días: {money_short(cxp_next60)}")
    print(f"Caja libre hoy (saldo - colchón - obligaciones 60d): {money_short(current_row['cajaLibre'])}")
    n_excedente = sum(1 for r in rows if r["alertaExcedente"])
    caja_libre_vals = [r["cajaLibre"] for r in rows]
    print(f"Caja libre proyectada en excedente (>1x colchón) en {n_excedente}/{len(rows)} meses "
          f"— rango {money_short(min(caja_libre_vals))} a {money_short(max(caja_libre_vals))}")
    print(f"Alertas generadas: {len(alerts)}")
    for a in alerts:
        print(f"  [{a['severidad'].upper():8s}] {a['texto']}")

    if args.html:
        data_js = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";"
        with open(args.html, encoding="utf-8") as f:
            html = f.read()
        html = patch_block(html, "<!-- DATA_START -->", "<!-- DATA_END -->", data_js)
        traj_svg = build_trajectory_svg(rows)
        html = patch_block(html, "<!-- TRAJECTORY_SVG_START -->", "<!-- TRAJECTORY_SVG_END -->", traj_svg)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nHTML actualizado: {args.html}")
    else:
        print("\n(--html no indicado, no se parcheó ningún archivo)")


if __name__ == "__main__":
    main()
