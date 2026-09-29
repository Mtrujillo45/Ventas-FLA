---
name: presupuesto-vs-real
description: "Refresca el dashboard de Presupuesto vs. Real de Mompossina: venta neta y unidades del mes en curso frente a la meta del Plan Estratégico 2026-2027, por canal (Online, Showroom, Mayoristas nacionales, Mayoristas internacionales) — cumplimiento, ritmo diario, proyección de cierre de mes, acumulado del periodo Sep-Dic y semáforo de alertas. Republica el Artifact y la página pública (GitHub Pages). Usar siempre que el usuario pida: actualiza el presupuesto vs real, cómo vamos vs. la meta, cumplimiento de ventas, cómo va el mes vs. el plan, refresca el dashboard de presupuesto, o cuando se ejecute automáticamente por el scheduler."
---

## Qué hace

Recalcula y republica el dashboard **Presupuesto vs. Real**. Toda la
aritmética vive en **`compute.py`** (no el modelo) — mismo principio que
`cierre-mensual` y `lovessence-dashboard`: el script arma el objeto `DATA`
completo y parchea `dashboards/presupuesto-vs-real.html` entre los
marcadores `<!-- DATA_START -->`/`<!-- DATA_END -->` (más
`<!-- RUNRATE_SVG_START -->`/`<!-- RUNRATE_SVG_END -->` para el gráfico de
ritmo diario, que también genera en Python como SVG inline — sin
dependencias externas, nada de Chart.js). Todo lo cuantitativo del HTML (KPIs,
barras de cumplimiento, ticket promedio, proyecciones, semáforo, tablas) se
renderiza client-side por JS a partir de ese único objeto `DATA`.

Lo único que se edita a mano en cada corrida es la **narrativa**: el bloque
"Resumen ejecutivo" (`<ul class="exec-list">`), la nota de mayoristas y el
footer — informado por el resumen que `compute.py` imprime en stdout. Eso es
interpretación, no aritmética.

Salidas que mantiene sincronizadas:
- **Artifact privado**: https://claude.ai/artifact/GLPEPUuAWn1C6FoPSB8JrN
  (reusar esta URL con `url:` en corridas siguientes)
- **Web pública (GitHub Pages)**: `dashboards/presupuesto-vs-real.html` dentro
  de `mtrujillo45/ventas-fla` → una vez fusionado a la rama por defecto del
  repo (`claude/medellin-dashboard-composio-shopify-9b1mlm`, confirmar con
  `git remote show origin` si cambia), queda en
  `https://mtrujillo45.github.io/Ventas-FLA/dashboards/presupuesto-vs-real.html`

## Regla de clasificación Online vs. Showroom (confirmada 2026-09-07 — no cambiar sin re-confirmar)

El usuario reportó que ventas de showroom conocidas (ej. $2.5M, $1.1M y dos de
$269K el 7-sep-2026) no aparecían en el canal Showroom. Investigado en
Shopify: **NO es un campo mal leído**, es que el tag `SHOWROOM` se aplica
manualmente al crear el pedido y con frecuencia se omite — 2 de esas 4
ventas no lo tenían, incluida la más grande del día.

Se probó `staffMember` (quién creó el pedido) como alternativa — bloqueado
por Shopify: requiere scope `read_users` y tienda Plus/Advanced o app
"finance embedded", no disponible en esta conexión. `retailLocation`
igual de bloqueado (`read_locations`). `app.name` y `sourceIdentifier` no
distinguen (todos los pedidos manuales vienen de la app "Draft Orders").

Patrón que SÍ es 100% consistente, verificado sobre ~150 pedidos de
muestra (25-ago a 7-sep-2026): toda venta manual por WhatsApp/Instagram
lleva **siempre** el tag `REDES SOCIALES` (y casi siempre también `Melonn`/
`Melonn-Entregado`), sin una sola excepción — mientras que las ventas de
showroom (pago con Bold/QR/efectivo/transferencia en el local) casi nunca
llevan tag. Regla implementada en `classify_shopify_order()`:

```
tags contiene "falabella" (marketplace de Falabella
  sincronizado a Shopify, sourceName propio tipo
  "3441759", casi siempre también trae tag "B2C")  -> Mayoristas nacionales
  (NO Online — ver corrección 2026-09-27 abajo)
sourceName == "web"                              -> Online
sourceName == "shopify_draft_order":
  tags contiene "redes sociales"/"melonn"/
  "melonn-entregado"                              -> Online (Redes propias)
  si no                                           -> Showroom
cualquier otro sourceName (otro marketplace
  sincronizado)                                   -> Online
pedido test, financial status fuera de {PAID,
  PARTIALLY_PAID, PARTIALLY_REFUNDED, REFUNDED},
  o valor $0 (saldo de bono, regalo, pago UGC)     -> excluido
```

**No usar `tags contains SHOWROOM`** como filtro — es la causa raíz del bug
reportado. Si en el futuro Shopify habilita `staffMember`/`retailLocation`
para esta cuenta, sería una señal más limpia — reevaluar en ese momento,
pero no es necesario mientras el patrón de tags siga siendo consistente.

**Corrección 2026-09-27 — pedidos de Falabella NO son Online.** El usuario
detectó que el marketplace de Falabella sincroniza sus pedidos a Shopify
(con `sourceName` propio, ej. `"3441759"`, y tags `Falabella`/`B2C`) y que
la regla genérica "cualquier otro sourceName -> Online" los estaba
clasificando mal. Son venta mayorista (Falabella revende), no venta propia
— van a **Mayoristas nacionales**, no a Online. Distintos de las facturas
RFEL manuales de Falabella (RFEL8314/8315/8339 etc., pedidos mayoristas en
firme facturados directamente) — ambos son Falabella pero por flujos
distintos: hay que sumar los dos al canal nacional sin duplicar. Al armar
`--shopify-summary`/`--shopify-orders`, excluir del agregado de Online los
pedidos con tag `Falabella`/`B2C` y agregarlos como una entrada aparte de
`--wholesale` (canal `"nacional"`, ver ejemplo en `wholesale_2026-09.json`
del corte 2026-09-27). Revisar cada corrida si aparecen pedidos con este
patrón — no son frecuentes (4 en todo septiembre) pero sí recurrentes.

## Envío — confirmado con el usuario, 2026-09-08

El envío que se cobra en pedidos web bajo $280.000 SÍ es ingreso de cuenta
4 (la misma cuenta de la que sale la "venta neta" histórica del plan), así
que el valor de cada pedido de Shopify para este dashboard es
`currentSubtotalPriceSet + currentShippingPriceSet` (producto + envío),
no solo producto — ver `order_value()` en `compute.py`. Aplica igual a
Online y Showroom (será $0 donde no se cobró envío). Si se usa el camino
`--shopify-summary` (agregación hecha aparte, ver más abajo), el valor que
se agrega por pedido también debe incluir el envío — copiar `order_value()`
igual que se copia `classify_shopify_order()`.

## Marcador de punto de equilibrio (PE) — confirmado 2026-09-08, actualizado 2026-09-10

La barra TOTAL del panel "Cumplimiento por canal — $ Valor" (sólo esa,
no la de unidades ni las de canal individual) lleva un triángulo invertido
"▽ PE" arriba, marcando la venta neta mínima mensual para no perder
dinero. Viene de la hoja "Costos y Márgenes" del plan: `Personal+Admin
fijo mensual / (1 - COGS% - Mercadeo%)`. Es una cifra de estructura de
costos fija — **no varía por mes** dentro del periodo Sep-Dic 2026, a
diferencia de la meta de venta que sí varía mes a mes. Está en
`plan_2026_2027.json` como `breakeven_value` (top-level, no por mes) y se
computa como
`total.breakevenValue`/`total.breakevenPctOfBudget`/`total.breakevenReached`
en `build_total()`. Si el plan cambia su estructura de costos fijos
(Personal+Admin) o sus techos de COGS%/Mercadeo%, este valor hay que
recalcularlo a mano — no está enlazado a esas hojas automáticamente.

**Historial:** $144.3M (60.3M / (1 - 0.382 - 0.20)) hasta el corte del
2026-09-08. **Actualizado a $152.5M el 2026-09-10** (63.7M / (1 - 0.382 -
0.20)) porque el Personal+Admin fijo subió de $60.3M a $63.7M/mes por la
contratación de Isabella Aponte (Analista de Diseño, desde septiembre de
2026, costo empresa total $3.407M/mes incl. prestaciones — hoja Supuestos
sección 12 del plan). Las metas de venta por canal/mes del plan NO
cambiaron con esta contratación, sólo el PE. Cada vez que se refresque el
dashboard conviene volver a revisar la hoja de Costos y Márgenes /
Supuestos del plan por si la nómina fija cambió de nuevo.

## Facturación adicional (fuera del presupuesto) — confirmado 2026-09-08, corregido 2026-09-12

A veces el mes trae facturas que no son venta recurrente de producto por
canal: colaboraciones/co-branding con marcas externas, paquetes puntuales,
patrocinios, ajustes de facturación anterior. Ejemplos:
- RFEL8320, un pago único de "Consorcio Licores de la Sabana Limitada y
  Otros" (razón social de la Fábrica de Licores de Antioquia — FLA) por la
  propuesta de co-branding Mompossina x Aguardiente Antioqueño,
  $64,250,000 sin IVA, sin unidades de producto → categoría `"FLA"`.
- RFEL8325 (Cristalina Swimwear, $6,784,469 COP, sin unidades de prenda) —
  ver el recuadro de advertencia más abajo. **NO es un servicio de
  diseño**, es un cuadre de cuentas de ventas de agosto subfacturadas →
  categoría `"AJUSTE"` ("Regularización de facturación anterior").

**Estas facturas NUNCA se suman a `channels`, `total`, `runrate`, `ytd` ni
al semáforo** — el plan no las contempla y mezclarlas infla el
cumplimiento de forma engañosa. En vez de eso van en la sección aparte
"Facturación adicional" del dashboard (`DATA.extraordinary`), claramente
marcada como fuera del presupuesto.

**Criterio para decidir dónde va una factura de mayoristas:** ¿tiene
unidades de producto vendido y encaja en un canal (nacional/
internacional)? Si sí → `--wholesale`. Si es un monto fijo por un
servicio/colaboración/patrocinio sin unidades → `--extraordinary`. Ante la
duda, preguntarle al usuario en vez de asumir. Si aparece una categoría
nueva de `--extraordinary` que parece que se va a repetir (un patrón
recurrente confirmado por el usuario), agregarla a
`EXTRAORDINARY_CATEGORIES` en `compute.py` con un label legible — si NO
está confirmado que sea recurrente, dejarla como categoría dinámica: cada
entrada puede llevar un campo opcional `"category_label"` con el texto
legible a mostrar (ver `build_extraordinary_by_category()`), sin
necesidad de comprometerse a una fila fija permanente del panel para
meses futuros.

> ⚠️ **Facturas de "servicios" a mayoristas existentes — confirmado con el
> usuario 2026-09-12, NUNCA asumir.** Algunos mayoristas (en particular
> Cristalina Swimwear) a veces piden subfacturar el producto realmente
> despachado para pagar menos impuesto, y facturan el valor restante
> después como si fuera un "servicio" (de diseño, consultoría, etc.).
> RFEL8325 (sep-2026) es un ejemplo: se había registrado como "servicio de
> diseño" pero en realidad era un cuadre de cuentas de ventas de agosto
> 2026 no facturadas por completo. **Antes de categorizar cualquier
> factura así — descripción vaga tipo "servicio"/"consultoría" sin
> referencias de prenda, tallas ni HS code por línea, facturada a un
> cliente mayorista ya existente — siempre preguntarle al usuario cómo
> tratarla.** Nunca asumir que es un servicio real, y nunca aplicar
> automáticamente el mismo tratamiento de una factura anterior aunque
> parezca el mismo patrón — se pregunta caso por caso. En cambio, una
> factura con líneas de producto detalladas (referencia, talla, HS code,
> cantidad — como RFEL8329/8331/8333 de sep-2026) sí es venta real de
> producto sin ambigüedad y va directo a `--wholesale`.

**Categorías fijas — confirmado 2026-09-08, actualizado 2026-09-12.** Cada
entrada de `--extraordinary` lleva un campo `"category"`. Las categorías
fijas en `EXTRAORDINARY_CATEGORIES` en `compute.py` son `"FLA"`
(colaboraciones/co-branding con la Fábrica de Licores de Antioquia) y
`"PAC"` (venta de paquete completo/curado a un cliente, fuera del esquema
normal por unidad de mayoristas) — (`"SERV"` se agregó el 2026-09-10 y se
quitó el 2026-09-12 al confirmarse que RFEL8325 no era un servicio real ni
un patrón recurrente confirmado). Las categorías fijas **siempre**
aparecen como fila en el panel "Cumplimiento por canal — $ Valor" (no en
el de unidades, no tienen unidades) — con una barra al 100% (color neutro
gris, no verde/amarillo/rojo) si hubo algo facturado ese mes bajo esa
categoría, o al 0% si no hubo nada. Es un indicador de presencia/ausencia,
no de cumplimiento real — no se compara contra ninguna meta, por eso no
lleva semáforo. Se calculan en `build_extraordinary_by_category()` y se
renderizan después de las filas de canal real (con un divisor "Fuera del
presupuesto — no suma al cumplimiento") en el JS del HTML. Una categoría
dinámica (no fija) también aparece ese mes en el panel de barras y en la
tabla resumen, usando su `category_label` si lo trae (o la clave cruda si
no) — solo no está garantizado que se muestre en meses sin datos.

**PAC por sufijo de archivo — confirmado 2026-09-27.** El usuario empezó a
renombrar en Drive las facturas de paquete completo agregando el sufijo
`PAC` al final del nombre del archivo (ej. `RFEL8373 CRISTALINA PAC.pdf`).
Antes de este cambio, `"PAC"` ya existía como categoría fija en
`EXTRAORDINARY_CATEGORIES` pero sin ninguna factura real registrada — a
partir de este corte, **revisar el nombre de archivo de cada factura de
mayoristas en Drive al descargarla**: si termina en `PAC` (con o sin
espacio, ej. `"...PAC.pdf"` o `"...SV PAC.pdf"`), va directo a
`--extraordinary` con `"category": "PAC"`, sale de `--wholesale`, sin
necesidad de preguntarle al usuario aunque la descripción de la factura
sea ambigua tipo "servicio" (el sufijo PAC ya es la confirmación). El
renombrado puede aplicarse también a facturas de meses anteriores para
llevar registro histórico — si el nombre cambia para una factura ya
registrada como wholesale en una corrida anterior, reclasificarla en la
corrida actual (ver ejemplo RFEL8344 en el corte 2026-09-27, que pasó de
`--wholesale` internacional a `--extraordinary` PAC al renombrarse el
archivo).

## Cristalina Swimwear vende en consignación, no en firme — confirmado 2026-09-27

El usuario confirmó que las facturas de Cristalina Swimwear (Miami) NO son
venta en firme — Cristalina recibe la mercancía en **consignación** y las
facturas de exportación son solo el trámite necesario para poder sacar la
mercancía del país, no un hecho de venta real. Por esto, **toda factura de
Cristalina del mes sale del cumplimiento de mayoristas internacionales**,
tenga o no el sufijo `PAC` en el nombre de archivo:
- Si el archivo termina en `PAC` → categoría `"PAC"` (ver arriba).
- Si NO termina en `PAC` (despacho normal en consignación) → categoría fija
  `"CONSIGNACION"` (`EXTRAORDINARY_CATEGORIES`, label "Consignación
  (Cristalina)"), agregada a `compute.py` en este corte. El usuario pidió
  explícitamente que esta categoría no genere ruido en el cumplimiento —
  igual que FLA/PAC, nunca se suma a `channels`/`total`/`runrate`/`ytd`/
  semáforo, solo aparece en el panel "Fuera del presupuesto".

Esto es distinto del caso RFEL8325 (cuadre de cuentas de agosto,
categoría `"AJUSTE"`) — ese es un problema de un mes ya cerrado, mientras
que la consignación es la naturaleza de la relación comercial completa con
Cristalina, aplica a toda factura suya hacia adelante. **No preguntar de
nuevo caso por caso si una factura nueva de Cristalina es "servicio
subfacturado"** (como se hacía antes, ver recuadro de advertencia arriba)
— cualquier factura de Cristalina en la carpeta de exportación va a PAC o
CONSIGNACION según el sufijo del archivo, no a `--wholesale`. Si Cristalina
alguna vez vuelve a comprar en firme (no en consignación), el usuario
avisará explícitamente — no asumir el cambio por cuenta propia.

## Pestañas por mes (histórico + mes en curso + vista previa de meses futuros) — agregado 2026-09-29

A pedido del usuario, el dashboard muestra una pestaña por cada mes del
periodo Sep-Dic 2026 (`plan.period_order`), no solo el mes en curso. Cada
mes tiene un `status`:
- `"current"` — el mes que se está calculando en esta corrida (`--month`).
  Se actualiza en cada corte, igual que siempre.
- `"closed"` — un mes ya cerrado, cargado desde
  `.claude/skills/presupuesto-vs-real/historico/<mes>.json`. Es una foto
  fija del último corte real de ese mes — **nunca se recalcula**, se
  muestra tal cual quedó congelado (incluida su narrativa del resumen
  ejecutivo, su gráfico de ritmo diario y su tabla de facturación
  adicional).
- `"template"` — un mes del plan que todavía no ha empezado (no es el
  `--month` actual ni tiene archivo en `historico/`). `compute.py` lo
  genera automáticamente en cada corrida a partir de
  `build_template_month()`: solo las metas del plan por canal, todo lo
  real en $0/0 unidades, sin ritmo/semáforo (dividir por 0 días
  transcurridos no tiene sentido). El dashboard lo muestra en **versión
  simplificada** (confirmado con el usuario 2026-09-29): se ocultan la
  sección "Ritmo diario" y "Semáforo", las barras quedan en gris
  "pendiente" al 0%, y el resumen ejecutivo es un placeholder genérico de
  una sola viñeta — no hace falta escribir nada a mano para estos meses,
  se generan solos con cada corrida mientras no tengan `historico/`.

**Cómo se arma cada corrida** (en `compute.py::main`): se parte de una
plantilla para cada mes de `plan.period_order`, se sobrescribe con lo que
haya en `historico/` (meses cerrados), y se sobrescribe otra vez con el
mes recién calculado (`--month`, siempre gana). El resultado se manda al
HTML como `DATA_BUNDLE = {byMonth: {...}, currentMonthKey, periodOrder,
ytd}`, reemplazando lo que antes era un `DATA` de un solo mes. El JS del
dashboard (`renderMonth(monthKey)`) puebla todas las secciones a partir de
`DATA_BUNDLE.byMonth[monthKey]` cada vez que se hace click en una pestaña
— no hay que tocar nada a mano para que las pestañas funcionen, solo
mantener el flujo normal de cada corte (correr `compute.py`, editar la
narrativa del mes en curso).

**Cerrar un mes (`freeze_month.py`)** — ver paso 4bis del procedimiento.
Congela `DATA_BUNDLE.byMonth[<mes>]` tal como quedó en el último corte
real (incluye `runrateSvg` ya generado, no hace falta recalcularlo) más el
HTML de `#exec-summary-body` (la narrativa hand-edited), y lo guarda en
`historico/<mes>.json` — este archivo queda **versionado en git**, se
puede auditar/corregir a mano si hace falta. No recalcula nada; si el
corte que se congela no era en realidad el último día del mes completo
(p.ej. se congela con datos de medio mes por error), corregirlo a mano en
el JSON o volver a correr con `--force` después de un corte más
actualizado.

**Qué NO cambia por pestaña** — sigue reflejando siempre el estado real de
hoy, sin importar qué mes esté seleccionado arriba: la sección "Acumulado
del periodo Sep-Dic 2026" (`DATA_BUNDLE.ytd`, fuera de `#month-panels` en
el HTML) y el footer completo (fuentes de datos, metodología). Son
period-level / siempre-vigentes, no tiene sentido que cambien al mirar un
mes distinto.

**Bug ya corregido, no reintroducir:** `patch_html()` usa
`re.subn(pattern, lambda m: wrapped, html, ...)` — el reemplazo va
envuelto en una función, NO como string directo. Si se pasa `wrapped`
como string, el módulo `re` interpreta secuencias como `\n` dentro del
JSON (que aparecen legítimamente al congelar un `narrativeHtml` con
saltos de línea reales) como caracteres de control literales, insertando
un salto de línea real dentro de un string JS de una sola línea y
rompiendo el parseo silenciosamente (el dashboard se ve en blanco, con un
`SyntaxError` en la consola del navegador). Verificado 2026-09-29.

## Datos de referencia

| Concepto | Valor |
|---|---|
| Plan de referencia | `.claude/skills/presupuesto-vs-real/plan_2026_2027.json` — meta por canal y mes (Sep-Dic 2026), precios de facturación, márgenes. Extraído una sola vez de Dropbox (`/Mompossina/Plan Estrategico/Plan_Estrategico_Mompossina_2026_2027.xlsx`, versión **SIN** "Ajuste" — 43,358 bytes, NO la de 48,351 bytes). No hace falta re-leer el Excel cada corrida: el plan no cambia dentro del periodo Sep-Dic salvo que el usuario avise de un ajuste. |
| Meta total del periodo | $1,399.0M (Sep-Dic 2026), 12,913 unidades |
| Canales | Online (Web/Redes propias), Showroom (Retail), Mayoristas nacionales (Multimarcas), Mayoristas internacionales (Internacional directo) |
| Mayoristas | Facturas electrónicas en Google Drive, carpetas "FACTURAS NACIONALES" y "FACTURA EXPOR" (no automatizado — se extrae a mano cada corrida, ver paso 3) |
| Script de cómputo | `.claude/skills/presupuesto-vs-real/compute.py` |
| Cuenta Google Drive | `googledrive_secern-burl` (operaciones@mompossina.com) — especificar `account` en `run_composio_tool`/`COMPOSIO_MULTI_EXECUTE_TOOL` si hay ambigüedad de múltiples cuentas conectadas |

## Procedimiento

Trabaja en un directorio temporal del scratchpad (p.ej.
`$SCRATCH/presupuesto-vs-real`).

**1. Rango del mes y hora de corte.** Por defecto, el mes calendario en
curso, desde el día 1 hasta hoy (hora Bogotá):
```
TZ="America/Bogota" date "+%Y-%m-%dT%H:%M:%S-05:00"
```
`daysElapsed` = día del mes de ese timestamp (no fracción de día). Si
`plan_2026_2027.json` no tiene todavía el mes pedido (p.ej. un mes fuera de
Sep-Dic 2026), avisar al usuario — no inventar meta.

**2. Traer pedidos de Shopify del mes** con `SHOPIFY_GRAPH_QL_QUERY`
(cuenta Mompossina), paginado:
```graphql
query Orders($q: String!, $after: String) {
  orders(first: 30, query: $q, sortKey: CREATED_AT, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      name createdAt tags sourceName test displayFinancialStatus
      currentSubtotalPriceSet { shopMoney { amount } }
      currentShippingPriceSet { shopMoney { amount } }
      lineItems(first: 50) { edges { node { currentQuantity } } }
    } }
  }
}
```
con `q = "created_at:>=<primer día del mes>T00:00:00-05:00 created_at:<=<hoy>T23:59:59-05:00"`.

**Importante — transferencia de datos:** el proxy de egreso de esta sesión
bloquea `backend.composio.dev` y otros hosts de almacenamiento (403), así
que un archivo grande guardado en el sandbox de `COMPOSIO_REMOTE_WORKBENCH`
o subido a S3 **no se puede descargar** con `curl` local. Dos caminos:
- **Preferido cuando el volumen del mes es manejable** (unos cientos de
  pedidos): pedir páginas pequeñas (`first: 30`) directamente con
  `COMPOSIO_MULTI_EXECUTE_TOOL` (no el workbench) — así la respuesta vuelve
  completa en línea (sin pasar por el sandbox) y se puede escribir a un
  archivo local con Write, página por página, para pasarle
  `--shopify-orders` a `compute.py`.
- **Si el mes tiene muchos más pedidos** (temporada alta, tienda mucho más
  grande): paginar y clasificar dentro de `COMPOSIO_REMOTE_WORKBENCH`
  (network propio, sin la restricción del proxy local), pero **copiando
  literalmente `classify_shopify_order()` de `compute.py`** dentro del
  notebook — no reescribir la regla de memoria. El resultado que cruza de
  vuelta es solo el resumen agregado (`{online, showroom, daily, excluded}`,
  unos pocos KB), que sí cabe en línea — pasarlo a `compute.py` con
  `--shopify-summary` en vez de `--shopify-orders` (ambos flags están
  soportados, uno u otro, no los dos).

**3. Traer facturas de mayoristas** (Google Drive, `GOOGLEDRIVE_FIND_FILE` /
`GOOGLEDRIVE_DOWNLOAD_FILE`, cuenta `googledrive_secern-burl`): carpetas
"FACTURAS NACIONALES" y "FACTURA EXPOR", filtrar a facturas con fecha del
mes en curso. Descargar y parsear cada PDF con `pdfplumber` dentro de
`COMPOSIO_REMOTE_WORKBENCH` (el link firmado de Cloudflare R2 que devuelve
`GOOGLEDRIVE_DOWNLOAD_FILE` sólo es alcanzable desde la red del sandbox, no
desde Bash local). Armar `wholesale_<mes>.json`:
```json
[{"channel":"nacional"|"internacional","date":"YYYY-MM-DD","value":123,
  "units":10,"invoice":"RFEL...","partner":"...","note":"opcional"}]
```
Una nota de crédito sin prenda despachada usa `"units": 0` (se suma al
valor del canal, no a las unidades — ver ejemplo RFEL8315 en septiembre).

Al revisar cada factura nueva, separa las que NO sean venta de producto por
unidades (colaboraciones, co-branding, patrocinios — ver sección
"Facturación adicional" arriba) en `extraordinary_<mes>.json` en vez de
`wholesale_<mes>.json`:
```json
[{"date":"YYYY-MM-DD","invoice":"RFEL...","category":"FLA","partner":"...",
  "description":"...","value":123,"note":"opcional"}]
```
`category` es `"FLA"` o `"PAC"` (ver `EXTRAORDINARY_CATEGORIES` en
`compute.py`) — determina en qué fila fija del panel "$ Valor" aparece.

**4. Acumulado de meses ya cerrados (sólo relevante desde octubre en
adelante).** `compute.py` necesita `--prior-real-value`/`--prior-real-units`
= suma de venta/unidades REAL de los meses del periodo ya cerrados antes del
mes que se está calculando (0 en septiembre, el mes 1). Llevar este
acumulado en un archivo simple del scratchpad o preguntarle al usuario el
real definitivo del mes anterior si no quedó registrado — no inventarlo.

**4bis. Si el mes cambió desde el corte anterior (el `--month` de hoy es
distinto al de la última corrida), congelar el mes que se cierra ANTES de
correr `compute.py` con el `--month` nuevo** (ver sección "Pestañas por
mes" más abajo):
```
python3 .claude/skills/presupuesto-vs-real/freeze_month.py \
  --html dashboards/presupuesto-vs-real.html \
  --month 2026-09
```
Esto lee el último corte real de septiembre (que sigue en el HTML porque
todavía no se ha corrido `compute.py` para octubre) y lo guarda en
`.claude/skills/presupuesto-vs-real/historico/2026-09.json`, congelado tal
cual — recién ahí correr `compute.py --month 2026-10 ...`, que carga ese
archivo automático y lo muestra como pestaña cerrada. Si el corte de hoy
sigue siendo del mismo mes que el corte anterior, saltar este paso.

**5. Calcular y parchear el dashboard:**
```
python3 .claude/skills/presupuesto-vs-real/compute.py \
  --plan .claude/skills/presupuesto-vs-real/plan_2026_2027.json \
  --month 2026-09 \
  --shopify-orders $SCRATCH/presupuesto-vs-real/orders.json \
  --wholesale $SCRATCH/presupuesto-vs-real/wholesale_2026-09.json \
  --now "<hora ISO Bogotá del paso 1>" \
  --html dashboards/presupuesto-vs-real.html
  [--prior-real-value 0 --prior-real-units 0]
  [--extraordinary $SCRATCH/presupuesto-vs-real/extraordinary_2026-09.json]
```
(o `--shopify-summary ...json` en vez de `--shopify-orders`, ver paso 2).
`--extraordinary` es opcional — solo pasarlo si hubo facturas fuera del
presupuesto ese mes (ver sección de arriba); si no se pasa, la sección
"Facturación adicional" del dashboard queda oculta automáticamente.
Revisa el resumen impreso (por canal: real/meta/% mes/ritmo/semáforo,
proyección de cierre, acumulado, canales en rojo). Si algo se ve fuera de
lugar (un canal en rojo que no debería, un ticket promedio absurdo), no
publiques — revisa los JSON de entrada antes de tocar `compute.py`.

**6. Reescribir a mano la narrativa**, usando los números que imprimió el
script:
- `<ul class="exec-list">` dentro de `<div id="exec-summary-body">`
  (Resumen ejecutivo): 4-6 bullets — cumplimiento total, canal(es) que más
  se destacan por delante/atrás del ritmo, canales en rojo, proyección de
  cierre, y la viñeta `id="accion-recomendada"` con la acción #1
  recomendada del mes. Este bloque es el que `freeze_month.py` congela tal
  cual cuando el mes cierra — no hace falta hacer nada especial para que
  quede guardado, solo mantenerlo actualizado en cada corte del mes en
  curso.
- Nota de mayoristas (`id="nota-mayoristas"`) si cambia la historia de
  nacional/internacional (facturó más, sigue en cero, etc.) — la explicación
  metodológica de por qué mayoristas no se proyecta por ritmo generalmente
  NO cambia, sólo los números específicos del párrafo final.
- Footer: fechas y facturas específicas de mayoristas del mes (el footer
  siempre describe el mes en curso, no cambia por pestaña — ver sección
  "Pestañas por mes" más abajo).
No toques el resto del HTML — todo lo demás ya se recalcula solo desde
`DATA_BUNDLE`.

**7. Screenshot antes de publicar.** Playwright/Chromium
(`/opt/pw-browsers/chromium`, `NODE_PATH=$(npm root -g)`), claro y oscuro,
revisando que no haya errores de JS (`pageerror`) y que las cifras nuevas
se vean bien — un marcador mal cerrado rompe todo el `DATA` silenciosamente.

**8. Republicar el Artifact:**
- `file_path`: `dashboards/presupuesto-vs-real.html`
- `url`: `https://claude.ai/artifact/GLPEPUuAWn1C6FoPSB8JrN`
- `favicon`: omitir en redeploys (ya quedó fijado como 🎯)

**9. Publicar/actualizar como página pública (GitHub Pages)**, dentro de
`ventas-fla`:
```
git add dashboards/presupuesto-vs-real.html
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "Actualizar presupuesto vs. real (<mes/año>, corte <fecha>)"
git push origin <rama de trabajo>   # reintenta con backoff si falla
```
Si el trabajo se hizo en una rama distinta a la rama por defecto del repo,
abrir un Pull Request hacia la rama por defecto y fusionarlo — una sesión
nueva parte de la rama por defecto, así que el dashboard sólo queda "vivo"
en GitHub Pages una vez fusionado.

**10. Reportar en el chat**: % cumplimiento del mes, ritmo esperado a la
fecha, canal(es) en rojo, proyección de cierre (piso) y acción #1
recomendada.

## Notas

- **`plan_2026_2027.json` es estático dentro del periodo Sep-Dic 2026** — no
  volver a leer el Excel de Dropbox cada corrida. Sólo regenerarlo si el
  usuario avisa de un ajuste al plan (como pasó con el archivo "Ajuste" que
  se descartó originalmente) o si se necesita extender el plan a 2027.
- **La regla de clasificación Showroom/Online vive únicamente en
  `classify_shopify_order()`** — si algún día hay que ajustarla (p.ej. si
  el equipo empieza a usar el tag `SHOWROOM` de forma consistente, o si
  Shopify habilita `staffMember`), cambiarla ahí, actualizar el docstring
  del módulo, y avisar al usuario del cambio de metodología igual que se
  hizo el 2026-09-07.
- **No inventar mayoristas ni el acumulado de meses previos**: si no se
  puede acceder a las facturas de Drive o al real de un mes ya cerrado, no
  se publica con datos estimados — se le pregunta al usuario o se marca
  explícitamente como pendiente en el footer.
- **Sin Chart.js ni dependencias externas**: todos los gráficos son SVG
  inline generados por `compute.py` (`build_runrate_svg`) o por el propio
  JS del HTML a partir de `DATA` — cdnjs.cloudflare.com resultó no ser
  confiable ni en el sandbox de pruebas ni en el navegador real del usuario
  (ver historial de commits de este dashboard).
