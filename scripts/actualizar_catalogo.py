#!/usr/bin/env python3
"""
actualizar_catalogo.py - Vigilante de las fuentes del catalogo de reglas.

Consulta los repos publicos de GitHub que respaldan Microsoft Learn y el
Power CAT Tools (1 llamada HTTP por fuente, sin autenticacion) y reporta que
cambio desde la ultima revision: commits nuevos y paginas agregadas/eliminadas.
Con eso se decide si hay que actualizar buenas-practicas.md y auditar_flujo.py.

Uso:
  python actualizar_catalogo.py                  Reporta cambios desde la ultima revision
  python actualizar_catalogo.py --marcar-revisado  Ademas, registra 'revisado hoy'

Primera corrida: crea la linea base (fecha + inventario de paginas) sin ruido.
Estado en references/estado-fuentes.json (versionado en git a proposito: el
historial muestra cuando se reviso cada fuente).

Salida: exit 0 = sin cambios, 1 = HAY cambios que revisar, 2 = error de red/API.
Solo lee metadatos publicos de GitHub; no envia ningun dato del usuario.
"""
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "references" / "estado-fuentes.json"

# (clave, repo, ruta_dentro_del_repo)
FUENTES = [
    ("guias-codigo", "MicrosoftDocs/power-automate-docs", "articles/guidance/coding-guidelines"),
    ("limites", "MicrosoftDocs/power-automate-docs", "articles/limits-and-config.md"),
    ("well-architected", "MicrosoftDocs/power-platform", "power-platform/well-architected"),
    ("alm", "MicrosoftDocs/power-platform", "power-platform/alm"),
    ("power-cat-review", "microsoft/Power-CAT-Tools", "CODE_REVIEW.md"),
]

CABECERAS = {"User-Agent": "power-automate-architect (auditoria de catalogo)",
             "Accept": "application/vnd.github+json"}


def _get_json(url):
    req = urllib.request.Request(url, headers=CABECERAS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("GitHub limito las llamadas anonimas (60/hora). Reintenta en un rato.")
        raise RuntimeError(f"GitHub respondio {e.code} para {url}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Sin red o GitHub inaccesible: {e.reason}")


def commits_desde(repo, ruta, desde_iso):
    url = (f"https://api.github.com/repos/{repo}/commits"
           f"?path={ruta}&since={desde_iso}&per_page=50")
    return _get_json(url)


def paginas_actuales(repo, ruta):
    """Lista de archivos .md de una carpeta (o [ruta] si la fuente es un archivo)."""
    if ruta.endswith(".md"):
        return [ruta.rsplit("/", 1)[-1]]
    datos = _get_json(f"https://api.github.com/repos/{repo}/contents/{ruta}")
    return sorted(x["name"] for x in datos if x.get("name", "").endswith(".md"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    marcar = "--marcar-revisado" in sys.argv
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        estado = {}

    hay_cambios = False
    primera_vez = not estado

    print("=" * 70)
    print("VIGILANTE DEL CATALOGO - fuentes oficiales de mejores practicas")
    print("=" * 70)

    for clave, repo, ruta in FUENTES:
        previo = estado.get(clave, {})
        desde = previo.get("ultima_revision")
        try:
            paginas = paginas_actuales(repo, ruta)
            if not desde:
                estado[clave] = {"ultima_revision": ahora, "paginas": paginas}
                print(f"\n[{clave}] linea base creada ({len(paginas)} pagina(s)). "
                      "Nada que revisar todavia.")
                continue
            commits = commits_desde(repo, ruta, desde)
            nuevas = sorted(set(paginas) - set(previo.get("paginas", [])))
            quitadas = sorted(set(previo.get("paginas", [])) - set(paginas))
            if not commits and not nuevas and not quitadas:
                print(f"\n[{clave}] sin cambios desde {desde[:10]}.")
            else:
                hay_cambios = True
                print(f"\n[{clave}] {len(commits)} commit(s) desde {desde[:10]}  "
                      f"(https://github.com/{repo}/commits/main/{ruta})")
                for c in commits[:10]:
                    fecha = (c.get("commit", {}).get("committer", {}) or {}).get("date", "?")[:10]
                    msg = (c.get("commit", {}).get("message", "?") or "?").splitlines()[0][:90]
                    print(f"    {fecha}  {msg}")
                if len(commits) > 10:
                    print(f"    ... y {len(commits) - 10} mas")
                for p in nuevas:
                    print(f"    + PAGINA NUEVA: {p}  <- posible regla nueva")
                for p in quitadas:
                    print(f"    - pagina eliminada/renombrada: {p}  <- revisar reglas que la citen")
            if marcar:
                estado[clave] = {"ultima_revision": ahora, "paginas": paginas}
        except RuntimeError as e:
            print(f"\n[{clave}] ERROR: {e}")
            return 2

    if primera_vez or marcar:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "-" * 70)
    if primera_vez:
        print("Linea base registrada en references/estado-fuentes.json.")
        print("Proxima corrida (sugerida: mensual) reportara todo lo que cambie.")
        return 0
    if hay_cambios:
        print("HAY CAMBIOS: revisar las paginas afectadas y decidir si el catalogo")
        print("(buenas-practicas.md + auditar_flujo.py) necesita reglas nuevas o ajustes.")
        print("Cuando el catalogo quede al dia:  python scripts/actualizar_catalogo.py --marcar-revisado")
        return 1
    print("Catalogo al dia con todas las fuentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
