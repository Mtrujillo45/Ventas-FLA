# Ventas FLA

Dashboards de rendimiento de campañas de Mompossina Swimwear, alimentados con datos de Shopify a través del conector de Composio.

## Dashboards

- [`dashboards/medellin-mi-amor.html`](dashboards/medellin-mi-amor.html) — Cápsula **Medellín Mi Amor** (colección `medellin-mi-amor`, 12 productos con tag `MEDELLIN`): ingresos, unidades, tendencia diaria, mezcla de clientes nuevos vs. recurrentes, canal de venta y cobertura de inventario por producto.
- [`dashboard/cierre-mensual.html`](dashboard/cierre-mensual.html) (también publicado como [`index.html`](index.html) para GitHub Pages) — **Cierre mensual de ventas**, todos los canales de Shopify: desglose financiero (subtotal, IVA y envío separados), ventas totales por día y top 20 productos por venta bruta. Solo venta real, sin proyección. Canal mayorista y World Office aparecen como capítulos pendientes hasta conectarse. Se regenera con el skill `.claude/skills/cierre-mensual/`.

Cada dashboard es una página HTML autocontenida (sin dependencias externas) que puede abrirse directamente en el navegador. Los datos son una foto fija tomada de la Admin API de Shopify (vía Composio) en el momento indicado en el encabezado de cada dashboard; para refrescarlos hay que volver a consultar Shopify y regenerar el archivo.

## Presupuesto de ventas 2026

- [`presupuesto-2026/plan-de-datos.md`](presupuesto-2026/plan-de-datos.md) — checklist de la información necesaria para construir el presupuesto de ventas 2026 (en $ y unidades, por canal: Punto de venta, Digital, Internacional, Nacional), los puntos de equilibrio y el cuadro de control de seguimiento mensual, incluyendo qué se puede alimentar desde Shopify y qué falta pedir a contabilidad/producción.
