---
name: informe-canales
description: Envía por correo el informe de alertas de cumplimiento por canal de Mompossina al equipo comercial (Online, Showroom, Mayoristas nacionales e internacionales), con una imagen por canal ($ y unidades vs. meta del mes, ritmo y semáforo) y un resumen corto. Corre automáticamente los lunes 8:00 am y miércoles 4:00 pm (hora Bogotá). Usar siempre que el usuario pida: informe por canal, alertas por canal, enviar el informe al equipo, correo de cumplimiento a las responsables, o cuando lo dispare el scheduler.
---

## Qué hace

Refresca el dashboard Presupuesto vs. Real (skill `presupuesto-vs-real`) y, a
partir de su `DATA_BUNDLE`, arma y **envía** un correo al equipo comercial:

- Un correo para todo el equipo (confirmado con el usuario 2026-10-13), desde
  **operaciones@mompossina.com** (cuenta Composio Gmail `gmail_rebold-risp`).
- Una sección por grupo de responsables, con un resumen de 1-2 frases y una
  imagen (tarjeta) con ventas en pesos y unidades vs. la meta del mes, la marca
  de lo esperado a la fecha, el ritmo y el semáforo:

| Grupo | Canales | Responsables |
|---|---|---|
| Online | `online` | Verónica y Laura |
| Showroom | `showroom` | Greisy |
| Mayoristas nacionales e internacionales | `nacional`, `internacional` | Camila y Natalia |

Grupos y nombres de responsables en `equipo.json` (definido por el usuario
2026-10-13). **Los correos NO están en el repo** (es público, y tres son correos
personales): viven en el prompt privado de las dos Routines "Informe por canal"
(lunes `trig_01L5K7qA74pk1hTVs1pbsh8x`, miércoles `trig_01DvmN5uCCJ9puppmKw5vWhZ`),
decidido con el usuario 2026-10-13. Para cambiar un correo se actualizan ambas
Routines (`update_trigger` con el prompt completo). Nunca escribir los correos en
archivos del repo, commits ni PRs. En una corrida manual fuera de las Routines,
pedirle los correos al usuario.

## Horario (confirmado 2026-10-13)

- **Lunes 8:00 am** y **miércoles 4:00 pm**, hora Bogotá. Las Routines arrancan
  ~15 minutos antes para que el correo llegue cerca de esa hora.
- **Corte = cierre del día anterior** (domingo 23:59 los lunes, martes 23:59 los
  miércoles). Regla pedida por el usuario el 2026-10-13: medir el ritmo con días
  completos, sin contar un día que apenas empieza (si no, el ritmo se ve
  artificialmente bajo). Shopify se consulta hasta las 23:59:59 del día anterior y
  `compute.py` corre con `--now <día anterior>T23:59:59-05:00`.

## Procedimiento (corrida automática, sin usuario presente)

1. **Repo al día.** Rama de trabajo nueva desde la rama por defecto
   (`claude/medellin-dashboard-composio-shopify-9b1mlm`, confirmar con
   `git remote show origin`).

2. **Refrescar Presupuesto vs. Real** siguiendo `.claude/skills/presupuesto-vs-real/SKILL.md`
   (pasos 1-6), con estas reglas para la corrida desatendida:
   - Corte al cierre del día anterior (ver arriba).
   - Si cambió el mes desde el último corte (p.ej. el lunes 2 de noviembre corta
     al 1-nov, pero el dashboard sigue en octubre): congelar primero el mes que
     cierra con `freeze_month.py` **corriendo antes un último corte de ese mes al
     día 31 23:59** (para que lo congelado sea el mes completo).
   - Insumos de mayoristas del mes: partir de
     `.claude/skills/presupuesto-vs-real/insumos/<YYYY-MM>/wholesale.json` y
     `extraordinary.json` (versionados en el repo) y **agregar solo** las facturas
     nuevas de Drive y los pedidos nuevos de Falabella-Shopify; guardar los JSON
     actualizados en esa misma carpeta.
   - `--prior-real-value/--prior-real-units` = suma de `total.realValue` /
     `total.realUnits` de los meses en `historico/` anteriores al mes en curso.
   - **Factura ambigua** (las que el SKILL de presupuesto dice "preguntar al
     usuario"): no hay a quién preguntar — dejarla FUERA del cálculo, anotarla en
     el footer del dashboard como "pendiente de clasificar" y mencionarla en el
     correo (ver paso 5). Nunca adivinar la categoría.
   - Facturas que **emiten otros a Mompossina** (p.ej. Falabella.com S.A.S. cobra
     comisiones; carpeta OCTUBRE de gastos) no son venta: no se cuentan.
   - Reescribir la narrativa del dashboard como siempre y republicar el Artifact
     (`https://claude.ai/artifact/GLPEPUuAWn1C6FoPSB8JrN`).

3. **Armar el informe:**
   ```
   OUT=informes/canales/<YYYY-MM-DD del corte>
   python3 .claude/skills/informe-canales/build_report.py \
     --html dashboards/presupuesto-vs-real.html \
     --team .claude/skills/informe-canales/equipo.json --out $OUT
   NODE_PATH=$(npm root -g) node .claude/skills/informe-canales/render.js $OUT
   ```
   Revisar las 3 imágenes (Read sobre los PNG) antes de seguir.

4. **Subir y publicar.** `git add` del dashboard, los insumos y `$OUT`, commit,
   push, PR a la rama por defecto y merge (igual que el skill de presupuesto).
   Tomar el SHA del merge commit y verificar que cada imagen responde 200:
   `https://raw.githubusercontent.com/Mtrujillo45/Ventas-FLA/<SHA>/$OUT/<id>.png`.
   El repo es público y la URL raw fijada al SHA funciona apenas se sube (no
   depende de GitHub Pages).

5. **Enviar.** Reemplazar `{{IMG_BASE}}` en `$OUT/correo.html` por
   `https://raw.githubusercontent.com/Mtrujillo45/Ventas-FLA/<SHA>/$OUT`.
   Si hubo facturas pendientes de clasificar o algo fuera de lo normal (p.ej. no
   se pudo leer Drive), agregar un párrafo corto al inicio del correo diciéndolo.
   Enviar con `GMAIL_SEND_EMAIL` (Composio), cuenta `gmail_rebold-risp`,
   `is_html: true`, asunto de `$OUT/asunto.txt`, `recipient_email` = primera
   responsable y `extra_recipients` = el resto (correos del directorio del prompt
   de la Routine).
   Enviar **una sola vez**: no reintentar si la respuesta trae id de mensaje.

6. **Reportar** en la sesión: asunto, destinatarios, ritmo total y canales en rojo.

## Si algo falla

- Shopify o Drive no responden: no enviar cifras viejas como si fueran nuevas.
  Enviar solo a operaciones@mompossina.com un aviso corto ("no se pudo generar el
  informe de hoy: <motivo>") y terminar.
- El render falla o una imagen no carga (raw ≠ 200): no enviar al equipo; avisar
  a operaciones@ igual que arriba.

## Archivos

- `build_report.py` — arma `tarjetas.html`, `correo.html`, `asunto.txt` y
  `resumen.json` desde el `DATA_BUNDLE` del dashboard. No hace aritmética de
  negocio: toma real/meta/ritmo/semáforo tal cual; solo calcula lo que falta por
  día para cumplir ((meta − real) / días restantes).
- `render.js` — screenshot 2x de cada tarjeta → `online.png`, `showroom.png`,
  `mayoristas.png` (Playwright, Chromium en `/opt/pw-browsers/chromium`).
- `equipo.json` — grupos, canales y responsables (nombre + correo).
- Colores del semáforo: paleta de estado fija (verde `#0ca30c`, amarillo
  `#fab219`, rojo `#d03b3b`), siempre con icono + texto, nunca solo color.
