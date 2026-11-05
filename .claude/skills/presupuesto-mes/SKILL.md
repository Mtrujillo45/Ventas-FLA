---
name: presupuesto-mes
description: Envía el día 1 de cada mes, por correo, la meta del mes por canal de Mompossina ($ y unidades, sin IVA) al equipo comercial (Online, Showroom, Mayoristas nacionales e internacionales). Corre automáticamente el día 1 a las 7:00 am (hora Bogotá). Usar siempre que el usuario pida: presupuesto del mes, meta del mes por canal, enviar la meta a las responsables, correo del día 1, o cuando lo dispare el scheduler.
---

## Qué hace

Arma y **envía** un correo con la meta del mes en curso para cada grupo de
responsables (pedido del usuario 2026-11-05: que las encargadas arranquen el mes
sabiendo su meta sin esperar a que se la digan). Es el complemento del informe de
cumplimiento (`informe-canales`, lunes y miércoles).

- Un solo correo para todo el equipo, desde **operaciones@mompossina.com**
  (cuenta Composio Gmail `gmail_rebold-risp`), igual que el informe por canal.
- Grupos y responsables: `.claude/skills/informe-canales/equipo.json`.
- Meta: `.claude/skills/presupuesto-vs-real/plan_2026_2027.json` (la misma fuente
  del dashboard Presupuesto vs. Real). **Nunca escribir cifras de meta a mano.**
- Por canal: meta en $ y unidades, promedio por día (meta ÷ días del mes), ticket
  implícito (meta $ ÷ meta und) y variación vs. la meta del mes anterior. Cifras
  sin IVA. Mayoristas internacionales (`BY_SHIPMENT`) no se reparte por día.

**Los correos del equipo NO están en el repo** (es público): viven en el prompt
privado de la Routine "Presupuesto del mes por canal — día 1". Si cambia un
correo hay que actualizar esa Routine y las dos del informe por canal.

## Procedimiento (corrida automática, sin usuario presente)

1. Rama por defecto al día (`claude/medellin-dashboard-composio-shopify-9b1mlm`,
   confirmar con `git remote show origin`). No hace falta rama de trabajo ni PR:
   esta corrida no cambia archivos del repo.
2. Mes = mes en curso en hora Bogotá (`python3 -c` con UTC-5; no confiar en `TZ=`).
3. Armar el correo:
   ```
   OUT=/tmp/presupuesto-mes/<YYYY-MM>
   python3 .claude/skills/presupuesto-mes/build_budget_mail.py --month <YYYY-MM> --out $OUT
   ```
   - **Código de salida 2** = el mes no está en el plan (p.ej. enero 2027 si nadie
     cargó la meta 2027). NO enviar nada al equipo: mandar solo a
     operaciones@mompossina.com un aviso corto ("no se envió la meta de <mes>: el
     mes no está cargado en plan_2026_2027.json") y terminar.
4. Leer `$OUT/correo.html` y revisar que tenga los 3 grupos y cifras > 0.
5. Enviar con `GMAIL_SEND_EMAIL` (Composio), cuenta `gmail_rebold-risp`,
   `is_html: true`, asunto = `$OUT/asunto.txt`, body = `$OUT/correo.html`,
   `recipient_email` = primera responsable y `extra_recipients` = el resto.
   Enviar **una sola vez**: no reintentar si la respuesta trae id de mensaje.
6. Reportar: asunto, destinatarios, meta total del mes ($ y unidades).

## Archivos

- `build_budget_mail.py` — arma `correo.html` y `asunto.txt` desde el plan y
  `equipo.json`. Sale con código 2 si el mes no está en el plan.
