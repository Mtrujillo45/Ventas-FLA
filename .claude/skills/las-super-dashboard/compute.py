#!/usr/bin/env python3
"""
compute.py — Motor de cálculo del Dashboard de Ventas de Las Super Empanadas.

Toda la aritmética vive AQUÍ, no en el modelo. Lee el texto plano extraído del
archivo "Caja LS 2026.xlsx" (Dropbox, carpeta LAS SUPER) — una línea por fila
de cada hoja de cálculo, columnas separadas por tabulador, con el nombre de la
hoja como línea propia justo antes de sus datos — y:

  1. Parsea la hoja "Caja" (el libro diario de caja: única fuente confiable
     de ventas 2026, según decisión del usuario — las hojas "ER" y
     "Venta Mensual" no siempre cuadran entre sí para el mismo mes).
  2. Agrega ventas por día, semana (lunes-domingo), mes y acumulado del año,
     y por empleada (Yaneth y Lina — únicas que registran ventas en el
     mostrador).
  3. Arma el Estado de Resultados mensual 2026 (Ventas, CMV, Utilidad Bruta,
     Nómina, Gastos Operativos, Producto malo, Impuestos, Utilidad Operativa,
     Retiros de socios, Flujo libre de caja) sumando por "Centro Costos".
  4. Extrae el histórico 2020-2026 de Ventas y Utilidad de Socios de la hoja
     "Venta Mensual" (única fuente con esos años; no existe libro diario
     anterior a 2026 en este archivo).
  5. Calcula alertas/semáforos usando el punto de equilibrio de la hoja "P.E"
     y los benchmarks de food cost / retiros de socios ya documentados en la
     hoja "Análisis" del propio archivo.
  6. Genera el HTML completo y autocontenido del dashboard (paleta viva
     amarillo/anaranjado/rojo).

Uso:
  python3 compute.py --text caja_ls_2026_text.txt --html dashboards/las-super.html \
      --now "2026-08-14T09:00:00-05:00" --source-modified "2026-08-14T16:42:30Z"

--text es el campo "text" (tal cual, texto plano) devuelto por
mcp__Dropbox__fetch sobre "/LAS SUPER/Caja LS 2026.xlsx", guardado con Write
o extraído del archivo de resultado grande con:
  jq -r '.text' mcp-Dropbox-fetch-*.txt > caja_ls_2026_text.txt
"""
import argparse
import datetime
import json
import re
from collections import defaultdict

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
MES_NUM = {m: i + 1 for i, m in enumerate(MESES)}
MES_CAP = {m: m.capitalize() for m in MESES}

CENTRO_BUCKET = {
    "materia prima": "cmv",
    "nomina": "nomina",
    "gasto operativo": "gasto_operativo",
    "producto malo": "producto_malo",
    "impuestos": "impuestos",
    "socios": "socios",
    "prestamo": "prestamo",
}

EMPLEADOS = ["yaneth", "lina"]
EMPLEADO_LABEL = {"yaneth": "Yaneth", "lina": "Lina"}


# ---------- utilidades numéricas ----------

def money(n):
    if n is None:
        return "—"
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(n):,.0f}"


def money_short(n):
    if n is None:
        return "—"
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1_000_000:
        return f"{sign}${a / 1_000_000:,.1f}M"
    if a >= 1_000:
        return f"{sign}${a / 1_000:,.0f}K"
    return f"{sign}${a:,.0f}"


def pct(part, whole):
    if not whole:
        return 0.0
    return part / whole * 100


def parse_money(s):
    s = (s or "").strip()
    if not s or "ERROR" in s.upper():
        return None
    neg = s.startswith("-")
    s2 = s.replace("$", "").replace(" ", "").replace(",", "").lstrip("-")
    if not s2 or s2 == "-":
        return None
    try:
        v = float(s2)
    except ValueError:
        return None
    return -v if neg else v


# ---------- localizar hojas dentro del volcado de texto ----------

def find_line_index(lines, target, start=0):
    for i in range(start, len(lines)):
        if lines[i].strip() == target:
            return i
    return None


def slice_sheet(lines, name, next_candidates):
    start = find_line_index(lines, name)
    if start is None:
        raise SystemExit(
            f"ERROR: no se encontró la hoja '{name}' en el texto extraído del "
            f"archivo — puede que la estructura del Excel haya cambiado."
        )
    end = len(lines)
    for cand in next_candidates:
        idx = find_line_index(lines, cand, start + 1)
        if idx is not None:
            end = idx
            break
    return lines[start:end]


# ---------- hoja "Caja": libro diario ----------

def parse_caja(lines):
    txs = []
    for l in lines:
        parts = l.split("\t")
        if len(parts) < 9:
            continue
        if parts[1].strip() != "2026":
            continue
        fecha_s = parts[2].strip()
        mes = parts[3].strip().lower()
        desc = parts[4].strip().lower()
        centro = parts[5].strip().lower()
        encargado = parts[6].strip().lower()
        entsal = parts[7].strip().lower()
        valor = parse_money(parts[8])
        saldo = parse_money(parts[9]) if len(parts) > 9 else None
        if valor is None or mes not in MES_NUM:
            continue
        try:
            fecha = datetime.datetime.strptime(fecha_s, "%m/%d/%y").date()
        except ValueError:
            continue
        txs.append(dict(fecha=fecha, mes=mes, desc=desc, centro=centro,
                         encargado=encargado, entsal=entsal, valor=valor, saldo=saldo))
    if not txs:
        raise SystemExit("ERROR: no se pudo parsear ninguna fila válida de la hoja 'Caja'.")
    return txs


def is_sale(tx):
    # OJO: el campo Ent/Sal NO es confiable para Centro Costos == "venta" —
    # ~26 filas de venta en 2026 están etiquetadas "Salida" con un monto
    # positivo (probable error de captura: el saldo de caja sube en esas
    # filas exactamente como si fueran "Entrada"). Verificado fila por fila
    # contra la columna "Saldo caja": en las 1,798 transiciones consecutivas
    # del libro diario, el saldo siempre cambia exactamente en el signo real
    # del "Valor" tal como está impreso (con o sin "-"), sin una sola
    # excepción — así que el signo de Valor manda, no la etiqueta de texto.
    # Por eso aquí se toma CUALQUIER fila con Centro Costos == "venta" con su
    # signo real (incluye 1 fila de -$10,000 en mayo, un reverso genuino).
    return tx["centro"] == "venta"


def week_key(d):
    iso_year, iso_week, _ = d.isocalendar()
    monday = d - datetime.timedelta(days=d.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return (iso_year, iso_week), monday, sunday


def aggregate_ventas(txs):
    daily = defaultdict(float)
    weekly = defaultdict(float)
    weekly_range = {}
    monthly = defaultdict(float)
    emp_monthly = {e: defaultdict(float) for e in EMPLEADOS}
    emp_total = {e: 0.0 for e in EMPLEADOS}

    for tx in txs:
        if not is_sale(tx):
            continue
        d = tx["fecha"]
        v = tx["valor"]
        daily[d] += v
        wk, mon, sun = week_key(d)
        weekly[wk] += v
        weekly_range[wk] = (mon, sun)
        monthly[d.month] += v
        emp = tx["encargado"]
        if emp in emp_monthly:
            emp_monthly[emp][d.month] += v
            emp_total[emp] += v

    return dict(daily=daily, weekly=weekly, weekly_range=weekly_range,
                monthly=monthly, emp_monthly=emp_monthly, emp_total=emp_total)


def build_er(txs):
    """Estado de Resultados por mes, sumando por Centro Costos.
    Metodología: la misma que ya usa la hoja 'Análisis' del propio archivo
    (sección 4, "Utilidad operativa real"): CMV, Nómina, Gastos operativos,
    Producto malo e Impuestos bajan hasta Utilidad Operativa; los Retiros de
    socios se muestran aparte, restados después, como reparto de utilidad
    (no como gasto operativo)."""
    er = {m: defaultdict(float) for m in range(1, 13)}
    for tx in txs:
        m = tx["fecha"].month
        if is_sale(tx):
            er[m]["ventas"] += tx["valor"]
            continue
        bucket = CENTRO_BUCKET.get(tx["centro"])
        if bucket:
            er[m][bucket] += tx["valor"]
    meses_con_datos = sorted(m for m in er if any(er[m].values()))
    rows = []
    for m in meses_con_datos:
        b = er[m]
        ventas = b.get("ventas", 0.0)
        cmv = b.get("cmv", 0.0)
        utilidad_bruta = ventas + cmv
        nomina = b.get("nomina", 0.0)
        gasto_operativo = b.get("gasto_operativo", 0.0)
        producto_malo = b.get("producto_malo", 0.0)
        impuestos = b.get("impuestos", 0.0)
        prestamo = b.get("prestamo", 0.0)
        utilidad_operativa = utilidad_bruta + nomina + gasto_operativo + producto_malo + impuestos
        socios = b.get("socios", 0.0)
        flujo_libre = utilidad_operativa + socios + prestamo
        rows.append(dict(
            mes=m, ventas=ventas, cmv=cmv, utilidad_bruta=utilidad_bruta,
            nomina=nomina, gasto_operativo=gasto_operativo, producto_malo=producto_malo,
            impuestos=impuestos, prestamo=prestamo, utilidad_operativa=utilidad_operativa,
            socios=socios, flujo_libre=flujo_libre,
        ))
    return rows


# ---------- hoja "Venta Mensual": histórico 2020-2026 ----------

def year_cols(header_line):
    parts = [p.strip() for p in header_line.split("\t")]
    cols = {}
    for j, c in enumerate(parts):
        if re.fullmatch(r"20\d\d", c):
            cols[c] = j
    return cols


def read_year_table(lines, header_idx, cols):
    years = sorted(cols.keys())
    data = {y: [None] * 12 for y in years}
    k = 1
    for expected_month in range(1, 13):
        if header_idx + k >= len(lines):
            break
        parts = [p.strip() for p in lines[header_idx + k].split("\t")]
        mes_label = None
        for p in parts:
            if p.lower() in MES_NUM:
                mes_label = p.lower()
                break
        if mes_label is None or MES_NUM[mes_label] != expected_month:
            break
        for y in years:
            idx = cols[y]
            if idx < len(parts):
                data[y][expected_month - 1] = parse_money(parts[idx])
        k += 1
    return data


def parse_historico(lines):
    ventas_hdr = None
    utilidad_hdr = None
    for i, l in enumerate(lines):
        cells = [p.strip() for p in l.split("\t")]
        if "VENTAS" in cells and "2020" in cells and ventas_hdr is None:
            ventas_hdr = i
        if "UTILIDAD SOCIOS" in cells and "2020" in cells and utilidad_hdr is None:
            utilidad_hdr = i
    if ventas_hdr is None or utilidad_hdr is None:
        raise SystemExit(
            "ERROR: no se encontraron las tablas históricas 'VENTAS' / "
            "'UTILIDAD SOCIOS' en la hoja 'Venta Mensual' — revisa si cambió "
            "la estructura del archivo."
        )
    ventas_cols = year_cols(lines[ventas_hdr])
    utilidad_cols = year_cols(lines[utilidad_hdr])
    ventas_hist = read_year_table(lines, ventas_hdr, ventas_cols)
    utilidad_hist = read_year_table(lines, utilidad_hdr, utilidad_cols)
    return ventas_hist, utilidad_hist


# ---------- hoja "P.E": punto de equilibrio ----------

def find_labeled_value(full_text, label):
    for line in full_text.split("\n"):
        idx = line.find(label)
        if idx == -1:
            continue
        m = re.search(r"\$\s*([\d,]+)", line[idx + len(label):])
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def parse_breakeven(full_text):
    costo_fijo = find_labeled_value(full_text, "COSTO FIJO TOTAL MES")
    venta_min_mes = find_labeled_value(full_text, "Venta minima (PuntoEq)")
    venta_min_dia = find_labeled_value(full_text, "Venta Diaria")
    faltantes = [n for n, v in [
        ("COSTO FIJO TOTAL MES", costo_fijo),
        ("Venta minima (PuntoEq)", venta_min_mes),
        ("Venta Diaria", venta_min_dia),
    ] if v is None]
    if faltantes:
        raise SystemExit(
            "ERROR: no se pudo leer el punto de equilibrio de la hoja 'P.E' "
            f"(etiquetas no encontradas: {', '.join(faltantes)}). Revisa si "
            "esa hoja cambió de estructura antes de publicar el dashboard."
        )
    return dict(costo_fijo_mes=costo_fijo, venta_min_mes=venta_min_mes,
                venta_min_dia=venta_min_dia, venta_min_semana=venta_min_mes / 30 * 7)


# ---------- alertas ----------

def build_alerts(agg, er_rows, breakeven, txs):
    alerts = []
    dias = sorted(agg["daily"].keys())
    ultimo_dia = dias[-1]
    venta_ultimo_dia = agg["daily"][ultimo_dia]

    if venta_ultimo_dia < breakeven["venta_min_dia"]:
        alerts.append(dict(level="critical",
            title=f"Venta del {ultimo_dia.strftime('%d %b').lower()} por debajo del punto de equilibrio",
            detail=f"{money(venta_ultimo_dia)} vs. meta diaria de {money(breakeven['venta_min_dia'])}."))
    else:
        alerts.append(dict(level="good",
            title=f"Venta del {ultimo_dia.strftime('%d %b').lower()} por encima del punto de equilibrio",
            detail=f"{money(venta_ultimo_dia)} vs. meta diaria de {money(breakeven['venta_min_dia'])}."))

    mes_actual = ultimo_dia.month
    dias_transcurridos_mes = {d.day for d in dias if d.month == mes_actual}
    venta_mes_actual = agg["monthly"].get(mes_actual, 0.0)
    meta_prorrateada = breakeven["venta_min_dia"] * len(dias_transcurridos_mes)
    if venta_mes_actual < meta_prorrateada:
        alerts.append(dict(level="warning",
            title=f"{MES_CAP[MESES[mes_actual-1]]} va por debajo del ritmo de punto de equilibrio",
            detail=(f"{money(venta_mes_actual)} acumulado en {len(dias_transcurridos_mes)} días con venta "
                    f"vs. meta de {money(meta_prorrateada)} a ese ritmo (meta mensual completa: "
                    f"{money(breakeven['venta_min_mes'])}).")))
    else:
        alerts.append(dict(level="good",
            title=f"{MES_CAP[MESES[mes_actual-1]]} va por encima del ritmo de punto de equilibrio",
            detail=(f"{money(venta_mes_actual)} acumulado en {len(dias_transcurridos_mes)} días con venta "
                    f"vs. meta de {money(meta_prorrateada)} a ese ritmo.")))

    saldos = [(tx["fecha"], tx["saldo"]) for tx in txs if tx["saldo"] is not None]
    if saldos:
        saldos.sort(key=lambda x: x[0])
        saldo_actual = saldos[-1][1]
        fecha_min, saldo_min = min(saldos, key=lambda x: x[1])
        if saldo_actual < 0:
            alerts.append(dict(level="critical", title="La caja está en negativo ahora mismo",
                detail=f"Saldo actual: {money(saldo_actual)}."))
        elif saldo_min < 0:
            alerts.append(dict(level="warning",
                title="La caja estuvo en negativo este año",
                detail=(f"Mínimo del año: {money(saldo_min)} el {fecha_min.strftime('%d %b').lower()}. "
                        f"Saldo actual: {money(saldo_actual)}.")))
        else:
            alerts.append(dict(level="good", title="La caja no ha estado en negativo este año",
                detail=f"Saldo actual: {money(saldo_actual)}. Mínimo del año: {money(saldo_min)}."))

    ventas_ytd = sum(r["ventas"] for r in er_rows)
    cmv_ytd = sum(r["cmv"] for r in er_rows)
    food_cost_pct = pct(abs(cmv_ytd), ventas_ytd)
    if food_cost_pct >= 45:
        level = "critical"
    elif food_cost_pct >= 35:
        level = "warning"
    else:
        level = "good"
    alerts.append(dict(level=level, title=f"Food cost del año: {food_cost_pct:.1f}% de las ventas",
        detail="Benchmark de restaurantes: 28%-35%. Por encima de 45% es food cost alto (revisar precios/porciones/proveedores)."))

    utilidad_operativa_ytd = sum(r["utilidad_operativa"] for r in er_rows)
    retiros_ytd = abs(sum(r["socios"] for r in er_rows))
    if utilidad_operativa_ytd > 0:
        retiro_pct = pct(retiros_ytd, utilidad_operativa_ytd)
        if retiro_pct > 60:
            level = "critical"
        elif retiro_pct > 30:
            level = "warning"
        else:
            level = "good"
        alerts.append(dict(level=level,
            title=f"Retiros de socios: {retiro_pct:.0f}% de la utilidad operativa del año",
            detail=(f"{money(retiros_ytd)} retirados de {money(utilidad_operativa_ytd)} de utilidad operativa. "
                    "Recomendación: limitar retiros al 30% para dejar caja de reinversión.")))

    if len(er_rows) >= 2:
        ultimo, anterior = er_rows[-1], er_rows[-2]
        if anterior["ventas"] > 0:
            var = pct(ultimo["ventas"] - anterior["ventas"], anterior["ventas"])
            if var <= -15:
                alerts.append(dict(level="warning",
                    title=f"Venta cayó {abs(var):.0f}% de {MES_CAP[MESES[anterior['mes']-1]]} a {MES_CAP[MESES[ultimo['mes']-1]]}",
                    detail=f"{money(anterior['ventas'])} → {money(ultimo['ventas'])}."))
            elif var >= 15:
                alerts.append(dict(level="good",
                    title=f"Venta subió {var:.0f}% de {MES_CAP[MESES[anterior['mes']-1]]} a {MES_CAP[MESES[ultimo['mes']-1]]}",
                    detail=f"{money(anterior['ventas'])} → {money(ultimo['ventas'])}."))

    order = {"critical": 0, "warning": 1, "good": 2}
    alerts.sort(key=lambda a: order[a["level"]])
    return alerts, dict(food_cost_pct=food_cost_pct, ventas_ytd=ventas_ytd,
                         utilidad_operativa_ytd=utilidad_operativa_ytd, retiros_ytd=retiros_ytd)


# ---------- construcción del HTML ----------

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def kpi_card(label, value, sub, tone=""):
    tone_cls = f" {tone}" if tone else ""
    return (f'<div class="kpi"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div>'
            f'<div class="sub{tone_cls}">{sub}</div></div>')


def build_kpis(agg, er_rows, breakeven, ytd_stats, txs):
    dias = sorted(agg["daily"].keys())
    ultimo_dia = dias[-1]
    venta_hoy = agg["daily"][ultimo_dia]
    mes_actual = ultimo_dia.month
    venta_mes = agg["monthly"].get(mes_actual, 0.0)
    wk, mon, sun = week_key(ultimo_dia)
    venta_semana = agg["weekly"].get(wk, 0.0)
    saldos = [(tx["fecha"], tx["saldo"]) for tx in txs if tx["saldo"] is not None]
    saldos.sort(key=lambda x: x[0])
    saldo_actual = saldos[-1][1] if saldos else None

    cards = [
        kpi_card("Venta acumulada del año", money_short(ytd_stats["ventas_ytd"]),
                 f"enero–{MES_CAP[MESES[mes_actual-1]].lower()} 2026 · dato hasta {ultimo_dia.strftime('%d %b').lower()}"),
        kpi_card(f"Venta de {MES_CAP[MESES[mes_actual-1]]} (mes en curso)", money_short(venta_mes),
                 f"meta del mes: {money_short(breakeven['venta_min_mes'])}",
                 "good" if venta_mes >= breakeven["venta_min_mes"] * (ultimo_dia.day / 30) else "critical"),
        kpi_card("Venta última semana", money_short(venta_semana),
                 f"{mon.strftime('%d %b').lower()}–{sun.strftime('%d %b').lower()}"),
        kpi_card(f"Venta del {ultimo_dia.strftime('%d %b').lower()}", money_short(venta_hoy),
                 f"meta diaria: {money_short(breakeven['venta_min_dia'])}",
                 "good" if venta_hoy >= breakeven["venta_min_dia"] else "critical"),
        kpi_card("Saldo de caja actual", money_short(saldo_actual),
                 "según el libro diario de caja", "critical" if (saldo_actual or 0) < 0 else "good"),
        kpi_card("Utilidad operativa (año)", money_short(ytd_stats["utilidad_operativa_ytd"]),
                 f"{pct(ytd_stats['utilidad_operativa_ytd'], ytd_stats['ventas_ytd']):.1f}% margen operativo"),
        kpi_card("Food cost del año", f"{ytd_stats['food_cost_pct']:.1f}%",
                 "benchmark restaurantes: 28%-35%",
                 "good" if ytd_stats["food_cost_pct"] < 35 else ("warning" if ytd_stats["food_cost_pct"] < 45 else "critical")),
        kpi_card("Retiros de socios (año)", money_short(ytd_stats["retiros_ytd"]),
                 f"{pct(ytd_stats['retiros_ytd'], ytd_stats['utilidad_operativa_ytd']):.0f}% de la utilidad operativa"),
    ]
    return '<section class="kpi-grid">\n' + "\n".join(cards) + "\n</section>"


def build_alerts_html(alerts):
    out = ['<section class="card"><h2>Alertas para decisiones inmediatas</h2>',
           '<p class="section-sub">Basadas en el punto de equilibrio y los benchmarks ya calculados en el propio archivo (hojas P.E y Análisis)</p>',
           '<div class="alerts-grid">']
    for a in alerts:
        out.append(f'<div class="callout {a["level"]}"><span class="dot"></span>'
                    f'<div><b>{esc(a["title"])}</b>{a["detail"]}</div></div>')
    out.append("</div></section>")
    return "\n".join(out)


def build_bar_chart(labels, values, target=None, value_fmt=money_short, scrollable=False, min_bar_width=46):
    # Headroom (12%) arriba del valor más alto: antes la barra más alta
    # tocaba el 100% exacto del contenedor, así que valores parecidos
    # (p.ej. varias semanas entre $21M y $27M) se veían con casi la misma
    # altura — con margen arriba, cada valor tiene más rango vertical real
    # para diferenciarse.
    raw_max = max([abs(v) for v in values] + [target or 0, 1])
    vmax = raw_max * 1.12
    col_style = f' style="flex:0 0 {min_bar_width}px"' if scrollable else ""
    cols = []
    for lab, v in zip(labels, values):
        h = max(2, round(abs(v) / vmax * 100))
        empty = " empty" if v == 0 else ""
        below = " below-target" if (target and v < target) else ""
        cols.append(
            f'<div class="bar-col"{col_style}>'
            f'<div class="bar-value">{value_fmt(v)}</div>'
            f'<div class="bar-shape{empty}{below}" style="height:{h}%"></div>'
            f'<div class="bar-label">{esc(lab)}</div></div>'
        )
    # Las barras escalan contra la altura de .bar-col, que es la caja de
    # .barchart SIN su padding-top (20px reservados arriba para que la
    # etiqueta de la barra más alta no se corte). La línea de meta y las
    # guías, en cambio, se posicionan con "bottom" contra el contenedor
    # completo (con ese padding incluido) — por eso NO alcanza con usar el
    # mismo % que las barras: hay que restar esos 20px fijos con calc()
    # antes de aplicar la fracción, o la línea de meta queda desalineada
    # respecto a una barra que valga justo lo mismo.
    def bottom_calc(frac):
        return f"calc((100% - 20px) * {frac:.5f})"

    target_line = ""
    if target:
        target_frac = min(1.0, target / vmax)
        target_line = f'<div class="target-line" style="bottom:{bottom_calc(target_frac)}"><span>meta {value_fmt(target)}</span></div>'
    # líneas guía horizontales (sin etiqueta, para no chocar con el valor
    # que ya va impreso encima de cada barra) — sirven de regla visual para
    # comparar alturas parecidas de un vistazo.
    gridlines = "".join(
        f'<div class="grid-line" style="bottom:{bottom_calc(frac)}"></div>'
        for frac in (0.25, 0.5, 0.75)
    )
    barchart = f'<div class="barchart{" scrollable" if scrollable else ""}" role="img">{"".join(cols)}</div>'

    if not scrollable:
        return f'<div class="barchart-wrap">{gridlines}{barchart}{target_line}</div>'

    # Cuando hay más semanas de las que caben legibles en el ancho de la
    # tarjeta, el contenedor se desplaza horizontalmente en vez de seguir
    # angostando cada barra. El scrollbar nativo del navegador no es
    # confiable como señal visual (en varios navegadores/SO viene oculto u
    # "overlay", solo aparece al pasar el mouse) así que se reemplaza por
    # una barra de desplazamiento propia, siempre visible y arrastrable,
    # sincronizada por JS al final de la página (ver <script> en build_html).
    return (
        '<div class="barchart-wrap barchart-wrap-scroll">'
        f'<div class="barchart-scroll-inner">{gridlines}{barchart}{target_line}</div>'
        '</div>'
        '<div class="scrollbar-ui"><div class="scrollbar-track"><div class="scrollbar-thumb"></div></div></div>'
    )


def build_grouped_bar_chart(labels, series_a, series_b, label_a, label_b, color_a="var(--series-1)", color_b="var(--series-2)"):
    vmax = max(series_a + series_b + [1])
    cols = []
    for lab, a, b in zip(labels, series_a, series_b):
        ha = max(1, round(a / vmax * 100))
        hb = max(1, round(b / vmax * 100))
        cols.append(
            '<div class="gbar-col">'
            f'<div class="gbar-pair">'
            f'<div class="gbar-shape" style="height:{ha}%;background:{color_a}" title="{esc(label_a)}: {money(a)}"></div>'
            f'<div class="gbar-shape" style="height:{hb}%;background:{color_b}" title="{esc(label_b)}: {money(b)}"></div>'
            f'</div><div class="bar-label">{esc(lab)}</div></div>'
        )
    legend = (f'<div class="legend"><span><i style="background:{color_a}"></i>{esc(label_a)}</span>'
              f'<span><i style="background:{color_b}"></i>{esc(label_b)}</span></div>')
    return f'<div class="gbarchart">{"".join(cols)}</div>{legend}'


def label_anchor(px, width, pad_r, pad_l):
    """Ancla de texto SVG para que una etiqueta cerca del borde no se corte.
    Usa style="text-anchor:..." (no el atributo) porque la regla CSS
    .chart-axis/.chart-point-label { text-anchor:middle } tiene más
    prioridad que el atributo de presentación y lo ignoraría."""
    if px > width - pad_r - 30:
        return "end"
    if px < pad_l + 30:
        return "start"
    return "middle"


def build_daily_svg(daily_map, breakeven_dia, width=900, height=230, last_n=30):
    dias = sorted(daily_map.keys())[-last_n:]
    values = [daily_map[d] for d in dias]
    pad_l, pad_r, pad_t, pad_b = 46, 16, 22, 30
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(values)
    vmax = max(values + [breakeven_dia]) * 1.15 if values else 1.0

    def x(i):
        return pad_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def y(v):
        return pad_t + plot_h - (plot_h * v / vmax if vmax else 0)

    pts = [(x(i), y(v)) for i, v in enumerate(values)]
    path_d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    floor_y = pad_t + plot_h
    area_d = path_d + f" L {pts[-1][0]:.1f},{floor_y:.1f} L {pts[0][0]:.1f},{floor_y:.1f} Z"
    target_y = y(breakeven_dia)

    step = max(1, n // 8)
    x_labels = []
    for i in range(0, n, step):
        x_labels.append(f'<text x="{x(i):.1f}" y="{height-8}" class="chart-axis">{dias[i].strftime("%d/%m")}</text>')

    peak_i = max(range(n), key=lambda i: values[i]) if n else 0
    markers = []
    if n:
        px, py = pts[peak_i]
        anchor_peak = label_anchor(px, width, pad_r, pad_l)
        markers.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" class="chart-dot chart-dot-peak"/>')
        markers.append(f'<text x="{px:.1f}" y="{py-10:.1f}" class="chart-point-label chart-point-label-peak" style="text-anchor:{anchor_peak}">{money_short(values[peak_i])}</text>')
        if peak_i != n - 1:
            # el último día no es el pico: mostrar también su propio valor
            lx, ly = pts[-1]
            anchor_last = label_anchor(lx, width, pad_r, pad_l)
            markers.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" class="chart-dot"/>')
            markers.append(f'<text x="{lx:.1f}" y="{ly-10:.1f}" class="chart-point-label" style="text-anchor:{anchor_last}">{money_short(values[-1])}</text>')

    return f'''<svg viewBox="0 0 {width} {height}" class="daily-chart" role="img" aria-label="Ventas diarias, últimos {n} días">
    <defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="var(--series-1)" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="var(--series-1)" stop-opacity="0"/>
    </linearGradient></defs>
    <line x1="{pad_l}" y1="{target_y:.1f}" x2="{width-pad_r}" y2="{target_y:.1f}" class="target-dashed"/>
    <text x="{pad_l}" y="{target_y-6:.1f}" class="chart-axis" style="text-anchor:start">meta diaria {money_short(breakeven_dia)}</text>
    <path d="{area_d}" fill="url(#areaFill)" stroke="none"/>
    <path d="{path_d}" fill="none" class="chart-line"/>
    {"".join(markers)}
    {"".join(x_labels)}
  </svg>'''


def build_ytd_svg(monthly_2026, monthly_2025, breakeven_mes, width=900, height=220):
    meses_con_datos = sorted(monthly_2026.keys())
    cum_2026, cum_2025, cum_meta = [], [], []
    run26 = run25 = runm = 0.0
    for m in range(1, 13):
        run26 += monthly_2026.get(m, 0.0)
        run25 += (monthly_2025[m - 1] or 0.0) if monthly_2025 else 0.0
        runm += breakeven_mes
        cum_2026.append(run26)
        cum_2025.append(run25)
        cum_meta.append(runm)
    last_m = meses_con_datos[-1] if meses_con_datos else 1
    pad_l, pad_r, pad_t, pad_b = 46, 16, 22, 26
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    vmax = max(cum_2026[:last_m] + cum_2025 + cum_meta[:last_m] + [1]) * 1.08

    def x(i):
        return pad_l + plot_w * i / 11

    def y(v):
        return pad_t + plot_h - (plot_h * v / vmax if vmax else 0)

    def path_for(series, upto):
        pts = [(x(i), y(series[i])) for i in range(upto)]
        return "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts), pts

    d26, pts26 = path_for(cum_2026, last_m)
    dmeta, _ = path_for(cum_meta, 12)
    d25, pts25 = path_for(cum_2025, 12) if monthly_2025 else ("", [])

    x_labels = "".join(f'<text x="{x(i):.1f}" y="{height-6}" class="chart-axis">{MES_CAP[MESES[i]][:3]}</text>' for i in range(12))
    last_x, last_y = pts26[-1]
    anchor_last = label_anchor(last_x, width, pad_r, pad_l)
    label = f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3.5" class="chart-dot chart-dot-peak"/><text x="{last_x:.1f}" y="{last_y-10:.1f}" class="chart-point-label chart-point-label-peak" style="text-anchor:{anchor_last}">{money_short(cum_2026[last_m-1])}</text>'

    prev_line = f'<path d="{d25}" fill="none" class="chart-line-prev"/>' if d25 else ""
    return f'''<svg viewBox="0 0 {width} {height}" class="ytd-chart" role="img" aria-label="Ventas acumuladas del año vs meta de punto de equilibrio">
    <path d="{dmeta}" fill="none" class="target-dashed-line"/>
    {prev_line}
    <path d="{d26}" fill="none" class="chart-line"/>
    {label}
    {x_labels}
  </svg>'''


def build_er_table(er_rows):
    rows_html = []
    totals = defaultdict(float)
    for r in er_rows:
        for k in ("ventas", "cmv", "utilidad_bruta", "nomina", "gasto_operativo",
                   "producto_malo", "impuestos", "utilidad_operativa", "socios", "flujo_libre"):
            totals[k] += r[k]
        margen = pct(r["utilidad_operativa"], r["ventas"])
        rows_html.append(
            f'<tr><td>{MES_CAP[MESES[r["mes"]-1]]}</td>'
            f'<td class="num">{money(r["ventas"])}</td>'
            f'<td class="num neg">{money(r["cmv"])}</td>'
            f'<td class="num">{money(r["utilidad_bruta"])}</td>'
            f'<td class="num neg">{money(r["nomina"])}</td>'
            f'<td class="num neg">{money(r["gasto_operativo"])}</td>'
            f'<td class="num neg">{money(r["producto_malo"])}</td>'
            f'<td class="num neg">{money(r["impuestos"])}</td>'
            f'<td class="num">{money(r["utilidad_operativa"])}</td>'
            f'<td class="num neg">{money(r["socios"])}</td>'
            f'<td class="num">{money(r["flujo_libre"])}<span class="units">{margen:.0f}% marg.</span></td></tr>'
        )
    margen_total = pct(totals["utilidad_operativa"], totals["ventas"])
    rows_html.append(
        f'<tr class="total-row"><td>Total {"" }</td>'
        f'<td class="num">{money(totals["ventas"])}</td>'
        f'<td class="num neg">{money(totals["cmv"])}</td>'
        f'<td class="num">{money(totals["utilidad_bruta"])}</td>'
        f'<td class="num neg">{money(totals["nomina"])}</td>'
        f'<td class="num neg">{money(totals["gasto_operativo"])}</td>'
        f'<td class="num neg">{money(totals["producto_malo"])}</td>'
        f'<td class="num neg">{money(totals["impuestos"])}</td>'
        f'<td class="num">{money(totals["utilidad_operativa"])}</td>'
        f'<td class="num neg">{money(totals["socios"])}</td>'
        f'<td class="num">{money(totals["flujo_libre"])}<span class="units">{margen_total:.0f}% marg.</span></td></tr>'
    )
    return (
        '<table><thead><tr><th>Mes</th><th class="num">Ventas</th><th class="num">CMV</th>'
        '<th class="num">Ut. Bruta</th><th class="num">Nómina</th><th class="num">Gastos Op.</th>'
        '<th class="num">Prod. malo</th><th class="num">Impuestos</th><th class="num">Ut. Operativa</th>'
        '<th class="num">Retiros socios</th><th class="num">Flujo libre</th></tr></thead><tbody>'
        + "".join(rows_html) + "</tbody></table>"
    )


def build_historico_html(ventas_hist, utilidad_hist, monthly_2026, current_month, socios_monthly_2026):
    years = sorted(ventas_hist.keys())
    ventas_totales = {}
    for y in years:
        if y == "2026":
            ventas_totales[y] = sum(monthly_2026.values())
        else:
            ventas_totales[y] = sum(v for v in ventas_hist[y] if v)
    max_v = max(ventas_totales.values()) or 1

    rows_full = []
    prev = None
    for y in years:
        v = ventas_totales[y]
        width_pct = v / max_v * 100
        # el crecimiento año-contra-año no aplica al último año si está parcial
        # (compararía un año completo contra unos pocos meses) — se omite aquí;
        # la comparación justa vive en el bloque "mismo período" de al lado.
        growth = (f'<span class="growth {"pos" if v >= prev else "neg"}">{"+" if v >= prev else ""}{pct(v - prev, prev):.0f}%</span>'
                  if prev and y != "2026" else "")
        label = f'{y}' + (' <small>(parcial, ene–' + MES_CAP[MESES[current_month-1]].lower() + ')</small>' if y == "2026" else "")
        rows_full.append(
            '<div class="hbar-row"><div class="hbar-name">' + label + '</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{width_pct:.1f}%"></div></div>'
            f'<div class="hbar-value">{money_short(v)}{growth}</div></div>'
        )
        prev = v

    ytd_totales = {}
    for y in years:
        vals = monthly_2026 if y == "2026" else {i + 1: ventas_hist[y][i] for i in range(12)}
        ytd_totales[y] = sum((vals.get(m) or 0) for m in range(1, current_month + 1))
    max_ytd = max(ytd_totales.values()) or 1
    rows_ytd = []
    prev = None
    periodo = f'enero–{MES_CAP[MESES[current_month-1]].lower()}'
    for y in years:
        v = ytd_totales[y]
        width_pct = v / max_ytd * 100
        growth = f'<span class="growth {"pos" if v >= prev else "neg"}">{"+" if v >= prev else ""}{pct(v - prev, prev):.0f}%</span>' if prev else ""
        rows_ytd.append(
            f'<div class="hbar-row"><div class="hbar-name">{y}</div>'
            f'<div class="hbar-track"><div class="hbar-fill seg-2" style="width:{width_pct:.1f}%"></div></div>'
            f'<div class="hbar-value">{money_short(v)}{growth}</div></div>'
        )
        prev = v

    utilidad_totales = {}
    for y in years:
        if y == "2026":
            # La hoja "Venta Mensual" solo tiene enero-marzo cargados en su
            # columna 2026 de "UTILIDAD SOCIOS" (quedó desactualizada, igual
            # que pasaba con su columna de ventas) — para 2026 se usa el
            # mismo libro diario de caja (Centro Costos "socios") que ya usan
            # el KPI "Retiros de socios" y la fila "RETIROS SOCIOS" del
            # Estado de Resultados, para que las tres cifras coincidan.
            utilidad_totales[y] = sum(socios_monthly_2026.values())
        else:
            vals = utilidad_hist.get(y, [None] * 12)
            utilidad_totales[y] = sum(v for v in vals if v)
    max_u = max(utilidad_totales.values()) or 1
    rows_u = []
    prev = None
    for y in years:
        v = utilidad_totales[y]
        width_pct = v / max_u * 100 if max_u else 0
        growth = (f'<span class="growth {"pos" if v >= prev else "neg"}">{"+" if v >= prev else ""}{pct(v - prev, prev):.0f}%</span>'
                  if prev and y != "2026" else "")
        label = f'{y}' + (' <small>(parcial, ene–' + MES_CAP[MESES[current_month-1]].lower() + ')</small>' if y == "2026" else "")
        rows_u.append(
            '<div class="hbar-row"><div class="hbar-name">' + label + '</div>'
            f'<div class="hbar-track"><div class="hbar-fill seg-3" style="width:{width_pct:.1f}%"></div></div>'
            f'<div class="hbar-value">{money_short(v)}{growth}</div></div>'
        )
        prev = v

    return f'''<section class="two-col">
    <div class="card">
      <h2>Ventas por año — total anual</h2>
      <p class="section-sub">2026 es parcial (enero–{MES_CAP[MESES[current_month-1]].lower()}); no comparable 1:1 contra años completos</p>
      {"".join(rows_full)}
    </div>
    <div class="card">
      <h2>Ventas por año — mismo período ({periodo})</h2>
      <p class="section-sub">Comparación justa: solo los meses que ya cerraron este año, en todos los años</p>
      {"".join(rows_ytd)}
    </div>
  </section>
  <section class="card">
    <h2>Utilidad de socios por año</h2>
    <p class="section-sub">Única cifra de rentabilidad con histórico completo 2020-2025 en el archivo (retiros/reparto a socios, no Utilidad Neta contable)</p>
    {"".join(rows_u)}
  </section>'''


CSS = '''
:root {
  color-scheme: light;
  --surface-1: #fffaf3;
  --page: #fff6ea;
  --text-primary: #2a1608;
  --text-secondary: #6b4a2e;
  --text-muted: #9c7a54;
  --grid: #f0ddc0;
  --baseline: #e3c79a;
  --border: rgba(42,22,8,0.10);
  --series-1: #f2660a;
  --series-2: #d92b2b;
  --series-3: #f5b700;
  --good: #12793f;
  --warning: #b8790a;
  --critical: #c81e1e;
  --good-bg: #e6f5ea;
  --warning-bg: #fff2d6;
  --critical-bg: #fde6e2;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface-1: #211208;
    --page: #180d05;
    --text-primary: #fff3e2;
    --text-secondary: #e7c39c;
    --text-muted: #b5875a;
    --grid: #3a2413;
    --baseline: #4a2f18;
    --border: rgba(255,243,226,0.10);
    --series-1: #ff8a3d;
    --series-2: #ff5c5c;
    --series-3: #ffcf3d;
    --good: #3fcf78;
    --warning: #ffc542;
    --critical: #ff6b6b;
    --good-bg: rgba(63,207,120,0.14);
    --warning-bg: rgba(255,197,66,0.14);
    --critical-bg: rgba(255,107,107,0.14);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-1: #211208; --page: #180d05; --text-primary: #fff3e2;
  --text-secondary: #e7c39c; --text-muted: #b5875a; --grid: #3a2413; --baseline: #4a2f18;
  --border: rgba(255,243,226,0.10); --series-1: #ff8a3d; --series-2: #ff5c5c; --series-3: #ffcf3d;
  --good: #3fcf78; --warning: #ffc542; --critical: #ff6b6b;
  --good-bg: rgba(63,207,120,0.14); --warning-bg: rgba(255,197,66,0.14); --critical-bg: rgba(255,107,107,0.14);
}
* { box-sizing: border-box; }
body { margin:0; background:var(--page); color:var(--text-primary); font-family: system-ui,-apple-system,"Segoe UI",sans-serif; -webkit-font-smoothing:antialiased; }
.wrap { max-width:1180px; margin:0 auto; padding:28px 20px 64px; }
header.top { margin-bottom:24px; }
.eyebrow { display:inline-flex; align-items:center; gap:8px; font-size:12px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--series-1); background:color-mix(in srgb, var(--series-1) 14%, transparent); padding:4px 10px; border-radius:999px; margin-bottom:10px; }
h1 { font-size:28px; font-weight:800; margin:0 0 6px; letter-spacing:-0.01em; }
.subtitle { font-size:14px; color:var(--text-secondary); margin:0 0 4px; }
.meta { font-size:12.5px; color:var(--text-muted); }
.meta code { background:var(--grid); padding:1px 5px; border-radius:4px; font-size:11.5px; }
.card { background:var(--surface-1); border:1px solid var(--border); border-radius:14px; padding:20px 22px; }
section { margin-top:22px; }
h2 { font-size:15px; font-weight:800; margin:0 0 4px; }
.section-sub { font-size:12.5px; color:var(--text-muted); margin:0 0 16px; }
.kpi-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
.kpi { background:var(--surface-1); border:1px solid var(--border); border-radius:14px; padding:16px 16px 14px; }
.kpi .label { font-size:12px; color:var(--text-secondary); margin-bottom:8px; }
.kpi .value { font-size:23px; font-weight:800; letter-spacing:-0.01em; font-variant-numeric:tabular-nums; }
.kpi .sub { font-size:12px; color:var(--text-muted); margin-top:4px; }
.kpi .sub.good { color:var(--good); font-weight:600; }
.kpi .sub.critical { color:var(--critical); font-weight:600; }
.alerts-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.callout { display:flex; gap:12px; align-items:flex-start; border-radius:12px; padding:14px 16px; font-size:13px; line-height:1.5; }
.callout.critical { background:var(--critical-bg); color:var(--text-primary); }
.callout.warning { background:var(--warning-bg); color:var(--text-primary); }
.callout.good { background:var(--good-bg); color:var(--text-primary); }
.callout .dot { width:8px; height:8px; border-radius:50%; margin-top:6px; flex-shrink:0; }
.callout.critical .dot { background:var(--critical); }
.callout.warning .dot { background:var(--warning); }
.callout.good .dot { background:var(--good); }
.callout b { display:block; margin-bottom:2px; }
.barchart-wrap { position:relative; }
.barchart-wrap-scroll {
  overflow-x:auto; overflow-y:hidden;
  scrollbar-width:none; -ms-overflow-style:none;
}
.barchart-wrap-scroll::-webkit-scrollbar { display:none; height:0; }
.barchart-scroll-inner { position:relative; width:max-content; min-width:100%; }
.scrollbar-ui { margin-top:10px; }
.scrollbar-track { position:relative; height:8px; background:var(--grid); border-radius:999px; cursor:pointer; }
.scrollbar-thumb { position:absolute; top:0; left:0; height:100%; min-width:24px; background:var(--series-1); border-radius:999px; cursor:grab; touch-action:none; }
.scrollbar-thumb:hover { background:var(--series-2); }
.scrollbar-thumb:active { cursor:grabbing; background:var(--series-2); }
.barchart { position:relative; z-index:1; display:flex; align-items:flex-end; gap:8px; height:280px; padding-top:20px; }
.barchart.scrollable { width:max-content; }
.bar-col { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; }
.bar-value { font-size:10.5px; color:var(--text-secondary); margin-bottom:6px; white-space:nowrap; font-variant-numeric:tabular-nums; }
.bar-shape { width:100%; max-width:42px; background:var(--series-1); border-radius:4px 4px 0 0; transition:height .15s ease; }
.bar-shape.below-target { background:var(--series-2); }
.bar-shape.empty { background:var(--grid); }
.bar-label { margin-top:8px; font-size:10.5px; color:var(--text-muted); text-align:center; line-height:1.25; }
.grid-line { position:absolute; left:0; right:0; border-top:1px dashed var(--grid); z-index:0; }
.target-line { position:absolute; left:0; right:0; border-top:2px dashed var(--series-3); z-index:1; }
.target-line span { position:absolute; right:0; top:-18px; font-size:10.5px; color:var(--text-secondary); background:var(--surface-1); padding:0 4px; }
.gbarchart { display:flex; align-items:flex-end; gap:6px; height:170px; padding-top:10px; overflow-x:auto; }
.gbar-col { flex:0 0 auto; width:38px; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; }
.gbar-pair { display:flex; gap:2px; align-items:flex-end; height:100%; width:100%; }
.gbar-shape { flex:1; border-radius:3px 3px 0 0; min-height:2px; }
.hbar-row { display:grid; grid-template-columns:180px 1fr 150px; align-items:center; gap:12px; padding:7px 0; }
.hbar-row + .hbar-row { border-top:1px solid var(--grid); }
.hbar-name { font-size:13px; color:var(--text-primary); }
.hbar-name small { color:var(--text-muted); font-weight:400; }
.hbar-track { position:relative; height:14px; background:var(--grid); border-radius:4px; overflow:hidden; }
.hbar-fill { position:absolute; inset:0 auto 0 0; background:var(--series-1); border-radius:4px; }
.hbar-fill.seg-2 { background:var(--series-2); }
.hbar-fill.seg-3 { background:var(--series-3); }
.hbar-value { font-size:12.5px; text-align:right; font-variant-numeric:tabular-nums; color:var(--text-secondary); }
.growth { display:inline-block; margin-left:6px; font-size:11px; padding:1px 6px; border-radius:999px; }
.growth.pos { background:var(--good-bg); color:var(--good); }
.growth.neg { background:var(--critical-bg); color:var(--critical); }
.legend { display:flex; gap:16px; margin-top:10px; font-size:12px; color:var(--text-secondary); }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.legend i { width:10px; height:10px; border-radius:3px; display:inline-block; }
table { width:100%; border-collapse:collapse; font-size:12.5px; }
thead th { text-align:left; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:.03em; padding:8px 8px; border-bottom:1px solid var(--grid); }
tbody td { padding:9px 8px; border-bottom:1px solid var(--grid); vertical-align:middle; }
tbody tr:last-child td { border-bottom:none; }
tbody tr.total-row td { font-weight:800; border-top:2px solid var(--baseline); }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
td.num.neg { color:var(--critical); }
.units { color:var(--text-muted); font-size:10.5px; display:block; }
.table-scroll { overflow-x:auto; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }
.chart-grid { stroke:var(--grid); stroke-width:1; }
.chart-axis { font-size:10px; fill:var(--text-muted); text-anchor:middle; }
.chart-line { stroke:var(--series-1); stroke-width:2.5; }
.chart-line-prev { stroke:var(--text-muted); stroke-width:1.5; stroke-dasharray:3 3; }
.target-dashed { stroke:var(--series-3); stroke-width:1.5; stroke-dasharray:5 4; }
.target-dashed-line { stroke:var(--series-3); stroke-width:1.5; stroke-dasharray:5 4; }
.chart-dot { fill:var(--series-1); }
.chart-dot-peak { fill:var(--series-2); }
.chart-point-label { font-size:11px; fill:var(--text-secondary); text-anchor:middle; font-weight:600; }
.chart-point-label-peak { fill:var(--series-2); }
footer { margin-top:28px; font-size:11.5px; color:var(--text-muted); line-height:1.6; }
@media (max-width:900px) {
  .kpi-grid { grid-template-columns:repeat(2,1fr); }
  .two-col { grid-template-columns:1fr; }
  .alerts-grid { grid-template-columns:1fr; }
  .hbar-row { grid-template-columns:110px 1fr 110px; }
}
'''


def build_html(ctx):
    kpis = build_kpis(ctx["agg"], ctx["er_rows"], ctx["breakeven"], ctx["ytd_stats"], ctx["txs"])
    alerts_html = build_alerts_html(ctx["alerts"])

    dias_meses = [MES_CAP[MESES[m - 1]][:3] for m in sorted(ctx["agg"]["monthly"].keys())]
    vals_meses = [ctx["agg"]["monthly"][m] for m in sorted(ctx["agg"]["monthly"].keys())]
    monthly_chart = build_bar_chart(dias_meses, vals_meses, target=ctx["breakeven"]["venta_min_mes"])

    weeks_sorted = sorted(ctx["agg"]["weekly"].keys())
    week_labels = [ctx["agg"]["weekly_range"][wk][0].strftime("%d/%m") for wk in weeks_sorted]
    week_vals = [ctx["agg"]["weekly"][wk] for wk in weeks_sorted]
    weekly_chart = build_bar_chart(week_labels, week_vals, target=ctx["breakeven"]["venta_min_semana"], scrollable=True)

    daily_svg = build_daily_svg(ctx["agg"]["daily"], ctx["breakeven"]["venta_min_dia"])

    monthly_2025 = ctx["ventas_hist"].get("2025")
    ytd_svg = build_ytd_svg(ctx["agg"]["monthly"], monthly_2025, ctx["breakeven"]["venta_min_mes"])

    meses_emp = sorted(ctx["agg"]["monthly"].keys())
    emp_labels = [MES_CAP[MESES[m - 1]][:3] for m in meses_emp]
    yaneth_vals = [ctx["agg"]["emp_monthly"]["yaneth"].get(m, 0.0) for m in meses_emp]
    lina_vals = [ctx["agg"]["emp_monthly"]["lina"].get(m, 0.0) for m in meses_emp]
    emp_chart = build_grouped_bar_chart(emp_labels, yaneth_vals, lina_vals, "Yaneth", "Lina")
    total_yaneth = ctx["agg"]["emp_total"]["yaneth"]
    total_lina = ctx["agg"]["emp_total"]["lina"]
    total_emp = total_yaneth + total_lina or 1

    er_table = build_er_table(ctx["er_rows"])
    socios_monthly_2026 = {r["mes"]: abs(r["socios"]) for r in ctx["er_rows"]}
    historico = build_historico_html(ctx["ventas_hist"], ctx["utilidad_hist"], ctx["agg"]["monthly"], ctx["current_month"], socios_monthly_2026)

    ultimo_dia = sorted(ctx["agg"]["daily"].keys())[-1]

    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Las Super Empanadas</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="eyebrow">● Fuente: Dropbox · LAS SUPER / Caja LS 2026.xlsx</div>
    <h1>Las Super Empanadas — Dashboard de Ventas</h1>
    <p class="subtitle">Ventas, Estado de Resultados y comparativo histórico, calculados desde el libro diario de caja (hoja "Caja")</p>
    <p class="meta">
      Datos hasta: <code>{ultimo_dia.strftime('%d %b %Y').lower()}</code> ·
      Archivo modificado: <code>{ctx['source_modified']}</code> ·
      Generado: <code>{ctx['now']}</code>
    </p>
  </header>

  {kpis}

  {alerts_html}

  <section class="card">
    <h2>Ventas por día</h2>
    <p class="section-sub">Últimos {min(30, len(ctx["agg"]["daily"]))} días con venta registrada, vs. meta diaria de punto de equilibrio</p>
    {daily_svg}
  </section>

  <section class="card">
    <h2>Ventas por semana</h2>
    <p class="section-sub">Semana lunes–domingo · línea punteada: meta semanal aproximada de punto de equilibrio</p>
    {weekly_chart}
  </section>

  <section class="card">
    <h2>Ventas por mes (2026)</h2>
    <p class="section-sub">Línea punteada: meta mensual de punto de equilibrio ({money_short(ctx["breakeven"]["venta_min_mes"])})</p>
    {monthly_chart}
  </section>

  <section class="card">
    <h2>Ventas acumuladas del año</h2>
    <p class="section-sub">2026 (línea sólida) vs. ritmo de punto de equilibrio (punteada amarilla) vs. trayectoria completa de 2025 (punteada gris, para referencia)</p>
    {ytd_svg}
  </section>

  <section class="card">
    <h2>Ventas por empleada</h2>
    <p class="section-sub">Yaneth y Lina son quienes registran ventas en el mostrador · total del año: Yaneth {money_short(total_yaneth)} ({pct(total_yaneth,total_emp):.0f}%) · Lina {money_short(total_lina)} ({pct(total_lina,total_emp):.0f}%)</p>
    {emp_chart}
  </section>

  <section class="card">
    <h2>Estado de Resultados 2026 (mensual)</h2>
    <p class="section-sub">Calculado sumando el libro diario de caja por Centro de Costos · Retiros de socios se muestran aparte de la Utilidad Operativa, como reparto de utilidad</p>
    <div class="table-scroll">{er_table}</div>
  </section>

  {historico}

  <footer>
    Dashboard generado por el skill <code>las-super-dashboard</code> a partir del libro diario de caja
    (hoja "Caja") de <code>LAS SUPER/Caja LS 2026.xlsx</code> en Dropbox. Ventas 2026 = suma de todos los
    movimientos con Centro de Costos "venta", con su signo real (columna Valor) — no se usa la columna
    Entrada/Salida porque tiene errores de captura en esa categoría. Histórico 2020-2025 tomado de la hoja "Venta Mensual"
    (no existe libro diario detallado de esos años en este archivo). Punto de equilibrio y benchmarks
    tomados de las hojas "P.E" y "Análisis" del propio archivo. Esta es una foto fija al momento de la
    generación — para actualizarla, pide de nuevo que se corra el dashboard.
  </footer>
</div>
<script>
  // Barra de desplazamiento propia para los gráficos de barras que se
  // desplazan horizontalmente (ej. Ventas por semana): el scrollbar nativo
  // del navegador no es una señal confiable (varios navegadores/SO lo
  // ocultan por defecto), así que esta barra siempre visible lo reemplaza
  // — se sincroniza con el scroll nativo (trackpad, touch, teclado) y
  // además se puede arrastrar o hacer clic para saltar.
  document.querySelectorAll('.barchart-wrap-scroll').forEach(function (scrollEl) {{
    var ui = scrollEl.nextElementSibling;
    if (!ui || !ui.classList.contains('scrollbar-ui')) return;
    var track = ui.querySelector('.scrollbar-track');
    var thumb = ui.querySelector('.scrollbar-thumb');

    function sync() {{
      var maxScroll = scrollEl.scrollWidth - scrollEl.clientWidth;
      if (maxScroll <= 1) {{ ui.style.display = 'none'; return; }}
      ui.style.display = '';
      var thumbPct = Math.max(scrollEl.clientWidth / scrollEl.scrollWidth * 100, 8);
      thumb.style.width = thumbPct + '%';
      var travel = track.clientWidth - thumb.offsetWidth;
      var pos = travel > 0 ? (scrollEl.scrollLeft / maxScroll) * travel : 0;
      thumb.style.transform = 'translateX(' + pos + 'px)';
    }}

    function scrollToClientX(clientX) {{
      var rect = track.getBoundingClientRect();
      var travel = rect.width - thumb.offsetWidth;
      var pct = travel > 0 ? (clientX - rect.left - thumb.offsetWidth / 2) / travel : 0;
      pct = Math.min(1, Math.max(0, pct));
      scrollEl.scrollLeft = pct * (scrollEl.scrollWidth - scrollEl.clientWidth);
    }}

    scrollEl.addEventListener('scroll', sync);
    window.addEventListener('resize', sync);

    var dragging = false;
    thumb.addEventListener('pointerdown', function (e) {{
      dragging = true;
      thumb.setPointerCapture(e.pointerId);
      e.preventDefault();
    }});
    thumb.addEventListener('pointermove', function (e) {{
      if (dragging) scrollToClientX(e.clientX);
    }});
    thumb.addEventListener('pointerup', function () {{ dragging = false; }});
    track.addEventListener('pointerdown', function (e) {{
      if (e.target === thumb) return;
      scrollToClientX(e.clientX);
    }});

    scrollEl.scrollLeft = scrollEl.scrollWidth; // arranca mostrando lo más reciente
    sync();
  }});
</script>
</body>
</html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="Texto plano extraído del xlsx (campo .text de Dropbox fetch)")
    ap.add_argument("--html", required=True, help="Ruta de salida del dashboard HTML")
    ap.add_argument("--now", required=True, help="Timestamp ISO de generación (hora Bogotá)")
    ap.add_argument("--source-modified", required=True, help="server_modified del archivo en Dropbox")
    args = ap.parse_args()

    full_text = open(args.text, encoding="utf-8").read()
    lines = full_text.split("\n")

    caja_lines = slice_sheet(lines, "Caja", ["Costos"])
    venta_mensual_lines = slice_sheet(lines, "Venta Mensual", ["Venta Semanal"])

    txs = parse_caja(caja_lines)
    agg = aggregate_ventas(txs)
    er_rows = build_er(txs)
    ventas_hist, utilidad_hist = parse_historico(venta_mensual_lines)
    breakeven = parse_breakeven(full_text)
    alerts, ytd_stats = build_alerts(agg, er_rows, breakeven, txs)

    current_month = sorted(agg["daily"].keys())[-1].month

    ctx = dict(agg=agg, er_rows=er_rows, ventas_hist=ventas_hist, utilidad_hist=utilidad_hist,
               breakeven=breakeven, alerts=alerts, ytd_stats=ytd_stats, txs=txs,
               current_month=current_month, now=args.now, source_modified=args.source_modified)

    html = build_html(ctx)
    with open(args.html, "w", encoding="utf-8") as f:
        f.write(html)

    # ---- resumen para revisión antes de publicar ----
    print(f"Transacciones válidas parseadas (2026): {len(txs)}")
    print(f"Días con venta: {len(agg['daily'])}  |  Semanas: {len(agg['weekly'])}  |  Meses con datos: {len(er_rows)}")
    print(f"Punto de equilibrio: diario {money(breakeven['venta_min_dia'])} · semanal ~{money(breakeven['venta_min_semana'])} · mensual {money(breakeven['venta_min_mes'])}")
    print(f"Venta acumulada del año: {money(ytd_stats['ventas_ytd'])}")
    print(f"Utilidad operativa del año: {money(ytd_stats['utilidad_operativa_ytd'])} ({pct(ytd_stats['utilidad_operativa_ytd'], ytd_stats['ventas_ytd']):.1f}% margen)")
    print(f"Food cost del año: {ytd_stats['food_cost_pct']:.1f}%")
    print(f"Retiros de socios del año: {money(ytd_stats['retiros_ytd'])}")
    print("\nVentas por mes 2026:")
    for r in er_rows:
        print(f"  {MES_CAP[MESES[r['mes']-1]]:<12} {money(r['ventas']):>15}   Ut.Op {money(r['utilidad_operativa']):>15}   Flujo libre {money(r['flujo_libre']):>15}")
    print(f"\nVentas por empleada (año): Yaneth {money(agg['emp_total']['yaneth'])}  |  Lina {money(agg['emp_total']['lina'])}")
    print(f"\nAlertas generadas: {len(alerts)}")
    for a in alerts:
        print(f"  [{a['level'].upper()}] {a['title']}")
    print(f"\nHistórico de ventas por año (total anual, tal como quedó en el archivo):")
    for y in sorted(ventas_hist.keys()):
        vals = agg["monthly"] if y == "2026" else {i + 1: ventas_hist[y][i] for i in range(12)}
        total = sum((vals.get(m) or 0) for m in range(1, 13))
        print(f"  {y}: {money(total)}")
    print(f"\nHTML escrito en: {args.html}")


if __name__ == "__main__":
    main()
