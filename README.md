# Ventas FLA

Dashboards de rendimiento de campañas de Mompossina Swimwear, alimentados con datos de Shopify a través del conector de Composio.

## Dashboards

- [`dashboards/medellin-mi-amor.html`](dashboards/medellin-mi-amor.html) — Cápsula **Medellín Mi Amor** (colección `medellin-mi-amor`, 12 productos con tag `MEDELLIN`): ingresos, unidades, tendencia diaria, mezcla de clientes nuevos vs. recurrentes, canal de venta y cobertura de inventario por producto.

Cada dashboard es una página HTML autocontenida (sin dependencias externas) que puede abrirse directamente en el navegador. Los datos son una foto fija tomada de la Admin API de Shopify (vía Composio) en el momento indicado en el encabezado de cada dashboard; para refrescarlos hay que volver a consultar Shopify y regenerar el archivo.
