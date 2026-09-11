#!/usr/bin/env python3
"""
compute.py — Motor de cálculo del dashboard Flujo de Caja (Mompossina).

Toda la aritmética vive AQUÍ, no en el modelo — mismo principio que
presupuesto-vs-real, lovessence-dashboard y cierre-mensual. El script arma
el objeto `DATA` completo y PARCHEA dashboards/flujo-caja.html entre los
marcadores <!-- DATA_START --> / <!-- DATA_END --> (más
<!-- TRAJECTORY_SVG_START/END --> para el gráfico de trayectoria de caja,
generado en Python como SVG inline, sin dependencias externas).

## Fuentes de datos y cómo se combinan

1. **Trayectoria de 16 meses (Sep-26 a Dic-27)** = la hoja "Flujo de Caja"
   del Plan Estratégico 2026-2027 (Dropbox), extraída completa a
   `plan_flujo_caja.json` (estático, no se vuelve a leer el Excel cada
   corrida salvo que el usuario avise de un ajuste al plan). Caja inicial
   $1,018M (banco $41M + fiducuenta $977M), supuestos de cobro/pago del
   propio plan (online/showroom/nacional 100% mismo mes, exportaciones
   80%/20% con 1 mes de rezago, producción 2 meses de anticipo, IVA en el
   mes real del bimestre). El "Pagos" de cada mes de la trayectoria YA
   incluye las 4 categorías completas del plan (Producción, Mercadeo y
   Ventas, Personal+Admin, IVA bimestral) — ver `pagosBreakdown` en `DATA`
   para el desglose mes a mes, y la sección "Pagos proyectados por
   categoría" del dashboard.

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
   ver `build_trajectory()`. Si se pasa `--saldo-real`, este ajuste queda
   reemplazado por el offset real vs. plan (ver más abajo).
   Cobros extraordinarios (ej. facturación FLA fuera de presupuesto) NO se
   mezclan en este ajuste — se muestran aparte en `presupuesto-vs-real`,
   marcados para conciliar contra el supuesto de "cobros pendientes de
   agosto" que ya trae el plan, porque no hay forma confiable de saber si
   ya estaban baked-in sin confirmación contable.

3. **CxP real (obligaciones próximas)** = ledger completo de
   `CONTROL DE PAGOS 2026.xlsx` (Google Drive), filtrado a filas con
   "TOTAL PEND*PAGO" > 0 (columna M) — es decir, lo que de verdad sigue
   pendiente de pago hoy, con su fecha de vencimiento real (columna N). Se
   muestra APARTE de la trayectoria de 16 meses (no se resta del saldo mes
   a mes) porque el ledger sólo captura lo pendiente, no el total gastado
   del mes (lo ya pagado no aparece) — mezclarlo subestimaría el gasto
   real. Sirve para la vista táctica "qué se vence y cuándo" y para el
   colchón de caja libre (ver abajo). "Ledger" = el registro/libro de
   pagos del archivo CONTROL DE PAGOS — se usa "registro real de pagos" en
   los textos de cara al usuario para no asumir jerga contable en inglés.

4. **Colchón dinámico (confirmado con el usuario, 2026-09-11)** — el
   colchón mínimo YA NO usa el valor estático "Personal+Admin fijo" del
   plan ($60.3M/mes, congelado desde que se armó el plan en agosto). En su
   lugar, `compute_personal_admin_actual()` calcula el promedio de los
   últimos 2 meses calendario YA CERRADOS de gasto real de Personal +
   Administrativos, tomado del mismo ledger de `CONTROL DE PAGOS 2026.xlsx`
   (todas las filas, pagadas y pendientes — no sólo lo pendiente). Esto
   hace que el colchón suba o baje automáticamente con la estructura real
   del equipo (ej. una contratación nueva sube el colchón en cuanto su
   primera nómina quede registrada en el archivo — no hace falta tocar
   `compute.py` cada vez).

   Limpieza aplicada antes de sumar cada mes (`clean_personal_admin_month`):
   - Se excluyen filas cuyo proveedor sea exactamente "IVA" o "RT" (pagos
     de impuestos/retenciones, NO son estructura de personal/admin — se
     encontró un caso real de $142M de IVA mal clasificado bajo "GASTOS
     ADMINISTRATIVOS" en julio-2026 que distorsionaba el mes por completo).
   - Se excluyen filas cuya "FECHA LLEGO" (o "FECHA PARA PAGO" si la
     primera está vacía) NO caiga dentro del mes que se está sumando — esto
     saca deuda vieja arrastrada de meses anteriores (ej. PADILLO, una
     factura de julio que sigue apareciendo en pestañas posteriores porque
     sigue sin pagarse) del cálculo de "estructura del mes".
   - Se exige además que la fila viva en la pestaña PROPIA de ese mes
     (`mes_tab`) — el archivo re-lista facturas viejas sin pagar en cada
     pestaña mensual siguiente como recordatorio (la misma factura PADILLO
     de julio aparece de nuevo, idéntica, en las pestañas de agosto Y
     septiembre). Sin este filtro la misma factura se contaría dos o tres
     veces sólo por aparecer repetida en varias pestañas.
   No se usa el mes en curso (parcial, subestimaría — muchos gastos
   recurrentes del mes todavía no se han registrado a mitad de mes) ni un
   promedio más largo (meses como junio-2026 muestran picos ~2x que no se
   pudieron explicar con la misma regla de limpieza — usar sólo los 2 más
   recientes evita que un mes atípico antiguo siga pesando indefinidamente).
   Si no se pasa `--personal-admin-ledger`, cae de vuelta al valor estático
   del plan (con aviso en el resumen impreso) — nunca debe faltar en una
   corrida normal del skill.

## Alertas (confirmado con el usuario — dos capas + desviación siempre visible)

- **Desviación vs. plan**: SIEMPRE se muestra una entrada para el mes en
  curso comparando el saldo (real si el usuario lo confirmó, si no
  ajustado con venta real) contra lo que el plan proyectaba para ese mismo
  punto — en rojo si está por debajo, en verde si está por encima, con el
  valor de la diferencia. No es una alerta condicional: es un indicador de
  estado permanente del mes en curso.
- **Colchón dinámico**: alerta (rojo) sólo si el saldo de algún mes cae por
  debajo del colchón calculado (ver punto 4 arriba) — no se muestra nada si
  ningún mes lo compromete.
- **Facturas vencidas**: alerta (rojo) sólo si hay alguna, con el total
  adeudado — igual que antes.
- **Excedente**: caja libre = saldo del mes − colchón − obligaciones
  conocidas de los próximos ~60 días (para el mes en curso, suma real del
  ledger de CxP con vencimiento ≤ hoy+60d; para meses futuros, se usa el
  total de "Pagos" que el propio plan proyecta para ese mes como proxy,
  ya que no hay ledger real tan adelante). Se marca excedente cuando la
  caja libre supera 1x el colchón (doble colchón: el estructural más otro
  tanto por encima de las obligaciones conocidas). NO se lista como alerta
  individual por mes — con la trayectoria tan holgada del plan, casi todos
  los meses califican y le resta señal a las alertas que sí importan. Vive
  como panel de tendencia aparte ("Caja libre proyectada por mes").

Uso:
  python3 compute.py \
      --plan-cashflow plan_flujo_caja.json \
      --ventas-mes ventas_mes.json \
      --cxp cxp_pendientes.json \
      --personal-admin-ledger personal_admin_ledger.json \
      --now "2026-09-11T00:00:00-05:00" \
      --cushion-months 6 \
      --html ../../../dashboards/flujo-caja.html \
      [--saldo-real 1204297352]
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

PAGOS_CATEGORY_LABELS = [
    ("produccion", "Producción"),
    ("mercadeo", "Mercadeo y Ventas"),
    ("personal_admin", "Personal + Administrativos"),
    ("iva_bimestral", "IVA bimestral"),
]

BUCKET_DEFS = [
    ("vencida", "Vencida", None, -1),
    ("0-7", "0-7 días", 0, 7),
    ("8-30", "8-30 días", 8, 30),
    ("31-60", "31-60 días", 31, 60),
    ("61-90", "61-90 días", 61, 90),
    ("90+", "Más de 90 días", 91, None),
]

TAX_ENTRY_RE = re.compile(r"^\s*(IVA|RT)\s*$", re.IGNORECASE)
PERSONAL_ADMIN_CATS = ("GASTOS PERSONAL", "GASTOS ADMINISTRATIVOS")


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


def clean_personal_admin_month(ledger_rows, target_ym):
    """Suma GASTOS PERSONAL + GASTOS ADMINISTRATIVOS de un mes (YYYY-MM),
    excluyendo pagos de impuestos (IVA/RT) y facturas cuyo origen (FECHA
    LLEGO, o FECHA PARA PAGO si la primera falta) sea de un mes distinto —
    deuda vieja arrastrada en la pestaña del mes en curso. También exige
    que la fila viva en la pestaña PROPIA de ese mes (`mes_tab`) — el
    archivo re-lista facturas viejas sin pagar en cada pestaña mensual
    siguiente como recordatorio (ej. PADILLO $13.12M aparece igual en
    AGOSTO y SEPTIEMBRE con la misma fecha de julio) — sin este filtro se
    cuenta la misma factura más de una vez. Ver docstring del módulo,
    sección "Colchón dinámico"."""
    y, m = (int(x) for x in target_ym.split("-"))
    target_tab = MESES_ES_LARGO[m - 1].upper()
    total = 0.0
    for r in ledger_rows:
        if r.get("categoria") not in PERSONAL_ADMIN_CATS:
            continue
        if (r.get("mes_tab") or "").upper() != target_tab:
            continue
        empresa = (r.get("empresa") or "").strip()
        if TAX_ENTRY_RE.match(empresa):
            continue
        ref_date = r.get("fecha_llego") or r.get("fecha_pago")
        if not ref_date or ref_date[:7] != target_ym:
            continue
        total += float(r["valor_factura"])
    return total


def compute_personal_admin_actual(ledger_rows, now, n_months=2):
    """Promedio de los `n_months` meses calendario completos más recientes
    antes de `now` (ej. si now es septiembre, usa julio y agosto)."""
    y, m = now.year, now.month
    targets = []
    for _ in range(n_months):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        targets.append(f"{y:04d}-{m:02d}")
    monthly = {ym: clean_personal_admin_month(ledger_rows, ym) for ym in targets}
    avg = sum(monthly.values()) / len(monthly) if monthly else 0.0
    return avg, monthly


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

    vencidas = sorted(
        [r for r in cxp_rows if datetime.date.fromisoformat(r["fecha_pago"][:10]) < cutoff_date],
        key=lambda r: r["fecha_pago"]
    )

    return {
        "total": total, "buckets": buckets, "byCategory": by_category,
        "vencidas": vencidas,
        "vencidaTotal": sum(r["pendiente"] for r in vencidas),
    }


def build_pagos_breakdown(plan, idx_current, n_months=4):
    end = min(idx_current + n_months, len(plan["_month_keys"]))
    month_keys = plan["_month_keys"][idx_current:end]
    categories = []
    for cat_key, cat_label in PAGOS_CATEGORY_LABELS:
        values = [plan["pagos"][cat_key][plan["_month_keys"].index(m)] for m in month_keys]
        categories.append({"key": cat_key, "label": cat_label, "values": values})
    totals = [
        sum(plan["pagos"][k][plan["_month_keys"].index(m)] for k, _ in PAGOS_CATEGORY_LABELS)
        for m in month_keys
    ]
    return {"months": [month_label(m) for m in month_keys], "categories": categories, "totals": totals}


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
    cushion_label = f'<text x="{pad_l + 6}" y="{cushion_y - 6:.1f}" class="chart-axis-label" text-anchor="start">Colchón {money_short(cushion)}</text>'

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
    ap.add_argument("--personal-admin-ledger",
                     help="JSON con filas de GASTOS PERSONAL/ADMINISTRATIVOS (todas, pagadas+pendientes, "
                          "con fecha_llego) de los últimos meses — para el colchón dinámico. Si se omite, "
                          "cae de vuelta al valor estático del plan (no debería pasar en una corrida normal).")
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

    personal_admin_plan_static = plan["pagos"]["personal_admin"][0]
    if args.personal_admin_ledger:
        with open(args.personal_admin_ledger, encoding="utf-8") as f:
            pa_ledger_rows = json.load(f)
        personal_admin_actual, pa_monthly = compute_personal_admin_actual(pa_ledger_rows, now)
        personal_admin_source = (
            "promedio real de " + ", ".join(pa_monthly.keys()) +
            " (GASTOS PERSONAL + ADMINISTRATIVOS del registro de pagos, sin impuestos ni deuda arrastrada)"
        )
    else:
        personal_admin_actual = personal_admin_plan_static
        pa_monthly = {}
        personal_admin_source = "valor estático del plan (sin --personal-admin-ledger en esta corrida)"

    cushion_value = args.cushion_months * personal_admin_actual

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
    else:
        current_row["esReal"] = False

    piso_minimo_idx = min(range(len(rows)), key=lambda i: rows[i]["saldoFinalAjustado"])
    piso_minimo = rows[piso_minimo_idx]
    pagos_breakdown = build_pagos_breakdown(plan, idx_current)

    # ---- alertas ----
    # Desviación vs. plan: SIEMPRE presente para el mes en curso (rojo si por debajo, verde si por
    # encima) — es un indicador de estado, no una alerta condicional. Colchón y vencidas sólo
    # aparecen cuando de verdad se disparan (ver docstring, sección "Alertas").
    delta_actual = current_row["saldoFinalAjustado"] - current_row["saldoFinalPlan"]
    alerts = [{
        "tipo": "desviacion",
        "severidad": "verde" if delta_actual >= 0 else "rojo",
        "mes": current_row["label"],
        "texto": (
            f"{current_row['label']}: saldo {'REAL' if saldo_real_confirmado else 'ajustado'} "
            f"{money_short(current_row['saldoFinalAjustado'])} está {money_short(abs(delta_actual))} "
            f"{'por encima' if delta_actual >= 0 else 'por debajo'} de lo que el plan proyectaba "
            f"({money_short(current_row['saldoFinalPlan'])})."
        ),
    }]
    for r in rows:
        if r["alertaColchon"]:
            alerts.append({"tipo": "colchon", "severidad": "rojo", "mes": r["label"],
                            "texto": f"{r['label']}: saldo proyectado {money_short(r['saldoFinalAjustado'])} por debajo del colchón mínimo de {money_short(r['colchonFijo'])}."})
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
        "cushion": {
            "months": args.cushion_months,
            "personalAdminMonthly": personal_admin_actual,
            "personalAdminSource": personal_admin_source,
            "personalAdminByMonth": pa_monthly,
            "personalAdminPlanStatic": personal_admin_plan_static,
            "value": cushion_value,
        },
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
        "pagosBreakdown": pagos_breakdown,
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
    print(f"Colchón ({args.cushion_months} meses × Personal+Admin real {money_short(personal_admin_actual)}/mes, "
          f"fuente: {personal_admin_source}): {money_short(cushion_value)}")
    if pa_monthly:
        for ym, val in pa_monthly.items():
            print(f"  {ym}: {money_short(val)} (limpio de IVA/RT y deuda arrastrada)")
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
