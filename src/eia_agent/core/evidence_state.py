"""
EvidenceState -- estados de evidencia del sistema EIA-Agent v2.1

Cada dato en el expediente lleva uno de estos estados.
Principio rector: primero se prueba, luego se delimita, luego se valora.
"""
from enum import Enum
from typing import Optional


class EvidenceState(Enum):
    """Estados de evidencia canónicos del sistema EIA-Agent."""

    # -- Confirmados (dato probado) ------------------------------------------
    CONFIRMADO_CAMPO = "CONFIRMADO_CAMPO"
    CONFIRMADO_GABINETE = "CONFIRMADO_GABINETE"
    CONFIRMADO = "CONFIRMADO"

    # -- Declarado por el promotor -------------------------------------------
    DECLARADO = "DECLARADO"

    # -- Asuncion de test (desbloqueo provisional) ---------------------------
    ASUNCION_TEST = "ASUNCION_TEST"

    # -- Inferidos -----------------------------------------------------------
    INFERIDO_TECNICO = "INFERIDO_TECNICO"
    INFERIDO = "INFERIDO"

    # -- Limitado / estimado / provisional -----------------------------------
    LIMITADO_ESCALA = "LIMITADO_ESCALA"
    ESTIMADO = "ESTIMADO"
    PROVISIONAL = "PROVISIONAL"

    # -- Pendientes ----------------------------------------------------------
    PENDIENTE_VERIFICACION = "PENDIENTE_VERIFICACION"
    PENDIENTE = "PENDIENTE"
    NO_CONSTA = "NO_CONSTA"

    # -- Terminales ----------------------------------------------------------
    DESCARTADO = "DESCARTADO"   # compatibilidad hacia atras con validate_expediente.py
    ERROR = "ERROR"

    # -----------------------------------------------------------------------
    # Metodos de consulta
    # -----------------------------------------------------------------------

    def is_confirmed(self) -> bool:
        """True si el dato está probado (campo o gabinete)."""
        return self in _CONFIRMED_STATES

    def is_test_assumption(self) -> bool:
        """True si el estado es ASUNCION_TEST."""
        return self is EvidenceState.ASUNCION_TEST

    def is_pending(self) -> bool:
        """True si el dato está pendiente de verificación o no consta."""
        return self in _PENDING_STATES

    def requires_qualifier(self) -> bool:
        """True si el estado obliga a incluir un cualificador en el texto."""
        return self in _REQUIRES_QUALIFIER

    def can_support_final_admin_document(self) -> bool:
        """True si el estado es apto para figurar en el documento administrativo final.

        ASUNCION_TEST y estados no confirmados bloquean la aptitud administrativa.
        """
        return self in _CONFIRMED_STATES

    def qualifier_label(self) -> str:
        """Etiqueta de cualificador para insertar en redacción técnica."""
        return _QUALIFIER_LABELS.get(self, self.value.lower().replace("_", " "))

    def confidence_rank(self) -> int:
        """Rango de confianza (0-100). Mayor valor = mayor certeza."""
        return _CONFIDENCE_RANKS.get(self, 0)

    # -----------------------------------------------------------------------
    # Transiciones
    # -----------------------------------------------------------------------

    @staticmethod
    def is_valid_transition(
        old: "EvidenceState",
        new: "EvidenceState",
        allow_downgrade: bool = False,
    ) -> bool:
        """Indica si la transicion de *old* a *new* está permitida.

        Regla especial: ASUNCION_TEST -> estados confirmados está SIEMPRE
        bloqueada, independientemente del rango de confianza.
        """
        if old is new:
            return True

        # Bloqueo permanente: AT nunca puede resolverse a confirmado
        if old is EvidenceState.ASUNCION_TEST and new in _CONFIRMED_STATES:
            return False

        if new.confidence_rank() >= old.confidence_rank():
            return True

        return allow_downgrade

    # -----------------------------------------------------------------------
    # Constructores alternativos
    # -----------------------------------------------------------------------

    @classmethod
    def from_string(cls, value: str) -> "EvidenceState":
        """Construye un EvidenceState desde una cadena, con alias y normalización.

        Raises:
            ValueError: si la cadena no corresponde a ningún estado conocido.
        """
        if not isinstance(value, str):
            raise TypeError(f"Se esperaba str, se recibio {type(value).__name__!r}")

        normalizado = value.strip().upper().replace(" ", "_").replace("-", "_")

        try:
            return cls(normalizado)
        except ValueError:
            pass

        if normalizado in _ALIASES:
            return _ALIASES[normalizado]

        estados_conocidos = ", ".join(e.value for e in cls)
        raise ValueError(
            f"Estado desconocido: {value!r}. "
            f"Estados validos: {estados_conocidos}"
        )


# ---------------------------------------------------------------------------
# Constantes de módulo -- definidas DESPUÉS de la clase para referenciar
# los miembros del enum directamente.
# ---------------------------------------------------------------------------

_CONFIRMED_STATES: frozenset = frozenset({
    EvidenceState.CONFIRMADO_CAMPO,
    EvidenceState.CONFIRMADO_GABINETE,
    EvidenceState.CONFIRMADO,
})

_PENDING_STATES: frozenset = frozenset({
    EvidenceState.PENDIENTE_VERIFICACION,
    EvidenceState.PENDIENTE,
    EvidenceState.NO_CONSTA,
})

_REQUIRES_QUALIFIER: frozenset = frozenset({
    EvidenceState.DECLARADO,
    EvidenceState.ASUNCION_TEST,
    EvidenceState.INFERIDO_TECNICO,
    EvidenceState.INFERIDO,
    EvidenceState.LIMITADO_ESCALA,
    EvidenceState.ESTIMADO,
    EvidenceState.PROVISIONAL,
    EvidenceState.PENDIENTE_VERIFICACION,
    EvidenceState.PENDIENTE,
    EvidenceState.NO_CONSTA,
})

_CONFIDENCE_RANKS: dict = {
    EvidenceState.CONFIRMADO_CAMPO:        100,
    EvidenceState.CONFIRMADO_GABINETE:      90,
    EvidenceState.CONFIRMADO:               80,
    EvidenceState.DECLARADO:                60,
    EvidenceState.INFERIDO_TECNICO:         50,
    EvidenceState.INFERIDO:                 40,
    EvidenceState.ESTIMADO:                 40,
    EvidenceState.LIMITADO_ESCALA:          30,
    EvidenceState.PROVISIONAL:              30,
    EvidenceState.ASUNCION_TEST:            25,
    EvidenceState.PENDIENTE_VERIFICACION:   20,
    EvidenceState.PENDIENTE:                10,
    EvidenceState.NO_CONSTA:                10,
    EvidenceState.DESCARTADO:                5,
    EvidenceState.ERROR:                     0,
}

_QUALIFIER_LABELS: dict = {
    EvidenceState.CONFIRMADO_CAMPO:       "confirmado mediante trabajo de campo",
    EvidenceState.CONFIRMADO_GABINETE:    "confirmado en gabinete",
    EvidenceState.CONFIRMADO:             "confirmado",
    EvidenceState.DECLARADO:              "declarado por el promotor",
    EvidenceState.ASUNCION_TEST:          "asuncion de test (provisional, bloquea aptitud administrativa)",
    EvidenceState.INFERIDO_TECNICO:       "inferido por criterio tecnico",
    EvidenceState.INFERIDO:               "inferido",
    EvidenceState.LIMITADO_ESCALA:        "limitado por escala cartografica",
    EvidenceState.ESTIMADO:               "estimado",
    EvidenceState.PROVISIONAL:            "provisional",
    EvidenceState.PENDIENTE_VERIFICACION: "pendiente de verificacion",
    EvidenceState.PENDIENTE:              "pendiente",
    EvidenceState.NO_CONSTA:              "no consta en la documentacion analizada",
    EvidenceState.DESCARTADO:             "descartado",
    EvidenceState.ERROR:                  "error de datos",
}

# Alias de entrada aceptados en from_string()
_ALIASES: dict = {
    # Abreviaturas históricas usadas en expedientes anteriores
    "CONF":            EvidenceState.CONFIRMADO,
    "CONF_CAMPO":      EvidenceState.CONFIRMADO_CAMPO,
    "CONF_GAB":        EvidenceState.CONFIRMADO_GABINETE,
    "DECL":            EvidenceState.DECLARADO,
    "AT":              EvidenceState.ASUNCION_TEST,
    "INF":             EvidenceState.INFERIDO,
    "INF_TEC":         EvidenceState.INFERIDO_TECNICO,
    "LIM":             EvidenceState.LIMITADO_ESCALA,
    "EST":             EvidenceState.ESTIMADO,
    "PROV":            EvidenceState.PROVISIONAL,
    "PV":              EvidenceState.PENDIENTE_VERIFICACION,
    "PEND":            EvidenceState.PENDIENTE,
    "NC":              EvidenceState.NO_CONSTA,
    "DESC":            EvidenceState.DESCARTADO,
    # Variantes con guion (normalize ya convierte - a _)
}
