# ⚡ Power Automate Architect

![Licencia](https://img.shields.io/badge/Licencia-MIT-green)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Funciona con](https://img.shields.io/badge/funciona%20con-Claude%20Code%20·%20Codex%20·%20Gemini%20CLI%20·%20OpenCode-blueviolet)
![Privacidad](https://img.shields.io/badge/privacidad-100%25%20local-brightgreen)

**Audita, corrige y crea flujos de Power Automate hablándole a tu asistente de IA en español — 100% local, con tu propio login de Microsoft.**

Son instrucciones reutilizables (skills) + scripts deterministas que le enseñan a
Claude Code, Codex, Gemini CLI u OpenCode a trabajar con Microsoft Power Automate
siguiendo las mejores prácticas oficiales (Microsoft Learn, Well-Architected,
Power CAT). Para makers y equipos que automatizan con datos sensibles: nada pasa
por servidores de terceros.

---

## 👀 Míralo en acción

```text
Tú ▸ audita mi flujo exportado facturas.zip

Agente ▸ PUNTUACIÓN: 55/100 → ACEPTABLE, requiere mejoras
         🔴 [ALTA]  Sin manejo de errores: si un paso falla, nadie se entera
                    Arreglo: Scope "Try" + Scope "Catch" + Terminate(Failed)
         🟠 [MEDIA] Listado sin paginación: solo llega la primera página
                    Arreglo: activa Paginación o define un tope ($top)
         ...4 hallazgos más, cada uno con su arreglo y la fuente oficial

Tú ▸ aplica el arreglo del manejo de errores al flujo real

Agente ▸ [SIMULACIÓN] Edité la definición y la re-auditė: 92/100 ✓
         Cambio: la lógica queda envuelta en Try/Catch con aviso de error.
         Antes de tocar el tenant haré un respaldo automático. ¿Confirmas?

Tú ▸ sí

Agente ▸ Flujo actualizado vía Dataverse (la vía soportada por Microsoft).
         Respaldo guardado. Última ejecución: ÉXITO ✅
```

Sin `--si` (tu confirmación) nada se ejecuta; una definición con hallazgos
graves **se niega a subir**. La red de seguridad está en el código, no en la
buena voluntad del modelo.

---

## 🚀 Instalación

**Prerrequisito común:** [Python 3.10+](https://www.python.org/downloads/). Para
los modos conectados al tenant: `pip install msal msal-extensions requests` y un
login único (`python scripts/pa_api.py login`).

Elige tu herramienta: [Claude Code](#claude-code) · [Codex](#openai-codex) ·
[Gemini CLI](#gemini-cli) · [OpenCode](#opencode)

### Claude Code

```text
/plugin marketplace add JoseAAA/power-automate-architect
/plugin install power-automate-architect@power-automate-architect-marketplace
```

### OpenAI Codex

```bash
git clone https://github.com/JoseAAA/power-automate-architect.git
```

Abre la carpeta con Codex: `AGENTS.md` y las skills de `.agents/skills/` se
autodescubren (estándares AGENTS.md + Agent Skills).

### Gemini CLI

Igual que Codex: clona y abre la carpeta. `GEMINI.md` y `.agents/skills/` se
autodescubren.

### OpenCode

Igual que Codex: clona y abre la carpeta (OpenCode lee además `skills/` en
formato Claude tal cual).

---

## 💬 Qué puedes pedirle (prompts de ejemplo)

| Modo | Escribe en tu agente, por ejemplo |
|---|---|
| 🔍 **Auditar** un flujo exportado | *"Audita este flujo: C:\descargas\facturas.zip"* |
| 🔑 **Ver tus flujos** del tenant | *"Conéctate a Power Automate y dime cuáles de mis flujos fallaron esta semana"* |
| ✍️ **Corregir** un flujo existente | *"Agrégale manejo de errores a mi flujo de vacaciones y súbelo"* |
| 🧙 **Crear** un flujo nuevo (copiloto) | *"Créame un flujo que pida aprobación cuando llegue una solicitud a SharePoint"* |
| 🔄 **Mantener el catálogo al día** | *"¿Hay novedades de Power Automate? Actualiza las reglas si hace falta"* |

El copiloto parte de **plantillas que auditan 100/100** (alertas programadas,
aprobaciones, clasificación con IA) y hace máximo 2-3 preguntas.

---

## 🧠 Cómo funciona (y por qué es seguro)

- **El análisis pesado no lo hace la IA**: es un analizador determinista, 40 reglas
  en Python puro (también a mano: `python scripts/auditar_flujo.py "flujo.zip"`).
  El catálogo completo: [references/buenas-practicas.md](references/buenas-practicas.md),
  con **40 reglas automatizadas** alineadas al Power CAT Tools Code Review de Microsoft.
- **Local-first**: el auditor es 100% offline; los modos conectados hablan SOLO
  con APIs de Microsoft usando tu login delegado (MSAL, tokens en caché cifrada).
  Sin telemetría, sin backend del proyecto.
- **Escritura con defensa en profundidad**: simulación por defecto, respaldo
  automático antes de tocar, auditoría previa que bloquea hallazgos graves, y la
  vía soportada por Microsoft (Dataverse) antes que APIs no soportadas.
- **Multi-agente por estándares abiertos**: AGENTS.md + Agent Skills; los CLIs
  tienen salida `--json` con contrato estable para encadenar pasos.
- Modelo de seguridad completo para TI: [SECURITY.md](SECURITY.md).

---

## 📚 Documentación

- **Modos (skills):** [Auditor](skills/pa-auditoria/SKILL.md) ·
  [Conectado lectura](skills/pa-flujos/SKILL.md) ·
  [Escritura](skills/pa-conectado/SKILL.md) ·
  [Copiloto](skills/pa-copiloto/SKILL.md) ·
  [Actualizador](skills/pa-actualizar/SKILL.md)
- **Catálogo de reglas PA-XXX:** [buenas-practicas.md](references/buenas-practicas.md) ·
  backlog: [reglas-candidatas.md](references/reglas-candidatas.md)
- **IA en Power Automate (créditos, cuándo usarla):** [ia-en-flujos.md](references/ia-en-flujos.md)
- **Arquitectura de conexión (APIs, login):** [api-conexion.md](references/api-conexion.md)
- **Contrato JSON para agentes:** [contrato-agente.md](references/contrato-agente.md)
- **Seguridad:** [SECURITY.md](SECURITY.md) · **Cambios:** [CHANGELOG.md](CHANGELOG.md)
- **Verificar tras cambios:** `python evals/verificar_auditor.py && python evals/verificar_conector.py && python evals/verificar_docs.py`

---

## 🤝 Contribuir y licencia

Issues y PRs bienvenidos (convenciones en [AGENTS.md](AGENTS.md)).
**JoseAAA** · [github.com/JoseAAA](https://github.com/JoseAAA) · MIT — ver [LICENSE](LICENSE)
