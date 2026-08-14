---
name: las-super-dashboard
description: "Genera y actualiza el dashboard de ventas de Las Super Empanadas a partir del libro diario de caja en Dropbox (carpeta LAS SUPER, archivo Caja LS 2026.xlsx): ventas por día, semana, mes y acumulado del año, por empleada (Yaneth y Lina), Estado de Resultados mensual, comparativo histórico de ventas y utilidad de socios (2020-2026), y alertas de punto de equilibrio / food cost / caja negativa / retiros de socios excesivos. Republica el Artifact y el archivo del repo. SOLO correr cuando el usuario lo pida explícitamente (ej. 'corre el dashboard de Las Super', 'actualiza las ventas de las empanadas', 'cómo va el negocio de Las Super') — no es una rutina automática ni programada."
---

## Qué hace

Recalcula y republica el **dashboard de ventas de Las Super Empanadas**. Toda
la aritmética la hace **`compute.py`** (no el modelo): parsea el texto plano
extraído del Excel, agrega, arma el Estado de Resultados y genera el HTML
completo — mismo principio que `cierre-mensual`.

Cubre:
- Ventas por día, semana (lunes–domingo), mes y acumulado del año.
- Ventas por empleada (Yaneth y Lina — únicas que registran ventas en el
  mostrador; Jochen, Mauricio y Socios solo aparecen en gastos/nómina).
- Estado de Resultados mensual 2026 (Ventas, CMV, Utilidad Bruta, Nómina,
  Gastos Operativos, Producto malo, Impuestos, Utilidad Operativa, Retiros de
  socios, Flujo libre de caja).
- Comparativo histórico 2020-2026 de ventas (total anual y mismo período) y
  de utilidad de socios.
- Alertas/semáforos basados en el punto de equilibrio y los benchmarks que ya
  están calculados en el propio archivo.

Salidas que mantiene sincronizadas:
- **Archivo en el repo**: `dashboards/las-super.html`.
- **Artifact privado**: https://claude.ai/code/artifact/ead95ea4-af2f-49af-a407-94f8e6d4daab
  (reusar esta URL en corridas siguientes con `url:` para actualizar el mismo
  link en vez de crear uno nuevo).

**No es una rutina automática.** El usuario fue explícito: quiere ser quien
dé la indicación cada vez. No crear un cron/trigger para este skill a menos
que lo pida directamente.

## Principio de diseño (leer antes de modificar)

**`compute.py` calcula y suma; el modelo orquesta y reporta.** El modelo NO
suma movimientos de caja a mano. Si algo no cuadra, se arregla el script, no
el resultado. `compute.py` regenera el HTML completo desde cero en cada
corrida (no hace parches con marcadores como `cierre-mensual`): casi todo el
contenido de este dashboard es data-driven, así que regenerar todo es más
simple y evita que el HTML y los datos se desincronicen.

**Fuente de datos confirmada con el usuario (no cambiar sin pedir
confirmación):**
- **Archivo oficial**: `/LAS SUPER/Caja LS 2026.xlsx` en Dropbox (NO usar
  `/LAS SUPER/Copia de Caja LS 2026mtr.xlsx`, que es una copia de trabajo).
- **Ventas y Estado de Resultados 2026**: se calculan SIEMPRE desde la hoja
  **"Caja"** (el libro diario), sumando por `Centro Costos`. Las hojas "ER" y
  "Venta Mensual" tienen sus propias tablas dinámicas/pivote que a veces NO
  coinciden entre sí para el mismo mes (se confirmó con el usuario: son cachés
  que pueden quedar desactualizados). La hoja "Caja" es la única fuente de
  verdad para 2026.
- **Ventas = "Centro Costos" == "venta", con su signo real (columna Valor),
  SIN filtrar por la columna Entrada/Salida.** Esa columna tiene errores de
  captura: ~26 filas de venta en 2026 están marcadas "Salida" con un monto
  positivo. Se verificó fila por fila contra la columna "Saldo caja" (1,798
  transiciones consecutivas del libro diario, cero excepciones) que el saldo
  siempre se mueve exactamente según el signo impreso del Valor — así que el
  signo de Valor manda, no la etiqueta de texto. Con esta regla, los totales
  mensuales coinciden casi al peso con el propio pivote de la hoja "ER" y con
  el resumen narrativo de la hoja "Análisis" (ambos, fuentes independientes
  dentro del mismo archivo). **Si esto se vuelve a revisar en el futuro y los
  números no cuadran, sospechar primero de la columna Entrada/Salida antes que
  de la lógica de suma.**
- **Histórico 2020-2025**: NO existe libro diario detallado de esos años en
  este archivo — se toma tal cual de la hoja **"Venta Mensual"** (tablas
  "VENTAS" y "UTILIDAD SOCIOS" por año/mes). Para 2026 se usa el cálculo desde
  "Caja" (más confiable), no la columna 2026 de "Venta Mensual".
- **"Utilidad" histórica** = Utilidad de Socios (retiros/reparto a socios),
  confirmado con el usuario como proxy porque es la única cifra de
  rentabilidad con histórico completo 2020-2025 en el archivo. No es Utilidad
  Neta contable.
- **Comparativo por año**: se muestran DOS vistas — total anual (2026 marcado
  como parcial, sin badge de crecimiento porque compararía un año completo
  contra unos pocos meses) y "mismo período" (enero–mes actual, para todos los
  años, comparación justa con badge de crecimiento).
- **Empleadas**: solo Yaneth y Lina en "ventas por empleada" (confirmado con
  el usuario). Jochen, Mauricio, Socios, Andrimar y Paola aparecen ocasional-
  mente en la columna `Encargado` pero solo en filas de gasto, no de venta.
- **Punto de equilibrio**: se lee dinámicamente de la hoja "P.E" (buscando las
  etiquetas "COSTO FIJO TOTAL MES", "Venta minima (PuntoEq)" y "Venta Diaria"
  en el texto plano) — no está hardcodeado, para que si cambian salarios o
  arriendo el dashboard se actualice solo. Si esas etiquetas no se encuentran,
  `compute.py` falla con un error claro en vez de publicar con datos viejos.
- **Alertas/semáforos**: confirmado con el usuario — sí quiere alertas
  automáticas, usando los mismos umbrales que ya calculó el archivo (venta
  diaria/mensual vs. punto de equilibrio, food cost 28-35% saludable / ≥45%
  alto, retiros de socios ≤30% de la utilidad operativa saludable).

**Paleta**: colores vivos (amarillo/anaranjado/rojo), pedido explícito del
usuario — `--series-1` naranja, `--series-2` rojo, `--series-3` amarillo/oro,
semáforo `--good` verde / `--warning` amarillo / `--critical` rojo. Tokens de
tema claro/oscuro en el `CSS` de `compute.py`, mismo patrón de variables que
`medellin-mi-amor.html` y `cierre-mensual.html` para que los tres dashboards
se sientan de la misma familia, pero con esta paleta propia (no la de
Mompossina).

**Cuidado con `text-anchor` en los SVG**: hay reglas CSS `.chart-axis` /
`.chart-point-label { text-anchor:middle }` que le ganan en especificidad al
atributo `text-anchor="end"` puesto directamente en el `<text>` (los
atributos de presentación SVG pierden contra reglas de hoja de estilo). Por
eso las etiquetas que necesitan alinearse a la izquierda/derecha usan
`style="text-anchor:..."` inline (gana por especificidad) a través del helper
`label_anchor()`, no el atributo suelto. Si se agregan más etiquetas de texto
a los SVG, seguir ese mismo patrón o se cortan en el borde del gráfico.

## Datos de referencia

| Concepto | Valor |
|---|---|
| Fuente | Dropbox: `/LAS SUPER/Caja LS 2026.xlsx` (carpeta LAS SUPER) |
| Hoja de ventas/ER | "Caja" (libro diario) |
| Hoja de histórico | "Venta Mensual" (tablas VENTAS y UTILIDAD SOCIOS, 2020-2026) |
| Hoja de punto de equilibrio | "P.E" |
| Empleadas en "por empleado" | Yaneth, Lina |
| Dashboard (doc completo) | `dashboards/las-super.html` |
| Script de cómputo | `.claude/skills/las-super-dashboard/compute.py` |

## Procedimiento

Trabaja en un directorio temporal del scratchpad (p.ej. `$SCRATCH/las-super`).

**1. Traer el archivo más reciente de Dropbox.** Usar
`mcp__Dropbox__fetch` con `id: "/LAS SUPER/Caja LS 2026.xlsx"` (la ruta
completa, no el ID de espacio de nombres, para no depender de una cuenta
específica). Si el resultado es grande, la herramienta lo guarda en un
archivo de resultados y hay que extraer el campo `.text` con `jq`:
```
jq -r '.text' <ruta-del-archivo-de-resultado> > $SCRATCH/las-super/caja_texto.txt
```
Guardar también el `metadata.server_modified` de la respuesta — se usa como
"archivo modificado" en el encabezado del dashboard.

**2. Hora de Bogotá** (sello de generación):
```
TZ="America/Bogota" date "+%Y-%m-%dT%H:%M:%S-05:00"
```

**3. Calcular y generar el HTML:**
```
python3 .claude/skills/las-super-dashboard/compute.py \
  --text $SCRATCH/las-super/caja_texto.txt \
  --html dashboards/las-super.html \
  --now "<hora ISO del paso 2>" \
  --source-modified "<server_modified del paso 1>"
```
Revisa el resumen impreso: transacciones parseadas, punto de equilibrio,
venta acumulada del año, ventas por mes, alertas generadas. Si algo se ve
fuera de lugar (una alerta que no tiene sentido, un mes con venta en cero
que debería tener datos, un error de "no se encontró la hoja X"), no
publiques — revisa el texto extraído antes de tocar `compute.py`. El script
falla explícitamente (`SystemExit`) si no encuentra las hojas o etiquetas
esperadas, en vez de publicar con datos parciales o viejos.

**4. Republicar el Artifact** con la herramienta Artifact:
- `file_path`: `dashboards/las-super.html`
- `url`: `https://claude.ai/code/artifact/ead95ea4-af2f-49af-a407-94f8e6d4daab`
  (si esta sesión publicó el archivo por primera vez en su propia conversación,
  se puede omitir `url` y republicar por `file_path` alcanza; pero desde
  cualquier otra conversación hay que pasar esta URL explícitamente o se crea
  un Artifact nuevo en vez de actualizar este)
- `favicon`: 🌶️ (el `<title>` ya está en el HTML: `Las Super Empanadas`)

**5. Commit y push** al branch de trabajo actual (o el que indique el
usuario si es distinto):
```
git add dashboards/las-super.html .claude/skills/las-super-dashboard/
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "Actualizar dashboard de Las Super (<fecha>)"
git push origin <rama de trabajo>   # reintenta con backoff si falla
```

**6. Reportar** en el chat: venta acumulada del año, venta del mes en curso
vs. meta, alertas críticas/de advertencia generadas, y el link del Artifact.

## Notas

- **No es automático.** Correr solo cuando el usuario lo pida explícitamente.
- **No inventar datos de mayorista, otros locales o años sin fuente.** Si el
  usuario pide algo que no está en "Caja LS 2026.xlsx" (p.ej. otro punto de
  venta), decirlo claramente en vez de estimar.
- **Reconciliación de caja vs. P&L**: hay filas "venta"+"Salida" grandes que,
  según la hipótesis más plausible (verificada solo indirectamente, no
  confirmada con el usuario), podrían ser consignaciones/transferencias del
  efectivo del mostrador — no se tratan como gasto ni se restan de ventas,
  solo se incluyen con su signo real. Si el usuario confirma o corrige esta
  interpretación, actualizar esta nota y, si aplica, la lógica de
  `is_sale()`.
- **`--text` es el paso más frágil**: si Dropbox cambia el formato de
  extracción, o el usuario reordena/renombra hojas en el Excel, `compute.py`
  puede fallar en `slice_sheet()`/`find_labeled_value()`. Los mensajes de
  error están escritos para señalar exactamente qué hoja o etiqueta no se
  encontró.
