---
name: magic-dashboard
description: "Genera y refresca el dashboard de ventas e inventario de la colección MAGIC de Mompossina (Shopify): pedidos, unidades por referencia y talla, inventario disponible, alertas de stock, ciudades de compra, fuente de tráfico y ticket promedio, más una sección de recompra/cohortes de toda la tienda. Mismo formato que LOVESSENCE. Republica el Artifact y la página pública (GitHub Pages). Usar siempre que el usuario pida: actualiza el dashboard de MAGIC, cómo va MAGIC, ventas de MAGIC, refresca MAGIC, inventario de MAGIC, o cuando se ejecute automáticamente por el scheduler."
---

## Qué hace

Recalcula y republica el **dashboard de MAGIC**, colección de Mompossina
publicada en Shopify el **30 de septiembre de 2026** (handle de colección
`magic`, id `gid://shopify/Collection/503551197423`). Es una réplica del
dashboard de LOVESSENCE (`.claude/skills/lovessence-dashboard/`): mismas
secciones, mismos marcadores en el HTML, misma lógica. Toda la aritmética la
hace **`compute.py`** (no el modelo).

Salidas que mantiene sincronizadas:
- **Artifact privado**: https://claude.ai/artifact/XcLXbT6vLwHo6seZLJbp64
  (reusar esta URL con `url:` en corridas siguientes desde otra conversación;
  omitir `icon` en redeploys)
- **Web pública (GitHub Pages)**: `dashboards/magic.html` →
  `https://mtrujillo45.github.io/Ventas-FLA/dashboards/magic.html` una vez
  fusionado a la rama por defecto. Ya tiene recuadro en `dashboards/index.html`.

## Decisiones confirmadas con el usuario (no cambiar sin re-confirmar)

- **Alcance de productos**: SOLO las 6 referencias nuevas con SKU `/MAG`
  (17 variantes). Los charms que también están en la colección y llevan el tag
  `MAGIC` — **Caribe Charm** (`caribe-charm-1`, de Colombia Drop) y
  **Medellín Mi Amor Primavera Charm** (`medellin-mi-amor-primavera-charm`) —
  quedan **fuera**: son de otras colecciones y mezclarían ventas.
  Handles incluidos:
  `magic-mesh-shirt`, `magic-strapless-top`, `magic-pareo`,
  `magic-one-shoulder-one-piece`, `magic-triangle-top`,
  `magic-strap-tie-side-bottom`.
  Si aparece un producto nuevo en la colección, preguntar antes de sumarlo.
- **Fecha de lanzamiento**: `since = 2026-09-30T00:00:00-05:00` (fecha de
  publicación en Shopify). Reportar siempre desde el lanzamiento, no ventana
  móvil.
- **Formato**: como LOVESSENCE, refrescable (no foto puntual como Medellín).
- **Recompra/cohortes**: el usuario pidió copiar la sección COMPLETA de
  cohortes de toda la tienda (igual a LOVESSENCE), etiquetada "Toda la
  tienda, no solo MAGIC". Si `lovessence-dashboard` corrió hace pocos días,
  se puede reusar su tabla de cohortes (parsear el bloque `COHORT` de
  `dashboards/lovessence.html`) en vez de repetir el bulk pull.
- **Paleta**: violeta `#7B52B8` (claro) / `#9A74D6` (oscuro) como color de
  la colección + azul `#2A78D6`/`#3987E5` como segundo color. Es
  **provisional**: no hay screenshots de la campaña MAGIC todavía. Si el
  usuario los envía, ajustar `--series-1` en los tres bloques de tokens.

## Procedimiento

Trabaja en `$SCRATCH/magic`.

**1. Pedidos desde el lanzamiento** (GraphQL vía Composio
`SHOPIFY_GRAPH_QL_QUERY`, cuenta `Mompossina`), paginando con `after`:

```graphql
orders(first: 100, after: $after, query: "created_at:>=2026-09-30T00:00:00-05:00", sortKey: CREATED_AT) {
  edges { node {
    id createdAt displayFinancialStatus test sourceName
    totalPriceSet { shopMoney { amount } }
    customer { id orders(first:1, sortKey:CREATED_AT) { edges { node { createdAt } } } }
    shippingAddress { city } billingAddress { city }
    customerJourneySummary { firstVisit { source } }
    lineItems(first: 30) { edges { node {
      quantity sku originalTotalSet { shopMoney { amount } }
      discountedTotalSet { shopMoney { amount } } product { handle title }
    } } }
  } }
  pageInfo { hasNextPage endCursor }
}
```

Filtra `test == false` y `displayFinancialStatus` en
{PAID, PARTIALLY_PAID, PARTIALLY_REFUNDED, REFUNDED}. Ese conjunto completo da
`orders_store` y `aov_store_order` (promedio de `totalPriceSet`). Los pedidos
con al menos una línea de los 6 handles son los pedidos MAGIC.

- **Ya era cliente vs. primera compra**: compara el `createdAt` del primer
  pedido del cliente con el del pedido MAGIC (si es anterior → ya era
  cliente). Es más robusto que `numberOfOrders > 1`, que marca como
  "existente" a quien compró MAGIC primero y volvió después.
- **Ciudades**: `shippingAddress.city` con fallback a `billingAddress.city`;
  normaliza variantes (Bogota / Bogotá D.C. / Usaquén → Bogotá; Medellin →
  Medellín) y agrupa las ciudades con 1 pedido en "Otras N ciudades". Sin
  ciudad → "Sin ciudad registrada".
- **Tráfico**: `firstVisit.source`; `sourceName == "shopify_draft_order"` →
  "Pedido manual (sin recorrido web)"; "an unknown source" o sin journey →
  "Fuente desconocida"; "direct" → "Directo".

**2. Inventario fresco**, justo antes de publicar:
```graphql
collection(id: "gid://shopify/Collection/503551197423") {
  products(first: 20) { edges { node { handle title
    variants(first: 10) { edges { node { sku title inventoryQuantity price } } } } } }
}
```
Ignora los dos charms. Arma `skus.json` con las 17 variantes (incluye las que
tengan 0 ventas).

**3. Cohortes**: ver "Decisiones" arriba (reusar las de LOVESSENCE si son
recientes; si no, seguir el paso 5 del SKILL de LOVESSENCE). Actualizar el
`flag` de la cohorte del mes en curso.

**4. Calcular y parchear:**
```
python3 .claude/skills/magic-dashboard/compute.py \
  --skus $SCRATCH/magic/skus.json --kpis $SCRATCH/magic/kpis.json \
  --cities $SCRATCH/magic/cities.json --traffic $SCRATCH/magic/traffic.json \
  --cohort $SCRATCH/magic/cohort.json --html dashboards/magic.html \
  --now "<hora ISO Bogotá>" --label "30 sep – <hoy> (desde el lanzamiento)"
```
Formato de cada JSON en el docstring de `compute.py` (las claves de KPIs son
`orders_magic` y `aov_magic_order`). Verifica que unidades por talla sumen el
total y que nuevos + existentes + sin cuenta = pedidos MAGIC.

**5. Screenshot** claro/oscuro y a 390px de ancho con Playwright
(`/opt/pw-browsers/chromium`, `NODE_PATH=$(npm root -g)`); el ancho de la
página no debe pasar de 390px.

**6. Republicar el Artifact** (misma URL) y **commit + push** de
`dashboards/magic.html`; si la rama no es la por defecto, ofrecer un PR.

**7. Reportar**: pedidos, unidades, ingresos, % de la tienda, tallas en
crítico/sin stock, referencia #1, ciudad #1 y mezcla nuevos vs. existentes.

## Notas

- Las alertas son por stock absoluto (umbrales en `compute.py`). Con 2–3
  semanas de historial se puede añadir cobertura por velocidad, sin quitar el
  umbral absoluto.
- Solo Shopify (online + pedidos manuales); no inventar datos de mayoristas.
