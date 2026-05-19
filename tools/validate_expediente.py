#!/usr/bin/env python3
"""
validate_expediente.py -- EIA-Agent v2.1
Validador minimo del modelo de datos de un expediente EIA.

Uso:
    python tools/validate_expediente.py <ruta_expediente>
    python tools/validate_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA

Salida:
    - VALIDO   (exit 0) si no hay errores
    - INVALIDO (exit 1) si hay errores de modelo

No requiere dependencias externas. Solo libreria estandar de Python 3.8+.
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CONSTANTES DEL MODELO DE DATOS (extraidas del piloto real)
# ---------------------------------------------------------------------------

ESTADOS_EVIDENCIA = {
    "CONFIRMADO", "DECLARADO", "INFERIDO", "ESTIMADO", "PENDIENTE", "DESCARTADO",
    # Modo test: hipótesis de trabajo provisionales, no confirmadas por el promotor.
    # Distinguibles de todos los estados de evidencia reales.
    "ASUNCION_TEST",
}

# El piloto usa tanto versiones con tilde como sin tilde (encoding historico).
# El validador acepta ambas variantes por robustez.
TIPOS_INFERENCIA = {
    # Versiones sin tilde (normalizadas). El validador normaliza el valor
    # del dato antes de comparar, por lo que los valores con tilde del piloto
    # (CONTRADICCION con acento) tambien son aceptados.
    "CONTRADICCION_RESUELTA_PROVISIONALMENTE",
    "CONTRADICCION",
    "INFERIDO",
    "PENDIENTE_NO_BLOQUEANTE_TEST",
    "PENDIENTE",
    "PUNTO_SENSIBLE_FASE2",
    "CAUTELA_FASE3",
    "CERRADO_PARCIALMENTE_FASE3",
    # Tipos descriptivos en minusculas introducidos en expediente NAVE-222.
    # Taxonomia de tipos lowercase para GAPs, inferencias y contradicciones.
    "gap_documental",
    "gap_dato_tecnico",
    "gap_administrativo",
    "gap_contradiccion_documental",
    "gap_flujo_residuos",
    "inferencia",
    "contradiccion_documental",
}

TIPOS_NORMATIVA = {
    "ley_estatal",
    "real_decreto",
    "ley_autonomica_canarias",
    "decreto_autonomico_canarias",
    "decreto_ley_autonomico_canarias",
}

ESTADOS_NORMATIVA = {"VERIFICADA ONLINE", "REFERENCIADA"}

TIPOS_CARTOGRAFIA = {"GENERADO_AUTOMATICAMENTE", "VERIFICACION_INTERNA"}

ESTADOS_CARTOGRAFIA = {"GENERADO", "VERIFICADO", "ERROR", "PENDIENTE", "PROVISIONAL"}

CAPAS_REQUERIDAS = [
    "hechos_confirmados.json",
    "inferencias_y_gaps.json",
    "normativa_aplicable.json",
    "matriz_trazabilidad.json",
    "cartografia_trace.json",
    "salidas_generadas.json",
]

# ---------------------------------------------------------------------------
# CONSTANTES OB-01: validacion de ficha_objeto_evaluado.md
# ---------------------------------------------------------------------------

FICHA_MIN_CHARS = 500

# Secciones criticas: su ausencia es ERROR (bloquea el gate).
# Cada tupla: (nombre_legible, patron_regex).
# Los patrones se aplican con re.IGNORECASE sobre el contenido completo del archivo.
# Los patrones de encabezado usan "##" como ancla; los de cuerpo buscan en todo el texto.
FICHA_SECCIONES_CRITICAS = [
    ("identificacion_del_proyecto",    r"##.*identificaci|##.*expediente"),
    ("operaciones_incluidas",          r"##.*operac.*incluid"),
    ("operaciones_excluidas",          r"##.*operac.*excluid"),
    ("referencia_catastral_en_cuerpo", r"referencia catastral"),
    ("coordenadas_en_cuerpo",          r"coordenadas"),
    ("superficie_evaluada_en_cuerpo",  r"superficie"),
]

# Secciones informativas: su ausencia es WARNING (no bloquea).
FICHA_SECCIONES_INFORMATIVAS = [
    ("promotor",                      r"##.*promotor"),
    ("ubicacion_o_delimitacion",      r"##.*ubicaci|##.*delimitaci"),
    ("equipos_o_recursos_materiales", r"##.*equipo"),
    ("dependencia_funcional",         r"##.*dependencia"),
    ("puntos_sensibles_o_pendientes", r"##.*puntos.sensibles|##.*pendientes"),
]

# Patrones de prefijo de ID por capa
ID_PREFIXES = {
    "hechos_confirmados.json":   "HC-",
    "normativa_aplicable.json":  "NJ-",
    "matriz_trazabilidad.json":  "TR-",
    "cartografia_trace.json":    "CT-",
    "salidas_generadas.json":    "SG-",
    # inferencias_y_gaps permite multiples prefijos, se valida por separado
}

# ---------------------------------------------------------------------------
# ACUMULADOR DE RESULTADOS
# ---------------------------------------------------------------------------

class Result:
    def __init__(self):
        self.errors   = []
        self.warnings = []
        self.checked  = 0

    def error(self, msg: str):
        self.errors.append(msg)

    def warning(self, msg: str):
        self.warnings.append(msg)

    def tick(self):
        self.checked += 1

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# HELPERS DE VALIDACION
# ---------------------------------------------------------------------------

def _require(item: dict, field: str, layer: str, item_id: str, r: Result,
             allow_null: bool = False) -> bool:
    if field not in item:
        r.error(f"[{layer}] {item_id}: campo obligatorio '{field}' ausente")
        return False
    if item[field] is None and not allow_null:
        r.error(f"[{layer}] {item_id}: campo '{field}' es null (obligatorio)")
        return False
    return True


def _require_nonempty_string(item: dict, field: str, layer: str, item_id: str, r: Result):
    if not _require(item, field, layer, item_id, r):
        return
    v = item[field]
    if not isinstance(v, str):
        r.error(f"[{layer}] {item_id}: '{field}' debe ser string, es {type(v).__name__}")
    elif v.strip() == "":
        r.warning(f"[{layer}] {item_id}: '{field}' esta vacio")


def _check_enum(item: dict, field: str, allowed: set, layer: str, item_id: str, r: Result):
    if field not in item or item[field] is None:
        return
    if item[field] not in allowed:
        r.error(
            f"[{layer}] {item_id}: '{field}' = '{item[field]}' no es un valor permitido. "
            f"Permitidos: {sorted(allowed)}"
        )


def _check_nonempty_array(item: dict, field: str, layer: str, item_id: str, r: Result):
    if not _require(item, field, layer, item_id, r):
        return
    v = item[field]
    if not isinstance(v, list):
        r.error(f"[{layer}] {item_id}: '{field}' debe ser array, es {type(v).__name__}")
    elif len(v) == 0:
        r.error(f"[{layer}] {item_id}: '{field}' no puede ser un array vacio")


def _check_id_uniqueness(data: list, layer: str, r: Result) -> set:
    seen = {}
    for item in data:
        item_id = item.get("id")
        if item_id is None:
            continue
        if item_id in seen:
            r.error(f"[{layer}] ID duplicado: '{item_id}'")
        seen[item_id] = True
    return set(seen.keys())


def _check_id_prefix(ids: set, prefix: str, layer: str, r: Result):
    for item_id in ids:
        if not item_id.startswith(prefix):
            r.warning(
                f"[{layer}] ID '{item_id}' no sigue el prefijo esperado '{prefix}NNN'"
            )


# ---------------------------------------------------------------------------
# VALIDADORES POR CAPA
# ---------------------------------------------------------------------------

def validate_hechos_confirmados(data: list, r: Result) -> set:
    layer = "hechos_confirmados"
    ids = _check_id_uniqueness(data, layer, r)

    for item in data:
        iid = item.get("id", "<sin id>")
        _require_nonempty_string(item, "id",       layer, iid, r)
        _require_nonempty_string(item, "categoria", layer, iid, r)
        _require_nonempty_string(item, "campo",     layer, iid, r)
        _require(item, "valor",   layer, iid, r)
        if _require(item, "estado", layer, iid, r):
            _check_enum(item, "estado", ESTADOS_EVIDENCIA, layer, iid, r)
        _check_nonempty_array(item, "fuentes", layer, iid, r)
        r.tick()

    _check_id_prefix(ids, "HC-", layer, r)
    return ids


def validate_inferencias_y_gaps(data: list, r: Result) -> set:
    layer = "inferencias_y_gaps"
    ids = _check_id_uniqueness(data, layer, r)
    VALID_PREFIXES = {"CONT-", "INF-", "GAP-", "PS-INF-", "CAUTELA-"}

    for item in data:
        iid = item.get("id", "<sin id>")
        _require_nonempty_string(item, "id",         layer, iid, r)
        _require_nonempty_string(item, "tipo",       layer, iid, r)
        _require_nonempty_string(item, "criticidad", layer, iid, r)
        _require_nonempty_string(item, "campo",      layer, iid, r)

        # tipo: validar contra enum normalizado (strip tildes en comparacion)
        if "tipo" in item:
            tipo_norm = item["tipo"].replace("\u00c3\u00b3", "o").replace("\u00f3", "o")
            tipo_clean = _normalize_accents(item["tipo"])
            if tipo_clean not in TIPOS_INFERENCIA:
                r.warning(
                    f"[{layer}] {iid}: 'tipo' = '{item['tipo']}' no esta en el enum conocido. "
                    "Puede ser un tipo nuevo -- verifica que es intencional."
                )

        # descripcion: requerida para GAP e INF, opcional para CONT y CAUTELA
        tipo = item.get("tipo", "")
        if "PENDIENTE" in tipo or "INFERIDO" in tipo:
            if "descripcion" not in item and "descripcion_original" not in item:
                r.warning(f"[{layer}] {iid}: ni 'descripcion' ni 'descripcion_original' presentes")

        # validar prefijo del ID
        iid_str = item.get("id", "")
        if not any(iid_str.startswith(p) for p in VALID_PREFIXES):
            r.warning(
                f"[{layer}] {iid}: ID no sigue ningun prefijo conocido "
                f"({', '.join(sorted(VALID_PREFIXES))})"
            )

        r.tick()

    return ids


def validate_normativa_aplicable(data: list, r: Result) -> set:
    layer = "normativa_aplicable"
    ids = _check_id_uniqueness(data, layer, r)

    for item in data:
        iid = item.get("id", "<sin id>")
        _require_nonempty_string(item, "id",    layer, iid, r)
        _require_nonempty_string(item, "norma", layer, iid, r)
        if _require(item, "tipo", layer, iid, r):
            _check_enum(item, "tipo", TIPOS_NORMATIVA, layer, iid, r)
        if _require(item, "estado", layer, iid, r):
            _check_enum(item, "estado", ESTADOS_NORMATIVA, layer, iid, r)
        r.tick()

    _check_id_prefix(ids, "NJ-", layer, r)
    return ids


def validate_matriz_trazabilidad(data: list, hc_ids: set, r: Result) -> set:
    layer = "matriz_trazabilidad"
    ids = _check_id_uniqueness(data, layer, r)

    for item in data:
        iid = item.get("id", "<sin id>")
        _require_nonempty_string(item, "id",            layer, iid, r)
        _require_nonempty_string(item, "dato",          layer, iid, r)
        _require(item, "valor",          layer, iid, r)
        _require_nonempty_string(item, "fuente_primaria", layer, iid, r)
        if _require(item, "estado_evidencia", layer, iid, r):
            _check_enum(item, "estado_evidencia", ESTADOS_EVIDENCIA, layer, iid, r)
        r.tick()

    _check_id_prefix(ids, "TR-", layer, r)
    return ids


def validate_cartografia_trace(data: list, r: Result) -> set:
    layer = "cartografia_trace"
    ids = _check_id_uniqueness(data, layer, r)

    for item in data:
        iid = item.get("id", "<sin id>")
        _require_nonempty_string(item, "id",              layer, iid, r)
        _require_nonempty_string(item, "titulo",          layer, iid, r)
        _require_nonempty_string(item, "archivo_resultado", layer, iid, r)
        if _require(item, "tipo_cartografia", layer, iid, r):
            _check_enum(item, "tipo_cartografia", TIPOS_CARTOGRAFIA, layer, iid, r)
        if _require(item, "estado", layer, iid, r):
            _check_enum(item, "estado", ESTADOS_CARTOGRAFIA, layer, iid, r)
        r.tick()

    _check_id_prefix(ids, "CT-", layer, r)
    return ids


def validate_salidas_generadas(data: list, r: Result) -> set:
    layer = "salidas_generadas"
    ids = _check_id_uniqueness(data, layer, r)

    for item in data:
        iid = item.get("id", "<sin id>")
        _require_nonempty_string(item, "id",           layer, iid, r)
        _require_nonempty_string(item, "fase",         layer, iid, r)
        _require_nonempty_string(item, "agente",       layer, iid, r)
        _require_nonempty_string(item, "fecha",        layer, iid, r)
        _require_nonempty_string(item, "tipo",         layer, iid, r)
        _require_nonempty_string(item, "nombre_archivo", layer, iid, r)
        _require_nonempty_string(item, "descripcion",  layer, iid, r)
        r.tick()

    _check_id_prefix(ids, "SG-", layer, r)
    return ids


# ---------------------------------------------------------------------------
# CONSISTENCIA ENTRE CAPAS
# ---------------------------------------------------------------------------

def validate_cross_layer(loaded: dict, hc_ids: set, r: Result):
    """Verificaciones minimas de consistencia entre capas."""

    # hechos_confirmados no debe estar vacia
    if "hechos_confirmados.json" in loaded:
        if len(loaded["hechos_confirmados.json"]) == 0:
            r.warning("hechos_confirmados esta vacia -- el expediente no tiene hechos registrados")

    # salidas_generadas no debe estar vacia (expediente con alguna fase completada)
    if "salidas_generadas.json" in loaded:
        if len(loaded["salidas_generadas.json"]) == 0:
            r.warning("salidas_generadas esta vacia -- ninguna salida registrada")

    # normativa_aplicable debe tener al menos una norma verificada online
    if "normativa_aplicable.json" in loaded:
        verificadas = [
            n for n in loaded["normativa_aplicable.json"]
            if n.get("estado") == "VERIFICADA ONLINE"
        ]
        if len(verificadas) == 0:
            r.warning(
                "normativa_aplicable: ninguna norma tiene estado 'VERIFICADA ONLINE' -- "
                "el triaje normativo puede no haberse ejecutado"
            )

    # cartografia_trace debe tener al menos un mapa generado
    if "cartografia_trace.json" in loaded:
        generados = [
            c for c in loaded["cartografia_trace.json"]
            if c.get("estado") in ("GENERADO", "VERIFICADO")
        ]
        if len(generados) == 0:
            r.warning("cartografia_trace: ningun mapa en estado GENERADO o VERIFICADO")


def count_gaps_alta(inferencias: list) -> list:
    """Devuelve los GAPs de tipo PENDIENTE con criticidad ALTA."""
    return [
        item for item in inferencias
        if item.get("tipo", "").startswith("PENDIENTE")
        and "ALTA" in str(item.get("criticidad", "")).upper()
        and "RESUELTA" not in str(item.get("criticidad", "")).upper()
    ]


def validate_hc_trazabilidad(hc_data: list, tr_data: list, r: Result):
    """
    AU-03: Verifica coherencia entre hechos_confirmados y matriz_trazabilidad.

    Regla de correspondencia:
      Cada entrada TR puede declarar un campo 'hc_ids' (array de HC-IDs).
      AU-03 comprueba:
        (a) Integridad referencial: cada ID en hc_ids debe existir en
            hechos_confirmados. Referencia colgante -> ERROR.
        (b) Cobertura: cada HC con estado CONFIRMADO y categoria fuera del
            conjunto excluido debe aparecer en al menos un hc_ids de algun TR.
            HC sin cobertura -> WARNING.

    Categorias excluidas de la comprobacion de cobertura:
      - 'tecnico_redactor': identificacion del equipo redactor — es
        informacion administrativa, no dato material del expediente.

    Notas:
      - Si ningun TR tiene el campo 'hc_ids', AU-03 emite un aviso global
        y no comprueba cobertura (campo opcional por retrocompatibilidad).
      - hc_ids: [] (array vacio) es valido y significa 'este TR no enlaza HC'.
    """
    EXCLUIR_CATS = {"tecnico_redactor"}

    # Construir set de todos los HC-IDs validos
    all_hc_ids = {h.get("id") for h in hc_data if h.get("id")}

    # Construir set de HC-IDs cubiertos por algun TR
    covered_hc_ids: set = set()
    tr_with_hc_ids = 0

    for tr in tr_data:
        tr_id  = tr.get("id", "<sin id>")
        hc_ids = tr.get("hc_ids")

        if hc_ids is None:
            continue  # campo no declarado en este TR: compatible

        if not isinstance(hc_ids, list):
            r.error(
                f"[matriz_trazabilidad] {tr_id}: 'hc_ids' debe ser un array, "
                f"es {type(hc_ids).__name__}"
            )
            continue

        tr_with_hc_ids += 1

        for hc_id in hc_ids:
            if not isinstance(hc_id, str):
                r.error(
                    f"[matriz_trazabilidad] {tr_id}: 'hc_ids' contiene un valor "
                    f"no-string: {hc_id!r}"
                )
                continue
            if hc_id not in all_hc_ids:
                r.error(
                    f"[matriz_trazabilidad] {tr_id}: 'hc_ids' referencia "
                    f"'{hc_id}' que no existe en hechos_confirmados"
                )
            else:
                covered_hc_ids.add(hc_id)

    # Si ninguna TR tiene hc_ids: no podemos comprobar cobertura
    if tr_with_hc_ids == 0:
        r.warning(
            "AU-03: ninguna entrada de matriz_trazabilidad tiene el campo "
            "'hc_ids' -- no se puede verificar cobertura HC -> TR"
        )
        return

    # Comprobar cobertura de HC CONFIRMADOS (excluidas categorias admin)
    for hc in hc_data:
        if hc.get("estado") != "CONFIRMADO":
            continue
        if hc.get("categoria") in EXCLUIR_CATS:
            continue
        hc_id = hc.get("id", "<sin id>")
        if hc_id not in covered_hc_ids:
            r.warning(
                f"[AU-03] {hc_id} ({hc.get('campo','?')}): HC CONFIRMADO sin "
                f"trazabilidad en matriz_trazabilidad"
            )


def validate_ficha_objeto(base: Path, r: Result):
    """
    OB-01: Valida el contenido minimo de control_interno/ficha_objeto_evaluado.md.

    Regla de validacion:
      1. El archivo debe existir.
      2. Debe superar FICHA_MIN_CHARS caracteres (no puede ser una plantilla vacia).
      3. Debe contener las secciones criticas definidas en FICHA_SECCIONES_CRITICAS.
         Ausencia de cualquier seccion critica -> ERROR (bloqueante).
      4. Debe contener las secciones informativas de FICHA_SECCIONES_INFORMATIVAS.
         Ausencia de seccion informativa -> WARNING (no bloqueante).

    Busqueda: re.search con re.IGNORECASE sobre el contenido completo del archivo.
    No se parsea lenguaje natural ni se valoran valores; solo presencia de terminos clave.

    Si el archivo no existe, se emite WARNING (no ERROR) porque el gate de Fase 3
    ya controla la existencia como requisito de la fase. Llamada desde el validador
    general, la ausencia es informativa.
    """
    ficha = base / "control_interno" / "ficha_objeto_evaluado.md"

    if not ficha.exists():
        r.warning(
            "OB-01: control_interno/ficha_objeto_evaluado.md no existe "
            "-- Fase 2 (AG-4) no se ha ejecutado"
        )
        return

    try:
        content = ficha.read_text(encoding="utf-8")
    except Exception as e:
        r.error(f"OB-01: no se puede leer ficha_objeto_evaluado.md -- {e}")
        return

    # 1. Tamano minimo
    if len(content) < FICHA_MIN_CHARS:
        r.error(
            f"OB-01: ficha_objeto_evaluado.md tiene {len(content)} caracteres "
            f"(minimo requerido: {FICHA_MIN_CHARS}) -- parece incompleta o vacia"
        )

    # 2. Secciones criticas
    for nombre, patron in FICHA_SECCIONES_CRITICAS:
        if not re.search(patron, content, re.IGNORECASE):
            r.error(
                f"OB-01: seccion critica ausente: '{nombre}' "
                f"(patron buscado: {patron!r})"
            )

    # 3. Secciones informativas
    for nombre, patron in FICHA_SECCIONES_INFORMATIVAS:
        if not re.search(patron, content, re.IGNORECASE):
            r.warning(
                f"OB-01: seccion informativa ausente: '{nombre}' "
                f"(patron buscado: {patron!r})"
            )


def validate_archivos_fisicos(loaded: dict, base: Path, r: Result):
    """
    EN-02: Verifica que los archivos referenciados en las capas existen en disco.

    Reglas de bloqueo:
      - cartografia_trace / archivo_resultado:
          ERROR   si estado GENERADO o VERIFICADO y el archivo no existe.
          WARNING si estado ERROR o PENDIENTE y el archivo no existe.
          SKIP    si archivo_resultado empieza por 'N/A' o tipo_cartografia
                  es VERIFICACION_INTERNA (entradas sin archivo fisico).
      - salidas_generadas / nombre_archivo:
          ERROR   siempre que el archivo no exista (todas las SG representan
                  salidas ya generadas; no hay estado intermedio en esta capa).
    """
    # ---- cartografia_trace: archivo_resultado --------------------------------
    if "cartografia_trace.json" in loaded:
        for ct in loaded["cartografia_trace.json"]:
            iid = ct.get("id", "<sin id>")
            ar  = ct.get("archivo_resultado", "")

            # Saltar entradas sin archivo fisico declarado
            if not ar or ar.strip().upper().startswith("N/A"):
                continue
            # Saltar verificaciones internas (no producen archivo)
            if ct.get("tipo_cartografia") == "VERIFICACION_INTERNA":
                continue

            ruta = base / ar
            if not ruta.exists():
                estado = ct.get("estado", "")
                if estado in ("GENERADO", "VERIFICADO"):
                    r.error(
                        f"[cartografia_trace] {iid}: archivo_resultado no existe en disco: {ar}"
                    )
                else:
                    r.warning(
                        f"[cartografia_trace] {iid}: archivo_resultado ausente "
                        f"(estado={estado}): {ar}"
                    )

    # ---- salidas_generadas: nombre_archivo -----------------------------------
    if "salidas_generadas.json" in loaded:
        for sg in loaded["salidas_generadas.json"]:
            iid = sg.get("id", "<sin id>")
            nf  = sg.get("nombre_archivo", "")

            if not nf:
                continue  # ya detectado como campo requerido ausente

            ruta = base / nf
            if not ruta.exists():
                r.error(
                    f"[salidas_generadas] {iid}: nombre_archivo no existe en disco: {nf}"
                )


# ---------------------------------------------------------------------------
# NORMALIZACION DE TILDES (para comparacion robusta de tipos)
# ---------------------------------------------------------------------------

def _normalize_accents(s: str) -> str:
    replacements = {
        "\u00e1": "a", "\u00e9": "e", "\u00ed": "i", "\u00f3": "o", "\u00fa": "u",
        "\u00c1": "A", "\u00c9": "E", "\u00cd": "I", "\u00d3": "O", "\u00da": "U",
        "\u00fc": "u", "\u00f1": "n", "\u00d1": "N",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    return s


# ---------------------------------------------------------------------------
# VALIDADOR PRINCIPAL
# ---------------------------------------------------------------------------

def validate_expediente(expediente_path: str) -> int:
    base = Path(expediente_path)
    capas_dir = base / "capas"

    r = Result()

    SEP = "=" * 70
    sep = "-" * 50

    print(f"\n{SEP}")
    print("EIA-Agent v2.1 -- Validador de expediente")
    print(f"Expediente : {base.resolve()}")
    print(f"{SEP}\n")

    # ------------------------------------------------------------------
    # 1. Existencia del directorio y de capas/
    # ------------------------------------------------------------------
    print(f"{sep}")
    print("1. EXISTENCIA DEL EXPEDIENTE Y CAPAS")
    print(f"{sep}")

    if not base.exists():
        print(f"  ERROR FATAL: el directorio '{base}' no existe.")
        return 1

    if not capas_dir.exists():
        print(f"  ERROR FATAL: el subdirectorio 'capas/' no existe en '{base}'.")
        return 1

    missing_capas = []
    for capa in CAPAS_REQUERIDAS:
        path = capas_dir / capa
        if path.exists():
            print(f"  OK  {capa}")
        else:
            print(f"  !!  {capa}  <- AUSENTE")
            missing_capas.append(capa)
            r.error(f"Capa requerida ausente: {capa}")
    print()

    # ------------------------------------------------------------------
    # 2. Validez del JSON
    # ------------------------------------------------------------------
    print(f"{sep}")
    print("2. VALIDEZ DEL JSON")
    print(f"{sep}")

    loaded = {}
    for capa in CAPAS_REQUERIDAS:
        path = capas_dir / capa
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                r.error(f"{capa}: el contenido raiz debe ser un array JSON, es {type(data).__name__}")
                print(f"  !!  {capa}: no es un array JSON")
            else:
                loaded[capa] = data
                print(f"  OK  {capa}  ({len(data)} registros)")
        except json.JSONDecodeError as e:
            r.error(f"{capa}: JSON invalido -- {e}")
            print(f"  !!  {capa}: JSON INVALIDO -- {e}")
    print()

    # ------------------------------------------------------------------
    # 3. Validacion de campos y valores por capa
    # ------------------------------------------------------------------
    print(f"{sep}")
    print("3. CAMPOS, TIPOS Y VALORES PERMITIDOS")
    print(f"{sep}")

    hc_ids = set()

    if "hechos_confirmados.json" in loaded:
        before = len(r.errors)
        hc_ids = validate_hechos_confirmados(loaded["hechos_confirmados.json"], r)
        errs = len(r.errors) - before
        print(f"  hechos_confirmados    : {len(hc_ids):3d} registros  {errs} errores")

    if "inferencias_y_gaps.json" in loaded:
        before = len(r.errors)
        gap_ids = validate_inferencias_y_gaps(loaded["inferencias_y_gaps.json"], r)
        errs = len(r.errors) - before
        print(f"  inferencias_y_gaps    : {len(gap_ids):3d} registros  {errs} errores")

    if "normativa_aplicable.json" in loaded:
        before = len(r.errors)
        nj_ids = validate_normativa_aplicable(loaded["normativa_aplicable.json"], r)
        errs = len(r.errors) - before
        print(f"  normativa_aplicable   : {len(nj_ids):3d} registros  {errs} errores")

    if "matriz_trazabilidad.json" in loaded:
        before = len(r.errors)
        tr_ids = validate_matriz_trazabilidad(loaded["matriz_trazabilidad.json"], hc_ids, r)
        errs = len(r.errors) - before
        print(f"  matriz_trazabilidad   : {len(tr_ids):3d} registros  {errs} errores")

    if "cartografia_trace.json" in loaded:
        before = len(r.errors)
        ct_ids = validate_cartografia_trace(loaded["cartografia_trace.json"], r)
        errs = len(r.errors) - before
        print(f"  cartografia_trace     : {len(ct_ids):3d} registros  {errs} errores")

    if "salidas_generadas.json" in loaded:
        before = len(r.errors)
        sg_ids = validate_salidas_generadas(loaded["salidas_generadas.json"], r)
        errs = len(r.errors) - before
        print(f"  salidas_generadas     : {len(sg_ids):3d} registros  {errs} errores")

    print()

    # ------------------------------------------------------------------
    # 4. Consistencia entre capas
    # ------------------------------------------------------------------
    print(f"{sep}")
    print("4. CONSISTENCIA ENTRE CAPAS")
    print(f"{sep}")

    validate_cross_layer(loaded, hc_ids, r)

    if "inferencias_y_gaps.json" in loaded:
        gaps_alta = count_gaps_alta(loaded["inferencias_y_gaps.json"])
        if gaps_alta:
            print(f"  AVISO: {len(gaps_alta)} GAP(s) de criticidad ALTA abiertos:")
            for g in gaps_alta:
                print(f"    - {g.get('id','?')}  {g.get('campo','?')}")
        else:
            print("  OK  Sin GAPs de criticidad ALTA abiertos")

    # AU-03: coherencia HC -> TR
    if "hechos_confirmados.json" in loaded and "matriz_trazabilidad.json" in loaded:
        before_w = len(r.warnings)
        before_e = len(r.errors)
        validate_hc_trazabilidad(
            loaded["hechos_confirmados.json"],
            loaded["matriz_trazabilidad.json"],
            r,
        )
        new_e = len(r.errors)   - before_e
        new_w = len(r.warnings) - before_w
        au03_warns = r.warnings[before_w:]
        au03_errs  = r.errors[before_e:]
        if new_e == 0 and new_w == 0:
            print("  OK  AU-03: todos los HC CONFIRMADOS tienen trazabilidad")
        else:
            if new_e:
                for e in au03_errs:
                    print(f"  !!  {e}")
            if new_w:
                au03_coverage = [w for w in au03_warns if "[AU-03]" in w]
                au03_other    = [w for w in au03_warns if "[AU-03]" not in w]
                for w in au03_other:
                    print(f"  >>  {w}")
                if au03_coverage:
                    print(f"  >>  AU-03: {len(au03_coverage)} HC CONFIRMADO(s) sin trazabilidad:")
                    for w in au03_coverage:
                        hc_part = w.split("]", 1)[-1].strip()
                        print(f"        - {hc_part}")

    # Mostrar advertencias de cross-layer (capas vacias, normativa, cartografia)
    cross_warnings = [w for w in r.warnings if "vacia" in w or "VERIFICADA" in w or "GENERADO" in w]
    for w in cross_warnings:
        print(f"  AVISO: {w}")

    print()

    # ------------------------------------------------------------------
    # 5. Ficha del objeto evaluado (OB-01)
    # ------------------------------------------------------------------
    print(f"{sep}")
    print("5. FICHA OBJETO EVALUADO (OB-01)")
    print(f"{sep}")

    before_err  = len(r.errors)
    before_warn = len(r.warnings)
    validate_ficha_objeto(base, r)
    new_errors   = len(r.errors)   - before_err
    new_warnings = len(r.warnings) - before_warn

    ficha_path = base / "control_interno" / "ficha_objeto_evaluado.md"
    if not ficha_path.exists():
        print("  >>  ficha_objeto_evaluado.md no existe")
    elif new_errors == 0 and new_warnings == 0:
        print("  OK  ficha_objeto_evaluado.md valida (estructura y contenido minimo)")
    else:
        if new_errors:
            for e in r.errors[before_err:]:
                print(f"  !!  {e}")
        if new_warnings:
            for w in r.warnings[before_warn:]:
                print(f"  >>  {w}")
    print()

    # ------------------------------------------------------------------
    # 6. Existencia fisica de archivos referenciados
    # ------------------------------------------------------------------
    print(f"{sep}")
    print("6. EXISTENCIA FISICA DE ARCHIVOS")
    print(f"{sep}")

    before_err  = len(r.errors)
    before_warn = len(r.warnings)
    validate_archivos_fisicos(loaded, base, r)
    new_errors   = len(r.errors)   - before_err
    new_warnings = len(r.warnings) - before_warn

    if new_errors == 0 and new_warnings == 0:
        print("  OK  Todos los archivos referenciados existen en disco")
    else:
        if new_errors:
            for e in r.errors[before_err:]:
                print(f"  !!  {e}")
        if new_warnings:
            for w in r.warnings[before_warn:]:
                print(f"  >>  {w}")
    print()

    # ------------------------------------------------------------------
    # 7. Resultado final
    # ------------------------------------------------------------------
    print(f"{SEP}")
    print("RESULTADO FINAL")
    print(f"{SEP}")

    n_errors   = len(r.errors)
    n_warnings = len(r.warnings)

    if n_errors > 0:
        print(f"\n  ERRORES ({n_errors}):")
        for e in r.errors:
            print(f"    !! {e}")

    if n_warnings > 0:
        print(f"\n  ADVERTENCIAS ({n_warnings}):")
        for w in r.warnings:
            print(f"    >> {w}")

    print()
    if r.valid:
        print(f"  RESULTADO: VALIDO")
        print(f"  Registros validados: {r.checked} | Advertencias: {n_warnings}")
    else:
        print(f"  RESULTADO: INVALIDO")
        print(f"  Errores: {n_errors} | Advertencias: {n_warnings} | Registros revisados: {r.checked}")

    print()
    return 0 if r.valid else 1


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    code = validate_expediente(sys.argv[1])
    sys.exit(code)
