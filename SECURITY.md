# Seguridad

## Modelo de seguridad (resumen para TI)

**Local-first.** Todo corre en la máquina del usuario. No existe ningún servidor
del proyecto: no hay telemetría, no hay backend, ningún dato del tenant pasa por
terceros.

| Componente | Qué hace en la red | Credenciales |
|---|---|---|
| `auditar_flujo.py` | **Nada** (100% offline, stdlib) | Ninguna |
| `pa_api.py` | Solo `api.flow.microsoft.com` y `*.dynamics.com` (HTTPS, verificación TLS por defecto) | Login **delegado** del propio usuario vía MSAL (OAuth de Microsoft). Actúa con los permisos que el usuario ya tiene — ni más ni menos |
| `actualizar_catalogo.py` | Solo `api.github.com` (metadatos públicos, sin auth) | Ninguna |

**Tokens.** Se guardan en caché local **cifrada con DPAPI de Windows**
(`msal-extensions`; Keychain en macOS, libsecret en Linux) en
`~/.power-automate-architect/`. Si el cifrado no está disponible, el script lo
AVISA en pantalla. Nunca se imprimen ni se registran. `logout` borra la sesión.
Revocable en cualquier momento desde Entra ID.

**Varias cuentas (multi-tenant).** Puedes iniciar sesión en varias cuentas (ej.
la personal y la de la empresa) y cambiar la activa con `cambiar-cuenta`. Esto
**no abre ningún hueco**:
- MSAL guarda los tokens **separados por cuenta**; cada llamada pide el token de
  la cuenta activa y nunca expone el de otra. "Cambiar de cuenta" solo elige a
  cuál pedirle token, no mezcla ni copia credenciales.
- La caché cifrada es **por usuario de Windows**: dos personas en cuentas de
  Windows distintas no comparten sesiones (no compartas la cuenta de Windows —
  práctica estándar de empresa).
- Al cambiar de cuenta o entrar a una nueva, se **olvida el entorno por defecto**
  cacheado: una escritura no puede terminar en el tenant equivocado por error. Si
  fuerzas un `--entorno` de otro tenant al que la cuenta activa no tiene acceso,
  la API responde 403 (nada silencioso).
- `config.json` guarda solo datos no secretos: id de entorno, client_id, tenant
  y el correo activo. Sin tokens, sin contraseñas.

**Recomendación para entornos corporativos estrictos:** registra tu propia app en
Entra ID y úsala con `--client-id`. Da control de Conditional Access y una
traza de auditoría a nombre de esa app, en vez del client público first-party de
Microsoft que se usa por defecto (ver `references/api-conexion.md`).

**Client ID.** Por defecto usa un client público *first-party de Microsoft*
(`1950a258-…`, el mismo del módulo oficial `Microsoft.PowerApps.Administration.PowerShell`)
— sin registrar apps ni secretos. Las organizaciones pueden exigir su propia app
registrada con `--client-id` (recomendado para despliegues corporativos; permite
Conditional Access y auditoría granular). Detalle: `references/api-conexion.md`.

**Escritura al tenant (defensa en profundidad, en el código — no en el prompt):**
1. Dry-run por defecto: sin `--si` nada se ejecuta.
2. Respaldo automático del flujo antes de cualquier modificación
   (`~/.power-automate-architect/respaldos/` — contiene definiciones de flujos:
   la carpeta es local y queda excluida de git; protégela como cualquier dato
   de negocio).
3. Auditoría previa que **rechaza** definiciones con hallazgos de severidad ALTA.
4. Vía soportada por Microsoft (Dataverse) primero; `If-Match` para evitar
   upserts accidentales; DLP del tenant sigue aplicando (un flujo que viole la
   política queda Suspendido, y el tool lo muestra).

**Prompt injection.** El contenido de los flujos (nombres de acciones, notes,
datos) se trata como **datos, nunca como instrucciones** para el asistente —
regla explícita en `AGENTS.md`. El auditor reporta el *nombre* de la acción con
un posible secreto, nunca el valor del secreto.

**Higiene de código:** sin `shell=True`, sin `eval`/`exec`, sin `verify=False`,
timeouts en todas las llamadas HTTP, subprocess siempre con listas de
argumentos. Verificable con `git grep`.

## Reportar una vulnerabilidad

Abre un *Security Advisory* privado en GitHub (Security → Report a vulnerability)
o un issue marcado como `security` sin detalles explotables. Respuesta objetivo:
7 días.

## Alcance

Este proyecto NO gestiona secretos de conectores ni contraseñas: las conexiones
de Power Automate se enlazan en el portal oficial de Microsoft. Cualquier
hallazgo sobre manejo de tokens, escritura al tenant o inyección vía contenido
de flujos es bienvenido y prioritario.
