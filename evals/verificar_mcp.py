#!/usr/bin/env python3
"""
verificar_mcp.py - Prueba offline del servidor MCP (sin red, sin login, sin cliente).

Prueba las implementaciones de las 7 herramientas de pa_mcp.py contra la misma
API simulada de verificar_conector.py. Verifica en especial el contrato de
seguridad de escritura: simular -> token de un solo uso -> aplicar.

  python evals/verificar_mcp.py   -> exit 0 si todo pasa, 1 si algo falla
"""
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "evals"))

import pa_api  # noqa: E402
import pa_mcp  # noqa: E402
from verificar_conector import _http_falso, FLUJO_LIMPIO  # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # Aislamiento: API simulada, sin login real, sin tocar config del usuario
    tmp_dir = Path(tempfile.mkdtemp())
    pa_api._http = _http_falso
    pa_api.DIR_CONFIG = tmp_dir
    _config = {}
    pa_api._cargar_config = lambda: _config
    pa_api._guardar_config = lambda cfg: _config.update(cfg)
    pa_api._token_para = lambda *a, **k: ("TOKEN-FALSO", "prueba@contoso.com")

    fallas = []

    def check(nombre, cond, detalle=""):
        print(f"{'OK  ' if cond else 'FALLO'} {nombre}" + (f"  [{detalle}]" if detalle and not cond else ""))
        if not cond:
            fallas.append(nombre)

    # 1. sesion
    est = pa_mcp._estado_sesion()
    check("estado_sesion detecta la sesion", est.get("sesion") is True and
          est.get("usuario") == "prueba@contoso.com")
    check("iniciar_sesion no re-loguea si ya hay sesion",
          pa_mcp._iniciar_sesion().get("estado") == "ya_iniciada")

    # 2. lectura
    fl = pa_mcp._listar_flujos()
    check("listar_flujos: contrato y 3 flujos",
          fl.get("contrato") == "pa-architect/flujos@1" and len(fl.get("flujos", [])) == 3)
    rep = pa_mcp._auditar_flujo("FLOW123")
    check("auditar_flujo: 100/100 del flujo limpio del tenant",
          rep.get("puntuacion") == 100 and rep.get("contrato") == "pa-architect/auditoria@1")
    cor = pa_mcp._ver_corridas("FLOW123", maximo=5)
    check("ver_corridas: 2 corridas con error parseado",
          len(cor.get("corridas", [])) == 2 and cor["corridas"][1]["error"] == "ActionFailed")

    # 3. escritura: simular -> token -> aplicar
    defn_ok = {"properties": {"definition": FLUJO_LIMPIO["definition"],
                              "connectionReferences": {"c": {"connectionName": "x", "source": "Invoker"}}}}
    sim = pa_mcp._simular_cambio("actualizar", flow_id="FLOW123", definicion=defn_ok)
    tok = sim.get("token_confirmacion", "")
    check("simular_cambio(actualizar): devuelve token y auditoria previa",
          bool(tok) and sim["simulacion"]["auditoria_previa"]["puntuacion"] == 100)
    apl = pa_mcp._aplicar_cambio(tok)
    check("aplicar_cambio: ejecuta via Dataverse con respaldo",
          apl.get("hecho") and apl.get("via", "").startswith("dataverse") and
          Path(apl.get("respaldo", "")).is_file())
    try:
        pa_mcp._aplicar_cambio(tok)
        reusado = False
    except pa_api.PaApiError:
        reusado = True
    check("el token es de un solo uso", reusado)
    try:
        pa_mcp._aplicar_cambio("token-inventado")
        inventado = False
    except pa_api.PaApiError:
        inventado = True
    check("aplicar sin simular es rechazado", inventado)

    # 4. el gate de auditoria bloquea definiciones con ALTA (sin token)
    defn_mala = json.loads(json.dumps(defn_ok))
    defn_mala["properties"]["definition"]["actions"]["Try"]["actions"][
        "Listar_contratos_por_vencer"]["inputs"]["parameters"]["password"] = "secreto-123"
    sim2 = pa_mcp._simular_cambio("actualizar", flow_id="FLOW123", definicion=defn_mala)
    check("simular bloquea definicion con hallazgos ALTA (sin token)",
          sim2.get("bloqueado") is True and "token_confirmacion" not in sim2)

    # 5. encender por token
    sim3 = pa_mcp._simular_cambio("encender", flow_id="FLOW123")
    apl3 = pa_mcp._aplicar_cambio(sim3["token_confirmacion"])
    check("encender via simular->aplicar", apl3.get("hecho") and "dataverse" in apl3.get("via", ""))

    # 6. validaciones de entrada
    try:
        pa_mcp._simular_cambio("borrar")
        op_mala = False
    except pa_api.PaApiError:
        op_mala = True
    check("operacion desconocida rechazada", op_mala)

    print("-" * 50)
    print("TODO OK" if not fallas else f"{len(fallas)} verificacion(es) fallida(s)")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
