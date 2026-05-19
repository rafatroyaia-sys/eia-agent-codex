"""
object_gate_validator -- OB-02
Valida si un ObjectScope (OB-01) tiene información suficiente para considerar
cerrado el Gate 2 (objeto evaluado).

No usa IA. No escribe nada. No resuelve contradicciones.
No consulta Catastro. No genera fichas.

Uso:
    from eia_agent.core.object_gate_validator import evaluate_gate_2

    result = evaluate_gate_2(scope, test_mode=True)
    print(result.summary())
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.object_scope_builder import ObjectScope, load_object_scope_json


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_HIGH_CRITICAL_RE = re.compile(
    r'\b(ALTA|CR[IÍ]TICA|CRITICA|BLOQUEANTE|CRITICAL)\b',
    re.IGNORECASE,
)

_RC_RE = re.compile(r'^[A-Z0-9]{20}$', re.IGNORECASE)

_PROVISIONAL_RE = re.compile(
    r'\b(PENDIENTE|ESTIMADO|NO_DECLARADO|NO\s+DECLARADO)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ObjectGateIssue:
    """Incidencia detectada durante la validación del Gate 2."""
    severity: str                    # ERROR / WARNING / INFO
    code: str
    message: str
    field: str | None = None
    recommendation: str | None = None


@dataclass
class ObjectGateResult:
    """Resultado completo de la validación del Gate 2."""
    expediente_id: str
    passed: bool
    test_mode: bool
    issues: list[ObjectGateIssue] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_blocked(self) -> bool:
        return not self.passed

    def summary(self) -> str:
        status = "APTO" if self.passed else "BLOQUEADO"
        mode = "TEST" if self.test_mode else "PRODUCCIÓN"
        lines = [
            f"Gate 2 [{mode}] — {self.expediente_id}: {status}",
            f"  Errores: {self.error_count()} | "
            f"Avisos: {self.warning_count()} | "
            f"Info: {self.info_count()}",
        ]
        for issue in self.issues:
            field_str = f" [{issue.field}]" if issue.field else ""
            lines.append(f"  [{issue.severity}]{field_str} {issue.code}: {issue.message}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def looks_like_referencia_catastral(value: str) -> bool:
    """Valida patrón básico de RC española: 20 caracteres alfanuméricos.

    No consulta Catastro. Solo verifica formato superficial.
    """
    return bool(_RC_RE.match(value.strip()))


def contains_high_or_critical_gap(text: str) -> bool:
    """Detecta texto con términos de criticidad alta: ALTA, CRÍTICA, BLOQUEANTE, CRITICAL."""
    return bool(_HIGH_CRITICAL_RE.search(text))


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def evaluate_gate_2(
    scope: ObjectScope,
    test_mode: bool = True,
    context: Optional[dict] = None,
) -> ObjectGateResult:
    """Evalúa si el ObjectScope tiene información suficiente para el Gate 2.

    Args:
        scope:      ObjectScope generado por build_object_scope() (OB-01).
        test_mode:  True  = modo test: warnings no bloquean, AT activos no bloquean.
                    False = modo producción: más restricciones.
        context:    Dict opcional con claves:
                    - rc_verificada (bool): si la RC ha sido verificada contra Catastro.
                    - cont_abiertos (bool): si hay contradicciones abiertas.
                    - uso_catastral (str): uso según Catastro.
                    - uso_declarado (str): uso declarado por el promotor.

    Returns:
        ObjectGateResult con passed=True solo si no hay ningún ERROR.
    """
    ctx = context or {}
    issues: list[ObjectGateIssue] = []

    # ------------------------------------------------------------------
    # 1. Titular / promotor
    # ------------------------------------------------------------------
    if not scope.titular:
        issues.append(ObjectGateIssue(
            severity="ERROR",
            code="OB02-E001",
            message="Falta titular/promotor. El Gate 2 requiere identificación del promotor.",
            field="titular",
            recommendation="Proporcionar nombre del titular via documento fuente u override.",
        ))
    else:
        titular_gap = any(
            ("titular" in g.lower() or "promotor" in g.lower())
            for g in scope.gaps
        )
        if titular_gap:
            sev = "WARNING" if test_mode else "ERROR"
            issues.append(ObjectGateIssue(
                severity=sev,
                code="OB02-W001",
                message="Gap de titularidad detectado en scope.gaps.",
                field="titular",
                recommendation="Verificar y confirmar identidad del titular antes de tramitar.",
            ))

    # ------------------------------------------------------------------
    # 2. Referencia catastral
    # ------------------------------------------------------------------
    if not scope.referencia_catastral:
        issues.append(ObjectGateIssue(
            severity="ERROR",
            code="OB02-E002",
            message="Falta referencia catastral.",
            field="referencia_catastral",
            recommendation="Proporcionar RC de 20 caracteres alfanuméricos.",
        ))
    else:
        if not looks_like_referencia_catastral(scope.referencia_catastral):
            issues.append(ObjectGateIssue(
                severity="ERROR",
                code="OB02-E003",
                message=(
                    f"Referencia catastral con formato inválido: "
                    f"'{scope.referencia_catastral}'."
                ),
                field="referencia_catastral",
                recommendation="La RC española tiene exactamente 20 caracteres alfanuméricos.",
            ))
        elif ctx.get("rc_verificada") is False:
            sev = "WARNING" if test_mode else "ERROR"
            issues.append(ObjectGateIssue(
                severity=sev,
                code="OB02-W002",
                message="Referencia catastral declarada pero no verificada contra Catastro.",
                field="referencia_catastral",
                recommendation="Verificar RC en Sede Electrónica del Catastro.",
            ))

    # ------------------------------------------------------------------
    # 3. Coordenadas
    # ------------------------------------------------------------------
    tiene_coords = bool(scope.coordenadas_wgs84 or scope.coordenadas_utm)
    if not tiene_coords:
        issues.append(ObjectGateIssue(
            severity="ERROR",
            code="OB02-E004",
            message="Faltan coordenadas (ni WGS84 ni UTM).",
            field="coordenadas_wgs84",
            recommendation="Proporcionar al menos un sistema de coordenadas geográficas.",
        ))
    else:
        all_coords = scope.coordenadas_wgs84 + scope.coordenadas_utm
        for coord in all_coords:
            if _PROVISIONAL_RE.search(coord):
                sev = "WARNING" if test_mode else "ERROR"
                issues.append(ObjectGateIssue(
                    severity=sev,
                    code="OB02-W003",
                    message=f"Coordenada con valor provisional detectada: '{coord}'.",
                    field="coordenadas_wgs84",
                    recommendation="Sustituir por coordenada geográfica real contrastada.",
                ))
                break

    # ------------------------------------------------------------------
    # 4. Operaciones incluidas
    # ------------------------------------------------------------------
    if not scope.operaciones_incluidas:
        issues.append(ObjectGateIssue(
            severity="ERROR",
            code="OB02-E005",
            message="No hay operaciones incluidas en el objeto evaluado.",
            field="operaciones_incluidas",
            recommendation="Declarar al menos una operación R/D incluida.",
        ))

    # ------------------------------------------------------------------
    # 5. Operaciones excluidas y contradicciones
    # ------------------------------------------------------------------
    cont_abiertos = ctx.get("cont_abiertos", False)
    if cont_abiertos and not scope.operaciones_excluidas and not scope.at_activos:
        issues.append(ObjectGateIssue(
            severity="ERROR",
            code="OB02-E006",
            message=(
                "Hay contradicciones abiertas (cont_abiertos=True) sin operaciones "
                "excluidas declaradas ni asunciones de test activas."
            ),
            field="operaciones_excluidas",
            recommendation=(
                "Declarar operaciones excluidas o activar AT para documentar "
                "la contradicción antes de avanzar."
            ),
        ))
    elif scope.operaciones_excluidas:
        issues.append(ObjectGateIssue(
            severity="INFO",
            code="OB02-I001",
            message=(
                f"Operaciones excluidas declaradas: "
                f"{', '.join(scope.operaciones_excluidas)}."
            ),
            field="operaciones_excluidas",
        ))

    # ------------------------------------------------------------------
    # 6. Modo de trabajo
    # ------------------------------------------------------------------
    if scope.modo == "NO_DECLARADO":
        issues.append(ObjectGateIssue(
            severity="ERROR",
            code="OB02-E007",
            message="Modo de trabajo no declarado (NO_DECLARADO).",
            field="modo",
            recommendation="Declarar GABINETE o CAMPO según el alcance del estudio.",
        ))
    elif scope.modo == "GABINETE":
        issues.append(ObjectGateIssue(
            severity="INFO",
            code="OB02-I002",
            message=(
                "Modo GABINETE: el estudio se basa exclusivamente en fuentes documentales."
            ),
            field="modo",
            recommendation=(
                "Verificar que todos los factores ambientales son evaluables "
                "sin prospección de campo."
            ),
        ))

    # ------------------------------------------------------------------
    # 7. Asunciones de test activas
    # ------------------------------------------------------------------
    if scope.at_activos:
        if test_mode:
            issues.append(ObjectGateIssue(
                severity="WARNING",
                code="OB02-W004",
                message=(
                    f"Hay {len(scope.at_activos)} asunción(es) de test activa(s). "
                    "Aceptable en modo test; no apto para tramitación administrativa real."
                ),
                field="at_activos",
                recommendation=(
                    "Sustituir datos de test por datos confirmados antes de tramitar."
                ),
            ))
        else:
            issues.append(ObjectGateIssue(
                severity="ERROR",
                code="OB02-E008",
                message=(
                    f"Hay {len(scope.at_activos)} asunción(es) de test activa(s). "
                    "El expediente no es apto para presentación administrativa real."
                ),
                field="at_activos",
                recommendation=(
                    "Eliminar todas las asunciones de test y confirmar los datos "
                    "con fuentes verificadas antes de tramitar."
                ),
            ))

    # ------------------------------------------------------------------
    # 8. Gaps de criticidad alta
    # ------------------------------------------------------------------
    for gap in scope.gaps:
        if contains_high_or_critical_gap(gap):
            sev = "WARNING" if test_mode else "ERROR"
            issues.append(ObjectGateIssue(
                severity=sev,
                code="OB02-W005" if test_mode else "OB02-E009",
                message=f"Gap de criticidad alta detectado: '{gap}'.",
                field="gaps",
                recommendation=(
                    "Resolver o documentar el gap de criticidad alta antes de avanzar."
                ),
            ))
        else:
            issues.append(ObjectGateIssue(
                severity="INFO",
                code="OB02-I003",
                message=f"Gap identificado: '{gap}'.",
                field="gaps",
            ))

    # ------------------------------------------------------------------
    # 9. Uso catastral vs uso declarado
    # ------------------------------------------------------------------
    uso_catastral = ctx.get("uso_catastral")
    uso_declarado = ctx.get("uso_declarado")
    if (uso_catastral and uso_declarado
            and uso_catastral.strip().lower() != uso_declarado.strip().lower()):
        tiene_cobertura = bool(scope.at_activos) or any(
            ("uso" in g.lower() or "catastral" in g.lower() or "cont" in g.lower())
            for g in scope.gaps
        )
        if tiene_cobertura:
            issues.append(ObjectGateIssue(
                severity="WARNING",
                code="OB02-W006",
                message=(
                    f"Discrepancia entre uso catastral ('{uso_catastral}') y uso declarado "
                    f"('{uso_declarado}'). Cubierta por AT activo o gap documentado."
                ),
                field="referencia_catastral",
                recommendation=(
                    "Verificar que el AT o CONT cubre esta discrepancia explícitamente."
                ),
            ))
        else:
            sev = "WARNING" if test_mode else "ERROR"
            issues.append(ObjectGateIssue(
                severity=sev,
                code="OB02-W007" if test_mode else "OB02-E010",
                message=(
                    f"Discrepancia entre uso catastral ('{uso_catastral}') y uso declarado "
                    f"('{uso_declarado}') sin AT activo ni CONT/gap documentado."
                ),
                field="referencia_catastral",
                recommendation=(
                    "Activar asunción de test o abrir CONT para documentar la discrepancia "
                    "antes de avanzar a fases siguientes."
                ),
            ))

    # ------------------------------------------------------------------
    # 10. Resultado
    # ------------------------------------------------------------------
    passed = all(i.severity != "ERROR" for i in issues)

    return ObjectGateResult(
        expediente_id=scope.expediente_id,
        passed=passed,
        test_mode=test_mode,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# Carga desde JSON
# ---------------------------------------------------------------------------

def evaluate_gate_2_from_json(
    path: "str | Path",
    test_mode: bool = True,
    context: Optional[dict] = None,
) -> ObjectGateResult:
    """Carga un ObjectScope desde JSON y evalúa el Gate 2.

    No escribe nada. Lanza FileNotFoundError si el JSON no existe.
    """
    scope = load_object_scope_json(path)
    return evaluate_gate_2(scope, test_mode=test_mode, context=context)
