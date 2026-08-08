#!/usr/bin/env python3
"""
verificar_docs.py - Consistencia documental (anti-drift, estilo ponytail).

Verifica que la documentacion no se desalinee del codigo ni entre si:
  1. El espejo .agents/skills/ esta sincronizado con skills/.
  2. El numero de reglas declarado en buenas-practicas.md y README == reglas
     reales definidas en scripts/auditar_flujo.py.
  3. Frases canario: invariantes criticos presentes donde deben estar
     (red de seguridad de escritura, semaforo, consulta puntual del catalogo).
  4. Descriptions de las skills: <=550 caracteres y con disparador "USAR cuando".

  python evals/verificar_docs.py   -> exit 0 si todo cuadra, 1 si hay drift
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# archivo -> frases que DEBEN estar presentes (comparacion en minusculas)
CANARIOS = {
    # incluye la politica anti-invencion: solo fuentes OFICIALES, con enlace
    "AGENTS.md": ["--si", "dry-run", "respaldo", "confirmación explícita", "pa-xxx-nn",
                  "nunca inventes", "learn.microsoft.com"],
    "skills/pa-conectado/SKILL.md": ["--si", "dry-run", "respaldo", "auditoría previa",
                                     "confirmación explícita"],
    "skills/pa-auditoria/SKILL.md": ["🟢 ≥90"],
    "skills/pa-copiloto/SKILL.md": ["nunca inventes", "learn.microsoft.com"],
    # triaje proporcional: lectura sin plan, escritura con UN plan y UN OK
    "skills/pa-flujos/SKILL.md": ["no armes un plan"],
}
CANARIOS["AGENTS.md"] += ["triaje", "al punto", "una aprobación por tarea"]
CANARIOS["skills/pa-conectado/SKILL.md"] += ["un solo plan, un solo ok"]

DESCRIPCION_RE = re.compile(r"(?s)^---.*?description:\s*>\s*(.*?)\n---", re.M)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    fallas = []

    def check(nombre, cond, detalle=""):
        print(f"{'OK  ' if cond else 'FALLO'} {nombre}" + (f"  [{detalle}]" if detalle and not cond else ""))
        if not cond:
            fallas.append(nombre)

    # 1. espejo .agents/skills sincronizado
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "sincronizar_skills.py"),
                        "--check"], capture_output=True, text=True, encoding="utf-8")
    check("espejo .agents/skills al dia", r.returncode == 0, (r.stdout or "").strip()[:120])

    # 2. conteo de reglas: codigo vs documentacion
    codigo = (RAIZ / "scripts" / "auditar_flujo.py").read_text(encoding="utf-8")
    reales = len(set(re.findall(r"\"(PA-[A-Z]+-\d+)\":", codigo)))
    for doc, patron in [("references/buenas-practicas.md", r"\*\*(\d+) reglas automatizadas\*\*"),
                        ("README.md", r"\*\*(\d+) reglas automatizadas\*\*"),
                        ("README.md", r"analizador determinista, (\d+) reglas")]:
        texto = (RAIZ / doc).read_text(encoding="utf-8")
        m = re.search(patron, texto)
        declaradas = int(m.group(1)) if m else -1
        check(f"conteo de reglas en {doc} ({patron[:20]}...)", declaradas == reales,
              f"doc dice {declaradas}, el codigo tiene {reales}")

    # 3. frases canario
    for archivo, frases in CANARIOS.items():
        texto = (RAIZ / archivo).read_text(encoding="utf-8").lower()
        faltan = [f for f in frases if f.lower() not in texto]
        check(f"canarios en {archivo}", not faltan, "faltan: " + ", ".join(faltan))

    # 4. las plantillas del copiloto deben auditar 100/100 (exit 0; INFO permitido)
    for plantilla in sorted((RAIZ / "skills" / "pa-copiloto" / "plantillas").glob("*.json")):
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "auditar_flujo.py"),
                            str(plantilla), "--json"],
                           capture_output=True, text=True, encoding="utf-8")
        try:
            datos = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            datos = {}
        check(f"plantilla {plantilla.name} audita 100/100",
              r.returncode == 0 and datos.get("puntuacion") == 100,
              f"exit={r.returncode}, puntuacion={datos.get('puntuacion')}")

    # 4b. PRIVACIDAD: ningun dato real de tenant/empresa en los archivos versionados.
    # Este repo es open source: correos, dominios de SharePoint o nombres de cuenta
    # reales NO deben viajar. Solo se permiten dominios de ejemplo.
    DOMINIOS_OK = ("example.com", "example.org", "contoso.com", "contoso.sharepoint.com",
                   "empresa.com", "bigcorp.com", "tuempresa.com", "midominio.com",
                   "microsoft.com", "github.com", "x.com")  # x.com: fixture de prueba
    # anotaciones OData (publisherid@odata.bind) no son correos
    NO_CORREO = ("odata.bind", "odata.etag", "odata.context", "odata.nextlink")
    correo_re = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
    sp_re = re.compile(r"https://([a-z0-9\-]+)\.sharepoint\.com", re.I)
    rastreados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                                text=True, encoding="utf-8").stdout.split()
    fugas = []
    for rel in rastreados:
        f = RAIZ / rel
        if not f.is_file() or f.suffix.lower() not in (".md", ".py", ".json", ".txt", ".yml", ".yaml"):
            continue
        try:
            texto = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for dom in correo_re.findall(texto):
            d = dom.lower().rstrip(".")
            if d not in DOMINIOS_OK and d not in NO_CORREO:
                fugas.append(f"{rel}: correo @{d}")
        for host in sp_re.findall(texto):
            if host.lower() not in ("contoso", "example", "tuempresa"):
                fugas.append(f"{rel}: sharepoint {host}")
    check("privacidad: sin correos/dominios reales en archivos versionados",
          not fugas, "; ".join(sorted(set(fugas))[:4]))

    # 5. descriptions: cortas y con disparador
    for skill_md in sorted((RAIZ / "skills").glob("*/SKILL.md")):
        texto = skill_md.read_text(encoding="utf-8")
        m = DESCRIPCION_RE.search(texto)
        desc = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        nombre = skill_md.parent.name
        check(f"description de {nombre}: <=550 chars y 'USAR cuando'",
              0 < len(desc) <= 550 and "USAR cuando" in desc,
              f"{len(desc)} chars")

    print("-" * 50)
    print("TODO OK" if not fallas else f"{len(fallas)} verificacion(es) fallida(s)")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
