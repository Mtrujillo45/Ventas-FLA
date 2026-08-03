# Presupuesto de Ventas 2026 y Cuadro de Control — Mompossina

Plan de recolección de información para responder al correo del asesor externo
sobre el presupuesto de ventas 2026 (en $ y en unidades), el desglose por
canal, los puntos de equilibrio y el cuadro de control de seguimiento.

Cuadro de control (Google Sheets, ya compartido):
https://docs.google.com/spreadsheets/d/1WqckoWaribXnwbGHkjJQhNcL2arp6_hPO7DaL2Z4IYE

## 1. Auditoría del cuadro de control (estado actual)

La pestaña **"Presupuesto de ventas"** ya tiene la estructura montada, con
fórmulas de suma, pero **sin ningún dato cargado todavía** (todo en cero o
vacío):

| Bloque | Filas | Contenido |
|---|---|---|
| Empresa (consolidado) | 3–4 | Presupuesto $ y unidades, mensual (Ene–Dic) + Total |
| Empresa | 6–7 | Punto de equilibrio: ventas totales y unidades totales |
| Punto de venta | 8–12 | Presupuesto $ y unidades (mensual) + punto de equilibrio (ventas/unidades) |
| Digital | 13–17 | Ídem |
| Internacional | 18–22 | Ídem |
| Nacional | 23–27 | Ídem |

Es decir: la plantilla está lista para recibir exactamente lo que pide el
correo. Lo que falta es **toda la información de entrada**.

## 2. Qué se puede alimentar automáticamente desde Shopify

Shopify está conectado (tienda `mompossina.myshopify.com`, moneda COP). Con
eso podemos calcular directamente:

- **Digital**: pedidos con `sourceName = web` (tienda online) — ventas $ y
  unidades reales, mes a mes, 2025 y lo corrido de 2026. Es el mismo criterio
  ShopifyQL que ya usa el skill `cierre-mensual`.
- **Punto de venta (aproximado)**: pedidos manuales/`draft_order` (showroom),
  igual que hace `cierre-mensual` al combinar "online + manual/showroom" como
  un solo bucket de Shopify. Si se quiere separar con precisión por ubicación
  física, se necesita el scope `read_locations` en la conexión de Shopify
  (hoy no está habilitado — dio `ACCESS_DENIED` al consultarlo).

Esto nos da una **línea base histórica real (2025)** para dos de los cuatro
canales, que sirve de punto de partida para proyectar 2026.

## 3. Vacío detectado: Nacional e Internacional

En una muestra de los ~50 pedidos más recientes de Shopify, el 100% de los
que tienen dirección de envío es a Colombia, todos vía tienda online — no
aparece ningún canal internacional ni nada que luzca como venta mayorista.
Esto coincide con lo que el skill `cierre-mensual` ya documenta como
"capítulos pendientes": **canal mayorista y World Office, sin conectar**.

**Hipótesis a confirmar con el asesor:** Nacional = venta mayorista /
distribución dentro de Colombia (fuera de la tienda Shopify), Internacional
= exportación / mayorista fuera de Colombia. Si es así, esos dos canales no
se pueden alimentar desde Shopify — necesitan otra fuente (Excel, correos,
facturación, World Office).

**Actualización (3 ago):** Natalia confirmó que **no existe una fuente de
ventas 2025** para Nacional e Internacional. Lo que se está construyendo
actualmente es el corrido **2026 Enero–Julio** de estos dos canales — sigue
sin fecha de entrega. Cuando llegue, el punto de partida para el presupuesto
2026 de estos canales será ese corrido parcial (no un año completo 2025 como
sí tenemos para Digital y Punto de venta).

## 4. Costeo de colecciones recibido (primer insumo real de costos)

Natalia compartió 4 archivos de costeo por colección (`COSTOS_ANCIENT.xlsx`,
`COSTOS_DICIEMBRE.xlsx`, `COSTOS_LA_EMPERATRIZ.xlsx`,
`COSTOS_SECRET_GARDEN.xlsx`), con la advertencia explícita de que **el costo
indirecto viene inflado por una doble imputación**. Se consolidaron en
[`presupuesto-2026/base-costos-precios.xlsx`](base-costos-precios.xlsx)
(pestañas `SKUs`, `Resumen por colección`, `Notas y advertencias`). Hallazgos:

- **433 SKUs consolidados** en 3 colecciones únicas: ANCIENT (135), LA
  EMPERATRIZ (185), SECRET GARDEN (113).
- **`COSTOS_ANCIENT.xlsx` y `COSTOS_DICIEMBRE.xlsx` son el mismo archivo**:
  135 SKUs, mismos costos y precios fila por fila, sin ninguna diferencia. Se
  consolidaron como una sola colección ("ANCIENT") para no duplicar esas 135
  referencias en la base. **Falta confirmar** si de verdad es la misma
  colección guardada dos veces, o si "Diciembre" debía tener datos propios.
- **✅ RESUELTO (3 ago): sin esquema de costos indirectos.** Natalia decidió
  eliminar por completo el prorrateo de "costo indirecto" del costeo de
  producto: todo lo que se cargaba ahí (diseño, fotógrafo, modelo, montaje,
  locación, alimentación, y el salario del Jefe de Producción) era, o doble
  contabilización, o en realidad gasto de mercadeo y ventas — no costo de
  producción. **De aquí en adelante el costo de producto es solo el costo
  directo.** `base-costos-precios.xlsx` se actualizó: las columnas y
  márgenes que usaban el indirecto quedan marcadas como histórico/no
  vigente, y se agregaron 5 columnas nuevas (en verde) con el margen
  correcto usando solo costo directo por cada canal de precio. Confirmado
  además por `CONTROL DE PAGOS 2026.xlsx` (ver sección 6): su sección
  "Mercadeo y Ventas" sí incluye maquillaje, ilustración, pauta y agencias —
  exactamente lo que antes se cargaba como indirecto al producto.
- **La estructura de precios por canal ya existe** dentro de estos mismos
  archivos (esto es lo que el correo del asesor llama "la estructura de
  precios que venimos desarrollando"). Revisando las fórmulas originales
  celda por celda (no solo los nombres de columna), el mapeo más probable a
  los 4 canales del presupuesto es:
  - **Precio Ideal (= PVP, coincide exacto con la hoja PRECIOS) → Punto de
    venta**
  - **Precio Página Web → Digital**
  - **Precio Multimarca → Nacional** (venta mayorista a boutiques dentro de
    Colombia — hipótesis a confirmar)
  - **Internacional / Distribuidor Inter 30% / Precio Sugerido Retail
    (encadenados en USD, ×3500 a COP en las fórmulas) → Internacional** —
    ojo, "Precio Sugerido Retail" NO es el precio nacional: es el precio de
    reventa sugerido en el exterior, en dólares.
- **Costo variable de Digital ya cuantificado** (hoja "Página Web", solo en
  Ancient/Diciembre): Pauta 15% + Pasarela de pago 3% + Shopify 2% + Flete 8%
  + Shopify Fee 0.18% + Contenido 2% = **30.18% del precio de venta**. Falta
  este mismo desglose para La Emperatriz y Secret Garden, y para Punto de
  venta / Nacional / Internacional.

## 5. Línea base real 2025 (Shopify) — Digital y Punto de venta

Se extrajeron los 7,142 pedidos de 2025 directamente de Shopify (bulk GraphQL
vía Composio, zona horaria Bogotá, excluyendo pedidos de prueba y quedándose
solo con estados PAID/PARTIALLY_PAID/PARTIALLY_REFUNDED/REFUNDED) y se
consolidaron mes a mes en
[`presupuesto-2026/real-2025-shopify.xlsx`](real-2025-shopify.xlsx). Es la
primera línea base real (no supuesta) para dos de los cuatro canales:

| Canal | Ventas 2025 (sin IVA) | Unidades 2025 | Precio promedio |
|---|---|---|---|
| Digital | $943.840.747 | 10.988 | $85.897 |
| Punto de venta | $240.291.611 | 3.337 | $72.008 |
| **Total (solo estos 2 canales)** | **$1.184.132.358** | **14.325** | **$82.662** |

El archivo trae el detalle mes a mes (Ene–Dic 2025) y precio promedio por mes,
con fórmulas vivas. Sirve como punto de partida directo para proyectar el
2026 de estos dos canales en cuanto se defina la meta de crecimiento (sección
7.1) — todavía falta el mismo ejercicio para Nacional e Internacional, que
no están en Shopify (ver sección 3).

**Nota:** esto es la línea base de *ventas*, no de *presupuesto*. No se
escribió nada todavía en la pestaña "Presupuesto de ventas" del Google
Sheet compartido con el asesor — eso implicaría decidir una meta de
crecimiento 2026 sobre esta base, algo que corresponde definir junto con
Natalia y el asesor, no asumirlo unilateralmente.

## 6. Costos fijos de la empresa (CONTROL DE PAGOS 2026)

Natalia compartió `CONTROL DE PAGOS 2026.xlsx` (Google Drive) — el registro
de pagos y pendientes de la empresa, por mes (Enero–Agosto 2026) y por
sección dentro de cada mes. Se consolidó en
[`presupuesto-2026/costos-fijos-2026.xlsx`](costos-fijos-2026.xlsx)
(pestañas `Resumen mensual`, `Detalle Gastos Personal`, `Detalle Gastos
Administrativos`, `Notas y advertencias`).

| Categoría | Total (8 meses) | Promedio mensual |
|---|---|---|
| Gastos Personal | $240.040.628 | $30.005.078 |
| Gastos Administrativos | $432.737.879 | $54.092.235 |
| Mercadeo y Ventas (no es costo fijo) | $638.274.571 | $79.784.321 |
| Producción (ya está en el costo directo por SKU) | $1.411.800.389 | $176.475.049 |
| Préstamos (financiación, no costo operativo) | $184.946.145 | $23.118.268 |

**Candidatos directos a costo fijo para el punto de equilibrio: Gastos
Personal + Gastos Administrativos.** Pero ojo, no son un número limpio
todavía:

- **⚠ El total de Gastos Administrativos incluye partidas que NO son costo
  operativo real**, y las infla mucho: el IVA ($142.127.000 en julio, un
  pago bimestral a la DIAN — el IVA se cobra al cliente y se traslada, no es
  gasto de la empresa), la declaración de renta anual, y pagos de tarjeta de
  crédito (Visa, TC48225) que probablemente ya corresponden a compras
  registradas en otra sección (riesgo de doble conteo, sin confirmar).
- **Hallazgo concreto: renta del Punto de Venta identificada.** "LIA UPEGUI"
  / "LOCAL [mes]" es, todo indica, el arriendo del local físico — se repite
  cada mes por $3.686.004. Es el primer dato específico de costo fijo por
  canal (Punto de venta) que tenemos.
- **Por confirmar:** "PADILLO" / "CUOTA CASA NATA" (cuota mensual de
  $4.373.334 u $8.746.668) — el nombre sugiere otra sede o una obligación
  fija, pero falta que Natalia confirme qué es y si debe ir en los costos
  fijos de la empresa.
- Solo cubre 2026 (Enero–Agosto), no hay dato de 2025.

`costos-fijos-2026.xlsx` trae el desglose proveedor por proveedor con
cuántos de los 8 meses aparece cada uno, para poder distinguir a simple
vista lo recurrente (nómina, seguridad ARUS, arriendo) de lo esporádico
(liquidaciones, impuestos anuales, gastos puntuales) — pero la
clasificación final de qué entra o no en "costos fijos" queda pendiente de
que Natalia la revise línea por línea.

## 7. Checklist de información por tarea

### 7.1 Presupuesto en $ y unidades — consolidado y por canal

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Ventas y unidades reales 2025, mensual — Digital | Shopify (online) | Yo lo extraigo | **Disponible** — ver sección 5 y `real-2025-shopify.xlsx` |
| Ventas y unidades reales 2025, mensual — Punto de venta | Shopify (draft orders/showroom) | Yo lo extraigo | **Disponible** (aproximado) — ver sección 5 |
| Ventas y unidades reales 2025, mensual — Nacional | ¿World Office / Excel / facturación mayorista? | Natalia / contabilidad | **Pendiente, en camino** |
| Ventas y unidades reales 2025, mensual — Internacional | ¿World Office / Excel / registros de exportación? | Natalia / contabilidad | **Pendiente, en camino** |
| Meta de crecimiento 2026 por canal (%, o cifra objetivo) | Decisión estratégica | Natalia + asesor | Pendiente de definir |
| Estacionalidad esperada (curva mensual) | Se deriva del histórico por canal | Ya calculada para Digital/PDV en `real-2025-shopify.xlsx`; falta Nacional/Internacional | Parcial |
| Capacidad de producción / restricciones de oferta 2026 | Producción | Natalia | Pendiente |

### 7.2 Conexión $ ↔ unidades ↔ precio ↔ costo ↔ margen ↔ rotación

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Precio promedio por canal | Se calcula de ventas $ / unidades (una vez haya datos) | Yo lo calculo | Depende del histórico |
| Estructura de precios por referencia/categoría | Recibida dentro de los 4 archivos de costeo (ver sección 4) | Asesor / Natalia | **Recibida y mapeo refinado** — falta confirmación final del asesor (pregunta 4) |
| Costo de producción (COGS) por prenda/categoría | 4 archivos de costeo (433 SKUs, ver `base-costos-precios.xlsx`) | Natalia | **✅ Resuelto** — política: solo costo directo, sin esquema de indirectos |
| Inventario y rotación por referencia/talla | Shopify (niveles de inventario) | Yo lo extraigo | Parcialmente disponible (ya lo usa el skill `reposicion-estrellas`) |
| Margen bruto por canal/categoría | Precio promedio − costo de producción | Yo lo calculo | **Recalculado con costo directo únicamente** en `base-costos-precios.xlsx` (columnas "VIGENTE", en verde) |

### 7.3 Puntos de equilibrio (por canal y consolidado)

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Costos fijos totales de la empresa | `CONTROL DE PAGOS 2026.xlsx` (ver sección 6) | Natalia | **Recibido (2026 Ene-Ago)** — falta que Natalia confirme qué partidas de Gastos Administrativos son costo operativo real (excluir IVA, renta, tarjetas de crédito) |
| Costos fijos asignables al Punto de venta (arriendo showroom, personal, servicios) | Contabilidad | Natalia | **Parcial** — arriendo identificado ("LIA UPEGUI"/LOCAL, $3.686.004/mes), falta el resto (personal, servicios asignados al local) |
| Costos fijos/variables asignables a Digital (plataforma, pauta, comisiones pasarela) | Contabilidad + marketing | Natalia | **Recibido en parte** — 30.18% de costo variable ya definido (hoja "Página Web"); costos reales de Mercadeo y Ventas ya están en `costos-fijos-2026.xlsx` para cruzar |
| Costos de operar Nacional e Internacional (comisiones, logística, aranceles si aplica) | Contabilidad | Natalia | **Pedir** |
| Costo variable por unidad vendida (producción + comisión + envío + pasarela) por canal | Costeo + contabilidad | Natalia | **Recibido** — costo directo por SKU (`base-costos-precios.xlsx`) + 30.18% de Digital; falta el mismo desglose para PDV/Nacional/Internacional |

Con eso: punto de equilibrio en $ = costos fijos ÷ % margen de contribución;
en unidades = costos fijos ÷ margen de contribución por unidad. Se calcula
igual para cada canal y para la empresa consolidada.

### 7.4 Cuadro de control (seguimiento mensual)

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Real mensual $ y unidades — Digital y Punto de venta | Shopify | Yo lo automatizo | **Ya extraído para 2025** (`real-2025-shopify.xlsx`); falta automatizar el refresco mensual (extensión del skill `cierre-mensual`) |
| Real mensual $ y unidades — Nacional e Internacional | Fuente por definir (ver 7.1) | Natalia | Pendiente |
| Costos reales mensuales (para margen real vs. presupuestado) | Contabilidad | Natalia | Pendiente |

## 8. Preguntas para resolver con el asesor / con Natalia

1. ¿Cómo se define exactamente cada canal, en especial **Nacional** e
   **Internacional**? ¿Coincide con mayorista nacional / exportación, o es
   otra cosa (p. ej. ventas online a clientes fuera de Colombia dentro de la
   misma tienda Shopify)?
2. Ya confirmado que no hay fuente de ventas 2025 para Nacional/Internacional
   — ¿para cuándo se espera el corrido 2026 (Enero–Julio) que se está
   construyendo?
3. ~~¿Cuál es la doble imputación exacta del costo indirecto?~~ — **resuelto**:
   se elimina el esquema de indirectos, solo costo directo (ver sección 4).
4. ¿"Precio Multimarca" corresponde al canal **Nacional** del presupuesto
   (venta mayorista a boutiques dentro de Colombia)? ¿Y la cadena
   Internacional / Distribuidor Inter 30% / Precio Sugerido Retail
   corresponde al canal **Internacional**? ¿Y "Precio Ideal" (= PVP) es el
   precio de **Punto de venta**?
5. ¿`COSTOS_ANCIENT.xlsx` y `COSTOS_DICIEMBRE.xlsx` son la misma colección
   guardada dos veces, o debían tener datos distintos?
6. De `CONTROL DE PAGOS 2026.xlsx`: ¿qué es exactamente "PADILLO" / "CUOTA
   CASA NATA" (~$4.37M–$8.75M/mes) y debe ir en los costos fijos de la
   empresa? ¿Los pagos de tarjeta de crédito (Visa, TC48225) ya están
   contados en otra sección (riesgo de doble conteo) o son gasto aparte?
   ¿El IVA y la declaración de renta deben excluirse por completo del costo
   fijo operativo (mi supuesto) o hay alguna porción que sí corresponda?
7. De Préstamos ($184.9M en 8 meses): ¿se puede separar el componente de
   interés (costo financiero) del capital (no es costo operativo), para
   decidir si el interés entra al punto de equilibrio?
8. ¿Se requiere separar Punto de venta por ubicación física exacta (lo que
   implicaría pedir el scope `read_locations` en Shopify), o basta con la
   aproximación por tipo de pedido (online vs. manual/showroom) que ya usa
   `cierre-mensual`?

## 9. Próximos pasos propuestos

1. ~~Natalia confirma la doble imputación del costo indirecto~~ — **hecho**:
   se elimina el esquema de indirectos (sección 4).
2. **Natalia / asesor** resuelven la definición de Nacional/Internacional y
   confirman el mapeo de columnas de precio (preguntas 1 y 4 de la sección 8).
3. ~~Yo extraigo de Shopify el histórico mensual 2025 de Digital y Punto de
   venta~~ — **hecho**, ver sección 5.
4. ~~Natalia entrega costos fijos de la empresa~~ — **hecho** (2026
   Ene-Ago, `costos-fijos-2026.xlsx`) — falta que Natalia responda las
   preguntas 6 y 7 de la sección 8 para depurar el número final.
5. **Natalia / contabilidad** entregan el corrido 2026 de ventas de
   Nacional/Internacional cuando esté listo.
6. Con esos insumos, armamos juntos el presupuesto 2026 mensualizado y los
   puntos de equilibrio directamente en la pestaña "Presupuesto de ventas"
   del Google Sheet.
7. Se extiende el skill `cierre-mensual` (o se crea uno nuevo) para que el
   cuadro de control compare mensualmente presupuestado vs. real, por canal,
   en $ y en unidades, con precio promedio — automatizando el seguimiento.
