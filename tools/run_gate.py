#!/usr/bin/env python3
"""
run_gate.py -- EIA-Agent v2.1
Gate automatico: valida el modelo de datos antes de ejecutar una fase.

Uso:
    python tools/run_gate.py <expediente_path> <fase>
    python tools/run_gate.py <expediente_path> <fase> --test

    <fase>  : numero o codigo de fase (1, 2, 3, 4A, 4B, 5, 6, 7, 8, 9)
    --test  : modo test -- GAPs ALTA producen aviso, no bloqueo

Salida:
    exit 0  -> gate aprobado (puede haber avisos)
    exit 1  -> gate bloqueado

Registra el resultado en <expediente>/control_interno/log_orquestador.md
"""

import json
import sys
from datetime import date
from pathlib import Path

# Importar logica de validacion del modulo validate_expediente
sys.path.insert(0, str(Path(__file__).parent))
from validate_expediente import (
    CAPAS_REQUERIDAS,
    Result,
    count_gaps_alta,
    validate_archivos_fisicos,
    validate_cartografia_trace,
    validate_cross_layer,
    validate_ficha_objeto,
    validate_hc_trazabilidad,
    validate_hechos_confirmados,
    validate_inferencias_y_gaps,
    validate_matriz_trazabilidad,
    validate_normativa_aplicable,
    validate_salidas_generadas,
)

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

GATE_PASS      = "APROBADO"
GATE_PASS_WARN = "APROBADO_CON_AVISOS"
GATE_BLOCK     = "BLOQUEADO"

# Requisitos minimos por fase (sobre las capas ya validadas)
# Solo los que se pueden comprobar programaticamente sin ejecutar la fase.
REQUISITOS_FASE = {
    "1":  {},   # Fase 1 es la primera -- solo valida estructura inicial
    "2":  {"min_hc": 5},
    "3":  {"min_hc": 10, "check_ficha_objeto": True},
    "4":  {"min_normativa": 1},
    "4A": {"min_normativa": 1},
    "4B": {"min_normativa": 1},
    "5":  {"min_mapas_generados": 1},
    "6":  {"min_mapas_generados": 8},
    "7":  {"min_hc": 10},
    "8":  {"check_bloques_redactados": True},
    "9":  {"check_docx": True},
}

# ---------------------------------------------------------------------------
# CARGA DE CAPAS
# ---------------------------------------------------------------------------

def _load_capas(capas_dir: Path, r: Result) -> dict:
    loaded = {}
    for capa in CAPAS_REQUERIDAS:
        path = capas_dir / capa
        if not path.exists():
            r.error(f"Capa requerida ausente: {capa}")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                loaded[capa] = data
            else:
                r.error(f"{capa}: el contenido raiz debe ser array JSON")
        except Exception as e:
            r.error(f"{capa}: JSON invalido -- {e}")
    return loaded


# ---------------------------------------------------------------------------
# VALIDACION COMPLETA
# ---------------------------------------------------------------------------

def run_full_validation(base: Path) -> tuple:
    """
    Ejecuta la validacion completa del modelo de datos.
    Retorna (result, loaded_capas, hc_ids).
    """
    r = Result()
    capas_dir = base / "capas"

    if not capas_dir.exists():
        r.error("Directorio 'capas/' no existe en el expediente")
        return r, {}, set()

    loaded = _load_capas(capas_dir, r)
    hc_ids = set()

    if "hechos_confirmados.json" in loaded:
        hc_ids = validate_hechos_confirmados(loaded["hechos_confirmados.json"], r)
    if "inferencias_y_gaps.json" in loaded:
        validate_inferencias_y_gaps(loaded["inferencias_y_gaps.json"], r)
    if "normativa_aplicable.json" in loaded:
        validate_normativa_aplicable(loaded["normativa_aplicable.json"], r)
    if "matriz_trazabilidad.json" in loaded:
        validate_matriz_trazabilidad(loaded["matriz_trazabilidad.json"], hc_ids, r)
    if "cartografia_trace.json" in loaded:
        validate_cartografia_trace(loaded["cartografia_trace.json"], r)
    if "salidas_generadas.json" in loaded:
        validate_salidas_generadas(loaded["salidas_generadas.json"], r)

    validate_cross_layer(loaded, hc_ids, r)
    validate_ficha_objeto(base, r)
    if "hechos_confirmados.json" in loaded and "matriz_trazabilidad.json" in loaded:
        validate_hc_trazabilidad(
            loaded["hechos_confirmados.json"],
            loaded["matriz_trazabilidad.json"],
            r,
        )
    validate_archivos_fisicos(loaded, base, r)
    return r, loaded, hc_ids


# ---------------------------------------------------------------------------
# CHECKS ESPECIFICOS DE FASE
# ---------------------------------------------------------------------------

def check_fase_requirements(fase: str, loaded: dict, base: Path) -> list:
    """
    Comprueba requisitos minimos especificos de la fase indicada.
    Retorna lista de mensajes de bloqueo (vacia = OK).
    """
    reqs = REQUISITOS_FASE.get(fase.upper(), REQUISITOS_FASE.get(fase, {}))
    blockers = []

    # min_hc: minimo de hechos confirmados
    if "min_hc" in reqs and "hechos_confirmados.json" in loaded:
        n = len(loaded["hechos_confirmados.json"])
        if n < reqs["min_hc"]:
            blockers.append(
                f"hechos_confirmados tiene {n} entradas -- se requieren al menos {reqs['min_hc']} para Fase {fase}"
            )

    # min_normativa: al menos 1 norma verificada online
    if "min_normativa" in reqs and "normativa_aplicable.json" in loaded:
        verificadas = [
            n for n in loaded["normativa_aplicable.json"]
            if n.get("estado") == "VERIFICADA ONLINE"
        ]
        if len(verificadas) < reqs["min_normativa"]:
            blockers.append(
                f"normativa_aplicable: {len(verificadas)} normas verificadas online -- "
                f"se requiere al menos {reqs['min_normativa']} para Fase {fase}"
            )

    # min_mapas_generados: mapas en estado GENERADO, VERIFICADO o PROVISIONAL
    # PROVISIONAL cuenta para la comprobacion de existencia de mapas de apoyo
    # (el estado distingue disponibilidad para el trabajo vs. aptitud para presentacion)
    if "min_mapas_generados" in reqs and "cartografia_trace.json" in loaded:
        generados = [
            c for c in loaded["cartografia_trace.json"]
            if c.get("estado") in ("GENERADO", "VERIFICADO", "PROVISIONAL")
        ]
        if len(generados) < reqs["min_mapas_generados"]:
            blockers.append(
                f"cartografia_trace: {len(generados)} mapas generados -- "
                f"se requieren al menos {reqs['min_mapas_generados']} para Fase {fase}"
            )

    # check_ficha_objeto: ficha_objeto_evaluado.md debe existir
    if reqs.get("check_ficha_objeto"):
        ficha = base / "control_interno" / "ficha_objeto_evaluado.md"
        if not ficha.exists():
            blockers.append(
                "control_interno/ficha_objeto_evaluado.md no existe -- "
                "la Fase 2 (cierre del objeto) no se ha ejecutado"
            )

    # check_bloques_redactados: al menos 10 SGs de fase 7 (bloques A-K)
    if reqs.get("check_bloques_redactados") and "salidas_generadas.json" in loaded:
        bloques = [
            s for s in loaded["salidas_generadas.json"]
            if str(s.get("fase", "")).startswith("7") and "MD" in str(s.get("tipo", ""))
        ]
        if len(bloques) < 10:
            blockers.append(
                f"salidas_generadas: solo {len(bloques)} bloques MD de Fase 7 -- "
                "se esperan al menos 10 bloques A-K redactados para Fase 8"
            )

    # check_docx: al menos 1 SG de fase 8 (DOCX)
    if reqs.get("check_docx") and "salidas_generadas.json" in loaded:
        docx_entries = [
            s for s in loaded["salidas_generadas.json"]
            if str(s.get("fase", "")) == "8" and "DOCX" in str(s.get("tipo", "")).upper()
        ]
        if not docx_entries:
            blockers.append(
                "salidas_generadas: no hay ninguna entrada de Fase 8 con tipo DOCX -- "
                "el ensamblador M-11 no se ha ejecutado"
            )

    return blockers


# ---------------------------------------------------------------------------
# DECISION DEL GATE
# ---------------------------------------------------------------------------

def decide_gate(
    r: Result,
    loaded: dict,
    base: Path,
    fase: str,
    modo_test: bool,
) -> tuple:
    """
    Aplica la logica de decision del gate.

    Retorna (estado, blockers, warnings) donde:
      estado   : APROBADO | APROBADO_CON_AVISOS | BLOQUEADO
      blockers : causas de bloqueo (lista de strings)
      warnings : avisos no bloqueantes (lista de strings)
    """
    blockers = list(r.errors)    # errores de modelo: siempre bloquean
    warnings = list(r.warnings)  # avisos del validador: nunca bloquean

    # Requisitos especificos de la fase
    fase_blockers = check_fase_requirements(fase, loaded, base)
    blockers.extend(fase_blockers)

    # GAPs de criticidad ALTA
    gaps_alta = []
    if "inferencias_y_gaps.json" in loaded:
        gaps_alta = count_gaps_alta(loaded["inferencias_y_gaps.json"])

    for gap in gaps_alta:
        msg = (
            f"GAP ALTA abierto: {gap.get('id','?')} -- {gap.get('campo','?')}"
        )
        if modo_test:
            # En modo test: los GAPs ALTA son avisos, no bloqueantes
            warnings.append(msg)
        else:
            # En produccion: los GAPs ALTA bloquean el gate
            blockers.append(msg)

    # Estado final
    if blockers:
        return GATE_BLOCK, blockers, warnings
    if warnings:
        return GATE_PASS_WARN, blockers, warnings
    return GATE_PASS, blockers, warnings


# ---------------------------------------------------------------------------
# LOG EN log_orquestador.md
# ---------------------------------------------------------------------------

def _truncate(items: list, max_items: int = 2) -> str:
    """Genera string legible para la celda del log (max caracteres aprox)."""
    shown = items[:max_items]
    extra = len(items) - max_items
    parts = [s.replace("|", "/") for s in shown]  # escapar pipe del Markdown
    result = "; ".join(parts)
    if extra > 0:
        result += f" (+{extra} mas)"
    return result


def log_gate_result(
    base: Path,
    fase: str,
    estado: str,
    blockers: list,
    warnings: list,
    r: Result,
    modo_test: bool,
):
    """Registra el resultado del gate en control_interno/log_orquestador.md."""
    log_path = base / "control_interno" / "log_orquestador.md"
    if not log_path.exists():
        return  # no crear el log si no existe

    today = date.today().strftime("%Y-%m-%d")
    modo_str = " (modo test)" if modo_test else ""

    if estado == GATE_PASS:
        resultado = (
            f"GATE {estado}. {r.checked} registros validados. "
            f"Sin errores ni avisos{modo_str}."
        )
    elif estado == GATE_PASS_WARN:
        resultado = (
            f"GATE {estado}. {r.checked} registros. "
            f"0 errores, {len(warnings)} avisos{modo_str}: "
            f"{_truncate(warnings)}."
        )
    else:
        resultado = (
            f"GATE {estado}. {len(blockers)} causa(s): "
            f"{_truncate(blockers)}. "
            f"Corregir antes de ejecutar Fase {fase}."
        )

    accion = (
        f"Validacion automatica del modelo de datos "
        f"(run_gate.py) antes de Fase {fase}"
    )
    row = f"| {today} | GATE FASE {fase} | Orquestador | {accion} | {resultado} |\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(row)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    args = sys.argv[1:]

    if len(args) < 2 or "--help" in args or "-h" in args:
        print(__doc__)
        return 1

    expediente_path = args[0]
    fase = args[1]
    modo_test = "--test" in args or "--modo-test" in args

    base = Path(expediente_path)
    if not base.exists():
        print(f"ERROR: El directorio '{base}' no existe.")
        return 1

    # --- Cabecera ---
    SEP  = "=" * 62
    sep2 = "-" * 44
    print(f"\n{SEP}")
    print(f"EIA-Agent v2.1 -- Gate Fase {fase}")
    print(f"Expediente : {base.resolve()}")
    print(f"Modo       : {'TEST (GAPs ALTA no bloquean)' if modo_test else 'PRODUCCION'}")
    print(f"{SEP}\n")

    # --- Validacion ---
    r, loaded, _ = run_full_validation(base)

    print(f"{sep2}")
    print("Capas del modelo de datos:")
    print(f"{sep2}")
    for capa in CAPAS_REQUERIDAS:
        n   = len(loaded.get(capa, []))
        ok  = "OK" if capa in loaded else "!!"
        print(f"  {ok}  {capa:<35} {n:3d} registros")
    print()

    # --- Decision ---
    estado, blockers, warnings = decide_gate(r, loaded, base, fase, modo_test)

    # --- Registro en log ---
    log_gate_result(base, fase, estado, blockers, warnings, r, modo_test)

    # --- Salida ---
    if warnings:
        print(f"  AVISOS ({len(warnings)}) -- no bloquean:")
        for w in warnings:
            print(f"    >> {w}")
        print()

    if blockers:
        print(f"  CAUSAS DE BLOQUEO ({len(blockers)}):")
        for b in blockers:
            print(f"    !! {b}")
        print()

    ICONOS = {GATE_PASS: "OK", GATE_PASS_WARN: "OK (con avisos)", GATE_BLOCK: "BLOQUEADO"}
    SEP3 = "-" * 62
    print(SEP3)
    print(f"  GATE FASE {fase}:  {ICONOS.get(estado, estado)}")
    print(SEP3 + "\n")

    return 0 if estado != GATE_BLOCK else 1


if __name__ == "__main__":
    sys.exit(main())
