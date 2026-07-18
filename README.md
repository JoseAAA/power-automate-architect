# Power Automate Architect

Copiloto experto para **Microsoft Power Automate** (cloud flows), construido como
plugin de Claude Code. Facil para expertos y no expertos: cada respuesta da
**solución y valor**, no más preguntas.

## Modos disponibles

### 🔍 Auditor (`pa-auditoria`)

Le pasas un flujo **exportado** y te dice qué tan bien sigue las mejores prácticas,
con puntuación, hallazgos por severidad y el **arreglo concreto** de cada uno.

### 🔌 Conectado — lectura (`pa-flujos`)

**Un solo login de Microsoft → todos tus flujos, sin exportar zips.**

```bash
python scripts/pa_api.py login     # abre el navegador una vez (o --device)
python scripts/pa_api.py flujos    # lista TODOS tus flujos (Mis flujos + soluciones)
python scripts/pa_api.py auditar <ID>   # descarga y audita con el catálogo completo, local
python scripts/pa_api.py corridas <ID>  # historial de ejecuciones (diagnóstico)
```

Requiere `pip install msal msal-extensions`. Usa login delegado con un client
first-party de Microsoft (sin registrar apps; `--client-id` propio como fallback),
tokens en caché cifrada local, y habla SOLO con `api.flow.microsoft.com`. Solo
lectura: no modifica nada del tenant.

- **Privado y offline:** el análisis corre 100% en tu máquina (Python). No envía
  datos a ningún servicio externo. Ideal para datos sensibles (legal, RR.HH.).
- **Eficiente en tokens:** todo el análisis pesado es determinista en
  `scripts/auditar_flujo.py`; el asistente solo lo ejecuta y lo explica en simple.
- **Fundamentado:** cada regla cita Microsoft Learn (coding guidelines /
  Well-Architected) y expertos reconocidos. Ver `references/buenas-practicas.md`.

### Cómo se usa

1. En Power Automate: **Mis flujos → … → Exportar → Paquete (.zip)**.
2. En Claude Code, dile: *"audita este flujo"* y pásale la ruta al `.zip`
   (o a la carpeta descomprimida, o al `definition.json`).
3. Recibes el informe en el chat con el veredicto y los pasos para mejorar.

### Probar a mano

```bash
python scripts/auditar_flujo.py "ruta/al/flujo.zip"   # auditar un flujo
python evals/verificar_auditor.py                     # regresión del auditor
```

El catálogo tiene **39 reglas automatizadas** (severidad ALTA/MEDIA/BAJA/INFO),
alineadas con el Power CAT Tools Code Review de Microsoft. Ver
`references/buenas-practicas.md`.

## Estructura

```
power-automate-architect/
├── .claude-plugin/        plugin.json + marketplace.json
├── skills/
│   ├── pa-auditoria/      modo Auditor (flujo exportado)
│   ├── pa-flujos/         modo conectado de lectura (login único)
│   ├── pa-actualizar/     vigilante del catálogo (novedades de Microsoft)
│   └── pa-conectado/      despliegue vía pac CLI (en evolución)
├── scripts/
│   ├── auditar_flujo.py        analizador determinista, 39 reglas
│   ├── pa_api.py               conector (MSAL + maker API, solo lectura)
│   └── actualizar_catalogo.py  vigila las fuentes oficiales (GitHub)
├── evals/
│   ├── verificar_auditor.py    regresión: códigos exactos por flujo de prueba
│   ├── verificar_conector.py   prueba offline del conector (API simulada)
│   └── flujos/                 5 flujos de prueba (4 con fallas + 1 limpio)
└── references/
    ├── buenas-practicas.md      catálogo de reglas PA-xxx + fuentes oficiales
    ├── reglas-candidatas.md     backlog de reglas + estado de implementación
    ├── ia-en-flujos.md          IA en Power Automate: costos y cuándo usarla
    ├── api-conexion.md          arquitectura login único → todos los flujos
    ├── estado-fuentes.json      última revisión de cada fuente oficial
    └── panorama-herramientas.md mercado 2026: reutilizar vs construir
```

## En el roadmap

- **✍️ Escritura (fase 3):** aplicar arreglos y crear flujos vía la **Web API de
  Dataverse** (tabla `workflow`, la vía soportada por Microsoft) con confirmación
  previa; migración de flujos legacy a soluciones. Arquitectura ya investigada en
  `references/api-conexion.md`.
- **🧙 Modo Copiloto (fase 4):** crear un flujo nuevo desde cero con pocas
  preguntas, ya cumpliendo el catálogo de reglas.
- **🔄 Actualizador (fase 5): ✅ entregado.** `python scripts/actualizar_catalogo.py`
  detecta cambios en las fuentes oficiales (skill `pa-actualizar`); cadencia
  mensual sugerida.
- `skills/pa-conectado/` (despliegue vía `pac` CLI por soluciones) queda como vía
  alternativa de ALM hasta que la fase 3 la reemplace.

> Alternativas evaluadas y descartadas para datos sensibles: FlowStudio MCP (SaaS
> de pago) y MCPs de terceros — ver `references/panorama-herramientas.md` y
> `references/nota-ti-flowstudio.md`.

## Fuentes

Microsoft Learn (Power Automate coding guidelines, Power Platform Well-Architected,
ALM), Matthew Devaney, Forward Forever, Reza Dorrani, Tom Riha, Pieter Veenstra.
