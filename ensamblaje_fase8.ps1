# EIA-Agent v2.1 - M-11 Ensamblaje DOCX - Fase 8
# Expediente: EIA-2026-RECIMETAL-PARCELA
# Fecha: 2026-04-13
# Modo: TEST

$ErrorActionPreference = "Stop"

$baseDir  = "C:\Users\KitDigital\proyecto-eia\expediente-EIA-2026-RECIMETAL-PARCELA"
$blqDir   = "$baseDir\bloques"
$mapDir   = "$baseDir\mapas"
$outDir   = "$baseDir\output"
$tmpDir   = "$env:TEMP\eia_docx_$(Get-Random)"
$outFile  = "$outDir\DA_RECIMETAL_PARCELA_v1.docx"

$blqOrder = @(
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
    "K_referencias.md"
)
# 00_triaje: documento interno de trabajo, se coloca como apendice al final
$blqInterno = "00_triaje.md"

# ── Crear estructura temporal ────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path "$tmpDir\word\media" | Out-Null
New-Item -ItemType Directory -Force -Path "$tmpDir\word\_rels"  | Out-Null
New-Item -ItemType Directory -Force -Path "$tmpDir\_rels"       | Out-Null

# ── Helpers ──────────────────────────────────────────────────────────────────
function XE([string]$s) {
    $s -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' -replace '"','&quot;'
}

function InlineML([string]$text) {
    $sb  = [System.Text.StringBuilder]::new()
    $rem = $text
    while ($rem.Length -gt 0) {
        $m = [regex]::Match($rem, '\*\*(.+?)\*\*')
        if ($m.Success) {
            if ($m.Index -gt 0) {
                $before = XE $rem.Substring(0, $m.Index)
                [void]$sb.Append("<w:r><w:t xml:space=`"preserve`">$before</w:t></w:r>")
            }
            $bold = XE $m.Groups[1].Value
            [void]$sb.Append("<w:r><w:rPr><w:b/></w:rPr><w:t xml:space=`"preserve`">$bold</w:t></w:r>")
            $rem = $rem.Substring($m.Index + $m.Length)
        } else {
            [void]$sb.Append("<w:r><w:t xml:space=`"preserve`">$(XE $rem)</w:t></w:r>")
            break
        }
    }
    return $sb.ToString()
}

function IsTableSep([string]$l) { $l -match '^\|[\s\-\|:]+\|$' }
function IsTableRow([string]$l) { $l -match '^\s*\|' }

function TblRow([string]$line, [bool]$hdr) {
    $cells = $line -split '\|' | Where-Object { $_ -ne '' -and $_ -ne $null }
    $tr = "<w:tr>"
    foreach ($c in $cells) {
        $ct = $c.Trim()
        if ($hdr) {
            $tr += "<w:tc><w:tcPr><w:shd w:val=`"clear`" w:color=`"auto`" w:fill=`"D0D8E8`"/></w:tcPr>"
            $tr += "<w:p><w:pPr><w:jc w:val=`"center`"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t xml:space=`"preserve`">$(XE $ct)</w:t></w:r></w:p></w:tc>"
        } else {
            $tr += "<w:tc><w:p>$(InlineML $ct)</w:p></w:tc>"
        }
    }
    $tr += "</w:tr>"
    return $tr
}

function BlockToML([string]$path) {
    $lines    = [System.IO.File]::ReadAllLines($path, [System.Text.Encoding]::UTF8)
    $body     = [System.Text.StringBuilder]::new()
    $inTbl    = $false
    $firstRow = $false
    $tbl      = [System.Text.StringBuilder]::new()
    $tblBord  = '<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders>'

    foreach ($l in $lines) {
        # ── TABLE ──
        if (IsTableRow $l) {
            if (-not $inTbl) {
                $inTbl    = $true
                $firstRow = $true
                [void]$tbl.Clear()
                [void]$tbl.Append("<w:tbl><w:tblPr><w:tblW w:w=`"0`" w:type=`"auto`"/>$tblBord</w:tblPr>")
            }
            if (IsTableSep $l) { $firstRow = $false; continue }
            [void]$tbl.Append((TblRow $l $firstRow))
            $firstRow = $false
            continue
        } else {
            if ($inTbl) {
                [void]$tbl.Append("</w:tbl>")
                [void]$body.Append($tbl.ToString())
                [void]$body.Append("<w:p/>")
                $inTbl = $false
            }
        }

        # ── HEADINGS ──
        if ($l -match '^###\s+(.+)$') {
            [void]$body.Append("<w:p><w:pPr><w:pStyle w:val=`"Heading3`"/></w:pPr>$(InlineML $matches[1])</w:p>")
            continue
        }
        if ($l -match '^##\s+(.+)$') {
            [void]$body.Append("<w:p><w:pPr><w:pStyle w:val=`"Heading2`"/></w:pPr>$(InlineML $matches[1])</w:p>")
            continue
        }
        if ($l -match '^#\s+(.+)$') {
            [void]$body.Append("<w:p><w:pPr><w:pStyle w:val=`"Heading1`"/></w:pPr>$(InlineML $matches[1])</w:p>")
            continue
        }

        # ── HORIZONTAL RULE ──
        if ($l -match '^---+$') {
            [void]$body.Append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="888888"/></w:pBdr></w:pPr></w:p>')
            continue
        }

        # ── BULLET LIST ──
        if ($l -match '^[-\*]\s+(.+)$') {
            [void]$body.Append("<w:p><w:pPr><w:ind w:left=`"720`" w:hanging=`"360`"/></w:pPr><w:r><w:t xml:space=`"preserve`">• $(XE $matches[1])</w:t></w:r></w:p>")
            continue
        }

        # ── NUMBERED LIST ──
        if ($l -match '^\d+\.\s+(.+)$') {
            [void]$body.Append("<w:p><w:pPr><w:ind w:left=`"720`" w:hanging=`"360`"/></w:pPr><w:r><w:t xml:space=`"preserve`">  $(XE $matches[1])</w:t></w:r></w:p>")
            continue
        }

        # ── BLOCKQUOTE ──
        if ($l -match '^>\s*(.*)$') {
            [void]$body.Append("<w:p><w:pPr><w:ind w:left=`"720`"/></w:pPr><w:r><w:rPr><w:i/><w:color w:val=`"555555`"/></w:rPr><w:t xml:space=`"preserve`">$(XE $matches[1])</w:t></w:r></w:p>")
            continue
        }

        # ── CODE BLOCK marker ──
        if ($l -match '^```') { continue }

        # ── EMPTY ──
        if ($l -match '^\s*$') {
            [void]$body.Append("<w:p/>")
            continue
        }

        # ── NORMAL PARAGRAPH ──
        [void]$body.Append("<w:p>$(InlineML $l)</w:p>")
    }

    # cerrar tabla si queda abierta
    if ($inTbl) {
        [void]$tbl.Append("</w:tbl>")
        [void]$body.Append($tbl.ToString())
    }

    return $body.ToString()
}

function ImgXML([string]$rId, [string]$name, [int]$id) {
    $cx = 5400000; $cy = 3600000
    $n  = XE $name
@"
<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="$cx" cy="$cy"/>
<wp:effectExtent l="0" t="0" r="0" b="0"/>
<wp:docPr id="$id" name="$n"/>
<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic><pic:nvPicPr><pic:cNvPr id="$id" name="$n"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="$rId"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="$cx" cy="$cy"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic>
</wp:inline></w:drawing></w:r></w:p>
"@
}

# ── CUERPO DEL DOCUMENTO ─────────────────────────────────────────────────────
$doc = [System.Text.StringBuilder]::new()

# PORTADA
[void]$doc.Append(@'
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="2880"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="56"/><w:szCs w:val="56"/><w:b/><w:color w:val="1F3864"/></w:rPr>
  <w:t>DOCUMENTO AMBIENTAL</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="40"/><w:szCs w:val="40"/><w:b/><w:color w:val="2E74B5"/></w:rPr>
  <w:t>Evaluación de Impacto Ambiental Simplificada</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="40"/><w:szCs w:val="40"/><w:b/><w:color w:val="2E74B5"/></w:rPr>
  <w:t>Art. 7.2.a) Ley 21/2013 &#x2014; Anexo II, Grupo 9 b) y d)</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="480"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="36"/><w:szCs w:val="36"/><w:b/></w:rPr>
  <w:t>RECIMETAL LANZAROTE, S.L.</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="28"/></w:rPr>
  <w:t>NIF: B72798846</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="28"/></w:rPr>
  <w:t>Instalaci&#xF3;n exterior vinculada &#x2014; almacenamiento, clasificaci&#xF3;n</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="28"/></w:rPr>
  <w:t>complementaria y expedici&#xF3;n de residuos met&#xE1;licos no peligrosos</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="480"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="24"/></w:rPr>
  <w:t>RC: 2462302DS4026S0001GQ &#x2014; Pol&#xED;gono Industrial Tenorio, Arrecife, Lanzarote</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="24"/></w:rPr>
  <w:t>Redactor: Claudio Su&#xE1;rez Llarena, Ing. T&#xE9;cnico Industrial Col. n&#xBA; 2167</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="24"/></w:rPr>
  <w:t>Fecha: Marzo 2026</w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="960"/></w:pPr>
  <w:r><w:rPr><w:sz w:val="20"/><w:color w:val="CC0000"/><w:b/></w:rPr>
  <w:t>DOCUMENTO DE TRABAJO &#x2014; MODO TEST &#x2014; v1 &#x2014; 2026-04-13</w:t></w:r></w:p>
<w:p><w:pPr><w:pageBreakBefore/></w:pPr></w:p>
'@)

Write-Host "Portada generada."

# BLOQUES A-K
$blqFailed = @()
foreach ($b in $blqOrder) {
    $bPath = "$blqDir\$b"
    if (Test-Path $bPath) {
        try {
            $content = BlockToML $bPath
            [void]$doc.Append($content)
            [void]$doc.Append('<w:p><w:pPr><w:pageBreakBefore/></w:pPr></w:p>')
            Write-Host "  OK: $b"
        } catch {
            $blqFailed += $b
            [void]$doc.Append("<w:p><w:r><w:rPr><w:color w:val=`"CC0000`"/></w:rPr><w:t>ERROR AL PROCESAR BLOQUE: $(XE $b) - $($_.Exception.Message)</w:t></w:r></w:p>")
            Write-Host "  ERROR: $b - $($_.Exception.Message)"
        }
    } else {
        $blqFailed += $b
        [void]$doc.Append("<w:p><w:r><w:rPr><w:color w:val=`"CC0000`"/></w:rPr><w:t>BLOQUE NO ENCONTRADO: $(XE $b)</w:t></w:r></w:p>")
        Write-Host "  NO ENCONTRADO: $b"
    }
}

# ANEJO CARTOGRÁFICO
[void]$doc.Append('<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore/></w:pPr><w:r><w:t>ANEJO CARTOGR&#xC1;FICO</w:t></w:r></w:p>')
[void]$doc.Append('<w:p><w:r><w:rPr><w:color w:val="555555"/></w:rPr><w:t>Mapas generados autom&#xE1;ticamente mediante servicios WMS (Fase 4A). Ver trazabilidad en capas/cartografia_trace.json.</w:t></w:r></w:p>')
[void]$doc.Append('<w:p/>')

$mapFiles   = Get-ChildItem $mapDir -File | Where-Object { $_.Extension -match '\.(png|jpg|jpeg)$' } | Sort-Object Name
$imgRels    = @()
$imgInserted = @()
$imgFailed  = @()
$rIdBase    = 10
$imgIdBase  = 100

$idx = 0
foreach ($img in $mapFiles) {
    $idx++
    $rId      = "rId$($rIdBase + $idx)"
    $imgId    = $imgIdBase + $idx
    $mediaFn  = $img.Name
    $dst      = "$tmpDir\word\media\$mediaFn"

    try {
        Copy-Item $img.FullName $dst -Force
        $ext  = $img.Extension.ToLower().TrimStart('.')
        $mime = if ($ext -eq "jpg" -or $ext -eq "jpeg") { "image/jpeg" } else { "image/png" }
        $imgRels += "<Relationship Id=`"$rId`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image`" Target=`"media/$mediaFn`"/>"

        $caption = $img.BaseName -replace '_', ' '
        [void]$doc.Append("<w:p><w:pPr><w:pStyle w:val=`"Heading2`"/></w:pPr><w:r><w:t>$(XE $caption)</w:t></w:r></w:p>")
        [void]$doc.Append((ImgXML $rId $img.Name $imgId))
        [void]$doc.Append('<w:p/>')

        $imgInserted += $img.Name
        Write-Host "  IMG OK: $($img.Name)"
    } catch {
        $imgFailed += "$($img.Name): $($_.Exception.Message)"
        [void]$doc.Append("<w:p><w:r><w:rPr><w:color w:val=`"FF8800`"/></w:rPr><w:t>Imagen no insertada: $(XE $img.Name). Consultar carpeta mapas/.</w:t></w:r></w:p>")
        Write-Host "  IMG ERROR: $($img.Name) - $($_.Exception.Message)"
    }
}

# APENDICE INTERNO: Ficha de triaje (00_triaje) — no forma parte del DA
$blqInternoPath = "$blqDir\$blqInterno"
if (Test-Path $blqInternoPath) {
    [void]$doc.Append('<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore/></w:pPr><w:r><w:rPr><w:color w:val="CC0000"/></w:rPr><w:t>APENDICE INTERNO - FICHA DE TRIAJE JURIDICO-PROCEDIMENTAL</w:t></w:r></w:p>')
    [void]$doc.Append('<w:p><w:pPr><w:pBdr><w:top w:val="single" w:sz="12" w:space="1" w:color="CC0000"/><w:bottom w:val="single" w:sz="12" w:space="1" w:color="CC0000"/></w:pBdr><w:shd w:val="clear" w:color="auto" w:fill="FFF0F0"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="CC0000"/></w:rPr><w:t xml:space="preserve">DOCUMENTO INTERNO DE TRABAJO - NO FORMA PARTE DEL TEXTO DEL DOCUMENTO AMBIENTAL. Alimenta la portada, la introduccion y el bloque K (referencias). Para uso exclusivo del equipo redactor y del promotor.</w:t></w:r></w:p>')
    [void]$doc.Append('<w:p/>')
    try {
        $internoContent = BlockToML $blqInternoPath
        [void]$doc.Append($internoContent)
        Write-Host "  OK (apendice interno): $blqInterno"
    } catch {
        Write-Host "  ERROR apendice interno: $($_.Exception.Message)"
    }
}

# Pie de documento
[void]$doc.Append('<w:p/>')
[void]$doc.Append('<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:sz w:val="18"/><w:color w:val="888888"/></w:rPr><w:t>&#x2014; Fin del Documento Ambiental &#x2014;</w:t></w:r></w:p>')
[void]$doc.Append('<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:sz w:val="18"/><w:color w:val="888888"/></w:rPr><w:t>EIA-Agent v2.1 &#x2014; EIA-2026-RECIMETAL-PARCELA &#x2014; Modo test</w:t></w:r></w:p>')

# Sección de página: A4
[void]$doc.Append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1417" w:right="1134" w:bottom="1134" w:left="1701" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>')

Write-Host "Cuerpo ensamblado."

# ── XML COMPONENTS ───────────────────────────────────────────────────────────

$documentXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
$($doc.ToString())
  </w:body>
</w:document>
"@

$stylesXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
      <w:lang w:val="es-ES"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr>
      <w:spacing w:after="160" w:line="259" w:lineRule="auto"/>
    </w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Normal" w:default="1">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="160"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:outlineLvl w:val="0"/>
      <w:spacing w:before="360" w:after="120"/>
      <w:keepNext/>
      <w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="1F3864"/></w:pBdr>
    </w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/><w:color w:val="1F3864"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:outlineLvl w:val="1"/>
      <w:spacing w:before="240" w:after="80"/>
      <w:keepNext/>
    </w:pPr>
    <w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/><w:color w:val="2E74B5"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/><w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:outlineLvl w:val="2"/>
      <w:spacing w:before="160" w:after="60"/>
      <w:keepNext/>
    </w:pPr>
    <w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/><w:color w:val="5B9BD5"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720"/></w:pPr>
  </w:style>
</w:styles>
'@

$settingsXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:compat>
    <w:compatSetting w:name="compatibilityMode"
      w:uri="http://schemas.microsoft.com/office/word"
      w:val="15"/>
  </w:compat>
</w:settings>
'@

$relsXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>
'@

$docRelsXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"   Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"  Target="settings.xml"/>
$($imgRels -join "`n")
</Relationships>
"@

$ctXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels"  ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"   ContentType="application/xml"/>
  <Default Extension="png"   ContentType="image/png"/>
  <Default Extension="jpeg"  ContentType="image/jpeg"/>
  <Default Extension="jpg"   ContentType="image/jpeg"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>
'@

# ── ESCRITURA DE ARCHIVOS XML ────────────────────────────────────────────────
$enc = [System.Text.UTF8Encoding]::new($false)  # UTF-8 sin BOM

[System.IO.File]::WriteAllText("$tmpDir\[Content_Types].xml",      $ctXml,        $enc)
[System.IO.File]::WriteAllText("$tmpDir\_rels\.rels",               $relsXml,      $enc)
[System.IO.File]::WriteAllText("$tmpDir\word\document.xml",         $documentXml,  $enc)
[System.IO.File]::WriteAllText("$tmpDir\word\styles.xml",           $stylesXml,    $enc)
[System.IO.File]::WriteAllText("$tmpDir\word\settings.xml",         $settingsXml,  $enc)
[System.IO.File]::WriteAllText("$tmpDir\word\_rels\document.xml.rels", $docRelsXml, $enc)

Write-Host "Archivos XML escritos."

# ── EMPAQUETAR DOCX ──────────────────────────────────────────────────────────
Add-Type -Assembly System.IO.Compression.FileSystem
if (Test-Path $outFile) { Remove-Item $outFile -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tmpDir, $outFile)
Write-Host "DOCX generado: $outFile"

# Verificar tamaño
$size = (Get-Item $outFile).Length
Write-Host "Tamaño: $([math]::Round($size/1KB, 1)) KB"

# Limpiar temp
Remove-Item $tmpDir -Recurse -Force

# ── RESUMEN ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== RESULTADO FASE 8 ==="
Write-Host "Archivo: $outFile"
Write-Host "Bloques procesados: $($blqOrder.Count - $blqFailed.Count) / $($blqOrder.Count)"
if ($blqFailed.Count -gt 0) { Write-Host "Bloques fallidos: $($blqFailed -join ', ')" }
Write-Host "Imágenes insertadas ($($imgInserted.Count)): $($imgInserted -join ', ')"
if ($imgFailed.Count -gt 0) { Write-Host "Imágenes fallidas: $($imgFailed -join '; ')" }
Write-Host "Tamaño DOCX: $([math]::Round($size/1KB, 1)) KB"
Write-Host ""
Write-Host "FASE 8 COMPLETADA - APTA PARA PASAR A FASE 9 EN MODO TEST"
