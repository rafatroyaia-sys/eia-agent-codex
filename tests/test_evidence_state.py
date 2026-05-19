"""
Tests para EvidenceState -- NL-05
Ejecutar: venv/Scripts/python -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

# Permite importar sin instalar el paquete
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.evidence_state import EvidenceState


# ---------------------------------------------------------------------------
# from_string
# ---------------------------------------------------------------------------

class TestFromString(unittest.TestCase):

    def test_valor_canonico_exacto(self):
        self.assertIs(EvidenceState.from_string("CONFIRMADO"), EvidenceState.CONFIRMADO)

    def test_lowercase_normalizado(self):
        self.assertIs(EvidenceState.from_string("confirmado"), EvidenceState.CONFIRMADO)

    def test_espacios_normalizados(self):
        self.assertIs(
            EvidenceState.from_string("CONFIRMADO CAMPO"),
            EvidenceState.CONFIRMADO_CAMPO,
        )

    def test_guiones_normalizados(self):
        self.assertIs(
            EvidenceState.from_string("CONFIRMADO-CAMPO"),
            EvidenceState.CONFIRMADO_CAMPO,
        )

    def test_alias_conf(self):
        self.assertIs(EvidenceState.from_string("CONF"), EvidenceState.CONFIRMADO)

    def test_alias_at(self):
        self.assertIs(EvidenceState.from_string("AT"), EvidenceState.ASUNCION_TEST)

    def test_alias_nc(self):
        self.assertIs(EvidenceState.from_string("NC"), EvidenceState.NO_CONSTA)

    def test_alias_pend(self):
        self.assertIs(EvidenceState.from_string("PEND"), EvidenceState.PENDIENTE)

    def test_estado_desconocido_lanza_valueerror(self):
        with self.assertRaises(ValueError) as ctx:
            EvidenceState.from_string("INVENTADO")
        self.assertIn("INVENTADO", str(ctx.exception))

    def test_tipo_incorrecto_lanza_typeerror(self):
        with self.assertRaises(TypeError):
            EvidenceState.from_string(42)  # type: ignore

    def test_descartado_retrocmpatibilidad(self):
        self.assertIs(EvidenceState.from_string("DESCARTADO"), EvidenceState.DESCARTADO)


# ---------------------------------------------------------------------------
# is_confirmed
# ---------------------------------------------------------------------------

class TestIsConfirmed(unittest.TestCase):

    def test_confirmado_campo(self):
        self.assertTrue(EvidenceState.CONFIRMADO_CAMPO.is_confirmed())

    def test_confirmado_gabinete(self):
        self.assertTrue(EvidenceState.CONFIRMADO_GABINETE.is_confirmed())

    def test_confirmado(self):
        self.assertTrue(EvidenceState.CONFIRMADO.is_confirmed())

    def test_declarado_no_es_confirmado(self):
        self.assertFalse(EvidenceState.DECLARADO.is_confirmed())

    def test_asuncion_test_no_es_confirmado(self):
        self.assertFalse(EvidenceState.ASUNCION_TEST.is_confirmed())

    def test_pendiente_no_es_confirmado(self):
        self.assertFalse(EvidenceState.PENDIENTE.is_confirmed())

    def test_error_no_es_confirmado(self):
        self.assertFalse(EvidenceState.ERROR.is_confirmed())


# ---------------------------------------------------------------------------
# is_pending
# ---------------------------------------------------------------------------

class TestIsPending(unittest.TestCase):

    def test_pendiente(self):
        self.assertTrue(EvidenceState.PENDIENTE.is_pending())

    def test_pendiente_verificacion(self):
        self.assertTrue(EvidenceState.PENDIENTE_VERIFICACION.is_pending())

    def test_no_consta(self):
        self.assertTrue(EvidenceState.NO_CONSTA.is_pending())

    def test_confirmado_no_es_pendiente(self):
        self.assertFalse(EvidenceState.CONFIRMADO.is_pending())

    def test_asuncion_test_no_es_pendiente(self):
        self.assertFalse(EvidenceState.ASUNCION_TEST.is_pending())


# ---------------------------------------------------------------------------
# is_test_assumption
# ---------------------------------------------------------------------------

class TestIsTestAssumption(unittest.TestCase):

    def test_asuncion_test_es_at(self):
        self.assertTrue(EvidenceState.ASUNCION_TEST.is_test_assumption())

    def test_confirmado_no_es_at(self):
        self.assertFalse(EvidenceState.CONFIRMADO.is_test_assumption())

    def test_pendiente_no_es_at(self):
        self.assertFalse(EvidenceState.PENDIENTE.is_test_assumption())

    def test_declarado_no_es_at(self):
        self.assertFalse(EvidenceState.DECLARADO.is_test_assumption())


# ---------------------------------------------------------------------------
# requires_qualifier
# ---------------------------------------------------------------------------

class TestRequiresQualifier(unittest.TestCase):

    def test_declarado_requiere(self):
        self.assertTrue(EvidenceState.DECLARADO.requires_qualifier())

    def test_asuncion_test_requiere(self):
        self.assertTrue(EvidenceState.ASUNCION_TEST.requires_qualifier())

    def test_inferido_requiere(self):
        self.assertTrue(EvidenceState.INFERIDO.requires_qualifier())

    def test_pendiente_requiere(self):
        self.assertTrue(EvidenceState.PENDIENTE.requires_qualifier())

    def test_no_consta_requiere(self):
        self.assertTrue(EvidenceState.NO_CONSTA.requires_qualifier())

    def test_confirmado_no_requiere(self):
        self.assertFalse(EvidenceState.CONFIRMADO.requires_qualifier())

    def test_confirmado_campo_no_requiere(self):
        self.assertFalse(EvidenceState.CONFIRMADO_CAMPO.requires_qualifier())

    def test_descartado_no_requiere(self):
        self.assertFalse(EvidenceState.DESCARTADO.requires_qualifier())


# ---------------------------------------------------------------------------
# can_support_final_admin_document
# ---------------------------------------------------------------------------

class TestCanSupportFinalAdminDocument(unittest.TestCase):

    def test_confirmado_apto(self):
        self.assertTrue(EvidenceState.CONFIRMADO.can_support_final_admin_document())

    def test_confirmado_campo_apto(self):
        self.assertTrue(EvidenceState.CONFIRMADO_CAMPO.can_support_final_admin_document())

    def test_confirmado_gabinete_apto(self):
        self.assertTrue(EvidenceState.CONFIRMADO_GABINETE.can_support_final_admin_document())

    def test_asuncion_test_no_apto(self):
        self.assertFalse(EvidenceState.ASUNCION_TEST.can_support_final_admin_document())

    def test_declarado_no_apto(self):
        self.assertFalse(EvidenceState.DECLARADO.can_support_final_admin_document())

    def test_pendiente_no_apto(self):
        self.assertFalse(EvidenceState.PENDIENTE.can_support_final_admin_document())

    def test_inferido_no_apto(self):
        self.assertFalse(EvidenceState.INFERIDO.can_support_final_admin_document())


# ---------------------------------------------------------------------------
# confidence_rank
# ---------------------------------------------------------------------------

class TestConfidenceRank(unittest.TestCase):

    def test_confirmado_campo_maximo(self):
        self.assertEqual(EvidenceState.CONFIRMADO_CAMPO.confidence_rank(), 100)

    def test_confirmado_gabinete_90(self):
        self.assertEqual(EvidenceState.CONFIRMADO_GABINETE.confidence_rank(), 90)

    def test_confirmado_80(self):
        self.assertEqual(EvidenceState.CONFIRMADO.confidence_rank(), 80)

    def test_error_es_cero(self):
        self.assertEqual(EvidenceState.ERROR.confidence_rank(), 0)

    def test_asuncion_test_menor_que_declarado(self):
        self.assertLess(
            EvidenceState.ASUNCION_TEST.confidence_rank(),
            EvidenceState.DECLARADO.confidence_rank(),
        )

    def test_orden_general(self):
        """Verificar que el orden esperado se mantiene."""
        orden = [
            EvidenceState.ERROR,
            EvidenceState.DESCARTADO,
            EvidenceState.PENDIENTE,
            EvidenceState.NO_CONSTA,
            EvidenceState.PENDIENTE_VERIFICACION,
            EvidenceState.ASUNCION_TEST,
            EvidenceState.PROVISIONAL,
            EvidenceState.LIMITADO_ESCALA,
            EvidenceState.ESTIMADO,
            EvidenceState.INFERIDO,
            EvidenceState.INFERIDO_TECNICO,
            EvidenceState.DECLARADO,
            EvidenceState.CONFIRMADO,
            EvidenceState.CONFIRMADO_GABINETE,
            EvidenceState.CONFIRMADO_CAMPO,
        ]
        ranks = [e.confidence_rank() for e in orden]
        self.assertEqual(ranks, sorted(ranks))


# ---------------------------------------------------------------------------
# is_valid_transition
# ---------------------------------------------------------------------------

class TestIsValidTransition(unittest.TestCase):

    def test_misma_estado_siempre_valido(self):
        for estado in EvidenceState:
            with self.subTest(estado=estado):
                self.assertTrue(EvidenceState.is_valid_transition(estado, estado))

    def test_subida_de_rango_valida(self):
        self.assertTrue(
            EvidenceState.is_valid_transition(
                EvidenceState.PENDIENTE,
                EvidenceState.CONFIRMADO,
            )
        )

    def test_bajada_de_rango_invalida_sin_flag(self):
        self.assertFalse(
            EvidenceState.is_valid_transition(
                EvidenceState.CONFIRMADO,
                EvidenceState.PENDIENTE,
            )
        )

    def test_bajada_de_rango_valida_con_flag(self):
        self.assertTrue(
            EvidenceState.is_valid_transition(
                EvidenceState.CONFIRMADO,
                EvidenceState.PENDIENTE,
                allow_downgrade=True,
            )
        )

    def test_at_a_confirmado_bloqueado(self):
        """ASUNCION_TEST -> CONFIRMADO es SIEMPRE invalido, sin excepcion."""
        self.assertFalse(
            EvidenceState.is_valid_transition(
                EvidenceState.ASUNCION_TEST,
                EvidenceState.CONFIRMADO,
            )
        )

    def test_at_a_confirmado_campo_bloqueado(self):
        self.assertFalse(
            EvidenceState.is_valid_transition(
                EvidenceState.ASUNCION_TEST,
                EvidenceState.CONFIRMADO_CAMPO,
            )
        )

    def test_at_a_confirmado_gabinete_bloqueado(self):
        self.assertFalse(
            EvidenceState.is_valid_transition(
                EvidenceState.ASUNCION_TEST,
                EvidenceState.CONFIRMADO_GABINETE,
            )
        )

    def test_at_a_confirmado_bloqueado_incluso_con_allow_downgrade(self):
        """allow_downgrade no desbloquea la regla especial de AT."""
        self.assertFalse(
            EvidenceState.is_valid_transition(
                EvidenceState.ASUNCION_TEST,
                EvidenceState.CONFIRMADO,
                allow_downgrade=True,
            )
        )

    def test_pendiente_a_declarado_valido(self):
        self.assertTrue(
            EvidenceState.is_valid_transition(
                EvidenceState.PENDIENTE,
                EvidenceState.DECLARADO,
            )
        )

    def test_inferido_a_confirmado_valido(self):
        self.assertTrue(
            EvidenceState.is_valid_transition(
                EvidenceState.INFERIDO,
                EvidenceState.CONFIRMADO_GABINETE,
            )
        )


if __name__ == "__main__":
    unittest.main()
