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

## 4. Checklist de información por tarea

### 4.1 Presupuesto en $ y unidades — consolidado y por canal

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Ventas y unidades reales 2025, mensual — Digital | Shopify (online) | Yo lo extraigo | Disponible ahora |
| Ventas y unidades reales 2025, mensual — Punto de venta | Shopify (draft orders/showroom) | Yo lo extraigo | Disponible ahora (aproximado) |
| Ventas y unidades reales 2025, mensual — Nacional | ¿World Office / Excel / facturación mayorista? | Natalia / contabilidad | **Falta definir fuente** |
| Ventas y unidades reales 2025, mensual — Internacional | ¿World Office / Excel / registros de exportación? | Natalia / contabilidad | **Falta definir fuente** |
| Meta de crecimiento 2026 por canal (%, o cifra objetivo) | Decisión estratégica | Natalia + asesor | Pendiente de definir |
| Estacionalidad esperada (curva mensual) | Se deriva del histórico por canal | Yo la calculo una vez haya histórico | Depende de lo anterior |
| Capacidad de producción / restricciones de oferta 2026 | Producción | Natalia | Pendiente |

### 4.2 Conexión $ ↔ unidades ↔ precio ↔ costo ↔ margen ↔ rotación

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Precio promedio por canal | Se calcula de ventas $ / unidades (una vez haya datos) | Yo lo calculo | Depende del histórico |
| Estructura de precios por referencia/categoría | "la estructura de precios que venimos desarrollando" (mencionada en el correo) | Asesor | Pedir el documento/avance actual |
| Costo de producción (COGS) por prenda/categoría | Producción / costeo | Natalia | **No está en ningún sistema conectado — pedir** |
| Inventario y rotación por referencia/talla | Shopify (niveles de inventario) | Yo lo extraigo | Parcialmente disponible (ya lo usa el skill `reposicion-estrellas`) |
| Margen bruto por canal/categoría | Precio promedio − costo de producción | Yo lo calculo | Depende de COGS |

### 4.3 Puntos de equilibrio (por canal y consolidado)

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Costos fijos totales de la empresa | Contabilidad (World Office) | Natalia | **Pedir** |
| Costos fijos asignables al Punto de venta (arriendo showroom, personal, servicios) | Contabilidad | Natalia | **Pedir** |
| Costos fijos/variables asignables a Digital (plataforma, pauta, comisiones pasarela) | Contabilidad + marketing | Natalia | **Pedir** |
| Costos de operar Nacional e Internacional (comisiones, logística, aranceles si aplica) | Contabilidad | Natalia | **Pedir** |
| Costo variable por unidad vendida (producción + comisión + envío + pasarela) por canal | Costeo + contabilidad | Natalia | **Pedir** |

Con eso: punto de equilibrio en $ = costos fijos ÷ % margen de contribución;
en unidades = costos fijos ÷ margen de contribución por unidad. Se calcula
igual para cada canal y para la empresa consolidada.

### 4.4 Cuadro de control (seguimiento mensual)

| Dato necesario | Fuente | Responsable | Estado |
|---|---|---|---|
| Real mensual $ y unidades — Digital y Punto de venta | Shopify | Yo lo automatizo | Se puede montar ya (extensión del skill `cierre-mensual`, separando por canal y agregando unidades) |
| Real mensual $ y unidades — Nacional e Internacional | Fuente por definir (ver 4.1) | Natalia | Pendiente |
| Costos reales mensuales (para margen real vs. presupuestado) | Contabilidad | Natalia | Pendiente |

## 5. Preguntas para resolver con el asesor / con Natalia

1. ¿Cómo se define exactamente cada canal, en especial **Nacional** e
   **Internacional**? ¿Coincide con mayorista nacional / exportación, o es
   otra cosa (p. ej. ventas online a clientes fuera de Colombia dentro de la
   misma tienda Shopify)?
2. Si Nacional/Internacional no están en Shopify, ¿dónde vive hoy esa
   información (Excel, correos, World Office, facturación manual)? ¿Ya hay
   historial 2025, o son canales nuevos que se abren en 2026?
3. ¿Existe ya un documento de la "estructura de precios" que se menciona en
   el correo? Si sí, compartirlo — ahorra tener que reconstruir precio
   promedio y margen desde cero.
4. ¿Quién tiene los costos fijos y el costeo de producción (COGS) por
   categoría — Natalia directamente, contabilidad, o el asesor ya los tiene
   consolidados en algún archivo?
5. ¿Se requiere separar Punto de venta por ubicación física exacta (lo que
   implicaría pedir el scope `read_locations` en Shopify), o basta con la
   aproximación por tipo de pedido (online vs. manual/showroom) que ya usa
   `cierre-mensual`?

## 6. Próximos pasos propuestos

1. **Natalia / asesor** resuelven las preguntas de la sección 5 (sobre todo
   la definición de Nacional/Internacional y su fuente de datos).
2. **Yo** extraigo de Shopify el histórico mensual 2025 (y lo corrido de
   2026) de Digital y Punto de venta — $ y unidades — como primer borrador de
   línea base.
3. **Natalia / contabilidad** entregan costos fijos, costeo de producción y
   cualquier histórico de Nacional/Internacional.
4. Con esos tres insumos, armamos juntos el presupuesto 2026 mensualizado y
   los puntos de equilibrio directamente en la pestaña "Presupuesto de
   ventas" del Google Sheet.
5. Se extiende el skill `cierre-mensual` (o se crea uno nuevo) para que el
   cuadro de control compare mensualmente presupuestado vs. real, por canal,
   en $ y en unidades, con precio promedio — automatizando el seguimiento.
