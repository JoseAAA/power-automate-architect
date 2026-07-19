---
name: pa-flujos
allowed-tools: Bash(python *)
description: >
  Modo conectado de LECTURA (vía 100% Microsoft, sin terceros): un solo login →
  listar, inspeccionar y auditar TODOS los cloud flows del usuario sin exportar
  zips. USAR cuando el usuario dice "conéctate a Power Automate", "lista mis
  flujos", "qué flujos tengo", "audita mi flujo X" (sin adjuntar archivo),
  "por qué falló mi flujo", "muéstrame las corridas", "descarga la definición",
  "inicia sesión". NO modifica ni despliega flujos (para eso: pa-conectado).
---

# Modo conectado (lectura) — todos los flujos con un solo login

Objetivo: que el usuario NO exporte zips a mano. Con un login de su cuenta
Microsoft, el conector `pa_api.py` lista todos sus flujos ("Mis flujos" + los de
solución), descarga definiciones, muestra corridas y audita contra el catálogo completo de reglas.

## Privacidad (explícala si preguntan)
- Habla SOLO con `api.flow.microsoft.com` (Microsoft) con login delegado del
  propio usuario (MSAL + client first-party de Microsoft; sin registrar apps).
- Tokens en caché local cifrada (DPAPI). Ningún tercero ve nada.
- El análisis de reglas corre 100% local (`auditar_flujo.py`).

## Comandos (todos vía `${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py`)

Requisito único: `pip install msal msal-extensions requests` (si falta, instálalo).
Para encadenar resultados agrega `--json` a `flujos`/`corridas` (contrato estable,
ver `${CLAUDE_PLUGIN_ROOT}/references/contrato-agente.md`); no raspes el texto humano.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" login            # abre el navegador (una vez)
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" login --device   # alternativa con código
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" sesion           # a qué cuenta(s) estás conectado
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" cambiar-cuenta <correo>  # cambiar de cuenta (ej. la de tu empresa)
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" entornos
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" flujos           # TODOS los flujos del usuario
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" flujo <ID> --guardar flujo.json
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" corridas <ID>
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" auditar <ID>     # descarga + auditoría local
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" auditar-todos --detalle informe.json  # tablero del tenant
```

## Procedimiento

1. **Sesión.** Intenta directamente el comando pedido (ej. `flujos`). Si sale
   `ERROR: No hay sesion activa` (exit 3), avisa al usuario que se abrirá el
   navegador para iniciar sesión con su cuenta de trabajo y corre `login`
   (espera hasta 5 min). Si el navegador no es viable, `login --device`.
   - **Transparencia de cuenta:** `flujos`/`entornos` muestran "conectado como
     &lt;correo&gt;". Menciónaselo al usuario. Si dice que sus flujos están en OTRA
     cuenta (ej. la de la empresa), usa `login` para agregarla y luego
     `cambiar-cuenta &lt;correo&gt;` (o `sesion` para ver las disponibles).
2. **Listar.** `flujos` → presenta en lenguaje llano: cuántos hay, cuáles están
   apagados (`Stopped`) y sobre todo cuáles **Suspendido** (= bloqueados por
   política DLP: eso hay que decirlo claro). Ofrece auditar los importantes.
3. **Auditar.** `auditar <ID>` → presenta el informe igual que la skill
   `pa-auditoria`: resumen ejecutivo con semáforo (🟢 ≥90 · 🟡 75-89 · 🟠 50-74 ·
   🔴 <50), tabla por severidad con arreglos, lo bueno, y UNA oferta de acción.
4. **Diagnosticar fallas.** `corridas <ID>` → si hay `Failed`, correlaciona con
   los hallazgos de la auditoría (ej. sin retry → fallas transitorias) y explica
   el arreglo concreto.
5. **Tablero del tenant** ("audita todos mis flujos", "¿cómo está mi tenant?"):
   `auditar-todos --detalle informe.json`. Presenta al usuario SOLO el resumen
   que imprime (media, distribución 🟢🟡🟠🔴, peores, reglas más incumplidas) —
   es de tamaño fijo aunque haya cientos de flujos. **NO leas el archivo
   `--detalle`**: es el detalle por flujo y solo se abre si el usuario pide uno
   concreto (o audita ese flujo con `auditar <ID>`). Así el costo en tokens es
   mínimo sin importar el tamaño del tenant.

## Errores comunes y qué hacer
- **"Se necesita aprobación del administrador" al hacer login:** el tenant exige
  consentimiento. Opciones: TI aprueba el client, o crear una app propia y usar
  `--client-id <guid>` (guía en `${CLAUDE_PLUGIN_ROOT}/references/api-conexion.md`).
- **403 en un flujo:** el usuario no es dueño/co-propietario de ese flujo.
- **La respuesta no trae la definición:** flujo de otro dueño → pedir co-propiedad.
- **429/throttling:** el conector ya reintenta con backoff; si persiste, esperar.

## Reglas de oro
- Este modo es SOLO LECTURA: jamás modifica nada del tenant.
- Nunca muestres ni registres tokens; no pegues el contenido de la caché.
- IDs de flujo/entorno son GUIDs largos: usa siempre los que devuelve `flujos`,
  no los inventes ni los recortes.
