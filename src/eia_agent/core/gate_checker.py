"""gate_checker.py -- NL-04
Gate-checker básico para EIA-Agent v2.1.

Evalúa si un expediente cumple las condiciones mínimas de archivos y estado
para avanzar de una fase a la siguiente.

No ejecuta agentes. No modifica archivos. No crea ni completa fases.

Uso:
    from eia_agent.core.gate_checker import GateChecker

    gc = GateChecker("expediente-EIA-2026-RECIMETAL-NAVE-222", test_mode=True)
    result = gc.check_phase("5")
    print(result.summary())
    if result.is_blocked():
        for issue in result.issues:
            if issue.severity == "ERROR":
                print(issue)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.orchestrator_log import OrchestratorLog
from eia_agent.core.schema_validator import validate_expediente


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REQUIRED_LAYERS = [
    "hechos_confirmados.json",
    "inferencias_y_gaps.json",
    "normativa_aplicable.json",
    "cartografia_trace.json",
    "salidas_generadas.json",
    "matriz_trazabilidad.json",
]

REQUIRED_BLOCKS = [
    "00_triaje.md",
    "A_identificacion_y_descripcion.md",
    "B_inventario_ambiental.md",
    "C_impactos.md",
    "D_medidas.md",
    "E_PVA.md",
    "F_alternativas.md",
    "G_vulnerabilidad.md",
    "H_red_natura_2000.md",
    "I_conclusiones.md",
    "J_resumen_no_tecnico.md",
    "K_referencias.md",
]

# Nombre canónico primero; luego alias usados en pilotos anteriores.
REQUIRED_IMPACT_FILES: dict[str, list[str]] = {
    "impactos": ["impactos.json", "identificacion_valoracion_impactos.json"],
    "medidas":  ["medidas.json",  "medidas_correctoras.json"],
    "pva":      ["pva.json"],
}

FINAL_CONCLUSION_KEYWORDS = [
    "CONFORME EN MODO TEST",
    "CON OBSERVACIONES EN MODO TEST",
    "NO CONFORME",
    "CONFORME",
]

_NORMA_VALID_STATES  = {"VERIFICADA", "VERIFICADA ONLINE", "VERIFICADO", "REFERENCIADA"}
_CART_PROVISIONAL    = "PROVISIONAL"
_GAP_OPEN_CRITICIDADES = {"ALTA", "CRITICA"}


# ---------------------------------------------------------------------------
# GateIssue
# ---------------------------------------------------------------------------

@dataclass
class GateIssue:
    """Problema detectado por el gate-checker en un expediente."""
    severity: str            # ERROR / WARNING / INFO
    phase: str
    code: str
    message: str
    path: Optional[str] = None

    def __str__(self) -> str:
        path_str = f" [{self.path}]" if self.path else ""
        return f"[{self.severity}] {self.code}{path_str}: {self.message}"


# ---------------------------------------------------------------------------
# GateResult
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Resultado completo de la evaluación de gate para una fase."""
    expediente_path: Path
    phase: str
    passed: bool
    test_mode: bool
    issues: list[GateIssue] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_blocked(self) -> bool:
        """True si hay al menos un issue de severidad ERROR."""
        return self.error_count() > 0

    def summary(self) -> str:
        estado = "PASSED" if self.passed else "BLOCKED"
        lines = [
            f"Expediente : {self.expediente_path.name}",
            f"Fase       : {self.phase}",
            f"Gate       : {estado}",
            f"Test mode  : {'SI' if self.test_mode else 'NO'}",
            f"Problemas  : {len(self.issues)} "
            f"({self.error_count()} errores, "
            f"{self.warning_count()} avisos, "
            f"{self.info_count()} info)",
        ]
        if self.issues:
            lines.append("")
            for issue in self.issues:
                lines.append(f"  {issue}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# GateChecker
# ---------------------------------------------------------------------------

class GateChecker:
    """Evaluador de condiciones mínimas de fase para EIA-Agent v2.1.

    Lee el expediente sin modificarlo.
    No ejecuta agentes. No crea ni completa fases en el orquestador.

    test_mode=True: condiciones AT/PROVISIONAL/INDETERMINADO producen WARNING.
    test_mode=False: las mismas condiciones producen ERROR en fases finales.
    """

    def __init__(
        self,
        expediente_path: "str | Path",
        test_mode: bool = True,
    ) -> None:
        self.expediente_path = Path(expediente_path).resolve()
        self.test_mode = test_mode
        self.expediente_id = self.expediente_path.name

    # -----------------------------------------------------------------------
    # API principal
    # -----------------------------------------------------------------------

    def check_phase(self, phase: str) -> GateResult:
        """Evalúa si el expediente cumple las condiciones de gate para la fase indicada.

        Ejecuta en orden:
        1. Validación de schemas (NL-02).
        2. Fase anterior completada (orchestrator_state.json).
        3. Errores bloqueantes en OrchestratorLog.
        4. Archivos requeridos por fase.
        5. Condiciones propias de modo test.
        """
        issues: list[GateIssue] = []
        issues += self.check_model_schema()
        issues += self.check_previous_phase_completed(phase)
        issues += self.check_blocking_log_errors()
        issues += self.check_required_files(phase)
        issues += self.check_test_mode_conditions(phase)

        has_errors = any(i.severity == "ERROR" for i in issues)
        return GateResult(
            expediente_path=self.expediente_path,
            phase=phase,
            passed=not has_errors,
            test_mode=self.test_mode,
            issues=issues,
        )

    # -----------------------------------------------------------------------
    # check_model_schema — NL-02
    # -----------------------------------------------------------------------

    def check_model_schema(self) -> list[GateIssue]:
        """Valida el expediente contra los schemas v2.1 (NL-02).

        Los errores de ValidationResult se mapean a GateIssue ERROR.
        Los warnings de ValidationResult se mapean a GateIssue WARNING.
        """
        result = validate_expediente(self.expediente_path)
        issues: list[GateIssue] = []
        for vi in result.issues:
            sev = "ERROR" if vi.severity == "ERROR" else "WARNING"
            issues.append(GateIssue(
                severity=sev,
                phase="schema",
                code=vi.code or "SCHEMA_ERROR",
                message=vi.message,
                path=vi.path,
            ))
        return issues

    # -----------------------------------------------------------------------
    # check_required_files — despacho por fase
    # -----------------------------------------------------------------------

    def check_required_files(self, phase: str) -> list[GateIssue]:
        """Comprueba la existencia y contenido mínimo de los archivos requeridos por fase."""
        dispatch = {
            "1": self._check_files_phase1,
            "2": self._check_files_phase2,
            "3": self._check_files_phase3,
            "4": self._check_files_phase4,
            "5": self._check_files_phase5,
            "6": self._check_files_phase6,
            "7": self._check_files_phase7,
            "8": self._check_files_phase8,
            "9": self._check_files_phase9,
        }
        fn = dispatch.get(phase)
        if fn is None:
            return [GateIssue(
                severity="WARNING",
                phase=phase,
                code="UNKNOWN_PHASE",
                message=f"Fase {phase!r} no reconocida — comprobaciones de archivos omitidas",
            )]
        return fn()

    # -- Fase 1: Ingesta documental --

    def _check_files_phase1(self) -> list[GateIssue]:
        issues = []
        capas_dir = self.expediente_path / "capas"
        for layer in REQUIRED_LAYERS:
            if not (capas_dir / layer).exists():
                issues.append(GateIssue(
                    severity="ERROR", phase="1",
                    code="LAYER_MISSING",
                    message=f"Capa requerida ausente: {layer}",
                    path=f"capas/{layer}",
                ))
        hc = capas_dir / "hechos_confirmados.json"
        if hc.exists():
            data = self._load_json(hc)
            if data is not None and len(data) == 0:
                issues.append(GateIssue(
                    severity="ERROR", phase="1",
                    code="HC_EMPTY",
                    message="hechos_confirmados.json está vacío — la ingesta no ha producido hechos",
                    path="capas/hechos_confirmados.json",
                ))
        return issues

    # -- Fase 2: Objeto evaluado --

    def _check_files_phase2(self) -> list[GateIssue]:
        issues = []
        ficha = self.expediente_path / "control_interno" / "ficha_objeto_evaluado.md"
        if not ficha.exists():
            issues.append(GateIssue(
                severity="ERROR", phase="2",
                code="FICHA_OBJETO_MISSING",
                message="ficha_objeto_evaluado.md no existe — el objeto evaluado no está cerrado",
                path="control_interno/ficha_objeto_evaluado.md",
            ))
        hc = self.expediente_path / "capas" / "hechos_confirmados.json"
        if hc.exists():
            data = self._load_json(hc)
            if data is not None and len(data) == 0:
                issues.append(GateIssue(
                    severity="ERROR", phase="2",
                    code="HC_EMPTY",
                    message="hechos_confirmados.json está vacío",
                    path="capas/hechos_confirmados.json",
                ))
        ig = self.expediente_path / "capas" / "inferencias_y_gaps.json"
        if not ig.exists():
            issues.append(GateIssue(
                severity="ERROR", phase="2",
                code="GAPS_MISSING",
                message="inferencias_y_gaps.json no existe",
                path="capas/inferencias_y_gaps.json",
            ))
        return issues

    # -- Fase 3: Triaje normativo --

    def _check_files_phase3(self) -> list[GateIssue]:
        issues = []
        nota = self.expediente_path / "control_interno" / "nota_encuadre_legal.md"
        if not nota.exists():
            issues.append(GateIssue(
                severity="ERROR", phase="3",
                code="NOTA_LEGAL_MISSING",
                message="nota_encuadre_legal.md no existe — triaje normativo no cerrado",
                path="control_interno/nota_encuadre_legal.md",
            ))
        nm_path = self.expediente_path / "capas" / "normativa_aplicable.json"
        if not nm_path.exists():
            issues.append(GateIssue(
                severity="ERROR", phase="3",
                code="NORMATIVA_MISSING",
                message="normativa_aplicable.json no existe",
                path="capas/normativa_aplicable.json",
            ))
        else:
            data = self._load_json(nm_path)
            if data is not None:
                normas = data if isinstance(data, list) else []
                if not normas:
                    issues.append(GateIssue(
                        severity="ERROR", phase="3",
                        code="NORMATIVA_EMPTY",
                        message="normativa_aplicable.json está vacío",
                        path="capas/normativa_aplicable.json",
                    ))
                else:
                    verificadas = [
                        n for n in normas
                        if n.get("estado", "") in _NORMA_VALID_STATES
                    ]
                    if not verificadas:
                        issues.append(GateIssue(
                            severity="ERROR", phase="3",
                            code="NORMATIVA_SIN_VERIFICAR",
                            message=(
                                "Ninguna norma tiene estado válido "
                                "(esperado: VERIFICADA / VERIFICADA ONLINE / VERIFICADO / REFERENCIADA)"
                            ),
                            path="capas/normativa_aplicable.json",
                        ))
        return issues

    # -- Fase 4: Cartografía y clima --

    def _check_files_phase4(self) -> list[GateIssue]:
        issues = []
        ct_path = self.expediente_path / "capas" / "cartografia_trace.json"
        if not ct_path.exists():
            issues.append(GateIssue(
                severity="ERROR", phase="4",
                code="CARTOGRAFIA_TRACE_MISSING",
                message="cartografia_trace.json no existe",
                path="capas/cartografia_trace.json",
            ))
        else:
            data = self._load_json(ct_path)
            if data is not None:
                entradas = data if isinstance(data, list) else []
                if not entradas:
                    issues.append(GateIssue(
                        severity="ERROR", phase="4",
                        code="CARTOGRAFIA_TRACE_EMPTY",
                        message="cartografia_trace.json está vacío",
                        path="capas/cartografia_trace.json",
                    ))
                else:
                    provisionales = [
                        x for x in entradas if x.get("estado", "") == _CART_PROVISIONAL
                    ]
                    if provisionales:
                        sev = "WARNING" if self.test_mode else "ERROR"
                        issues.append(GateIssue(
                            severity=sev, phase="4",
                            code="CARTOGRAFIA_PROVISIONAL",
                            message=(
                                f"{len(provisionales)} entrada(s) cartográficas en estado PROVISIONAL. "
                                + ("Aceptable en modo test." if self.test_mode
                                   else "En producción: requiere datos cartográficos definitivos.")
                            ),
                            path="capas/cartografia_trace.json",
                        ))
        # Clima: descripcion_clima.md o salida climática en salidas_generadas.json
        clima_md = self.expediente_path / "clima" / "descripcion_clima.md"
        tiene_clima = clima_md.exists()
        if not tiene_clima:
            sg_path = self.expediente_path / "capas" / "salidas_generadas.json"
            if sg_path.exists():
                sg = self._load_json(sg_path)
                if isinstance(sg, list):
                    tiene_clima = any(
                        "clima" in str(x.get("tipo", "")).lower() for x in sg
                    )
        if not tiene_clima:
            issues.append(GateIssue(
                severity="ERROR", phase="4",
                code="CLIMA_MISSING",
                message=(
                    "No se detecta descripcion_clima.md ni salida climática "
                    "en capas/salidas_generadas.json"
                ),
                path="clima/descripcion_clima.md",
            ))
        return issues

    # -- Fase 5: Inventario ambiental --

    def _check_files_phase5(self) -> list[GateIssue]:
        issues = []
        inv_dir = self.expediente_path / "fichas_inventario"
        if not inv_dir.is_dir():
            issues.append(GateIssue(
                severity="ERROR", phase="5",
                code="INVENTARIO_DIR_MISSING",
                message="Carpeta fichas_inventario/ no existe",
                path="fichas_inventario/",
            ))
            return issues

        fi_mds  = list(inv_dir.glob("FI-*.md"))
        indice  = inv_dir / "indice_inventario.json"
        inv_json = inv_dir / "inventario_ambiental.json"

        if not fi_mds and not indice.exists() and not inv_json.exists():
            issues.append(GateIssue(
                severity="ERROR", phase="5",
                code="INVENTARIO_EMPTY",
                message=(
                    "fichas_inventario/ existe pero no contiene fichas FI-*.md "
                    "ni índice/inventario JSON"
                ),
                path="fichas_inventario/",
            ))
            return issues

        # Contar factores ambientales detectados
        n_factores: Optional[int] = None
        if fi_mds:
            n_factores = len(fi_mds)
        elif inv_json.exists():
            data = self._load_json(inv_json)
            if isinstance(data, dict) and "fichas" in data:
                n_factores = len(data["fichas"])

        if n_factores is not None and n_factores < 16:
            issues.append(GateIssue(
                severity="WARNING", phase="5",
                code="INVENTARIO_FACTORES_INCOMPLETO",
                message=f"Se detectan {n_factores} factor(es) ambientales (se esperan 16)",
                path="fichas_inventario/",
            ))
        elif n_factores is None:
            issues.append(GateIssue(
                severity="INFO", phase="5",
                code="INVENTARIO_FACTORES_NO_CONTABLE",
                message="No se puede contar factores automáticamente — verificar manualmente",
                path="fichas_inventario/",
            ))
        return issues

    # -- Fase 6: Impactos, medidas y PVA --

    def _check_files_phase6(self) -> list[GateIssue]:
        issues = []
        imp_dir = self.expediente_path / "impactos"
        if not imp_dir.is_dir():
            issues.append(GateIssue(
                severity="ERROR", phase="6",
                code="IMPACTOS_DIR_MISSING",
                message="Carpeta impactos/ no existe",
                path="impactos/",
            ))
            return issues

        for tipo, candidates in REQUIRED_IMPACT_FILES.items():
            found = next((c for c in candidates if (imp_dir / c).exists()), None)
            if not found:
                issues.append(GateIssue(
                    severity="ERROR", phase="6",
                    code=f"IMPACT_FILE_MISSING_{tipo.upper()}",
                    message=(
                        f"No se encuentra {candidates[0]}"
                        + (f" (ni alias: {', '.join(candidates[1:])})" if len(candidates) > 1 else "")
                    ),
                    path=f"impactos/{candidates[0]}",
                ))
                continue

            data = self._load_json(imp_dir / found)
            if data is None:
                continue
            n = self._count_impact_entries(data)
            if n == 0:
                issues.append(GateIssue(
                    severity="ERROR", phase="6",
                    code=f"IMPACT_FILE_EMPTY_{tipo.upper()}",
                    message=f"{found} existe pero no contiene entradas",
                    path=f"impactos/{found}",
                ))
        return issues

    # -- Fase 7: Redacción bloques A-K --

    def _check_files_phase7(self) -> list[GateIssue]:
        issues = []
        bloques_dir = self.expediente_path / "bloques"
        if not bloques_dir.is_dir():
            issues.append(GateIssue(
                severity="ERROR", phase="7",
                code="BLOQUES_DIR_MISSING",
                message="Carpeta bloques/ no existe",
                path="bloques/",
            ))
            return issues
        for bloque in REQUIRED_BLOCKS:
            if not (bloques_dir / bloque).exists():
                issues.append(GateIssue(
                    severity="ERROR", phase="7",
                    code="BLOQUE_MISSING",
                    message=f"Bloque requerido ausente: {bloque}",
                    path=f"bloques/{bloque}",
                ))
        return issues

    # -- Fase 8: Ensamblaje DOCX --

    def _check_files_phase8(self) -> list[GateIssue]:
        issues = []
        out_dir = self.expediente_path / "output"
        if not out_dir.is_dir():
            issues.append(GateIssue(
                severity="ERROR", phase="8",
                code="OUTPUT_DIR_MISSING",
                message="Carpeta output/ no existe",
                path="output/",
            ))
            return issues
        docx_files = list(out_dir.glob("*.docx"))
        if not docx_files:
            issues.append(GateIssue(
                severity="ERROR", phase="8",
                code="DOCX_MISSING",
                message="No se encuentra ningún archivo .docx en output/",
                path="output/",
            ))
            return issues
        if self.test_mode:
            marcados = [
                f for f in docx_files
                if any(kw in f.name.upper() for kw in ("BORRADOR", "TEST", "DRAFT"))
            ]
            if not marcados:
                issues.append(GateIssue(
                    severity="WARNING", phase="8",
                    code="DOCX_SIN_MARCA_TEST",
                    message=(
                        "Expediente en test_mode pero el DOCX no incluye 'BORRADOR'/'TEST'/'DRAFT' "
                        "en el nombre del archivo. No se puede verificar sin abrir el documento."
                    ),
                    path=f"output/{docx_files[0].name}",
                ))
        return issues

    # -- Fase 9: Auditoría M-12 --

    def _check_files_phase9(self) -> list[GateIssue]:
        issues = []
        ci_dir = self.expediente_path / "control_interno"
        candidatos = list(ci_dir.glob("informe_auditoria*.md")) if ci_dir.is_dir() else []
        if not candidatos:
            issues.append(GateIssue(
                severity="ERROR", phase="9",
                code="AUDITORIA_MISSING",
                message=(
                    "No se encuentra informe_auditoria_final.md (ni variante) "
                    "en control_interno/"
                ),
                path="control_interno/informe_auditoria_final.md",
            ))
            return issues
        informe = candidatos[0]
        texto = informe.read_text(encoding="utf-8", errors="replace")
        tiene_conclusion = any(kw in texto for kw in FINAL_CONCLUSION_KEYWORDS)
        if not tiene_conclusion:
            issues.append(GateIssue(
                severity="ERROR", phase="9",
                code="AUDITORIA_SIN_CONCLUSION",
                message=(
                    f"El informe '{informe.name}' no contiene ninguna conclusión reconocible "
                    f"(esperado uno de: {FINAL_CONCLUSION_KEYWORDS})"
                ),
                path=f"control_interno/{informe.name}",
            ))
        return issues

    # -----------------------------------------------------------------------
    # check_previous_phase_completed
    # -----------------------------------------------------------------------

    def check_previous_phase_completed(self, phase: str) -> list[GateIssue]:
        """Verifica que la fase anterior esté COMPLETED según orchestrator_state.json.

        Si el archivo no existe:
        - test_mode=True  → WARNING
        - test_mode=False → ERROR
        """
        from eia_agent.core.orchestrator import Phase, PhaseStatusValue

        if phase == "1":
            return []
        prev = Phase.previous(phase)
        if prev is None:
            return []

        state_path = self.expediente_path / "control_interno" / "orchestrator_state.json"
        if not state_path.exists():
            sev = "WARNING" if self.test_mode else "ERROR"
            return [GateIssue(
                severity=sev, phase=phase,
                code="ORCHESTRATOR_STATE_MISSING",
                message=(
                    f"orchestrator_state.json no existe — no se puede verificar que "
                    f"la fase {prev} esté COMPLETED"
                ),
                path="control_interno/orchestrator_state.json",
            )]

        try:
            state_data = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return [GateIssue(
                severity="ERROR", phase=phase,
                code="ORCHESTRATOR_STATE_CORRUPT",
                message=f"orchestrator_state.json no puede parsearse: {exc}",
                path="control_interno/orchestrator_state.json",
            )]

        phases = state_data.get("phases", {})
        prev_status = phases.get(prev, {}).get("status", "")
        if prev_status != PhaseStatusValue.COMPLETED:
            return [GateIssue(
                severity="ERROR", phase=phase,
                code="PREV_PHASE_NOT_COMPLETED",
                message=(
                    f"Fase {prev} no está COMPLETED "
                    f"(estado actual: {prev_status or 'DESCONOCIDO'})"
                ),
                path=f"control_interno/orchestrator_state.json",
            )]
        return []

    # -----------------------------------------------------------------------
    # check_blocking_log_errors
    # -----------------------------------------------------------------------

    def check_blocking_log_errors(self) -> list[GateIssue]:
        """Verifica si OrchestratorLog tiene eventos bloqueantes (ERROR o BLOCKED).

        Si el log no existe, no emite issue.
        """
        log_path = self.expediente_path / "control_interno" / "orchestrator_log.json"
        if not log_path.exists():
            return []
        orch_log = OrchestratorLog(self.expediente_path)
        if orch_log.has_blocking_errors():
            return [GateIssue(
                severity="ERROR", phase="any",
                code="LOG_BLOCKING_ERRORS",
                message=(
                    "El OrchestratorLog contiene eventos bloqueantes (ERROR o BLOCKED). "
                    "Revise control_interno/orchestrator_log.json."
                ),
                path="control_interno/orchestrator_log.json",
            )]
        return []

    # -----------------------------------------------------------------------
    # check_test_mode_conditions
    # -----------------------------------------------------------------------

    def check_test_mode_conditions(self, phase: str) -> list[GateIssue]:
        """Detecta condiciones propias del modo test en el expediente.

        Detecta: asunciones AT, cartografía PROVISIONAL, impactos INDETERMINADO,
        y gaps ALTA/CRITICA abiertos.

        test_mode=True  → WARNING (documentado, no bloqueante).
        test_mode=False → ERROR en fases finales (presentación administrativa).
        """
        issues: list[GateIssue] = []
        issues += self._check_asuncion_test(phase)
        issues += self._check_cartografia_provisional_tm(phase)
        issues += self._check_impactos_indeterminado(phase)
        issues += self._check_gaps_alta_abiertos(phase)
        return issues

    def _check_asuncion_test(self, phase: str) -> list[GateIssue]:
        """Detecta referencias a AT-XXX en hechos o archivos de asunciones."""
        issues = []
        hc_path = self.expediente_path / "capas" / "hechos_confirmados.json"
        if hc_path.exists():
            hc = self._load_json(hc_path)
            if isinstance(hc, list):
                at_refs = [
                    x for x in hc
                    if "AT-" in str(x.get("nota", ""))
                    or "AT-" in str(x.get("fuentes", ""))
                ]
                if at_refs:
                    sev = "WARNING" if self.test_mode else "ERROR"
                    issues.append(GateIssue(
                        severity=sev, phase=phase,
                        code="AT_EN_HECHOS",
                        message=(
                            f"{len(at_refs)} hecho(s) referencia(n) asunciones test (AT-XXX). "
                            + ("Documentado en modo test." if self.test_mode
                               else "Requiere resolución antes de presentación administrativa.")
                        ),
                        path="capas/hechos_confirmados.json",
                    ))
        ci_dir = self.expediente_path / "control_interno"
        if ci_dir.is_dir():
            at_files = list(ci_dir.glob("asunciones_test*.md"))
            if at_files:
                sev = "WARNING" if self.test_mode else "ERROR"
                issues.append(GateIssue(
                    severity=sev, phase=phase,
                    code="AT_FILE_PRESENT",
                    message=(
                        f"Archivo de asunciones test detectado: {at_files[0].name}. "
                        + ("Aceptable en modo test." if self.test_mode
                           else "Requiere revisión antes de presentación administrativa.")
                    ),
                    path=f"control_interno/{at_files[0].name}",
                ))
        return issues

    def _check_cartografia_provisional_tm(self, phase: str) -> list[GateIssue]:
        """Detecta cartografía PROVISIONAL en fases 4+.

        Fase 4 ya comprueba esto en check_required_files. Esta comprobación
        actúa como recordatorio en fases posteriores donde la cartografía
        provisional puede afectar a inventario, impactos o redacción.
        """
        if phase in ("1", "2", "3", "4"):
            return []
        ct_path = self.expediente_path / "capas" / "cartografia_trace.json"
        if not ct_path.exists():
            return []
        ct = self._load_json(ct_path)
        if not isinstance(ct, list):
            return []
        provisionales = [x for x in ct if x.get("estado", "") == _CART_PROVISIONAL]
        if not provisionales:
            return []
        sev = "WARNING" if self.test_mode else "ERROR"
        return [GateIssue(
            severity=sev, phase=phase,
            code="CARTOGRAFIA_PROVISIONAL_TM",
            message=(
                f"{len(provisionales)} entrada(s) cartográficas aún en estado PROVISIONAL "
                f"(fase {phase}). "
                + ("Condición de test mode." if self.test_mode
                   else "Debe resolverse antes de presentación.")
            ),
            path="capas/cartografia_trace.json",
        )]

    def _check_impactos_indeterminado(self, phase: str) -> list[GateIssue]:
        """Detecta impactos con clasificación que contiene INDETERMINADO."""
        if phase in ("1", "2", "3", "4", "5"):
            return []
        imp_dir = self.expediente_path / "impactos"
        for candidate in REQUIRED_IMPACT_FILES["impactos"]:
            imp_path = imp_dir / candidate
            if not imp_path.exists():
                continue
            data = self._load_json(imp_path)
            if data is None:
                break
            items = data if isinstance(data, list) else []
            if isinstance(data, dict):
                items = data.get("valoracion_impactos", data.get("impactos", []))

            def _is_indet(item: dict) -> bool:
                if "INDETERMINADO" in str(item.get("clasificacion", "")).upper():
                    return True
                return any(
                    "INDETERMINADO" in str(v.get("clasificacion", "")).upper()
                    for v in item.values() if isinstance(v, dict)
                )

            indet = [x for x in items if isinstance(x, dict) and _is_indet(x)]
            if indet:
                sev = "WARNING" if self.test_mode else "ERROR"
                return [GateIssue(
                    severity=sev, phase=phase,
                    code="IMPACTO_INDETERMINADO",
                    message=(
                        f"{len(indet)} impacto(s) con clasificación INDETERMINADO. "
                        + ("Admisible en modo test." if self.test_mode
                           else "Requiere resolución antes de presentación.")
                    ),
                    path=f"impactos/{candidate}",
                )]
            break  # solo revisar el primer archivo que exista
        return []

    def _check_gaps_alta_abiertos(self, phase: str) -> list[GateIssue]:
        """Detecta gaps con criticidad ALTA o CRITICA no resueltos."""
        ig_path = self.expediente_path / "capas" / "inferencias_y_gaps.json"
        if not ig_path.exists():
            return []
        ig = self._load_json(ig_path)
        if not isinstance(ig, list):
            return []
        abiertos = [
            x for x in ig
            if x.get("criticidad", "") in _GAP_OPEN_CRITICIDADES
        ]
        if not abiertos:
            return []
        sev = "WARNING" if self.test_mode else "ERROR"
        codigos = [x.get("id", "?") for x in abiertos[:5]]
        return [GateIssue(
            severity=sev, phase=phase,
            code="GAPS_ALTA_ABIERTOS",
            message=(
                f"{len(abiertos)} gap(s) ALTA/CRITICA abiertos: {codigos}"
                + (" (y más)" if len(abiertos) > 5 else "") + ". "
                + ("Documentados en modo test." if self.test_mode
                   else "Deben resolverse antes de presentación administrativa.")
            ),
            path="capas/inferencias_y_gaps.json",
        )]

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    def _load_json(self, path: Path) -> "list | dict | None":
        """Carga un archivo JSON. Devuelve None si no puede parsearse o leerse."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _count_impact_entries(self, data: "list | dict") -> int:
        """Cuenta entradas en un archivo de impactos/medidas/pva (lista o dict)."""
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            # Buscar clave que contenga la lista de ítems
            for key in ("valoracion_impactos", "impactos", "medidas", "pva", "items"):
                if key in data and isinstance(data[key], list):
                    return len(data[key])
            # Fallback: si el dict no está vacío, asumir que tiene contenido
            return 1 if data else 0
        return 0
