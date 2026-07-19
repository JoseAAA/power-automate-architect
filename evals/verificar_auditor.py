#!/usr/bin/env python3
"""
verificar_auditor.py - Prueba de regresion del auditor de flujos.

Corre auditar_flujo.py sobre los flujos de evals/flujos/ y comprueba que los
codigos de regla detectados sean EXACTAMENTE los esperados (ni falsos positivos
ni reglas que dejaron de disparar). Ejecutar tras cualquier cambio del auditor:

  python evals/verificar_auditor.py

Codigo de salida: 0 si todo coincide, 1 si hay diferencias.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AUDITOR = RAIZ / "scripts" / "auditar_flujo.py"
FLUJOS = RAIZ / "evals" / "flujos"

# Por cada flujo de prueba: (codigos exactos esperados, exit code esperado)
ESPERADO = {
    "flujo-con-fallas.json": ({
        "PA-ERR-01", "PA-ERR-02", "PA-SEC-01", "PA-SEC-02", "PA-SEC-03",
        "PA-TEST-01", "PA-CONC-01", "PA-PERF-01", "PA-PERF-02", "PA-PERF-03",
        "PA-PERF-05", "PA-PERF-07", "PA-PERF-08", "PA-DATE-01", "PA-TRG-01",
        "PA-NAME-01", "PA-DOC-01", "PA-DOC-02", "PA-CFG-01", "PA-LIC-01",
    }, 1),
    "flujo-http-esperas.json": ({
        "PA-SEC-03", "PA-SEC-04", "PA-ERR-03", "PA-PERF-09", "PA-PERF-10",
        "PA-PERF-11", "PA-PERF-12", "PA-VAR-01", "PA-VAR-02", "PA-NAME-01",
        "PA-DOC-01", "PA-DOC-02", "PA-LIC-01",
    }, 1),
    "flujo-dataverse.json": ({
        "PA-ERR-01", "PA-ERR-02", "PA-TRG-01", "PA-TRG-02", "PA-TRG-03",
        "PA-TRG-04", "PA-DOC-02", "PA-LIC-01",
    }, 1),
    "flujo-agente-ia.json": ({
        "PA-ERR-01", "PA-ERR-02", "PA-IA-01", "PA-IA-02", "PA-IA-03",
        "PA-AGT-01", "PA-AGT-02", "PA-PERF-12", "PA-NAME-01", "PA-DOC-02",
        "PA-CFG-01", "PA-LIC-01",
    }, 1),
    "flujo-limpio.json": (set(), 0),
}

CODIGO_RE = re.compile(r"\[(?:ALTA|MEDIA|BAJA|INFO)\] (PA-[A-Z]+-\d+)")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    fallas = 0
    for nombre, (esperados, exit_esp) in ESPERADO.items():
        ruta = FLUJOS / nombre
        r = subprocess.run([sys.executable, str(AUDITOR), str(ruta)],
                           capture_output=True, text=True, encoding="utf-8")
        detectados = set(CODIGO_RE.findall(r.stdout or ""))
        # el contrato --json debe coincidir con el reporte humano (mismos codigos y exit)
        rj = subprocess.run([sys.executable, str(AUDITOR), str(ruta), "--json"],
                            capture_output=True, text=True, encoding="utf-8")
        try:
            datos = json.loads(rj.stdout or "{}")
            json_codigos = {h["codigo"] for h in datos.get("hallazgos", [])}
            json_ok = (json_codigos == esperados and rj.returncode == exit_esp
                       and datos.get("contrato") == "pa-architect/auditoria@1")
        except (json.JSONDecodeError, KeyError, TypeError):
            json_ok = False
        faltan = esperados - detectados
        sobran = detectados - esperados
        ok = not faltan and not sobran and r.returncode == exit_esp and json_ok
        print(f"{'OK  ' if ok else 'FALLO'} {nombre}: {len(detectados)} regla(s), "
              f"exit={r.returncode}, json={'OK' if json_ok else 'FALLO'}")
        if faltan:
            print(f"      faltan:  {', '.join(sorted(faltan))}")
        if sobran:
            print(f"      sobran:  {', '.join(sorted(sobran))}")
        if r.returncode != exit_esp:
            print(f"      exit esperado={exit_esp}")
            if r.stderr:
                print(f"      stderr: {r.stderr.strip()[:300]}")
        fallas += 0 if ok else 1
    print("-" * 50)
    print("TODO OK" if fallas == 0 else f"{fallas} flujo(s) con diferencias")
    return 0 if fallas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
