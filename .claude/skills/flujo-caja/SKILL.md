---
name: flujo-caja
description: "Refresca el dashboard de Flujo de Caja de Mompossina: saldo de banco+fiducuenta proyectado Sep-26 a Dic-27 (Plan Estratégico), ajustado con la venta real del mes en curso (cruzado con Presupuesto vs. Real para no doblar venta), cuentas por pagar reales con vencimientos (CONTROL DE PAGOS 2026.xlsx) y alertas de colchón mínimo dinámico (ligado a la estructura real de Personal+Admin), desviación vs. plan y excedente de caja. Republica el Artifact y la página pública (GitHub Pages). Usar siempre que el usuario pida: actualiza el flujo de caja, cómo va la caja, cuánta plata tenemos, refresca el flujo de caja, qué se vence de cuentas por pagar, o cuando se ejecute automáticamente por el scheduler semanal."
---

## Qué hace

Recalcula y republica el dashboard **Flujo de Caja**. Toda la aritmética vive
en **`compute.py`** (no el modelo) — mismo principio que `presupuesto-vs-real`,
`cierre-mensual` y `lovessence-dashboard`: el script arma el objeto `DATA`
completo y parchea `dashboards/flujo-caja.html` entre los marcadores
`<!-- DATA_START -->`/`<!-- DATA_END -->` (más
`<!-- TRAJECTORY_SVG_START -->`/`<!-- TRAJECTORY_SVG_END -->` para el gráfico
de trayectoria de 16 meses, generado en Python como SVG inline — sin
dependencias externas, nada de Chart.js).

Lo único que se edita a mano en cada corrida es la **narrativa**: el bloque
"Resumen ejecutivo" (`<ul class="exec-list">`) — informado por el resumen que
`compute.py` imprime en stdout.

Salidas que mantiene sincronizadas:
- **Artifact privado**: https://claude.ai/code/artifact/1f504f5a-c233-4205-b5f1-f7887ec5908d
  (reusar esta URL con `url:` en corridas siguientes)
- **Web pública (GitHub Pages)**: `dashboards/flujo-caja.html` dentro de
  `mtrujillo45/ventas-fla` → una vez fusionado a la rama por defecto del
  repo (confirmar con `git remote show origin` si cambia), queda en
  `https://mtrujillo45.github.io/Ventas-FLA/dashboards/flujo-caja.html`

## Decisiones confirmadas con el usuario (2026-09-08, actualizado 2026-09-11 — no cambiar sin re-confirmar)

- **Horizonte**: los 16 meses completos del plan (Sep-26 a Dic-27), no sólo
  Sep-Dic 2026 — el usuario quería visibilidad del runway completo para la
  junta, no sólo el trimestre en curso.
- **Alcance de CxP**: TODAS las categorías de `CONTROL DE PAGOS 2026.xlsx`
  (Personal, Administrativos, Mercadeo, Producción) se tratan como una sola
  bolsa de "cuentas por pagar" — el usuario decidió NO separar Préstamos en
  un panel aparte de servicio de deuda (de momento esa categoría no ha
  aparecido con saldo pendiente en el ledger).
- **Mecanismo de saldo real**: el dashboard arranca siempre con el saldo
  PROYECTADO (plan + ajuste por venta real del mes en curso). En cada
  corrida, preguntar al usuario si tiene el saldo real de banco+fiducuenta a
  la fecha de corte — si lo da, pasarlo con `--saldo-real` (reemplaza el
  ajustado del mes en curso y recalcula el offset hacia adelante). Si no lo
  da, el dashboard se publica igual, dejando claro en el texto que es
  proyección, no saldo bancario confirmado — **nunca inventar un saldo real**.
- **Alertas — dos capas independientes** (pedido explícito del usuario):
  - **Desviación vs. plan**: siempre visible (no sólo cuando hay problema) —
    compara el saldo del mes en curso (real si el usuario lo confirmó,
    ajustado si no) contra lo que el plan proyectaba para ese mismo mes.
    **Verde** si está por encima, **rojo** si está por debajo, mostrando
    siempre el monto de la diferencia. Reemplaza el antiguo "piso dinámico"
    (que sólo alertaba en rojo y no mostraba nada si todo iba bien — el
    usuario pidió ver también cuando vamos mejor que el plan).
  - **Colchón — ahora dinámico** (cambio del 2026-09-11, pedido explícito del
    usuario): ya NO es 6 × Personal+Admin fijo del plan ($60.3M/mes,
    estático). Se calcula como 6 × el promedio real de los últimos 2 meses
    calendario **completos** de GASTOS PERSONAL + GASTOS ADMINISTRATIVOS del
    ledger `CONTROL DE PAGOS 2026.xlsx` (ver `--personal-admin-ledger` abajo
    y el docstring de `compute.py` para la limpieza de datos necesaria). La
    razón: la estructura de personal cambia (ej. contratación de Isabella
    Aponte en sep-2026) y el colchón debe reflejar el gasto fijo real, no un
    número congelado del plan de hace meses. Si no se pasa
    `--personal-admin-ledger`, cae de vuelta al valor estático del plan
    (dejando explícito en el texto que es fallback, no el cálculo real).
    Alerta si cualquier mes de la trayectoria cae por debajo del colchón así
    calculado.
  - **Excedente**: NO se lista como alerta individual por mes (con la
    trayectoria tan holgada del plan, casi todos los meses calificaban y le
    restaba señal a las alertas que sí importan) — vive como panel de
    tendencia aparte ("Caja libre proyectada por mes"), calculado como
    saldo − colchón − obligaciones conocidas de ~60 días. Ver docstring de
    `compute.py` para el criterio exacto (1x colchón de holgura adicional) —
    es una propuesta inicial, ajustable si el usuario pide otro múltiplo.
- **CxP se muestra APARTE de la trayectoria de 16 meses**, no restada del
  saldo mes a mes — este registro (`CONTROL DE PAGOS 2026.xlsx`) sólo captura
  lo PENDIENTE (lo ya pagado no aparece), así que mezclarlo subestimaría el
  gasto real del mes. Sirve como vista táctica "qué se vence y cuándo", no
  como insumo de la trayectoria macro (que viene del plan). Evitar la palabra
  "ledger" en el HTML/labels visibles al usuario — causaba confusión
  ("¿ledger, qué es eso?"); usar "registro real de pagos" o similar.
- **Panel de CxP simplificado** (pedido explícito 2026-09-11): se quitaron
  del dashboard las tablas "Próximos 30 días" (detalle factura por factura)
  y "Top proveedores por saldo pendiente" — con el ledger creciendo, esas
  tablas alargaban demasiado la página y le quitaban interés a la junta. El
  panel de CxP quedó sólo con: buckets por antigüedad, por categoría, y
  facturas vencidas (las que sí importan con urgencia). `compute.py` ya no
  calcula ni retorna `topProveedores` ni `proximos30`.
- **Nuevo panel "Pagos proyectados por categoría"** (pedido 2026-09-11): tabla
  con los últimos ~4 meses de `pagos` del plan desagregados por categoría
  (Producción, Mercadeo y Ventas, Personal + Administrativos, IVA bimestral)
  — responde visualmente a la pregunta de si la proyección de flujo
  contempla todos los costos de producción/mercadeo/ventas/personal (sí, los
  4 están ahí). Generado por `build_pagos_breakdown()` en `compute.py`, va en
  `DATA.pagosBreakdown`.
- **Orden de secciones del HTML** (ajustado 2026-09-11): Estado de caja hoy →
  Semáforo de alertas → Trayectoria de caja → **Resumen ejecutivo** (subido,
  antes estaba casi al final) → Ajuste por venta real → Venta del mes en
  curso vs. plan → Cuentas por pagar → Pagos proyectados por categoría →
  Caja libre proyectada por mes.
- **Semáforo de alertas sin descripciones fijas de rojo/amarillo**: se quitó
  la leyenda estática ("🔴 significa esto, 🟡 significa esto") — sólo se
  listan alertas reales cuando existen (vencidas, colchón, desviación).
- **Etiquetas de KPI** (ajustadas 2026-09-11): "Saldo de caja" ahora dice
  explícitamente "Real" o "Planeado" según haya saldo confirmado por el
  usuario o no (antes decía "plan original" de forma genérica); "Piso más
  ajustado del periodo" pasó a llamarse "Saldo mínimo del periodo"; "CxP
  pendiente (real, ledger)" pasó a "CxP pendiente (real)". "Colchón fijo
  mínimo" se mantuvo igual (el usuario confirmó que ese label está bien —
  "fijo" se refiere a la política de 6 meses, no a que el monto esté
  congelado).
- **Ajuste por venta real**: Online/Showroom usan la proyección de cierre por
  ritmo diario cuando van por delante del presupuesto (mismo método que
  `presupuesto-vs-real`); Mayoristas nacionales/internacionales usan "Método
  1" (real + resto del presupuesto tal cual) porque son venta lumpy, no se
  proyectan por ritmo. El delta resultante se suma como **un único ajuste de
  nivel** a todos los meses desde el actual en adelante — NO es un reforecast
  mes a mes de todo el periodo (eso requeriría rehacer el plan completo, fuera
  de alcance).
- **Cobros extraordinarios** (ej. facturación FLA fuera de presupuesto) NUNCA
  se mezclan automáticamente en el ajuste de caja — el plan ya trae un
  supuesto de "cobros pendientes de agosto" que podría solaparse con esas
  facturas, y no hay forma confiable de saberlo sin confirmación contable. Se
  deja como nota de "pendiente de conciliar" en el resumen ejecutivo (ver
  ejemplo del 2026-09: FLA RFEL8320 $64.25M vs. el supuesto de $91.6M ya en
  el plan).

## Datos de referencia

| Concepto | Valor |
|---|---|
| Trayectoria de 16 meses | `.claude/skills/flujo-caja/plan_flujo_caja.json` — extraído una sola vez de la hoja "Flujo de Caja" de `Plan_Estrategico_Mompossina_2026_2027.xlsx` (Dropbox, versión SIN "Ajuste"). Estático dentro del periodo salvo que el usuario avise de un ajuste al plan. |
| Caja inicial del plan | $1,018M (banco $41M + fiducuenta $977M) |
| Colchón (dinámico desde 2026-09-11) | 6 × promedio real de los últimos 2 meses completos de Personal+Admin (`--personal-admin-ledger`). Fallback estático si no se pasa: 6 × $60.3M/mes del plan = $361.8M |
| CxP (registro real) | `CONTROL DE PAGOS 2026.xlsx` (Google Drive) — se re-extrae cada corrida, no es estático como el plan |
| Personal+Admin (registro real) | Mismo archivo `CONTROL DE PAGOS 2026.xlsx`, categorías GASTOS PERSONAL + GASTOS ADMINISTRATIVOS — se re-extrae cada corrida junto con CxP (ver limpieza obligatoria en el paso 4) |
| Venta del mes en curso | Reusa el `DATA` ya publicado en `dashboards/presupuesto-vs-real.html` (no se vuelve a consultar Shopify/mayoristas si ese dashboard ya se corrió hoy) |
| Script de cómputo | `.claude/skills/flujo-caja/compute.py` |
| Cuenta Google Drive | `googledrive_secern-burl` u operaciones@mompossina.com — el archivo CxP también es visible desde la cuenta personal del usuario |

## Procedimiento

Trabaja en un directorio temporal del scratchpad (p.ej. `$SCRATCH/flujo-caja`).

**1. Hora de corte** (Bogotá): `TZ="America/Bogota" date "+%Y-%m-%dT%H:%M:%S-05:00"`

**2. Preguntar al usuario si tiene el saldo real de banco+fiducuenta a hoy.**
Si lo da, guardarlo para pasarlo con `--saldo-real`. Si no, seguir sin él —
NUNCA inventarlo ni asumir que el proyectado es el real.

**3. Traer venta real del mes en curso.** Si `dashboards/presupuesto-vs-real.html`
ya se corrió hoy (mismo día del corte), extraer su bloque `DATA` (entre
`<!-- DATA_START -->`/`<!-- DATA_END -->`) y guardarlo como `ventas_mes.json`
— no volver a consultar Shopify/mayoristas. Si no se ha corrido hoy, correr
primero el skill `.claude/skills/presupuesto-vs-real/` (o al menos su
procedimiento de traída de datos) para tener un corte fresco.

**4. Traer CxP fresca de `CONTROL DE PAGOS 2026.xlsx`** (Google Drive, vía
Composio `GOOGLEDRIVE_DOWNLOAD_FILE` + `COMPOSIO_REMOTE_WORKBENCH` con
`openpyxl` — el archivo es un `.xlsx` subido a Drive, no una hoja nativa de
Sheets, así que `GOOGLESHEETS_*` falla con "document must not be an Office
file"). Recorrer cada pestaña mensual (Ene...mes actual), sección por sección
(los encabezados de sección son celdas en mayúsculas de la columna A:
GASTOS PERSONAL, GASTOS ADMINISTRATIVOS, PRESTAMOS, MERCADEO Y VENTAS,
PRODUCCION — puede haber más si el usuario agrega categorías), filtrando a
filas con `TOTAL PEND*PAGO` (columna M) > 0. Guardar como `cxp_pendientes.json`:
```json
[{"mes_tab":"SEPTIEMBRE","categoria":"PRODUCCION","empresa":"...",
  "factura":"...","valor_factura":123,"pendiente":123,"fecha_pago":"2026-09-15T00:00:00"}]
```
Ignorar pestañas que no sean meses del año en curso (ej. "ADP LA 49" es un
acuerdo de pago puntual ya vencido, no una categoría de gasto mensual).

**4b. Traer también Personal+Admin fresco para el colchón dinámico** (mismo
archivo, mismo recorrido de pestañas que el paso 4, pero esta vez **TODAS**
las filas de GASTOS PERSONAL + GASTOS ADMINISTRATIVOS de los últimos ~3
meses — no filtrar por pendiente > 0, aquí interesa el gasto total incurrido,
pagado o no). Guardar como `personal_admin_ledger.json`, incluyendo
`fecha_llego` (columna A) además de `fecha_pago`/`mes_tab`/`empresa`/`valor`:
```json
[{"mes_tab":"AGOSTO","categoria":"GASTOS PERSONAL","empresa":"...",
  "valor_factura":123,"fecha_llego":"2026-08-05T00:00:00", ...}]
```
`compute.py` hace la limpieza pesada (excluir filas de IVA/RT mal
clasificadas bajo GASTOS ADMINISTRATIVOS, y de-duplicar facturas viejas
re-listadas en varias pestañas por seguimiento manual — sólo cuenta filas
nativas de la pestaña de su propio mes). Ver el docstring de `compute.py`
antes de tocar esta lógica; es fácil reintroducir el bug de doble conteo si
se relaja el filtro de "nativo de su pestaña".

**5. Calcular y parchear el dashboard:**
```
python3 .claude/skills/flujo-caja/compute.py \
  --plan-cashflow .claude/skills/flujo-caja/plan_flujo_caja.json \
  --ventas-mes $SCRATCH/flujo-caja/ventas_mes.json \
  --cxp $SCRATCH/flujo-caja/cxp_pendientes.json \
  --personal-admin-ledger $SCRATCH/flujo-caja/personal_admin_ledger.json \
  --now "<hora ISO Bogotá del paso 1>" \
  --cushion-months 6 \
  --html dashboards/flujo-caja.html \
  [--saldo-real <monto si el usuario lo dio en el paso 2>]
```
Si se omite `--personal-admin-ledger`, el colchón cae de vuelta al valor
estático del plan ($60.3M/mes) — sólo aceptable si el ledger no está
disponible ese corte, y hay que decírselo explícitamente al usuario.

Revisa el resumen impreso (saldo hoy, ajuste por canal, colchón y su fuente
—dinámica o fallback—, desviación vs. plan, CxP pendiente/vencida, caja
libre, alertas). Si algo se ve fuera de lugar (un ajuste absurdamente grande,
CxP vencida que no cuadra, un mes de Personal+Admin que parece duplicado),
no publiques — revisa los JSON de entrada antes de tocar `compute.py`.

**6. Reescribir a mano el Resumen ejecutivo** (`<ul class="exec-list">`),
usando los números que imprimió el script: saldo hoy y si es real o
proyectado, estado del colchón, facturas vencidas más urgentes, hallazgos de
venta del mes que afecten la caja (ej. un canal en $0 que compromete el
rezago de exportaciones del mes siguiente), acción recomendada, y cualquier
nota de conciliación pendiente (cobros extraordinarios vs. supuestos del
plan). No toques el resto del HTML — todo lo demás se recalcula solo desde
`DATA`.

**7. Screenshot antes de publicar.** Playwright/Chromium
(`/opt/pw-browsers/chromium`, `NODE_PATH=$(npm root -g)`), claro y oscuro,
revisando que no haya errores de JS (`pageerror`) y que el gráfico de
trayectoria y las tablas de CxP se vean bien — es una página densa en datos.

**8. Republicar el Artifact:**
- `file_path`: `dashboards/flujo-caja.html`
- `url`: `https://claude.ai/code/artifact/1f504f5a-c233-4205-b5f1-f7887ec5908d`
- `favicon`: omitir en redeploys (ya quedó fijado como 💧)

**9. Publicar/actualizar como página pública (GitHub Pages)**, dentro de
`ventas-fla`:
```
git add dashboards/flujo-caja.html .claude/skills/flujo-caja/
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "Actualizar flujo de caja (<fecha>)"
git push origin <rama de trabajo>   # reintenta con backoff si falla
```
Si el trabajo se hizo en una rama distinta a la rama por defecto del repo,
abrir un Pull Request hacia la rama por defecto y fusionarlo — una sesión
nueva parte de la rama por defecto, así que el dashboard sólo queda "vivo" en
GitHub Pages una vez fusionado.

**10. Reportar en el chat**: saldo hoy (real o proyectado), estado del
colchón, facturas vencidas y su total, caja libre hoy, y la acción #1
recomendada del corte.

## Notas

- **`plan_flujo_caja.json` es estático** dentro del periodo Sep-26/Dic-27 —
  no volver a leer el Excel de Dropbox cada corrida, salvo que el usuario
  avise de un ajuste al plan o pida extender el horizonte más allá de
  dic-2027.
- **No inventar el saldo real, ni el CxP, ni la venta del mes**: si no se
  puede acceder a `CONTROL DE PAGOS 2026.xlsx`, o a un corte fresco de
  `presupuesto-vs-real`, avisar al usuario y no publicar con datos
  estimados o de una corrida vieja sin decirlo explícitamente.
- **Sin Chart.js ni dependencias externas**: igual que el resto de la
  familia de dashboards, todos los gráficos son SVG inline generados por
  `compute.py` o por el propio JS del HTML a partir de `DATA`.
- **Refresco automático**: rutina semanal programada (ver `create_trigger`
  en la sesión que creó este skill, 2026-09-08) — si se pierde o se quiere
  cambiar la cadencia, recrearla con `mcp__Claude_Code_Remote__create_trigger`
  apuntando a este mismo procedimiento.
