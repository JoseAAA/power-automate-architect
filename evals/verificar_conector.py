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
 11-15. multi-cuenta, auditoria de tenant, salud, creacion moderna, modificar por .zip
 16. construir_solucion_zip (fallback sin permisos): .zip importable valido + --solo-zip

  python evals/verificar_conector.py     -> exit 0 si todo pasa, 1 si algo falla
"""
import base64
import io
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import pa_api  # noqa: E402

FLUJO_LIMPIO = json.loads((RAIZ / "evals" / "flujos" / "flujo-limpio.json")
                          .read_text(encoding="utf-8"))["properties"]

URLS_PEDIDAS = []
CAPTURADO = {}  # metodo+patron -> (url, cuerpo, cabeceras)

DV_API = "https://contoso.api.crm.dynamics.com"
WF_ZIP_ID = "aaaabbbb-0000-0000-0000-000000000009"


def _solucion_zip(definicion):
    """Un .zip de solucion minimo con un Workflows/*.json (para probar el round-trip)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("solution.xml",
                   "<ImportExportXml><Version>1.0.0.5</Version></ImportExportXml>")
        z.writestr("customizations.xml", "<ImportExportXml/>")
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(f"Workflows/Test-{WF_ZIP_ID}.json", json.dumps({"properties": {
            "connectionReferences": {"x": {"connection": {"connectionReferenceLogicalName": "pak_x"}}},
            "definition": definicion}, "schemaVersion": "1.0.0.0"}, ensure_ascii=False))
    return buf.getvalue()


def _http_falso(metodo, url, token, cuerpo=None, intentos=3, cabeceras=None,
                con_cabeceras=False, timeout=60):
    URLS_PEDIDAS.append(f"{metodo} {url}")
    # --- round-trip de solucion (.zip) ---
    if metodo == "POST" and url.endswith("/ExportSolution"):
        return {"ExportSolutionFile": base64.b64encode(_solucion_zip(FLUJO_LIMPIO["definition"])).decode()}
    if metodo == "POST" and url.endswith("/ImportSolution"):
        CAPTURADO["import_sol"] = (url, cuerpo, cabeceras)
        return {}
    if metodo == "POST" and url.endswith("/AddSolutionComponent"):
        return {}
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
        if WF_ZIP_ID in url:
            return {"value": [{"workflowid": WF_ZIP_ID, "name": "Test"}]}
        return {"value": []}  # FLOWLEGACY: sin fila -> legacy
    if metodo == "PATCH" and f"{DV_API}/api/data/v9.2/workflows(wf-123)" in url:
        CAPTURADO["patch_dv"] = (url, cuerpo, cabeceras)
        return {}
    if metodo == "POST" and url == f"{DV_API}/api/data/v9.2/workflows":
        CAPTURADO["post_dv"] = (url, cuerpo, cabeceras)
        return ({}, {"OData-EntityId": f"{DV_API}/api/data/v9.2/workflows(nuevo-guid-0001)"}) \
            if con_cabeceras else {}
    # --- Dataverse: solucion / publisher / connection references (formato moderno) ---
    if metodo == "GET" and f"{DV_API}/api/data/v9.2/solutions?" in url:
        return {"value": []}  # no existe -> se crea
    if metodo == "GET" and f"{DV_API}/api/data/v9.2/publishers?" in url:
        return {"value": []}
    if metodo == "GET" and f"{DV_API}/api/data/v9.2/connectionreferences?" in url:
        return {"value": []}
    if metodo == "POST" and url == f"{DV_API}/api/data/v9.2/publishers":
        return ({}, {"OData-EntityId": f"{DV_API}/api/data/v9.2/publishers(pub-1)"})
    if metodo == "POST" and url == f"{DV_API}/api/data/v9.2/solutions":
        CAPTURADO["post_sol"] = (url, cuerpo, cabeceras)
        return ({}, {"OData-EntityId": f"{DV_API}/api/data/v9.2/solutions(sol-1)"})
    if metodo == "POST" and url == f"{DV_API}/api/data/v9.2/connectionreferences":
        CAPTURADO.setdefault("post_connref", []).append((url, cuerpo, cabeceras))
        return ({}, {"OData-EntityId": f"{DV_API}/api/data/v9.2/connectionreferences(cr-1)"})
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
    defn_mala["actions"]["Try"]["actions"]["Listar_productos_con_stock_bajo"]["inputs"][
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

    # 13. reporte de salud: cruce flujos x conexiones + estados
    pa_api.listar_flujos = lambda t, e: [
        {"name": "fa", "properties": {"displayName": "Usa SharePoint roto", "state": "Started",
            "connectionReferences": {"shared_sharepointonline": {"connectionName": "conn-sp"}}}},
        {"name": "fb", "properties": {"displayName": "Suspendido", "state": "Suspended",
            "flowSuspensionReason": "CompanyDlpViolation", "connectionReferences": {}}},
        {"name": "fc", "properties": {"displayName": "Sano", "state": "Started",
            "connectionReferences": {"shared_office365": {"connectionName": "conn-o365"}}}},
    ]
    pa_api.listar_conexiones = lambda t, e: [
        {"name": "conn-sp", "properties": {"displayName": "SharePoint",
            "apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
            "statuses": [{"status": "Error"}]}},
        {"name": "conn-o365", "properties": {"displayName": "Office 365",
            "apiId": "/providers/Microsoft.PowerApps/apis/shared_office365",
            "statuses": [{"status": "Connected"}]}},
    ]
    salud = pa_api.reporte_salud("tf", "tp", "env")
    check("salud: detecta 1 conexion rota", salud["conexiones_rotas_total"] == 1)
    check("salud: el flujo que usa la conexion rota queda como afectado",
          any(a["nombre"] == "Usa SharePoint roto" for a in salud["afectados"]))
    check("salud: el flujo sano NO aparece como afectado",
          not any(a["nombre"] == "Sano" for a in salud["afectados"]))
    check("salud: detecta el flujo suspendido (DLP)",
          salud["suspendidos_total"] == 1 and salud["suspendidos"][0]["motivo"] == "CompanyDlpViolation")
    check("salud: reparto de estados correcto",
          salud["estados"]["Started"] == 2 and salud["estados"]["Suspended"] == 1)

    # 14. creacion en FORMATO MODERNO (solucion + connection references, Shape B)
    pa_api.listar_conexiones = lambda t, e: [  # solo SharePoint tiene conexion -> se pre-enlaza
        {"name": "conn-sp-real", "properties": {"displayName": "SP",
            "apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
            "statuses": [{"status": "Connected"}]}},
    ]
    CAPTURADO.pop("post_connref", None)
    # por defecto: conexiones SIN enlazar (el usuario las conecta en el portal)
    res_def = pa_api.crear_flujo_moderno(
        tok, "Default-tenant1", "Flujo default",
        FLUJO_LIMPIO["definition"], FLUJO_LIMPIO.get("connectionReferences", {}))
    check("moderno: por defecto deja TODAS las conexiones sin enlazar",
          set(res_def.get("conexiones_sin_enlazar", [])) == {"shared_sharepointonline", "shared_office365"})
    # con --enlazar: pre-enlaza a las existentes
    CAPTURADO.pop("post_connref", None)
    res_m = pa_api.crear_flujo_moderno(
        tok, "Default-tenant1", "Flujo moderno demo",
        FLUJO_LIMPIO["definition"], FLUJO_LIMPIO.get("connectionReferences", {}),
        enlazar_existentes=True)
    cd_m = json.loads((CAPTURADO.get("post_dv", ("", {}, {}))[1] or {}).get("clientdata", "{}"))
    cr_m = cd_m.get("properties", {}).get("connectionReferences", {})
    hdr_wf = CAPTURADO.get("post_dv", ("", {}, {}))[2] or {}
    check("moderno: via solución", res_m.get("via", "").startswith("dataverse (solución"))
    check("moderno: clientdata usa Shape B (connectionReferenceLogicalName)",
          all("connectionReferenceLogicalName" in (v.get("connection") or {})
              for v in cr_m.values()) and len(cr_m) >= 1)
    check("moderno: el POST del flujo lleva MSCRM.SolutionUniqueName",
          hdr_wf.get("MSCRM.SolutionUniqueName") == pa_api.SOL_UNIQUE)
    check("moderno: la connection reference se crea en la solución",
          any((c[2] or {}).get("MSCRM.SolutionUniqueName") == pa_api.SOL_UNIQUE
              for c in CAPTURADO.get("post_connref", [])))
    check("moderno: SharePoint (con conexión) se pre-enlaza; Office365 queda por autorizar",
          res_m.get("conexiones_sin_enlazar") == ["shared_office365"])
    check("moderno: la connref de SharePoint lleva connectionid enlazado",
          any((c[1] or {}).get("connectionid") == "conn-sp-real"
              for c in CAPTURADO.get("post_connref", [])))

    # 15. MODIFICAR por .zip de solucion (export -> editar JSON real -> import)
    wf = pa_api.exportar_flujo_json(tok, "Default-tenant1", WF_ZIP_ID)
    check("zip: exportar-flujo devuelve el JSON REAL (con connectionReferences)",
          "connectionReferences" in wf.get("properties", {}) and "definition" in wf.get("properties", {}))
    wf["properties"]["definition"]["triggers"] = {"nuevo": {"type": "Recurrence"}}  # editar
    CAPTURADO.pop("import_sol", None)
    res_zip = pa_api.modificar_flujo_zip(tok, "Default-tenant1", WF_ZIP_ID, wf)
    check("zip: via solución .zip", res_zip.get("via", "").startswith("solución .zip"))
    check("zip: respaldo del zip anterior creado", Path(res_zip.get("respaldo", "")).is_file())
    imp_b64 = (CAPTURADO.get("import_sol", ("", {}, {}))[1] or {}).get("CustomizationFile", "")
    zimp = zipfile.ZipFile(io.BytesIO(base64.b64decode(imp_b64)))
    wf_name = next(n for n in zimp.namelist() if n.startswith("Workflows/"))
    wf_imp = json.loads(zimp.read(wf_name).decode("utf-8"))
    check("zip: el import lleva la definicion EDITADA",
          "nuevo" in wf_imp["properties"]["definition"]["triggers"])
    check("zip: subio la version de la solucion (1.0.0.5 -> 1.0.0.6)",
          "1.0.0.6" in zimp.read("solution.xml").decode("utf-8"))
    check("zip: el import lleva OverwriteUnmanagedCustomizations",
          (CAPTURADO.get("import_sol", ("", {}, {}))[1] or {}).get("OverwriteUnmanagedCustomizations") is True)

    # 16. CONSTRUIR .zip importable desde cero + fallback de permisos en cmd_crear
    import xml.dom.minidom as _MD
    defn_z = json.loads(json.dumps(FLUJO_LIMPIO["definition"]))
    zb, info = pa_api.construir_solucion_zip(
        "Recordatorio Cumpleaños", defn_z,
        {"shared_office365": {}, "shared_sharepointonline": {}})
    zz = zipfile.ZipFile(io.BytesIO(zb))
    nombres = set(zz.namelist())
    check("build-zip: contiene los 4 archivos de solución",
          {"[Content_Types].xml", "solution.xml", "customizations.xml"} <= nombres
          and any(n.startswith("Workflows/") for n in nombres))
    ok_xml = True
    for n in ("[Content_Types].xml", "solution.xml", "customizations.xml"):
        try:
            _MD.parseString(zz.read(n))
        except Exception:
            ok_xml = False
    check("build-zip: XML bien formado en los 3 manifiestos", ok_xml)
    g = info["workflowid"]
    sol_x = zz.read("solution.xml").decode("utf-8")
    cus_x = zz.read("customizations.xml").decode("utf-8")
    wf_entry = info["archivo_interno"]
    check("build-zip: RootComponent type 29 con el guid del flujo",
          'type="29"' in sol_x and "{" + g + "}" in sol_x.lower())
    check("build-zip: JsonFileName apunta al archivo real del flujo",
          "/" + wf_entry in cus_x and g.replace("-", "").upper() in wf_entry)
    cd_z = json.loads(zz.read(wf_entry).decode("utf-8"))
    check("build-zip: el flujo hace round-trip (definición + $authentication)",
          bool(cd_z["properties"]["definition"]["triggers"]) and
          "$authentication" in cd_z["properties"]["definition"]["parameters"] and
          cd_z["schemaVersion"] == "1.0.0.0")
    check("build-zip: conexiones SIN enlazar por defecto (logical name, sin connectionid)",
          all("connectionReferenceLogicalName" in (v.get("connection") or {})
              for v in cd_z["properties"]["connectionReferences"].values())
          and info["conexiones_sin_enlazar"] == ["shared_office365", "shared_sharepointonline"])

    # fallback: si crear_flujo_moderno falla por permisos, cmd_crear deja el .zip y NO revienta
    carpeta_zip = tmp_dir / "flujos-locales"
    ARCHIVO_LIMPIO = str(RAIZ / "evals" / "flujos" / "flujo-limpio.json")

    def _crear_403(*a, **k):
        raise pa_api.PaApiError("Sin permiso para .../workflows (403).")

    pa_api.crear_flujo_moderno = _crear_403
    rc_fb = pa_api.cmd_crear(_Args(
        archivo=ARCHIVO_LIMPIO, nombre="Flujo sin permisos", entorno="Default-tenant1",
        si=True, forzar=False, enlazar=False, solo_zip=False, carpeta=str(carpeta_zip)))
    check("fallback: sin permisos, cmd_crear devuelve 0 y deja un .zip",
          rc_fb == 0 and len(list(carpeta_zip.glob("*.zip"))) == 1)

    # --solo-zip: genera el .zip SIN --si y sin tocar el tenant
    rc_sz = pa_api.cmd_crear(_Args(
        archivo=ARCHIVO_LIMPIO, nombre="Flujo solo zip", entorno="Default-tenant1",
        si=False, forzar=False, enlazar=False, solo_zip=True, carpeta=str(carpeta_zip)))
    check("--solo-zip: genera el .zip sin --si y sin tocar el tenant",
          rc_sz == 0 and len(list(carpeta_zip.glob("*.zip"))) == 2)

    print("-" * 50)
    print("TODO OK" if not fallas else f"{len(fallas)} verificacion(es) fallida(s)")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
