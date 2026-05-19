"""
phase4_precheck -- CA-08
Precheck programático de Fase 4: evalúa preparación del expediente para
cartografía y clima.

No genera mapas. No genera climogramas. No llama a APIs externas.
No usa WMS/WMTS. No usa web. No usa IA.
Solo comprueba preparación, riesgos y bloqueos.

Usa phase2_result.json (ObjectScope) como fuente principal.
Fase 3 (triaje normativo) es informativa — su ausencia no bloquea.

Uso:
    from eia_agent.core.phase4_precheck import run_phase4_precheck

    result = run_phase4_precheck("expediente-EIA-2026-RECIMETAL-PARCELA")
    print(result.summary())

    result = run_phase4_precheck(
        "expediente-EIA-2026-RECIMETAL-PARCELA",
        write_outputs=True,
    )
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_REQUIRED_MAPS: list[str] = [
    "MAP-001 situacion general",
    "MAP-002 emplazamiento",
    "MAP-003 parcela/catastro",
    "MAP-004 Red Natura / ENP",
    "MAP-005 usos del suelo",
    "MAP-006 inundabilidad / riesgos fisicos",
]

_REQUIRED_CLIMATE_OUTPUTS: list[str] = [
    "estacion climatica de referencia",
    "tabla climatica mensual",
    "climograma",
    "clasificacion Koppen",
    "riesgos climaticos relevantes",
]

# Regex básico para RC española — 20 caracteres
_RC_PATTERN = re.compile(
    r"^\d{7}[A-Z]{2}\d{4}[A-Z]\d{4}[A-Z]{2}$",
    re.IGNORECASE,
)

# Marcadores de estado poco fiable que pueden aparecer en cadenas de coordenadas
_UNRELIABLE_COORD_MARKERS: frozenset[str] = frozenset({
    "PENDIENTE", "ESTIMADO", "NO_DECLARADO", "PROVISIONAL",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Phase4PrecheckIssue:
    """Issue detectado durante el precheck de Fase 4."""
    severity: str           # ERROR / WARNING / INFO
    code: str
    message: str
    field: str | None = None
    recommendation: str | None = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "recommendation": self.recommendation,
        }


@dataclass
class Phase4PrecheckResult:
    """Resultado completo del precheck de Fase 4.

    ready_for_phase4=True solo si:
    - ready_for_cartography=True
    - ready_for_climate=True
    - error_count() == 0

    Los warnings no bloquean en modo test pero deben resolverse antes
    de presentación administrativa.
    """
    expediente_id: str
    ready_for_cartography: bool
    ready_for_climate: bool
    ready_for_phase4: bool
    coordinates_status: str       # OK / WARNING / ERROR / ABSENT
    rc_status: str                # OK / WARNING / INVALID / ABSENT
    api_keys_status: dict         # {"AEMET_API_KEY": bool, "MAPBOX_TOKEN": bool}
    required_maps: list[str]
    required_climate_outputs: list[str]
    issues: list[Phase4PrecheckIssue]
    warnings: list[str]
    notes: list[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def summary(self) -> str:
        lines = [
            f"Fase 4 Precheck — {self.expediente_id}",
            f"  Cartografia lista     : {'SI' if self.ready_for_cartography else 'NO'}",
            f"  Clima listo           : {'SI' if self.ready_for_climate else 'NO'}",
            f"  Fase 4 lista          : {'SI' if self.ready_for_phase4 else 'NO'}",
            f"  Errores               : {self.error_count()}",
            f"  Avisos                : {self.warning_count()}",
            f"  Info                  : {self.info_count()}",
            f"  Coordenadas           : {self.coordinates_status}",
            f"  Ref. Catastral        : {self.rc_status}",
        ]
        for key in sorted(self.api_keys_status):
            present = self.api_keys_status[key]
            lines.append(f"  {key:<22}: {'PRESENTE' if present else 'AUSENTE'}")
        if self.issues:
            lines.append("  Issues:")
            for issue in self.issues[:5]:
                lines.append(f"    [{issue.severity}] {issue.code}: {issue.message}")
            if len(self.issues) > 5:
                lines.append(f"    ... y {len(self.issues) - 5} issue(s) mas")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "ready_for_cartography": self.ready_for_cartography,
            "ready_for_climate": self.ready_for_climate,
            "ready_for_phase4": self.ready_for_phase4,
            "coordinates_status": self.coordinates_status,
            "rc_status": self.rc_status,
            "api_keys_status": dict(self.api_keys_status),
            "required_maps": list(self.required_maps),
            "required_climate_outputs": list(self.required_climate_outputs),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_api_keys() -> dict[str, bool]:
    """Lee variables de entorno de API. No las valida, solo comprueba presencia."""
    return {
        "AEMET_API_KEY": bool(os.environ.get("AEMET_API_KEY", "").strip()),
        "MAPBOX_TOKEN": bool(os.environ.get("MAPBOX_TOKEN", "").strip()),
    }


def _looks_like_rc(value: str) -> bool:
    """Comprueba si una cadena tiene el formato estándar de RC española (20 chars)."""
    return bool(_RC_PATTERN.match(value.strip()))


def _parse_wgs84_coord(coord_str: str) -> tuple[float, float] | None:
    """Intenta parsear 'lat, lon' de una cadena WGS84. Devuelve None si falla."""
    parts = coord_str.replace(" ", "").split(",")
    if len(parts) >= 2:
        try:
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return None


def _check_coordinates(
    object_scope: dict,
    issues: list[Phase4PrecheckIssue],
    warnings: list[str],
) -> tuple[bool, str]:
    """Evalúa coordenadas del ObjectScope. Devuelve (has_location, status)."""
    coords_wgs84: list = object_scope.get("coordenadas_wgs84") or []
    coords_utm: list = object_scope.get("coordenadas_utm") or []

    if not coords_wgs84 and not coords_utm:
        issues.append(Phase4PrecheckIssue(
            severity="ERROR",
            code="P4-E001",
            message=(
                "No se han encontrado coordenadas (WGS84 ni UTM) en el ObjectScope. "
                "Sin coordenadas no es posible generar cartografia ni localizar la "
                "estacion climatica."
            ),
            field="coordenadas_wgs84",
            recommendation=(
                "Ejecute Fase 2 y declare las coordenadas del emplazamiento. "
                "Formato WGS84 esperado: 'latitud, longitud' (ej. '28.1, -15.4')."
            ),
        ))
        return False, "ABSENT"

    # Comprobar si alguna coordenada contiene marcadores de estado poco fiable
    all_coord_text = " ".join(str(c) for c in coords_wgs84 + coords_utm).upper()
    for marker in _UNRELIABLE_COORD_MARKERS:
        if marker in all_coord_text:
            issues.append(Phase4PrecheckIssue(
                severity="WARNING",
                code="P4-W001",
                message=(
                    f"Coordenadas contienen marcador de estado no confirmado: '{marker}'. "
                    "Los datos no estan verificados con el promotor ni con Catastro."
                ),
                field="coordenadas_wgs84",
                recommendation=(
                    "Confirme las coordenadas antes de generar cartografia definitiva. "
                    "Sustituyalas por valores numericos contrastados."
                ),
            ))
            warnings.append(
                f"Coordenadas con estado '{marker}' — verificar antes de generar mapas."
            )
            return True, "WARNING"

    # Comprobar formato de coordenadas WGS84
    if coords_wgs84:
        bad = [c for c in coords_wgs84 if _parse_wgs84_coord(str(c)) is None]
        if bad:
            issues.append(Phase4PrecheckIssue(
                severity="WARNING",
                code="P4-W002",
                message=(
                    f"Coordenadas WGS84 con formato no reconocido: {bad[:3]}. "
                    "No se podra calcular el bounding box para los mapas."
                ),
                field="coordenadas_wgs84",
                recommendation=(
                    "Formato esperado: 'latitud, longitud' (ej. '28.1, -15.4'). "
                    "Corrija las coordenadas en el ObjectScope via overrides de Fase 2."
                ),
            ))
            warnings.append(
                f"Coordenadas WGS84 con formato no estandar: {bad[:2]}"
            )
            return True, "WARNING"

    return True, "OK"


def _check_rc(
    object_scope: dict,
    issues: list[Phase4PrecheckIssue],
    warnings: list[str],
) -> str:
    """Evalúa la referencia catastral. Devuelve el status."""
    rc = (object_scope.get("referencia_catastral") or "").strip()

    if not rc:
        issues.append(Phase4PrecheckIssue(
            severity="WARNING",
            code="P4-W003",
            message=(
                "No hay referencia catastral en el ObjectScope. "
                "MAP-003 (parcela/catastro) no podra generarse sin ella."
            ),
            field="referencia_catastral",
            recommendation=(
                "Obtenga la RC del promotor o consultela en la sede electronica "
                "del Catastro. Declarela en Fase 2 via override."
            ),
        ))
        warnings.append("Referencia catastral ausente — MAP-003 requiere RC valida.")
        return "ABSENT"

    if not _looks_like_rc(rc):
        issues.append(Phase4PrecheckIssue(
            severity="ERROR",
            code="P4-E002",
            message=(
                f"Referencia catastral con formato invalido: '{rc}'. "
                "El formato esperado es de 20 caracteres alfanumericos."
            ),
            field="referencia_catastral",
            recommendation=(
                "Ejemplo de RC valida: '1234567AB1234A0001LP'. "
                "Verifiquela en la sede electronica del Catastro "
                "(https://www.catastro.minhap.es)."
            ),
        ))
        return "INVALID"

    return "OK"


def _check_api_keys_issues(
    api_keys: dict[str, bool],
    issues: list[Phase4PrecheckIssue],
    warnings: list[str],
) -> None:
    """Genera WARNINGs (nunca ERRORs) por claves API ausentes."""
    if not api_keys.get("AEMET_API_KEY"):
        issues.append(Phase4PrecheckIssue(
            severity="WARNING",
            code="P4-W004",
            message=(
                "Variable de entorno AEMET_API_KEY no encontrada. "
                "La descarga automatica de normales climatologicas no estara disponible."
            ),
            field="AEMET_API_KEY",
            recommendation=(
                "Configure AEMET_API_KEY en el archivo .env del proyecto. "
                "Sin ella, los datos climaticos deberan introducirse manualmente "
                "o usar una fuente climatica alternativa documentada."
            ),
        ))
        warnings.append(
            "AEMET_API_KEY ausente — normales climatologicas no descargables automaticamente."
        )

    if not api_keys.get("MAPBOX_TOKEN"):
        issues.append(Phase4PrecheckIssue(
            severity="WARNING",
            code="P4-W005",
            message=(
                "Variable de entorno MAPBOX_TOKEN no encontrada. "
                "Se usaran servicios WMS/WMTS oficiales para fondos de mapa."
            ),
            field="MAPBOX_TOKEN",
            recommendation=(
                "Configure MAPBOX_TOKEN en .env para acceso a tiles de mapa de fondo. "
                "Alternativa: GRAFCAN WMS, MITECO WMS, IDECanarias — todos publicos "
                "y gratuitos para uso administrativo."
            ),
        ))
        warnings.append(
            "MAPBOX_TOKEN ausente — se usaran WMS/WMTS oficiales para fondos de mapa."
        )


def _check_phase3_available(
    phase3_result_path: Path | None,
    exp_path: Path,
    output_dir: str,
    issues: list[Phase4PrecheckIssue],
    notes: list[str],
) -> None:
    """Comprueba disponibilidad del triaje normativo de Fase 3. Solo informativo."""
    p3_path = (
        phase3_result_path
        if phase3_result_path is not None
        else exp_path / output_dir / "phase3_result.json"
    )
    if not p3_path.exists():
        issues.append(Phase4PrecheckIssue(
            severity="INFO",
            code="P4-I001",
            message=(
                "phase3_result.json no encontrado. El triaje normativo no esta "
                "disponible para enriquecer las fichas de inventario ambiental."
            ),
            field=None,
            recommendation=(
                "Ejecute Fase 3 antes de Fase 4:\n"
                "  python run_expediente.py <exp> phase3 --write"
            ),
        ))
        notes.append("Triaje normativo (Fase 3) no disponible — ejecute phase3 --write.")


# ---------------------------------------------------------------------------
# Escritura opcional
# ---------------------------------------------------------------------------

def _build_phase4_precheck_md(result: Phase4PrecheckResult) -> str:
    """Genera el informe de precheck en Markdown."""
    hoy = date.today().isoformat()

    def _yn(b: bool) -> str:
        return "LISTO" if b else "NO LISTO"

    lines = [
        "# Precheck Fase 4 — Cartografia y Clima",
        "",
        f"**Expediente**: {result.expediente_id}",
        f"**Fecha de precheck**: {hoy}",
        "",
        "> PRECHECK AUTOMATICO. No genera mapas ni climogramas.",
        "> No llama a APIs externas. Solo evalua preparacion.",
        "",
        "---",
        "",
        "## 1. Estado de preparacion",
        "",
        "| Componente | Estado |",
        "|------------|--------|",
        f"| Cartografia | {_yn(result.ready_for_cartography)} |",
        f"| Clima | {_yn(result.ready_for_climate)} |",
        f"| Fase 4 global | {_yn(result.ready_for_phase4)} |",
        "",
        f"Errores: {result.error_count()} | Avisos: {result.warning_count()} "
        f"| Info: {result.info_count()}",
        "",
        "---",
        "",
        "## 2. Datos geograficos",
        "",
        f"- **Coordenadas**: {result.coordinates_status}",
        f"- **Referencia catastral**: {result.rc_status}",
        "",
        "---",
        "",
        "## 3. Variables de entorno",
        "",
    ]
    for key in sorted(result.api_keys_status):
        present = result.api_keys_status[key]
        lines.append(f"- **{key}**: {'PRESENTE' if present else 'AUSENTE'}")
    lines += [
        "",
        "---",
        "",
        "## 4. Issues",
        "",
    ]
    if result.issues:
        lines += ["| Severidad | Codigo | Mensaje |", "|-----------|--------|---------|"]
        for issue in result.issues:
            msg = issue.message[:80].replace("|", "/")
            lines.append(f"| {issue.severity} | {issue.code} | {msg} |")
        lines.append("")
        lines.append("### Detalle")
        for issue in result.issues:
            lines += [
                "",
                f"#### [{issue.severity}] {issue.code}",
                "",
                f"- **Mensaje**: {issue.message}",
            ]
            if issue.field:
                lines.append(f"- **Campo**: {issue.field}")
            if issue.recommendation:
                lines.append(f"- **Recomendacion**: {issue.recommendation}")
    else:
        lines.append("Sin issues.")
    lines += [
        "",
        "---",
        "",
        "## 5. Mapas minimos requeridos",
        "",
    ]
    for m in result.required_maps:
        lines.append(f"- {m}")
    lines += [
        "",
        "---",
        "",
        "## 6. Salidas climaticas requeridas",
        "",
    ]
    for c in result.required_climate_outputs:
        lines.append(f"- {c}")
    lines.append("")
    if result.warnings:
        lines += ["---", "", "## 7. Avisos del pipeline", ""]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")
    if result.notes:
        lines += ["---", "", "## 8. Notas operativas", ""]
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines)


def _write_phase4_outputs(result: Phase4PrecheckResult, output_dir: Path) -> tuple[Path, Path]:
    """Escribe phase4_precheck.json y phase4_precheck.md en output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "phase4_precheck.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    md_path = output_dir / "phase4_precheck.md"
    md_path.write_text(_build_phase4_precheck_md(result), encoding="utf-8")

    return json_path, md_path


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def run_phase4_precheck(
    expediente_path: "str | Path",
    phase2_result_path: "str | Path | None" = None,
    phase3_result_path: "str | Path | None" = None,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
) -> Phase4PrecheckResult:
    """Ejecuta el precheck de Fase 4: cartografia y clima.

    No genera mapas. No genera climogramas. No llama a APIs externas.

    Args:
        expediente_path:    Ruta al directorio del expediente.
        phase2_result_path: Ruta explícita a phase2_result.json. Si None,
                            busca en control_interno/phase2_result.json.
                            Si no existe: ERROR P4-E005, ObjectScope vacío.
        phase3_result_path: Ruta explícita a phase3_result.json. Si None,
                            busca en control_interno/phase3_result.json.
                            Opcional — solo comprobación informativa.
        write_outputs:      Si True, escribe phase4_precheck.json y
                            phase4_precheck.md en output_dir.
        output_dir:         Subdirectorio relativo al expediente (default
                            "control_interno").

    Returns:
        Phase4PrecheckResult con estado de preparación, issues y recomendaciones.
    """
    exp_path = Path(expediente_path)
    expediente_id = exp_path.name
    issues: list[Phase4PrecheckIssue] = []
    warnings: list[str] = []
    notes: list[str] = []

    # 1. Cargar phase2_result.json (fuente principal)
    p2_path = (
        Path(phase2_result_path)
        if phase2_result_path is not None
        else exp_path / output_dir / "phase2_result.json"
    )
    object_scope: dict = {}
    phase2_loaded = False

    if p2_path.exists():
        try:
            with open(p2_path, encoding="utf-8") as f:
                phase2_data = json.load(f)
            object_scope = phase2_data.get("object_scope") or {}
            phase2_loaded = True
            if phase2_data.get("warnings"):
                warnings.extend(f"[Fase 2] {w}" for w in phase2_data["warnings"])
        except json.JSONDecodeError as exc:
            issues.append(Phase4PrecheckIssue(
                severity="ERROR",
                code="P4-E004",
                message=f"phase2_result.json con JSON invalido: {exc}",
                field=None,
                recommendation=(
                    f"Regenere Fase 2: python run_expediente.py {expediente_id} "
                    "phase2 --write"
                ),
            ))
            warnings.append(
                f"phase2_result.json invalido ({exc}); precheck con ObjectScope vacio."
            )
    else:
        issues.append(Phase4PrecheckIssue(
            severity="ERROR",
            code="P4-E005",
            message=(
                "phase2_result.json no encontrado. ObjectScope vacio. "
                "El precheck no puede evaluar coordenadas ni RC."
            ),
            field=None,
            recommendation=(
                f"Ejecute primero Fase 2:\n"
                f"  python run_expediente.py {expediente_id} phase2 --write\n"
                "o pase una ruta explicita via phase2_result_path."
            ),
        ))
        warnings.append(
            "phase2_result.json no encontrado — precheck con datos vacios."
        )

    # 2. Coordenadas y RC (solo si phase2 está cargado)
    if phase2_loaded:
        has_location, coords_status = _check_coordinates(object_scope, issues, warnings)
        rc_status = _check_rc(object_scope, issues, warnings)
    else:
        has_location = False
        coords_status = "ABSENT"
        rc_status = "ABSENT"
        notes.append(
            "Coordenadas y RC no evaluadas — phase2_result.json no disponible."
        )

    # 3. Variables de entorno API (siempre, solo warnings)
    api_keys = _check_api_keys()
    _check_api_keys_issues(api_keys, issues, warnings)

    # 4. Fase 3 disponible (siempre, solo INFO)
    _check_phase3_available(
        Path(phase3_result_path) if phase3_result_path is not None else None,
        exp_path,
        output_dir,
        issues,
        notes,
    )

    # 5. Determinar readiness
    # ready_for_cartography: necesita ubicación geográfica sin errores de coords
    coord_blocking = sum(
        1 for i in issues
        if i.severity == "ERROR" and i.code == "P4-E001"
    )
    ready_for_cartography = has_location and coord_blocking == 0

    # ready_for_climate: misma dependencia que cartografía (necesita coords)
    ready_for_climate = has_location

    # ready_for_phase4: ambas ready + cero errores globales
    n_errors = sum(1 for i in issues if i.severity == "ERROR")
    ready_for_phase4 = ready_for_cartography and ready_for_climate and n_errors == 0

    result = Phase4PrecheckResult(
        expediente_id=expediente_id,
        ready_for_cartography=ready_for_cartography,
        ready_for_climate=ready_for_climate,
        ready_for_phase4=ready_for_phase4,
        coordinates_status=coords_status,
        rc_status=rc_status,
        api_keys_status=api_keys,
        required_maps=list(_REQUIRED_MAPS),
        required_climate_outputs=list(_REQUIRED_CLIMATE_OUTPUTS),
        issues=issues,
        warnings=warnings,
        notes=notes,
    )

    if write_outputs:
        _write_phase4_outputs(result, exp_path / output_dir)

    return result
