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
         Antes de tocar el tenant haré un respaldo automático. ¿Confirmas?

Tú ▸ sí

Agente ▸ Flujo actualizado vía Dataverse (la vía soportada por Microsoft).
         Respaldo guardado. Última ejecución: ÉXITO ✅
```

Sin tu confirmación nada se ejecuta; una definición con hallazgos graves **se
niega a subir**. La red de seguridad está en el código, no en la buena voluntad
del modelo.

---

## 🚀 Instalación

**Prerrequisito:** [Python 3.10+](https://www.python.org/downloads/). Elige tu
herramienta: [Claude Code](#claude-code) · [Codex](#openai-codex) ·
[Gemini CLI](#gemini-cli) · [OpenCode](#opencode)

### Claude Code

```text
/plugin marketplace add JoseAAA/power-automate-architect
/plugin install power-automate-architect@power-automate-architect-marketplace
```
Para actualizarlo más adelante: `/plugin marketplace update power-automate-architect-marketplace`
y luego `/plugin update power-automate-architect@power-automate-architect-marketplace`.

### OpenAI Codex

```bash
git clone https://github.com/JoseAAA/power-automate-architect.git
```
Abre la carpeta con Codex: `AGENTS.md` y las skills de `.agents/skills/` se
autodescubren (estándares AGENTS.md + Agent Skills).

### Gemini CLI

Igual que Codex: clona y abre la carpeta (`GEMINI.md` + `.agents/skills/`).

### OpenCode

Igual que Codex: clona y abre la carpeta (además lee `skills/` en formato Claude).

---

## 🏁 Primeros pasos

Hay **dos formas de usarlo** según lo que necesites:

### A) Solo auditar un flujo exportado — sin conectarte a nada

No necesita login ni instalar más. En Power Automate: **Mis flujos → ⋯ →
Exportar → Paquete (.zip)**. Luego dile a tu agente:

> *"audita este flujo: C:\descargas\mi-flujo.zip"*

### B) Conectarte a tu tenant — listar, auditar, corregir y crear flujos

Requiere iniciar sesión **una sola vez**, y se hace **hablándole al agente** — no
tienes que tocar la terminal:

**1.** Instala las dependencias (una vez): `pip install msal msal-extensions requests`

**2.** Dile a tu agente: *"conéctate a Power Automate"*. Te dará **un enlace y un
código**; abre el enlace, ingresa el código e inicia con tu cuenta de Microsoft.
Avísale al agente cuando termines y él confirma *"Sesión iniciada como…"*. Queda
guardado en una caché cifrada; no lo repites.

**3.** Habla normal: *"lista mis flujos"*, *"audita todos mis flujos"*, *"¿qué
flujos están fallando por conexiones rotas?"*…

> ¿Prefieres la terminal? También puedes: `python scripts/pa_api.py login` (si
> clonaste el repo) — abre el navegador directamente.

---

## 💬 Qué puedes pedirle (prompts de ejemplo)

| Quiero… | Escríbele a tu agente, por ejemplo |
|---|---|
| 🔍 **Auditar** un flujo exportado | *"Audita este flujo: C:\descargas\facturas.zip"* |
| 🔑 **Ver mis flujos** del tenant | *"Lista mis flujos de Power Automate"* |
| 📊 **Revisar TODO el tenant** | *"Audita todos mis flujos y dame el panorama"* |
| 🩺 **Salud / conexiones rotas** | *"¿Qué flujos están fallando por conexiones desconectadas?"* |
| 🧭 **Por qué falló** un flujo | *"¿Por qué falló mi flujo de vacaciones esta semana?"* |
| ✍️ **Corregir** un flujo | *"Agrégale manejo de errores a mi flujo de vacaciones y súbelo"* |
| 🧙 **Crear** un flujo nuevo | *"Créame un flujo que pida aprobación cuando llegue una solicitud a SharePoint"* |
| 👥 **Ver/cambiar cuenta** | *"¿A qué cuenta estoy conectado?"* · *"Conéctate con mi cuenta de la empresa"* |
| 🔄 **Catálogo al día** | *"¿Hay novedades de Power Automate? Actualiza las reglas si hace falta"* |

El copiloto (crear) parte de **plantillas que auditan 100/100** y hace máximo
2-3 preguntas. Las auditorías del tenant devuelven un **resumen compacto** (el
detalle va a un archivo), así que auditar 1 o 500 flujos cuesta casi lo mismo.

---

## 👥 Varias cuentas (personal / empresa)

Si tus flujos de trabajo están en otra cuenta, puedes tener varias e ir
cambiando — todo **por lenguaje natural**, díselo al agente:

| Quiero… | Dile al agente |
|---|---|
| Ver a qué cuentas estoy conectado | *"¿a qué cuentas estoy conectado?"* |
| Agregar la cuenta de la empresa | *"conéctate con mi cuenta correo@empresa.com"* |
| Cambiar la cuenta activa | *"usa mi cuenta correo@empresa.com"* |
| Cerrar una cuenta / todas | *"cierra la sesión de correo@empresa.com"* · *"cierra todas las sesiones"* |

(El agente corre los comandos por ti: `sesion`, `login`, `cambiar-cuenta`,
`logout`.)

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
- Modelo de seguridad completo para TI: [SECURITY.md](SECURITY.md).

---

## 🩺 Problemas comunes

| Problema | Solución |
|---|---|
| **"No se abrió la página" al iniciar sesión** | Dile al agente *"conéctate a Power Automate"*: te dará un enlace + código para abrir a mano (no depende de que abra el navegador). |
| **Dice que no hay sesión / no ve mis flujos** | Conéctate (paso B). Pregúntale *"¿a qué cuenta estoy conectado?"* para verificar. |
| **"Se necesita aprobación del administrador"** | Tu tenant exige consentimiento: pídelo a TI, o usa una app propia con `--client-id` (ver [api-conexion.md](references/api-conexion.md)). |
| **El agente no toma la última versión** | Actualiza el plugin: `/plugin marketplace update …` → `/plugin update …`. |
| **Errores `jq: command not found`** | **No son de este plugin** — son de otro plugin tuyo (`claude-code-warp`). Instala `jq` (`winget install jqlang.jq`) o desactiva ese plugin. |
| **Un flujo aparece "Suspendido"** | Lo bloqueó una política DLP del tenant; el reporte de salud te dice cuál. |
| **Una conexión dice "Error"** | Se desconectó/caducó: reconéctala en make.powerautomate.com → Conexiones, y reactiva el flujo. |

---

## 📚 Documentación

- **Modos (skills):** [Auditor](skills/pa-auditoria/SKILL.md) ·
  [Conectado lectura](skills/pa-flujos/SKILL.md) ·
  [Escritura](skills/pa-conectado/SKILL.md) ·
  [Copiloto](skills/pa-copiloto/SKILL.md) ·
  [Actualizador](skills/pa-actualizar/SKILL.md)
- **Catálogo de reglas PA-XXX:** [buenas-practicas.md](references/buenas-practicas.md)
- **IA en Power Automate (créditos, cuándo usarla):** [ia-en-flujos.md](references/ia-en-flujos.md)
- **Arquitectura de conexión (APIs, login, cuentas):** [api-conexion.md](references/api-conexion.md)
- **Seguridad:** [SECURITY.md](SECURITY.md) · **Cambios:** [CHANGELOG.md](CHANGELOG.md)

---

## 🤝 Contribuir y licencia

Issues y PRs bienvenidos (convenciones en [AGENTS.md](AGENTS.md)).
**JoseAAA** · [github.com/JoseAAA](https://github.com/JoseAAA) · MIT — ver [LICENSE](LICENSE)
