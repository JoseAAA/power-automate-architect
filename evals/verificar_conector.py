#!/usr/bin/env python3
"""
verificar_conector.py - Prueba offline del conector pa_api.py (sin red ni login).

Simula las respuestas de la maker API y de Dataverse (monkeypatch de pa_api._http)
y verifica lectura Y escritura:
  1. listar_entornos + deteccion del entorno por defecto
  2. listar_flujos sigue la paginacion (nextLink) y pide includeSolutionCloudFlows
  3. obtener_flujo -> guardar_flujo -> auditar_flujo.py da 100/100 (ciclo completo)
  4. guardar_flujo normaliza connectionReferences cuando viene como lista
  5. listar_corridas parsea el historial
  6. actualizar_flujo: via Dataverse (PATCH clientdata + If-Match) con respaldo previo
  7. actualizar_flujo: fallback maker API para flujos legacy (sin fila workflow)
  8. crear_flujo: POST a Dataverse y extraccion del id (OData-EntityId)
  9. cambiar_estado: statecode via Dataverse / start-stop via maker (sin Dataverse)
 10. _preauditar: acepta una definicion limpia y bloquea (exit 1) una con ALTA

  python evals/verificar_conector.py     -> exit 0 si todo pasa, 1 si algo falla
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import pa_api  # noqa: E402

FLUJO_LIMPIO = json.loads((RAIZ / "evals" / "flujos" / "flujo-limpio.json")
                          .read_text(encoding="utf-8"))["properties"]

URLS_PEDIDAS = []
CAPTURADO = {}  # metodo+patron -> (url, cuerpo, cabeceras)

DV_API = "https://contoso.api.crm.dynamics.com"


def _http_falso(metodo, url, token, cuerpo=None, intentos=3, cabeceras=None, con_cabeceras=False):
    URLS_PEDIDAS.append(f"{metodo} {url}")
    # --- lecturas maker API ---
    if metodo == "GET" and "/environments?" in url:
        return {"value": [
            {"name": "guid-secundario", "properties": {"displayName": "Sandbox", "isDefault": False}},
            {"name": "Default-tenant1", "properties": {
                "displayName": "Contoso (default)", "isDefault": True,
                "linkedEnvironmentMetadata": {
                    "instanceUrl": "https://contoso.crm.dynamics.com",
                    "instanceApiUrl": DV_API}}},
        ]}
    if metodo == "GET" and "/flows?" in url:
        return {"value": [
            {"name": "flow-a", "properties": {"displayName": "Flujo A", "state": "Started"}},
            {"name": "flow-b", "properties": {"displayName": "Flujo B", "state": "Stopped",
                                              "flowSuspensionReason": "None"}},
        ], "nextLink": "https://fake.local/pagina2"}
    if metodo == "GET" and url == "https://fake.local/pagina2":
        return {"value": [
            {"name": "flow-c", "properties": {"displayName": "Flujo C (solucion)", "state": "Started"}},
        ]}
    if metodo == "GET" and ("/flows/FLOW123?" in url or "/flows/FLOWLEGACY?" in url):
        return {"name": "FLOW123", "properties": {
            "displayName": FLUJO_LIMPIO["displayName"],
            "description": FLUJO_LIMPIO["description"],
            "state": "Started",
            "definition": FLUJO_LIMPIO["definition"],
            "connectionReferences": [
                {"connectionName": "sp-legal", "source": "Invoker",
                 "id": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"},
            ],
        }}
    if metodo == "GET" and "/runs?" in url:
        return {"value": [
            {"properties": {"status": "Succeeded", "startTime": "2026-07-16T07:00:01Z",
                            "endTime": "2026-07-16T07:00:09Z"}},
            {"properties": {"status": "Failed", "startTime": "2026-07-15T07:00:01Z",
                            "endTime": "2026-07-15T07:00:04Z",
                            "error": {"code": "ActionFailed"}}},
        ]}
    # --- Dataverse ---
    if metodo == "GET" and f"{DV_API}/api/data/v9.2/workflows?" in url:
        if "FLOW123" in url:
            return {"value": [{"workflowid": "wf-123", "name": "prueba", "statecode": 1,
                               "clientdata": json.dumps({"properties": {
                                   "connectionReferences": {}, "definition": {"vieja": True}},
                                   "schemaVersion": "1.0.0.0"})}]}
        return {"value": []}  # FLOWLEGACY: sin fila -> legacy
    if metodo == "PATCH" and f"{DV_API}/api/data/v9.2/workflows(wf-123)" in url:
        CAPTURADO["patch_dv"] = (url, cuerpo, cabeceras)
        return {}
    if metodo == "POST" and url == f"{DV_API}/api/data/v9.2/workflows":
        CAPTURADO["post_dv"] = (url, cuerpo, cabeceras)
        return ({}, {"OData-EntityId": f"{DV_API}/api/data/v9.2/workflows(nuevo-guid-0001)"}) \
            if con_cabeceras else {}
    # --- escrituras maker (fallback legacy / entorno sin Dataverse) ---
    if metodo == "PATCH" and "/flows/FLOWLEGACY?" in url:
        CAPTURADO["patch_maker"] = (url, cuerpo, cabeceras)
        return {}
    if metodo == "POST" and "/flows/flow-a/start?" in url:
        CAPTURADO["start_maker"] = (url, cuerpo, cabeceras)
        return {}
    raise AssertionError(f"URL inesperada: {metodo} {url}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # Aislar del entorno real: sin red, sin login, sin tocar config/respaldos del usuario
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

    tok = "TOKEN-FALSO"

    # 1. entornos + por defecto
    entornos = pa_api.listar_entornos(tok)
    check("listar_entornos devuelve 2", len(entornos) == 2, str(len(entornos)))
    predet = pa_api.entorno_por_defecto(tok)
    check("detecta el entorno por defecto", predet == "Default-tenant1", predet)

    # 2. flujos con paginacion e includeSolutionCloudFlows
    flujos = pa_api.listar_flujos(tok, predet)
    check("paginacion: 3 flujos entre 2 paginas", len(flujos) == 3, str(len(flujos)))
    url_flujos = next(u for u in URLS_PEDIDAS if "/flows?" in u)
    check("pide includeSolutionCloudFlows", "include=includeSolutionCloudFlows" in url_flujos)

    # 3+4. obtener -> guardar (normalizando lista) -> auditar = 100/100
    flujo = pa_api.obtener_flujo(tok, predet, "FLOW123")
    destino = tmp_dir / "descargado.json"
    ruta = pa_api.guardar_flujo(flujo, destino)
    doc = json.loads(ruta.read_text(encoding="utf-8"))
    check("connectionReferences normalizada a dict",
          isinstance(doc["properties"]["connectionReferences"], dict))
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "auditar_flujo.py"), str(ruta)],
                       capture_output=True, text=True, encoding="utf-8")
    check("flujo descargado audita 100/100 y exit 0",
          r.returncode == 0 and re.search(r"PUNTUACION: 100/100", r.stdout or ""),
          f"exit={r.returncode}")

    # 5. corridas
    corridas = pa_api.listar_corridas(tok, predet, "FLOW123")
    check("historial: 2 corridas y el error parseado", len(corridas) == 2 and
          corridas[1]["properties"]["error"]["code"] == "ActionFailed")

    # 6. actualizar via Dataverse (con respaldo)
    defn_nueva = dict(FLUJO_LIMPIO["definition"])
    res = pa_api.actualizar_flujo(tok, predet, "FLOW123", defn_nueva)
    _url, cuerpo, cabeceras = CAPTURADO.get("patch_dv", ("", {}, {}))
    cd = json.loads((cuerpo or {}).get("clientdata", "{}"))
    check("actualizar usa la via Dataverse", res.get("via", "").startswith("dataverse"))
    check("PATCH clientdata trae la definicion nueva y conserva el envoltorio",
          cd.get("properties", {}).get("definition", {}).get("triggers") is not None
          and cd.get("schemaVersion") == "1.0.0.0")
    check("PATCH lleva If-Match:* (no upsert accidental)", (cabeceras or {}).get("If-Match") == "*")
    check("se creo el respaldo previo", Path(res.get("respaldo", "")).is_file())

    # 7. actualizar flujo legacy -> fallback maker API
    res2 = pa_api.actualizar_flujo(tok, predet, "FLOWLEGACY", defn_nueva)
    check("legacy cae a maker API", "maker" in res2.get("via", ""),
          res2.get("via", "?"))
    check("PATCH maker con properties.definition",
          "definition" in ((CAPTURADO.get("patch_maker", ("", {}, {}))[1] or {})
                           .get("properties", {})))

    # 8. crear via Dataverse
    res3 = pa_api.crear_flujo(tok, predet, "Flujo nuevo demo", defn_nueva)
    cuerpo_post = CAPTURADO.get("post_dv", ("", {}, {}))[1] or {}
    check("crear: POST workflows con category 5 y clientdata",
          cuerpo_post.get("category") == 5 and "clientdata" in cuerpo_post)
    check("crear: id extraido de OData-EntityId", res3.get("workflowid") == "nuevo-guid-0001")

    # 9. estado: Dataverse cuando hay fila; maker cuando el entorno no tiene Dataverse
    via_on = pa_api.cambiar_estado(tok, predet, "FLOW123", True)
    check("encender via Dataverse (statecode 1)", via_on.startswith("dataverse") and
          (CAPTURADO.get("patch_dv", ("", {}, {}))[1] or {}).get("statecode") == 1)
    via_legacy = pa_api.cambiar_estado(tok, "guid-secundario", "flow-a", True)
    check("encender sin Dataverse cae a maker /start",
          via_legacy == "maker API" and "start_maker" in CAPTURADO)

    # 10. auditoria previa: pasa lo limpio, bloquea lo que tiene ALTA
    cod_ok, _ = pa_api._preauditar(FLUJO_LIMPIO["definition"],
                                   {"c": {"connectionName": "x", "source": "Invoker"}})
    defn_mala = json.loads(json.dumps(FLUJO_LIMPIO["definition"]))
    defn_mala["actions"]["Try"]["actions"]["Listar_contratos_por_vencer"]["inputs"][
        "parameters"]["password"] = "super-secreto-123"
    cod_mal, _ = pa_api._preauditar(defn_mala, {})
    check("preauditoria: limpio pasa (0) y con secreto bloquea (1)",
          cod_ok == 0 and cod_mal == 1, f"ok={cod_ok} mal={cod_mal}")

    # 11. gestion multi-cuenta (sin red: MSAL simulado)
    class _FakeApp:
        def __init__(self, correos):
            self._c = [{"username": u} for u in correos]

        def get_accounts(self):
            return list(self._c)

        def remove_account(self, acc):
            self._c = [c for c in self._c if c is not acc]

    fake = _FakeApp(["personal@contoso.com", "empresa@bigcorp.com"])
    pa_api._app = lambda *a, **k: fake

    class _Args:
        def __init__(self, **kw):
            self.client_id = self.tenant = None
            self.__dict__.update(kw)

    _config.pop("cuenta_activa", None)
    _config["entorno"] = "env-personal"
    cuenta_def, _ = pa_api._cuenta_activa(fake)
    check("sin cuenta activa -> primera cuenta", cuenta_def["username"] == "personal@contoso.com")

    pa_api.cmd_cambiar_cuenta(_Args(correo="empresa@bigcorp.com"))
    check("cambiar-cuenta fija la activa en config",
          _config.get("cuenta_activa") == "empresa@bigcorp.com")
    check("cambiar de cuenta olvida el entorno cacheado", "entorno" not in _config)
    cuenta_emp, _ = pa_api._cuenta_activa(fake)
    check("_cuenta_activa respeta la cuenta elegida", cuenta_emp["username"] == "empresa@bigcorp.com")

    try:
        pa_api.cmd_cambiar_cuenta(_Args(correo="noexiste@x.com"))
        rechazo = False
    except pa_api.PaApiError:
        rechazo = True
    check("cambiar-cuenta rechaza un correo sin sesion", rechazo)

    # activa = empresa; cerrar una cuenta PUNTUAL (personal, no activa) la quita y respeta la activa
    pa_api.cmd_logout(_Args(correo="personal@contoso.com", todas=False))
    check("logout <correo> cierra esa cuenta y respeta la activa",
          _config.get("cuenta_activa") == "empresa@bigcorp.com" and
          [c["username"] for c in fake.get_accounts()] == ["empresa@bigcorp.com"])
    # cerrar la activa (ya sin correo): al no quedar ninguna, se limpia cuenta_activa
    pa_api.cmd_logout(_Args(correo=None, todas=False))
    check("logout de la ultima cuenta limpia cuenta_activa",
          "cuenta_activa" not in _config and not fake.get_accounts())

    # 12. auditoria del tenant (agregado token-minimal, sin per-flujo en el resumen)
    import copy
    malo = copy.deepcopy(FLUJO_LIMPIO)
    malo["definition"]["actions"].pop("Catch")  # sin Catch -> PA-ERR-01 (ALTA)
    pa_api.listar_flujos = lambda t, e: [
        {"name": "f1", "properties": {"displayName": "Limpio",
                                      "definition": FLUJO_LIMPIO["definition"],
                                      "connectionReferences": FLUJO_LIMPIO.get("connectionReferences", {})}},
        {"name": "f2", "properties": {"displayName": "Sin manejo de errores",
                                      "definition": malo["definition"]}},
        {"name": "f3", "properties": {"displayName": "De otro dueno"}},  # sin definicion
    ]

    def _obtener_falso(t, e, fid):
        raise pa_api.PaApiError("otro dueno")  # f3 no accesible

    pa_api.obtener_flujo = _obtener_falso
    ag = pa_api.auditar_tenant("tok", "env", progreso=False)
    check("tenant: 2 auditados, 1 no accesible",
          ag["auditados"] == 2 and ag["no_accesibles"] == 1)
    check("tenant: el flujo limpio cuenta como verde (>=90)", ag["distribucion"]["verde"] >= 1)
    check("tenant: PA-ERR-01 aparece en reglas mas incumplidas",
          any(r["codigo"] == "PA-ERR-01" for r in ag["reglas_frecuentes"]))
    check("tenant: el resumen expone 'peores' pero el detalle va aparte",
          "peores" in ag and "resultados" in ag)

    print("-" * 50)
    print("TODO OK" if not fallas else f"{len(fallas)} verificacion(es) fallida(s)")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
