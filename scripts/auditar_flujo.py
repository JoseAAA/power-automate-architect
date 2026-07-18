#!/usr/bin/env python3
"""
auditar_flujo.py - Auditor estatico de flujos de Power Automate (cloud flows).

Uso:
  python auditar_flujo.py <ruta>

<ruta> puede ser:
  - un paquete exportado .zip  (export "como paquete .zip" de Power Automate)
  - una carpeta ya descomprimida del paquete
  - un definition.json directo  (o el clientdata de la tabla workflow)

Lee la definicion (Workflow Definition Language, igual que Logic Apps), recorre
triggers y acciones de forma recursiva y aplica un catalogo de reglas basadas en
las guias oficiales de Microsoft Learn (Power Automate coding guidelines /
Well-Architected), el Power CAT Tools Code Review de Microsoft y estandares de
la comunidad (Matthew Devaney, Forward Forever, David Wyatt).

Salida: reporte en consola con puntuacion (0-100), veredicto y hallazgos por
severidad [ALTA]/[MEDIA]/[BAJA]/[INFO], cada uno con su arreglo concreto y la
fuente. Codigo de salida 1 si hay hallazgos de severidad ALTA, 0 si no.

Es 100% determinista: no usa IA ni red. El asistente solo lo ejecuta y explica.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Catalogo de reglas. Cada regla: codigo, severidad, peso, titulo, arreglo, fuente.
# El peso se descuenta de 100 por cada ocurrencia (ALTA 15 / MEDIA 7 / BAJA 3 / INFO 0).
# ---------------------------------------------------------------------------
LEARN = "https://learn.microsoft.com/power-automate/guidance/coding-guidelines"
WAF = "https://learn.microsoft.com/power-platform/well-architected"
LIMITS = "https://learn.microsoft.com/power-automate/limits-and-config"
POWERCAT = "https://github.com/microsoft/Power-CAT-Tools/blob/main/CODE_REVIEW.md"

REGLAS = {
    # ---- Confiabilidad -----------------------------------------------------
    "PA-ERR-01": ("ALTA", 15, "No hay manejo de errores (Try/Catch)",
        "Envuelve la logica principal en un Scope llamado 'Try' y agrega un Scope "
        "'Catch' con 'Configurar ejecucion despues' = solo cuando 'Try' falle "
        "(has failed / has timed out). En el Catch notifica o registra el error.",
        f"{LEARN}/error-handling"),
    "PA-ERR-02": ("BAJA", 3, "Accion de conector sin politica de reintentos exponencial",
        "En Configuracion de la accion, pon Tipo de reintento = Exponencial. "
        "Ayuda a sobrevivir fallos transitorios de red/servicio.",
        f"{WAF}/reliability/handle-transient-faults"),
    "PA-ERR-03": ("MEDIA", 7, "El Catch no termina la corrida como fallida (o Terminate mal ubicado)",
        "Al final del Scope 'Catch' agrega una accion 'Terminar' con estado = Error "
        "(Failed) y un mensaje: si no, la corrida fallida queda registrada como "
        "exitosa y nadie se entera. Nunca pongas 'Terminar' dentro de un bucle.",
        f"{LEARN}/error-handling"),
    # ---- Seguridad ----------------------------------------------------------
    "PA-SEC-01": ("ALTA", 15, "Posible secreto/credencial escrito directamente en el flujo",
        "No escribas contrasenas, API keys ni tokens en el flujo. Guardalos en una "
        "Environment Variable (referenciando Azure Key Vault) y activa Entradas/Salidas "
        "seguras en la accion.",
        f"{LEARN}/use-secure-inputs-outputs-triggers"),
    "PA-SEC-02": ("MEDIA", 7, "Conexion embebida en vez de Connection Reference",
        "Usa Connection References (no conexiones embebidas). Permiten mover el flujo "
        "entre entornos (dev/test/prod) sin reconfigurar y son requisito de un buen ALM.",
        "https://learn.microsoft.com/power-apps/maker/data-platform/create-connection-reference"),
    "PA-SEC-03": ("ALTA", 15, "Accion con datos sensibles sin Entradas/Salidas seguras",
        "La accion maneja encabezados de autorizacion, claves o contrasenas pero no "
        "tiene activado 'Entradas seguras'/'Salidas seguras' (Configuracion de la "
        "accion). Sin eso, los valores quedan visibles en el historial de ejecucion.",
        f"{LEARN}/use-secure-inputs-outputs-triggers"),
    "PA-SEC-04": ("MEDIA", 7, "Trigger HTTP 'Cuando se recibe una solicitud' sin restriccion clara",
        "Verifica la autenticacion del trigger HTTP: exige OAuth de Entra ID o al menos "
        "restringe 'Quien puede desencadenar el flujo'. Una URL con SAS filtrada "
        "permite a cualquiera disparar el flujo.",
        f"{LEARN}/use-secure-inputs-outputs-triggers"),
    # ---- Pruebas / artefactos ----------------------------------------------
    "PA-TEST-01": ("ALTA", 15, "Resultados estaticos (mock de pruebas) habilitados",
        "La accion tiene 'Static result' activado: no ejecuta de verdad, devuelve un "
        "resultado simulado. Es un artefacto de pruebas; desactivalo antes de usar el "
        "flujo en serio (Configuracion de la accion > Static result).",
        f"{LEARN}/test-cloud-flows"),
    # ---- Rendimiento y eficiencia -------------------------------------------
    "PA-PERF-01": ("MEDIA", 7, "Se llena una variable de tipo array con 'Anexar' dentro de un bucle",
        "Reemplaza el patron 'Apply to each' + 'Anexar a variable' por una sola accion "
        "'Seleccionar' (Select): transforma todo el array de una vez, mas rapido y sin variable.",
        f"{LEARN}/use-data-operations"),
    "PA-PERF-02": ("MEDIA", 7, "Bucles 'Apply to each' anidados",
        "Evita bucles dentro de bucles. Trae los datos ya relacionados desde el origen "
        "(OData $expand) o usa 'Filtrar matriz'/'Seleccionar' en vez de un bucle interno.",
        f"{LEARN}/avoid-anti-patterns"),
    "PA-PERF-03": ("MEDIA", 7, "Crear/Actualizar registros uno por uno dentro de un bucle",
        "Para muchos registros usa operaciones por lote (batch / CreateMultiple en "
        "Dataverse) en vez de crear/actualizar dentro de un 'Apply to each'.",
        f"{LEARN}/avoid-anti-patterns"),
    "PA-PERF-04": ("BAJA", 3, "Muchas variables individuales",
        "Si tienes muchas variables, considera una sola variable de tipo objeto (JSON) "
        "o usar acciones 'Redactar' (Compose) para valores que no cambian. Menos acciones.",
        f"{LEARN}/use-data-operations"),
    "PA-PERF-05": ("MEDIA", 7, "Se traen todas las filas y se filtran despues",
        "Filtra en el origen: usa 'Filter Query' (OData $filter) y 'Select Query' para "
        "traer solo las columnas/filas necesarias. Reduce datos, tiempo y consumo de API.",
        f"{LEARN}/use-data-operations"),
    "PA-PERF-06": ("MEDIA", 7, "Bloques de acciones repetidos casi identicos",
        "Detectamos varias lecturas/acciones casi iguales. Consolidalas en un solo bucle "
        "parametrizado o en un flujo hijo reutilizable; evita copiar-pegar logica.",
        f"{LEARN}/avoid-anti-patterns"),
    "PA-PERF-07": ("BAJA", 3, "Una 'Condition' dentro de un bucle podria filtrarse antes",
        "Si dentro del bucle solo actuas cuando se cumple una condicion, usa 'Filtrar "
        "matriz' (Filter array) ANTES del bucle para iterar solo lo necesario.",
        f"{LEARN}/use-data-operations"),
    "PA-PERF-08": ("MEDIA", 7, "Accion de listado sin paginacion ni tope de filas",
        "La accion lista filas sin 'Paginacion' activada ni tope ($top / Top Count): "
        "solo traera la primera pagina (a menudo 100 filas) y el resto se pierde EN "
        "SILENCIO. Activa Paginacion (Configuracion) o define un tope explicito.",
        f"{LEARN}/work-with-relevant-data"),
    "PA-PERF-09": ("MEDIA", 7, "Accion de espera larga (aprobacion/webhook) sin timeout",
        "Las acciones que esperan (aprobaciones, webhooks) corren hasta 30 dias y el "
        "flujo muere sin avisar. En Configuracion de la accion define 'Tiempo de espera' "
        "(ej. P7D) y maneja el timeout con un camino alterno (recordatorio/escalamiento).",
        f"{LEARN}/asychronous-flow-pattern"),
    "PA-PERF-10": ("MEDIA", 7, "'Do until' sin limites sanos",
        "Define 'Count' y 'Timeout' razonables en el Do until (Cambiar limites). Sin "
        "limites o con valores enormes, un bug se convierte en un bucle de horas que "
        "consume tu cuota de acciones.",
        LIMITS),
    "PA-PERF-11": ("BAJA", 3, "'Delay' (retraso) dentro de un bucle",
        "Un Delay dentro de un bucle multiplica la duracion de la corrida y arriesga el "
        "limite de 30 dias. Saca la espera del bucle o replantea el patron (ej. "
        "programar el flujo, o usar concurrencia con lotes).",
        LIMITS),
    "PA-PERF-12": ("BAJA", 3, "El bucle itera la salida del trigger: oportunidad de 'Split On'",
        "Si el trigger devuelve una lista y lo primero que haces es recorrerla, activa "
        "'Split On' en el trigger: Power Automate crea una corrida por elemento y el "
        "flujo queda mas simple y paralelo.",
        LIMITS),
    # ---- Concurrencia -------------------------------------------------------
    "PA-CONC-01": ("ALTA", 15, "Bucle en paralelo que escribe variables (condicion de carrera)",
        "El 'Apply to each' tiene concurrencia > 1 y dentro se escriben variables "
        "(Set/Append/Increment): las iteraciones se pisan entre si y el resultado es "
        "impredecible. Quita la concurrencia o reemplaza la variable por 'Seleccionar'.",
        POWERCAT),
    # ---- IA y agent flows ----------------------------------------------------
    "PA-IA-01": ("MEDIA", 7, "Salida de IA sin validacion ni humano en el circuito",
        "La IA es probabilistica: la misma entrada puede dar salidas distintas o "
        "inventadas. Pide al prompt salida JSON, valida con 'Parse JSON' + condiciones, "
        "y para decisiones con impacto inserta una aprobacion humana antes de actuar.",
        "https://learn.microsoft.com/ai-builder/azure-openai-human-review"),
    "PA-IA-02": ("ALTA", 15, "Accion de IA dentro de un bucle (quema creditos)",
        "Cada iteracion consume creditos (Copilot/AI Builder); al agotarse la cuota, "
        "TODAS las acciones de IA del entorno fallan (QuotaExceeded). Filtra antes del "
        "bucle, procesa por lotes o resuelvelo con una sola llamada al prompt.",
        "https://learn.microsoft.com/ai-builder/administer-licensing"),
    "PA-IA-03": ("INFO", 0, "Usa acciones de IA (consumo de creditos)",
        "Las acciones de IA se cobran por uso (prompt basico 0.1 creditos/1K tokens; "
        "factura 8/pagina; etc.). Ojo: en nov-2026 desaparecen los creditos incluidos "
        "en las licencias; presupuesta Copilot Credits. No es un error.",
        "https://learn.microsoft.com/ai-builder/endofaibcredits"),
    "PA-AGT-01": ("ALTA", 15, "Flujo de agente mal formado (el agente fallara al llamarlo)",
        "El trigger 'When an agent calls the flow' exige una accion 'Respond to the "
        "agent' con respuesta asincrona APAGADA, respondiendo en <100 s, y con las "
        "MISMAS salidas en todas las ramas. Si no, el agente recibe error 3000/timeout.",
        "https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent"),
    "PA-AGT-02": ("MEDIA", 7, "Trigger de agente con parametros sin describir",
        "El orquestador del agente decide como usar tu flujo leyendo los nombres y "
        "descripciones de los parametros: 'text_1' no le dice nada. Renombra cada "
        "parametro con un nombre significativo y describe que espera.",
        "https://learn.microsoft.com/microsoft-copilot-studio/flow-agent"),
    # ---- Fechas y zonas horarias --------------------------------------------
    "PA-DATE-01": ("MEDIA", 7, "Zona horaria manejada a mano con addHours()",
        "No restes horas a mano (ej. addHours(utcNow(),-5)). Usa la accion 'Convertir "
        "zona horaria' o convertFromUtc(); maneja el horario de verano automaticamente.",
        "https://learn.microsoft.com/power-automate/convert-time-zone"),
    # ---- Triggers ------------------------------------------------------------
    "PA-TRG-01": ("BAJA", 3, "Trigger automatico sin condiciones de activacion",
        "Agrega 'Condiciones de desencadenador' para que el flujo se ejecute solo cuando "
        "haga falta. Ahorra ejecuciones y evita bucles infinitos.",
        f"{LEARN}/optimize-power-automate-triggers"),
    "PA-TRG-02": ("BAJA", 3, "Concurrencia configurada en el trigger (ajuste irreversible)",
        "El trigger tiene control de concurrencia activado. Ojo: una vez activado NO se "
        "puede volver al comportamiento por defecto; ademas puede reordenar corridas. "
        "Verifica que sea intencional y documentalo en una Note.",
        f"{LEARN}/optimize-power-automate-triggers"),
    "PA-TRG-03": ("ALTA", 15, "Riesgo de bucle infinito: el flujo escribe en la misma tabla que lo dispara",
        "El trigger reacciona a cambios en una tabla/lista y el propio flujo escribe en "
        "ella: cada corrida vuelve a disparar el flujo (bucle infinito que consume tu "
        "cuota). Agrega 'Condiciones de desencadenador' que excluyan los cambios hechos "
        "por el flujo, o filtra por columnas (Filter columns / filteringattributes).",
        f"{LEARN}/avoid-anti-patterns"),
    "PA-TRG-04": ("MEDIA", 7, "Trigger de Dataverse sin filtro de columnas",
        "El trigger reacciona a modificaciones sin 'Seleccionar columnas' "
        "(filteringattributes): se dispara con CUALQUIER cambio de la fila, aunque no "
        "te interese. Filtra por las columnas relevantes; ahorra corridas y evita bucles.",
        f"{LEARN}/optimize-power-automate-triggers"),
    # ---- Variables -----------------------------------------------------------
    "PA-VAR-01": ("BAJA", 3, "Variable inicializada que nunca se usa",
        "La variable se inicializa pero nunca se lee ni se escribe despues: eliminala. "
        "Cada accion innecesaria suma tiempo y ruido al flujo.",
        POWERCAT),
    "PA-VAR-02": ("BAJA", 3, "Variable que nunca cambia: usa 'Redactar' (Compose)",
        "La variable se lee pero nunca se vuelve a asignar: es una constante. Una accion "
        "'Redactar' (Compose) es mas barata y deja claro que el valor no cambia.",
        f"{LEARN}/use-data-operations"),
    # ---- Tamano y organizacion ----------------------------------------------
    "PA-SIZE-01": ("BAJA", 3, "Flujo muy grande (mas de 50 acciones)",
        "Divide el flujo en flujos hijos reutilizables (padre e hijos en la misma "
        "solucion). Un flujo gigante es dificil de entender, probar y mantener.",
        f"{LEARN}/create-reusable-code"),
    "PA-SIZE-02": ("BAJA", 3, "Flujo largo sin Scopes que lo organicen",
        "Con mas de ~10 acciones, agrupa pasos relacionados en Scopes con nombre "
        "('Preparar datos', 'Notificar'...). El flujo se lee como capitulos y el manejo "
        "de errores se vuelve natural.",
        f"{LEARN}/create-scopes"),
    # ---- Configuracion portable ----------------------------------------------
    "PA-CFG-01": ("BAJA", 3, "Valores de entorno escritos a mano (URLs de sitio, correos, GUIDs)",
        "Hay URLs de sitio, correos o IDs escritos como texto fijo. Usa Environment "
        "Variables para poder mover el flujo entre entornos (dev/test/prod) y cambiar "
        "destinos sin editar el flujo.",
        f"{LEARN}/keep-flow-configuration-generic"),
    # ---- Legibilidad y mantenimiento ------------------------------------------
    "PA-NAME-01": ("BAJA", 3, "Acciones con nombre generico (sin renombrar)",
        "Renombra las acciones con un nombre descriptivo (ej. 'Compose' -> "
        "'Redactar mensaje de alerta'). Facilita leer y mantener el flujo.",
        f"{LEARN}/use-consistent-naming-conventions"),
    "PA-DOC-01": ("BAJA", 3, "El flujo no tiene comentarios (Notes)",
        "Agrega Notes a las acciones clave (boton derecho > Agregar una nota). Son los "
        "comentarios del flujo: explican el 'por que' a quien lo mantenga.",
        f"{LEARN}/use-peekcode-addnotes"),
    "PA-DOC-02": ("BAJA", 3, "El flujo no tiene descripcion",
        "Agrega una descripcion al flujo (Detalles > Editar): que hace, cada cuanto y "
        "quien es el dueno. Ademas, Copilot y los agentes la usan para entender el "
        "flujo como herramienta.",
        POWERCAT),
    # ---- Informativas (peso 0) -------------------------------------------------
    "PA-LIC-01": ("INFO", 0, "Usa conectores/acciones premium (nota de licencia)",
        "El flujo usa conectores premium (HTTP, Dataverse, SQL...): requiere licencia "
        "Premium por usuario o de proceso al guardarlo/ejecutarlo. Solo para que lo "
        "tengas presente; no es un error.",
        "https://learn.microsoft.com/power-platform/admin/power-automate-licensing/types"),
}

ORDEN_SEV = {"ALTA": 0, "MEDIA": 1, "BAJA": 2, "INFO": 3}
PESO_SEV = {"ALTA": 15, "MEDIA": 7, "BAJA": 3, "INFO": 0}

# Nombres por defecto que Power Automate asigna (senal de "sin renombrar").
DEFAULTS = (
    "Compose", "Condition", "Scope", "Switch", "Terminate",
    "Apply_to_each", "Initialize_variable", "Set_variable", "Increment_variable",
    "Append_to_array_variable", "Append_to_string_variable", "Filter_array",
    "Select", "Parse_JSON", "HTTP", "Get_items", "Get_item", "Send_an_email",
    "Create_item", "Update_item", "Get_response_details", "Get_rows",
    "Do_until", "Delay", "Delay_until", "List_rows", "Add_a_new_row",
    "Update_a_row", "Get_a_row_by_ID", "Send_an_email_(V2)",
    "Start_and_wait_for_an_approval", "Respond_to_a_PowerApp_or_flow",
    "Post_message_in_a_chat_or_channel",
)
DEFAULT_RE = re.compile(r"^(" + "|".join(re.escape(d) for d in DEFAULTS) + r")(_\d+)?$")

SECRET_RE = re.compile(
    r"(?i)(\"?(password|pwd|client[_-]?secret|api[_-]?key|apikey|secret|access[_-]?token)\"?\s*[:=]\s*\"[^\"]{4,}\")"
    r"|(bearer\s+[A-Za-z0-9._\-]{20,})"
    r"|(eyJ[A-Za-z0-9._\-]{20,})"  # JWT
)

# Pistas de que una accion maneja material sensible (para PA-SEC-03).
SENSIBLE_RE = re.compile(
    r"(?i)(\"authorization\"|x-api-key|api[_-]?key|apikey|password|pwd|client[_-]?secret|getsecret)"
)

# Senales de configuracion hardcodeada (PA-CFG-01).
URL_SITIO_RE = re.compile(r"https://[a-z0-9\-]+\.sharepoint\.com", re.I)
CORREO_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
GUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")

# Tipos de accion que escriben variables (para PA-CONC-01 / PA-VAR-xx).
VAR_ESCRITURA = ("setvariable", "appendtoarrayvariable", "appendtostringvariable",
                 "incrementvariable", "decrementvariable")

# operationId que leen listas / escriben registros.
OPS_LISTADO = ("getitems", "listrows", "getrows", "getentities")
OPS_ESCRITURA = ("create", "insert", "update", "patch", "postitem", "additem", "upsert")

# apiId que implican conector premium (lista corta y segura, ampliable).
APIS_PREMIUM = ("commondataservice", "dataverse", "sqlserver", "servicebus",
                "azurequeues", "azureblob", "keyvault", "azuread", "desktopflow")

# Acciones de IA (Run a prompt / AI Builder / Predict) viajan por el conector de
# Dataverse con operationId (aibuilder)predict. Ver references/ia-en-flujos.md.
IA_OP_RE = re.compile(r"(?i)^(aibuilder)?predict$")

# Nombres genericos de parametros del trigger de agente (no le dicen nada al orquestador).
PARAM_GENERICO_RE = re.compile(r"(?i)^(input|text|number|boolean|file|date|item)_?\d*$")


# ---------------------------------------------------------------------------
# Carga de la definicion desde zip / carpeta / json
# ---------------------------------------------------------------------------
def _texto_definitions(raiz: Path):
    """Devuelve lista de (nombre, texto_json) de posibles definiciones de flujo."""
    out = []
    if raiz.is_file() and raiz.suffix.lower() == ".zip":
        with zipfile.ZipFile(raiz) as z:
            for n in z.namelist():
                if n.endswith("definition.json"):
                    out.append((n, z.read(n).decode("utf-8", "replace")))
    elif raiz.is_dir():
        for f in raiz.rglob("definition.json"):
            out.append((str(f), f.read_text(encoding="utf-8", errors="replace")))
        # tambien .json sueltos por si exportaron asi
        if not out:
            for f in raiz.rglob("*.json"):
                out.append((str(f), f.read_text(encoding="utf-8", errors="replace")))
    elif raiz.is_file():
        out.append((str(raiz), raiz.read_text(encoding="utf-8", errors="replace")))
    return out


def _extraer_definicion(obj):
    """Normaliza distintos formatos al nodo {triggers, actions} + connectionReferences."""
    # clientdata puede venir como string JSON
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return None, None
    if not isinstance(obj, dict):
        return None, None
    props = obj.get("properties", obj)
    if isinstance(props.get("clientdata"), str):
        try:
            props = json.loads(props["clientdata"]).get("properties", props)
        except Exception:
            pass
    defn = props.get("definition", obj.get("definition"))
    if defn is None and "actions" in obj and "triggers" in obj:
        defn = obj
    connrefs = props.get("connectionReferences") or (defn or {}).get("connectionReferences") or {}
    return defn, connrefs


def cargar_flujo(ruta: Path):
    """Devuelve (nombre, definicion, connectionReferences, descripcion) del flujo principal."""
    candidatos = _texto_definitions(ruta)
    mejor = None
    for nombre, texto in candidatos:
        try:
            obj = json.loads(texto)
        except Exception:
            continue
        defn, connrefs = _extraer_definicion(obj)
        if defn and isinstance(defn.get("actions"), dict):
            props = obj.get("properties", {}) if isinstance(obj.get("properties"), dict) else {}
            display = props.get("displayName") or obj.get("displayName") or Path(nombre).stem
            desc = props.get("description") or obj.get("description") or ""
            score = len(defn.get("actions", {}))
            if mejor is None or score > mejor[4]:
                mejor = (display, defn, connrefs, desc, score)
    if mejor is None:
        return None, None, None, None
    return mejor[0], mejor[1], mejor[2], mejor[3]


# ---------------------------------------------------------------------------
# Recorrido recursivo de acciones
# ---------------------------------------------------------------------------
def caminar(acciones, profundidad=0, dentro_foreach=0, dentro_bucle=0):
    """Genera (nombre, accion, profundidad, foreach_arriba, bucles_arriba).

    foreach_arriba cuenta solo 'Apply to each'; bucles_arriba cuenta ademas 'Do until'.
    """
    if not isinstance(acciones, dict):
        return
    for nombre, acc in acciones.items():
        if not isinstance(acc, dict):
            continue
        yield nombre, acc, profundidad, dentro_foreach, dentro_bucle
        tipo = acc.get("type", "").lower()
        es_foreach = tipo == "foreach"
        es_bucle = tipo in ("foreach", "until")
        sub_fe = dentro_foreach + (1 if es_foreach else 0)
        sub_lp = dentro_bucle + (1 if es_bucle else 0)
        # subacciones en distintos contenedores
        if isinstance(acc.get("actions"), dict):
            yield from caminar(acc["actions"], profundidad + 1, sub_fe, sub_lp)
        if isinstance(acc.get("else"), dict) and isinstance(acc["else"].get("actions"), dict):
            yield from caminar(acc["else"]["actions"], profundidad + 1, sub_fe, sub_lp)
        if isinstance(acc.get("cases"), dict):
            for caso in acc["cases"].values():
                if isinstance(caso, dict) and isinstance(caso.get("actions"), dict):
                    yield from caminar(caso["actions"], profundidad + 1, sub_fe, sub_lp)
        if isinstance(acc.get("default"), dict) and isinstance(acc["default"].get("actions"), dict):
            yield from caminar(acc["default"]["actions"], profundidad + 1, sub_fe, sub_lp)


def _tipo(acc):
    return (acc.get("type") or "").lower()


def _ins(acc):
    """inputs de la accion como dict (los Compose pueden traer un string)."""
    ins = acc.get("inputs")
    return ins if isinstance(ins, dict) else {}


def _host(acc):
    h = _ins(acc).get("host")
    return h if isinstance(h, dict) else {}


def _op(acc):
    return _host(acc).get("operationId", "") or ""


def _api_id(acc):
    return str(_host(acc).get("apiId", "") or "").lower()


def _params(acc):
    p = _ins(acc).get("parameters")
    return p if isinstance(p, dict) else {}


def _rc(acc):
    return acc.get("runtimeConfiguration") or {}


def _inputs_sin_host(acc):
    """JSON de los inputs sin el nodo host (apiId/conexion), para buscar literales."""
    ins = acc.get("inputs")
    if isinstance(ins, dict):
        ins = {k: v for k, v in ins.items() if k != "host"}
    return json.dumps(ins if ins is not None else "", ensure_ascii=False)


def _fuente_norm(params):
    """Normaliza parametros de origen a categorias {tabla, fuente} para compararlos."""
    out = {}
    for k, v in (params or {}).items():
        kl, vl = str(k).lower(), str(v).strip().lower()
        if not vl or vl.startswith("@"):
            continue  # expresiones dinamicas no son comparables
        if any(s in kl for s in ("entityname", "table", "list")):
            out["tabla"] = vl
        elif any(s in kl for s in ("dataset", "site")):
            out["fuente"] = vl
    return out


def _clases_trigger(trigger):
    """Que tipo de cambio dispara el trigger: {'create'}, {'update'} o ambos."""
    op = _op(trigger).lower()
    clases = set()
    if "updat" in op:
        clases.add("update")
    if "new" in op or "creat" in op:
        clases.add("create")
    if "subscribe" in op:  # Dataverse: el tipo de cambio va en el parametro message
        msg = ""
        for k, v in _params(trigger).items():
            if "message" in str(k).lower():
                msg = str(v)
        clases |= {"1": {"create"}, "2": set(), "3": {"update"},
                   "4": {"create", "update"}, "5": {"create", "update"}}.get(
                       msg, {"create", "update"})
    return clases


def _es_accion_ia(acc):
    return (_tipo(acc) == "openapiconnection"
            and "commondataservice" in _api_id(acc)
            and bool(IA_OP_RE.match(_op(acc))))


def _clase_escritura(op):
    op = op.lower()
    if any(s in op for s in ("update", "patch", "upsert")):
        return "update"
    if any(s in op for s in ("create", "insert", "additem", "postitem")):
        return "create"
    return ""


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------
def auditar(defn, connrefs, descripcion=""):
    triggers = defn.get("triggers", {}) or {}
    acciones = defn.get("actions", {}) or {}
    todas = list(caminar(acciones))
    texto_completo = json.dumps(defn, ensure_ascii=False)

    hallazgos = []  # (codigo, detalle_extra)

    def add(codigo, extra=""):
        hallazgos.append((codigo, extra))

    # ---- PA-ERR-01: manejo de errores (Try/Catch via Scope + runAfter Failed)
    hay_scope = any(_tipo(a) == "scope" for _, a, _, _, _ in todas)
    hay_catch = False
    for _, a, _, _, _ in todas:
        ra = a.get("runAfter", {}) or {}
        for estados in ra.values():
            if isinstance(estados, list) and ("Failed" in estados or "TimedOut" in estados):
                hay_catch = True
    if not (hay_scope and hay_catch):
        add("PA-ERR-01")

    # ---- PA-ERR-02: conectores sin retry exponencial (informativo)
    sin_retry = []
    for nombre, a, _, _, _ in todas:
        if _tipo(a) == "openapiconnection":
            tipo_retry = ""
            if isinstance(_ins(a).get("retryPolicy"), dict):
                tipo_retry = _ins(a)["retryPolicy"].get("type", "")
            if tipo_retry in ("", "none", "fixed"):
                sin_retry.append(nombre)
    # Solo lo marcamos si ninguna accion de conector tiene exponencial (evita ruido)
    conectores = [n for n, a, _, _, _ in todas if _tipo(a) == "openapiconnection"]
    if conectores and len(sin_retry) == len(conectores):
        add("PA-ERR-02", f"{len(conectores)} accion(es) de conector")

    # ---- PA-ERR-03: Catch sin Terminate(Failed) / Terminate dentro de bucle
    if hay_catch:
        hay_term_fail = any(
            _tipo(a) == "terminate" and lp == 0 and
            str(_ins(a).get("runStatus", "")).lower() == "failed"
            for _, a, _, _, lp in todas)
        if not hay_term_fail:
            add("PA-ERR-03", "el Catch no hace Terminate(Failed); la corrida fallida figura como exitosa")
    for n, a, _, _, lp in todas:
        if _tipo(a) == "terminate" and lp > 0:
            add("PA-ERR-03", f"Terminate dentro de bucle ('{n}')")

    # ---- PA-SEC-01: secretos hardcodeados
    for nombre, a, _, _, _ in todas:
        ins = json.dumps(a.get("inputs", {}), ensure_ascii=False)
        if SECRET_RE.search(ins):
            add("PA-SEC-01", f"accion '{nombre}'")

    # ---- PA-SEC-02: conexiones embebidas
    embebidas = [k for k, v in (connrefs or {}).items()
                 if isinstance(v, dict) and str(v.get("source", "")).lower() == "embedded"]
    if embebidas:
        add("PA-SEC-02", f"{len(embebidas)} conexion(es): {', '.join(embebidas)}")

    # ---- PA-SEC-03: material sensible sin secure inputs/outputs
    for nombre, a, _, _, _ in todas:
        ins = json.dumps(a.get("inputs", {}), ensure_ascii=False)
        if SENSIBLE_RE.search(ins) or "getsecret" in _op(a).lower():
            sd = (_rc(a).get("secureData") or {}).get("properties") or []
            if not sd:
                add("PA-SEC-03", f"accion '{nombre}'")

    # ---- PA-SEC-04: trigger HTTP Request sin restriccion verificable
    for tn, t in triggers.items():
        if _tipo(t) == "request" and str(t.get("kind", "")).lower() == "http":
            add("PA-SEC-04", f"trigger '{tn}'")

    # ---- PA-TEST-01: static results habilitados
    for nombre, a, _, _, _ in todas:
        sr = _rc(a).get("staticResult") or {}
        if str(sr.get("staticResultOptions", "")).lower() == "enabled":
            add("PA-TEST-01", f"accion '{nombre}'")

    # ---- PA-PERF-01: Append a array dentro de Foreach
    append_loop = [n for n, a, _, fe, _ in todas
                   if _tipo(a) == "appendtoarrayvariable" and fe > 0]
    if append_loop:
        add("PA-PERF-01", f"{len(append_loop)} caso(s)")

    # ---- PA-PERF-02: Foreach anidados
    foreach_anidados = [n for n, a, _, fe, _ in todas
                        if _tipo(a) == "foreach" and fe > 0]
    if foreach_anidados:
        add("PA-PERF-02", f"{len(foreach_anidados)} bucle(s) anidado(s)")

    # ---- PA-PERF-03: Create/Update dentro de Foreach
    cud = []
    for n, a, _, fe, _ in todas:
        if fe > 0 and _tipo(a) == "openapiconnection":
            op = _op(a).lower()
            if any(k in op for k in OPS_ESCRITURA):
                cud.append(n)
    if cud:
        add("PA-PERF-03", f"{len(cud)} operacion(es) de escritura en bucle")

    # ---- PA-PERF-04: muchas variables
    inits = [n for n, a, _, _, _ in todas if _tipo(a) == "initializevariable"]
    if len(inits) >= 5:
        add("PA-PERF-04", f"{len(inits)} variables inicializadas")

    # ---- PA-PERF-05: listar sin $filter
    listas_sin_filtro = []
    for n, a, _, _, _ in todas:
        op = _op(a).lower()
        if any(k in op for k in OPS_LISTADO):
            tiene_filtro = any("filter" in str(k).lower() for k in _params(a).keys())
            if not tiene_filtro:
                listas_sin_filtro.append(n)
    if listas_sin_filtro:
        add("PA-PERF-05", f"{len(listas_sin_filtro)} lectura(s) sin filtro de origen")

    # ---- PA-PERF-06: bloques repetidos (mismas operaciones de lectura sobre misma fuente)
    firmas = {}
    for n, a, _, _, _ in todas:
        if _tipo(a) == "openapiconnection":
            op = _op(a).lower()
            if any(k in op for k in ("getitems", "listrows", "getrows")):
                params = _params(a)
                fuente = str(params.get("source", "")) + "|" + str(params.get("file", "") or params.get("drive", ""))
                firmas[fuente] = firmas.get(fuente, 0) + 1
    repetidos = max(firmas.values()) if firmas else 0
    if repetidos >= 3:
        add("PA-PERF-06", f"{repetidos} lecturas casi identicas sobre la misma fuente")

    # ---- PA-PERF-07: Condition dentro de Foreach
    cond_en_loop = [n for n, a, _, fe, _ in todas if _tipo(a) == "if" and fe > 0]
    if cond_en_loop:
        add("PA-PERF-07", f"{len(cond_en_loop)} condicion(es) dentro de bucle")

    # ---- PA-PERF-08: listado sin paginacion ni tope
    sin_pag = []
    for n, a, _, _, _ in todas:
        op = _op(a).lower()
        if any(k in op for k in OPS_LISTADO):
            tiene_top = any("top" in str(k).lower() or "count" in str(k).lower()
                            for k in _params(a).keys())
            pag = (_rc(a).get("paginationPolicy") or {}).get("minimumItemCount")
            if not tiene_top and not pag:
                sin_pag.append(n)
    if sin_pag:
        add("PA-PERF-08", f"{len(sin_pag)} listado(s): {', '.join(sin_pag[:4])}")

    # ---- PA-PERF-09: accion webhook/espera sin timeout
    for n, a, _, _, _ in todas:
        if _tipo(a).endswith("connectionwebhook"):
            if not (a.get("limit") or {}).get("timeout"):
                add("PA-PERF-09", f"accion '{n}'")

    # ---- PA-PERF-10: Do until sin limites sanos
    for n, a, _, _, _ in todas:
        if _tipo(a) == "until":
            lim = a.get("limit") or {}
            cnt = lim.get("count")
            if not cnt or not lim.get("timeout"):
                add("PA-PERF-10", f"'{n}' sin count/timeout definidos")
            else:
                try:
                    if int(cnt) > 5000:
                        add("PA-PERF-10", f"'{n}' con count={cnt} (enorme)")
                except (TypeError, ValueError):
                    pass

    # ---- PA-PERF-11: Delay dentro de bucle
    for n, a, _, _, lp in todas:
        if _tipo(a) == "wait" and lp > 0:
            add("PA-PERF-11", f"accion '{n}'")

    # ---- PA-PERF-12: foreach sobre la salida del trigger sin Split On
    if not any(t.get("splitOn") for t in triggers.values() if isinstance(t, dict)):
        for n, a, _, _, _ in todas:
            if _tipo(a) == "foreach" and re.search(r"trigger(Body|Outputs)\(\)",
                                                   str(a.get("foreach", ""))):
                add("PA-PERF-12", f"bucle '{n}'")

    # ---- PA-CONC-01: foreach en paralelo que escribe variables
    for n, a, _, _, _ in todas:
        if _tipo(a) != "foreach":
            continue
        rep = ((_rc(a).get("concurrency") or {}).get("repetitions"))
        try:
            rep = int(rep)
        except (TypeError, ValueError):
            continue
        if rep <= 1:
            continue
        escritores = [nn for nn, aa, _, _, _ in caminar(a.get("actions") or {})
                      if _tipo(aa) in VAR_ESCRITURA]
        if escritores:
            add("PA-CONC-01", f"bucle '{n}' (paralelo x{rep}) escribe: {', '.join(escritores[:3])}")

    # ---- PA-IA-01/02/03: acciones de IA (Run a prompt / AI Builder)
    ia_acciones = [(n, lp) for n, a, _, _, lp in todas if _es_accion_ia(a)]
    if ia_acciones:
        en_bucle = [n for n, lp in ia_acciones if lp > 0]
        if en_bucle:
            add("PA-IA-02", f"{len(en_bucle)} accion(es) de IA en bucle: {', '.join(en_bucle[:3])}")
        hay_validacion = any(
            _tipo(a) in ("if", "parsejson") or _tipo(a).endswith("connectionwebhook")
            for _, a, _, _, _ in todas)
        if not hay_validacion:
            add("PA-IA-01", ", ".join(n for n, _ in ia_acciones[:3]))
        add("PA-IA-03", f"{len(ia_acciones)} accion(es) de IA")

    # ---- PA-AGT-01/02: agent flows (trigger 'When an agent calls the flow')
    triggers_agente = [tn for tn, t in triggers.items()
                       if _tipo(t) == "request" and str(t.get("kind", "")).lower() == "skills"]
    if triggers_agente:
        respuestas = [a for _, a, _, _, _ in todas if _tipo(a) == "response"]
        if not respuestas:
            add("PA-AGT-01", "no hay accion 'Respond to the agent'")
        elif len(respuestas) > 1:
            firmas_resp = {json.dumps(_ins(a).get("schema") or _ins(a).get("body") or {},
                                      sort_keys=True) for a in respuestas}
            if len(firmas_resp) > 1:
                add("PA-AGT-01", "las respuestas de cada rama tienen salidas distintas")
        for tn in triggers_agente:
            props = ((_ins(triggers[tn]).get("schema") or {}).get("properties") or {})
            genericos_ag = [k for k in props if PARAM_GENERICO_RE.match(k)]
            if genericos_ag:
                add("PA-AGT-02", f"trigger '{tn}': {', '.join(genericos_ag[:4])}")

    # ---- PA-DATE-01: zona horaria a mano
    if re.search(r"addHours\(\s*utcNow\(\)\s*,\s*-?\d+", texto_completo):
        add("PA-DATE-01")

    # ---- PA-TRG-01: trigger automatico sin condiciones
    for tn, t in triggers.items():
        if _tipo(t) == "openapiconnection":
            if not (t.get("conditions") or _ins(t).get("conditions")):
                add("PA-TRG-01", f"trigger '{tn}'")

    # ---- PA-TRG-02: concurrencia configurada en el trigger
    for tn, t in triggers.items():
        if isinstance(t, dict) and (_rc(t).get("concurrency")):
            add("PA-TRG-02", f"trigger '{tn}'")

    # ---- PA-TRG-03: el flujo escribe en la misma tabla que lo dispara
    for tn, t in triggers.items():
        if _tipo(t) != "openapiconnection":
            continue
        clases_t = _clases_trigger(t)
        if not clases_t:
            continue
        if t.get("conditions") or _ins(t).get("conditions"):
            continue  # con trigger conditions asumimos que el maker ya corto el bucle
        origen_t = _fuente_norm(_params(t))
        if not origen_t:
            continue
        for n, a, _, _, _ in todas:
            if _tipo(a) != "openapiconnection":
                continue
            clase_a = _clase_escritura(_op(a))
            if not clase_a or clase_a not in clases_t:
                continue
            origen_a = _fuente_norm(_params(a))
            comunes = [c for c in origen_t if c in origen_a]
            if comunes and all(origen_t[c] == origen_a[c] for c in comunes):
                add("PA-TRG-03", f"trigger '{tn}' y accion '{n}' sobre la misma tabla")

    # ---- PA-TRG-04: trigger Dataverse sin filteringattributes
    for tn, t in triggers.items():
        if _tipo(t) != "openapiconnection":
            continue
        if "commondataservice" not in _api_id(t) and "dataverse" not in _api_id(t):
            continue
        params = _params(t)
        if any("filteringattributes" in str(k).lower() for k in params.keys()):
            continue
        msg = ""
        for k, v in params.items():
            if "message" in str(k).lower():
                msg = str(v)
        if msg in ("3", "4", "5") or (not msg and "updat" in _op(t).lower()):
            add("PA-TRG-04", f"trigger '{tn}'")

    # ---- PA-VAR-01 / PA-VAR-02: variables sin usar / constantes
    nombres_var = []
    for n, a, _, _, _ in todas:
        if _tipo(a) == "initializevariable":
            try:
                for v in a["inputs"]["variables"]:
                    nombres_var.append(str(v.get("name", "")))
            except (KeyError, TypeError):
                pass
    usadas = {m.lower() for m in re.findall(r"variables\('([^']+)'\)", texto_completo)}
    objetivos = set()
    for n, a, _, _, _ in todas:
        if _tipo(a) in VAR_ESCRITURA:
            objetivos.add(str(_ins(a).get("name", "")).lower())
    for nv in nombres_var:
        nvl = nv.lower()
        if not nvl:
            continue
        if nvl not in usadas and nvl not in objetivos:
            add("PA-VAR-01", f"variable '{nv}'")
        elif nvl in usadas and nvl not in objetivos:
            add("PA-VAR-02", f"variable '{nv}'")

    # ---- PA-SIZE-01 / PA-SIZE-02: tamano y organizacion
    if len(todas) > 50:
        add("PA-SIZE-01", f"{len(todas)} acciones")
    if len(todas) > 10 and not hay_scope:
        add("PA-SIZE-02", f"{len(todas)} acciones sin ningun Scope")

    # ---- PA-CFG-01: configuracion hardcodeada (fuera de host/conexiones)
    sitios = correos = guids = 0
    for n, a, _, _, _ in todas:
        texto = _inputs_sin_host(a)
        sitios += len(URL_SITIO_RE.findall(texto))
        correos += len(CORREO_RE.findall(texto))
        guids += len(GUID_RE.findall(texto))
    for tn, t in triggers.items():
        if isinstance(t, dict):
            texto = _inputs_sin_host(t)
            sitios += len(URL_SITIO_RE.findall(texto))
            correos += len(CORREO_RE.findall(texto))
            guids += len(GUID_RE.findall(texto))
    if sitios or correos or guids:
        partes = [f"{c} {e}" for c, e in ((sitios, "URL(s) de sitio"),
                                          (correos, "correo(s)"), (guids, "GUID(s)")) if c]
        add("PA-CFG-01", ", ".join(partes))

    # ---- PA-NAME-01: nombres genericos
    genericos = [n for n, a, _, _, _ in todas if DEFAULT_RE.match(n)]
    genericos += [n for n in triggers if DEFAULT_RE.match(n)]
    if genericos:
        muestra = ", ".join(genericos[:5]) + (" ..." if len(genericos) > 5 else "")
        add("PA-NAME-01", f"{len(genericos)} accion(es): {muestra}")

    # ---- PA-DOC-01: sin Notes/descripcion
    con_nota = any(a.get("description") or (a.get("metadata", {}) or {}).get("description")
                   for _, a, _, _, _ in todas)
    if not con_nota and len(todas) >= 4:
        add("PA-DOC-01")

    # ---- PA-DOC-02: flujo sin descripcion
    if not (descripcion or "").strip():
        add("PA-DOC-02")

    # ---- PA-LIC-01: conectores premium (informativo)
    premium = set()
    for coleccion in (dict(triggers), {n: a for n, a, _, _, _ in todas}):
        for n, x in coleccion.items():
            if not isinstance(x, dict):
                continue
            if _tipo(x) == "http":
                premium.add("HTTP")
            api = _api_id(x)
            for p in APIS_PREMIUM:
                if p in api:
                    premium.add(p)
    if premium:
        add("PA-LIC-01", ", ".join(sorted(premium)))

    return hallazgos, len(todas), triggers


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------
def veredicto(score):
    if score >= 90:
        return "EXCELENTE - sigue las mejores practicas"
    if score >= 75:
        return "BUENO - mejoras menores recomendadas"
    if score >= 50:
        return "ACEPTABLE - requiere mejoras importantes"
    return "NECESITA REFACTORIZACION"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    ruta = Path(sys.argv[1])
    if not ruta.exists():
        print(f"No existe la ruta: {ruta}")
        return 2

    nombre, defn, connrefs, descripcion = cargar_flujo(ruta)
    if defn is None:
        print("No se encontro una definicion de flujo valida (definition.json con triggers/actions).")
        return 2

    hallazgos, n_acciones, triggers = auditar(defn, connrefs, descripcion)

    # puntuacion
    score = 100
    for cod, _ in hallazgos:
        score -= PESO_SEV[REGLAS[cod][0]]
    score = max(0, score)

    trg_tipos = ", ".join(sorted({(t.get("type") or "?") for t in triggers.values()})) or "?"
    print("=" * 70)
    print(f"AUDITORIA DE FLUJO: {nombre}")
    print("=" * 70)
    print(f"Trigger(s): {trg_tipos}   |   Acciones: {n_acciones}   |   "
          f"Conexiones: {len(connrefs or {})}")
    print(f"PUNTUACION: {score}/100   ->   {veredicto(score)}")
    print("-" * 70)

    if not hallazgos:
        print("Sin hallazgos. El flujo respeta las reglas automatizadas. Excelente.")
        return 0

    # agrupar por codigo (una linea por regla, con conteo)
    vistos = {}
    for cod, extra in hallazgos:
        vistos.setdefault(cod, []).append(extra)

    ordenados = sorted(vistos.items(), key=lambda kv: ORDEN_SEV[REGLAS[kv[0]][0]])
    n_alta = 0
    for cod, extras in ordenados:
        sev, _peso, titulo, arreglo, fuente = REGLAS[cod]
        if sev == "ALTA":
            n_alta += len(extras)
        detalle = "; ".join(e for e in extras if e)
        print(f"\n[{sev}] {cod} - {titulo}")
        if detalle:
            print(f"  Donde: {detalle}")
        print(f"  Arreglo: {arreglo}")
        print(f"  Fuente: {fuente}")

    print("\n" + "-" * 70)
    n_total = sum(len(v) for v in vistos.values())
    print(f"Total: {len(vistos)} tipo(s) de hallazgo, {n_total} ocurrencia(s) "
          f"({n_alta} de severidad ALTA).")
    return 1 if n_alta else 0


if __name__ == "__main__":
    sys.exit(main())
