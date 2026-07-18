# Panorama de herramientas existentes (julio 2026) — qué reutilizar y qué construir

> `investigado: 2026-07-15` · Conclusión central: **no existe** ningún linter
> open-source mantenido para `definition.json` de cloud flows, ni un MCP oficial de
> Microsoft para gestionar flujos. El nicho de este proyecto está validado.

## MCP oficiales de Microsoft

| Servidor | ¿Sirve para gestionar flujos? | Nota |
|---|---|---|
| **Dataverse MCP** (GA) | No en la práctica: herramientas genéricas de registros, `read_query` ~20 filas, `clientdata` de cientos de KB | Además, desde dic-2025 sus llamadas desde agentes externos consumen **créditos Copilot** |
| **pac CLI MCP** (preview, `pac copilot mcp --run`) | Indirecto (solo solution export/import) | pac sigue sin comandos de flujo |
| Power Apps MCP (preview) | No — es para que agentes *ejecuten* flujos/apps, no para auditarlos/editarlos | Centrado en Copilot Studio |
| Process Mining MCP (preview) | No — solo insights de procesos | |

**No existe "Power Automate MCP" oficial para autoría/gestión de flujos (jul-2026).**

## Comunidad / open-source

| Proyecto | Capacidad | Contra |
|---|---|---|
| [rcb0727/powerautomate-mcp](https://github.com/rcb0727/powerautomate-mcp-docs) | 121 herramientas (CRUD de flujos, debug por acción, admin) — activo (v0.13.2 jul-2026), corre local | **Binario cerrado** (solo docs en GitHub) + permisos delegados amplios → inauditables. Referencia de capacidades, no dependencia |
| [FlowStudio MCP](https://mcp.flowstudio.app/) (John Liu) | 25+ herramientas, debug excelente | **SaaS hospedado de pago** ($29-499/mes) — viola el requisito sin-terceros (ver `nota-ti-flowstudio.md`) |
| [kaael1/mcp-power-automate](https://github.com/kaael1/mcp-power-automate) | 23 comandos, local, snapshots/revert | Auth por **captura de token con extensión de navegador** — frágil y gris en ToS |
| [Cliveo/Power-Platform-MCP](https://github.com/Cliveo/Power-Platform-MCP) | Lectura de triggers/runs | Dormido (3 commits) |
| [frankeluoregon/power-automate-mcp](https://github.com/frankeluoregon/power-automate-mcp) | Paquetes exportados offline (Python) | Prototipo (1 commit) |
| [PowerDocu](https://github.com/modery/PowerDocu) | Parser C# maduro de paquetes/soluciones → Word/Markdown | Documenta, no lintea. **Mejor prior-art de parsing** |
| [FlowToVisio](https://github.com/LinkeD365/FlowToVisio) | Diagrama Visio desde definition.json | Prior-art de visualización |

## Analizadores estáticos / linters

- **Flow Checker** (diseñador): errores de inputs + advertencias superficiales; **sin API pública**; no duplicar sus chequeos de validación.
- **Solution checker**: sus reglas publicadas de flujos son solo para **desktop flows** (11 reglas); cloud flows solo pasan por el flow checker superficial. Invocable vía `pac solution check` — útil como chequeo complementario del lado servicio.
- **Power CAT Tools – Code Review** ([GitHub](https://github.com/microsoft/Power-CAT-Tools)): 13 patrones automatizados para cloud flows, corre como app instalada en el entorno (no local). Es el "estándar de facto" de Microsoft → alinear nuestro catálogo con él (ver `reglas-candidatas.md`).
- Comunidad: reglas solo como prosa/blogs; el AutoReview de David Wyatt es extensión de Chrome.

## Ecosistema establecido

- **CoE Starter Kit: retirado (feb-2026).** Sucesores nativos: admin center Inventory/Usage/Monitor/Actions + [Inventory API](https://learn.microsoft.com/power-platform/admin/inventory-api).
- Módulos PowerShell PowerApps: soportados pero legacy (WinPS 5.1); útiles puntualmente (`Add-AdminFlowsToSolution`).
- XrmToolBox (FlowToVisio, run history viewers, PowerAutomateCloudManager): desktop .NET, no scriptables desde Python.

## Veredicto para este proyecto

**Reutilizar:** Dataverse Web API (columna vertebral de escritura soportada) ·
maker API para descubrimiento/lectura · pac CLI solo para ALM por solución +
`pac solution check` · Inventory API para auditoría a escala de tenant ·
PowerDocu/FlowToVisio como prior-art de parsing/visualización.

**No adoptar como dependencia:** FlowStudio MCP (hospedado), rcb0727 (cerrado),
kaael1 (auth frágil), Dataverse MCP para flujos (forma inadecuada + créditos).

**Construir (el valor único del proyecto):**
1. El **linter de cloud flows** en Python — primera herramienta OSS real del espacio.
2. La **capa de operaciones con semántica de flujo** (diff, snapshot/rollback, validar-antes-de-PATCH, remapeo de connectionReferences) sobre las APIs de Microsoft.
3. El **actualizador permanente** del catálogo de reglas (ver `reglas-candidatas.md`).
