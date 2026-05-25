# ROADMAP DE PRODUCTIZACIÓN — EIA-Agent v2.1
## Del piloto validado al sistema de producción

**Fecha**: 2026-04-13  
**Última actualización**: 2026-04-19 — normalización de IDs pre-P1 código  
**Baseline de partida**: Piloto 1 (PARCELA — CON OBSERVACIONES) + Piloto 2 (NAVE-222 — CONFORME EN MODO TEST)  
**Horizonte total**: 3 fases de productización (P1 → P2 → P3)

> **AVISO POST-NORMALIZACIÓN**: Los IDs en este roadmap están alineados con `matriz_maestra_items_productizacion.md`.  
> El orden canónico de arranque P1 es: **INST-01 → NL-05 → NL-01 → NL-02 → NL-03** (no NL-01+NL-05+NL-02 como indicaba la recomendación de Etapa 1, que tenía asignaciones incorrectas).  
> EN-05 (TOC) es **P2** aunque aparecía en la sección semana 5-6 — no es necesario para CONFORME.  
> Área 14: ítems de prompt completados (Etapa 1). Los ítems de código correspondientes están en semana 9.  

---

## PRINCIPIO DEL ROADMAP

El roadmap sigue la misma lógica del sistema: **primero se prueba la arquitectura, después se amplía la cobertura, y al final se construye la interfaz.**

No se construye frontend hasta que el núcleo esté suficientemente maduro para no requerir refactors que rompan contratos de API. No se amplían tipologías hasta que el tipo R12/R13 esté completamente automatizable. No se abre a usuarios hasta que la auditoría sea programática y no manual.

---

## FASE P1 — NÚCLEO FUNCIONAL AUTOMATIZABLE

**Objetivo**: Poder ejecutar un segundo expediente real (no piloto) sin asistencia manual en ninguna fase, sobre el mismo tipo de proyecto (R12/R13 polígono industrial en Canarias), con un resultado de auditoría CONFORME o CON OBSERVACIONES justificadas.

**Duración estimada**: 6-10 semanas de desarrollo

### Criterios de éxito P1
- [x] ~~Un segundo expediente R12/R13 en Canarias ejecutado~~ — **PARCIALMENTE alcanzado**: Nave 222 CONFORME en modo test con sistema AT. Pendiente: ejecución sin modo AT (datos confirmados)
- [ ] La auditoría M-12 produce resultado automático (no narrativo LLM) basado en checks programáticos
- [x] ~~El DOCX se genera sin errores en entorno Linux y Windows~~ — **ALCANZADO en Windows**: ensamblar_docx.py 0 bugs, 438 KB. Linux sin probar.
- [ ] El sistema detecta y bloquea automáticamente los gaps de criticidad ALTA
- [ ] Ningún dato del DA carece de estado de evidencia trazable

> **Estado P1 tras segundo piloto**: 2 de 5 criterios parcialmente alcanzados como práctica LLM. Ningún criterio alcanzado como código ejecutable. El siguiente paso es iniciar NL-01 + NL-05 + NL-02 para convertir la práctica validada en código.

### Ítems del backlog para P1

#### Semana 1-2: Infraestructura base + modelo de datos
- ~~**INST-01**: Instalador multiplataforma~~ — **COMPLETADO ✅ 2026-04-20**
- ~~**ASSETS-01**: Recursos de marca (logo, colores, usos)~~ — **COMPLETADO ✅ 2026-04-26** (`assets/brand/` + `docs/BRAND_ASSETS.md`, logo pendiente de colocar)
- ~~**SOURCES-01**: Catálogo de fuentes EIA (30 fuentes)~~ — **COMPLETADO ✅ 2026-04-26** (`config/reference_sources/eia_sources_catalog.json` + `docs/EIA_SOURCES_CATALOG.md`, estado REFERENCIA_MANUAL)
- **BE-03**: Estructura de carpetas como función Python
- **BE-04**: Gestión segura de AEMET API key
- ~~**NL-05**: Clase `EvidenceState` con transiciones~~ — **COMPLETADO ✅ 2026-04-19** (15 estados, 8 métodos, 58 tests OK)
- ~~**NL-01**: JSON Schema v2.1 formalizado para las 6 capas~~ — **COMPLETADO ✅ 2026-04-20** (7 schemas, 27 tests OK, pilotos PARCELA y NAVE-222 validan)
- ~~**NL-02**: Validador de schemas (Python + jsonschema)~~ — **COMPLETADO ✅ 2026-04-20** (33 tests OK, pilotos PARCELA y NAVE-222 validan)
- ~~**NL-06**: Log de orquestador en JSON estructurado~~ — **COMPLETADO ✅ 2026-04-20** (44 tests OK, `OrchestratorLog` + `OrchestratorEvent`, persiste a `control_interno/orchestrator_log.json`)

#### Semana 3-4: Ingesta y cierre del objeto
- ~~IN-01: Parser DOCX modular (python-docx)~~ — **COMPLETADO ✅ 2026-04-21** (55 tests OK, `parse_docx()` + `extract_tables_raw()` + `DocxContent`, fixture PARCELA)
- ~~IN-02: Extractor de entidades con validación de formato~~ — **COMPLETADO ✅ 2026-04-21** (105 tests OK, `extract_entities_from_text()` + `extract_entities_from_docx()`, 10 tipos, regex puro, fixture PARCELA)
- ~~IN-03: Clasificador de evidencias automático~~ — **COMPLETADO ✅ 2026-04-22** (89 tests OK, `classify_entities()` + `classify_entities_from_docx()` + `CandidateFact` + `ClassificationResult`, DECLARADO/ASUNCION_TEST/conflictos, fixture PARCELA)
- ~~IN-05: Generador de `inputs_index.json`~~ — **COMPLETADO ✅ 2026-04-22** (86 tests OK, `build_inputs_index()` + `write_inputs_index()` + `load_inputs_index()`, sha256, 8 tipos detectados, PARCELA y NAVE-222 solo lectura)
- ~~OB-01: Template de `ficha_objeto_evaluado.md`~~ — **COMPLETADO ✅ 2026-04-22** (70 tests OK, `build_object_scope()` + `ObjectScope` + `write_object_scope_markdown/json()` + `load_object_scope_json()`, ficha 10 secciones, estado_gate2 APTO/PENDIENTE/BLOQUEADO, fixture PARCELA solo lectura)
- ~~OB-02: Validador de gate 2 programático~~ — **COMPLETADO ✅ 2026-04-23** (79 tests OK, `evaluate_gate_2()` + `ObjectGateResult` + `ObjectGateIssue`, 10 reglas, test_mode vs producción, fixture PARCELA solo lectura)
- ~~**OB-06**: Pipeline Fase 2 (integración IN-06+OB-01+OB-02)~~ — **COMPLETADO ✅ 2026-04-25** (66 tests OK, `run_phase2()` + `Phase2Result` + `build_classification_result_from_phase1()`, CLI `phase2 [--write] [--prod]`, pilots PARCELA y NAVE-222 solo lectura)
- ~~**TN-05**: Pipeline Fase 3 (triaje normativo básico)~~ — **COMPLETADO ✅ 2026-04-25** (115 tests OK, `run_phase3()` + `Phase3Result` + `NormativeItem`, 10 normas, 7 cautelas, CLI `phase3 [--write]`, pilots solo lectura)
- ~~**CA-08**: Precheck Fase 4 (cartografía y clima)~~ — **COMPLETADO ✅ 2026-04-25** (113 tests OK, `run_phase4_precheck()` + `Phase4PrecheckResult` + `Phase4PrecheckIssue`, 7 códigos P4-E/W/I, CLI `phase4-precheck [--write]`, pilots via tempfiles solo lectura)

#### Semana 4-5: Cartografía y clima
- CA-01: `config/wms_services.json` con primary + fallback
- CA-02: Cliente WMS con retry y circuit-breaker
- CA-03: Generador de 8 mapas mínimos parametrizados
- CA-04: `cartografia_trace.json` automático
- CA-05: `config/jurisdicciones/canarias.json`
- ~~CL-01: Clase cliente AEMET~~ — **COMPLETADO ✅ 2026-04-26** (84 tests OK, `AEMETClient` + `from_env()` + `get_normales_climatologicas()`, retry backoff, 8 excepciones tipadas)
- ~~CL-02: Selector de estación más próxima~~ — **COMPLETADO ✅ 2026-04-26** (78 tests OK, `ClimateStation` + `StationSelection` + `haversine_km()` + `find_nearest_station()` + `parse_station_from_aemet_dict()` DMS+decimal + `load_stations_from_json()` + `select_station_for_object_scope()`, OPTIMA/ACEPTABLE/LEJANA/NO_DISPONIBLE)
- ~~CL-03: Calculador Köppen + Martonne~~ — **COMPLETADO ✅ 2026-04-26** (77 tests OK, `MonthlyClimateData` + `ClimateClassification` + `classify_koppen()` B/A/C/D/E + `martonne_index()` + `gaussen_dry_months()` + `classify_climate()` + parser AEMET)
- ~~CL-04: Generador PNG climograma (matplotlib)~~ — **COMPLETADO ✅ 2026-04-26** (53 tests OK, `ClimogramConfig` + `ClimogramResult` + `generate_climogram()` + `validate_png()` + `default_climogram_filename()`, backend Agg, doble eje Y, Gaussen, ValueError no-.png)
- ~~CL-06: Pipeline climático Fase 4 offline (integración CL-02+CL-03+CL-04)~~ — **COMPLETADO ✅ 2026-04-27** (63 tests OK, `run_phase4_climate()` + `load_monthly_climate_dataset()` + `extract_wgs84_from_phase2()` + CLI `phase4-climate`, sin AEMET)
- ~~CL-05: Inserción climograma en DOCX~~ — **COMPLETADO ✅ 2026-04-26** (56 tests OK, `insert_climogram_in_docx()` + `validate_docx_contains_image()` + `count_docx_images()` + `default_climogram_caption()`, python-docx sin LibreOffice)
- ~~**CA-09**: Núcleo geoespacial offline para cartografía~~ — **COMPLETADO ✅ 2026-04-27** (96 tests OK, `GeoPoint` + `BoundingBox` + `MapExtent` + `parse_wgs84_coordinate()` + `haversine_distance_km()` + `bounding_box_around_point()` + `build_map_extent()` + `build_standard_map_extents()` + `extract_geopoint_from_phase2()`, 5 extents estándar EIA, sin Mapbox/WMS, 1877 suite OK)
- ~~**CA-10**: Planificador cartográfico offline~~ — **COMPLETADO ✅ 2026-04-27** (75 tests OK, `MapSpec` + `CartographyPlanResult` + `build_cartography_plan()` + `build_cartography_plan_markdown()`, 6 mapas MAP-001…MAP-006, READY_FOR_RENDER/PLANNED por status coordenadas, CLI `cartography-plan [--write]`, outputs `cartografia_plan.json` + `cartografia_plan.md`, sin Mapbox/WMS/imágenes, 1952 suite OK)
- ~~**CA-11**: Generador de mapas esquemáticos offline~~ — **COMPLETADO ✅ 2026-04-27** (62 tests OK, `SchematicMapConfig` + `SchematicMapResult` + `generate_schematic_map()` + `generate_schematic_maps_from_plan()` + `validate_png()` + `load_cartography_plan()` + `build_map_generation_report()`, PNG 1600×1100 con cuadrícula/marcador/norte/escala/leyenda/watermark, CLI `schematic-maps [--plan] [--write]`, sin WMS/Mapbox/datos reales, 2014 suite OK)
- ~~**F4-01**: Pipeline integrador Fase 4 offline~~ — **COMPLETADO ✅ 2026-04-27** (79 tests OK, `Phase4OfflineResult` + `build_phase4_offline_markdown()` + `run_phase4_offline()`, cadena CA-08→CL-06→CA-10→CA-11, `administrative_ready` siempre False, CLI `phase4-offline --stations --climate-data [--write]`, outputs `fase4/phase4_result.json` + `fase4/phase4_result.md`, sin AEMET/Mapbox/WMS, 2093 suite OK)
- ~~**IV-00**: Modelo base de inventario ambiental~~ — **COMPLETADO ✅ 2026-04-29** (139 tests OK, `InventoryGap` + `FactorInventory` + `InventorySummary`, 16 factores FI-001…FI-016, `classify_semaphore_from_evidence()`, regla prudencia + coherencia, `build_empty_factor_inventory()` + `build_all_empty_factors()` + `build_inventory_summary()`, sin CLI/web/WMS/IA, 2232 suite OK, 12 skipped)
- ~~**IV-01**: Templates fichas de inventario ambiental~~ — **COMPLETADO ✅ 2026-04-29** (143 tests OK, `render_factor_inventory_markdown()` + `render_inventory_summary_markdown()` + `build_inventory_index()` + `write_inventory_markdown_files()`, 8 secciones, `safe_factor_filename()` sin tildes, detección COMPATIBLE/MODERADO/SEVERO/CRÍTICO por stems, `InventoryRenderConfig` + `InventoryRenderResult`, sin CLI/web/IA, 2375 suite OK, 12 skipped)
- ~~**IV-02**: Constructor de inventario desde Fase 4 offline~~ — **COMPLETADO ✅ 2026-04-29** (117 tests OK, `load_json_file()` + `InventoryBuildResult` + `build_climate_factor_from_phase4()` + `build_base_factor()` + `build_inventory_from_phase4_data()` + `build_inventory_from_phase4()`, FI-001 Clima CONFIRMADO_GABINETE/DECLARADO/PENDIENTE según CL-06, FI-002…FI-016 PENDIENTE/NO_CONSTA, CLI `inventory-build [--write]`, Lanzarote BWh VERDE ready=True, 2492 suite OK, 12 skipped)

#### Semana 5-6: Ensamblador DOCX + CLI básico
- ~~EN-01: Reescritura en python-docx~~ — **VALIDADO ✅** (Nave 222, 2026-04-19)
- ~~EN-03: Inserción PNG sin bug de rutas~~ — **Resuelto ✅** (Nave 222, 2026-04-19)
- ~~**CL-05**: Inserción climograma PNG en DOCX (resuelve problema SVG del piloto)~~ — **COMPLETADO ✅ 2026-04-26**
- **EN-02**: Tabla de posicionamiento de bloques
- **EN-04**: Eliminar referencia huérfana numbering.xml
- ~~EN-05: TOC automático~~ — **MOVIDO A P2** (no necesario para CONFORME)
- ~~EN-06: Portada parametrizable~~ — **MOVIDO A P2**
- ~~**CLI-01**: Runner básico `run_expediente.py [ID] [--fase N]`~~ — **COMPLETADO ✅ 2026-04-21** (43 tests OK, comandos status/validate/gate/recover/log-summary, main(argv)->int, solo lectura salvo --write-report)

#### Semana 7-8: Auditoría programática
- AU-01: Checklist art.45 + Anexo VI como código
- AU-02: Validador de regla de prudencia (grep de patrones)
- AU-03: Validador de trazabilidad HC↔DA
- AU-04: Informe de auditoría en JSON + MD

#### Semana 7-8: Orquestador, gates y auditoría
- ~~**NL-03**: Clase `EIAOrchestrator` con grafo de dependencias~~ — **COMPLETADO ✅ 2026-04-21** (67 tests OK, 16 criterios verificados)
- ~~**NL-04**: Gate-checker automático~~ — **COMPLETADO ✅ 2026-04-21** (82 tests OK, `GateChecker` + `GateIssue` + `GateResult`, test_mode/producción, aliases NAVE-222/PARCELA)
- ~~**NL-07**: Recuperación de sesión desde checkpoint~~ — **COMPLETADO ✅ 2026-04-21** (94 tests OK, `SessionRecovery` + `RecoveryIssue` + `RecoveryReport`, detecta IN_PROGRESS/BLOCKED/corrupto/discrepancias, solo lectura)
- ~~**IV-02**: Constructor de inventario desde Fase 4 offline~~ — **ya marcado arriba**
- ~~**IV-03**: Constructor factores FI-005 e FI-016 desde Fase 4 offline~~ — **COMPLETADO ✅ 2026-04-30** (99 tests OK, `build_flood_risk_factor_from_phase4()` + `build_natural_risks_factor_from_phase4()` + `build_risk_inventory_factors_from_phase4()` + `merge_risk_factors_into_summary()` + `RiskInventoryBuildResult`, FI-005 ESTIMADO/AMARILLO si MAP-006 en plan, FI-016 ESTIMADO/AMARILLO si coords+plan, GAP ALTA siempre, nunca VERDE, sin SNCZI/WMS/IA, integrado en `inventory-build`, 2591 suite OK, 12 skipped)
- ~~**IV-04**: Constructor factores FI-011 Paisaje y FI-013 Socioeconomía desde Fase 2/Fase 4 offline~~ — **COMPLETADO ✅ 2026-04-30** (105 tests OK, `build_landscape_factor_from_phase_data()` + `build_socioeconomic_factor_from_phase_data()` + `build_context_inventory_factors_from_phase_data()` + `merge_context_factors_into_summary()` + `ContextInventoryBuildResult`, FI-011 ESTIMADO/AMARILLO si coords+plan, FI-013 DECLARADO/AMARILLO+ready=True si promotor+actividad+ubicacion, GAP-FI-011-001 MEDIA/CAMPO siempre, GAP-FI-013-001 MEDIA/GABINETE siempre, nunca VERDE, sin visores/WMS/IA, carga automática phase2_result.json, 2696 suite OK, 12 skipped)
- ~~**IV-05**: Constructor factores FI-006 Calidad del aire y FI-014 Ruido desde Fase 2/Fase 4 offline~~ — **COMPLETADO ✅ 2026-04-30**
- ~~**IV-06**: Constructor factores FI-009 ENP y FI-010 Red Natura 2000 desde Fase 4 offline~~
- ~~**IV-07**: Constructor factores FI-002 Geología, FI-003 Suelos y FI-004 Hidrología desde Fase 4 offline~~ — **COMPLETADO ✅ 2026-05-01** (119 tests OK, `has_geology/soil/hydrology_source_planned()` + `build_geology/soil/hydrology_factor_from_phase4()` + `build_physical_inventory_factors_from_phase4()` + `merge_physical_factors_into_summary()` + `PhysicalInventoryBuildResult`, FI-002/FI-003/FI-004 ESTIMADO/AMARILLO si hay plan/ubicación, GAP-FI-002-001 MEDIA/GABINETE, GAP-FI-003-001 MEDIA/CAMPO, GAP-FI-004-001 ALTA con MAP-006/MEDIA sin él, nunca VERDE, sin IGME/SIGPAC/SNCZI/IA, 3043 suite OK, 12 skipped) — **COMPLETADO ✅ 2026-04-30** (108 tests OK, `has_red_natura_map_planned()` + `has_enp_map_planned()` + `extract_protected_area_context()` + `build_enp_factor_from_phase4()` + `build_red_natura_factor_from_phase4()` + `build_protected_areas_inventory_factors_from_phase4()` + `merge_protected_area_factors_into_summary()` + `ProtectedAreasInventoryBuildResult`, FI-009/FI-010 ESTIMADO/AMARILLO si hay plan cartográfico, GAP ALTA/GABINETE siempre, nunca VERDE, sin WMS/WMTS/IA, no afirma ausencia de ENP/Red Natura, decisión evaluación de repercusiones → órgano ambiental, integrado en `inventory-build`, 2924 suite OK, 12 skipped) (120 tests OK, `extract_activity_text()` + `detect_air_quality_relevant_operations()` + `detect_noise_relevant_operations()` + `build_air_quality_factor_from_phase_data()` + `build_noise_factor_from_phase_data()` + `build_pressure_inventory_factors_from_phase_data()` + `merge_pressure_factors_into_summary()` + `PressureInventoryBuildResult`, detección por términos en operaciones declaradas, FI-006 ROJO_AMARILLO si alta presión sin filtro/AMARILLO si filtro, FI-014 ROJO_AMARILLO/CAMPO_NECESARIO si maquinaria pesada, GAP-FI-006-001 ALTA/CAMPO siempre, GAP-FI-014-001 ALTA o MEDIA/CAMPO siempre, nunca VERDE, sin WMS/IA, integrado en `inventory-build`)
- ~~**IV-08**: Constructor factor FI-015 Cambio climático desde Fase 2/Fase 4 offline~~ — **COMPLETADO ✅ 2026-05-01**
- ~~**F5-01**: Gate de cierre de Fase 5 / Inventario ambiental offline~~ — **COMPLETADO ✅ 2026-05-02**
- ~~**IM-00**: Modelo base de impactos, medidas y PVA~~ — **COMPLETADO ✅ 2026-05-03**
- ~~**IM-01**: Motor de valoración Conesa~~ — **COMPLETADO ✅ 2026-05-03**
- ~~**IM-02**: Constructor de acciones del proyecto desde Fase 2~~ — **COMPLETADO ✅ 2026-05-04**
- ~~**IM-03**: Identificador preliminar de impactos acción × receptor~~ — **COMPLETADO ✅ 2026-05-05**
- ~~**IM-04**: Asignador prudente de atributos Conesa para impactos identificados~~ — **COMPLETADO ✅ 2026-05-06** (86 tests OK, `ConesaAssignmentRule` + `matches()` + `ConesaAssignmentResult` + `default_conesa_assignment_rules()` (10 reglas CASSIGN-A…CASSIGN-J) + `assign_conesa_attributes_to_impact()` + `assign_conesa_attributes_to_model()`, tablas tipológicas R12/R13, INDETERMINADO para ENP/Flora/Fauna/Paisaje/Patrimonio/ClimaCambio, scoring vía IM-01, CLI `phase6-assign-conesa [--write] [--no-score]`, sin IA/web/creación-impactos/medidas/PVA, 3952 suite OK, 12 skipped) (96 tests OK, `ImpactIdentificationRule` + `matches()` + `ImpactIdentificationResult` + `default_impact_identification_rules()` (10 reglas RULE-A…RULE-J) + `build_minimal_receptor_factors()` + `identify_impacts_from_model()` + `merge_identified_impacts_into_model()` + `build_phase6_model_with_identified_impacts()`, status PENDIENTE_DATOS/INDETERMINADO, significancia NO_VALORADO, elevación a INDETERMINADO con critical_gaps, CLI `phase6-identify-impacts [--write]`, sin IA/web/Conesa/medidas/PVA, 3866 suite OK, 12 skipped) (106 tests OK, `ProjectActionBuildResult` + `extract_project_action_text()` + `detect_project_operations()` (7 grupos) + `build_actions_from_phase2_data()` + `merge_actions_into_phase6_model()` + `build_phase6_model_with_actions()`, normalización UTF-8 sin acentos, detección LER con regex, acción mínima si sin detección, CLI `phase6-actions [--write]`, sin IA/web/impactos/medidas/PVA, 3770 suite OK, 12 skipped) (77 tests OK, `ConesaScoreResult` + `calculate_conesa_score()` + `classify_conesa_score()` + `validate_conesa_attributes()` + `apply_conesa_to_impact(with_measures)` + `score_phase6_impacts()`, fórmula I=3·IN+2·EX+resto×1, umbrales <25/25-49/50-74/≥75, CONESA_MIN=1/MAX=12, no mutación con `dataclasses.replace()`, sin IA/web/asignación automática, 3664 suite OK, 12 skipped) (144 tests OK, `ProjectAction` + `ReceptorFactor` + `ConesaAttributes` + `EnvironmentalImpact` + `MitigationMeasure` + `PVAProgram` + `Phase6Model`, constantes dominio Fase 6, reglas AG09-13/AG09-14 en `validate()`, regla de no compensación positivos, `build_receptor_factors_from_inventory()` + `build_empty_phase6_model()`, sin IA/web/CLI/escritura de archivos, 3587 suite OK, 12 skipped) (75 tests OK, `Phase5GateIssue` + `Phase5GateResult` + `evaluate_phase5_gate()` + `evaluate_phase5_gate_from_inventory_json()` + `build_phase5_gate_markdown()` + `write_phase5_gate_outputs()`, decisiones APTO_FASE6/APTO_FASE6_CON_CAUTELAS/NO_APTO_FASE6, 12 tipos de issue ERROR/WARNING/INFO, `administrative_ready` siempre False, CLI `inventory-gate [--write] [--prod]`, offline típico → APTO_CON_CAUTELAS, 3506 suite OK, 12 skipped) (126 tests OK, `extract_climate_change_context()` + `detect_ghg_relevant_sources()` + `detect_climate_vulnerability_terms()` + `build_climate_change_factor_from_phase_data()` + `build_climate_change_inventory_factor_from_phase4()` + `merge_climate_change_factor_into_summary()` + `ClimateChangeInventoryBuildResult`, FI-015 DECLARADO si clima CL-06 + actividad / ESTIMADO si solo uno / PENDIENTE si ninguno, ROJO_AMARILLO con diesel/generador/caldera/camión, GAP-FI-015-001 ALTA si combustión/MEDIA si no / GABINETE, GAP-FI-015-002 MEDIA/GABINETE siempre, nunca VERDE, sin cuantificación de emisiones/huella de carbono/IA, 3169 suite OK, 12 skipped)
- ~~**IV-09**: Constructor factor FI-012 Patrimonio cultural desde Fase 2/Fase 4 offline~~ — **COMPLETADO ✅ 2026-05-01** (119 tests OK, `extract_heritage_context()` + `detect_heritage_mentions()` + `build_heritage_factor_from_phase_data()` + `build_heritage_inventory_factor_from_phase4()` + `merge_heritage_factor_into_summary()` + `HeritageInventoryBuildResult`, FI-012 DECLARADO si promotor declara info patrimonial / ESTIMADO si ubicación o menciones / PENDIENTE si sin datos, ROJO_AMARILLO con BIC/yacimiento/arqueología detectados, GAP-FI-012-001 ALTA/GABINETE siempre, GAP-FI-012-002 ALTA/GABINETE si menciones, nunca VERDE, no afirma ausencia de patrimonio, sin consulta a inventarios/IA, 3288 suite OK, 12 skipped) — **NUEVO ítem**, no existía en backlog original
- ~~**IV-10**: Constructor factores FI-007 Flora y FI-008 Fauna desde Fase 2/Fase 4 offline~~ — **COMPLETADO ✅ 2026-05-02** (155 tests OK, `extract_biodiversity_context()` + `detect_flora_mentions()` + `detect_fauna_mentions()` + `has_biodiversity_related_context()` + `build_flora_factor_from_phase_data()` + `build_fauna_factor_from_phase_data()` + `build_biodiversity_inventory_factors_from_phase_data()` + `merge_biodiversity_factors_into_summary()` + `BiodiversityInventoryBuildResult`, FI-007/FI-008 DECLARADO si promotor declara bio / ESTIMADO si ubicación/contexto ENP / PENDIENTE si sin datos, ROJO_AMARILLO con flora/fauna/hábitat/nidificación detectados, CAMPO_NECESARIO con menciones, GAP-FI-007-001 y GAP-FI-008-001 ALTA con Red Natura/menciones / MEDIA en general, GAP-002 ALTA/CAMPO si menciones, nunca VERDE, no afirma ausencia de flora ni fauna, sin WMS/bancos biodiversidad/IA, 3443 suite OK, 12 skipped) — **NUEVO ítem**, no existía en backlog original
- ~~**IM-05**: Generador de medidas ambientales por tipo de impacto~~ — **COMPLETADO ✅ 2026-05-06** (93 tests OK, `MeasureGenerationRule` + `matches()` + `MeasureGenerationResult` + `default_measure_generation_rules()` (16 reglas MGEN-A…MGEN-P cubriendo FR-003/004/006/007/008/009/010/011/012/013/014/015/016) + `generate_measures_for_impact()` + `generate_measures_for_model()` + `merge_measures_into_model()`, todas las reglas aplican (no first-wins), deduplicación por (name, type), DIAGNOSTICA+PRL_NO_EIA en _NON_REDUCING_MEASURE_TYPES, 16 reglas: 4×FR-014-ruido/2×FR-006-aire/2×FR-003-suelos/1×FR-004-hidro/1×FR-005+016-riesgos/1×FR-009+010-ENP/1×FR-007+008-biodiversidad/1×FR-012-patrimonio/1×FR-011-paisaje/1×FR-015-climacambio/1×FR-013-socioeco-solo-POSITIVO, sin IA/web/modificación-significancia/PVA, CLI `phase6-generate-measures [--write]`, 4045 suite OK, 12 skipped)
- ~~**IM-06**: Fichas PVA~~ — **COMPLETADO ✅ 2026-05-09** (82 tests OK, `PVAGenerationRule` + `PVAGenerationResult` + `default_pva_generation_rules()` (11 reglas PVAGEN-A…PVAGEN-K) + `generate_pva_for_model()` + `merge_pva_into_model()` + `_build_annual_review_pva()`, un PVA por receptor, ficha revisión anual global siempre, E-9 CONDICIONADO por CONTs, E-10 incertidumbre en positivos con gaps, GAP-PVA-001 Responsable Ambiental en todas las fichas, nota remisión órgano ambiental obligatoria, `uncovered_impact_ids` para gaps de cobertura, CLI `phase6-generate-pva [--write]`, outputs `fase6/phase6_model_with_pva.json` + `fase6/pva_generation_result.json`, sin IA/web/WMS, 4190 suite OK, 12 skipped)

- ~~**IM-07**: Validador de cobertura PVA~~ — **COMPLETADO ✅ 2026-05-10** (ver entrada anterior en semana 7-8)
- ~~**IM-08**: Generador sección C.5 acumulativos/sinérgicos~~ — **COMPLETADO ✅ 2026-05-12** (91 tests OK, `build_cumulative_synergistic_section()` + `detect_cumulative_impact_groups()` + `detect_synergistic_impact_groups()` + `extract_unresolved_cumulative_gaps()` + `build_cumulative_synergistic_markdown()` + `write_cumulative_synergistic_outputs()`, 5 pares sinérgicos, texto prudente C.5.1–C.5.5, nunca "no existen efectos", CLI `phase6-cumulative [--write]`, `docs/CUMULATIVE_SYNERGISTIC_SECTION.md`, 4380 suite OK, 12 skipped) (99 tests OK, `PVACoverageIssue` + `PVACoverageResult` + `impact_requires_pva()` + `find_pva_coverage_for_impact()` + `validate_pva_coverage()` + `build_pva_coverage_markdown()` + `validate_pva_coverage_from_json()` + `write_pva_coverage_outputs()`, cobertura DIRECT/BY_FACTOR/TRANSVERSAL, revisión anual excluida, 8 códigos incidencia PVA-COV-E/W/I, CLI `phase6-validate-pva [--write]`, exit 0/1, `docs/PVA_COVERAGE_VALIDATOR.md`, 4289 suite OK, 12 skipped) — ID canónico asignado por usuario (era IM-08 en backlog); IM-08 reservado para C.5 acumulativos/sinérgicos

#### Semana 8-9: Auditoría programática
- ~~**AU-01**: Checklist art.45 como código~~ — **COMPLETADO ✅ 2026-05-14** (81 tests OK, `Art45ChecklistItem` + `Art45ChecklistIssue` + `Art45ChecklistResult` + `evaluate_art45_checklist_from_model()` + `evaluate_art45_checklist_from_files()` + `build_art45_checklist_markdown()` + `write_art45_checklist_outputs()`, 12 requisitos ART45-01…ART45-12, CUBIERTO/PARCIAL/NO_CUBIERTO/NO_APLICA, administrative_ready siempre False, CLI `audit-art45 [--write]`, `docs/ART45_CHECKLIST.md`, 4461 suite OK)
- ~~**AU-02**: Validador regla prudencia (incluye anti-despreciable RD-05)~~ — **COMPLETADO ✅ 2026-05-14** (109 tests OK, `PrudenceIssue` + `PrudenceValidationResult` + `find_forbidden_phrases()` + `validate_inventory_prudence()` + `validate_phase6_prudence()` + `validate_markdown_prudence()` + `validate_prudence_from_files()` + `build_prudence_report_markdown()` + `write_prudence_validation_outputs()`, 8 categorías, contexto metodológico ±150 chars, AU02-E001/E002/E003/W001/W002/I001, CLI `audit-prudence [--write]`, `docs/PRUDENCE_VALIDATOR.md`)
- ~~**AU-03**: Validador trazabilidad HC↔DA~~ — **COMPLETADO ✅ 2026-05-14** (117 tests OK, `TraceabilityReference` + `TraceabilityIssue` + `TraceabilityResult` + `normalize_traceability_text()` + `extract_traceability_references_from_dict()` + `load_traceability_references()` + `extract_claims_from_markdown()` + `claim_has_traceability()` + `validate_markdown_traceability()` + `validate_traceability_from_files()` + `build_traceability_report_markdown()` + `write_traceability_validation_outputs()`, 4 estados TRAZADO/PARCIAL/NO_TRAZADO/NO_APLICA, 16 factores, 16 fuentes JSON, CLI `audit-traceability [--write]`, `docs/TRACEABILITY_VALIDATOR.md`)
- ~~**AU-04**: Informe auditoría JSON+MD~~ — **COMPLETADO ✅ 2026-05-15** (104 tests OK, `FinalAuditIssue` + `FinalAuditResult` + `load_audit_json()` + `extract_final_issues_from_art45/prudence/traceability()` + `determine_final_audit_status()` + `build_final_audit_result()` + `build_final_audit_from_files()` + `build_final_audit_report_markdown()` + `write_final_audit_outputs()`, 4 estados, 5 severidades BLOQUEANTE/ALTA/MEDIA/BAJA/INFO, combina AU-01+AU-02+AU-03, CLI `audit-final [--write]`, exit 0/1, `docs/FINAL_AUDIT_REPORT.md`)
- ~~**PIPE-01**: Pipeline tecnico automatico F5->AU-04~~ — **COMPLETADO ✅ 2026-05-15** (72 tests OK, 13 pasos, `TechnicalPipelineStepResult` + `TechnicalPipelineResult` + `run_technical_pipeline()` + `build_technical_pipeline_markdown()` + `write_pipeline_outputs()`, stop_on_error, dry-run, mode TEST/PROD, CLI `run-technical-pipeline [--write] [--prod] [--continue-on-error]`, exit 0/1, `docs/TECHNICAL_PIPELINE.md`, 4875 suite OK)
- ~~**QA-01**: Saneamiento suite completa post AU-04~~ — **COMPLETADO ✅ 2026-05-15** (suite 4803 OK, 155 skipped, 0 failures, 0 errors. Corregidos: `↔` cp1252 en argparse, pytest→unittest en test_phase5_gate (75 tests recuperados), matplotlib guard en test_climogram_generator/test_climogram_docx_inserter/test_phase4_climate_pipeline, requests guard en test_aemet_client, climograma opcional en phase4_climate_pipeline.py con try/except ImportError + fix Path(None) en nota de outputs)
- ~~**QA-02**: Prueba end-to-end del pipeline sobre copia temporal de NAVE-222~~ — **COMPLETADO ✅ 2026-05-15** (13/13 pasos OK, 3 bugs corregidos: `result.sections`→`cumulative_groups/synergistic_groups`, `result.total_factors`→`result.factor_count`, `dry_months_gaussen` int/list. Suite 4875 OK. `control_interno/qa02_prueba_end_to_end_pipeline.md`)
- ~~**RD-04**: Validador coherencia entre bloques~~ — **COMPLETADO ✅ 2026-05-17** (121 tests OK, `src/eia_agent/core/block_consistency_validator.py`, 7 validadores: Red Natura/biodiversidad/patrimonio/medidas-PRL/ATs/PVA/conclusiones, CLI `audit-block-consistency [--write]`, suite 5106 OK, `docs/BLOCK_CONSISTENCY_VALIDATOR.md`)

#### Semana 9: Validadores OBS-M12 (componente código — prompts ya hechos)
- ~~RD-02: Anti-hiperbolización~~ — **DONE** (Etapa 1 corta)
- ~~**OB-04** código: función `verificar_visibilidad_gaps_a1` en AU-01~~ — **COMPLETADO ✅ 2026-04-23** (65 tests OK, `check_block_a_gap_visibility()` + `GapVisibilityResult`, código explícito en A.1/A.3.1, 1007 suite OK)
- ~~**OB-05** código: `AsuncionTest`, `AsuncionTestRegistry`, factories, I/O, `assumptions_block_administrative_submission`~~ — **COMPLETADO ✅ 2026-05-17** (110 tests OK, `src/eia_agent/core/assumption_test_system.py`, CLI `assumptions-summary [--write]`, suite 4985 OK, `docs/ASSUMPTION_TEST_SYSTEM.md`)
- ~~**RD-06** código: checker Conesa 10 atributos~~ — **COMPLETADO ✅ 2026-05-17** (89 tests OK, `src/eia_agent/core/conesa_checker.py`, reglas CC-A001…CC-F001 + markdown CC-MD-*, CLI `audit-conesa [--write]`, suite 5195 OK, `docs/CONESA_CHECKER.md`)
- ~~**PIPE-02**: Integrar RD-04 y RD-06 en pipeline técnico y AU-04~~ — **COMPLETADO ✅ 2026-05-17** (pipeline 13→15 pasos: añade AUDIT_BLOCK_CONSISTENCY + AUDIT_CONESA; AU-04 acepta `block_consistency_data`/`conesa_check_data`, None → sin issue (backward compat.); 6 tests nuevos `TestNewAuditStepsPIPE02`; suite 5235 OK)
- ~~**PIPE-03**: Integrar RD-08 y RD-09 en pipeline técnico y AU-04~~ — **COMPLETADO ✅ 2026-05-18** (pipeline 15→17 pasos: añade AUDIT_DIAGNOSTIC_MEASURES + AUDIT_PRL_MEASURES; AU-04 acepta `diagnostic_measure_data`/`prl_measure_data`, None → sin issue; 11 tests `TestNewAuditStepsPIPE03`; markdown AU-04 pasa de 11→13 secciones; suite 5482 OK)
- ~~**QA-03**: Prueba end-to-end pipeline 17 pasos sobre copia NAVE-222~~ — **COMPLETADO ✅ 2026-05-18** (17/17 OK, 0 bugs de código, 2 incidencias documentadas, suite 5482 OK, `control_interno/qa03_prueba_end_to_end_pipeline_17steps.md`)
- ~~**DOC-00**: Manifest del Documento Ambiental~~ — **COMPLETADO ✅ 2026-05-18** (63 tests OK, `src/eia_agent/core/document_manifest.py`, bloques A-K READY/PARTIAL/MISSING, CLI `document-manifest [--write]`, corrección `phase6_model_scored`→`phase6_model_with_conesa` en 6 fuentes+docs, suite 5545 OK, `docs/DOCUMENT_MANIFEST.md`) (17/17 OK, 0 bugs de código, 2 incidencias documentadas: input fase4 faltante + nombre spec, suite 5482 OK, `control_interno/qa03_prueba_end_to_end_pipeline_17steps.md`) (pipeline 15→17 pasos: añade AUDIT_DIAGNOSTIC_MEASURES + AUDIT_PRL_MEASURES; AU-04 acepta `diagnostic_measure_data`/`prl_measure_data`, None → sin issue; 11 tests `TestNewAuditStepsPIPE03`; markdown AU-04 pasa de 11→13 secciones; suite 5482 OK)
- ~~**DOC-01**: Generador Markdown del Documento Ambiental~~ — **COMPLETADO ✅ 2026-05-18** (108 tests OK, `src/eia_agent/core/document_markdown_builder.py`, bloques A-K GENERATED/PARTIAL/MISSING, `DocumentBlockBuildResult`+`DocumentMarkdownBuildResult`, 11 builders A-K, `assemble_document_markdown`, `build_document_markdown(write_outputs)`, CLI `document-build-md [--write]`, exit 0 si no MISSING, sin IA/web/DOCX, suite 5653 OK, `docs/DOCUMENT_MARKDOWN_BUILDER.md`)
- ~~**DOC-02**: Generador DOCX del Documento Ambiental desde Markdown~~ — **COMPLETADO ✅ 2026-05-19** (99 tests OK, `src/eia_agent/core/document_docx_builder.py`, `parse_markdown_blocks` 9 tipos, portada+TOC+estilos, `add_markdown_block_to_docx`, `build_docx_from_markdown`, `build_docx_from_expediente`, `validate_docx_basic`, CLI `document-build-docx [--write]`, sin IA/web/PDF, suite 5752 OK, `docs/DOCUMENT_DOCX_BUILDER.md`)
- ~~**QA-04**: Prueba end-to-end generación documental Markdown + DOCX~~ — **COMPLETADO ✅ 2026-05-20**
- ~~**DOC-03**: Inserción de figuras, mapas, climogramas y anexos gráficos en DOCX~~ — **COMPLETADO ✅ 2026-05-20** (90 tests OK tras bug fix QA-05, `document_figure_inserter.py`, 6 tipos MAPA/CLIMOGRAMA/FOTOGRAFIA/LOGO/GRAFICO/OTRO, 8 dirs de busqueda incluye `mapas/`, `discover_document_figures`, `add_figures_annex_to_docx`, `insert_figures_into_document`, CLI `document-insert-figures [--write]`, sin IA/web/PDF, suite 5841 OK, `docs/DOCUMENT_FIGURE_INSERTER.md`)
- ~~**QA-05**: Prueba end-to-end con figuras reales de NAVE-222~~ — **COMPLETADO ✅ 2026-05-20** (6/6 mapas reales detectados+clasificados MAPA, DOCX 1380→1715 KB, heading "Anexo grafico y cartografico" + 6 captions FIG-001..FIG-006 verificados, DOCX base sin modificar, 0 warnings, 1 bug corregido `mapas/` en FIGURE_SOURCE_DIRS, suite 5841 OK, `control_interno/qa05_prueba_figuras_reales_nave222.md`)
- ~~**DOC-04**: Control de calidad del paquete documental final~~ — **COMPLETADO ✅ 2026-05-20** (118 tests OK, `document_quality_checker.py`, `DocumentQualityIssue`, `DocumentQualityResult`, 5 funciones de check, 15 codigos QC-E/W/I, `detect_blocks_in_text` tolerante A-K, `check_no_administrative_ready_claim` con negacion, `run_document_quality_check`, `build_document_quality_report_markdown`, `write_document_quality_outputs`, CLI `document-qc [--write]`, sin IA/web/PDF, no modifica DOCX/MD, suite 5960 OK, `docs/DOCUMENT_QUALITY_CHECKER.md`)
- ~~**QA-06**: Prueba real del QC documental sobre DOCX enriquecido~~ — **COMPLETADO ✅ 2026-05-21** (copia QA-05 reutilizada, 11/11 archivos presentes, DOCX enriquecido seleccionado, bloques A-K 11/11, captions FIG-001..FIG-006 verificados, 0 warnings, 1 error real QC-E006 correctamente detectado — gap de DOC-01 documentado, archivos fuente sin modificar, suite 5960 OK, `control_interno/qa06_prueba_qc_documental_real.md`)
- ~~**DOC-05**: Visibilidad obligatoria del estado de auditoria final~~ — **COMPLETADO ✅ 2026-05-21** (causa raiz: "NO_CONFORME" normaliza a "no_conforme" (guion bajo); DOC-01 `build_block_i` ahora escribe "NO CONFORME" (espacio) + aviso prescrito para los 4 estados de auditoria; `build_block_j` J.6 actualizado; DOC-04 `check_final_audit_visibility` ampliado con "no_conforme" en keywords; +18 tests DOC-05 en MD builder + 3 tests DOC-05 en QC; prueba real: QC pasa de NO_CONFORME a OK; suite 5980 OK)
- ~~**DOC-06**: Empaquetador final del Documento Ambiental~~ — **COMPLETADO ✅ 2026-05-25** (68 tests OK, `src/eia_agent/core/document_package_builder.py`, `PackageFile`+`DocumentPackageResult`, `safe_copy_file`+`collect_package_files`+`build_readme_entrega`+`build_package_report_markdown`+`build_document_package`+`write_package_build_outputs`, CLI `document-package [--write] [--overwrite]`, genera `documento/paquete_entrega/` con 4 secciones + README_ENTREGA.md + package_build_result.json/md, sin IA/web/PDF/ZIP/modificacion fuentes, suite 6048 OK, `docs/DOCUMENT_PACKAGE_BUILDER.md`)
- ~~**QA-07**: Prueba real del paquete de entrega sobre NAVE-222~~ — **COMPLETADO ✅ 2026-05-25** (copia QA-05 reutilizada, QC 0 errores 11/11 bloques 6 figuras, dry-run exit 0, `--write` 20 archivos 4 secciones correctas, README_ENTREGA.md con disclaimer, `document_figures_result.md` → 03_anexos_graficos correcto, DOCX con figuras 1.68 MB, sin sensibles/ZIP/PDF/inputs, piloto intacto, suite 6036 OK, `control_interno/qa07_prueba_paquete_entrega_nave222.md`)
- ~~**DOC-07**: Exportacion ZIP y PDF del paquete documental final~~ — **COMPLETADO ✅ 2026-05-25** (80 tests OK, `src/eia_agent/core/document_exporter.py`, `ExportIssue`+`DocumentExportResult`, `find_soffice_executable`+`can_use_word_com`+`create_zip_from_directory`+`convert_docx_to_pdf_with_soffice`+`convert_docx_to_pdf_with_word_com`+`export_pdf_best_effort`+`export_document_package`+`write_export_result_outputs`, CLI `document-export [--write] [--no-pdf] [--overwrite]`, PDF best-effort sin bloquear exit, sin IA/web/modificar fuentes, suite 6128 OK, `docs/DOCUMENT_EXPORTER.md`)
- ~~**QA-08**: Prueba real de exportacion ZIP/PDF sobre NAVE-222~~ — **COMPLETADO ✅ 2026-05-25** (copia QA-07 reutilizada, dry-run exit 0 21 archivos, `--write` ZIP=GENERADO 3.2 MB PDF=SKIPPED_NO_CONVERTER exit 0, `--write --no-pdf` PDF=NOT_REQUESTED exit 0, ZIP 4 secciones rutas relativas sin recursion, JSON `is_success=true`, piloto intacto, suite 6128 OK, `control_interno/qa08_prueba_export_zip_pdf_nave222.md`)
- **IM-06** código: template C.5 en IM-01
- **IM-07** código: módulo propagación cadenas condicionales
- ~~**RD-08** código: check diagnóstico≠reductor~~ — **COMPLETADO ✅ 2026-05-17** (97 tests OK, `src/eia_agent/core/diagnostic_measure_validator.py`, detección diagnóstica por flag/tipo/keyword con negación, 4 reglas RD08-E001/E002/W001/W002, CLI `audit-diagnostic-measures [--write]`, suite 5332 OK, `docs/DIAGNOSTIC_MEASURE_VALIDATOR.md`)
- ~~**RD-09** código: check EIA/PRL~~ — **COMPLETADO ✅ 2026-05-17** (110 tests OK, `src/eia_agent/core/prl_measure_validator.py`, validación modelo + markdown, 4 reglas E001/E002/E003/W001 + 2 MD E001/W001, CLI `audit-prl-measures [--write]`, suite 5442 OK, `docs/PRL_MEASURE_VALIDATOR.md`)

### Entregables P1
1. Repositorio `eia-agent-core/` con módulos Python documentados
2. `config/wms_services.json` con Canarias completo
3. `config/jurisdicciones/canarias.json`
4. `prompts/AG-10/` con bloques A-K separados
5. Script de ejecución de expediente: `run_expediente.py [ID]`
6. Test suite básica: 1 expediente de prueba ejecutable en CI
7. Documentación técnica: README técnico del núcleo

### Riesgos P1
| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| AEMET API rate-limit en CI | Alta | Medio | Mock de respuesta AEMET para tests |
| WMS institucionales sin disponibilidad | Alta | Alto | Tabla de fallbacks + modo sin-mapa degradado |
| python-docx no soporta todos los estilos necesarios | Media | Medio | Investigar con documento test antes de comprometer |
| LLM context window insuficiente para expedientes grandes | Media | Alto | Chunking por fase con serialización a disco |

---

## FASE P2 — AMPLIACIÓN DE COBERTURA Y BACKEND API

**Objetivo**: El sistema cubre más de un tipo de proyecto y más de una jurisdicción. Un técnico ambiental externo puede ejecutar un expediente sin necesidad de conocer el código interno. Existe una API REST invocable desde herramientas externas.

**Prerequisito**: P1 cerrado con al menos un expediente real ejecutado con resultado CONFORME.

**Duración estimada**: 8-12 semanas de desarrollo

### Criterios de éxito P2
- [ ] El sistema ejecuta correctamente al menos 2 tipos de proyecto distintos (R12/R13 + un segundo tipo)
- [ ] El sistema funciona en al menos 2 jurisdicciones (Canarias + una segunda CCAA)
- [ ] Existe API REST documentada con endpoints por fase
- [ ] Un técnico ambiental puede iniciar un expediente via CLI documentada sin leer el código fuente
- [ ] El tiempo de ejecución de las fases 1-4 es inferior a 10 minutos (sin contar LLM)

### Ítems del backlog para P2

#### Módulo de multi-tipología
- NL-08: Config tipológica separada del núcleo
- RD-03: Plantillas tipológicas por tipo de instalación
- TN-02: Base de normativa por tipo y CCAA como JSON
- TN-04: Tabla de órganos competentes multi-CCAA

#### Módulo de multi-jurisdicción
- NL-09: Config por CCAA
- CA-06: Config servicios WMS Andalucía (IECA, RedIA, DERA)
- TN-01: Módulo de consulta normativa online BOE/BOC

#### Backend API
- BE-01: API REST con endpoints por fase (FastAPI recomendado)
- BE-02: Sistema de proyectos (crear/listar/abrir expedientes)
- BE-05: Worker asíncrono para tareas largas (Celery o asyncio)
- BE-06: Logging estructurado de llamadas LLM

#### Completar cobertura de auditoría
- AU-05: Validador de coherencia inter-bloques
- RD-04: Validador de coherencia entre bloques (A↔B, B↔H, I↔H, J↔H)
- IV-04: Validador de regla de prudencia en fichas de inventario

#### Mejoras de ensamblador
- EN-05: TOC automático
- EN-06: Portada parametrizable con logo
- EN-07: Estilos Word conformes a guías de la administración
- EN-08: Pipeline CI/CD para el ensamblador

#### Mejoras de inventario e impactos
- IM-04: PVA genérico para impactos Compatible sin PVA propio
- NL-10: Flujo de solicitud de datos al promotor por criticidad
- OB-03: Resolución interactiva de contradicciones
- IN-04: Parser PDF con OCR

### Entregables P2
1. API REST documentada (`docs/api_reference.md`)
2. CLI de usuario: `eia-agent init`, `eia-agent run-phase`, `eia-agent status`
3. `config/tipologias/`: configuraciones para R12, R13, canteras, industria
4. `config/jurisdicciones/andalucia.json`
5. Guía de usuario técnico (cómo ejecutar un expediente con el sistema)
6. Test suite ampliada: 2+ tipos de proyecto, 2+ jurisdicciones

### Riesgos P2
| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| Normativa cambia mientras se ejecuta un expediente largo | Media | Alto | Fecha de consulta en cada verificación normativa |
| Diferencias de criterio de evaluación entre CCAA | Alta | Alto | Validar con técnico local antes de implementar cada CCAA |
| API REST introduce latencia que rompe flujos de sesión LLM | Baja | Medio | Diseño async desde el principio |

---

## FASE P3 — INTERFAZ DE USUARIO Y ACCESO EXTERNO

**Objetivo**: Un técnico ambiental sin conocimientos de programación puede usar el sistema a través de una interfaz web. El sistema es accesible para múltiples usuarios simultáneos con expedientes aislados.

**Prerequisito**: P2 cerrado con API REST estable. Al menos 3 expedientes reales ejecutados en producción.

**Duración estimada**: 10-16 semanas de desarrollo

### Criterios de éxito P3
- [ ] Un técnico ambiental puede ejecutar un expediente completo sin usar el terminal
- [ ] El sistema soporta múltiples usuarios con expedientes aislados
- [ ] El tiempo de onboarding de un nuevo tipo de proyecto es inferior a 2 semanas de configuración
- [ ] La interfaz cumple accesibilidad WCAG 2.1 AA
- [ ] Existe un sistema de backup automático de expedientes

### Ítems del backlog para P3

#### Frontend básico
- FE-01: Panel de estado del expediente (fases, gates, pendientes)
- FE-02: Formulario de ingesta con carga de documentos
- FE-06: Descarga del DOCX final

#### Frontend avanzado
- FE-03: Visor de mapa interactivo (8 mapas mínimos)
- FE-04: Editor de fichas de inventario
- FE-05: Dashboard de auditoría con historial

#### Multi-usuario e infraestructura
- Autenticación y autorización por expediente
- Base de datos para metadatos de expedientes (PostgreSQL)
- Sistema de backup automático
- Monitorización y alertas (uptime WMS, AEMET API)

### Entregables P3
1. Aplicación web desplegable (Docker Compose o similar)
2. Manual de usuario para técnicos ambientales
3. Documentación de despliegue en servidor propio
4. Sistema de monitorización de servicios externos (WMS, AEMET)

---

## GRÁFICO DE DEPENDENCIAS CRÍTICAS

```
NL-01 (schemas)
  └── NL-02 (validador) ──┐
  └── NL-03 (orquestador) ─┴── NL-04 (gate-checker)
                           └── NL-07 (recuperación sesión)

IN-01 (parser DOCX)
  └── IN-02 (entidades)
        └── IN-03 (evidencias)
              └── OB-01 (ficha objeto)
                    └── OB-02 (validador gate 2)

CA-01 (config WMS)
  └── CA-02 (cliente WMS)
        └── CA-03 (8 mapas) ─── CA-04 (trazabilidad)

EN-01 (python-docx) ←── DESBLOQUEA: EN-02, EN-03, EN-04, EN-05, EN-06, EN-07, CL-05

AU-01 + AU-02 + AU-03 ──► AU-04 (informe auditoría)

BE-01 (API REST) ←── DESBLOQUEA: BE-02, BE-05, FE-01..FE-06
```

---

## MÉTRICAS DE PROGRESO POR FASE

| Métrica | Piloto 1 (PARCELA) | Piloto 2 (NAVE-222) | Objetivo P1 | Objetivo P2 | Objetivo P3 |
|---------|-------------------|---------------------|-------------|-------------|-------------|
| Tipos de proyecto cubiertos | 1 (R12/R13) | 1 (R12/R13, mayor complejidad) | 1 (automatizado) | 3+ | 5+ |
| Jurisdicciones | 1 (Canarias) | 1 (Canarias) | 1 (código) | 3 | Todas CCAA |
| Resultado M-12 | CON OBSERVACIONES | CONFORME EN MODO TEST | CONFORME (código) | CONFORME | CONFORME |
| Intervención manual requerida | Alta (todo LLM) | Alta (todo LLM) — AT system | Baja (solo gate decisions) | Mínima | Ninguna |
| Tiempo de ejecución F1-F6 | 3+ días | 3+ días | <4h | <2h | <1h |
| Cobertura de tests | 0% | 0% | 40% | 70% | 90% |
| Expedientes reales ejecutados | 0 (piloto test) | 0 (piloto test) | 1 | 3+ | 10+ |
| Bugs en ensamblador | 3 (no resueltos) | 0 (resueltos en sesión) | 0 | 0 | 0 |
| Usuarios simultáneos soportados | 1 (LLM) | 1 (LLM) | 1 (CLI) | 5 (API) | N (web) |

---

## DECISIONES DE ARQUITECTURA PARA P1

Estas decisiones deben tomarse antes de iniciar el código de P1:

1. **Lenguaje del núcleo**: Python 3.11+ (confirmado por dependencias: python-docx, jsonschema, requests)
2. **LLM backend**: API Anthropic (Claude claude-sonnet-4-6 por defecto, configurable)
3. **Almacenamiento**: Sistema de archivos local (sin DB para P1; PostgreSQL en P3)
4. **Testing**: pytest + fixtures de expediente de prueba con inputs sintéticos
5. **Config format**: JSON para datos operativos, TOML para configuración del sistema
6. **CLI**: Click o Typer (Python)
7. **Entorno controlado**: requirements.txt + Dockerfile para garantizar reproducibilidad

---

*Documento generado por EIA-Agent v2.1 — Productización — 2026-04-13*
