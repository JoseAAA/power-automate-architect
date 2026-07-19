#!/usr/bin/env python3
"""
pa_mcp.py - Servidor MCP delgado para clientes GUI (Claude Desktop).

Adaptador de 7 herramientas orientadas a tareas sobre el nucleo existente
(pa_api.py + auditar_flujo.py) — cero logica duplicada; devuelve los mismos
contratos JSON del CLI. Para agentes con terminal (Claude Code, Codex, Gemini
CLI, OpenCode) la via preferida sigue siendo CLI + skills (mas barata en
tokens); este servidor existe para quien NO tiene terminal.

Diseno segun consenso experto 2026 (ver references/panorama-herramientas.md y
CHANGELOG v0.7.0): pocas herramientas con forma de tarea; confirmacion en el
contrato (simular_cambio -> token de un solo uso -> aplicar_cambio), no en los
modales del cliente; anotaciones readOnly/destructive; el codigo de login viaja
como RESULTADO de herramienta (nunca stdout/stderr: stdout es el canal MCP).

Ejecutar:  python scripts/pa_mcp.py   (transporte stdio)
Requiere:  pip install mcp msal msal-extensions requests
"""
import json
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pa_api  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

AUDITOR = Path(__file__).resolve().parent / "auditar_flujo.py"
TTL_TOKEN_CAMBIO = 900  # 15 min para confirmar un cambio simulado

mcp = FastMCP("power-automate-architect")

_login = {"hilo": None, "resultado": None}
_cambios_pendientes = {}  # token -> operacion simulada pendiente de confirmacion


# ---------------------------------------------------------------------------
# Nucleo compartido
# ---------------------------------------------------------------------------
def _sesion_usuario():
    """Usuario con sesion silenciosa activa, o None (sin abrir navegador)."""
    try:
        _tok, usuario = pa_api._token_para(pa_api.SCOPE_FLOW)
        return usuario
    except pa_api.PaApiError:
        return None


def _token_o_error():
    tok, _ = pa_api._token_para(pa_api.SCOPE_FLOW)
    return tok


def _entorno(token, entorno):
    return entorno or pa_api.entorno_por_defecto(token)


def _extraer_defn(doc):
    """Acepta el documento completo {properties:{definition,...}} o la definicion pelada."""
    if not isinstance(doc, dict):
        raise pa_api.PaApiError("La definicion debe ser un objeto JSON.")
    props = doc.get("properties", doc)
    defn = props.get("definition") or (doc if "actions" in doc and "triggers" in doc else None)
    if not defn:
        raise pa_api.PaApiError("La definicion no trae triggers/actions validos.")
    connrefs = props.get("connectionReferences") or {}
    if isinstance(connrefs, list):  # algunas respuestas de la API la traen como lista
        connrefs = {str(c.get("connectionName") or i): c for i, c in enumerate(connrefs)}
    return defn, connrefs


def _auditar_defn(defn, connrefs):
    """Corre el auditor local (--json) sobre una definicion. -> (exit_code, dict)."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "definition.json"
        ruta.write_text(json.dumps({"properties": {
            "displayName": "candidata", "description": "x",
            "definition": defn, "connectionReferences": connrefs}},
            ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(AUDITOR), str(ruta), "--json"],
                           capture_output=True, text=True, encoding="utf-8")
        try:
            return r.returncode, json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            return 2, {"error": (r.stdout or r.stderr or "?")[:400]}


# ---------------------------------------------------------------------------
# Implementaciones (funciones planas: testeables sin cliente MCP)
# ---------------------------------------------------------------------------
def _iniciar_sesion() -> dict:
    usuario = _sesion_usuario()
    if usuario:
        return {"estado": "ya_iniciada", "usuario": usuario}
    if _login["hilo"] and _login["hilo"].is_alive():
        return {"estado": "pendiente",
                "instruccion": "El login sigue en curso; consulta estado_sesion tras completarlo."}
    app = pa_api._app()
    flujo = app.initiate_device_flow(scopes=pa_api.SCOPE_FLOW)
    if "user_code" not in flujo:
        return {"estado": "error",
                "error": str(flujo.get("error_description") or flujo)[:300]}

    def _esperar():
        _login["resultado"] = app.acquire_token_by_device_flow(flujo)

    _login["hilo"] = threading.Thread(target=_esperar, daemon=True)
    _login["hilo"].start()
    return {"estado": "codigo_generado",
            "url": flujo.get("verification_uri", "https://microsoft.com/devicelogin"),
            "codigo": flujo["user_code"],
            "expira_en_segundos": flujo.get("expires_in", 900),
            "instruccion": ("Muestra al usuario la URL y el codigo tal cual y dile que inicie "
                            "sesion con su cuenta del trabajo. Despues verifica con estado_sesion.")}


def _estado_sesion() -> dict:
    usuario = _sesion_usuario()
    if usuario:
        return {"sesion": True, "usuario": usuario}
    r = _login.get("resultado")
    detalle = ""
    if isinstance(r, dict) and r.get("error"):
        detalle = str(r.get("error_description") or r["error"])[:200]
    return {"sesion": False,
            "detalle": detalle or "Sin sesion. Usa iniciar_sesion.",
            "login_en_curso": bool(_login["hilo"] and _login["hilo"].is_alive())}


def _listar_flujos(entorno: str = "") -> dict:
    tok = _token_o_error()
    env = _entorno(tok, entorno)
    flujos = pa_api.listar_flujos(tok, env)
    flujos.sort(key=lambda f: str((f.get("properties", {}) or {}).get("displayName", "")).lower())
    items = [{"id": f.get("name"),
              "nombre": (f.get("properties", {}) or {}).get("displayName", "?"),
              "estado": pa_api._estado_flujo(f.get("properties", {}) or {})}
             for f in flujos[:100]]
    out = {"contrato": "pa-architect/flujos@1", "entorno": env, "flujos": items}
    if len(flujos) > 100:
        out["nota"] = f"Mostrando 100 de {len(flujos)}."
    return out


def _auditar_flujo(flow_id: str, entorno: str = "") -> dict:
    tok = _token_o_error()
    env = _entorno(tok, entorno)
    flujo = pa_api.obtener_flujo(tok, env, flow_id)
    props = flujo.get("properties", {}) or {}
    if not props.get("definition"):
        raise pa_api.PaApiError("La respuesta no trae la definicion (¿flujo de otro dueno?). "
                                "Pide co-propiedad al dueno del flujo.")
    defn, connrefs = _extraer_defn(flujo)
    _code, reporte = _auditar_defn(defn, connrefs)
    reporte["flujo"] = props.get("displayName", flow_id)
    return reporte


def _ver_corridas(flow_id: str, entorno: str = "", maximo: int = 10) -> dict:
    tok = _token_o_error()
    env = _entorno(tok, entorno)
    corridas = pa_api.listar_corridas(tok, env, flow_id)
    return {"contrato": "pa-architect/corridas@1", "flujo": flow_id,
            "corridas": [{"estado": (c.get("properties", {}) or {}).get("status", "?"),
                          "inicio": pa_api._fecha((c.get("properties", {}) or {}).get("startTime")),
                          "fin": pa_api._fecha((c.get("properties", {}) or {}).get("endTime")),
                          "error": ((c.get("properties", {}) or {}).get("error") or {}).get("code", "")}
                         for c in corridas[:maximo]]}


def _simular_cambio(operacion: str, flow_id: str = "", definicion: dict | None = None,
                    nombre: str = "", entorno: str = "") -> dict:
    if operacion not in ("actualizar", "crear", "encender", "apagar"):
        raise pa_api.PaApiError("operacion debe ser: actualizar | crear | encender | apagar")
    if operacion in ("actualizar", "encender", "apagar") and not flow_id:
        raise pa_api.PaApiError(f"'{operacion}' requiere flow_id.")
    tok = _token_o_error()
    env = _entorno(tok, entorno)
    simulacion = {"operacion": operacion, "flow_id": flow_id or None,
                  "nombre": nombre or None, "entorno": env}
    defn = connrefs = None
    if operacion in ("actualizar", "crear"):
        if not definicion or (operacion == "crear" and not nombre):
            raise pa_api.PaApiError("'actualizar' requiere definicion; 'crear' ademas nombre.")
        defn, connrefs = _extraer_defn(definicion)
        code, reporte = _auditar_defn(defn, connrefs)
        simulacion["auditoria_previa"] = {"puntuacion": reporte.get("puntuacion"),
                                          "veredicto": reporte.get("veredicto"),
                                          "hallazgos_alta": (reporte.get("totales") or {}).get("alta", 0)}
        if code == 1:
            return {"bloqueado": True, "motivo": "La definicion tiene hallazgos ALTA; corrigelos primero.",
                    "auditoria": reporte}
        if code == 2:
            return {"bloqueado": True, "motivo": "Definicion invalida.", "detalle": reporte}
        simulacion["acciones"] = len(defn.get("actions", {}) or {})
    token = secrets.token_hex(8)
    _cambios_pendientes[token] = {"operacion": operacion, "flow_id": flow_id, "defn": defn,
                                  "connrefs": connrefs, "nombre": nombre, "entorno": env,
                                  "expira": time.time() + TTL_TOKEN_CAMBIO}
    return {"simulacion": simulacion, "token_confirmacion": token,
            "instruccion": ("Muestra este resumen al usuario y pide su confirmacion EXPLICITA. "
                            "Solo si dice que si, llama aplicar_cambio con el token. "
                            "El token vence en 15 minutos y es de un solo uso.")}


def _aplicar_cambio(token_confirmacion: str) -> dict:
    pendiente = _cambios_pendientes.pop(token_confirmacion, None)
    if not pendiente or pendiente["expira"] < time.time():
        raise pa_api.PaApiError("Token invalido, usado o vencido: corre simular_cambio de nuevo "
                                "y vuelve a pedir confirmacion al usuario.")
    tok = _token_o_error()
    op, env = pendiente["operacion"], pendiente["entorno"]
    if op == "actualizar":
        r = pa_api.actualizar_flujo(tok, env, pendiente["flow_id"],
                                    pendiente["defn"], pendiente["connrefs"])
        return {"hecho": True, "operacion": op, "via": r["via"], "respaldo": r["respaldo"],
                "siguiente_paso": "Valida con ver_corridas tras la proxima ejecucion."}
    if op == "crear":
        r = pa_api.crear_flujo(tok, env, pendiente["nombre"],
                               pendiente["defn"], pendiente["connrefs"])
        return {"hecho": True, "operacion": op, "via": r["via"], "flow_id": r["workflowid"],
                "siguiente_paso": ("Nace APAGADO: el usuario debe enlazar las conexiones una vez "
                                   "en el portal y luego simular_cambio(encender).")}
    via = pa_api.cambiar_estado(tok, env, pendiente["flow_id"], op == "encender")
    return {"hecho": True, "operacion": op, "via": via}


# ---------------------------------------------------------------------------
# Registro MCP (descripciones estaticas y cortas: son parte del prompt)
# ---------------------------------------------------------------------------
_RO = ToolAnnotations(readOnlyHint=True)

iniciar_sesion = mcp.tool(
    description="Inicia sesion Microsoft (device code). Devuelve URL+codigo para mostrarselos al usuario. Una sola vez; luego queda en cache.")(_iniciar_sesion)
estado_sesion = mcp.tool(
    annotations=_RO,
    description="Verifica si hay sesion Microsoft activa y quien es el usuario.")(_estado_sesion)
listar_flujos = mcp.tool(
    annotations=_RO,
    description="Lista TODOS los flujos de Power Automate del usuario (id, nombre, estado; 'Suspendido' = bloqueado por politica DLP).")(_listar_flujos)
auditar_flujo = mcp.tool(
    annotations=_RO,
    description="Descarga un flujo del tenant y lo audita localmente contra el catalogo de mejores practicas (Microsoft/Power CAT). Devuelve puntuacion 0-100 y hallazgos con arreglo.")(_auditar_flujo)
ver_corridas = mcp.tool(
    annotations=_RO,
    description="Historial de ejecuciones de un flujo (estado, fechas, codigo de error). Para diagnosticar por que fallo.")(_ver_corridas)
simular_cambio = mcp.tool(
    annotations=_RO,
    description="SIMULA una escritura (actualizar/crear/encender/apagar) sin tocar nada: audita la definicion nueva (bloquea si hay hallazgos ALTA) y devuelve un token de confirmacion de un solo uso. Nunca apliques sin mostrar la simulacion al usuario.")(_simular_cambio)
aplicar_cambio = mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True),
    description="Aplica un cambio previamente simulado y confirmado por el usuario (requiere el token de simular_cambio). Hace respaldo automatico antes de modificar.")(_aplicar_cambio)


def main():
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
