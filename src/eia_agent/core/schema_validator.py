"""
schema_validator -- NL-02
Valida un expediente EIA-Agent v2.1 contra los schemas JSON de NL-01.

Uso:
    from eia_agent.core.schema_validator import validate_expediente
    result = validate_expediente("expediente-EIA-2026-RECIMETAL-NAVE-222")
    print(result.summary())
    if not result.is_valid():
        for issue in result.issues:
            if issue.severity == "ERROR":
                print(issue)
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_DEFAULT_SCHEMA_SUBPATH = Path("config") / "schemas" / "v2_1"
_SCHEMA_INDEX_FILENAME = "schema_index.json"
_SCHEMA_VERSION = "2.1"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """Un problema detectado durante la validacion de una capa."""
    severity: str           # ERROR / WARNING / INFO
    layer: str              # nombre de la capa (hechos_confirmados, etc.)
    path: str               # ruta legible dentro del JSON o descripcion
    message: str            # descripcion del problema
    code: Optional[str] = None  # codigo opcional para filtrado programatico

    def __str__(self) -> str:
        code_str = f" [{self.code}]" if self.code else ""
        return f"[{self.severity}]{code_str} {self.layer} / {self.path}: {self.message}"


@dataclass
class ValidationResult:
    """Resultado completo de la validacion de un expediente."""
    expediente_path: Path
    schema_version: str
    issues: list[ValidationIssue] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        """True si no hay errores (warnings e infos no bloquean)."""
        return self.error_count() == 0

    def summary(self) -> str:
        total = len(self.issues)
        e = self.error_count()
        w = self.warning_count()
        i = self.info_count()
        estado = "VALIDO" if self.is_valid() else "NO VALIDO"
        lines = [
            f"Expediente : {self.expediente_path}",
            f"Schema v   : {self.schema_version}",
            f"Estado     : {estado}",
            f"Problemas  : {total} total ({e} errores, {w} avisos, {i} info)",
        ]
        if self.issues:
            lines.append("")
            for issue in self.issues:
                lines.append(f"  {issue}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones internas
# ---------------------------------------------------------------------------

def _project_root_from_schema_dir(schema_dir: Path) -> Path:
    """Devuelve la raiz del proyecto asumiendo que schema_dir es config/schemas/v2_1."""
    return schema_dir.parent.parent.parent


def _build_resolver_store(schema_dir: Path) -> dict:
    """Carga todos los schemas del directorio en un store por file URI."""
    store: dict = {}
    for f in schema_dir.glob("*.schema.json"):
        try:
            schema = json.loads(f.read_text(encoding="utf-8"))
            store[f.as_uri()] = schema
        except (json.JSONDecodeError, OSError):
            pass
    return store


def _make_resolver(schema_path: Path, schema: dict, store: dict):
    """Crea un RefResolver con el store precargado."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return jsonschema.RefResolver(
            base_uri=schema_path.as_uri(),
            referrer=schema,
            store=store,
        )


def _json_path_to_str(absolute_path) -> str:
    """Convierte la ruta absoluta de jsonschema a string legible."""
    parts = list(absolute_path)
    if not parts:
        return "<raiz>"
    return " / ".join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def load_schema_index(schema_dir: Path) -> dict:
    """Carga y devuelve el contenido de schema_index.json.

    Args:
        schema_dir: directorio que contiene los schemas v2.1.

    Returns:
        dict con la estructura del schema_index.json.

    Raises:
        FileNotFoundError: si schema_index.json no existe.
        json.JSONDecodeError: si el archivo no es JSON valido.
    """
    index_path = schema_dir / _SCHEMA_INDEX_FILENAME
    if not index_path.exists():
        raise FileNotFoundError(
            f"schema_index.json no encontrado en: {schema_dir}"
        )
    return json.loads(index_path.read_text(encoding="utf-8"))


def validate_layer(
    expediente_path: Path,
    layer_name: str,
    layer_file: str,
    schema_file: str,
    schema_dir: Path,
) -> list[ValidationIssue]:
    """Valida una capa individual de un expediente contra su schema.

    Args:
        expediente_path: directorio raiz del expediente.
        layer_name:      nombre logico de la capa (ej. 'hechos_confirmados').
        layer_file:      ruta relativa del archivo de datos (ej. 'capas/hechos_confirmados.json').
        schema_file:     nombre del archivo de schema (ej. 'hechos_confirmados.schema.json').
        schema_dir:      directorio que contiene los schemas.

    Returns:
        Lista de ValidationIssue. Vacia si la capa es completamente valida.
    """
    issues: list[ValidationIssue] = []

    # --- 1. Verificar que el archivo de la capa existe ---
    data_path = expediente_path / layer_file
    if not data_path.exists():
        issues.append(ValidationIssue(
            severity="ERROR",
            layer=layer_name,
            path=layer_file,
            message=f"Archivo de capa no encontrado: {data_path}",
            code="LAYER_NOT_FOUND",
        ))
        return issues

    # --- 2. Verificar que el JSON es valido ---
    try:
        raw_text = data_path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(ValidationIssue(
            severity="ERROR",
            layer=layer_name,
            path=layer_file,
            message=f"Error al leer el archivo: {exc}",
            code="FILE_READ_ERROR",
        ))
        return issues

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        issues.append(ValidationIssue(
            severity="ERROR",
            layer=layer_name,
            path=layer_file,
            message=f"JSON mal formado: {exc}",
            code="JSON_PARSE_ERROR",
        ))
        return issues

    # --- 3. Verificar que el schema existe ---
    schema_path = schema_dir / schema_file
    if not schema_path.exists():
        issues.append(ValidationIssue(
            severity="ERROR",
            layer=layer_name,
            path=schema_file,
            message=f"Schema no encontrado: {schema_path}",
            code="SCHEMA_NOT_FOUND",
        ))
        return issues

    if not _JSONSCHEMA_AVAILABLE:
        issues.append(ValidationIssue(
            severity="WARNING",
            layer=layer_name,
            path=layer_file,
            message="jsonschema no instalado -- validacion de schema omitida",
            code="JSONSCHEMA_NOT_AVAILABLE",
        ))
        return issues

    # --- 4. Cargar schema y validar ---
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(ValidationIssue(
            severity="ERROR",
            layer=layer_name,
            path=schema_file,
            message=f"Schema con JSON mal formado: {exc}",
            code="SCHEMA_PARSE_ERROR",
        ))
        return issues

    store = _build_resolver_store(schema_dir)
    resolver = _make_resolver(schema_path, schema, store)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        validator = Draft202012Validator(schema, resolver=resolver)
        for error in validator.iter_errors(data):
            path_str = _json_path_to_str(error.absolute_path)
            issues.append(ValidationIssue(
                severity="ERROR",
                layer=layer_name,
                path=path_str,
                message=error.message,
                code="SCHEMA_VALIDATION_ERROR",
            ))

    return issues


def validate_expediente(
    expediente_path: "str | Path",
    schema_dir: "str | Path | None" = None,
) -> ValidationResult:
    """Valida un expediente EIA-Agent v2.1 completo contra los schemas JSON.

    Valida las 6 capas definidas en schema_index.json.
    No modifica ningun archivo del expediente.

    Args:
        expediente_path: directorio raiz del expediente.
        schema_dir:      directorio con los schemas. Por defecto usa
                         <project_root>/config/schemas/v2_1/.

    Returns:
        ValidationResult con todos los issues encontrados.
    """
    expediente_path = Path(expediente_path).resolve()

    # Resolver schema_dir
    if schema_dir is None:
        # Asumir que el modulo esta en src/eia_agent/core/,
        # por lo que la raiz del proyecto es 3 niveles arriba.
        module_dir = Path(__file__).resolve().parent
        project_root = module_dir.parent.parent.parent
        schema_dir = project_root / _DEFAULT_SCHEMA_SUBPATH
    else:
        schema_dir = Path(schema_dir).resolve()

    result = ValidationResult(
        expediente_path=expediente_path,
        schema_version=_SCHEMA_VERSION,
    )

    # Cargar indice de schemas
    try:
        index = load_schema_index(schema_dir)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        result.issues.append(ValidationIssue(
            severity="ERROR",
            layer="<indice>",
            path=str(schema_dir / _SCHEMA_INDEX_FILENAME),
            message=str(exc),
            code="INDEX_NOT_FOUND",
        ))
        return result

    capas = index.get("capas", [])
    if not capas:
        result.issues.append(ValidationIssue(
            severity="ERROR",
            layer="<indice>",
            path=str(schema_dir / _SCHEMA_INDEX_FILENAME),
            message="schema_index.json no contiene ninguna capa",
            code="INDEX_EMPTY",
        ))
        return result

    # Validar cada capa
    for entrada in capas:
        layer_name = entrada.get("nombre", "?")
        layer_file = entrada.get("archivo_json", "")
        schema_rel = entrada.get("schema", "")
        schema_file = Path(schema_rel).name  # solo el nombre, sin prefijo de ruta

        layer_issues = validate_layer(
            expediente_path=expediente_path,
            layer_name=layer_name,
            layer_file=layer_file,
            schema_file=schema_file,
            schema_dir=schema_dir,
        )
        result.issues.extend(layer_issues)

    return result
