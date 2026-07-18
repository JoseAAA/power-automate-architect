#!/usr/bin/env python3
"""
pa_api.py - Conector local a Power Automate: UN login -> todos tus flujos.

Uso:
  python pa_api.py login [--device]        Inicia sesion (abre el navegador)
  python pa_api.py entornos                Lista tus entornos
  python pa_api.py flujos [--entorno ID]   Lista TODOS tus flujos (Mis flujos + soluciones)
  python pa_api.py flujo <flowId> [--guardar ruta.json]   Detalle/definicion de un flujo
  python pa_api.py corridas <flowId>       Historial de ejecuciones
  python pa_api.py auditar <flowId>        Descarga el flujo y corre el auditor (34 reglas)
  python pa_api.py logout                  Borra la sesion local

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
import json
import subprocess
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
APIVER = "2016-11-01"

DIR_CONFIG = Path.home() / ".power-automate-architect"
ARCHIVO_CACHE = DIR_CONFIG / "token_cache.bin"
ARCHIVO_CONFIG = DIR_CONFIG / "config.json"

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


def _token_para(scopes, interactivo=False, device=False, client_id=None, tenant=None):
    """Token delegado: silencioso si hay sesion; si no (y se pide), interactivo."""
    app = _app(client_id, tenant)
    cuentas = app.get_accounts()
    if cuentas:
        r = app.acquire_token_silent(scopes, account=cuentas[0])
        if r and "access_token" in r:
            return r["access_token"], cuentas[0].get("username", "?")
    if not interactivo:
        raise PaApiError("No hay sesion activa. Corre primero:  python pa_api.py login")
    if device:
        flujo = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flujo:
            raise PaApiError(f"No se pudo iniciar device flow: {flujo.get('error_description', flujo)}")
        print(flujo["message"])  # instrucciones: ir a microsoft.com/devicelogin con el codigo
        r = app.acquire_token_by_device_flow(flujo)
    else:
        print("Abriendo el navegador para iniciar sesion con tu cuenta de trabajo...")
        r = app.acquire_token_interactive(scopes=scopes, prompt="select_account", timeout=300)
    if "access_token" not in r:
        err = r.get("error_description") or r.get("error") or str(r)
        if "AADSTS65001" in err or "consent" in err.lower():
            raise PaApiError(
                "El tenant exige consentimiento para este client. Opciones: (1) pedir a TI "
                "que apruebe, o (2) usar una app propia con --client-id (ver references/api-conexion.md).\n"
                f"Detalle: {err[:300]}")
        raise PaApiError(f"Login fallido: {err[:400]}")
    cuentas = app.get_accounts()
    return r["access_token"], (cuentas[0].get("username", "?") if cuentas else "?")


# ---------------------------------------------------------------------------
# HTTP (unico punto de salida a la red; endpoints intercambiables)
# ---------------------------------------------------------------------------
def _http(metodo, url, token, cuerpo=None, intentos=3):
    for i in range(intentos):
        r = requests.request(
            metodo, url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=cuerpo, timeout=60)
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
        return r.json() if r.text else {}
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
# Comandos
# ---------------------------------------------------------------------------
def _fecha(s):
    return (s or "")[:19].replace("T", " ")


def cmd_login(args):
    token, usuario = _token_para(SCOPE_FLOW, interactivo=True, device=args.device,
                                 client_id=args.client_id, tenant=args.tenant)
    cfg = _cargar_config()
    if args.client_id:
        cfg["client_id"] = args.client_id
    if args.tenant:
        cfg["tenant"] = args.tenant
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
    print("Siguiente paso:  python pa_api.py flujos")
    return 0


def cmd_logout(args):
    if ARCHIVO_CACHE.exists():
        ARCHIVO_CACHE.unlink()
        print("Sesion local borrada (cache de tokens eliminada).")
    else:
        print("No habia sesion local.")
    return 0


def cmd_entornos(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entornos = listar_entornos(token)
    print(f"{len(entornos)} entorno(s):\n")
    for e in entornos:
        p = e.get("properties", {}) or {}
        marca = "  <- por defecto" if p.get("isDefault") else ""
        print(f"  {e.get('name')}\n      {p.get('displayName', '?')}{marca}")
    return 0


def cmd_flujos(args):
    token, _ = _token_para(SCOPE_FLOW, client_id=args.client_id, tenant=args.tenant)
    entorno = args.entorno or entorno_por_defecto(token)
    flujos = listar_flujos(token, entorno)
    flujos.sort(key=lambda f: str((f.get("properties", {}) or {}).get("displayName", "")).lower())
    print(f"{len(flujos)} flujo(s) en {entorno}:\n")
    print(f"  {'ESTADO':<10} {'FLUJO':<52} ID")
    for f in flujos:
        p = f.get("properties", {}) or {}
        estado = p.get("state", "?")
        if p.get("flowSuspensionReason") and str(p.get("flowSuspensionReason")).lower() not in ("", "none"):
            estado = "Suspendido"  # tipicamente por politica DLP
        nombre = str(p.get("displayName", "?"))[:50]
        print(f"  {estado:<10} {nombre:<52} {f.get('name')}")
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

    p = sub.add_parser("login", help="Iniciar sesion");                 comunes(p)
    p.add_argument("--device", action="store_true", help="usar codigo de dispositivo en vez de navegador")
    p.set_defaults(fn=cmd_login)
    p = sub.add_parser("logout", help="Borrar la sesion local");        p.set_defaults(fn=cmd_logout)
    p = sub.add_parser("entornos", help="Listar entornos");             comunes(p); p.set_defaults(fn=cmd_entornos)
    p = sub.add_parser("flujos", help="Listar todos mis flujos");       comunes(p); p.set_defaults(fn=cmd_flujos)
    p = sub.add_parser("flujo", help="Detalle/definicion de un flujo"); comunes(p)
    p.add_argument("flow_id"); p.add_argument("--guardar", help="ruta .json donde guardar la definicion")
    p.set_defaults(fn=cmd_flujo)
    p = sub.add_parser("corridas", help="Historial de ejecuciones");    comunes(p)
    p.add_argument("flow_id"); p.add_argument("--max", default="15", help="cuantas mostrar (def. 15)")
    p.set_defaults(fn=cmd_corridas)
    p = sub.add_parser("auditar", help="Descargar un flujo y auditarlo"); comunes(p)
    p.add_argument("flow_id"); p.set_defaults(fn=cmd_auditar)

    args = ap.parse_args()
    try:
        return args.fn(args)
    except PaApiError as e:
        print(f"\nERROR: {e}")
        return 3
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
