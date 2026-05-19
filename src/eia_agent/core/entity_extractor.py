"""
entity_extractor -- IN-02
Extractor de entidades ambientales, administrativas y técnicas de documentos DOCX.

Usa reglas, regex y heurísticas. No usa IA ni LLM.

Uso:
    from eia_agent.core.entity_extractor import extract_entities_from_docx

    result = extract_entities_from_docx("inputs/memorias/Documento_Ambiental.docx")
    for rc in result.by_type("REFERENCIA_CATASTRAL"):
        print(rc.value)
    for ler in result.by_type("LER"):
        print(ler.value, "peligroso:", ler.normalized_value and "*" in ler.normalized_value)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ExtractedEntity:
    """Entidad detectada en el documento."""
    entity_type: str           # RC / LER / OPERACION / COORDENADA / SUPERFICIE /
                               # CAPACIDAD / POTENCIA / FECHA / PROMOTOR / EQUIPO
    value: str                 # valor tal como aparece en el texto
    source: str                # "texto" / "tabla:<nombre_columna>" / "tabla:celda"
    confidence: str            # HIGH / MEDIUM / LOW
    context: Optional[str] = None          # fragmento de texto donde se encontró
    normalized_value: Optional[str] = None # valor normalizado

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExtractedEntity):
            return NotImplemented
        return self.entity_type == other.entity_type and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.entity_type, self.value))


@dataclass
class ExtractionResult:
    """Resultado de la extracción de entidades de un documento."""
    entities: list[ExtractedEntity] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def by_type(self, entity_type: str) -> list[ExtractedEntity]:
        """Devuelve todas las entidades del tipo indicado."""
        return [e for e in self.entities if e.entity_type == entity_type]

    def values(self, entity_type: str) -> list[str]:
        """Devuelve los valores de las entidades del tipo indicado."""
        return [e.value for e in self.entities if e.entity_type == entity_type]

    def summary(self) -> str:
        """Resumen de entidades detectadas por tipo."""
        if not self.entities:
            return "Sin entidades detectadas."
        counts: dict[str, int] = {}
        for e in self.entities:
            counts[e.entity_type] = counts.get(e.entity_type, 0) + 1
        lines = [f"{t}: {n}" for t, n in sorted(counts.items())]
        total = len(self.entities)
        warn_str = f" | {len(self.warnings)} aviso(s)" if self.warnings else ""
        return f"{total} entidades — " + ", ".join(lines) + warn_str


# ---------------------------------------------------------------------------
# Patrones compilados
# ---------------------------------------------------------------------------

# Referencia catastral española: 20 chars alfanuméricos
# 7 dígitos + 2 mayúsculas + 4 dígitos + 1 mayúscula + 4 dígitos + 2 mayúsculas
_RC_RE = re.compile(r'\b(\d{7}[A-Z]{2}\d{4}[A-Z]\d{4}[A-Z]{2})\b')

# LER con espacios: XX XX XX (con asterisco opcional para peligrosos)
_LER_SPACES_RE = re.compile(r'\b(\d{2})\s(\d{2})\s(\d{2})(\*?)')
# LER sin espacios: XXXXXX (con asterisco opcional)
# No usar \b al final: el asterisco no es word-char y rompería el boundary
_LER_COMPACT_RE = re.compile(r'\b(\d{6})(\*?)(?!\d)')

# Operaciones R/D (de más específico a más general — orden importa en búsqueda)
_OPS_RE = re.compile(r'\b(R\d{4}|R\d{3}|R\d{2}|D\d{2})\b')

# Coordenadas decimales cerca de palabras clave
_COORD_KW_RE = re.compile(
    r'(?:latitud|longitud|lat\b|lon\b|coordenadas?|wgs\s*84|epsg)'
    r'[^:\n=]{0,30}[:=\s]\s*(-?\d{1,3}[.,]\d{4,})',
    re.I | re.UNICODE,
)

# Coordenadas UTM: E: 642000 / N: 3207000 / X= / Y=
_COORD_UTM_RE = re.compile(r'\b([ENXY])\s*[:=]\s*([\d.,]{4,})', re.I)

# Superficies: número + m² / m2 / metros cuadrados
_SURFACE_RE = re.compile(
    r'([\d.,]+)\s*(?:m[²2²\xb2]|metros?\s+cuadrados?)',
    re.I | re.UNICODE,
)

# Capacidades: número + t|TM / día|año
_CAPACITY_RE = re.compile(
    r'([\d.,]+)\s*(?:tm?|toneladas?)\s*[./]\s*(?:a[ñn]o|d[íi]a)'
    r'|'
    r'([\d.,]+)\s*t\s*/\s*(?:a[ñn]o|d[íi]a)',
    re.I | re.UNICODE,
)

# Potencias: kW, W, CV, HP
_POWER_RE = re.compile(r'([\d.,]+)\s*(kW|W|CV|HP)\b')

# Fechas dd/mm/yyyy y yyyy-mm-dd
_DATE_RE = re.compile(r'\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b')

# Promotor/titular por palabras clave en texto
_PROMOTOR_TEXT_RE = re.compile(
    r'(?:promovid[oa]\s+por|promotor[^:]*:|titular[^:]*:|solicitante[^:]*:)\s*'
    r'([A-ZÁÉÍÓÚÜÑ][^,.\n]{3,60}(?:S\.L\.|S\.A\.|S\.L\.U\.|S\.A\.U\.|SL|SA)?)',
    re.I | re.UNICODE,
)

# Patrón para detectar nombres de empresa (S.L., S.A., etc.)
_EMPRESA_RE = re.compile(
    r'([A-ZÁÉÍÓÚÜÑ][A-Za-záéíóúüñÁÉÍÓÚÜÑ\s,.-]{2,50}'
    r'(?:,\s*)?(?:S\.L\.U?\.?|S\.A\.U?\.?|S\.L|S\.A|SLU|SAU)\.?)',
    re.UNICODE,
)

# Equipos/maquinaria por palabras clave
_EQUIPO_RE = re.compile(
    r'\b(molino|criba|cizalla|prensa|compresor|b[áa]scula|carretilla'
    r'|radial|trituradora|cinta\s+transportadora)\b',
    re.I | re.UNICODE,
)


# ---------------------------------------------------------------------------
# Funciones de normalización
# ---------------------------------------------------------------------------

def normalize_ler(value: str) -> str:
    """Normaliza un código LER al formato 'XX XX XX' (con asterisco si peligroso).

    Acepta formatos: '170405', '17 04 05', '17 04 05*'.
    """
    digits = re.sub(r'[^0-9]', '', value)[:6]
    peligroso = '*' if '*' in value else ''
    if len(digits) == 6:
        return f"{digits[:2]} {digits[2:4]} {digits[4:6]}{peligroso}"
    return value.strip()


def is_ler_peligroso(value: str) -> bool:
    """True si el código LER lleva asterisco (residuo peligroso)."""
    return '*' in value


def normalize_surface(value: str) -> str:
    """Normaliza un valor de superficie al formato '<número> m²'.

    Convierte separadores españoles: 1.931,40 → 1931.40.
    """
    # Eliminar separador de miles (punto) y convertir decimal (coma → punto)
    clean = re.sub(r'\.(?=\d{3})', '', value.strip())
    clean = clean.replace(',', '.')
    try:
        num = float(clean)
        return f"{num:g} m²"
    except ValueError:
        return f"{value.strip()} m²"


def normalize_power(value: str, unit: str) -> str:
    """Normaliza un valor de potencia al formato '<número> <unidad>'."""
    clean = value.replace('.', '').replace(',', '.').strip()
    try:
        num = float(clean)
        return f"{num:g} {unit.upper()}"
    except ValueError:
        return f"{value.strip()} {unit}"


# ---------------------------------------------------------------------------
# Extractores internos por tipo
# ---------------------------------------------------------------------------

def _ctx(text: str, start: int, end: int, window: int = 60) -> str:
    """Devuelve un fragmento de contexto alrededor de una coincidencia."""
    a = max(0, start - window)
    b = min(len(text), end + window)
    return text[a:b].replace('\n', ' ').strip()


def _extract_rc(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _RC_RE.finditer(text):
        val = m.group(1)
        if val not in seen:
            seen.add(val)
            entities.append(ExtractedEntity(
                entity_type="REFERENCIA_CATASTRAL",
                value=val,
                source=source,
                confidence="HIGH",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=val,
            ))
    return entities


def _extract_ler(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()

    for m in _LER_SPACES_RE.finditer(text):
        d1, d2, d3, asterisk = m.group(1), m.group(2), m.group(3), m.group(4)
        raw = f"{d1} {d2} {d3}{asterisk}"
        norm = normalize_ler(raw)
        if norm not in seen:
            seen.add(norm)
            entities.append(ExtractedEntity(
                entity_type="LER",
                value=raw,
                source=source,
                confidence="HIGH",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=norm,
            ))

    for m in _LER_COMPACT_RE.finditer(text):
        digits, asterisk = m.group(1), m.group(2)
        norm = normalize_ler(digits + asterisk)
        if norm not in seen:
            seen.add(norm)
            entities.append(ExtractedEntity(
                entity_type="LER",
                value=digits + asterisk,
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=norm,
            ))

    return entities


def _extract_operaciones(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _OPS_RE.finditer(text):
        val = m.group(1).upper()
        if val not in seen:
            seen.add(val)
            entities.append(ExtractedEntity(
                entity_type="OPERACION",
                value=val,
                source=source,
                confidence="HIGH",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=val,
            ))
    return entities


def _extract_coordenadas(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()

    for m in _COORD_KW_RE.finditer(text):
        val = m.group(1).replace(',', '.')
        key = f"DEC:{val}"
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(
                entity_type="COORDENADA",
                value=val,
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=f"DEC {val}",
            ))

    for m in _COORD_UTM_RE.finditer(text):
        axis, val = m.group(1).upper(), m.group(2)
        key = f"UTM:{axis}:{val}"
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(
                entity_type="COORDENADA",
                value=f"{axis}: {val}",
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=f"UTM {axis}={val}",
            ))

    return entities


def _extract_superficies(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _SURFACE_RE.finditer(text):
        raw = m.group(1)
        norm = normalize_surface(raw)
        # Contexto puede indicar tipo de superficie
        ctx = _ctx(text, m.start(), m.end())
        ctx_lower = ctx.lower()
        tipo = "SUPERFICIE"
        for kw in ("construida", "útil", "util", "catastral", "parcela", "nave"):
            if kw in ctx_lower:
                tipo = f"SUPERFICIE_{kw.upper().replace('ÚTIL', 'UTIL')}"
                break
        key = f"{tipo}:{norm}"
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(
                entity_type=tipo,
                value=m.group(0).strip(),
                source=source,
                confidence="MEDIUM",
                context=ctx,
                normalized_value=norm,
            ))
    return entities


def _extract_capacidades(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _CAPACITY_RE.finditer(text):
        raw = m.group(0).strip()
        num = (m.group(1) or m.group(2) or "").strip()
        if raw not in seen:
            seen.add(raw)
            entities.append(ExtractedEntity(
                entity_type="CAPACIDAD",
                value=raw,
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=raw,
            ))
    return entities


def _extract_potencias(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _POWER_RE.finditer(text):
        num, unit = m.group(1), m.group(2)
        norm = normalize_power(num, unit)
        if norm not in seen:
            seen.add(norm)
            entities.append(ExtractedEntity(
                entity_type="POTENCIA",
                value=m.group(0).strip(),
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=norm,
            ))
    return entities


def _extract_fechas(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _DATE_RE.finditer(text):
        val = m.group(1)
        if val not in seen:
            seen.add(val)
            entities.append(ExtractedEntity(
                entity_type="FECHA",
                value=val,
                source=source,
                confidence="HIGH",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=val,
            ))
    return entities


def _extract_promotor(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()

    # Heurística 1: "promovido por", "promotor:", "titular:"
    for m in _PROMOTOR_TEXT_RE.finditer(text):
        val = m.group(1).strip().rstrip('.,')
        if val not in seen and len(val) > 3:
            seen.add(val)
            entities.append(ExtractedEntity(
                entity_type="PROMOTOR",
                value=val,
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=val,
            ))

    # Heurística 2: nombres de empresa (S.L., S.A., etc.) en el texto
    for m in _EMPRESA_RE.finditer(text):
        val = m.group(1).strip().rstrip('.,')
        if val not in seen and len(val) > 5:
            seen.add(val)
            entities.append(ExtractedEntity(
                entity_type="PROMOTOR",
                value=val,
                source=source,
                confidence="LOW",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=val,
            ))

    return entities


def _extract_equipos(text: str, source: str) -> list[ExtractedEntity]:
    entities = []
    seen: set[str] = set()
    for m in _EQUIPO_RE.finditer(text):
        val = m.group(1).lower()
        if val not in seen:
            seen.add(val)
            entities.append(ExtractedEntity(
                entity_type="EQUIPO",
                value=m.group(0).strip(),
                source=source,
                confidence="MEDIUM",
                context=_ctx(text, m.start(), m.end()),
                normalized_value=val,
            ))
    return entities


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def extract_entities_from_text(
    texto: str,
    source: str = "texto",
) -> ExtractionResult:
    """Extrae entidades de un texto plano usando regex y heurísticas.

    Args:
        texto:  Texto plano a analizar.
        source: Etiqueta de origen para las entidades detectadas.

    Returns:
        ExtractionResult con todas las entidades detectadas.
        Si texto está vacío devuelve entities=[].
    """
    if not texto or not texto.strip():
        return ExtractionResult()

    all_entities: list[ExtractedEntity] = []
    all_entities.extend(_extract_rc(texto, source))
    all_entities.extend(_extract_ler(texto, source))
    all_entities.extend(_extract_operaciones(texto, source))
    all_entities.extend(_extract_coordenadas(texto, source))
    all_entities.extend(_extract_superficies(texto, source))
    all_entities.extend(_extract_capacidades(texto, source))
    all_entities.extend(_extract_potencias(texto, source))
    all_entities.extend(_extract_fechas(texto, source))
    all_entities.extend(_extract_promotor(texto, source))
    all_entities.extend(_extract_equipos(texto, source))

    return ExtractionResult(entities=all_entities)


def extract_entities_from_docx(path: "str | Path") -> ExtractionResult:
    """Extrae entidades de un archivo .docx combinando texto y tablas.

    Usa parse_docx() (IN-01) para leer el documento.
    No modifica el archivo.

    Args:
        path: Ruta al archivo .docx.

    Returns:
        ExtractionResult con todas las entidades detectadas.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el archivo no es un DOCX válido.
    """
    from eia_agent.core.docx_parser import parse_docx, extract_tables_raw

    path = Path(path)
    content = parse_docx(path)  # puede lanzar FileNotFoundError / ValueError

    all_entities: list[ExtractedEntity] = []
    seen_keys: set[tuple[str, str]] = set()
    warnings: list[str] = []

    def _add(entities: list[ExtractedEntity]) -> None:
        for e in entities:
            key = (e.entity_type, e.value)
            if key not in seen_keys:
                seen_keys.add(key)
                all_entities.append(e)

    # ---- Extraer del texto ----
    _add(extract_entities_from_text(content.texto, source="texto").entities)

    # ---- Extraer de tablas ----
    try:
        raw_tables = extract_tables_raw(path)
    except Exception as exc:
        warnings.append(f"No se pudieron leer tablas crudas: {exc}")
        raw_tables = []

    for t_idx, tabla in enumerate(raw_tables):
        for r_idx, fila in enumerate(tabla):
            for c_idx, celda in enumerate(fila):
                if not celda.strip():
                    continue
                src = f"tabla:{t_idx}:fila{r_idx}:col{c_idx}"
                _add(extract_entities_from_text(celda, source=src).entities)

    # ---- Extraer promotor de estructura de tablas (key-value) ----
    for tabla in content.tablas:
        for fila in tabla:
            for key, val in fila.items():
                # Caso: key = "Promotor" o similar → val puede ser el nombre
                if re.search(r'promotor|titular|solicitante', key, re.I):
                    if val and len(val.strip()) > 3 and not re.match(r'^[A-Z]{2,3}$', val.strip()):
                        e_key = ("PROMOTOR", val.strip())
                        if e_key not in seen_keys:
                            seen_keys.add(e_key)
                            all_entities.append(ExtractedEntity(
                                entity_type="PROMOTOR",
                                value=val.strip(),
                                source="tabla:kv",
                                confidence="HIGH",
                                normalized_value=val.strip(),
                            ))
                # Caso inverso: key contiene el nombre de empresa → es promotor
                if _EMPRESA_RE.search(key):
                    e_key = ("PROMOTOR", key.strip())
                    if e_key not in seen_keys:
                        seen_keys.add(e_key)
                        all_entities.append(ExtractedEntity(
                            entity_type="PROMOTOR",
                            value=key.strip(),
                            source="tabla:cabecera",
                            confidence="HIGH",
                            normalized_value=key.strip(),
                        ))

    return ExtractionResult(entities=all_entities, warnings=warnings)
