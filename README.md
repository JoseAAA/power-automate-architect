# ⚡ Power Automate Architect

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Licencia](https://img.shields.io/badge/Licencia-MIT-green)
![AGENTS.md](https://img.shields.io/badge/est%C3%A1ndar-AGENTS.md-blue)
![Agent Skills](https://img.shields.io/badge/est%C3%A1ndar-Agent%20Skills-blueviolet)
![Local first](https://img.shields.io/badge/privacidad-100%25%20local-brightgreen)

> Habla con tu asistente de IA en español y **audita, arregla y crea flujos de
> Power Automate** con las mejores prácticas oficiales de Microsoft. Sin exportar
> zips, sin servidores de terceros: un login de Microsoft y listo.

---

## 📋 Contenido

- [🚀 Instalación](#-instalación)
- [✨ Funciones](#-funciones)
- [💬 Cómo se usa (ejemplos reales)](#-cómo-se-usa-ejemplos-reales)
- [🧠 Cómo funciona](#-cómo-funciona)
- [🔐 Privacidad](#-privacidad)
- [🩺 Problemas comunes](#-problemas-comunes)
- [🧰 Stack](#-stack)
- [🗺️ Roadmap](#️-roadmap)

---

## 🚀 Instalación

**Prerrequisitos:** [Python 3.10+](https://www.python.org/downloads/) y un agente
de IA con terminal (Claude Code, OpenAI Codex, Gemini CLI u OpenCode).

```bash
git clone https://github.com/JoseAAA/power-automate-architect.git
cd power-automate-architect
pip install msal msal-extensions requests   # solo para el modo conectado
```

Abre la carpeta con tu agente y ya está: el proyecto sigue los estándares
**AGENTS.md** y **Agent Skills**, así que Claude Code, Codex, Gemini CLI y
OpenCode descubren los modos solos (Claude vía `CLAUDE.md`/plugin; el resto vía
`AGENTS.md` + `.agents/skills/`).

> **Solo quieres auditar un flujo exportado (sin conectarte):** no necesitas
> instalar nada más — el auditor es 100% offline con la librería estándar.

---

## ✨ Funciones

- 🔍 **Auditor de flujos** — **40 reglas automatizadas** (severidad
  ALTA/MEDIA/BAJA/INFO) basadas en Microsoft Learn, Well-Architected y el Power
  CAT Tools Code Review. Cada hallazgo trae su arreglo concreto y la fuente.
- 🔑 **Un solo login → todos tus flujos** — lista, descarga, audita y diagnostica
  directo del tenant (login delegado de Microsoft, sin registrar apps).
- ✍️ **Arregla y crea por lenguaje natural** — "agrégale try/catch a mi flujo" o
  "crea un flujo que avise cuando…". Con triple red de seguridad: respaldo
  automático, auditoría previa que bloquea lo malo, y simulación antes de tocar.
- 🧙 **Copiloto con plantillas 100/100** — alertas programadas, aprobaciones y
  clasificación con IA, listas para personalizar sin saber JSON.
- 🤖 **Al día con la IA de Power Automate** — reglas específicas para AI Builder
  y agent flows (créditos, validación de salidas, humano en el circuito).
- 🔄 **Vigilante del catálogo** — detecta cambios en la documentación oficial de
  Microsoft para que las reglas nunca queden viejas.
- 🧪 **Verificado** — 4 suites de regresión (auditor, conector, docs, consistencia)
  con coincidencia exacta y cero falsos positivos tolerados.

---

## 💬 Cómo se usa (ejemplos reales)

Dile a tu asistente, en español:

| Tú dices | El asistente hace |
|---|---|
| *"Audita este flujo"* (+ el .zip exportado) | Informe con semáforo 🟢🟡🟠🔴, hallazgos y arreglos |
| *"Conéctate a Power Automate y lista mis flujos"* | Login de Microsoft (una vez) → tabla de todos tus flujos |
| *"¿Por qué falló mi flujo de vacaciones?"* | Historial de corridas + causa + arreglo |
| *"Agrégale manejo de errores"* | Edita el JSON, lo audita, **te muestra el cambio y espera tu OK** antes de subir (con respaldo) |
| *"Crea un flujo que pida aprobación cuando llegue una solicitud"* | Copiloto: 2-3 preguntas → plantilla 100/100 personalizada → creado (apagado, tú lo enciendes) |
| *"¿Hay novedades de Power Automate?"* | Chequea las fuentes oficiales y propone actualizar reglas |

---

## 🧠 Cómo funciona

```
 Tú (español) ──► Agente de IA (Claude/Codex/Gemini/OpenCode)
                       │  lee las skills (qué hacer y cuándo)
                       ▼
              scripts/ (Python determinista)
              ├─ auditar_flujo.py      analizador determinista, 40 reglas (offline)
              ├─ pa_api.py             conector Microsoft (MSAL, login delegado)
              └─ actualizar_catalogo.py vigilante de fuentes oficiales
                       │
                       ▼
              APIs de Microsoft (con TU login)   ← nada de terceros
```

1. El análisis pesado es **determinista en Python** (0 tokens de razonamiento);
   el asistente solo ejecuta y explica en simple.
2. La escritura va por la **vía soportada de Microsoft** (Dataverse) con
   respaldo + auditoría previa + simulación (`--si` para ejecutar de verdad).
3. Los CLIs tienen salida `--json` con contrato estable
   (`references/contrato-agente.md`) para que cualquier agente encadene pasos
   sin raspar texto.

---

## 🔐 Privacidad

Pensado para datos sensibles (legal, RR.HH., finanzas). Ver [SECURITY.md](SECURITY.md).

| Acción | ¿Sale a la red? |
|---|---|
| Auditar un flujo exportado | ❌ Nunca (100% local) |
| Listar/leer/modificar tus flujos | ✅ Solo a APIs de Microsoft, con tu propio login |
| Chequear novedades del catálogo | ✅ Solo metadatos públicos de GitHub |
| Telemetría, analytics, servidores del proyecto | ❌ No existen |

Tokens en caché local **cifrada** (DPAPI); nunca se muestran ni registran.
`python scripts/pa_api.py logout` borra la sesión.

---

## 🩺 Problemas comunes

| Problema | Solución |
|---|---|
| "No hay sesion activa" | `python scripts/pa_api.py login` (abre el navegador; `--device` para código) |
| "Se necesita aprobación del administrador" al login | Tu tenant exige consentimiento: pide a TI aprobar el client, o usa una app propia con `--client-id` (guía en `references/api-conexion.md`) |
| `flujos` devuelve 0 | Tu cuenta no es dueña/co-dueña de flujos en ese entorno: revisa `entornos` o pide co-propiedad |
| Flujo aparece "Suspendido" | Lo bloqueó una política DLP del tenant: revisa qué conector chocó |
| "La definicion nueva tiene hallazgos ALTA" | Es la red de seguridad: corrige lo señalado (o `--forzar` bajo tu responsabilidad) |
| Un flujo nuevo no corre | Nace apagado: enlaza las conexiones en el portal y luego `encender <ID> --si` |
| 429 / throttling | El conector ya reintenta con backoff; espera un momento |
| Falta `msal` | `pip install msal msal-extensions requests` |

---

## 🧰 Stack

| Capa | Tecnología |
|---|---|
| Análisis de flujos | Python 3 (stdlib), determinista |
| Autenticación | MSAL (OAuth delegado de Microsoft) + msal-extensions (caché DPAPI) |
| APIs | maker API (lectura) · Dataverse Web API (escritura soportada) |
| Instrucciones del agente | AGENTS.md + Agent Skills (`skills/`, espejo `.agents/skills/`) |
| Catálogo de reglas | Microsoft Learn · Power Platform Well-Architected · Power CAT Tools |
| Pruebas | 4 suites en `evals/` (regresión exacta, API simulada, anti-drift) |

Créditos: [Microsoft Learn](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/),
[Power CAT Tools](https://github.com/microsoft/Power-CAT-Tools), Matthew Devaney,
Forward Forever, Tom Riha, Pieter Veenstra, David Wyatt.

---

## 🗺️ Roadmap

- 📦 Release en GitHub (v1.0) y marketplace de plugins de Claude Code
- 🧙 Más plantillas del copiloto (documentos con IA, sincronización de listas)
- 📊 Auditoría masiva: puntuar todos los flujos del tenant de una vez
- 🌐 Conector remoto auto-hosteado (solo si una empresa lo necesita para web/móvil)

Issues y PRs bienvenidos.

---

## 👤 Autor

**JoseAAA** · [github.com/JoseAAA](https://github.com/JoseAAA)

## 📜 Licencia

MIT — ver [LICENSE](LICENSE)
