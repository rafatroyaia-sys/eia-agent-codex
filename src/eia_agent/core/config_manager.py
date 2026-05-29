"""
config_manager.py — BE-04
Gestión segura de configuración local y API keys.

Documenta variables de entorno, valida presencia, detecta placeholders,
escanea secretos potenciales en el repositorio. Todo offline.

No valida claves contra APIs externas.
No almacena secretos.
No imprime valores reales.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CONFIG_STATUS: Dict[str, str] = {
    "OK": "Configuración válida sin incidencias.",
    "CON_OBSERVACIONES": "Configuración válida con advertencias.",
    "NO_CONFORME": "Configuración con errores bloqueantes.",
    "SIN_DATOS": "Sin variables de entorno ni .env detectados.",
}

CONFIG_SEVERITY: Dict[str, str] = {
    "ERROR": "Error bloqueante.",
    "WARNING": "Advertencia no bloqueante.",
    "INFO": "Información.",
}

KNOWN_ENV_VARS: List[str] = [
    "AEMET_API_KEY",
    "MAPBOX_TOKEN",
    "OPENAI_API_KEY",
    "EIA_ENV",
]

SENSITIVE_ENV_VARS: set = {
    "AEMET_API_KEY",
    "MAPBOX_TOKEN",
    "OPENAI_API_KEY",
}

PLACEHOLDER_VALUES: set = {
    "",
    "change_me",
    "todo",
    "your_api_key",
    "your_token",
    "xxx",
    "xxxxx",
    "sk-...",
    "pendiente",
    "none",
    "null",
}

# Backward-compatible: incluye local/ci del .env.example existente
ALLOWED_EIA_ENV: set = {"local", "dev", "ci", "test", "prod"}

# Dirs excluidos por defecto en escaneo de repo
_DEFAULT_EXCLUDE_DIRS: set = {
    ".git", "venv", "env", ".venv", "tmp", "temp",
    "__pycache__", ".pytest_cache", ".tox", "node_modules",
    "dist", "build", ".mypy_cache", ".ruff_cache",
}

# Extensiones de texto a escanear
_TEXT_EXTENSIONS: set = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".env", ".sh", ".bat",
    ".rst", ".html", ".xml", ".js", ".ts", ".css",
}

# Patrones de detección de secretos — (compiled_re, descripcion_tipo)
_SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "posible clave OpenAI sk-..."),
    (re.compile(r"\bpk\.[A-Za-z0-9_\-]{20,}"), "posible token Mapbox pk."),
    (re.compile(r"\bsk\.[A-Za-z0-9_\-]{20,}"), "posible token Mapbox sk."),
    (
        re.compile(
            r"[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"
        ),
        "posible JWT (header.payload.signature)",
    ),
    (
        re.compile(r"(?i)api[_\-]?key\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?"),
        "posible valor api_key",
    ),
    (
        re.compile(r"(?i)Authorization\s*:\s*Bearer\s+([A-Za-z0-9_\-\.]{20,})"),
        "posible Bearer token",
    ),
    (
        re.compile(r"(?i)token\s*[=:]\s*['\"]?([A-Za-z0-9_\-\.]{24,})['\"]?"),
        "posible valor token",
    ),
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ConfigIssue:
    severity: str
    code: str
    variable: Optional[str]
    message: str
    recommendation: str
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "variable": self.variable,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }

    def summary(self) -> str:
        var_part = f" [{self.variable}]" if self.variable else ""
        return f"[{self.severity}] {self.code}{var_part}: {self.message}"


@dataclass
class EnvVarStatus:
    name: str
    present: bool
    is_sensitive: bool
    is_placeholder: bool
    masked_value: Optional[str]
    source: str
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "present": self.present,
            "is_sensitive": self.is_sensitive,
            "is_placeholder": self.is_placeholder,
            "masked_value": self.masked_value,
            "source": self.source,
            "warnings": self.warnings,
            "notes": self.notes,
        }

    def summary(self) -> str:
        if not self.present:
            return f"{self.name}: ausente (source={self.source})"
        ph = " [PLACEHOLDER]" if self.is_placeholder else ""
        return f"{self.name}: {self.masked_value}{ph} (source={self.source})"


@dataclass
class ConfigValidationResult:
    status: str
    env_vars: List[EnvVarStatus] = field(default_factory=list)
    issues: List[ConfigIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "env_vars": [v.to_dict() for v in self.env_vars],
            "issues": [i.to_dict() for i in self.issues],
            "warnings": self.warnings,
            "notes": self.notes,
        }

    def summary(self) -> str:
        lines = [
            f"Config  : {self.status}",
            f"Vars    : {len(self.env_vars)} revisadas, "
            f"{sum(1 for v in self.env_vars if v.present)} presentes",
            f"Errores : {self.error_count()}",
            f"Avisos  : {self.warning_count()}",
            f"Info    : {self.info_count()}",
        ]
        for n in self.notes:
            lines.append(f"  [NOTA] {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones utilitarias
# ---------------------------------------------------------------------------

def mask_secret(value: Optional[str]) -> Optional[str]:
    """Enmascara un valor sensible. Nunca devuelve el valor real completo."""
    if value is None:
        return None
    if len(value) <= 8:
        return "****"
    return value[:4] + "..." + value[-4:]


def is_placeholder_value(value: Optional[str]) -> bool:
    """Detecta valores que son placeholders, no credenciales reales."""
    if value is None:
        return True
    v = value.strip().lower()
    if not v:
        return True
    if v in PLACEHOLDER_VALUES:
        return True
    # Patrones compuestos solo por x, *, puntos, guiones
    if re.fullmatch(r"[x\*\.\-]{3,}", v):
        return True
    # Contiene frases típicas de placeholder
    placeholder_phrases = [
        "your_api_key", "your_token", "change_me",
        "insert_here", "api_key_here", "replace_me",
        "your_key_here", "your_secret",
    ]
    for phrase in placeholder_phrases:
        if phrase in v:
            return True
    return False


def load_dotenv_file(path) -> Dict[str, str]:
    """
    Carga pares KEY=VALUE de un archivo .env.
    Ignora comentarios y líneas vacías.
    Devuelve {} si el archivo no existe o no es legible.
    """
    result: Dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, _, val = stripped.partition("=")
                key = key.strip()
                val = val.strip()
                # Eliminar comillas simples o dobles
                if len(val) >= 2:
                    if (val[0] == '"' and val[-1] == '"') or \
                       (val[0] == "'" and val[-1] == "'"):
                        val = val[1:-1]
                if key:
                    result[key] = val
    except (OSError, IOError):
        pass
    return result


def read_env_var_status(
    name: str,
    env: Optional[Dict[str, str]] = None,
    dotenv_values: Optional[Dict[str, str]] = None,
) -> EnvVarStatus:
    """
    Lee el estado de una variable de entorno.
    Prioridad: env (sistema) → dotenv_values → ausente.
    masked_value nunca expone el valor real completo.
    """
    if env is None:
        env = {}
    if dotenv_values is None:
        dotenv_values = {}

    is_sensitive = name in SENSITIVE_ENV_VARS
    value: Optional[str] = None
    source: str = "missing"

    if name in env:
        value = env[name]
        source = "environment"
    elif name in dotenv_values:
        value = dotenv_values[name]
        source = ".env"

    present = value is not None
    ph = is_placeholder_value(value) if present else False
    masked = mask_secret(value) if (present and is_sensitive) else (value if present else None)

    warnings: List[str] = []
    notes: List[str] = []

    if present and ph:
        warnings.append(f"{name} tiene valor placeholder.")

    return EnvVarStatus(
        name=name,
        present=present,
        is_sensitive=is_sensitive,
        is_placeholder=ph,
        masked_value=masked,
        source=source,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Validación de configuración
# ---------------------------------------------------------------------------

def validate_config(
    required_vars: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    dotenv_path=None,
    allow_missing_optional: bool = True,
) -> ConfigValidationResult:
    """
    Valida las variables de entorno conocidas.

    required_vars: nombres de variables obligatorias (ausencia → ERROR).
    env: dict de entorno (por defecto os.environ).
    dotenv_path: ruta a .env local para leer adicionalmente.
    allow_missing_optional: si True, variables opcionales ausentes generan INFO.
    """
    if env is None:
        env = dict(os.environ)

    dotenv_values: Dict[str, str] = {}
    if dotenv_path is not None:
        dotenv_values = load_dotenv_file(dotenv_path)

    required_set: set = set(required_vars) if required_vars else set()

    env_var_statuses: List[EnvVarStatus] = []
    issues: List[ConfigIssue] = []
    warnings: List[str] = []
    notes: List[str] = []

    for name in KNOWN_ENV_VARS:
        status = read_env_var_status(name, env=env, dotenv_values=dotenv_values)
        env_var_statuses.append(status)

        is_required = name in required_set

        if not status.present:
            if is_required:
                issues.append(ConfigIssue(
                    severity="ERROR",
                    code="BE04-E001",
                    variable=name,
                    message=f"Variable obligatoria {name} no está configurada.",
                    recommendation=(
                        f"Configure {name} en .env o como variable de entorno del sistema."
                    ),
                    evidence=[f"source: {status.source}"],
                ))
            elif not allow_missing_optional:
                issues.append(ConfigIssue(
                    severity="WARNING",
                    code="BE04-W001",
                    variable=name,
                    message=f"Variable opcional {name} no está configurada.",
                    recommendation=f"Configure {name} si necesita este servicio.",
                    evidence=[f"source: {status.source}"],
                ))
            else:
                issues.append(ConfigIssue(
                    severity="INFO",
                    code="BE04-I001",
                    variable=name,
                    message=(
                        f"Variable opcional {name} no configurada "
                        "(no requerida para el pipeline offline)."
                    ),
                    recommendation=f"Configure {name} si va a utilizar el servicio asociado.",
                    evidence=[f"source: {status.source}"],
                ))
        else:
            if status.is_placeholder:
                sev = "ERROR" if is_required else "WARNING"
                code = "BE04-E002" if is_required else "BE04-W002"
                issues.append(ConfigIssue(
                    severity=sev,
                    code=code,
                    variable=name,
                    message=(
                        f"Variable {'obligatoria' if is_required else 'opcional'} "
                        f"{name} tiene valor placeholder."
                    ),
                    recommendation=(
                        f"Sustituya el placeholder por el valor real de {name}."
                    ),
                    evidence=[f"source: {status.source}", "valor: placeholder detectado"],
                ))

    # Validación específica de EIA_ENV (no enmascarado, no sensible)
    eia_env_status = next((s for s in env_var_statuses if s.name == "EIA_ENV"), None)
    if eia_env_status and eia_env_status.present and not eia_env_status.is_placeholder:
        actual_eia_env = (env.get("EIA_ENV") or dotenv_values.get("EIA_ENV", "")).strip()
        if actual_eia_env.lower() not in {v.lower() for v in ALLOWED_EIA_ENV}:
            issues.append(ConfigIssue(
                severity="WARNING",
                code="BE04-W003",
                variable="EIA_ENV",
                message=(
                    f"EIA_ENV tiene valor no reconocido. "
                    f"Use uno de: {', '.join(sorted(ALLOWED_EIA_ENV))}."
                ),
                recommendation=(
                    f"Cambie EIA_ENV a uno de los valores válidos: "
                    f"{', '.join(sorted(ALLOWED_EIA_ENV))}."
                ),
                evidence=[
                    f"valor actual: {actual_eia_env}",
                    f"valores permitidos: {', '.join(sorted(ALLOWED_EIA_ENV))}",
                ],
            ))

    # OPENAI_API_KEY nunca se marca como obligatoria automáticamente
    # (solo si el caller la pasa en required_vars explícitamente)

    # Determinar status global
    has_any_present = any(s.present for s in env_var_statuses)
    has_errors = any(i.severity == "ERROR" for i in issues)
    has_warnings = any(i.severity == "WARNING" for i in issues)

    if has_errors:
        global_status = "NO_CONFORME"
    elif has_warnings:
        global_status = "CON_OBSERVACIONES"
    elif not has_any_present and not dotenv_values:
        global_status = "SIN_DATOS"
    else:
        global_status = "OK"

    # Notas informativas
    if dotenv_path is not None and Path(dotenv_path).exists():
        notes.append(f"Archivo .env leído: {dotenv_path}")
    elif dotenv_path is not None:
        notes.append(f"Archivo .env no encontrado: {dotenv_path}")

    present_count = sum(1 for s in env_var_statuses if s.present)
    notes.append(
        f"{present_count}/{len(KNOWN_ENV_VARS)} variables presentes. "
        "OPENAI_API_KEY no es obligatoria para el pipeline offline."
    )

    return ConfigValidationResult(
        status=global_status,
        env_vars=env_var_statuses,
        issues=issues,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Informe Markdown
# ---------------------------------------------------------------------------

def build_config_report_markdown(result: ConfigValidationResult) -> str:
    """
    Genera un informe Markdown seguro de la configuración.
    No incluye claves reales. Los valores sensibles aparecen enmascarados.
    """
    lines = [
        "# Informe seguro de configuración",
        "",
        "## 1. Resumen",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Estado | **{result.status}** |",
        f"| Variables revisadas | {len(result.env_vars)} |",
        f"| Presentes | {sum(1 for v in result.env_vars if v.present)} |",
        f"| Errores | {result.error_count()} |",
        f"| Avisos | {result.warning_count()} |",
        f"| Informativas | {result.info_count()} |",
        "",
        "## 2. Variables revisadas",
        "",
        "| Variable | Presente | Sensible | Placeholder | Valor (enmascarado) | Fuente |",
        "|----------|----------|----------|-------------|---------------------|--------|",
    ]

    for v in result.env_vars:
        present_str = "Sí" if v.present else "No"
        sensitive_str = "Sí" if v.is_sensitive else "No"
        ph_str = "Sí" if v.is_placeholder else "No"
        val_str = v.masked_value if v.masked_value is not None else "—"
        lines.append(
            f"| {v.name} | {present_str} | {sensitive_str} "
            f"| {ph_str} | `{val_str}` | {v.source} |"
        )

    lines += [
        "",
        "## 3. Incidencias",
        "",
    ]

    if result.issues:
        for issue in result.issues:
            lines.append(f"### {issue.code} — {issue.severity}")
            lines.append("")
            if issue.variable:
                lines.append(f"**Variable:** `{issue.variable}`")
                lines.append("")
            lines.append(f"**Mensaje:** {issue.message}")
            lines.append("")
            lines.append(f"**Recomendación:** {issue.recommendation}")
            if issue.evidence:
                lines.append("")
                lines.append("**Evidencia:**")
                for ev in issue.evidence:
                    lines.append(f"- {ev}")
            lines.append("")
    else:
        lines.append("Sin incidencias.")
        lines.append("")

    lines += [
        "## 4. Recomendaciones",
        "",
        "1. Copie `.env.example` como `.env` y rellene sus claves reales.",
        "2. Añada `.env` a `.gitignore` — nunca lo suba al repositorio.",
        "3. Compruebe periódicamente que `.claude/settings.local.json` "
        "no contiene claves reales.",
        "4. AEMET_API_KEY y MAPBOX_TOKEN solo son necesarias para módulos online "
        "(Fase 4 con datos reales).",
        "5. OPENAI_API_KEY no es requerida para el pipeline offline de EIA-Agent.",
        "",
        "## 5. Advertencia de seguridad",
        "",
        "> **Este informe no muestra claves reales. "
        "Los valores sensibles aparecen enmascarados.**",
        "> No comparta este informe si contiene fragmentos de claves, aunque estén parcialmente enmascarados.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_config_validation_outputs(
    result: ConfigValidationResult,
    output_dir,
) -> tuple:
    """
    Escribe config_validation_result.json y config_validation_result.md
    en output_dir. Devuelve (json_path, md_path).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "config_validation_result.json"
    md_path = out / "config_validation_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    md_content = build_config_report_markdown(result)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return json_path, md_path


# ---------------------------------------------------------------------------
# Escaneo de secretos
# ---------------------------------------------------------------------------

def scan_text_for_potential_secrets(text: str) -> List[str]:
    """
    Detecta patrones sospechosos en texto.
    Devuelve descripciones con el secreto ENMASCARADO — nunca el valor completo.
    """
    findings: List[str] = []
    seen: set = set()

    for pattern, desc in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0)
            # Enmascara el fragmento encontrado
            masked = mask_secret(raw) if raw else "****"
            finding = f"{desc}: {masked}"
            if finding not in seen:
                seen.add(finding)
                findings.append(finding)

    return findings


def scan_file_for_potential_secrets(path) -> List[str]:
    """
    Lee un archivo de texto y busca patrones de secretos.
    Tolera archivos binarios o inexistentes.
    Devuelve hallazgos enmascarados.
    """
    try:
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
        return scan_text_for_potential_secrets(content)
    except (OSError, IOError):
        return []


def scan_repo_for_potential_secrets(
    root_path,
    include_patterns: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
) -> ConfigValidationResult:
    """
    Escanea archivos de texto del repositorio en busca de secretos potenciales.
    Excluye: .git, venv, tmp, __pycache__, .pytest_cache, expediente-EIA-*.
    No incluye el secreto completo en ningún output.
    """
    root = Path(root_path)
    exclude_set = set(exclude_dirs) if exclude_dirs else set()
    exclude_set.update(_DEFAULT_EXCLUDE_DIRS)

    issues: List[ConfigIssue] = []
    notes: List[str] = []
    files_scanned = 0
    files_with_findings = 0

    for file_path in _iter_text_files(root, exclude_set, include_patterns):
        files_scanned += 1
        findings = scan_file_for_potential_secrets(file_path)
        if findings:
            files_with_findings += 1
            rel = _safe_relative(file_path, root)
            for finding in findings:
                issues.append(ConfigIssue(
                    severity="ERROR",
                    code="BE04-E003",
                    variable=None,
                    message=f"Posible secreto en {rel}: {finding}",
                    recommendation=(
                        "Verifique manualmente el archivo. Si contiene credenciales reales, "
                        "retírelas y rote las claves afectadas. "
                        "Añada el archivo a .gitignore si corresponde."
                    ),
                    evidence=[f"archivo: {rel}", f"hallazgo: {finding}"],
                ))

    notes.append(f"Archivos escaneados: {files_scanned}.")
    notes.append(f"Archivos con hallazgos: {files_with_findings}.")
    notes.append(
        "Directorios excluidos: " + ", ".join(sorted(exclude_set)) + "."
    )

    if issues:
        global_status = "NO_CONFORME"
    else:
        global_status = "OK"

    return ConfigValidationResult(
        status=global_status,
        env_vars=[],
        issues=issues,
        warnings=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _iter_text_files(root: Path, exclude_set: set, include_patterns):
    """Itera sobre archivos de texto en root, respetando exclusiones."""
    _expediente_re = re.compile(r"^expediente-EIA-", re.IGNORECASE)

    for item in root.rglob("*"):
        if not item.is_file():
            continue

        # Comprobar si algún componente del path está excluido
        skip = False
        for part in item.relative_to(root).parts[:-1]:
            if part in exclude_set:
                skip = True
                break
            if _expediente_re.match(part):
                skip = True
                break
        if skip:
            continue

        # Extensión
        ext = item.suffix.lower()
        if include_patterns:
            if not any(item.match(p) for p in include_patterns):
                continue
        else:
            if ext not in _TEXT_EXTENSIONS:
                continue

        yield item


def _safe_relative(path: Path, root: Path) -> str:
    """Devuelve ruta relativa de forma segura."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
