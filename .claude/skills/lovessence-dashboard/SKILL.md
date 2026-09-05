---
name: lovessence-dashboard
description: "Genera y refresca el dashboard de ventas e inventario de la colección LOVESSENCE de Mompossina (Shopify): pedidos, unidades por referencia y talla, inventario disponible, alertas de stock, ciudades de compra, fuente de tráfico y ticket promedio, más una sección de recompra/cohortes de toda la tienda. Republica el Artifact y la página pública (GitHub Pages). Usar siempre que el usuario pida: actualiza el dashboard de LOVESSENCE, cómo va LOVESSENCE, ventas de LOVESSENCE, refresca LOVESSENCE, inventario de LOVESSENCE, o cuando se ejecute automáticamente por el scheduler."
---

## Qué hace

Recalcula y republica el **dashboard de LOVESSENCE**, la colección permanente de
Mompossina lanzada el **4 de septiembre de 2026** (handle de colección
`lovessence`, tag de producto `LOVESSENCE`, 13 productos / 40 variantes —
incluye el pin "Love For Colombia" como accesorio de la cápsula, confirmado
con el usuario). Toda la aritmética la hace **`compute.py`** (no el modelo),
mismo principio que `cierre-mensual` y `monitor-medellin`.

A diferencia de Medellín (cápsula corta) y de cierre-mensual (informe puntual),
LOVESSENCE es una **colección permanente**: este dashboard está pensado para
refrescarse periódicamente, no como una foto de una sola vez.

Salidas que mantiene sincronizadas:
- **Artifact privado**: https://claude.ai/code/artifact/59f06194-b611-43f4-a78d-e7f5294a0652
  (reusar esta URL en corridas siguientes con `url:` para actualizar el mismo
  link en vez de crear uno nuevo)
- **Web pública (GitHub Pages)**: `dashboards/lovessence.html` dentro de
  `mtrujillo45/ventas-fla` → una vez fusionado a la rama por defecto del repo,
  `https://mtrujillo45.github.io/Ventas-FLA/dashboards/lovessence.html`

## Decisiones confirmadas con el usuario (no cambiar sin re-confirmar)

- **Alcance**: desde el lanzamiento (2026-09-04) hasta hoy. En corridas
  futuras, mantener "desde el lanzamiento" como el `since` por defecto (no
  una ventana móvil) — la colección es permanente pero el dashboard reporta
  su vida completa, igual que Medellín.
- **Pin "Love For Colombia"**: SÍ se incluye en ventas/inventario de la
  cápsula (está en la colección y el tag, aunque es un accesorio económico
  de alto volumen — 450 unidades iniciales). No excluirlo de `skus.json`.
- **Alertas de inventario**: por **stock absoluto**, no por velocidad de
  venta (ver umbrales en el docstring de `compute.py`). Cuando la colección
  acumule ~2–3 semanas de historial real, considerar agregar una segunda
  columna de cobertura estimada (stock ÷ velocidad diaria) como en Medellín
  — no reemplazar el umbral absoluto, complementarlo.
- **Recompra/cohortes**: el usuario pidió específicamente que esta sección
  mida **recompra general de la tienda** (¿cuántos compradores de LOVESSENCE
  ya eran clientes antes?, más una vista de cohortes mensuales de TODA la
  tienda), no recompra dentro de la misma colección. Se muestra como sección
  aparte, etiquetada "toda la tienda, no solo LOVESSENCE".
- **Mayo–junio 2026**: pico real de ~10x en pedidos por la campaña de la
  colección **"Colombia"** (confirmado por el usuario, no es ruido). Esos
  meses y julio (cola) deben seguir marcados con la nota de campaña en
  `cohort.json` — no borrar el flag aunque pase el tiempo, es contexto
  histórico permanente de esa cohorte.
- **Paleta**: tomada visualmente de screenshots del home y el banner
  "NEW DROP LOVESSENCE" de mompossina.com que el usuario envió por chat
  (rosa `#C9576A` como color de marca, azul `#2A78D6`/`#3987E5` del ribete
  como segundo color categórico — ambos ya pasan el validador de paleta de
  `dataviz`). El conector de Shopify **no tiene el scope `read_themes`**, así
  que no se puede leer la paleta del tema vía API; si se necesita refinar,
  pedir screenshots nuevos en vez de intentar acceder al tema.

## Datos de referencia

| Concepto | Valor |
|---|---|
| Colección | handle `lovessence`, tag `LOVESSENCE`, 13 productos / 40 variantes |
| Moneda | COP, `taxesIncluded: true` |
| Zona horaria de la tienda | America/Bogota |
| ShopifyQL | Confirmado funcionando en esta tienda/sesión (`shopifyqlQuery`) |
| Historial de pedidos de la tienda | Desde marzo 2021 (33,194 pedidos a sep 2026) |

## Procedimiento

Trabaja en un directorio temporal del scratchpad (p. ej. `$SCRATCH/lovessence`).

**1. Reconfirmar el rango.** Por defecto `since = 2026-09-04T00:00:00-05:00`
(lanzamiento) hasta el momento de la corrida. Si el usuario pide otra ventana,
úsala, pero el KPI "unidades/ingresos" siempre debe aclarar qué ventana cubre
en el `<label>` que se le pasa a `compute.py`.

**2. Traer ventas de LOVESSENCE.** No hay un filtro directo por colección en
ShopifyQL, así que se usa GraphQL Admin API vía Composio
(`SHOPIFY_GRAPH_QL_QUERY`, cuenta `Mompossina`):

```graphql
orders(first: 100, query: "created_at:>=<SINCE>", sortKey: CREATED_AT) {
  edges { node {
    id createdAt displayFinancialStatus test sourceName
    customer { id numberOfOrders }
    shippingAddress { city } billingAddress { city }
    customerJourneySummary { firstVisit { source utmParameters { source } } }
    lineItems(first: 20) { edges { node {
      quantity sku variantTitle originalTotalSet { shopMoney { amount } }
      discountedTotalSet { shopMoney { amount } }
      product { handle title }
    } } }
  } }
  pageInfo { hasNextPage endCursor }
}
```

Pagina con `pageInfo`/`after` si `hasNextPage` es true. Filtra a
`test == false` y `displayFinancialStatus` en
{PAID, PARTIALLY_PAID, PARTIALLY_REFUNDED, REFUNDED}. Une los line items cuyo
`product.handle` esté entre los 13 handles de LOVESSENCE (ver lista completa
en el primer commit de este skill o pedirla de nuevo con
`collectionByHandle(handle:"lovessence")`).

Con eso arma `skus.json` (agregando unidades/ingresos por SKU) y las piezas de
`kpis.json` (`orders_lovessence`, `customers_new/existing/noaccount` a partir
de `numberOfOrders`), `cities.json` (agrupando `shippingAddress.city`, con
fallback a `billingAddress.city`) y `traffic.json` (agrupando
`customerJourneySummary.firstVisit.source`, con "Pedido manual" para
`sourceName == "shopify_draft_order"` que no trae journey).

**3. Inventario fresco.** Un solo query, SIEMPRE justo antes de publicar (no
reusar un inventario de horas atrás):

```graphql
collection(id: "gid://shopify/Collection/501411676399") {
  products(first: 20) { edges { node {
    handle title status
    variants(first: 10) { edges { node { sku title inventoryQuantity price } } }
  } } }
}
```

`inventoryQuantity` en la variante ya es "available" (neto de lo comprometido
por pedidos abiertos) — no hace falta restarle nada.

**4. Store-wide: pedidos totales del mismo período** (para el % que
representa LOVESSENCE) con `FROM sales SHOW orders, total_sales SINCE <since>
UNTIL today` vía ShopifyQL, y el AOV general de la tienda en la misma ventana.

**5. Cohortes (toda la tienda).** Esto es pesado (>30k pedidos de historia) —
usar `SHOPIFY_BULK_QUERY_OPERATION` para traer `id, createdAt,
displayFinancialStatus, test, customer { id }` de TODA la historia de
pedidos, filtrar igual que el paso 2, y en Python (workbench o bash local)
asignar cada cliente a la cohorte del mes de su primer pedido calificado (en
hora Bogotá), y calcular recompra a 30/60/90 días por cohorte. Recorta la
tabla final a los últimos ~12 meses de cohortes para que sea legible, pero
usa la historia COMPLETA para determinar quién es "nuevo" (si no, se
clasifican mal clientes antiguos). Esto no cambia seguido — si ya corriste
esto en los últimos días, puedes reusar `cohort.json` de la corrida anterior
y solo actualizar las cohortes más recientes en vez de repetir el bulk pull
completo cada vez.

**6. Calcular y parchear el dashboard:**
```
python3 .claude/skills/lovessence-dashboard/compute.py \
  --skus $SCRATCH/lovessence/skus.json \
  --kpis $SCRATCH/lovessence/kpis.json \
  --cities $SCRATCH/lovessence/cities.json \
  --traffic $SCRATCH/lovessence/traffic.json \
  --cohort $SCRATCH/lovessence/cohort.json \
  --html dashboards/lovessence.html \
  --now "<hora ISO Bogotá>" \
  --label "<rango legible del período>"
```
Revisa el resumen impreso. Si algo se ve fuera de lugar (unidades por talla
que no cuadran con la suma total, % de clientes que no suma 100, etc.), no
publiques — revisa los JSON de entrada.

**7. Screenshot antes de publicar.** Renderiza `dashboards/lovessence.html`
con Playwright/Chromium (`/opt/pw-browsers/chromium`, con
`NODE_PATH=$(npm root -g)` si `playwright` no está en el proyecto) en modo
claro y oscuro, y revisa que las tablas/badges/cohortes se vean bien antes de
republicar — es una página densa en datos, un marcador roto o una columna
desalineada no se nota solo leyendo el HTML.

**8. Republicar el Artifact** con la herramienta Artifact:
- `file_path`: `dashboards/lovessence.html`
- `url`: `https://claude.ai/code/artifact/59f06194-b611-43f4-a78d-e7f5294a0652`
- `favicon`: omitir en redeploys (ya quedó fijado como 💗 en la primera
  publicación)

**9. Publicar/actualizar como página pública (GitHub Pages)**, dentro de
`ventas-fla`:
```
git add dashboards/lovessence.html
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "Actualizar dashboard de LOVESSENCE (<fecha>)"
git push origin <rama de trabajo>   # reintenta con backoff si falla
```
Si el trabajo se hizo en una rama distinta a la rama por defecto del repo,
avisar al usuario y ofrecer abrir un Pull Request hacia la rama por
defecto — el link público de GitHub Pages solo queda "vivo" ahí una vez
fusionado (no crear el PR sin que el usuario lo pida explícitamente, salvo
que ya haya autorizado ese flujo antes).

**10. Reportar** en el chat: pedidos, unidades, ingresos, % de la tienda,
tallas sin inventario/en crítico, ciudad #1, y la tasa de recompra histórica
de la tienda.

## Notas

- **No es cobertura por velocidad todavía**: con 1-3 días de historial la
  velocidad de venta es demasiado ruidosa para estimar "cobertura en días"
  por SKU de forma confiable — por eso las alertas usan stock absoluto. Una
  vez haya ~2-3 semanas de datos, se puede agregar esa columna (mismo cálculo
  que Medellín: stock ÷ velocidad diaria observada) sin quitar el umbral
  absoluto.
- **Ciudades con 1 solo pedido**: para no inflar la tabla con filas de bajo
  valor informativo, se agrupan en una fila "Otras N ciudades" — solo
  desagregar si el usuario pide el detalle completo.
- **No inventar datos de mayorista/World Office ni de canal**: este dashboard
  cubre únicamente Shopify (tienda online + manual/showroom), igual que el
  resto de dashboards del repo.
- **Scope de Shopify sin `read_themes`**: no se puede leer la paleta de la
  tienda desde la API; si hace falta ajustar colores de marca, pedir
  screenshots en vez de intentar el theme API de nuevo.
