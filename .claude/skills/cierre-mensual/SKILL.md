---
name: cierre-mensual
description: "Genera el informe de cierre mensual de ventas de Mompossina (Shopify, todos los canales) con desglose financiero (subtotal, IVA y envío separados), gráfico de ventas diarias y top 20 productos. Solo venta real del mes, sin proyección. Incluye capítulos pendientes para canal mayorista y World Office hasta que se conecten. Republica el Artifact y la página pública (GitHub Pages). Usar siempre que el usuario pida: cierre de mes, cierre mensual, informe mensual de ventas, cómo cerró el mes, resumen financiero del mes, consolidado mensual, o cuando se ejecute automáticamente por el scheduler a inicio de mes."
---

## Qué hace

Recalcula y republica el **informe de cierre mensual** de Mompossina. Toda la
aritmética la hace **`compute.py`** (no el modelo): así se procesa el mes
completo sin errores de suma manual — mismo principio que `monitor-medellin`.

Cubre **solo Shopify** (tienda online + pedidos manuales/showroom vía app y
POS, combinados). El canal **mayorista** y **World Office** (contabilidad)
son capítulos aparte marcados como *pendientes* en el dashboard hasta que se
defina cómo conectarlos — no se debe inventar ni estimar esa data.

Salidas que mantiene sincronizadas:
- **Artifact privado**: (pegar aquí la URL la primera vez que se publique con la herramienta Artifact, y reusarla en corridas siguientes con `url:` para actualizar el mismo link en vez de crear uno nuevo)
- **Web pública (GitHub Pages)**: pendiente de decidir rama/repo — ver nota abajo.

## Principio de diseño (leer antes de modificar)

**`compute.py` calcula y suma; el modelo orquesta y narra.** El modelo NO
suma pedidos ni ventas a mano. Si algo no cuadra, se arregla el script, no el
resultado.

**Desglose financiero (confirmado con el usuario, no cambiar sin pedir
confirmación):**
- **Ventas brutas** = `gross_sales` — catálogo antes de descuentos/devoluciones.
- **Subtotal (sin IVA)** = `net_sales` — bruto menos descuentos y devoluciones,
  SIN IVA ni envío.
- **IVA** = `taxes` — aparte, tal cual lo separa ShopifyQL.
- **Envío** = `shipping_charges` — aparte del IVA.
- **Ventas totales** = `total_sales` = subtotal + IVA + envío = lo cobrado al
  cliente.

No se aplica ningún factor manual (a diferencia de `monitor-medellin`, que sí
necesita dividir por 1.19 porque parte de `originalTotalSet` con IVA incluido
de la API de pedidos). Aquí se usa `run-analytics-query` (ShopifyQL), que ya
entrega impuestos y envío como columnas independientes.

**Solo venta real:** este informe NO incluye proyección ni forecast — a
diferencia del dashboard de Medellín, que sí tiene una sección de modelo
proyectado. No agregar esa sección aquí aunque se reutilice estilo visual de
ese dashboard.

**Qué NO llevar del estilo Medellín** (decisión explícita del usuario):
- Nada de desglose por talla/prenda con inventario y sell-through.
- Nada de alertas de inventario (agotado/crítico).
- Nada de desglose por canal de Shopify individual (Online Store, Draft
  Orders, Mobile, etc.) — en su lugar va el gráfico de ventas diarias.

**Qué SÍ llevar:**
- Tarjetas KPI con una frase corta debajo de cada valor explicando qué es
  (mismo patrón que las tarjetas de Medellín, pero con la explicación
  agregada — ver `build_kpis()` en `compute.py`).
- Ranking horizontal de productos (mismo componente visual `.hbar-row` que
  usa Medellín para su ranking por producto), aquí ampliado a top 20 y
  ordenado por venta bruta.
- Paleta, tipografía y tokens de tema claro/oscuro: tomados directamente del
  dashboard de Medellín (`--series-1`, `--series-2`, `--good/warning/critical`,
  etc.) para que ambos dashboards se vean como parte de la misma familia.

## Datos de referencia

| Concepto | Valor |
|---|---|
| Cobertura | Shopify, todos los canales combinados (online + manual/showroom) |
| Fuera de alcance (capítulos pendientes) | Canal mayorista, World Office |
| Ranking de productos | Top 20 por `gross_sales`, todos los canales |
| Gráfico diario | `total_sales` por día (con IVA y envío) |
| Dashboard fuente (doc completo) | `dashboard/cierre-mensual.html` |
| Script de cómputo | `.claude/skills/cierre-mensual/compute.py` |

## Procedimiento

Trabaja en un directorio temporal del scratchpad para los JSON crudos (p.ej.
`$SCRATCH/cierre-mensual`).

**1. Calcular el rango del mes a cerrar.** Por defecto, el mes calendario
completo más reciente ya terminado (si hoy es 2 de agosto, el cierre es
julio completo: 1–31 de julio). Si el usuario pide un mes específico, usar
ese rango.

```
python3 -c "
from datetime import date
import calendar
today = date.today()
y, m = today.year, today.month
# mes anterior completo
m -= 1
if m == 0: m, y = 12, y - 1
last_day = calendar.monthrange(y, m)[1]
print(f'SINCE={y:04d}-{m:02d}-01')
print(f'UNTIL={y:04d}-{m:02d}-{last_day:02d}')
"
```

**2. Hora de Bogotá** (sello del informe):
```
TZ="America/Bogota" date "+%Y-%m-%dT%H:%M:%S-05:00"
```

**3. Ejecutar las 4 consultas ShopifyQL en paralelo** con
`mcp__Shopify__run-analytics-query`, y guardar CADA respuesta completa (con
sus campos `columns`/`rows`, tal cual la devuelve la herramienta) con Write
en archivos separados del scratchpad:

```
totals.json   → FROM sales SHOW orders, gross_sales, discounts, returns, net_sales, shipping_charges, taxes, total_sales SINCE {SINCE} UNTIL {UNTIL}

daily.json    → FROM sales SHOW total_sales TIMESERIES day SINCE {SINCE} UNTIL {UNTIL}

products.json → FROM sales SHOW gross_sales, net_sales, orders GROUP BY product_title ORDER BY gross_sales DESC LIMIT 20 SINCE {SINCE} UNTIL {UNTIL}

units.json    → FROM inventory SHOW inventory_units_sold SINCE {SINCE} UNTIL {UNTIL}
```

**4. Calcular y parchear el dashboard:**
```
python3 .claude/skills/cierre-mensual/compute.py \
  --totals $SCRATCH/cierre-mensual/totals.json \
  --daily $SCRATCH/cierre-mensual/daily.json \
  --products $SCRATCH/cierre-mensual/products.json \
  --units $SCRATCH/cierre-mensual/units.json \
  --since {SINCE} --until {UNTIL} --label "{Mes en español} {Año}" \
  --html dashboard/cierre-mensual.html \
  --now "<hora ISO del paso 2>"
```
Revisa el resumen impreso (ventas brutas, subtotal, IVA, envío, total,
pedidos, unidades, producto #1). Si algo se ve fuera de lugar (p.ej. IVA
negativo, total menor al subtotal), no publiques — revisa los JSON de
entrada antes de tocar `compute.py`.

**5. Republicar el Artifact** con la herramienta Artifact:
- `file_path`: `dashboard/cierre-mensual.html`
- `url`: la del Artifact ya publicado (una vez exista, guardarla en este
  SKILL.md en la sección "Qué hace" para reusarla en corridas futuras)
- `favicon`: 🧾 · `title`: `Mompossina — Cierre Mensual de Ventas`

**6. Publicar como página pública (GitHub Pages).** Esto quedó pendiente de
confirmar con el usuario: a diferencia de `monitor-medellin` (que publica en
un repo/rama externos llamados "Web"), este skill vive en el repo
`mtrujillo45/ventas-fla`, que es el único al que esta sesión tiene acceso.
Antes de hacer push, confirmar con el usuario:
  - ¿En qué rama de este repo se publica (o se crea una rama `gh-pages` /
    `docs`)?
  - ¿GitHub Pages ya está habilitado en este repo, o hay que activarlo
    (Settings → Pages) — eso lo debe hacer el usuario, no esta sesión?
Una vez confirmado, documentar aquí la rama y la URL final, siguiendo el
mismo patrón de `monitor-medellin` (archivo `index.html` con el head
envolvente + `dashboard/cierre-mensual.html` como fuente).

**7. Reportar** en el chat: ventas totales, subtotal, IVA, envío, pedidos,
unidades, producto #1 del ranking, y recordar el estado pendiente de
mayorista y World Office.

## Notas

- **Reembolsos:** ShopifyQL ya los descuenta en `returns`; no hay que
  restarlos aparte.
- **Sin proyección:** este informe es solo venta real. No agregar modelos de
  forecast aunque se reutilice estilo del dashboard de Medellín.
- **Mayorista / World Office:** nunca completar esas secciones con datos
  inventados o estimados. Se quedan marcadas "pendiente" hasta tener una
  fuente real conectada (credenciales, CSV, API o reenvío de correo).
- **Refresco automático:** desactivado por defecto. Para correr cada cierre
  de mes automáticamente, crear un cron/routine que invoque este skill al
  inicio del mes siguiente.
