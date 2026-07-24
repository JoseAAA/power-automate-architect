#!/usr/bin/env python3
"""
pa_api.py - Conector local a Power Automate: UN login -> todos tus flujos.

Uso:
  python pa_api.py login                   Inicia sesion por navegador (en TU terminal)
  python pa_api.py login --iniciar         [agente] paso 1: muestra URL+codigo (no bloquea)
  python pa_api.py login --completar       [agente] paso 2: espera a que ingreses el codigo
  python pa_api.py sesion                  A que cuenta(s) estas conectado
  python pa_api.py cambiar-cuenta <correo> Cambia la cuenta activa (ej. la de tu empresa)
  python pa_api.py logout [<correo>|--todas]  Cierra la cuenta activa, una puntual, o todas
  python pa_api.py entornos                Lista tus entornos
  python pa_api.py flujos [--entorno ID]   Lista TODOS tus flujos (Mis flujos + soluciones)
  python pa_api.py flujo <flowId> [--guardar ruta.json]   Detalle/definicion de un flujo
  python pa_api.py corridas <flowId>       Historial de ejecuciones
  python pa_api.py auditar <flowId>        Descarga el flujo y corre el auditor local
  python pa_api.py auditar-todos [--detalle f.json]  Audita TODO el tenant (resumen)
  python pa_api.py exportar-flujo <flowId> --a f.json  Exporta el JSON real para editar
  python pa_api.py actualizar <flowId> --archivo f.json --si  Modifica por .zip (paso 2)
  python pa_api.py salud [--detalle f.json]  Conexiones rotas, flujos afectados, suspendidos
  python pa_api.py actualizar <flowId> --archivo f.json --si   Modifica un flujo (con respaldo)
  python pa_api.py crear --archivo f.json --nombre "X" --si    Crea un flujo (nace apagado)
  python pa_api.py crear ... --solo-zip     Solo genera el .zip importable (no toca el tenant)
  python pa_api.py encender <flowId> --si  Activa un flujo
  python pa_api.py apagar <flowId> --si    Desactiva un flujo
  python pa_api.py logout                  Borra la sesion local

Escritura (seguridad):
  - SIEMPRE respalda el flujo actual antes de tocarlo (en ~/.power-automate-architect/respaldos/).
  - SIEMPRE audita la definicion nueva antes de subirla; si hay hallazgos ALTA se
    niega salvo --forzar.
  - Sin --si solo muestra que haria (dry-run). Via Dataverse (soportada por
    Microsoft) cuando el flujo vive en la tabla workflow; maker API como fallback
    para flujos legacy.

Opciones comunes: --entorno <id> (por defecto: el entorno predeterminado del tenant),
--tenant <id|dominio>, --client-id <guid>.

Privacidad: habla SOLO con APIs de Microsoft (api.flow.microsoft.com) usando tu
propio login delegado (MSAL). Nada pasa por servidores de terceros. Los tokens se
guardan en cache local cifrada (DPAPI de Windows via msal-extensions).

Nota de arquitectura: la maker API es oficialmente "unsupported" (es la misma que
usa el portal de Power Automate). Por eso TODO el acceso HTTP pasa por _http() y
las URLs viven en un solo lugar: si Microsoft cambia algo, se ajusta aqui sin
tocar los comandos. Detalle y fuentes: references/api-conexion.md.

Requiere: pip install msal msal-extensions requests
"""
import argparse
import base64
import hashlib
import io
import json
import re
import subprocess
import uuid
import zipfile
import sys
import tempfile
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Falta 'requests'. Instala con: pip install requests")
    sys.exit(3)

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
# Client publico first-party de Microsoft (el mismo que usa el modulo oficial
# Microsoft.PowerApps.Administration.PowerShell). No requiere registrar una app.
# Si el tenant lo bloquea, usar --client-id con una app propia (ver api-conexion.md).
CLIENT_ID_DEFAULT = "1950a258-227b-4e31-a9cf-717495945fc2"
TENANT_DEFAULT = "organizations"
SCOPE_FLOW = ["https://service.flow.microsoft.com//.default"]

API_FLOW = "https://api.flow.microsoft.com"
API_POWERAPPS = "https://api.powerapps.com"
APIVER = "2016-11-01"
SCOPE_POWERAPPS = ["https://service.powerapps.com//.default"]  # conexiones viven aqui, no en el servicio de flujos

DIR_CONFIG = Path.home() / ".power-automate-architect"
ARCHIVO_CACHE = DIR_CONFIG / "token_cache.bin"
ARCHIVO_CONFIG = DIR_CONFIG / "config.json"
ARCHIVO_DEVICE = DIR_CONFIG / ".device_flow.json"  # login por codigo en 2 pasos (agente)

AUDITOR = Path(__file__).resolve().parent / "auditar_flujo.py"


class PaApiError(Exception):
    """Error con mensaje pensado para el usuario final."""


def _cargar_config():
    try:
        return json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _guardar_config(cfg):
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    ARCHIVO_CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Autenticacion (MSAL) - un login interactivo, luego tokens silenciosos
# ---------------------------------------------------------------------------
def _cache_tokens():
    """Cache persistente de tokens, cifrada si la plataforma lo permite."""
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    try:
        from msal_extensions import PersistedTokenCache, build_encrypted_persistence
        return PersistedTokenCache(build_encrypted_persistence(str(ARCHIVO_CACHE)))
    except Exception:
        try:
            from msal_extensions import PersistedTokenCache, FilePersistence
            print("AVISO: cache de tokens SIN cifrar (msal-extensions no pudo cifrar aqui).")
            return PersistedTokenCache(FilePersistence(str(ARCHIVO_CACHE)))
        except Exception:
            return None  # cache solo en memoria: pedira login en cada corrida


def _app(client_id=None, tenant=None):
    try:
        import msal
    except ImportError:
        raise PaApiError("Falta 'msal'. Instala con: pip install msal msal-extensions")
    cfg = _cargar_config()
    client_id = client_id or cfg.get("client_id") or CLIENT_ID_DEFAULT
    tenant = tenant or cfg.get("tenant") or TENANT_DEFAULT
    return msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant}",
        token_cache=_cache_tokens(),
    )


def _cuenta_activa(app):
    """Cuenta MSAL activa: la de config 'cuenta_activa', o la primera si no hay match."""
    cuentas = app.get_accounts()
    if not cuentas:
        return None, cuentas
    activa = (_cargar_config().get("cuenta_activa") or "").lower()
    if activa:
        for c in cuentas:
            if str(c.get("username", "")).lower() == activa:
                return c, cuentas
    return cuentas[0], cuentas


def _token_para(scopes, interactivo=False, device=False, client_id=None, tenant=None,
                hint=None):
    """Token delegado de la cuenta activa: silencioso si hay sesion; si no (y se
    pide), interactivo. `hint` (correo) fuerza esa cuenta en el login interactivo.
    Devuelve (access_token, usuario)."""
    app = _app(client_id, tenant)
    if not (interactivo and hint):  # con hint explicito no reuses la cuenta silenciosa
        cuenta, _cuentas = _cuenta_activa(app)
        if cuenta:
            r = app.acquire_token_silent(scopes, account=cuenta)
            if r and "access_token" in r:
                return r["access_token"], cuenta.get("username", "?")
    if not interactivo:
        raise PaApiError("No hay sesion activa. Corre primero:  python pa_api.py login")
    if device:
        flujo = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flujo:
            raise PaApiError(f"No se pudo iniciar device flow: {flujo.get('error_description', flujo)}")
        print(flujo["message"])  # instrucciones: ir a microsoft.com/devicelogin con el codigo
        if hint:
            print(f"IMPORTANTE: en esa pagina elige 'Usar otra cuenta' e inicia con: {hint}")
        r = app.acquire_token_by_device_flow(flujo)
    else:
        destino = f" ({hint})" if hint else ""
        print(f"Abriendo el navegador para iniciar sesion con tu cuenta de Microsoft{destino}...")
        r = app.acquire_token_interactive(scopes=scopes, prompt="select_account",
                                          login_hint=hint, timeout=300)
    if "access_token" not in r:
        err = r.get("error_description") or r.get("error") or str(r)
        if "AADSTS65001" in err or "consent" in err.lower():
            raise PaApiError(
                "El tenant exige consentimiento para este client. Opciones: (1) pedir a TI "
                "que apruebe, o (2) usar una app propia con --client-id (ver references/api-conexion.md).\n"
                f"Detalle: {err[:300]}")
        raise PaApiError(f"Login fallido: {err[:400]}")
    # usuario de ESTA sesion (no 'la primera de la cache'): viene en el id_token
    usuario = (r.get("id_token_claims") or {}).get("preferred_username")
    if not usuario:
        cuenta, _ = _cuenta_activa(app)
        usuario = cuenta.get("username", "?") if cuenta else "?"
    return r["access_token"], usuario


# ---------------------------------------------------------------------------
# HTTP (unico punto de salida a la red; endpoints intercambiables)
# ---------------------------------------------------------------------------
def _http(metodo, url, token, cuerpo=None, intentos=3, cabeceras=None, con_cabeceras=False,
          timeout=60):
    for i in range(intentos):
        r = requests.request(
            metodo, url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     **(cabeceras or {})},
            json=cuerpo, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            espera = int(r.headers.get("Retry-After", 2 ** (i + 1)))
            if i < intentos - 1:
                time.sleep(min(espera, 60))
                continue
        if r.status_code == 401:
            raise PaApiError("Token invalido o vencido. Corre:  python pa_api.py login")
        if r.status_code == 403:
            raise PaApiError(f"Sin permiso para {url.split('?')[0]} (403). ¿Tu cuenta tiene acceso a ese entorno/flujo?")
        if r.status_code == 404:
            raise PaApiError("No encontrado (404): revisa el id de entorno/flujo.")
        if not r.ok:
            raise PaApiError(f"HTTP {r.status_code}: {r.text[:300]}")
        datos = r.json() if r.text else {}
        return (datos, r.headers) if con_cabeceras else datos
    raise PaApiError("Demasiados reintentos (throttling). Espera un momento y vuelve a intentar.")


def _get_paginado(url, token):
    """Sigue nextLink hasta agotar las paginas; devuelve la lista completa de 'value'."""
    items = []
    while url:
        datos = _http("GET", url, token)
        items.extend(datos.get("value", []))
        url = datos.get("nextLink") or datos.get("@odata.nextLink")
    return items


# ---------------------------------------------------------------------------
# Operaciones (devuelven datos; los cmd_* imprimen)
# ---------------------------------------------------------------------------
def listar_entornos(token):
    url = f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments?api-version={APIVER}"
    return _get_paginado(url, token)


def entorno_por_defecto(token):
    cfg = _cargar_config()
    if cfg.get("entorno"):
        return cfg["entorno"]
    for e in listar_entornos(token):
        if (e.get("properties", {}) or {}).get("isDefault"):
            cfg["entorno"] = e["name"]
            _guardar_config(cfg)
            return e["name"]
    raise PaApiError("No pude detectar el entorno por defecto; usa --entorno <id> (ver 'entornos').")


def listar_flujos(token, entorno):
    """TODOS los flujos del usuario: Mis flujos + flujos de solucion (una sola llamada)."""
    url = (f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments/{entorno}/flows"
           f"?api-version={APIVER}&include=includeSolutionCloudFlows")
    return _get_paginado(url, token)


def obtener_flujo(token, entorno, flow_id):
    url = (f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments/{entorno}"
           f"/flows/{flow_id}?api-version={APIVER}")
    return _http("GET", url, token)


def listar_corridas(token, entorno, flow_id):
    url = (f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments/{entorno}"
           f"/flows/{flow_id}/runs?api-version={APIVER}")
    return _get_paginado(url, token)


def guardar_flujo(flujo, ruta):
    """Guarda el flujo en el formato que entiende auditar_flujo.py (definition.json)."""
    props = flujo.get("properties", {}) or {}
    connrefs = props.get("connectionReferences") or {}
    if isinstance(connrefs, list):  # algunas respuestas lo traen como lista
        connrefs = {str(c.get("connectionName") or i): c for i, c in enumerate(connrefs)}
    doc = {"properties": {
        "displayName": props.get("displayName", flujo.get("name", "?")),
        "description": props.get("description", ""),
        "definition": props.get("definition"),
        "connectionReferences": connrefs,
    }}
    if not doc["properties"]["definition"]:
        raise PaApiError(
            "La respuesta no trae la definicion completa (¿flujo de otro dueno?). "
            "Pide acceso de co-propietario o exporta el flujo desde el portal.")
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


# ---------------------------------------------------------------------------
# Escritura: Dataverse (via soportada) primero, maker API como fallback legacy.
# Ver references/api-conexion.md.
# ---------------------------------------------------------------------------
def _entorno_dataverse(token, entorno):
    """(instanceUrl, instanceApiUrl) del entorno, o (None, None) si no tiene Dataverse."""
    for e in listar_entornos(token):
        if e.get("name") == entorno:
            md = (e.get("properties", {}) or {}).get("linkedEnvironmentMetadata") or {}
            inst = str(md.get("instanceUrl") or "").rstrip("/")
            api = str(md.get("instanceApiUrl") or inst).rstrip("/")
            return (inst or None), (api or None)
    return None, None


def _token_dv(inst_url, client_id=None, tenant=None):
    tok, _ = _token_para([f"{inst_url}/.default"], client_id=client_id, tenant=tenant)
    return tok


def buscar_workflow(tok_dv, api_base, flow_id):
    """Fila de la tabla workflow (Dataverse) para un flujo, o None si es legacy."""
    url = (f"{api_base}/api/data/v9.2/workflows"
           f"?$filter=workflowidunique eq {flow_id} and category eq 5"
           f"&$select=workflowid,name,statecode,clientdata")
    filas = _http("GET", url, tok_dv).get("value", [])
    return filas[0] if filas else None


def _cargar_definicion_archivo(ruta):
    """Lee un .json (formato completo o definicion pelada) -> (definition, connrefs, descripcion)."""
    obj = json.loads(Path(ruta).read_text(encoding="utf-8"))
    props = obj.get("properties", obj) if isinstance(obj, dict) else {}
    defn = props.get("definition") or (obj if "actions" in obj and "triggers" in obj else None)
    if not defn:
        raise PaApiError(f"{ruta} no contiene una definicion valida (triggers/actions).")
    connrefs = props.get("connectionReferences") or {}
    return defn, connrefs, props.get("description", "")


def _respaldar(token, entorno, flow_id):
    """Descarga el flujo actual a ~/.power-automate-architect/respaldos/ antes de tocarlo."""
    flujo = obtener_flujo(token, entorno, flow_id)
    marca = time.strftime("%Y%m%d-%H%M%S")
    ruta = DIR_CONFIG / "respaldos" / f"{flow_id}-{marca}.json"
    return guardar_flujo(flujo, ruta), flujo


def _preauditar(defn, connrefs):
    """Audita la definicion nueva ANTES de subirla. Devuelve (exit_code, salida)."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "definition.json"
        ruta.write_text(json.dumps({"properties": {
            "displayName": "candidata", "description": "x",
            "definition": defn, "connectionReferences": connrefs}},
            ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(AUDITOR), str(ruta)],
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout or ""


def actualizar_flujo(token, entorno, flow_id, defn, connrefs=None,
                     client_id=None, tenant=None):
    """Reemplaza la definicion de un flujo existente. Devuelve dict con via y respaldo."""
    respaldo, _flujo = _respaldar(token, entorno, flow_id)
    inst, api = _entorno_dataverse(token, entorno)
    if inst:
        tok_dv = _token_dv(inst, client_id, tenant)
        fila = buscar_workflow(tok_dv, api, flow_id)
        if fila:
            cd = json.loads(fila.get("clientdata") or "{}")
            props = cd.setdefault("properties", {})
            props["definition"] = _asegurar_parametros_definicion(defn)
            # PRESERVAR las connection references existentes (Shape B de solucion);
            # no pisarlas con la forma de la maker API (romperia el diseñador moderno).
            # Solo asignar si el flujo aun no tenia ninguna.
            if connrefs and not props.get("connectionReferences"):
                props["connectionReferences"] = connrefs
            _http("PATCH", f"{api}/api/data/v9.2/workflows({fila['workflowid']})",
                  tok_dv, {"clientdata": json.dumps(cd, ensure_ascii=False)},
                  cabeceras={"If-Match": "*"})
            return {"via": "dataverse (soportada)", "respaldo": str(respaldo),
                    "workflowid": fila["workflowid"]}
    # Fallback: flujo legacy fuera de Dataverse -> maker API (misma llamada del portal)
    cuerpo = {"properties": {"definition": defn}}
    if connrefs:
        cuerpo["properties"]["connectionReferences"] = connrefs
    _http("PATCH", f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments/{entorno}"
          f"/flows/{flow_id}?api-version={APIVER}", token, cuerpo)
    return {"via": "maker API (flujo legacy)", "respaldo": str(respaldo)}


def crear_flujo(token, entorno, nombre, defn, connrefs=None, client_id=None, tenant=None):
    """Crea un flujo nuevo (nace APAGADO). Devuelve dict con via e id."""
    inst, api = _entorno_dataverse(token, entorno)
    if inst:
        tok_dv = _token_dv(inst, client_id, tenant)
        cd = {"properties": {"connectionReferences": connrefs or {}, "definition": defn},
              "schemaVersion": "1.0.0.0"}
        _, cab = _http("POST", f"{api}/api/data/v9.2/workflows", tok_dv,
                       {"category": 5, "name": nombre, "type": 1,
                        "primaryentity": "none",
                        "clientdata": json.dumps(cd, ensure_ascii=False)},
                       con_cabeceras=True)
        ent = str(cab.get("OData-EntityId", ""))
        wf_id = ent[ent.rfind("(") + 1: ent.rfind(")")] if "(" in ent else "?"
        return {"via": "dataverse (soportada)", "workflowid": wf_id}
    cuerpo = {"properties": {"displayName": nombre, "state": "Stopped",
                             "definition": defn,
                             "connectionReferences": connrefs or {}}}
    r = _http("POST", f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments/{entorno}"
              f"/flows?api-version={APIVER}", token, cuerpo)
    return {"via": "maker API", "workflowid": r.get("name", "?")}


# ---------------------------------------------------------------------------
# Creacion en FORMATO MODERNO: flujo de solucion + connection references, para
# que abra en el disenador nuevo y cierre PA-SEC-02. Ver references/api-conexion.md.
# ---------------------------------------------------------------------------
SOL_UNIQUE = "PowerAutomateArchitect"
SOL_FRIENDLY = "Power Automate Architect"
PUB_UNIQUE = "paarchitect"
PUB_PREFIX = "pak"


def _identidad_solucion():
    """Identidad de solución/publisher PROPIA por cuenta activa (determinista).

    Causa raíz del error 412 "A record with matching key values already exists":
    antes TODAS las cuentas compartían la MISMA solución/publisher (`pak_`). Si dos
    cuentas del mismo entorno creaban flujos, la segunda chocaba con connection
    references de la primera que ni siquiera podía leer (403 invisible). Derivando
    la identidad de la cuenta activa, cada cuenta trabaja en SU propia solución y
    nunca pisa componentes ajenos. Ver bitácora del tenant analiticadedatos."""
    usuario = str(_cargar_config().get("cuenta_activa") or "default").lower()
    h = hashlib.sha1(usuario.encode("utf-8")).hexdigest()
    return {
        "sol_unique": f"PAArchitect_{h[:8]}",
        "sol_friendly": SOL_FRIENDLY,
        "pub_unique": f"paarchitect_{h[:8]}",
        "pub_prefix": "pa" + h[:4],                       # 6 chars alfanuméricos
        "opt_value_prefix": 20000 + (int(h[:4], 16) % 60000),  # 20000-79999, único por publisher
    }


def _dv_get(tok_dv, api, ruta):
    return _http("GET", f"{api}/api/data/v9.2/{ruta}", tok_dv)


def _dv_post(tok_dv, api, entity, cuerpo, solucion=None):
    cab = {"MSCRM.SolutionUniqueName": solucion} if solucion else None
    _datos, headers = _http("POST", f"{api}/api/data/v9.2/{entity}", tok_dv, cuerpo,
                            cabeceras=cab, con_cabeceras=True)
    ent = str(headers.get("OData-EntityId", ""))
    return ent[ent.rfind("(") + 1: ent.rfind(")")] if "(" in ent else None


def _asegurar_solucion(tok_dv, api, ident=None):
    """Devuelve (unique_name, prefijo) de la solucion PROPIA de la cuenta, creandola
    si falta. La identidad (nombre/publisher/prefijo) es por cuenta para no chocar
    con componentes de otras cuentas (ver _identidad_solucion)."""
    ident = ident or _identidad_solucion()
    sol_u, sol_f = ident["sol_unique"], ident["sol_friendly"]
    pub_u, pub_p, optv = ident["pub_unique"], ident["pub_prefix"], ident["opt_value_prefix"]
    r = _dv_get(tok_dv, api, f"solutions?$filter=uniquename eq '{sol_u}'&$select=solutionid")
    pr = _dv_get(tok_dv, api, f"publishers?$filter=uniquename eq '{pub_u}'"
                              "&$select=publisherid,customizationprefix")
    pub = (pr.get("value") or [None])[0]
    if r.get("value") and pub:
        return sol_u, pub.get("customizationprefix", pub_p)
    if not pub:
        pid = _dv_post(tok_dv, api, "publishers", {
            "uniquename": pub_u, "friendlyname": sol_f,
            "customizationprefix": pub_p, "customizationoptionvalueprefix": int(optv)})
        prefijo = pub_p
    else:
        pid, prefijo = pub["publisherid"], pub.get("customizationprefix", pub_p)
    if not r.get("value"):
        _dv_post(tok_dv, api, "solutions", {
            "uniquename": sol_u, "friendlyname": sol_f, "version": "1.0.0.0",
            "publisherid@odata.bind": f"/publishers({pid})"})
    return sol_u, prefijo


def _asegurar_connref(tok_dv, api, solucion, prefijo, conector, connection_id=None):
    """Asegura una connection reference para el conector; devuelve su logical name.
    Si connection_id viene, la deja enlazada (el flujo se puede encender sin tocar el portal)."""
    logical = f"{prefijo}_{conector}".lower().replace('-', '_')
    r = _dv_get(tok_dv, api, "connectionreferences?$filter=connectionreferencelogicalname eq "
                             f"'{logical}'&$select=connectionreferenceid")
    if not r.get("value"):
        cuerpo = {"connectionreferencelogicalname": logical,
                  "connectionreferencedisplayname": conector,
                  "connectorid": f"/providers/Microsoft.PowerApps/apis/{conector}"}
        if connection_id:
            cuerpo["connectionid"] = connection_id
        _dv_post(tok_dv, api, "connectionreferences", cuerpo, solucion=solucion)
    return logical


def crear_flujo_moderno(token, entorno, nombre, defn, connrefs,
                        client_id=None, tenant=None, descripcion="", enlazar_existentes=False):
    """Crea el flujo como flujo de SOLUCION con connection references (Shape B):
    abre en el disenador moderno y cumple PA-SEC-02. Por defecto las connection
    references quedan SIN ENLAZAR: el usuario las conecta en el portal (un clic por
    conector) — asi la creacion NO se traba buscando conexiones. Con
    enlazar_existentes=True intenta pre-enlazar a conexiones que el usuario ya tenga."""
    inst, api = _entorno_dataverse(token, entorno)
    if not inst:
        raise PaApiError("El entorno no tiene Dataverse: no puedo crear en formato moderno "
                         "(el clasico esta descontinuado y no se usa).")
    tok_dv = _token_dv(inst, client_id, tenant)

    conn_por_conector = {}
    if enlazar_existentes:  # opcional: pre-enlazar a conexiones existentes (no pregunta, es silencioso)
        try:
            tok_pa, _ = _token_para(SCOPE_POWERAPPS, client_id=client_id, tenant=tenant)
            for c in listar_conexiones(tok_pa, entorno):
                p = c.get("properties", {}) or {}
                if _conexion_rota(p):
                    continue
                clave = str(p.get("apiId", "")).split("/")[-1]
                conn_por_conector.setdefault(clave, c.get("name"))
        except PaApiError:
            pass

    solucion, prefijo = _asegurar_solucion(tok_dv, api)
    nuevas, sin_enlazar = {}, []
    for conector in (connrefs or {}):
        conn_id = conn_por_conector.get(conector)
        if not conn_id:
            sin_enlazar.append(conector)
        logical = _asegurar_connref(tok_dv, api, solucion, prefijo, conector, conn_id)
        nuevas[conector] = {"runtimeSource": "embedded",
                            "connection": {"connectionReferenceLogicalName": logical},
                            "api": {"name": conector}}

    cd = {"properties": {"connectionReferences": nuevas,
                         "definition": _asegurar_parametros_definicion(defn)},
          "schemaVersion": "1.0.0.0"}
    cuerpo = {"category": 5, "name": nombre, "type": 1, "primaryentity": "none",
              "clientdata": json.dumps(cd, ensure_ascii=False)}
    if descripcion:
        cuerpo["description"] = descripcion
    wf_id = _dv_post(tok_dv, api, "workflows", cuerpo, solucion=solucion)
    return {"via": "dataverse (solución, formato moderno)", "workflowid": wf_id,
            "solucion": solucion, "conexiones_sin_enlazar": sin_enlazar}


def cambiar_estado(token, entorno, flow_id, encender, client_id=None, tenant=None):
    """Enciende (True) o apaga (False) un flujo. Devuelve la via usada."""
    inst, api = _entorno_dataverse(token, entorno)
    if inst:
        tok_dv = _token_dv(inst, client_id, tenant)
        fila = buscar_workflow(tok_dv, api, flow_id)
        if fila:
            _http("PATCH", f"{api}/api/data/v9.2/workflows({fila['workflowid']})",
                  tok_dv, {"statecode": 1 if encender else 0},
                  cabeceras={"If-Match": "*"})
            return "dataverse (soportada)"
    accion = "start" if encender else "stop"
    _http("POST", f"{API_FLOW}/providers/Microsoft.ProcessSimple/environments/{entorno}"
          f"/flows/{flow_id}/{accion}?api-version={APIVER}", token)
    return "maker API"


# ---------------------------------------------------------------------------
# MODIFICAR por round-trip de SOLUCION (.zip) — el modo confiable y rapido:
# exportar la solucion -> editar el JSON REAL del flujo (ya trae $authentication,
# connection references, etc.) -> reimportar. Igual que hace un experto a mano,
# pero automatico. Verificado en vivo + fuentes en references/api-conexion.md.
# ComponentType 29 = Workflow (verificado: Microsoft Learn solutioncomponent).
# ---------------------------------------------------------------------------
COMPONENT_TYPE_WORKFLOW = 29


def exportar_solucion(tok_dv, api, nombre_solucion):
    try:
        r = _http("POST", f"{api}/api/data/v9.2/ExportSolution", tok_dv,
                  {"SolutionName": nombre_solucion, "Managed": False}, timeout=300)
    except PaApiError as e:
        s = str(e)
        if "403" in s or "does not have" in s or "ReadAccess" in s or "privilege" in s.lower():
            raise PaApiError(
                "No pude exportar/gestionar la solucion por PERMISOS de Dataverse. La via de "
                "solucion (formato moderno + modificar por zip) necesita que TU cuenta tenga el "
                "rol de personalizador (System Customizer / Creador del entorno) y acceso a los "
                "componentes de la solucion. Habla con tu admin de Power Platform para que te "
                "asigne ese rol en este entorno. Sin eso, ni el portal ni esta herramienta pueden "
                "crear/editar flujos en solucion.")
        raise
    return base64.b64decode(r["ExportSolutionFile"])


def importar_solucion(tok_dv, api, zip_bytes):
    _http("POST", f"{api}/api/data/v9.2/ImportSolution", tok_dv,
          {"OverwriteUnmanagedCustomizations": True, "PublishWorkflows": True,
           "CustomizationFile": base64.b64encode(zip_bytes).decode(),
           "ImportJobId": str(uuid.uuid4())}, timeout=600)


def _resolver_workflowid(tok_dv, api, flow_id):
    """El id del flujo (maker) mapea al workflowid o workflowidunique en Dataverse."""
    for campo in ("workflowid", "workflowidunique"):
        r = _dv_get(tok_dv, api, f"workflows?$filter={campo} eq {flow_id} and category eq 5"
                                 "&$select=workflowid,name")
        if r.get("value"):
            return r["value"][0]["workflowid"], r["value"][0].get("name", "")
    return None, None


def _asegurar_flujo_en_solucion(tok_dv, api, workflow_id, solucion):
    """Agrega el flujo a nuestra solucion (si no estaba). No destructivo."""
    try:
        _http("POST", f"{api}/api/data/v9.2/AddSolutionComponent", tok_dv,
              {"ComponentId": workflow_id, "ComponentType": COMPONENT_TYPE_WORKFLOW,
               "SolutionUniqueName": solucion, "AddRequiredComponents": False})
    except PaApiError:
        pass  # ya estaba, o no se puede agregar; el export igual lo trae si estaba


def _subir_version_solucion(xml_bytes):
    m = re.search(rb"<Version>(\d+)\.(\d+)\.(\d+)\.(\d+)</Version>", xml_bytes)
    if not m:
        return xml_bytes
    a, b, c, d = (int(x) for x in m.groups())
    return xml_bytes[:m.start()] + f"<Version>{a}.{b}.{c}.{d + 1}</Version>".encode() + xml_bytes[m.end():]


def _hallar_workflow_en_zip(zin, wf_id):
    corto = wf_id.replace("-", "").lower()
    for n in zin.namelist():
        if (n.lower().startswith("workflows/") and n.lower().endswith(".json")
                and corto in n.replace("-", "").lower()):
            return n
    return None


def _preparar_flujo_en_solucion(tok_dv, api, flow_id):
    wf_id, _nombre = _resolver_workflowid(tok_dv, api, flow_id)
    if not wf_id:
        raise PaApiError("No encontre el flujo en Dataverse (¿es de otro dueno o de otro entorno?).")
    solucion, _p = _asegurar_solucion(tok_dv, api)
    _asegurar_flujo_en_solucion(tok_dv, api, wf_id, solucion)
    return wf_id, solucion


def exportar_flujo_json(token, entorno, flow_id, client_id=None, tenant=None):
    """Devuelve el JSON REAL del flujo (formato de solucion) para que el agente lo
    edite. Asegura primero que el flujo este en nuestra solucion."""
    inst, api = _entorno_dataverse(token, entorno)
    if not inst:
        raise PaApiError("El entorno no tiene Dataverse.")
    tok_dv = _token_dv(inst, client_id, tenant)
    wf_id, solucion = _preparar_flujo_en_solucion(tok_dv, api, flow_id)
    zin = zipfile.ZipFile(io.BytesIO(exportar_solucion(tok_dv, api, solucion)))
    target = _hallar_workflow_en_zip(zin, wf_id)
    if not target:
        raise PaApiError("El flujo no aparecio en el zip de la solucion.")
    return json.loads(zin.read(target).decode("utf-8"))


def modificar_flujo_zip(token, entorno, flow_id, workflows_json, client_id=None, tenant=None):
    """Reemplaza el JSON del flujo dentro del .zip de la solucion y reimporta.
    workflows_json = el JSON REAL editado (el que dio exportar_flujo_json)."""
    inst, api = _entorno_dataverse(token, entorno)
    if not inst:
        raise PaApiError("El entorno no tiene Dataverse.")
    tok_dv = _token_dv(inst, client_id, tenant)
    wf_id, solucion = _preparar_flujo_en_solucion(tok_dv, api, flow_id)
    raw = exportar_solucion(tok_dv, api, solucion)
    zin = zipfile.ZipFile(io.BytesIO(raw))
    target = _hallar_workflow_en_zip(zin, wf_id)
    if not target:
        raise PaApiError("El flujo no aparecio en el zip de la solucion.")
    # respaldo: el zip exportado (estado anterior completo)
    marca = time.strftime("%Y%m%d-%H%M%S")
    ruta = DIR_CONFIG / "respaldos" / f"{flow_id}-{marca}.zip"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(raw)
    # reempaquetar con el JSON editado y la version subida
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in zin.namelist():
            data = zin.read(n)
            if n == target:
                data = _fusionar_definicion(zin.read(n), workflows_json)
            elif n.lower() == "solution.xml":
                data = _subir_version_solucion(data)
            zout.writestr(n, data)
    importar_solucion(tok_dv, api, buf.getvalue())
    return {"via": "solución .zip (export→editar→import)", "respaldo": str(ruta), "solucion": solucion}


def _fusionar_definicion(json_actual_bytes, editado):
    """Núcleo de "modificar sin desconectar": toma el JSON REAL del flujo (el que
    Microsoft exportó, con sus connection references YA ENLAZADAS por el usuario) y
    le cambia SOLO `properties.definition` por la editada. NUNCA pisa
    `connectionReferences`: por eso una modificación de lógica no obliga a
    reconectar nada. Solo se SUMAN connection references de conectores NUEVOS que la
    edición introduzca (los que ya estaban ganan y conservan su enlace)."""
    actual = json.loads(json_actual_bytes.decode("utf-8"))
    props_ed = editado.get("properties", editado) if isinstance(editado, dict) else {}
    nueva_def = props_ed.get("definition") if isinstance(props_ed, dict) else None
    if nueva_def is None:
        raise PaApiError("El JSON editado no trae properties.definition (nada que aplicar).")
    props = actual.setdefault("properties", {})
    props["definition"] = nueva_def
    existentes = props.get("connectionReferences") or {}
    entrantes = props_ed.get("connectionReferences") or {}
    # existentes GANAN (conservan el enlace del usuario); solo se agregan conectores nuevos
    props["connectionReferences"] = {**entrantes, **existentes}
    return json.dumps(actual, ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# CONSTRUIR un .zip de solucion importable DESDE CERO (sin exportar del tenant).
# Sirve para el fallback "sin permisos": si tu cuenta no puede crear/modificar en
# el tenant, dejamos el .zip listo en tu carpeta y lo importas a mano en el portal
# (Soluciones > Importar solucion). El objetivo: SIEMPRE hay un resultado usable.
#
# Estructura verificada contra fuentes de Microsoft (no inventada):
#  - solution.xml: manifiesto real (ImportExportXml/SolutionManifest/Publisher/
#    RootComponents). RootComponent de un flujo = type="29" id="{guid}" behavior="0"
#    (verbatim de un export real). ComponentType 29 = Workflow (MS Learn).
#  - Workflows/<Nombre>-<GUID>.json = el "clientdata" (properties.connectionReferences
#    + properties.definition + schemaVersion) — shape verbatim de MS Learn
#    "Work with cloud flows using code".
#  - customizations.xml: <Workflows>/<Workflow> + <connectionreferences> (shape de
#    temmyraharjo, export real). [Content_Types].xml = OPC estandar.
# NOTA: la validez estructural se prueba offline (eval); la aceptacion por el
# validador de Microsoft se confirma con UNA importacion real antes de prometerla.
# ---------------------------------------------------------------------------
def _xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _slug_flujo(nombre):
    s = re.sub(r"[^A-Za-z0-9]+", "", str(nombre or ""))
    return s or "Flujo"


CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/octet-stream" />'
    '<Default Extension="json" ContentType="application/octet-stream" />'
    '</Types>')

_ADDRESS_XML = (
    "        <Address>\r\n"
    "          <AddressNumber>{n}</AddressNumber>\r\n"
    "          <AddressTypeCode>1</AddressTypeCode>\r\n"
    '          <City xsi:nil="true"></City>\r\n'
    '          <County xsi:nil="true"></County>\r\n'
    '          <Country xsi:nil="true"></Country>\r\n'
    '          <Fax xsi:nil="true"></Fax>\r\n'
    '          <FreightTermsCode xsi:nil="true"></FreightTermsCode>\r\n'
    '          <ImportSequenceNumber xsi:nil="true"></ImportSequenceNumber>\r\n'
    '          <Latitude xsi:nil="true"></Latitude>\r\n'
    '          <Line1 xsi:nil="true"></Line1>\r\n'
    '          <Line2 xsi:nil="true"></Line2>\r\n'
    '          <Line3 xsi:nil="true"></Line3>\r\n'
    '          <Longitude xsi:nil="true"></Longitude>\r\n'
    '          <Name xsi:nil="true"></Name>\r\n'
    '          <PostalCode xsi:nil="true"></PostalCode>\r\n'
    '          <PostOfficeBox xsi:nil="true"></PostOfficeBox>\r\n'
    '          <PrimaryContactName xsi:nil="true"></PrimaryContactName>\r\n'
    "          <ShippingMethodCode>1</ShippingMethodCode>\r\n"
    '          <StateOrProvince xsi:nil="true"></StateOrProvince>\r\n'
    '          <Telephone1 xsi:nil="true"></Telephone1>\r\n'
    '          <Telephone2 xsi:nil="true"></Telephone2>\r\n'
    '          <Telephone3 xsi:nil="true"></Telephone3>\r\n'
    '          <UPSZone xsi:nil="true"></UPSZone>\r\n'
    '          <UTCOffset xsi:nil="true"></UTCOffset>\r\n'
    "        </Address>\r\n")


def _solution_xml(workflow_id, version="1.0.0.0", sol_unique=None, sol_friendly=None,
                  pub_unique=None, pub_prefix=None, opt_value_prefix="72000"):
    sol_unique = sol_unique or SOL_UNIQUE
    sol_friendly = sol_friendly or SOL_FRIENDLY
    pub_unique = pub_unique or PUB_UNIQUE
    pub_prefix = pub_prefix or PUB_PREFIX
    guid = "{" + str(workflow_id).strip("{}").lower() + "}"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        '<ImportExportXml version="9.2.24024.171" SolutionPackageVersion="9.2" '
        'languagecode="1033" generatedBy="CrmLive" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\r\n'
        "  <SolutionManifest>\r\n"
        f"    <UniqueName>{_xml_escape(sol_unique)}</UniqueName>\r\n"
        "    <LocalizedNames>\r\n"
        f'      <LocalizedName description="{_xml_escape(sol_friendly)}" languagecode="1033" />\r\n'
        "    </LocalizedNames>\r\n"
        "    <Descriptions />\r\n"
        f"    <Version>{version}</Version>\r\n"
        "    <Managed>0</Managed>\r\n"
        "    <Publisher>\r\n"
        f"      <UniqueName>{_xml_escape(pub_unique)}</UniqueName>\r\n"
        "      <LocalizedNames>\r\n"
        f'        <LocalizedName description="{_xml_escape(sol_friendly)}" languagecode="1033" />\r\n'
        "      </LocalizedNames>\r\n"
        "      <Descriptions />\r\n"
        '      <EMailAddress xsi:nil="true"></EMailAddress>\r\n'
        '      <SupportingWebsiteUrl xsi:nil="true"></SupportingWebsiteUrl>\r\n'
        f"      <CustomizationPrefix>{_xml_escape(pub_prefix)}</CustomizationPrefix>\r\n"
        f"      <CustomizationOptionValuePrefix>{opt_value_prefix}</CustomizationOptionValuePrefix>\r\n"
        "      <Addresses>\r\n"
        + _ADDRESS_XML.format(n=1) + _ADDRESS_XML.format(n=2) +
        "      </Addresses>\r\n"
        "    </Publisher>\r\n"
        "    <RootComponents>\r\n"
        f'      <RootComponent type="29" id="{guid}" behavior="0" />\r\n'
        "    </RootComponents>\r\n"
        "    <MissingDependencies />\r\n"
        "  </SolutionManifest>\r\n"
        "</ImportExportXml>\r\n")


def _customizations_xml(workflow_id, nombre, json_file_name, connrefs_logicos):
    guid = "{" + str(workflow_id).strip("{}").lower() + "}"
    nombre_esc = _xml_escape(nombre)
    wf = (
        f'    <Workflow WorkflowId="{guid}" Name="{nombre_esc}">\r\n'
        f"      <JsonFileName>{_xml_escape(json_file_name)}</JsonFileName>\r\n"
        "      <Type>1</Type>\r\n"
        "      <Subprocess>0</Subprocess>\r\n"
        "      <Category>5</Category>\r\n"
        "      <Mode>0</Mode>\r\n"
        "      <Scope>4</Scope>\r\n"
        "      <OnDemand>0</OnDemand>\r\n"
        "      <TriggerOnCreate>0</TriggerOnCreate>\r\n"
        "      <TriggerOnDelete>0</TriggerOnDelete>\r\n"
        "      <AsyncAutodelete>0</AsyncAutodelete>\r\n"
        "      <SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>\r\n"
        "      <StateCode>0</StateCode>\r\n"
        "      <StatusCode>1</StatusCode>\r\n"
        "      <RunAs>1</RunAs>\r\n"
        "      <IsTransacted>1</IsTransacted>\r\n"
        "      <IntroducedVersion>1.0.0.0</IntroducedVersion>\r\n"
        "      <IsCustomizable>1</IsCustomizable>\r\n"
        "      <BusinessProcessType>0</BusinessProcessType>\r\n"
        "      <IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>\r\n"
        "      <PrimaryEntity>none</PrimaryEntity>\r\n"
        "      <LocalizedNames>\r\n"
        f'        <LocalizedName languagecode="1033" description="{nombre_esc}" />\r\n'
        "      </LocalizedNames>\r\n"
        "    </Workflow>\r\n")
    refs = ""
    for logical, conector in connrefs_logicos:
        refs += (
            f'    <connectionreference connectionreferencelogicalname="{_xml_escape(logical)}">\r\n'
            f"      <connectionreferencedisplayname>{_xml_escape(conector)}</connectionreferencedisplayname>\r\n"
            f"      <connectorid>/providers/Microsoft.PowerApps/apis/{_xml_escape(conector)}</connectorid>\r\n"
            "      <iscustomizable>1</iscustomizable>\r\n"
            "      <statecode>0</statecode>\r\n"
            "      <statuscode>1</statuscode>\r\n"
            "    </connectionreference>\r\n")
    bloque_refs = (f"  <connectionreferences>\r\n{refs}  </connectionreferences>\r\n"
                   if refs else "  <connectionreferences />\r\n")
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        '<ImportExportXml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\r\n'
        "  <Entities />\r\n"
        "  <Roles />\r\n"
        "  <Workflows>\r\n" + wf + "  </Workflows>\r\n"
        "  <FieldSecurityProfiles />\r\n"
        "  <Templates />\r\n"
        "  <EntityMaps />\r\n"
        "  <EntityRelationships />\r\n"
        "  <OrganizationSettings />\r\n"
        "  <optionsets />\r\n"
        "  <CustomControls />\r\n"
        "  <EntityDataProviders />\r\n"
        + bloque_refs +
        "  <Languages>\r\n"
        "    <Language>1033</Language>\r\n"
        "  </Languages>\r\n"
        "</ImportExportXml>\r\n")


def construir_solucion_zip(nombre, defn, connrefs, descripcion="", version="1.0.0.0",
                           sol_unique=None, sol_friendly=None, pub_unique=None,
                           pub_prefix=None, opt_value_prefix="72000"):
    """Arma en memoria un .zip de solucion NO administrada importable, con un flujo
    nuevo (nace apagado). Devuelve (zip_bytes, info). Sin red: 100% local.
    connrefs = dict {conector: <cualquier cosa>}; solo se usan las CLAVES (los
    conectores). Las connection references quedan SIN ENLAZAR (el que importe las
    conecta en el portal), tal como pide el flujo por defecto.
    La identidad de solucion/publisher es parametrizable (para pruebas aisladas)."""
    pub_prefix = pub_prefix or PUB_PREFIX
    workflow_id = str(uuid.uuid4())
    guid_archivo = workflow_id.replace("-", "").upper()
    slug = _slug_flujo(nombre)
    entrada_wf = f"Workflows/{slug}-{guid_archivo}.json"
    json_file_name = f"/Workflows/{slug}-{guid_archivo}.json"

    conectores = list((connrefs or {}).keys())
    connrefs_clientdata, connrefs_logicos = {}, []
    for conector in conectores:
        logical = f"{pub_prefix}_{conector}".lower().replace("-", "_")
        connrefs_clientdata[conector] = {
            "runtimeSource": "embedded",
            "connection": {"connectionReferenceLogicalName": logical},
            "api": {"name": conector}}
        connrefs_logicos.append((logical, conector))

    clientdata = {"properties": {"connectionReferences": connrefs_clientdata,
                                 "definition": _asegurar_parametros_definicion(defn)},
                  "schemaVersion": "1.0.0.0"}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        z.writestr("solution.xml", _solution_xml(
            workflow_id, version, sol_unique, sol_friendly, pub_unique,
            pub_prefix, opt_value_prefix))
        z.writestr("customizations.xml",
                   _customizations_xml(workflow_id, nombre, json_file_name, connrefs_logicos))
        z.writestr(entrada_wf, json.dumps(clientdata, ensure_ascii=False, indent=2))
    info = {"workflowid": workflow_id, "archivo_interno": entrada_wf,
            "conexiones_sin_enlazar": conectores}
    return buf.getvalue(), info


def guardar_zip_local(zip_bytes, nombre, carpeta=None):
    """Guarda el .zip importable en ./flujos-locales/ (dentro de la carpeta del
    proyecto/Claude Code) y devuelve la ruta. Esa carpeta esta en .gitignore."""
    carpeta = Path(carpeta) if carpeta else (Path.cwd() / "flujos-locales")
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = time.strftime("%Y%m%d-%H%M%S")
    ruta = carpeta / f"{_slug_flujo(nombre)}-{marca}.zip"
    ruta.write_bytes(zip_bytes)
    return ruta


def _instrucciones_importar(ruta_zip, sin_enlazar):
    """Texto en español, para el usuario, de como importar el .zip a mano."""
    pasos = [
        "",
        "📦 Te dejé el flujo listo como .zip de solución (importable a mano):",
        f"   {ruta_zip}",
        "",
        "Para ponerlo en Power Automate (no necesitas que yo tenga permisos):",
        "  1. Entra a https://make.powerautomate.com  (arriba a la derecha, elige el entorno correcto).",
        "  2. En el menú izquierdo abre  Soluciones.",
        "  3. Click en  Importar solución  →  Examinar  →  elige el .zip de arriba  →  Siguiente.",
        "  4. Click en  Importar  y espera a que termine (aparece en la lista de soluciones).",
        "  5. Abre la solución y luego el flujo: nace APAGADO.",
    ]
    if sin_enlazar:
        pasos += [
            f"  6. Conecta sus conexiones (una vez): {', '.join(sin_enlazar)}.",
            "     (el diseñador te pedirá elegir/crear cada conexión al abrir el flujo).",
            "  7. Guarda y enciéndelo.",
        ]
    else:
        pasos += ["  6. Guárdalo y enciéndelo."]
    pasos += [
        "",
        "Si otra persona de tu equipo es quien tiene permisos, pásale ese .zip: "
        "ella hace los mismos pasos.",
    ]
    return "\n".join(pasos)


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def _fecha(s):
    return (s or "")[:19].replace("T", " ")


def _post_login(token, usuario, args):
    """Comun tras un login exitoso (navegador o device): fija cuenta/entorno e informa."""
    cfg = _cargar_config()
    if args.client_id:
        cfg["client_id"] = args.client_id
    if args.tenant:
        cfg["tenant"] = args.tenant
    if str(cfg.get("cuenta_activa", "")).lower() != str(usuario).lower():
        cfg.pop("entorno", None)  # cuenta nueva: puede ser otro tenant
    cfg["cuenta_activa"] = usuario
    _guardar_config(cfg)
    entornos = listar_entornos(token)
    predet = next((e["name"] for e in entornos
                   if (e.get("properties", {}) or {}).get("isDefault")), None)
    if predet:
        cfg["entorno"] = predet
        _guardar_config(cfg)
    print(f"\nSesion iniciada como: {usuario}")
    print(f"Entornos accesibles: {len(entornos)}"
          + (f"   (por defecto: {predet})" if predet else ""))
    otras = [c.get("username") for c in _app(args.client_id, args.tenant).get_accounts()
             if str(c.get("username", "")).lower() != str(usuario).lower()]
    if otras:
        print(f"Otras cuentas en sesion: {', '.join(otras)}")
    return 0


def cmd_login(args):
    # --- login por codigo en 2 pasos (para agentes: sin navegador, relevando el codigo) ---
    if getattr(args, "iniciar", False):
        app = _app(args.client_id, args.tenant)
        flujo = app.initiate_device_flow(scopes=SCOPE_FLOW)
        if "user_code" not in flujo:
            raise PaApiError(f"No se pudo iniciar el login: {flujo.get('error_description', flujo)}")
        DIR_CONFIG.mkdir(parents=True, exist_ok=True)
        ARCHIVO_DEVICE.write_text(json.dumps(flujo), encoding="utf-8")
        print(f"Para iniciar sesion, abre:  {flujo.get('verification_uri', 'https://microsoft.com/devicelogin')}")
        print(f"E ingresa el codigo:  {flujo['user_code']}")
        if getattr(args, "como", None):
            print(f"Elige 'Usar otra cuenta' e inicia con: {args.como}")
        print("Cuando lo hayas hecho, completa con:  python pa_api.py login --completar")
        return 0
    if getattr(args, "completar", False):
        if not ARCHIVO_DEVICE.exists():
            raise PaApiError("No hay un login en curso. Inicia con:  python pa_api.py login --iniciar")
        flujo = json.loads(ARCHIVO_DEVICE.read_text(encoding="utf-8"))
        app = _app(args.client_id, args.tenant)
        r = app.acquire_token_by_device_flow(flujo)  # bloquea hasta que el usuario complete o expire
        ARCHIVO_DEVICE.unlink(missing_ok=True)
        if "access_token" not in r:
            err = r.get("error_description") or r.get("error") or str(r)
            raise PaApiError(f"Login no completado (¿ingresaste el codigo?): {err[:200]}")
        usuario = (r.get("id_token_claims") or {}).get("preferred_username") or "?"
        return _post_login(r["access_token"], usuario, args)

    # --- login por navegador (requiere terminal del usuario) ---
    token, usuario = _token_para(SCOPE_FLOW, interactivo=True, device=args.device,
                                 client_id=args.client_id, tenant=args.tenant,
                                 hint=getattr(args, "como", None))
    if getattr(args, "como", None) and str(usuario).lower() != args.como.lower():
        print(f"AVISO: iniciaste como {usuario}, no como {args.como}.")
    return _post_login(token, usuario, args)


def cmd_sesion(args):
    app = _app(args.client_id, args.tenant)
    cuenta, cuentas = _cuenta_activa(app)
    if not cuentas:
        print("Sin sesion. Inicia con:  python pa_api.py login")
        return 0
    print(f"{len(cuentas)} cuenta(s) en sesion:\n")
    for c in cuentas:
        u = c.get("username", "?")
        activa = "  <- activa" if c is cuenta else ""
        print(f"  {u}{activa}")
    if len(cuentas) > 1:
        print("\nCambiar de cuenta:  python pa_api.py cambiar-cuenta <correo>")
        print("Cerrar una cuenta:  python pa_api.py logout <correo>   (o --todas)")
    else:
        print("\nAgregar otra cuenta (ej. la de tu empresa):  python pa_api.py login")
        print("Cerrar la sesion:   python pa_api.py logout")
    return 0


def cmd_cambiar_cuenta(args):
    app = _app(args.client_id, args.tenant)
    cuentas = app.get_accounts()
    match = [c for c in cuentas if str(c.get("username", "")).lower() == args.correo.lower()]
    if not match:
        disp = ", ".join(c.get("username", "?") for c in cuentas) or "(ninguna)"
        raise PaApiError(f"No hay sesion para '{args.correo}'. Cuentas disponibles: {disp}. "
                         "Para agregarla inicia sesion:  python pa_api.py login")
    cfg = _cargar_config()
    cfg["cuenta_activa"] = match[0].get("username")
    cfg.pop("entorno", None)  # el entorno por defecto puede cambiar entre cuentas
    _guardar_config(cfg)
    print(f"Cuenta activa: {cfg['cuenta_activa']}")
    print("Siguiente:  python pa_api.py flujos")
    return 0


def cmd_logout(args):
    if args.todas:
        if ARCHIVO_CACHE.exists():
            ARCHIVO_CACHE.unlink()
        cfg = _cargar_config()
        cfg.pop("cuenta_activa", None)
        cfg.pop("entorno", None)
        _guardar_config(cfg)
        print("Todas las sesiones borradas.")
        return 0
    app = _app(args.client_id, args.tenant)
    cuentas = app.get_accounts()
    if not cuentas:
        print("No habia sesion local.")
        return 0
    correo = getattr(args, "correo", None)
    if correo:  # cerrar una cuenta puntual (aunque no sea la activa)
        objetivo = [c for c in cuentas if str(c.get("username", "")).lower() == correo.lower()]
        if not objetivo:
            disp = ", ".join(c.get("username", "?") for c in cuentas)
            raise PaApiError(f"No hay sesion para '{correo}'. Cuentas: {disp}")
        cuenta = objetivo[0]
    else:  # sin correo: cerrar la activa
        cuenta, _ = _cuenta_activa(app)
    app.remove_account(cuenta)
    cfg = _cargar_config()
    era_activa = str(cfg.get("cuenta_activa", "")).lower() == str(cuenta.get("username", "")).lower()
    if era_activa:  # si cerramos la activa, elegir otra (y olvidar el entorno de esa cuenta)
        cfg.pop("entorno", None)
        restantes = app.get_accounts()
        if restantes:
            cfg["cuenta_activa"] = restantes[0].get("username")
        else:
            cfg.pop("cuenta_activa", None)
    _guardar_config(cfg)
    msg = f"Sesion de {cuenta.get('username')} cerrada."
    if era_activa and cfg.get("cuenta_activa"):
        msg += f" Cuenta activa ahora: {cfg['cuenta_activa']}"
    print(msg)
    return 0


def cmd_entornos(args):
    token, usuario = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entornos = listar_entornos(token)
    print(f"{len(entornos)} entorno(s)  (conectado como {usuario}):\n")
    for e in entornos:
        p = e.get("properties", {}) or {}
        marca = "  <- por defecto" if p.get("isDefault") else ""
        print(f"  {e.get('name')}\n      {p.get('displayName', '?')}{marca}")
    return 0


def _estado_flujo(p):
    estado = p.get("state", "?")
    if p.get("flowSuspensionReason") and str(p.get("flowSuspensionReason")).lower() not in ("", "none"):
        estado = "Suspendido"  # tipicamente por politica DLP
    return estado


def cmd_flujos(args):
    token, usuario = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    flujos = listar_flujos(token, entorno)
    flujos.sort(key=lambda f: str((f.get("properties", {}) or {}).get("displayName", "")).lower())
    if args.como_json:
        print(json.dumps({"contrato": "pa-architect/flujos@1", "usuario": usuario,
                          "entorno": entorno,
                          "flujos": [{"id": f.get("name"),
                                      "nombre": (f.get("properties", {}) or {}).get("displayName", "?"),
                                      "estado": _estado_flujo(f.get("properties", {}) or {})}
                                     for f in flujos]}, ensure_ascii=False, indent=1))
        return 0
    print(f"Conectado como: {usuario}")
    print(f"{len(flujos)} flujo(s) en {entorno}:\n")
    print(f"  {'ESTADO':<10} {'FLUJO':<52} ID")
    for f in flujos:
        p = f.get("properties", {}) or {}
        nombre = str(p.get("displayName", "?"))[:50]
        print(f"  {_estado_flujo(p):<10} {nombre:<52} {f.get('name')}")
    if not flujos:
        print("  (nada aqui: revisa el entorno con 'entornos' o tus permisos)")
    print("\nDetalle:  python pa_api.py flujo <ID>   |   Auditar:  python pa_api.py auditar <ID>")
    return 0


def cmd_flujo(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    flujo = obtener_flujo(token, entorno, args.flow_id)
    p = flujo.get("properties", {}) or {}
    defn = p.get("definition") or {}
    print(f"Flujo: {p.get('displayName', '?')}")
    print(f"  Estado: {p.get('state', '?')}   Creado: {_fecha(p.get('createdTime'))}   "
          f"Modificado: {_fecha(p.get('lastModifiedTime'))}")
    if p.get("description"):
        print(f"  Descripcion: {p['description'][:200]}")
    print(f"  Triggers: {', '.join(defn.get('triggers', {}) or ['?'])}")
    print(f"  Acciones: {len(defn.get('actions', {}) or {})}")
    if args.guardar:
        ruta = guardar_flujo(flujo, args.guardar)
        print(f"  Definicion guardada en: {ruta}")
    return 0


def cmd_corridas(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    corridas = listar_corridas(token, entorno, args.flow_id)
    if args.como_json:
        print(json.dumps({"contrato": "pa-architect/corridas@1", "flujo": args.flow_id,
                          "corridas": [{"estado": (c.get("properties", {}) or {}).get("status", "?"),
                                        "inicio": _fecha((c.get("properties", {}) or {}).get("startTime")),
                                        "fin": _fecha((c.get("properties", {}) or {}).get("endTime")),
                                        "error": ((c.get("properties", {}) or {}).get("error") or {}).get("code", "")}
                                       for c in corridas[:int(args.max)]]},
                         ensure_ascii=False, indent=1))
        return 0
    print(f"{len(corridas)} corrida(s) (mas recientes primero):\n")
    for c in corridas[:int(args.max)]:
        p = c.get("properties", {}) or {}
        err = ""
        if isinstance(p.get("error"), dict):
            err = f"   error: {p['error'].get('code', '')}"
        print(f"  {p.get('status', '?'):<10} {_fecha(p.get('startTime'))}  ->  "
              f"{_fecha(p.get('endTime')) or 'en curso'}{err}")
    return 0


def cmd_auditar(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    flujo = obtener_flujo(token, entorno, args.flow_id)
    nombre = (flujo.get("properties", {}) or {}).get("displayName", args.flow_id)
    with tempfile.TemporaryDirectory() as tmp:
        ruta = guardar_flujo(flujo, Path(tmp) / "definition.json")
        print(f"Auditando '{nombre}' (descargado del tenant, analisis 100% local)...\n")
        r = subprocess.run([sys.executable, str(AUDITOR), str(ruta)])
        return r.returncode


def _asegurar_parametros_definicion(defn):
    """Un flujo de solucion con conectores requiere parameters.$connections y
    $authentication en la definicion; si faltan, Dataverse rechaza el update
    (error InvalidPowerFlow / missing '$authentication')."""
    if isinstance(defn, dict):
        params = defn.setdefault("parameters", {})
        params.setdefault("$connections", {"defaultValue": {}, "type": "Object"})
        params.setdefault("$authentication", {"defaultValue": {}, "type": "SecureObject"})
    return defn


def _connrefs_dict(connrefs):
    if isinstance(connrefs, list):
        return {str(c.get("connectionName") or j): c for j, c in enumerate(connrefs)}
    return connrefs or {}


def auditar_tenant(token, entorno, progreso=False):
    """Audita TODOS los flujos del entorno con Python (0 tokens de IA) y devuelve
    un AGREGADO compacto + el detalle por flujo. El caller decide que exponer al
    asistente (resumen) y que mandar a archivo (detalle)."""
    import importlib
    A = importlib.import_module("auditar_flujo")
    from collections import Counter

    flujos = listar_flujos(token, entorno)
    total = len(flujos)
    resultados, no_accesibles = [], 0
    for i, f in enumerate(flujos, 1):
        if progreso and (i == 1 or i % 10 == 0 or i == total):
            print(f"  auditando {i}/{total}...", file=sys.stderr)
        fid = f.get("name")
        props = f.get("properties", {}) or {}
        defn = props.get("definition")
        connrefs, desc = props.get("connectionReferences"), props.get("description", "")
        nombre = props.get("displayName", fid)
        if not defn:  # el listado no siempre trae la definicion completa: pedirla
            try:
                p2 = (obtener_flujo(token, entorno, fid).get("properties", {}) or {})
                defn, connrefs = p2.get("definition"), p2.get("connectionReferences")
                desc = p2.get("description", desc)
            except PaApiError:
                no_accesibles += 1
                continue
        if not defn:
            no_accesibles += 1
            continue
        hallazgos, _n, _t = A.auditar(defn, _connrefs_dict(connrefs), desc)
        score, conteo, codigos = 100, {"ALTA": 0, "MEDIA": 0, "BAJA": 0, "INFO": 0}, set()
        for cod, _extra in hallazgos:
            sev = A.REGLAS[cod][0]
            score -= A.PESO_SEV[sev]
            conteo[sev] += 1
            codigos.add(cod)
        resultados.append({"id": fid, "nombre": nombre, "puntuacion": max(0, score),
                           "alta": conteo["ALTA"], "media": conteo["MEDIA"],
                           "codigos": sorted(codigos)})

    aud = len(resultados)
    dist = {"verde": 0, "amarillo": 0, "naranja": 0, "rojo": 0}
    for r in resultados:
        s = r["puntuacion"]
        clave = "verde" if s >= 90 else "amarillo" if s >= 75 else "naranja" if s >= 50 else "rojo"
        dist[clave] += 1
    freq = Counter(c for r in resultados for c in r["codigos"])
    reglas = [{"codigo": c, "severidad": A.REGLAS[c][0], "titulo": A.REGLAS[c][2], "flujos": n}
              for c, n in freq.most_common(12)]
    return {
        "contrato": "pa-architect/auditoria-tenant@1", "entorno": entorno,
        "auditados": aud, "no_accesibles": no_accesibles,
        "puntuacion_media": round(sum(r["puntuacion"] for r in resultados) / aud) if aud else 0,
        "distribucion": dist,
        "peores": sorted(resultados, key=lambda r: (r["puntuacion"], -r["alta"]))[:10],
        "reglas_frecuentes": reglas,
        "resultados": resultados,  # detalle completo: el caller decide si va a archivo
    }


def listar_conexiones(token_pa, entorno):
    """Conexiones del entorno (via api.powerapps.com; requiere token de PowerApps)."""
    url = (f"{API_POWERAPPS}/providers/Microsoft.PowerApps/connections"
           f"?api-version={APIVER}&$filter=environment eq '{entorno}'")
    return _get_paginado(url, token_pa)


def _conexion_rota(props):
    """True si algun status de la conexion no es 'Connected' (desconectada/caducada/error)."""
    sts = props.get("statuses") or []
    return bool(sts) and any(str(s.get("status", "")).lower() != "connected" for s in sts)


def reporte_salud(token_flow, token_pa, entorno):
    """Cruza flujos x conexiones + estados. Detecta flujos que fallan/fallaran por
    una conexion rota, flujos suspendidos por DLP, y el reparto de estados.
    Todo en Python (0 tokens de IA). 2 llamadas de red: 1 flujos + 1 conexiones."""
    flujos = listar_flujos(token_flow, entorno)
    conexiones = listar_conexiones(token_pa, entorno)

    por_name, rotas = {}, []
    for c in conexiones:
        p = c.get("properties", {}) or {}
        info = {"name": c.get("name"),
                "conector": str(p.get("apiId", "")).split("/")[-1] or "?",
                "nombre": p.get("displayName", "?"),
                "estado": ", ".join(s.get("status", "?") for s in (p.get("statuses") or [])) or "?",
                "rota": _conexion_rota(p)}
        por_name[c.get("name")] = info
        if info["rota"]:
            rotas.append(info)

    estados = {"Started": 0, "Stopped": 0, "Suspended": 0, "Otro": 0}
    suspendidos, afectados = [], []
    for f in flujos:
        p = f.get("properties", {}) or {}
        st = p.get("state", "?")
        estados[st if st in estados else "Otro"] += 1
        if st == "Suspended":
            suspendidos.append({"id": f.get("name"), "nombre": p.get("displayName", "?"),
                                "motivo": p.get("flowSuspensionReason", "?")})
        cr = p.get("connectionReferences") or {}
        conx_rotas = sorted({por_name[ref.get("connectionName")]["nombre"]
                             for ref in (cr.values() if isinstance(cr, dict) else [])
                             if por_name.get(ref.get("connectionName"), {}).get("rota")})
        if conx_rotas:
            afectados.append({"id": f.get("name"), "nombre": p.get("displayName", "?"),
                              "estado": st, "conexiones_rotas": conx_rotas})

    return {
        "contrato": "pa-architect/salud@1", "entorno": entorno,
        "flujos": len(flujos), "conexiones": len(conexiones),
        "estados": estados,
        "conexiones_rotas_total": len(rotas),
        "conexiones_rotas": rotas,
        "afectados_total": len(afectados),
        "afectados": afectados,
        "suspendidos_total": len(suspendidos),
        "suspendidos": suspendidos,
    }


def cmd_salud(args):
    token, usuario = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    try:
        token_pa, _ = _token_para(SCOPE_POWERAPPS, client_id=args.client_id, tenant=args.tenant)
    except PaApiError:
        raise PaApiError("No pude obtener acceso a las conexiones (PowerApps). "
                         "Cierra e inicia sesion de nuevo:  python pa_api.py login")
    rep = reporte_salud(token, token_pa, entorno)

    detalle = None
    if args.detalle:
        Path(args.detalle).write_text(json.dumps(
            {k: rep[k] for k in ("conexiones_rotas", "afectados", "suspendidos")},
            ensure_ascii=False, indent=1), encoding="utf-8")
        detalle = str(Path(args.detalle))

    if args.como_json:
        # escalares + conexiones rotas (suele ser corto) + afectados/suspendidos acotados
        resumen = {k: v for k, v in rep.items() if not isinstance(v, list)}
        resumen["usuario"] = usuario
        resumen["conexiones_rotas"] = rep["conexiones_rotas"]
        resumen["afectados"] = rep["afectados"][:15]
        resumen["suspendidos"] = rep["suspendidos"][:15]
        if detalle:
            resumen["detalle_archivo"] = detalle
        print(json.dumps(resumen, ensure_ascii=False, indent=1))
        return 0

    e = rep["estados"]
    print(f"SALUD DEL TENANT — entorno {entorno}  (conectado como {usuario})")
    print(f"Flujos: {rep['flujos']}  (🟢 encendidos: {e['Started']}   ⚪ apagados: {e['Stopped']}"
          f"   🚫 suspendidos: {e['Suspended']})   |   Conexiones: {rep['conexiones']}")

    if rep["conexiones_rotas"]:
        print(f"\n🔴 Conexiones rotas/desconectadas: {rep['conexiones_rotas_total']}")
        for c in rep["conexiones_rotas"][:20]:
            print(f"  - {c['nombre'][:40]:<40} {c['conector']:<26} [{c['estado']}]")
        print(f"\n⚠️  Flujos afectados (fallan o fallaran por esas conexiones): {rep['afectados_total']}")
        for a in rep["afectados"][:15]:
            print(f"  - {a['nombre'][:44]:<44} ({a['estado']})  usa: {', '.join(a['conexiones_rotas'])}")
        print("\n  Arreglo: reconecta esas conexiones en make.powerautomate.com > Conexiones "
              "(o Datos > Conexiones), luego reactiva el flujo si quedo apagado.")
    else:
        print("\n🟢 Ninguna conexion rota. Todas responden 'Connected'.")

    if rep["suspendidos"]:
        print(f"\n🚫 Flujos suspendidos (normalmente por politica DLP): {rep['suspendidos_total']}")
        for s in rep["suspendidos"][:15]:
            print(f"  - {s['nombre'][:44]:<44} motivo: {s['motivo']}")

    if detalle:
        print(f"\nDetalle completo: {detalle}  (no lo cargues salvo que se pida)")
    return 0


def cmd_auditar_todos(args):
    token, usuario = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    ag = auditar_tenant(token, entorno, progreso=not args.como_json)

    detalle = None
    if args.detalle:
        Path(args.detalle).write_text(
            json.dumps(ag["resultados"], ensure_ascii=False, indent=1), encoding="utf-8")
        detalle = str(Path(args.detalle))

    # resumen compacto = lo UNICO que lee el asistente (tamano fijo, no crece con el tenant)
    resumen = {k: v for k, v in ag.items() if k != "resultados"}
    resumen["usuario"] = usuario
    if detalle:
        resumen["detalle_archivo"] = detalle

    if args.como_json:
        print(json.dumps(resumen, ensure_ascii=False, indent=1))
        return 0

    d = ag["distribucion"]
    print(f"AUDITORIA DEL TENANT — entorno {entorno}  (conectado como {usuario})")
    print(f"Flujos auditados: {ag['auditados']}"
          + (f"   |   No accesibles (otro dueno): {ag['no_accesibles']}" if ag["no_accesibles"] else ""))
    print(f"Puntuacion media: {ag['puntuacion_media']}/100")
    print(f"\nDistribucion:  🟢 ≥90: {d['verde']}   🟡 75-89: {d['amarillo']}   "
          f"🟠 50-74: {d['naranja']}   🔴 <50: {d['rojo']}")
    if ag["peores"]:
        print("\nPeores (revisar primero):")
        for r in ag["peores"]:
            print(f"  {r['puntuacion']:>3}  {r['nombre'][:44]:<44}  "
                  f"({r['alta']} ALTA, {r['media']} MEDIA)  {r['id']}")
    if ag["reglas_frecuentes"]:
        print("\nReglas mas incumplidas (foco de mejora global):")
        for r in ag["reglas_frecuentes"]:
            print(f"  {r['codigo']:<11} {r['titulo'][:46]:<46}  en {r['flujos']} flujo(s)")
    if detalle:
        print(f"\nDetalle completo por flujo: {detalle}")
        print("(no lo cargues salvo que se pida un flujo puntual)")
    else:
        print("\nTip: agrega --detalle informe.json para guardar el detalle por flujo.")
    return 0


def _preparar_escritura(args, necesita_archivo=True):
    """Pasos comunes de escritura: token, entorno, definicion nueva y auditoria previa."""
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    defn = connrefs = None
    descripcion = ""
    if necesita_archivo:
        defn, connrefs, descripcion = _cargar_definicion_archivo(args.archivo)
        codigo, salida = _preauditar(defn, connrefs)
        linea = next((l for l in salida.splitlines() if "PUNTUACION" in l), "")
        print(f"Auditoria previa de la definicion nueva: {linea.strip() or '?'}")
        if codigo == 1 and not getattr(args, "forzar", False):
            print(salida)
            raise PaApiError(
                "La definicion nueva tiene hallazgos de severidad ALTA (ver arriba). "
                "Corrigelos antes de subirla, o usa --forzar bajo tu responsabilidad.")
        if codigo == 2:
            raise PaApiError("No pude auditar el archivo: definicion invalida.")
    return token, entorno, defn, connrefs, descripcion


def cmd_exportar_flujo(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    wf = exportar_flujo_json(token, entorno, args.flow_id,
                             client_id=args.client_id, tenant=args.tenant)
    Path(args.a).write_text(json.dumps(wf, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"JSON REAL del flujo exportado a: {args.a}")
    print("Edita ese archivo (la definicion, dentro de properties.definition) y luego:")
    print(f"  python pa_api.py actualizar {args.flow_id} --archivo {args.a} --si")
    return 0


def cmd_actualizar(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    obj = json.loads(Path(args.archivo).read_text(encoding="utf-8"))
    props = obj.get("properties", obj) if isinstance(obj, dict) else {}
    defn = props.get("definition")
    if not defn:
        raise PaApiError(f"{args.archivo} no tiene properties.definition. Usa "
                         "'exportar-flujo' para obtener el JSON correcto, edítalo y vuelve.")
    # auditoria previa de la definicion editada
    codigo, salida = _preauditar(defn, props.get("connectionReferences") or {})
    linea = next((l for l in salida.splitlines() if "PUNTUACION" in l), "")
    print(f"Auditoria previa de la definicion editada: {linea.strip() or '?'}")
    if codigo == 1 and not getattr(args, "forzar", False):
        print(salida)
        raise PaApiError("La definicion editada tiene hallazgos ALTA; corrigelos o usa --forzar.")
    if not args.si:
        print(f"\n[SIMULACION] Modificaria el flujo {args.flow_id} via .zip de solucion "
              "(export→editar→import, con respaldo del zip anterior). Agrega --si para ejecutar.")
        return 0
    r = modificar_flujo_zip(token, entorno, args.flow_id, obj,
                            client_id=args.client_id, tenant=args.tenant)
    print(f"\nFlujo modificado via {r['via']}.")
    print(f"Respaldo (zip del estado anterior): {r['respaldo']}")
    print("Valida con:  python pa_api.py corridas " + args.flow_id)
    return 0


def cmd_crear(args):
    token, entorno, defn, connrefs, descripcion = _preparar_escritura(args)

    # Ruta rapida "--solo-zip": NO toca el tenant; deja el .zip importable listo en
    # tu carpeta. Util cuando ya sabes que no tienes permisos, o quieres el archivo
    # para pasarselo a quien sí los tiene. Es local y no destructivo: no pide --si.
    if getattr(args, "solo_zip", False):
        zip_bytes, info = construir_solucion_zip(args.nombre, defn, connrefs, descripcion,
                                                 **_identidad_solucion())
        ruta = guardar_zip_local(zip_bytes, args.nombre, getattr(args, "carpeta", None))
        print(f"\nFlujo '{args.nombre}' empaquetado como solución (NO se subió al tenant; --solo-zip).")
        print(_instrucciones_importar(ruta, info["conexiones_sin_enlazar"]))
        return 0

    if not args.si:
        print(f"\n[SIMULACION] Crearia el flujo '{args.nombre}' en {entorno} "
              "en formato moderno (solucion + connection references; nace APAGADO). "
              "Si tu cuenta no tiene permisos, en su lugar dejaria el .zip importable "
              "en ./flujos-locales/ con instrucciones. Agrega --si para ejecutar "
              "(o --solo-zip para solo generar el .zip, sin tocar el tenant).")
        return 0

    # SIEMPRE formato moderno. El disenador clasico esta prohibido (falla por
    # defecto y esta descontinuado en Power Automate).
    try:
        r = crear_flujo_moderno(token, entorno, args.nombre, defn, connrefs,
                                client_id=args.client_id, tenant=args.tenant,
                                descripcion=descripcion,
                                enlazar_existentes=getattr(args, "enlazar", False))
    except PaApiError as e:
        # Fallback (lo que pediste): si no se pudo crear en el tenant, SIEMPRE dejamos
        # un resultado usable -> el .zip importable en tu carpeta + como subirlo a mano.
        zip_bytes, info = construir_solucion_zip(args.nombre, defn, connrefs, descripcion,
                                                 **_identidad_solucion())
        ruta = guardar_zip_local(zip_bytes, args.nombre, getattr(args, "carpeta", None))
        es_permisos = any(t in str(e).lower() for t in
                          ("403", "permiso", "privilege", "does not have",
                           "readaccess", "personalizador"))
        print("\nNo pude crear el flujo directamente en tu tenant.")
        print(f"Motivo técnico: {e}")
        if es_permisos:
            print("\n➡️  Es un tema de PERMISOS: tu cuenta no puede crear flujos de solución en "
                  "este entorno (falta el rol de Creador del entorno / personalizador). No pasa "
                  "nada: te dejo el flujo empaquetado para importarlo a mano.")
        print(_instrucciones_importar(ruta, info["conexiones_sin_enlazar"]))
        return 0

    print(f"\nFlujo '{args.nombre}' creado via {r['via']}.  ID: {r['workflowid']}")
    if r.get("solucion"):
        print(f"Solucion: {r['solucion']}")
    sin = r.get("conexiones_sin_enlazar")
    if sin:
        print(f"Nace APAGADO. Conexiones a autorizar UNA vez en el portal: {', '.join(sin)}")
        print("  (abre el flujo en make.powerautomate.com, enlaza esas connection references)")
    else:
        print("Nace APAGADO (las conexiones ya quedaron enlazadas).")
    print(f"Enciendelo con:  python pa_api.py encender {r['workflowid']} --si")
    return 0


def cmd_estado(args, encender):
    token, entorno, _, _, _ = _preparar_escritura(args, necesita_archivo=False)
    verbo = "encenderia" if encender else "apagaria"
    if not args.si:
        print(f"[SIMULACION] {verbo} el flujo {args.flow_id} en {entorno}. Agrega --si para ejecutar.")
        return 0
    via = cambiar_estado(token, entorno, args.flow_id, encender,
                         client_id=args.client_id, tenant=args.tenant)
    print(f"Flujo {'encendido' if encender else 'apagado'} via {via}.")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Conector local a Power Automate (login unico).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comunes(p):
        p.add_argument("--entorno", help="Id del entorno (por defecto: el predeterminado)")
        p.add_argument("--tenant", help="Tenant (guid o dominio); por defecto 'organizations'")
        p.add_argument("--client-id", help="App de Entra ID propia (si el tenant bloquea la first-party)")

    p = sub.add_parser("login", help="Iniciar sesion (o agregar otra cuenta)");  comunes(p)
    p.add_argument("--device", action="store_true", help="usar codigo de dispositivo en vez de navegador")
    p.add_argument("--iniciar", action="store_true", help="[agente] paso 1: muestra URL+codigo y no bloquea")
    p.add_argument("--completar", action="store_true", help="[agente] paso 2: espera a que completes el codigo")
    p.add_argument("--como", help="correo de la cuenta a iniciar (fuerza esa cuenta, no la del navegador)")
    p.set_defaults(fn=cmd_login)
    p = sub.add_parser("sesion", help="Ver a que cuenta(s) estas conectado");    comunes(p)
    p.set_defaults(fn=cmd_sesion)
    p = sub.add_parser("cambiar-cuenta", help="Cambiar la cuenta activa");       comunes(p)
    p.add_argument("correo", help="correo de una cuenta ya iniciada (ver 'sesion')")
    p.set_defaults(fn=cmd_cambiar_cuenta)
    p = sub.add_parser("logout", help="Cerrar la cuenta activa, una puntual (<correo>) o todas"); comunes(p)
    p.add_argument("correo", nargs="?", help="correo de la cuenta a cerrar (por defecto: la activa)")
    p.add_argument("--todas", action="store_true", help="cerrar TODAS las cuentas")
    p.set_defaults(fn=cmd_logout)
    p = sub.add_parser("entornos", help="Listar entornos");             comunes(p); p.set_defaults(fn=cmd_entornos)
    p = sub.add_parser("flujos", help="Listar todos mis flujos");       comunes(p)
    p.add_argument("--json", action="store_true", dest="como_json", help="salida estructurada (contrato estable)")
    p.set_defaults(fn=cmd_flujos)
    p = sub.add_parser("flujo", help="Detalle/definicion de un flujo"); comunes(p)
    p.add_argument("flow_id"); p.add_argument("--guardar", help="ruta .json donde guardar la definicion")
    p.set_defaults(fn=cmd_flujo)
    p = sub.add_parser("corridas", help="Historial de ejecuciones");    comunes(p)
    p.add_argument("flow_id"); p.add_argument("--max", default="15", help="cuantas mostrar (def. 15)")
    p.add_argument("--json", action="store_true", dest="como_json", help="salida estructurada (contrato estable)")
    p.set_defaults(fn=cmd_corridas)
    p = sub.add_parser("auditar", help="Descargar un flujo y auditarlo"); comunes(p)
    p.add_argument("flow_id"); p.set_defaults(fn=cmd_auditar)
    p = sub.add_parser("auditar-todos", help="Auditar TODOS los flujos del tenant (resumen compacto)")
    comunes(p)
    p.add_argument("--detalle", help="ruta .json donde guardar el detalle por flujo")
    p.add_argument("--json", action="store_true", dest="como_json", help="salida estructurada (contrato estable)")
    p.set_defaults(fn=cmd_auditar_todos)
    p = sub.add_parser("salud", help="Reporte de salud: conexiones rotas, flujos afectados, suspendidos")
    comunes(p)
    p.add_argument("--detalle", help="ruta .json donde guardar el detalle")
    p.add_argument("--json", action="store_true", dest="como_json", help="salida estructurada (contrato estable)")
    p.set_defaults(fn=cmd_salud)

    def escritura(p):
        comunes(p)
        p.add_argument("--si", action="store_true", help="ejecutar de verdad (sin esto: simulacion)")
    p = sub.add_parser("exportar-flujo", help="Exporta el JSON REAL de un flujo para editarlo (paso 1 de modificar)")
    comunes(p); p.add_argument("flow_id")
    p.add_argument("--a", required=True, help="ruta .json donde guardar el JSON del flujo")
    p.set_defaults(fn=cmd_exportar_flujo)
    p = sub.add_parser("actualizar", help="Modificar un flujo por .zip de solucion (paso 2; con respaldo)")
    escritura(p); p.add_argument("flow_id")
    p.add_argument("--archivo", required=True, help="el JSON del flujo (de exportar-flujo) ya editado")
    p.add_argument("--forzar", action="store_true", help="subir aunque la auditoria previa tenga ALTA")
    p.set_defaults(fn=cmd_actualizar)
    p = sub.add_parser("crear", help="Crear un flujo nuevo (formato moderno; nace apagado)")
    escritura(p); p.add_argument("--archivo", required=True, help="ruta .json con la definicion")
    p.add_argument("--nombre", required=True, help="nombre del flujo nuevo")
    p.add_argument("--forzar", action="store_true", help="crear aunque la auditoria previa tenga ALTA")
    p.add_argument("--enlazar", action="store_true", help="pre-enlazar a conexiones existentes (def: las dejas en blanco para el portal)")
    p.add_argument("--solo-zip", action="store_true", dest="solo_zip",
                   help="NO tocar el tenant: solo generar el .zip importable en ./flujos-locales/")
    p.add_argument("--carpeta", help="carpeta donde dejar el .zip (def: ./flujos-locales/)")
    p.set_defaults(fn=cmd_crear)
    p = sub.add_parser("encender", help="Activar un flujo"); escritura(p)
    p.add_argument("flow_id"); p.set_defaults(fn=lambda a: cmd_estado(a, True))
    p = sub.add_parser("apagar", help="Desactivar un flujo"); escritura(p)
    p.add_argument("flow_id"); p.set_defaults(fn=lambda a: cmd_estado(a, False))

    args = ap.parse_args()
    try:
        return args.fn(args)
    except PaApiError as e:
        # En modo --json el error tambien es JSON (un solo documento por invocacion)
        if getattr(args, "como_json", False):
            print(json.dumps({"contrato": "pa-architect/error@1", "error": str(e)},
                             ensure_ascii=False))
        else:
            print(f"\nERROR: {e}")
        return 3
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
