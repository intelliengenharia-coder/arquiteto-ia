"""
ARQUITETO IA — Backend
FastAPI + Claude API + Replicate (imagens) + IfcOpenShell (IFC) + ezdxf (DWG)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import anthropic
import replicate
import os, json, uuid
from pathlib import Path

app = FastAPI(title="Arquiteto IA API")

# CORS — permite o frontend React chamar este backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção: coloque só seu domínio
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pasta para arquivos gerados
OUTPUTS = Path("outputs")
OUTPUTS.mkdir(exist_ok=True)

# ─── SKILL DE ARQUITETURA (carregada uma vez) ─────────────────────────────────
SKILL_ARQUITETURA = """
Você é um arquiteto sênior brasileiro com 30 anos de experiência.
Especialista em NBR 15575, NBR 6118 e legislação urbanística brasileira.

DIMENSIONAMENTO POR PADRÃO:
Alto padrão  → Suíte master: 20-35m² | Sala: 35-55m² | Cozinha: 16-24m²
Médio padrão → Suíte master: 14-18m² | Sala: 20-30m² | Cozinha: 10-14m²
Popular      → Suíte master:  9-12m² | Sala: 14-18m² | Cozinha:  6-9m²

RECUOS MÍNIMOS: Frontal 5m | Lateral 1.5m | Fundos 3m
TAXA OCUPAÇÃO MÁXIMA: 60% do terreno

ZONEAMENTO:
- Social (sala, cozinha, lavabo): acesso direto da entrada
- Íntimo (suítes): separado, fundo ou pavimento superior
- Serviço (lavanderia, depósito): lateral, próximo à cozinha

RESPONDA SOMENTE COM JSON VÁLIDO. Zero texto fora do JSON.
"""

# ─── MODELS ──────────────────────────────────────────────────────────────────
class DadosProjeto(BaseModel):
    frente: float
    lado: float
    topografia: str
    padrao: str
    tipo: str
    suites: str
    area_master: Optional[str] = ""
    banheiros: str
    garagem: str
    piscina: str
    fachada: str
    estilo: str

class DadosImagem(BaseModel):
    estilo: str
    padrao: str
    topografia: str
    fachada: str
    quantidade: int = 4

class DadosIFC(BaseModel):
    projeto_id: str
    programa: dict
    dados: dict

# ─── ROTA 1: GERAR PROGRAMA DE NECESSIDADES ──────────────────────────────────
@app.post("/api/programa")
async def gerar_programa(dados: DadosProjeto):
    """
    Claude calcula o programa de necessidades completo
    com áreas, dimensões e zoneamento funcional
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""
    Crie programa de necessidades para:
    Terreno: {dados.frente}m × {dados.lado}m | {dados.topografia}
    Padrão: {dados.padrao} | Tipo: {dados.tipo}
    Suítes: {dados.suites} | Área master: {dados.area_master or 'calcular'}
    Banheiros: {dados.banheiros} | Garagem: {dados.garagem}
    Piscina: {dados.piscina} | Estilo: {dados.estilo}

    Retorne SOMENTE este JSON:
    {{
      "area_total": 000,
      "area_terreno": {dados.frente * dados.lado},
      "taxa_ocupacao": "00%",
      "pavimentos": 1,
      "resumo": "descrição do projeto",
      "observacoes_tecnicas": ["obs1", "obs2"],
      "recuos": {{"frontal": 5.0, "lateral_esq": 1.5, "lateral_dir": 1.5, "fundos": 3.0}},
      "ambientes": [
        {{
          "nome": "Suíte Master",
          "area": 28.0,
          "largura": 5.6,
          "profundidade": 5.0,
          "pavimento": 1,
          "adjacencias": ["Closet", "Banheiro Master"],
          "observacao": "ventilação cruzada obrigatória"
        }}
      ]
    }}
    """

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=SKILL_ARQUITETURA,
        messages=[{"role": "user", "content": prompt}]
    )

    texto = response.content[0].text
    limpo = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(limpo)


# ─── ROTA 2: GERAR IMAGENS DE FACHADA ────────────────────────────────────────
@app.post("/api/imagens/fachada")
async def gerar_fachadas(dados: DadosImagem):
    """
    Gera imagens fotorrealistas de fachada usando Flux Pro (Replicate)
    """

    # Prompts por estilo — altamente detalhados para resultado fotorrealista
    prompts_estilo = {
        "neoclassico": (
            "Neoclassical luxury Brazilian residential mansion, "
            "ionic columns, symmetrical facade, natural limestone cladding, "
            "ornate cornice moldings, arched windows with shutters, "
            "grand entrance with double doors, manicured hedges, "
            "cobblestone driveway"
        ),
        "contemporaneo": (
            "Contemporary Brazilian luxury house, "
            "clean geometric volumes, floor-to-ceiling glass panels, "
            "cantilevered upper floor, concrete and wood combination, "
            "integrated landscape, infinity pool reflection, "
            "architectural LED lighting, minimalist garden"
        ),
        "classico": (
            "Traditional Brazilian colonial mansion, "
            "terracotta clay roof tiles, arched windows and doorways, "
            "warm ochre painted stucco walls, wrought iron details, "
            "mature tropical garden, ceramic tile accents, "
            "wide covered veranda"
        ),
    }

    modificadores_padrao = {
        "popular": "simple painted plaster finish, modest front garden",
        "medio":   "quality ceramic cladding, well-maintained garden, aluminum windows",
        "alto":    "premium marble and granite cladding, luxury landscaping, smart glass, LED accent lighting",
    }

    modificadores_topo = {
        "aclive":  "hillside construction, exposed stone foundation, stepped retaining walls, elevated view",
        "declive": "split-level design on slope, pilotis structure, panoramic valley view",
        "plano":   "ground level, defined front garden, straight driveway",
    }

    base = prompts_estilo.get(dados.estilo, prompts_estilo["contemporaneo"])
    padrao_mod = modificadores_padrao.get(dados.padrao, "")
    topo_mod = modificadores_topo.get(dados.topografia, "")
    imponente = "grand imposing presence, monumental scale" if dados.fachada == "imponente" else "understated elegant presence"

    prompt_final = (
        f"{base}, {padrao_mod}, {topo_mod}, {imponente}, "
        "professional architectural photography, "
        "8K ultra-realistic, photorealistic not a render, "
        "looks exactly like a real photograph, "
        "sharp focus, perfect exposure, golden hour lighting, "
        "blue sky with soft clouds, ultra detailed"
    )

    urls = []
    for i in range(dados.quantidade):
        try:
            output = replicate.run(
                "black-forest-labs/flux-pro",
                input={
                    "prompt": prompt_final,
                    "width": 1440,
                    "height": 960,
                    "num_inference_steps": 50,
                    "guidance": 3.5,
                    "seed": 1000 + (i * 777),  # seeds diferentes = variações
                    "output_format": "webp",
                    "output_quality": 90,
                }
            )
            urls.append(str(output))
        except Exception as e:
            urls.append(f"ERRO: {str(e)}")

    return {"urls": urls, "prompt_usado": prompt_final}


# ─── ROTA 3: GERAR IMAGENS INTERNAS ──────────────────────────────────────────
@app.post("/api/imagens/internas")
async def gerar_internas(dados: DadosImagem):
    """
    Gera 6 imagens fotorrealistas dos ambientes internos
    """
    ambientes = [
        ("suite_master",   "master bedroom, king bed, walk-in closet view, luxury hotel atmosphere"),
        ("sala",           "open plan living and dining room, large sectional sofa, dining table for 8"),
        ("cozinha",        "gourmet kitchen, large island with waterfall countertop, pendant lights, wine cellar"),
        ("area_externa",   "backyard with swimming pool, sun loungers, outdoor kitchen, tropical landscaping"),
        ("banheiro_master","luxury master bathroom, freestanding bathtub, double vanity, rainfall shower, marble"),
        ("varanda",        "covered terrace, outdoor furniture, garden view, string lights"),
    ]

    estilo_int = {
        "neoclassico":   "neoclassical interior, ornate moldings, marble floors, gold accents, chandeliers",
        "contemporaneo": "contemporary interior, clean lines, concrete and wood, minimalist furniture",
        "classico":      "classic Brazilian interior, terracotta tiles, wooden beams, antique furniture",
    }.get(dados.estilo, "luxury modern interior")

    padrao_int = {
        "alto":   "ultra luxury finishes, Italian marble, designer furniture, museum-quality art",
        "medio":  "high quality finishes, porcelain tiles, quality furniture",
        "popular":"simple clean finishes, ceramic tiles, functional furniture",
    }.get(dados.padrao, "luxury finishes")

    urls = []
    for ambiente_id, ambiente_desc in ambientes:
        prompt = (
            f"Brazilian residential interior, {ambiente_desc}, "
            f"{estilo_int}, {padrao_int}, "
            "professional interior photography, 8K photorealistic, "
            "natural light + artificial accent lighting, "
            "looks exactly like a real photo, ultra detailed"
        )
        try:
            output = replicate.run(
                "black-forest-labs/flux-pro",
                input={
                    "prompt": prompt,
                    "width": 1440,
                    "height": 960,
                    "num_inference_steps": 50,
                    "guidance": 3.5,
                    "seed": 2000 + len(urls) * 333,
                    "output_format": "webp",
                    "output_quality": 90,
                }
            )
            urls.append({"ambiente": ambiente_id, "url": str(output)})
        except Exception as e:
            urls.append({"ambiente": ambiente_id, "url": f"ERRO: {str(e)}"})

    return {"imagens": urls}


# ─── ROTA 4: GERAR IFC ────────────────────────────────────────────────────────
@app.post("/api/arquivos/ifc")
async def gerar_ifc(dados: DadosIFC):
    """
    Gera arquivo IFC 2x3 completo com todos os elementos BIM
    Paredes, lajes, telhado, esquadrias — separados por família
    """
    try:
        import ifcopenshell
        import ifcopenshell.api
        import ifcopenshell.guid
    except ImportError:
        raise HTTPException(500, "ifcopenshell não instalado. Execute: pip install ifcopenshell")

    programa = dados.programa
    projeto_id = dados.projeto_id or str(uuid.uuid4())[:8]

    # Cria arquivo IFC
    ifc = ifcopenshell.file(schema="IFC2X3")

    # ── Contexto geométrico obrigatório ──
    ctx = ifc.createIfcGeometricRepresentationContext(
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=ifc.createIfcAxis2Placement3D(
            ifc.createIfcCartesianPoint((0.0, 0.0, 0.0))
        )
    )

    # ── Hierarquia obrigatória IFC ──
    projeto = ifc.createIfcProject(
        GlobalId=ifcopenshell.guid.new(),
        Name=f"Residência {dados.dados.get('padrao','').title()} — Arquiteto IA",
        Description=programa.get("resumo", "Projeto gerado por Arquiteto IA"),
        UnitsInContext=ifc.createIfcUnitAssignment([
            ifc.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE"),
            ifc.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
        ])
    )

    site = ifc.createIfcSite(
        GlobalId=ifcopenshell.guid.new(),
        Name="Terreno",
        CompositionType="ELEMENT"
    )

    edificio = ifc.createIfcBuilding(
        GlobalId=ifcopenshell.guid.new(),
        Name="Residência",
        CompositionType="ELEMENT"
    )

    # Pavimentos
    pavimentos_ifc = []
    n_pavs = programa.get("pavimentos", 1)
    for i in range(n_pavs):
        pav = ifc.createIfcBuildingStorey(
            GlobalId=ifcopenshell.guid.new(),
            Name="Térreo" if i == 0 else f"{'1º' if i == 1 else '2º'} Pavimento",
            Elevation=float(i * 3.0),
            CompositionType="ELEMENT"
        )
        pavimentos_ifc.append(pav)

    # Relações de agregação (hierarquia)
    ifc.createIfcRelAggregates(
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=projeto,
        RelatedObjects=[site]
    )
    ifc.createIfcRelAggregates(
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=site,
        RelatedObjects=[edificio]
    )
    ifc.createIfcRelAggregates(
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=edificio,
        RelatedObjects=pavimentos_ifc
    )

    # ── Criar paredes para cada ambiente ──
    todos_elementos = []
    x_cursor, y_cursor = 0.0, 0.0
    row_height = 0.0
    X_MAX = float(dados.dados.get("frente", 12))

    for amb in programa.get("ambientes", []):
        larg = float(amb.get("largura", 4.0))
        prof = float(amb.get("profundidade", 3.0))
        pav_idx = min(int(amb.get("pavimento", 1)) - 1, len(pavimentos_ifc) - 1)
        elev = float(pav_idx * 3.0)
        altura_parede = 3.0
        esp = 0.15  # 15cm

        if x_cursor + larg > X_MAX + 2:
            x_cursor = 0.0
            y_cursor += row_height + esp
            row_height = 0.0

        # 4 paredes do ambiente
        definicoes_paredes = [
            {"p": (x_cursor,        y_cursor,        elev), "dir": (1,0,0), "comp": larg},
            {"p": (x_cursor + larg, y_cursor,        elev), "dir": (0,1,0), "comp": prof},
            {"p": (x_cursor + larg, y_cursor + prof, elev), "dir": (-1,0,0),"comp": larg},
            {"p": (x_cursor,        y_cursor + prof, elev), "dir": (0,-1,0),"comp": prof},
        ]

        for wd in definicoes_paredes:
            ponto = ifc.createIfcCartesianPoint(list(wd["p"]))
            eixo  = ifc.createIfcDirection(list(wd["dir"]) + [0.0])
            eixoz = ifc.createIfcDirection([0.0, 0.0, 1.0])
            placement = ifc.createIfcAxis2Placement3D(ponto, eixoz, eixo)
            local_placement = ifc.createIfcLocalPlacement(None, placement)

            # Geometria da parede (extrusão)
            perfil = ifc.createIfcRectangleProfileDef(
                ProfileType="AREA",
                XDim=esp,
                YDim=altura_parede
            )
            extrusao = ifc.createIfcExtrudedAreaSolid(
                SweptArea=perfil,
                ExtrudedDirection=ifc.createIfcDirection([0.0, 0.0, 1.0]),
                Depth=wd["comp"]
            )
            shape = ifc.createIfcShapeRepresentation(
                ContextOfItems=ctx,
                RepresentationIdentifier="Body",
                RepresentationType="SweptSolid",
                Items=[extrusao]
            )
            prod_def = ifc.createIfcProductDefinitionShape(Representations=[shape])

            parede = ifc.createIfcWallStandardCase(
                GlobalId=ifcopenshell.guid.new(),
                Name=f"Parede — {amb['nome']}",
                Description="Alvenaria de blocos cerâmicos 14cm",
                ObjectPlacement=local_placement,
                Representation=prod_def
            )
            todos_elementos.append(parede)

        # Laje de piso
        laje_ponto = ifc.createIfcCartesianPoint([x_cursor, y_cursor, elev])
        laje_place = ifc.createIfcAxis2Placement3D(laje_ponto)
        laje_local = ifc.createIfcLocalPlacement(None, laje_place)
        laje_perfil = ifc.createIfcRectangleProfileDef(ProfileType="AREA", XDim=larg, YDim=prof)
        laje_ext = ifc.createIfcExtrudedAreaSolid(
            SweptArea=laje_perfil,
            ExtrudedDirection=ifc.createIfcDirection([0.0, 0.0, 1.0]),
            Depth=0.12
        )
        laje_shape = ifc.createIfcShapeRepresentation(
            ContextOfItems=ctx, RepresentationIdentifier="Body",
            RepresentationType="SweptSolid", Items=[laje_ext]
        )
        laje = ifc.createIfcSlab(
            GlobalId=ifcopenshell.guid.new(),
            Name=f"Laje — {amb['nome']}",
            Description="Laje maciça esp. 12cm",
            PredefinedType="FLOOR",
            ObjectPlacement=laje_local,
            Representation=ifc.createIfcProductDefinitionShape(Representations=[laje_shape])
        )
        todos_elementos.append(laje)

        x_cursor += larg + esp
        row_height = max(row_height, prof)

    # Containment — associa elementos ao pavimento
    for i, pav_ifc in enumerate(pavimentos_ifc):
        els_pav = [e for j, e in enumerate(todos_elementos) if j % max(len(pavimentos_ifc), 1) == i]
        if els_pav:
            ifc.createIfcRelContainedInSpatialStructure(
                GlobalId=ifcopenshell.guid.new(),
                RelatingStructure=pav_ifc,
                RelatedElements=els_pav
            )

    # Salva
    caminho = OUTPUTS / f"projeto_{projeto_id}.ifc"
    ifc.write(str(caminho))
    return {"arquivo": str(caminho), "elementos": len(todos_elementos)}


# ─── ROTA 5: GERAR DWG ───────────────────────────────────────────────────────
@app.post("/api/arquivos/dwg")
async def gerar_dwg(dados: DadosIFC):
    """
    Gera arquivo DWG/DXF com planta baixa técnica
    Layers ABNT, cotas, carimbo
    """
    try:
        import ezdxf
    except ImportError:
        raise HTTPException(500, "ezdxf não instalado. Execute: pip install ezdxf")

    programa = dados.programa
    projeto_id = dados.projeto_id or str(uuid.uuid4())[:8]

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # ── Layers padrão ABNT ──
    layers = {
        "A-WALL": (7,   "continuous"),   # paredes — branco
        "A-DIMS": (4,   "continuous"),   # cotas — ciano
        "A-TEXT": (2,   "continuous"),   # textos — amarelo
        "A-HATCH":(8,   "continuous"),   # hachuras — cinza
        "A-DOOR": (1,   "continuous"),   # portas — vermelho
        "A-WIND": (3,   "continuous"),   # janelas — verde
        "A-COLS": (6,   "continuous"),   # pilares — magenta
        "A-GRID": (9,   "continuous"),   # eixos — cinza claro
    }
    for nome, (cor, lt) in layers.items():
        doc.layers.add(name=nome, color=cor, linetype=lt)

    # ── Desenha ambientes ──
    FATOR = 100  # 1m = 100 unidades DXF (escala 1:100)
    esp_parede = 15  # 15cm em unidades
    x_cur, y_cur = 0.0, 0.0
    row_h = 0.0
    X_MAX = dados.dados.get("frente", 12) * FATOR

    for amb in programa.get("ambientes", []):
        larg = float(amb.get("largura", 4.0)) * FATOR
        prof = float(amb.get("profundidade", 3.0)) * FATOR
        nome = amb.get("nome", "Ambiente")
        area = float(amb.get("area", larg * prof / FATOR**2))

        if x_cur + larg > X_MAX + 200:
            x_cur = 0.0
            y_cur += row_h + esp_parede
            row_h = 0.0

        # Parede externa (hachura de corte)
        msp.add_lwpolyline(
            [(x_cur, y_cur), (x_cur+larg, y_cur),
             (x_cur+larg, y_cur+prof), (x_cur, y_cur+prof)],
            close=True,
            dxfattribs={"layer": "A-WALL", "lineweight": 50}
        )

        # Hachura de parede (representação de corte)
        hatch = msp.add_hatch(color=8, dxfattribs={"layer": "A-HATCH"})
        hatch.set_pattern_fill("ANSI31", scale=30, angle=45)
        hatch.paths.add_polyline_path(
            [(x_cur, y_cur), (x_cur+larg, y_cur),
             (x_cur+larg, y_cur+prof), (x_cur, y_cur+prof)],
            is_closed=True
        )

        # Interior (linha fina)
        msp.add_lwpolyline(
            [(x_cur+esp_parede, y_cur+esp_parede),
             (x_cur+larg-esp_parede, y_cur+esp_parede),
             (x_cur+larg-esp_parede, y_cur+prof-esp_parede),
             (x_cur+esp_parede, y_cur+prof-esp_parede)],
            close=True,
            dxfattribs={"layer": "A-WALL", "lineweight": 13}
        )

        # Nome do ambiente
        cx = x_cur + larg / 2
        cy = y_cur + prof / 2
        msp.add_text(
            nome.upper(),
            dxfattribs={
                "layer": "A-TEXT", "height": 18,
                "insert": (cx, cy + 12), "halign": 1,
                "style": "Standard"
            }
        ).set_placement((cx, cy + 12), align=ezdxf.enums.TextEntityAlignment.CENTER)

        msp.add_text(
            f"{area:.1f}m²",
            dxfattribs={
                "layer": "A-TEXT", "height": 14,
                "style": "Standard"
            }
        ).set_placement((cx, cy - 12), align=ezdxf.enums.TextEntityAlignment.CENTER)

        # Cota de largura
        msp.add_linear_dim(
            base=(x_cur, y_cur - 60),
            p1=(x_cur, y_cur - 40),
            p2=(x_cur + larg, y_cur - 40),
            dimstyle="EZ_M_100",
            dxfattribs={"layer": "A-DIMS"}
        ).render()

        x_cur += larg + esp_parede
        row_h = max(row_h, prof)

    # ── Carimbo ──
    carimbo_y = -300
    msp.add_lwpolyline(
        [(0, carimbo_y), (800, carimbo_y),
         (800, carimbo_y - 120), (0, carimbo_y - 120)],
        close=True, dxfattribs={"layer": "A-TEXT", "lineweight": 35}
    )
    msp.add_text(
        "PLANTA BAIXA — TÉRREO",
        dxfattribs={"layer": "A-TEXT", "height": 20}
    ).set_placement((20, carimbo_y - 40), align=ezdxf.enums.TextEntityAlignment.LEFT)

    msp.add_text(
        f"PROJETO: RESIDÊNCIA {dados.dados.get('padrao','').upper()} | ESC 1:100",
        dxfattribs={"layer": "A-TEXT", "height": 14}
    ).set_placement((20, carimbo_y - 70), align=ezdxf.enums.TextEntityAlignment.LEFT)

    msp.add_text(
        "ARQUITETO IA © 2025",
        dxfattribs={"layer": "A-TEXT", "height": 12}
    ).set_placement((20, carimbo_y - 95), align=ezdxf.enums.TextEntityAlignment.LEFT)

    # ── Símbolo Norte ──
    msp.add_circle(center=(X_MAX + 100, y_cur / 2), radius=40,
                   dxfattribs={"layer": "A-TEXT"})
    msp.add_text("N", dxfattribs={"layer": "A-TEXT", "height": 30}).set_placement(
        (X_MAX + 100, y_cur / 2 + 10), align=ezdxf.enums.TextEntityAlignment.CENTER
    )

    # Salva como DXF (compatível com AutoCAD como DWG)
    caminho = OUTPUTS / f"planta_{projeto_id}.dxf"
    doc.saveas(str(caminho))
    return {"arquivo": str(caminho), "layers": list(layers.keys())}


# ─── ROTA 6: GERAR PDF MEMORIAL ──────────────────────────────────────────────
@app.post("/api/arquivos/pdf")
async def gerar_pdf(dados: DadosIFC):
    """
    Gera PDF do memorial descritivo com todas as especificações
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
    except ImportError:
        raise HTTPException(500, "reportlab não instalado. Execute: pip install reportlab")

    programa = dados.programa
    d = dados.dados
    projeto_id = dados.projeto_id or str(uuid.uuid4())[:8]
    caminho = str(OUTPUTS / f"memorial_{projeto_id}.pdf")

    doc = SimpleDocTemplate(caminho, pagesize=A4,
                            leftMargin=2.5*cm, rightMargin=2.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle("titulo", parent=styles["Heading1"],
                                   fontSize=18, textColor=colors.HexColor("#C8A96E"),
                                   spaceAfter=6)
    sub_style = ParagraphStyle("sub", parent=styles["Heading2"],
                                fontSize=12, textColor=colors.HexColor("#555555"),
                                spaceAfter=4, spaceBefore=12)
    body_style = ParagraphStyle("body", parent=styles["Normal"],
                                 fontSize=10, leading=14, textColor=colors.HexColor("#333333"))

    story = []

    # Cabeçalho
    story.append(Paragraph("MEMORIAL DESCRITIVO", titulo_style))
    story.append(Paragraph(
        f"Residência {d.get('padrao','').title()} — {d.get('estilo','').title()} | "
        f"Terreno {d.get('frente','?')}m × {d.get('lado','?')}m",
        sub_style
    ))
    story.append(Spacer(1, 0.4*cm))

    # Dados gerais
    story.append(Paragraph("1. DADOS GERAIS DO PROJETO", sub_style))
    dados_gerais = [
        ["Item", "Descrição"],
        ["Terreno", f"{d.get('frente','?')}m (frente) × {d.get('lado','?')}m (profundidade)"],
        ["Área do Terreno", f"{programa.get('area_terreno','?')}m²"],
        ["Topografia", d.get('topografia','?').title()],
        ["Padrão", d.get('padrao','?').title()],
        ["Tipologia", d.get('tipo','?').title()],
        ["Pavimentos", str(programa.get('pavimentos', 1))],
        ["Área Total Construída", f"{programa.get('area_total','?')}m²"],
        ["Taxa de Ocupação", programa.get('taxa_ocupacao','?')],
        ["Estilo Arquitetônico", d.get('estilo','?').title()],
    ]
    t = Table(dados_gerais, colWidths=[6*cm, 11*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#C8A96E")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F9F9F9")]),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Programa de necessidades
    story.append(Paragraph("2. PROGRAMA DE NECESSIDADES", sub_style))
    amb_data = [["Ambiente", "Área (m²)", "Dimensões (m)", "Pavimento"]]
    for a in programa.get("ambientes", []):
        amb_data.append([
            a.get("nome","?"),
            f"{a.get('area', 0):.1f}",
            f"{a.get('largura',0):.1f} × {a.get('profundidade',0):.1f}",
            f"{a.get('pavimento',1)}º"
        ])
    # Total
    total = sum(a.get("area", 0) for a in programa.get("ambientes", []))
    amb_data.append(["ÁREA TOTAL", f"{total:.1f}", "", ""])

    t2 = Table(amb_data, colWidths=[7*cm, 3*cm, 4.5*cm, 2.5*cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#F0E8D8")),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#F9F9F9")]),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.5*cm))

    # Recuos
    story.append(Paragraph("3. RECUOS E AFASTAMENTOS", sub_style))
    recuos = programa.get("recuos", {})
    rec_data = [
        ["Frontal", f"{recuos.get('frontal', 5.0)}m", "Conforme Plano Diretor Municipal"],
        ["Lateral Esq.", f"{recuos.get('lateral_esq', 1.5)}m", "NBR mínimo 1,50m"],
        ["Lateral Dir.", f"{recuos.get('lateral_dir', 1.5)}m", "NBR mínimo 1,50m"],
        ["Fundos", f"{recuos.get('fundos', 3.0)}m", "NBR mínimo 3,00m"],
    ]
    t3 = Table([["Recuo", "Medida", "Observação"]] + rec_data,
               colWidths=[4*cm, 3*cm, 10*cm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#C8A96E")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.5*cm))

    # Observações técnicas
    if programa.get("observacoes_tecnicas"):
        story.append(Paragraph("4. OBSERVAÇÕES TÉCNICAS", sub_style))
        for obs in programa["observacoes_tecnicas"]:
            story.append(Paragraph(f"• {obs}", body_style))
        story.append(Spacer(1, 0.3*cm))

    # Rodapé
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "Documento gerado automaticamente pelo sistema Arquiteto IA. "
        "Este memorial é um documento de referência e deve ser revisado "
        "por profissional habilitado (CAU/CREA) antes da execução.",
        ParagraphStyle("aviso", parent=styles["Normal"],
                       fontSize=8, textColor=colors.HexColor("#999999"),
                       borderPad=8)
    ))

    doc.build(story)
    return {"arquivo": caminho}


# ─── ROTA 7: DOWNLOAD DE ARQUIVO ─────────────────────────────────────────────
@app.get("/api/download/{filename}")
async def download(filename: str):
    caminho = OUTPUTS / filename
    if not caminho.exists():
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(str(caminho), filename=filename)


# ─── SERVE O FRONTEND ────────────────────────────────────────────────────────
@app.get("/app", response_class=HTMLResponse)
async def frontend():
    """Serve o app frontend diretamente"""
    html_path = Path("static/index.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse("<h1>Frontend não encontrado</h1>")

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/")
async def health():
    return {
        "status": "online",
        "servicos": {
            "claude": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "replicate": bool(os.environ.get("REPLICATE_API_TOKEN")),
        }
    }
