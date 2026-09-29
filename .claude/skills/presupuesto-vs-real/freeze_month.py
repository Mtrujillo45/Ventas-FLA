#!/usr/bin/env python3
"""
freeze_month.py — Congela el mes actual del dashboard Presupuesto vs. Real
como snapshot histórico, para cuando el mes cierra y el siguiente corte va a
pasar a --month del mes nuevo.

Qué hace:
  1. Lee dashboards/presupuesto-vs-real.html (o el que se indique).
  2. Extrae del bloque DATA_START/END el objeto de datos del mes que se está
     cerrando (DATA_BUNDLE.byMonth[<mes>]) — ya trae channels/total/runrate/
     runrateSvg/extraordinary tal como quedaron en el último corte real.
  3. Extrae también el HTML tal cual del resumen ejecutivo hand-edited
     (<div id="exec-summary-body">...</div>) — se congela literal, con las
     mismas viñetas que el usuario vio en el último corte del mes.
  4. Escribe .claude/skills/presupuesto-vs-real/historico/<mes>.json con
     status="closed" y esos datos — este archivo queda versionado en git.

Uso típico (al primer corte de un mes nuevo, ANTES de correr compute.py con
el --month nuevo):
  python3 freeze_month.py --html dashboards/presupuesto-vs-real.html --month 2026-09

No recalcula nada — solo copia lo que ya estaba en el último corte real de
ese mes. Si el corte que se va a congelar no es realmente el último día del
mes, avisa pero no bloquea (a veces el cierre se hace con el corte de la
mañana del día 1 siguiente, que ya trae el mes completo).
"""
import argparse
import json
import os
import re
import sys


def extract_data_bundle(html):
    m = re.search(r"<!-- DATA_START -->\s*const DATA_BUNDLE = (.*?);\s*<!-- DATA_END -->", html, re.S)
    if not m:
        raise SystemExit("ERROR: no se encontró DATA_BUNDLE entre los marcadores DATA_START/DATA_END.")
    return json.loads(m.group(1))


def extract_narrative_html(html):
    m = re.search(r'<div id="exec-summary-body">(.*?)</div>\s*</section>', html, re.S)
    if not m:
        raise SystemExit('ERROR: no se encontró <div id="exec-summary-body"> en el HTML.')
    return m.group(1).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--month", required=True, help="YYYY-MM del mes que se está cerrando")
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico"))
    ap.add_argument("--force", action="store_true", help="sobrescribir si ya existe historico/<mes>.json")
    args = ap.parse_args()

    with open(args.html, encoding="utf-8") as f:
        html = f.read()

    bundle = extract_data_bundle(html)
    if args.month not in bundle["byMonth"]:
        raise SystemExit(f"ERROR: {args.month} no está en DATA_BUNDLE.byMonth del HTML actual.")
    month_data = bundle["byMonth"][args.month]

    if bundle["currentMonthKey"] != args.month:
        print(f"AVISO: el mes actual del dashboard es {bundle['currentMonthKey']}, no {args.month} — "
              f"¿seguro que {args.month} es el que se está cerrando? Congelando de todas formas "
              f"con los datos que había para {args.month} en el último corte.", file=sys.stderr)
    if month_data["status"] != "current" and not args.force:
        raise SystemExit(f"ERROR: {args.month} ya tiene status={month_data['status']!r} en el HTML "
                          f"(¿ya estaba congelado?) — usa --force si de verdad quieres re-congelarlo.")

    narrative_html = extract_narrative_html(html)

    snapshot = dict(month_data)
    snapshot["status"] = "closed"
    snapshot["narrativeHtml"] = narrative_html

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"{args.month}.json")
    if os.path.exists(out_path) and not args.force:
        raise SystemExit(f"ERROR: {out_path} ya existe — usa --force para sobrescribir.")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"Congelado {args.month} -> {out_path}")
    print(f"  Total real: {snapshot['total']['realValue']:.0f} / meta {snapshot['total']['budgetValue']:.0f} "
          f"({snapshot['total']['pctValue']:.1f}% del mes)")
    print(f"  Cutoff congelado: {snapshot['meta']['cutoff']}")
    print("  Recuerda: al correr compute.py para el mes nuevo, este archivo se carga automático desde "
          "historico/ y aparece como pestaña cerrada — no hace falta pasarlo por argumento.")


if __name__ == "__main__":
    main()
