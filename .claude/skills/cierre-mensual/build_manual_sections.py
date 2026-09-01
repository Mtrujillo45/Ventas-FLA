#!/usr/bin/env python3
"""Genera el HTML de las secciones nuevas (Tienda web recap, Showroom,
Socios comerciales, Consolidado) a partir de los JSON ya calculados, y
parcha dashboard/cierre-mensual.html insertándolas antes del footer.
NO hace aritmética nueva: solo formatea lo que ya calcularon
prep_inputs.py / compute.py (Shopify) y manual_invoices.py (facturas manuales).
"""
import json
import re

SCRATCH = "/tmp/claude-0/-home-user-Ventas-FLA/d8d7c767-218c-529c-a6c6-62c666190b4a/scratchpad/cierre-agosto"

with open(f"{SCRATCH}/august_aggregated.json", encoding="utf-8") as f:
    shopify = json.load(f)

with open(f"{SCRATCH}/manual_invoices_out.json", encoding="utf-8") as f:
    manual = json.load(f)

def money(n):
    return "${:,.0f}".format(round(float(n)))

# ---- Consolidado ----
tw_units, tw_neto, tw_iva, tw_envio, tw_total = (
    shopify["units"], shopify["net"], shopify["taxes"], shopify["shipping"], shopify["total"])
sc_units = manual["total_units"]
sc_neto = manual["total_neto_sin_iva"]
sc_iva = manual["total_iva"]
sc_envio = manual["total_envio"]
sc_total = manual["total_con_iva"] + manual["total_envio"]

cons_units = tw_units + sc_units
cons_neto = tw_neto + sc_neto
cons_iva = tw_iva + sc_iva
cons_envio = tw_envio + sc_envio
cons_total = tw_total + sc_total

# ---- Bloque: canales (tienda web recap + showroom pendiente + socios comerciales) ----
categories = [
    ("Mayoristas y retail — Colombia", [
        "Wanitta (Creemos que todo es posible S.A.S)",
        "Casa Viva (18 Razones S.A.S)",
        "Falabella de Colombia S.A.S",
        "Learia (Luz Andrea Ochoa Garcés)",
    ]),
    ("Exportaciones", [
        "Shop Greta SRL (exportación · Rep. Dominicana)",
        "Cristalina Swimwear (exportación · Miami, EE.UU.)",
        "Siete Mares CA (exportación · Valencia, Venezuela)",
    ]),
]
partner_order = [name for _, names in categories for name in names]

def render_partner(name, g):
    envio_note = f' · Envío {money(g["envio"])}' if g["envio"] else ""
    return f'''
    <div class="partner-block">
      <div class="partner-summary">
        <span class="partner-name">{name}</span>
        <span class="partner-figures">{money(g["neto_sin_iva"])}<span class="units">{g["units"]:,} uds · {len(g["docs"])} docs · IVA {money(g["iva"])}{envio_note}</span></span>
      </div>
    </div>'''

partner_rows = []
for cat_label, names in categories:
    partner_rows.append(f'<div class="partner-category">{cat_label}</div>')
    for name in names:
        partner_rows.append(render_partner(name, manual["socios"][name]))

channels_block = f'''  <section>
    <h2>Facturación por canal — Agosto 2026</h2>
    <p class="section-sub">Tienda web (Shopify) vs. Showroom vs. Socios comerciales (facturas/proformas manuales fuera de Shopify)</p>
    <div class="channel-grid">
      <div class="card channel-card">
        <div class="channel-badge channel-badge-live">● Shopify</div>
        <h3>Tienda web</h3>
        <p class="channel-desc">Tienda online + pedidos manuales/showroom vía app y POS de Shopify, combinados.</p>
        <div class="channel-kpis">
          <div><span class="ck-label">Unidades</span><span class="ck-value">{tw_units:,.0f}</span></div>
          <div><span class="ck-label">Venta neta (sin IVA)</span><span class="ck-value">{money(tw_neto)}</span></div>
          <div><span class="ck-label">IVA</span><span class="ck-value">{money(tw_iva)}</span></div>
          <div><span class="ck-label">Envío</span><span class="ck-value">{money(tw_envio)}</span></div>
        </div>
      </div>
      <div class="card channel-card">
        <div class="channel-badge channel-badge-pending">○ Sin datos este mes</div>
        <h3>Showroom</h3>
        <p class="channel-desc">Ventas directas a personas naturales fuera de Shopify (mostrador/showroom). De las facturas revisadas para agosto, ninguna correspondió a este canal — Learia se clasificó como socio comercial (precio mayorista) a pedido del usuario.</p>
        <div class="channel-kpis">
          <div><span class="ck-label">Unidades</span><span class="ck-value">0</span></div>
          <div><span class="ck-label">Venta neta (sin IVA)</span><span class="ck-value">$0</span></div>
        </div>
      </div>
      <div class="card channel-card channel-card-wide">
        <div class="channel-badge channel-badge-manual">◐ Carga manual (agosto)</div>
        <h3>Socios comerciales</h3>
        <p class="channel-desc">Facturas/proformas de mayoristas, retail y exportación, fuera de Shopify (sistema World Office). Cargadas manualmente para este cierre a partir de los documentos adjuntos por el usuario — <strong>no es todavía una conexión automática</strong>; falta definir cómo conectar este canal mes a mes.</p>
        <div class="channel-kpis channel-kpis-4">
          <div><span class="ck-label">Documentos</span><span class="ck-value">{sum(len(manual["socios"][p]["docs"]) for p in partner_order)}</span></div>
          <div><span class="ck-label">Unidades</span><span class="ck-value">{sc_units:,.0f}</span></div>
          <div><span class="ck-label">Venta neta (sin IVA)</span><span class="ck-value">{money(sc_neto)}</span></div>
          <div><span class="ck-label">IVA</span><span class="ck-value">{money(sc_iva)}</span></div>
          <div><span class="ck-label">Envío</span><span class="ck-value">{money(sc_envio)}</span></div>
        </div>
        <div class="partner-list">{"".join(partner_rows)}</div>
        <p class="channel-footnote">Mayoristas/retail nacional: IVA calculado dividiendo el total de cada proforma entre 1.19 (los totales de Wanitta/Casa Viva/Learia ya incluyen IVA, confirmado con el usuario); Falabella es factura electrónica DIAN formal, ya desglosada. La retención en la fuente que aparece en las proformas es informativa (anticipo de renta descontado por el comprador) y no se resta de la venta. Se excluyeron por ser de julio: proforma Ana Mercedes (31 jul) y las proformas Wanitta de julio (Jul25/Jul28/Jul30-31). Se excluyeron por ser pendientes/planeación, no facturas confirmadas: "Eterna Pendientes Julio31" y "Abanicos Pends Ago21" del archivo Wanitta.
        Exportaciones: facturas electrónicas DIAN en USD, convertidas a COP con la TRM del día que trae cada factura; 0% IVA por ser exportación exenta. Flete y seguro internacional se separan como envío (confirmado con el usuario). Cristalina (RFEL8279), Siete Mares (RFEL8289, RFEL8295) son honorarios de asesoría en diseño/patronaje, no unidades de producto — se suman a la venta neta a pedido del usuario, marcados como "servicio" en vez de unidades.</p>
      </div>
    </div>
  </section>'''

consolidado_block = f'''  <section class="card consolidado-card">
    <h2>Consolidado — Agosto 2026</h2>
    <p class="section-sub">Tienda web + Showroom + Socios comerciales. World Office (conciliación contable) sigue pendiente de conectar — no se incluye ni estima aquí.</p>
    <section class="kpi-grid">
      <div class="kpi kpi-highlight"><div class="label">Unidades totales</div><div class="value">{cons_units:,.0f}</div><div class="sub">Tienda web + socios comerciales</div></div>
      <div class="kpi kpi-highlight"><div class="label">Venta neta total (sin IVA)</div><div class="value">{money(cons_neto)}</div><div class="sub">Subtotal después de descuentos/devoluciones, antes de IVA y envío</div></div>
      <div class="kpi"><div class="label">IVA total</div><div class="value">{money(cons_iva)}</div><div class="sub">Impuesto cobrado en todos los canales</div></div>
      <div class="kpi"><div class="label">Envío total</div><div class="value">{money(cons_envio)}</div><div class="sub">Ingreso de envío, aparte del IVA — debe facturarse</div></div>
      <div class="kpi"><div class="label">Venta total con IVA y envío</div><div class="value">{money(cons_total)}</div><div class="sub">Lo cobrado a clientes en todos los canales</div></div>
    </section>
    <div class="consolidado-split">
      <div class="split-row"><span>Tienda web (Shopify)</span><span>{money(tw_neto)} <span class="split-pct">{tw_neto/cons_neto*100:.1f}%</span></span></div>
      <div class="split-row"><span>Socios comerciales</span><span>{money(sc_neto)} <span class="split-pct">{sc_neto/cons_neto*100:.1f}%</span></span></div>
      <div class="split-row"><span>Showroom</span><span>$0 <span class="split-pct">0.0%</span></span></div>
    </div>
  </section>'''

with open("dashboard/cierre-mensual.html", encoding="utf-8") as f:
    html = f.read()

if "MANUAL_CHANNELS_START" not in html:
    # Insertar antes de la sección de capítulos pendientes (World Office)
    anchor = '  <section>\n    <div class="two-col-pending">'
    insertion = (
        f'<!-- MANUAL_CHANNELS_START -->\n{channels_block}\n  <!-- MANUAL_CHANNELS_END -->\n\n'
        f'<!-- CONSOLIDADO_START -->\n{consolidado_block}\n  <!-- CONSOLIDADO_END -->\n\n'
    )
    assert anchor in html, "No se encontró el ancla de la sección de capítulos pendientes"
    html = html.replace(anchor, insertion + anchor, 1)
else:
    html = re.sub(r'<!-- MANUAL_CHANNELS_START -->.*?<!-- MANUAL_CHANNELS_END -->',
                   f'<!-- MANUAL_CHANNELS_START -->\n{channels_block}\n  <!-- MANUAL_CHANNELS_END -->', html, flags=re.S)
    html = re.sub(r'<!-- CONSOLIDADO_START -->.*?<!-- CONSOLIDADO_END -->',
                   f'<!-- CONSOLIDADO_START -->\n{consolidado_block}\n  <!-- CONSOLIDADO_END -->', html, flags=re.S)

# Quitar la sección "Top 20 productos por venta bruta" (a pedido del usuario)
html = re.sub(
    r'\n  <section class="card">\n    <h2>Top 20 productos por venta bruta</h2>.*?</section>\n',
    '\n', html, count=1, flags=re.S,
)

# Quitar la tarjeta "Canal mayorista" pendiente (ya no aplica: ahora se carga manualmente)
# y dejar la tarjeta de World Office como columna única.
html = html.replace(
    '''    <div class="two-col-pending">
      <div class="pending-card">
        <div class="pending-badge">Capítulo pendiente</div>
        <p><strong>Canal mayorista.</strong> Aún no está conectado a este informe. Falta definir el método de extracción: credenciales de acceso directo al sistema donde se registra, o archivo CSV de carga manual.</p>
        <p>En cuanto se defina la conexión, este canal se suma al consolidado con su propio desglose de ventas y unidades.</p>
      </div>
      <div class="pending-card">''',
    '''    <div class="two-col-pending two-col-pending-single">
      <div class="pending-card">'''
)

with open("dashboard/cierre-mensual.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Secciones insertadas en dashboard/cierre-mensual.html")
print(f"Consolidado: unidades={cons_units:,.0f} neto={money(cons_neto)} iva={money(cons_iva)} envio={money(cons_envio)} total={money(cons_total)}")
