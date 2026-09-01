#!/usr/bin/env python3
"""Cómputo de las facturas/proformas manuales de agosto 2026 (fuera de Shopify,
canal socios comerciales), extraídas de los xlsx/pdf adjuntos.

Reglas confirmadas con el usuario:
- LEARIA se clasifica como socio comercial (no showroom).
- El TOTAL/SUBTOTAL de las proformas Wanitta/Casa Viva/Learia YA incluye IVA
  -> se divide entre 1.19 para dejar la venta neta sin IVA (misma convención
  que ya usa monitor-medellin / el fallback de Shopify de este mismo skill).
- Falabella es una factura electrónica DIAN formal que YA trae el desglose
  subtotal/IVA por separado -> se usa tal cual, sin dividir.
- RETENCIÓN es retención en la fuente (anticipo de renta descontado por el
  comprador al pagar) -> NO se resta de la venta; es solo informativa/de
  flujo de caja, no reduce el ingreso reconocido.
- Se excluyen 'ETERNA PENDIENTES JULIO31' y 'ABANICOS PENDS AGO21' (Wanitta):
  son pestañas de planeación/pendientes, no facturas nuevas confirmadas.
- Se excluye PROFORMA_ANAMERCEDES (fechada 31 de julio, fuera de agosto).

Segunda tanda (facturas de exportación, RFEL/World Office, USD -> COP con la
TRM del día que trae cada factura, IVA 0% por ser exportación exenta):
- Flete y seguro internacional se separan como "envío" (confirmado con el
  usuario), igual que ya se hacía con Casa Viva.
- Las facturas de "Asesoría en diseño/patronaje" (Cristalina, Siete Mares)
  son honorarios de consultoría, no unidades de producto -> unidades=0 en
  esos documentos, pero su valor SÍ se suma a la venta neta (confirmado con
  el usuario).
- Van 5 de ~8 facturas de exportación; 3 más quedan pendientes de una
  próxima carga del usuario.
"""
import json

IVA_DIVISOR = 1.19

def con_iva(total_incl_iva):
    neto = total_incl_iva / IVA_DIVISOR
    iva = total_incl_iva - neto
    return neto, iva

def export_doc(doc, fecha, units, total_cop, envio_cop=0, kind="producto"):
    """Factura de exportación: TOTAL FACTURA COP ya viene convertido con la TRM
    del día por World Office; IVA 0% (exportación exenta); el envío (flete +
    seguro internacional) se resta del total para dejarlo aparte.
    Convención de 'total_con_iva' en todo este script: valor de PRODUCTO/SERVICIO
    con IVA, SIN envío (igual que Casa Viva) — el envío se suma aparte una sola
    vez al construir el consolidado, nunca dentro de total_con_iva."""
    neto = total_cop - envio_cop
    return {
        "doc": doc, "fecha": fecha, "units": units, "kind": kind,
        "neto_sin_iva": neto, "iva": 0.0,
        "total_con_iva": neto, "envio": envio_cop,
    }

wanitta = [
    {"doc": "RFEL8231", "fecha": "2026-08-03", "units": 95,  "total_incl_iva": 7_428_300},
    {"doc": "RFEL8237", "fecha": "2026-08-05", "units": 137, "total_incl_iva": 10_555_620},
    {"doc": "RFEL8245", "fecha": "2026-08-10", "units": 173, "total_incl_iva": 13_039_420},
    {"doc": "s/n",      "fecha": "2026-08-26", "units": 112, "total_incl_iva": 7_030_780},
]

casaviva = [
    {"doc": "RFEL8230", "fecha": "2026-08-03", "units": 108, "total_incl_iva": 9_442_440,  "envio": 0},
    {"doc": "RFEL8246", "fecha": "2026-08-05", "units": 44,  "total_incl_iva": 4_805_920,  "envio": 0},
    {"doc": "RFEL8247", "fecha": "2026-08-08", "units": 148, "total_incl_iva": 13_457_640, "envio": 0},
    {"doc": "RFEL8260", "fecha": "2026-08-12", "units": 26,  "total_incl_iva": 2_378_180,  "envio": 0},
    {"doc": "RFEL8261", "fecha": "2026-08-18", "units": 24,  "total_incl_iva": 2_252_320,  "envio": 0},
    {"doc": "RFEL8267", "fecha": "2026-08-20", "units": 6,   "total_incl_iva": 965_580,    "envio": 44_997},
    {"doc": "RFEL8281", "fecha": "2026-08-21", "units": 12,  "total_incl_iva": 839_160,    "envio": 0},
    {"doc": "RFEL8282", "fecha": "2026-08-25", "units": 58,  "total_incl_iva": 5_046_440,  "envio": 0},
]

learia = [
    {"doc": "s/n", "fecha": "2026-08-05", "units": 16, "total_incl_iva": 1_419_880},
]

falabella = [
    {"doc": "RFEL8257", "fecha": "2026-08-18", "units": 121,
     "subtotal_sin_iva": 8_900_676, "iva": 1_691_128, "total": 10_591_804},
]

# --- Exportaciones (segunda tanda, 5 de ~8 facturas) ---
# TOTAL FACTURA COP se divide proporcionalmente entre producto y envío
# (flete + seguro) usando el peso de cada uno en USD dentro de la misma
# factura -> evita reconvertir a mano con la TRM y no deja residuo de
# redondeo (producto_cop + envio_cop = TOTAL FACTURA COP exacto).
def split_cop(total_cop, product_usd, envio_usd):
    total_usd = product_usd + envio_usd
    envio_cop = round(total_cop * envio_usd / total_usd)
    return total_cop - envio_cop, envio_cop

_greta8275_envio = split_cop(1_168_657, 374.85, 7.50)[1]
_greta8273_envio = split_cop(5_024_826, 1_623.50, 25.00)[1]
shop_greta = [
    export_doc("RFEL8275", "2026-08-25", 9, 1_168_657, envio_cop=_greta8275_envio),
    export_doc("RFEL8273", "2026-08-24", 54, 5_024_826, envio_cop=_greta8273_envio),
]

_cristalina8269_envio = split_cop(3_061_735, 899.60, 100.00)[1]
_cristalina8276_envio = split_cop(3_056_296, 899.93, 100.00)[1]
_cristalina8298_envio = split_cop(2_673_456, 750.26, 100.00)[1]
cristalina = [
    export_doc("RFEL8269", "2026-08-21", 260, 3_061_735, envio_cop=_cristalina8269_envio),
    export_doc("RFEL8279", "2026-08-26", 0, 54_566_253, kind="servicio"),
    export_doc("RFEL8276", "2026-08-25", 243, 3_056_296, envio_cop=_cristalina8276_envio),
    export_doc("RFEL8298", "2026-08-28", 162, 2_673_456, envio_cop=_cristalina8298_envio),
]

siete_mares = [
    export_doc("RFEL8289", "2026-08-26", 0, 7_731_748, kind="servicio"),
    export_doc("RFEL8295", "2026-08-27", 0, 6_068_095, kind="servicio"),
]

def compute_group(rows, key="total_incl_iva"):
    for r in rows:
        neto, iva = con_iva(r[key])
        r["neto_sin_iva"] = neto
        r["iva"] = iva
        r["total_con_iva"] = r[key]
    return {
        "docs": rows,
        "units": sum(r["units"] for r in rows),
        "neto_sin_iva": sum(r["neto_sin_iva"] for r in rows),
        "iva": sum(r["iva"] for r in rows),
        "total_con_iva": sum(r["total_con_iva"] for r in rows),
        "envio": sum(r.get("envio", 0) for r in rows),
    }

def compute_group_raw(rows):
    """Para docs que ya traen neto_sin_iva/iva/total_con_iva/envio calculados
    (facturas de exportación: export_doc() ya hizo la aritmética)."""
    return {
        "docs": rows,
        "units": sum(r["units"] for r in rows),
        "neto_sin_iva": sum(r["neto_sin_iva"] for r in rows),
        "iva": sum(r["iva"] for r in rows),
        "total_con_iva": sum(r["total_con_iva"] for r in rows),
        "envio": sum(r.get("envio", 0) for r in rows),
    }

g_wanitta = compute_group(wanitta)
g_casaviva = compute_group(casaviva)
g_learia = compute_group(learia)
g_shopgreta = compute_group_raw(shop_greta)
g_cristalina = compute_group_raw(cristalina)
g_sietemares = compute_group_raw(siete_mares)

# Falabella ya viene desglosada
for r in falabella:
    r["neto_sin_iva"] = r["subtotal_sin_iva"]
g_falabella = {
    "docs": falabella,
    "units": sum(r["units"] for r in falabella),
    "neto_sin_iva": sum(r["subtotal_sin_iva"] for r in falabella),
    "iva": sum(r["iva"] for r in falabella),
    "total_con_iva": sum(r["total"] for r in falabella),
    "envio": 0,
}

socios = {
    "Wanitta (Creemos que todo es posible S.A.S)": g_wanitta,
    "Casa Viva (18 Razones S.A.S)": g_casaviva,
    "Falabella de Colombia S.A.S": g_falabella,
    "Learia (Luz Andrea Ochoa Garcés)": g_learia,
    "Shop Greta SRL (exportación · Rep. Dominicana)": g_shopgreta,
    "Cristalina Swimwear (exportación · Miami, EE.UU.)": g_cristalina,
    "Siete Mares CA (exportación · Valencia, Venezuela)": g_sietemares,
}

total_units = sum(g["units"] for g in socios.values())
total_neto = sum(g["neto_sin_iva"] for g in socios.values())
total_iva = sum(g["iva"] for g in socios.values())
total_envio = sum(g["envio"] for g in socios.values())
total_con_iva = sum(g["total_con_iva"] for g in socios.values())

print("=== SOCIOS COMERCIALES — AGOSTO 2026 ===")
for name, g in socios.items():
    print(f"\n{name}: {len(g['docs'])} documentos, {g['units']} unidades")
    print(f"  Neto sin IVA: ${g['neto_sin_iva']:,.0f}  IVA: ${g['iva']:,.0f}  "
          f"Envío: ${g['envio']:,.0f}  Total c/IVA: ${g['total_con_iva']:,.0f}")
    for r in g["docs"]:
        print(f"    {r['doc']:>10} {r['fecha']}  {r['units']:>4} uds  "
              f"neto ${r['neto_sin_iva']:,.0f}  iva ${r['iva']:,.0f}")

print(f"\n--- TOTAL SOCIOS COMERCIALES ---")
print(f"Documentos: {sum(len(g['docs']) for g in socios.values())}")
print(f"Unidades: {total_units}")
print(f"Neto sin IVA: ${total_neto:,.0f}")
print(f"IVA: ${total_iva:,.0f}")
print(f"Envío: ${total_envio:,.0f}")
print(f"Total con IVA (+envío): ${total_con_iva + total_envio:,.0f}")

# Control: neto + iva debe igualar total_con_iva por grupo (envío aparte,
# nunca mezclado dentro de total_con_iva) -- si algo no cuadra, se arregla
# aquí, no en el HTML.
for name, g in socios.items():
    lhs = round(g["neto_sin_iva"] + g["iva"])
    rhs = round(g["total_con_iva"])
    assert lhs == rhs, f"Descuadre en {name}: neto+iva={lhs} vs total_con_iva={rhs}"
print("\nControl OK: neto + IVA == total_con_iva en los 7 grupos (envío separado, sin doble conteo).")

out = {
    "socios": socios,
    "total_units": total_units,
    "total_neto_sin_iva": total_neto,
    "total_iva": total_iva,
    "total_envio": total_envio,
    "total_con_iva": total_con_iva,
}
with open("manual_invoices_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nGuardado manual_invoices_out.json")
