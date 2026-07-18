#!/usr/bin/env python3
"""
verificar_conector.py - Prueba offline del conector pa_api.py (sin red ni login).

Simula las respuestas de la maker API (monkeypatch de pa_api._http) y verifica:
  1. listar_entornos + deteccion del entorno por defecto
  2. listar_flujos sigue la paginacion (nextLink) y pide includeSolutionCloudFlows
  3. obtener_flujo -> guardar_flujo -> auditar_flujo.py da 100/100 (ciclo completo)
  4. guardar_flujo normaliza connectionReferences cuando viene como lista
  5. listar_corridas parsea el historial

  python evals/verificar_conector.py     -> exit 0 si todo pasa, 1 si algo falla
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import pa_api  # noqa: E402

FLUJO_LIMPIO = json.loads((RAIZ / "evals" / "flujos" / "flujo-limpio.json")
                          .read_text(encoding="utf-8"))["properties"]

URLS_PEDIDAS = []


def _http_falso(metodo, url, token, cuerpo=None, intentos=3):
    URLS_PEDIDAS.append(url)
    assert metodo == "GET", f"comando de lectura hizo {metodo}"
    if "/environments?" in url:
        return {"value": [
            {"name": "guid-secundario", "properties": {"displayName": "Sandbox", "isDefault": False}},
            {"name": "Default-tenant1", "properties": {"displayName": "Contoso (default)", "isDefault": True}},
        ]}
    if "/flows?" in url:
        return {"value": [
            {"name": "flow-a", "properties": {"displayName": "Flujo A", "state": "Started"}},
            {"name": "flow-b", "properties": {"displayName": "Flujo B", "state": "Stopped",
                                              "flowSuspensionReason": "None"}},
        ], "nextLink": "https://fake.local/pagina2"}
    if url == "https://fake.local/pagina2":
        return {"value": [
            {"name": "flow-c", "properties": {"displayName": "Flujo C (solucion)", "state": "Started"}},
        ]}
    if "/flows/FLOW123?" in url:
        return {"name": "FLOW123", "properties": {
            "displayName": FLUJO_LIMPIO["displayName"],
            "description": FLUJO_LIMPIO["description"],
            "state": "Started",
            "definition": FLUJO_LIMPIO["definition"],
            # como LISTA a proposito: guardar_flujo debe normalizarla a dict
            "connectionReferences": [
                {"connectionName": "sp-legal", "source": "Invoker",
                 "id": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"},
            ],
        }}
    if "/runs?" in url:
        return {"value": [
            {"properties": {"status": "Succeeded", "startTime": "2026-07-16T07:00:01Z",
                            "endTime": "2026-07-16T07:00:09Z"}},
            {"properties": {"status": "Failed", "startTime": "2026-07-15T07:00:01Z",
                            "endTime": "2026-07-15T07:00:04Z",
                            "error": {"code": "ActionFailed"}}},
        ]}
    raise AssertionError(f"URL inesperada: {url}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # Aislar del entorno real: sin red, sin login, sin tocar la config del usuario
    pa_api._http = _http_falso
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
    check("guarda el entorno en config", _config.get("entorno") == "Default-tenant1")

    # 2. flujos con paginacion e includeSolutionCloudFlows
    flujos = pa_api.listar_flujos(tok, predet)
    check("paginacion: 3 flujos entre 2 paginas", len(flujos) == 3, str(len(flujos)))
    url_flujos = next(u for u in URLS_PEDIDAS if "/flows?" in u)
    check("pide includeSolutionCloudFlows (Mis flujos + soluciones)",
          "include=includeSolutionCloudFlows" in url_flujos, url_flujos)

    # 3+4. obtener -> guardar (normalizando lista) -> auditar = 100/100
    flujo = pa_api.obtener_flujo(tok, predet, "FLOW123")
    destino = RAIZ / "evals" / "flujos" / "_tmp_descargado.json"
    try:
        ruta = pa_api.guardar_flujo(flujo, destino)
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        connrefs = doc["properties"]["connectionReferences"]
        check("connectionReferences normalizada a dict", isinstance(connrefs, dict) and "sp-legal" in connrefs)
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "auditar_flujo.py"), str(ruta)],
                           capture_output=True, text=True, encoding="utf-8")
        check("flujo descargado audita 100/100 y exit 0",
              r.returncode == 0 and re.search(r"PUNTUACION: 100/100", r.stdout or ""),
              f"exit={r.returncode}")
    finally:
        destino.unlink(missing_ok=True)

    # 5. corridas
    corridas = pa_api.listar_corridas(tok, predet, "FLOW123")
    check("historial: 2 corridas y el error parseado", len(corridas) == 2 and
          corridas[1]["properties"]["error"]["code"] == "ActionFailed")

    print("-" * 50)
    print("TODO OK" if not fallas else f"{len(fallas)} verificacion(es) fallida(s)")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
