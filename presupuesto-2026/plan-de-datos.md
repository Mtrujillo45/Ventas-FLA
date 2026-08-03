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

Natalia confirmó (3 ago) que la fuente de ventas de Nacional e Internacional
llega en un momento — **sigue pendiente**, sin fecha aún.

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
- **⚠ Costo indirecto sin depurar todavía.** Cada colección prorratea un
  "costo por prenda" (diseño, fotógrafo, modelo, montaje, locación, empaque,
  y el **salario del Jefe de Producción**) entre las prendas producidas:
  $11.739 (Ancient), $10.185 (La Emperatriz), $11.926 (Secret Garden) por
  prenda. El salario del Jefe de Producción es la línea más grande del pool
  en las tres colecciones (33%–37% del total, ver pestaña "Resumen por
  colección") — es el sospechoso más probable de la doble imputación que
  advirtió Natalia: si ese salario **también** se contabiliza como costo fijo
  de nómina en la contabilidad general, se está sumando dos veces. La columna
  "Costo Indirecto asignado" en la base quedó marcada en rojo como pendiente
  de corrección — **no usar el "Costo Total" de esta base para márgenes o
  puntos de equilibrio hasta confirmar la cifra correcta**.
- **La estructura de precios por canal ya existe** dentro de estos mismos
  archivos (esto es lo que el correo del asesor llama "la estructura de
  precios que venimos desarrollando"). Cada SKU trae precio y margen para:
  Precio Multimarca, Precio Página Web, Internacional, Distribuidor Inter
  30%, Precio Sugerido Retail / Precio Ideal. Esto refina la hipótesis de la
  sección 3:
  - **Página Web → Digital**
  - **Multimarca → Nacional** (venta mayorista a boutiques/multimarca dentro
    de Colombia — hipótesis a confirmar)
  - **Internacional / Distribuidor Inter 30% → Internacional**
  - **Precio Sugerido Retail / Precio Ideal → Punto de venta**
- **Costo variable de Digital ya cuantificado** (hoja "Página Web", solo en
  Ancient/Diciembre): Pauta 15% + Pasarela de pago 3% + Shopify 2% + Flete 8%
  + Shopify Fee 0.18% + Contenido 2% = **30.18% del precio de venta**. Falta
  este mismo desglose para La Emperatriz y Secret Garden, y para Punto de
  venta / Nacional / Internacional.
- Sigue sin aparecer nada de **costos fijos de la empresa** (arriendo,
  nómina, servicios) — este archivo cubre costo de producto y costeo por
  colección, no el P&L completo. Sigue siendo indispensable para el punto de
  equilibrio (ver 5.3).

## 5. Checklist de información por tarea

### 5.1 Presupuesto en $ y unidades — consolidado y por canal

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Ventas y unidades reales 2025, mensual — Digital | Shopify (online) | Yo lo extraigo | Disponible ahora |
| Ventas y unidades reales 2025, mensual — Punto de venta | Shopify (draft orders/showroom) | Yo lo extraigo | Disponible ahora (aproximado) |
| Ventas y unidades reales 2025, mensual — Nacional | ¿World Office / Excel / facturación mayorista? | Natalia / contabilidad | **Pendiente, en camino** |
| Ventas y unidades reales 2025, mensual — Internacional | ¿World Office / Excel / registros de exportación? | Natalia / contabilidad | **Pendiente, en camino** |
| Meta de crecimiento 2026 por canal (%, o cifra objetivo) | Decisión estratégica | Natalia + asesor | Pendiente de definir |
| Estacionalidad esperada (curva mensual) | Se deriva del histórico por canal | Yo la calculo una vez haya histórico | Depende de lo anterior |
| Capacidad de producción / restricciones de oferta 2026 | Producción | Natalia | Pendiente |

### 5.2 Conexión $ ↔ unidades ↔ precio ↔ costo ↔ margen ↔ rotación

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Precio promedio por canal | Se calcula de ventas $ / unidades (una vez haya datos) | Yo lo calculo | Depende del histórico |
| Estructura de precios por referencia/categoría | Recibida dentro de los 4 archivos de costeo (ver sección 4) | Asesor / Natalia | **Recibida** — falta confirmar el mapeo canal↔columna de precio |
| Costo de producción (COGS) por prenda/categoría | 4 archivos de costeo (433 SKUs, ver `base-costos-precios.xlsx`) | Natalia | **Recibido, pendiente depurar doble conteo del costo indirecto** |
| Inventario y rotación por referencia/talla | Shopify (niveles de inventario) | Yo lo extraigo | Parcialmente disponible (ya lo usa el skill `reposicion-estrellas`) |
| Margen bruto por canal/categoría | Precio promedio − costo de producción | Yo lo calculo | Ya calculado por SKU en los archivos originales; falta validar con el costo indirecto corregido |

### 5.3 Puntos de equilibrio (por canal y consolidado)

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Costos fijos totales de la empresa | Contabilidad (World Office) | Natalia | **Pedir** |
| Costos fijos asignables al Punto de venta (arriendo showroom, personal, servicios) | Contabilidad | Natalia | **Pedir** |
| Costos fijos/variables asignables a Digital (plataforma, pauta, comisiones pasarela) | Contabilidad + marketing | Natalia | **Recibido en parte** — 30.18% de costo variable ya definido (hoja "Página Web"); falta el componente fijo |
| Costos de operar Nacional e Internacional (comisiones, logística, aranceles si aplica) | Contabilidad | Natalia | **Pedir** |
| Costo variable por unidad vendida (producción + comisión + envío + pasarela) por canal | Costeo + contabilidad | Natalia | **Recibido en parte** (costo de producto + indirecto por SKU, y 30.18% de Digital) — pendiente depurar y completar por canal |
| Cifra correcta del costo indirecto por prenda (sin doble conteo) | Natalia / producción | Natalia | **Pedir con prioridad** — bloquea usar cualquier margen o punto de equilibrio de esta base |

Con eso: punto de equilibrio en $ = costos fijos ÷ % margen de contribución;
en unidades = costos fijos ÷ margen de contribución por unidad. Se calcula
igual para cada canal y para la empresa consolidada.

### 5.4 Cuadro de control (seguimiento mensual)

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Real mensual $ y unidades — Digital y Punto de venta | Shopify | Yo lo automatizo | Se puede montar ya (extensión del skill `cierre-mensual`, separando por canal y agregando unidades) |
| Real mensual $ y unidades — Nacional e Internacional | Fuente por definir (ver 5.1) | Natalia | Pendiente |
| Costos reales mensuales (para margen real vs. presupuestado) | Contabilidad | Natalia | Pendiente |

## 6. Preguntas para resolver con el asesor / con Natalia

1. ¿Cómo se define exactamente cada canal, en especial **Nacional** e
   **Internacional**? ¿Coincide con mayorista nacional / exportación, o es
   otra cosa (p. ej. ventas online a clientes fuera de Colombia dentro de la
   misma tienda Shopify)?
2. Si Nacional/Internacional no están en Shopify, ¿dónde vive hoy esa
   información (Excel, correos, World Office, facturación manual)? ¿Ya hay
   historial 2025, o son canales nuevos que se abren en 2026?
3. ¿Cuál es la doble imputación exacta del costo indirecto, y cuál es el
   valor correcto por prenda para cada colección? Hipótesis a confirmar o
   descartar: el salario del Jefe de Producción, ya prorrateado aquí por
   prenda, ¿se contabiliza también como costo fijo de nómina en la
   contabilidad general?
4. ¿"Precio Multimarca" corresponde al canal **Nacional** del presupuesto
   (venta mayorista a boutiques dentro de Colombia)? ¿Y "Internacional" /
   "Distribuidor Inter 30%" corresponden al canal **Internacional**?
5. ¿`COSTOS_ANCIENT.xlsx` y `COSTOS_DICIEMBRE.xlsx` son la misma colección
   guardada dos veces, o debían tener datos distintos?
6. ¿Quién tiene los costos fijos de la empresa (arriendo, nómina, servicios)
   — Natalia directamente, contabilidad, o ya están consolidados en algún
   archivo de World Office?
7. ¿Se requiere separar Punto de venta por ubicación física exacta (lo que
   implicaría pedir el scope `read_locations` en Shopify), o basta con la
   aproximación por tipo de pedido (online vs. manual/showroom) que ya usa
   `cierre-mensual`?

## 7. Próximos pasos propuestos

1. **Natalia** confirma la doble imputación del costo indirecto (pregunta 3)
   — bloquea usar la base de costos para cualquier margen o punto de
   equilibrio real.
2. **Natalia / asesor** resuelven la definición de Nacional/Internacional y
   el mapeo de columnas de precio (preguntas 1, 2 y 4).
3. **Yo** extraigo de Shopify el histórico mensual 2025 (y lo corrido de
   2026) de Digital y Punto de venta — $ y unidades — como primer borrador de
   línea base.
4. **Natalia / contabilidad** entregan costos fijos de la empresa y
   cualquier histórico de ventas de Nacional/Internacional.
5. Con esos insumos, armamos juntos el presupuesto 2026 mensualizado y los
   puntos de equilibrio directamente en la pestaña "Presupuesto de ventas"
   del Google Sheet.
6. Se extiende el skill `cierre-mensual` (o se crea uno nuevo) para que el
   cuadro de control compare mensualmente presupuestado vs. real, por canal,
   en $ y en unidades, con precio promedio — automatizando el seguimiento.
