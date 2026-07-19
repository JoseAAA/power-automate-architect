# Conexión programática a Power Automate — referencia técnica

> `investigado: 2026-07-15` · Objetivo: **un solo login → acceso a TODOS los flujos**
> (listar, leer, crear, modificar, activar, historial) desde Python local, sin
> servidores de terceros y sin registrar una app en Entra ID.

## Resumen ejecutivo — las 4 superficies de API

| Superficie | Base URL | Cubre | ¿Escritura? | ¿Sin registrar app? | Estado |
|---|---|---|---|---|---|
| **Maker/Flow API** | `api.flow.microsoft.com` (provider `Microsoft.ProcessSimple`) | "Mis flujos" **y** flujos de solución (`include=includeSolutionCloudFlows`) | Sí: create, update, on/off, delete, runs | **Sí** (client first-party) | Funciona (es lo que usa el portal), pero Microsoft: *"no soportada, úsala bajo tu riesgo"* |
| **Dataverse Web API** | `{org}.api.crm{N}.dynamics.com/api/data/v9.2` | Solo flujos de solución (tabla `workflow`, `category eq 5`) | Sí: POST/PATCH `workflows`, `statecode`, tabla `flowrun` | **Sí** (client `51f81489-…`) | **Soportada y documentada** oficialmente |
| Power Platform API | `api.powerplatform.com` | namespace `powerautomate` | **No** (solo lectura: list flows/runs/actions) | No (exige app propia) | Soportada, GA `2024-10-01` — descartada por ahora |
| BAP API | `api.bap.microsoft.com` | Entornos, `exportPackage` (.zip sin UI) | Solo paquetes | Sí (mismos tokens) | No documentada |

**Conclusión:** la arquitectura correcta usa **dos tokens delegados con UN solo login**
(MSAL `PublicClientApplication` + caché persistente):
- `https://service.flow.microsoft.com//.default` → maker API (descubrimiento/lectura: es la ÚNICA que ve "Mis flujos").
- `https://{org}.crm.dynamics.com/.default` → Dataverse (la ÚNICA vía de escritura soportada).

## Autenticación sin registrar app (client IDs first-party de Microsoft)

| Client ID | Nombre | Sirve para | Evidencia |
|---|---|---|---|
| `1950a258-227b-4e31-a9cf-717495945fc2` | Microsoft Azure PowerShell | flow service, powerapps service, BAP, Dataverse | Es el `ApplicationId` **hard-coded del propio módulo oficial** `Microsoft.PowerApps.Administration.PowerShell` ([AuthModule.psm1](https://www.powershellgallery.com/packages/Microsoft.PowerApps.Administration.PowerShell/2.0.142/Content/Microsoft.PowerApps.AuthModule.psm1)) |
| `51f81489-12ee-4a9e-aaae-a2591f45987d` | Dynamics 365 Example Client App | Dataverse | Microsoft lo documenta como ID "sin necesidad de registrar app" ([authenticate-oauth](https://learn.microsoft.com/power-apps/developer/data-platform/authenticate-oauth)); es el que usa `pac auth` |
| `04b07795-8ddb-461a-bbee-02f9e1bf7b46` | Microsoft Azure CLI | amplio | [apps-to-allow](https://learn.microsoft.com/power-platform/admin/apps-to-allow) |

Patrón MSAL Python (login interactivo una vez, luego tokens silenciosos):

```python
import msal
app = msal.PublicClientApplication(
    client_id="1950a258-227b-4e31-a9cf-717495945fc2",  # configurable, no constante
    authority="https://login.microsoftonline.com/organizations",
    token_cache=cache_persistente)                     # msal-extensions (cifrado DPAPI)
flow = ["https://service.flow.microsoft.com//.default"]
dv   = ["https://{org}.crm.dynamics.com/.default"]
cta = app.get_accounts()
tok  = app.acquire_token_silent(flow, account=cta[0]) if cta else app.acquire_token_interactive(flow)
tokd = app.acquire_token_silent(dv, account=app.get_accounts()[0]) or app.acquire_token_interactive(dv)
```

- **Solo permisos delegados** — la maker API no acepta permisos de aplicación.
- **Riesgo conocido:** los client IDs "prestados" pueden bloquearse por Conditional
  Access o el control de apps cliente (preview). Precedente: la app PnP Management
  Shell fue **eliminada por Microsoft en sep-2024**. Mitigación: `client_id` como
  configuración con fallback a app propia del usuario, nunca constante.

## Maker API — endpoints clave (`api-version=2016-11-01`)

| Operación | Verbo | Ruta |
|---|---|---|
| Listar entornos | GET | `/providers/Microsoft.ProcessSimple/environments` |
| **Listar TODOS mis flujos** | GET | `/environments/{envId}/flows?include=includeSolutionCloudFlows` |
| Leer flujo (con `properties.definition` completa) | GET | `/environments/{envId}/flows/{flowGuid}` |
| Crear flujo | POST | `/environments/{envId}/flows` (body: `properties.displayName/state/definition/connectionReferences`) |
| Modificar flujo | PATCH | `/environments/{envId}/flows/{flowGuid}` |
| Encender / Apagar | POST | `.../flows/{flowGuid}/start` · `.../stop` |
| Historial de corridas | GET | `.../flows/{flowGuid}/runs` |
| Reenviar corrida | POST | `.../triggers/{trigger}/histories/{runId}/resubmit` |
| Exportar paquete .zip sin UI | POST | BAP `/environments/{envId}/exportPackage` |

Nota: el scope admin (`/scopes/admin/`) ve flujos de otros usuarios pero NO acepta
`includeSolutionCloudFlows` y sus listados no traen la definición completa.

## Dataverse Web API — la vía soportada de escritura

Fuente oficial: [Work with cloud flows using code](https://learn.microsoft.com/power-automate/manage-flows-with-code)

- Tabla `workflow` (`/workflows`): `category` 5 = cloud flow; `clientdata` = JSON
  string con `{properties:{connectionReferences, definition}}`; `statecode` 0=Off /
  1=On / 2=Suspendido (DLP).
- Listar: `GET /workflows?$filter=category eq 5&$select=name,clientdata,statecode`.
- Crear: `POST /workflows` con `{"category":5,"name":"...","type":1,"primaryentity":"none","clientdata":"..."}` → nace apagado (`statecode 0`); hay que enlazar connection references antes de activar.
- Modificar: `PATCH /workflows({id})` con `If-Match: *` y `{"clientdata": "..."}`.
- On/Off: `PATCH` con `{"statecode": 1}` / `{"statecode": 0}`.
- Historial: tabla `flowrun` — `GET /flowruns?$filter=_workflow_value eq {id}&$orderby=starttime desc` (TTL ~28 días, eventually consistent, solo flujos de solución).
- Límites: 6.000 req/300 s por usuario, 429 con `Retry-After` → backoff exponencial.

**Limitación oficial:** los flujos de "Mis flujos" (no-solución) NO existen en la
tabla `workflow`. Cierre del hueco:
1. Desde nov-2023, los flujos nuevos en entornos con Dataverse **nacen en solución por defecto** — la población legacy se reduce sola.
2. Migración masiva: `Add-AdminFlowsToSolution` (módulo PowerShell ≥ 2.0.167) o replicar su llamada — acción "moderniza tus flujos" de la herramienta.
3. Mientras tanto, la maker API los lee/edita igual que lo hace el portal.

## Conexiones (para el reporte de salud) — verificado en vivo 2026-07-20

Las conexiones NO viven en el servicio de flujos (probado: `api.flow.microsoft.com/.../connections`
da 404). Viven en PowerApps y requieren su propio token:

- **Endpoint (verificado, HTTP 200):**
  `GET https://api.powerapps.com/providers/Microsoft.PowerApps/connections?api-version=2016-11-01&$filter=environment eq '{envId}'`
- **Token:** scope `https://service.powerapps.com//.default` — se obtiene
  silencioso con el MISMO login (client first-party FOCI), sin re-login.
- **Estado de la conexión:** `properties.statuses[*].status` — array; `Connected`
  = sana; cualquier otro (`Error`) = rota/desconectada/caducada. Un `error.message`
  string distingue la causa (token caducado a 90 días, contraseña cambiada,
  cuenta deshabilitada) pero NO hay campo estructurado fiable para eso.
- **Cruce flujo → conexión (verificado):** la lista de flujos ya trae
  `properties.connectionReferences` inline (0 llamadas extra); la clave de unión
  es `connectionReferences[*].connectionName == connection.name`.
- **Costo:** 2 llamadas por entorno (flujos + conexiones) + cruce en memoria.
- Flujos suspendidos por DLP: `properties.state == "Suspended"` +
  `flowSuspensionReason` (gratis en la lista de flujos).

## Otras piezas evaluadas

- **pac CLI (jul-2026): sigue SIN comandos de flujos.** Solo round-trip por solución (`pac solution export/unpack/pack/import`). Útil para versionar en git, no como vía primaria.
- **Módulos PowerShell PowerApps:** siguen soportados (solo Windows PowerShell 5.1). `Get-AdminFlow`, `Enable-/Disable-AdminFlow`, `Add-AdminFlowsToSolution`. NO crean ni editan definiciones.
- **Licencias:** llamar estas APIs de gestión no exige licencia premium (el conector de gestión es clase Standard). Leer `flowrun` sí consume request limits.
- **DLP:** las APIs no se bloquean por DLP, pero un flujo que viole la política queda **suspendido** (`statecode 2`) — la herramienta debe mostrarlo claro.
- **Deprecación:** sin retiro anunciado de `api.flow.microsoft.com` (sigue "unsupported"). Dirección estratégica de Microsoft: todo hacia Dataverse.

## Arquitectura recomendada (decisión)

1. **Auth:** MSAL público + caché cifrada local; client id configurable (default `1950a258-…`); interactivo con fallback device-code.
2. **Lectura/descubrimiento:** maker API (`environments` → `flows?include=includeSolutionCloudFlows` → GET por flujo → `runs`).
3. **Escritura:** Dataverse si el flujo es de solución (soportado); maker API para legacy, ofreciendo siempre la migración a solución como arreglo permanente.
4. **Resiliencia:** capa de abstracción sobre la maker API (endpoints intercambiables), backoff en 429, versiones fijadas (`2016-11-01` / `v9.2`).
5. **No construir sobre:** Power Platform API (read-only + app propia), pac CLI (sin comandos de flujo), módulos PS maker (sin write).
