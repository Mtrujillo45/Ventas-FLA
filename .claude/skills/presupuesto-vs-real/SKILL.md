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
- **Artifact privado**: https://claude.ai/code/artifact/7c2de969-18d9-4d3e-bf27-37505c48196b
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
sourceName == "web"                              -> Online
sourceName == "shopify_draft_order":
  tags contiene "redes sociales"/"melonn"/
  "melonn-entregado"                              -> Online (Redes propias)
  si no                                           -> Showroom
cualquier otro sourceName (marketplace sincronizado,
  ej. Falabella)                                  -> Online
pedido test, financial status fuera de {PAID,
  PARTIALLY_PAID, PARTIALLY_REFUNDED, REFUNDED},
  o valor $0 (saldo de bono, regalo, pago UGC)     -> excluido
```

**No usar `tags contains SHOWROOM`** como filtro — es la causa raíz del bug
reportado. Si en el futuro Shopify habilita `staffMember`/`retailLocation`
para esta cuenta, sería una señal más limpia — reevaluar en ese momento,
pero no es necesario mientras el patrón de tags siga siendo consistente.

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

## Facturación adicional (fuera del presupuesto) — confirmado 2026-09-08

A veces el mes trae facturas que no son venta recurrente de producto por
canal: colaboraciones/co-branding con marcas externas, paquetes puntuales,
patrocinios. Ejemplo: RFEL8320, un pago único de "Consorcio Licores de la
Sabana Limitada y Otros" (razón social de la Fábrica de Licores de
Antioquia — FLA) por la propuesta de co-branding Mompossina x Aguardiente
Antioqueño, $64,250,000 sin IVA, sin unidades de producto.

**Estas facturas NUNCA se suman a `channels`, `total`, `runrate`, `ytd` ni
al semáforo** — el plan no las contempla y mezclarlas infla el
cumplimiento de forma engañosa. En vez de eso van en la sección aparte
"Facturación adicional" del dashboard (`DATA.extraordinary`), claramente
marcada como fuera del presupuesto.

**Criterio para decidir dónde va una factura de mayoristas:** ¿tiene
unidades de producto vendido y encaja en un canal (nacional/
internacional)? Si sí → `--wholesale`. Si es un monto fijo por un
servicio/colaboración/patrocinio sin unidades → `--extraordinary`. Ante la
duda, preguntarle al usuario en vez de asumir.

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
[{"date":"YYYY-MM-DD","invoice":"RFEL...","partner":"...",
  "description":"...","value":123,"note":"opcional"}]
```

**4. Acumulado de meses ya cerrados (sólo relevante desde octubre en
adelante).** `compute.py` necesita `--prior-real-value`/`--prior-real-units`
= suma de venta/unidades REAL de los meses del periodo ya cerrados antes del
mes que se está calculando (0 en septiembre, el mes 1). Llevar este
acumulado en un archivo simple del scratchpad o preguntarle al usuario el
real definitivo del mes anterior si no quedó registrado — no inventarlo.

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
- `<ul class="exec-list">` (Resumen ejecutivo): 4-6 bullets — cumplimiento
  total, canal(es) que más se destacan por delante/atrás del ritmo, canales
  en rojo, proyección de cierre, y la viñeta `id="accion-recomendada"` con
  la acción #1 recomendada del mes.
- Nota de mayoristas (`id="nota-mayoristas"`) si cambia la historia de
  nacional/internacional (facturó más, sigue en cero, etc.) — la explicación
  metodológica de por qué mayoristas no se proyecta por ritmo generalmente
  NO cambia, sólo los números específicos del párrafo final.
- Footer: fechas y facturas específicas de mayoristas del mes.
No toques el resto del HTML — todo lo demás ya se recalcula solo desde
`DATA`.

**7. Screenshot antes de publicar.** Playwright/Chromium
(`/opt/pw-browsers/chromium`, `NODE_PATH=$(npm root -g)`), claro y oscuro,
revisando que no haya errores de JS (`pageerror`) y que las cifras nuevas
se vean bien — un marcador mal cerrado rompe todo el `DATA` silenciosamente.

**8. Republicar el Artifact:**
- `file_path`: `dashboards/presupuesto-vs-real.html`
- `url`: `https://claude.ai/code/artifact/7c2de969-18d9-4d3e-bf27-37505c48196b`
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
