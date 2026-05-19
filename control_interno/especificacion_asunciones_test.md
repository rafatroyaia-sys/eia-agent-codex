# Especificación técnica — Sistema AT (Asunciones de Test)

**Versión**: 1.0  
**Estado**: VALIDADO  
**Fecha**: 2026-04-19  
**Baseline**: piloto NAVE-222 (formalización post-auditoría M-12)  
**Origen**: OB-05 / OBS-M12-002

---

## §1. Propósito y posición en el sistema

El sistema AT (Asunciones de Test) es el mecanismo que permite desbloquear la ejecución de un expediente cuando existe un CONT (contradicción no resuelta entre documentos del promotor) que, de otro modo, impediría avanzar.

Un AT no resuelve el CONT — lo aparca provisionalmente para que el expediente pueda continuar en modo test, con la condición explícita de que el resultado no puede ser apto para uso administrativo real hasta que el CONT se resuelva.

**Posición en el flujo**: el sistema AT se activa en AG-09 (o excepcionalmente en AG-10) cuando un CONT bloquea la cadena de impacto-medida-PVA. Es un instrumento de desbloqeo controlado, no un mecanismo para eludir la clarificación del promotor.

---

## §2. Cuándo activar un AT

Un AT se activa cuando se cumplen TODAS estas condiciones:

1. Existe un CONT registrado en `inferencias_y_gaps.json` con estado ABIERTO
2. El CONT impide la valoración de uno o más impactos o el diseño de sus medidas/PVA
3. No hay datos adicionales disponibles para resolver el CONT (el promotor no ha clarificado)
4. El avance del expediente es necesario (modo test, prueba de concepto, formación)

**No se activa un AT si**:
- El CONT puede resolverse con información disponible en los documentos del promotor
- El CONT afecta a datos de identidad del expediente (titular, RC, coordenadas, superficie): estos son irreductibles y el expediente no puede avanzar sin ellos
- El expediente es de producción real y va a presentarse ante la administración

---

## §3. Qué puede y qué no puede hacer un AT

### Puede hacer

- Desbloquear la valoración de un impacto asumiendo la hipótesis más prudente o más conservadora
- Permitir que las medidas y el PVA se diseñen sobre la base asumida, con estado CONDICIONADO
- Permitir que el expediente avance en modo test con la advertencia explícita de que no es apto administrativamente
- Resolver exactamente un CONT por AT (relación 1:1)

### No puede hacer

- Transformar un dato PENDIENTE en CONFIRMADO
- Resolver contradicciones sobre datos de identidad del expediente (titular, RC, coordenadas, superficie)
- Sustituir la clarificación del promotor en un expediente real
- Aplicarse silenciosamente — cada AT debe estar registrado y visible en todos los bloques afectados
- Activarse más de una vez sobre el mismo CONT (un CONT → un AT máximo)

---

## §4. Formato JSON del AT

Cada AT se registra en `capas/inferencias_y_gaps.json` o en `impactos/asunciones_test.json` con la siguiente estructura:

```json
{
  "id": "AT-001",
  "cont_resuelto": "CONT-XXX",
  "descripcion_cont": "Descripción de la contradicción entre [DOC-A] y [DOC-B]",
  "asuncion": "Hipótesis asumida para desbloquear el expediente: [descripción de qué se asume]",
  "justificacion_prudencia": "Por qué esta hipótesis es la más conservadora/prudente disponible",
  "estado_evidencia": "ASUMIDO_PROVISIONALMENTE_TEST",
  "bloques_afectados": ["C", "D", "E"],
  "impactos_afectados": ["IMP-XX", "IMP-YY"],
  "impide_aptitud_administrativa": true,
  "fecha_activacion": "YYYY-MM-DD",
  "resolucion": null
}
```

**Campo `estado_evidencia`**: solo puede tomar el valor `ASUMIDO_PROVISIONALMENTE_TEST`. Nunca `CONFIRMADO`, nunca `DECLARADO`. El valor `ASUMIDO_PROVISIONALMENTE_TEST` es intencionalmente largo para que sea visible y no se confunda con un estado normal.

**Campo `impide_aptitud_administrativa`**: siempre `true`. No hay ATs que no impidan la aptitud administrativa. Si el AT no impidiera la aptitud, no sería un AT — sería una asunción ordinaria.

---

## §5. Propagación obligatoria del AT a los bloques

Un AT registrado en AG-09 debe propagarse a todos los bloques de redacción que use la hipótesis asumida. La propagación no es opcional.

### En Bloque C (AG-10/bloque_C)

Nota visible en la descripción del impacto afectado:
```
> ⚠️ **AT-XXX activo**: La valoración de este impacto se basa en [hipótesis asumida] 
> por resolución provisional de CONT-XXX. Si CONT-XXX se resuelve de forma distinta 
> a la hipótesis asumida, esta valoración debe revisarse.
```

### En Bloque D (AG-10/bloque_D)

Nota visible en la ficha de la medida condicionada:
```
> ⚠️ **AT-XXX activo**: Esta medida se diseñó asumiendo [hipótesis]. Si CONT-XXX 
> se confirma en sentido contrario, puede ser necesario revisar o ampliar las medidas.
```

### En Bloque E (AG-10/bloque_E)

La ficha PVA afectada tiene estado CONDICIONADO (ver §12a especificación Bloque E):
```
**Estado**: CONDICIONADO — activado provisionalmente por AT-XXX
```

### En toda la documentación

Si un AT está activo en el expediente, la portada o el apartado de introducción del Documento Ambiental debe incluir una advertencia de que el documento contiene asunciones de test y no es apto para uso administrativo.

---

## §6. Registro en control_interno

Cada AT activado se registra en `control_interno/registro_asunciones_test.md` con:

| ID | CONT resuelto | Hipótesis asumida | Bloques afectados | Fecha activación | Estado |
|----|--------------|------------------|------------------|-----------------|--------|
| AT-001 | CONT-XXX | [descripción breve] | C, D, E | YYYY-MM-DD | ACTIVO |

Este registro es el punto de entrada para saber qué asunciones están activas en el expediente y cuáles se han resuelto. Cuando el promotor clarifica el CONT, el AT pasa a estado RESUELTO y se documenta la hipótesis final.

---

## §7. Ejemplo piloto — AT-001 (Nave 222)

**Contexto**: En Nave 222, existía una discrepancia entre el uso declarado en la memoria ("almacén de chatarra y metales") y el uso catastral registrado ("almacén agrario"). Esta discrepancia es un CONT sobre el uso del inmueble.

**Hipótesis asumida por AT-001**: uso industrial de almacenamiento de residuos metálicos no peligrosos, en coherencia con el objeto declarado por el promotor en la memoria técnica, con la licencia de actividad solicitada y con la normativa de gestión de residuos (código LER 17 04 05).

**Justificación de prudencia**: la hipótesis asumida es la más conservadora porque implica mayor complejidad ambiental que "almacén agrario" — mayor número de acciones, mayor número de impactos potenciales, mayor necesidad de medidas.

**Bloques afectados**: C (valoración IMP-01 a IMP-11), D (medidas M-01 a M-10), E (PVA-01 a PVA-07).

**Impide aptitud administrativa**: sí — el uso catastral debe subsanarse antes de que el expediente se presente ante el órgano ambiental.

---

## §8. Diferencia AT vs GAP

| Concepto | AT (Asunción de Test) | GAP (Brecha de información) |
|----------|----------------------|----------------------------|
| Qué es | Hipótesis provisional que resuelve un CONT | Ausencia de un dato necesario |
| Cuándo se activa | Cuando un CONT bloquea el avance en modo test | Cuando falta información que el promotor debería aportar |
| Efecto sobre el expediente | Permite avanzar con la hipótesis, señalando el riesgo | Bloquea si criticidad ALTA; permite avanzar con precaución si MEDIA/BAJA |
| ¿Resuelve el problema? | No — lo aparca provisionalmente | No — señala la brecha para que se rellene |
| Estado en JSON | `ASUMIDO_PROVISIONALMENTE_TEST` | `PENDIENTE`, `INDETERMINADO` o `NO_CONSTA` |
| Impide aptitud administrativa | Siempre sí | Solo si criticidad ALTA |

Un AT puede coexistir con un GAP sobre el mismo dato: el AT desbloquea el flujo, el GAP sigue activo hasta que el promotor aporte el dato real.

---

*Especificación redactada en P2 — 2026-04-19*  
*Formalizada tras OB-05 / OBS-M12-002 del expediente NAVE-222*
