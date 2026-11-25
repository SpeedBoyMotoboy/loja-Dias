# -*- coding: utf-8 -*-
"""Nome da peça pela moto (pesquisa 25/11: as grandes lojas escrevem 'Kit relação CG 160 Titan/Fan 2016 a 2025').
O nome da Real vem como 'KIT TRANSMISSAO 428HX118/44X15 - 0009KR - COBREQ'; cliente não busca assim."""
import re, unicodedata

def _n(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

SIGLAS = {"CG", "XRE", "PCX", "CB", "CBX", "SH", "XR", "NX", "XLR", "CRF", "XT", "YBR", "XTZ", "NXR", "YS", "FZ15", "FZ25", "NX4", "T115",
          "ML", "XL", "XLX", "NC", "CBR", "GSX", "KLX", "VT", "DT", "DL", "GS", "YZ", "WR", "VS", "RD", "XVS", "TVS", "BMW", "XMAX", "WGK", "EN", "AN", "GSR", "XY", "XV"}  # 25/11: "Bmw", "Cbr" pareciam erro
CARRO = re.compile(r"\b\d{1,2}V\b|\bAUDI\b|\(|FORA DA FROTA|CAMINH|AUTOMOV|UTILIT|N[AÃ]O VEICULAR|SEM APLICA|M[AÁ]QUINAS|[OÔ]NIBUS", re.I)  # carro, caminhão (motor entre parênteses) e afins
PRIORIDADE = ["CG 160", "CG 150", "CG 125", "Biz 125", "Biz 110i", "Biz 100", "Pop 110i", "Pop 100", "Bros 160", "Bros 150", "Bros 125",
              "Fazer 150", "Factor 150", "Crosser 150", "XRE 300", "XRE 190", "Fazer 250", "Lander 250", "Twister 250", "CB 300", "PCX 150", "NMax 160"]

def _cap(w):
    if "-" in w and not re.search(r"\d", w):  # Harley-Davidson
        return "-".join(_cap(x) for x in w.split("-"))
    return w if (w.upper() in SIGLAS or re.search(r"\d", w)) else w.capitalize()

def moto_amigavel(modelo):
    """'NXR 160 BROS' -> ('Bros 160', ''), 'CG 160 FAN' -> ('CG 160', 'Fan'). Devolve (familia, variante)."""
    m = modelo.strip().upper()
    m = re.sub(r"\s+ESDD$", "", m)
    for pat, rep in ((r"^NXR (\d+) BROS$", r"Bros \1"), (r"^XTZ (\d+) CROSSER$", r"Crosser \1"), (r"^YS (\d+) FAZER$", r"Fazer \1"),
                     (r"^FZ25 250 FAZER$", "Fazer 250"), (r"^FAZER FZ15$", "Fazer FZ15"), (r"^YBR (\d+)I? FACTOR$", r"Factor \1"),
                     (r"^XTZ LANDER 250$", "Lander 250"), (r"^XTZ 250 T[EÉ]N[EÉ]R[EÉ]$", "Ténéré 250"), (r"^XT 600 Z T[EÉ]N[EÉ]R[EÉ]$", "Ténéré 600"),
                     (r"^XR 250 TORNADO$", "Tornado 250"), (r"^CBX? 250 TWISTER$", "Twister 250"), (r"^CB 300F TWISTER$", "Twister 300"),
                     (r"^NX4 FALCON 400$", "Falcon 400"), (r"^CB 300R?$", "CB 300"), (r"^BIZ 110I$", "Biz 110i"), (r"^BIZ (\d+)[I+]?$", r"Biz \1"),
                     (r"^POP 110I$", "Pop 110i"), (r"^NMAX (\d+)$", r"NMax \1"), (r"^SH (\d+)I$", r"SH \1i")):
        if re.match(pat, m):
            return re.sub(pat, rep, m), ""
    g = re.match(r"^CG (\d+) (\w+)$", m)
    if g:
        return f"CG {g.group(1)}", _cap(g.group(2))
    return " ".join(_cap(w) for w in m.split()), ""

def _parse(v):
    g = re.match(r"^(.*?)\s+(\d{4})-(\d{4})?$", v.strip())
    if not g:
        return None
    return g.group(1), int(g.group(2)), int(g.group(3)) if g.group(3) else None

def familias(veiculos, primeiro=()):
    """Lista ordenada de (familia, [variantes], ano_ini, ano_fim) só de motos. ano_* = None quando as variantes divergem."""
    fam = {}
    for v in veiculos:
        p = _parse(v)
        if not p or CARRO.search(p[0]):
            continue
        f, var = moto_amigavel(p[0])
        d = fam.setdefault(f, {"vars": [], "anos": set()})
        if var and var not in d["vars"]:
            d["vars"].append(var)
        d["anos"].add((p[1], p[2]))
    def chave(f):  # 'primeiro': famílias da página por moto, para a peça aparecer com o nome daquela moto
        return (f not in primeiro, PRIORIDADE.index(f) if f in PRIORIDADE else 99, list(fam).index(f))
    out = []
    for f in sorted(fam, key=chave):
        d = fam[f]
        ini, fim = (next(iter(d["anos"])) if len(d["anos"]) == 1 else (None, None))
        ordem = ["Fan", "Titan", "Start", "Cargo"]
        out.append((f, sorted(d["vars"], key=lambda x: ordem.index(x) if x in ordem else 9), ini, fim))
    return out

def resumo_motos(veiculos, max_fam=2, ano_atual=2026, primeiro=()):
    fs = familias(veiculos, primeiro)
    if not fs:
        return ""
    partes = []
    for f, vs, ini, fim in fs[:max_fam]:
        t = f + (" " + "/".join(vs) if vs else "")
        if ini and len(fs) == 1:
            t += f" {ini} em diante" if (fim is None or fim >= ano_atual) else (f" {ini}" if ini == fim else f" {ini} a {fim}")
        partes.append(t)
    return (", ".join(partes) + " e outras") if len(fs) > max_fam else " e ".join(partes)

TIPOS_PECA = [
    (r"^kit transmissao o.?ring", "Kit relação com retentor"), (r"^kit transmissao", "Kit relação"),
    (r"^pastilha (de )?freio dianteira", "Pastilha de freio dianteira"), (r"^pastilha (de )?freio traseira", "Pastilha de freio traseira"),
    (r"^filtro (de )?ar", "Filtro de ar"), (r"^filtro (de |do |de do )?oleo", "Filtro de óleo"),
    (r"^cabo (de |do )?acelerador", "Cabo do acelerador"), (r"^cabo (de )?embreagem", "Cabo de embreagem"),
    (r"^vela ignicao iridium", "Vela de ignição iridium"), (r"^vela ignicao", "Vela de ignição"),
    (r"^lampada farol alto, farol baixo", "Lâmpada do farol"), (r"^lampada farol moto", "Lâmpada do farol"),
    (r"^manete freio a disco", "Manete de freio a disco"), (r"^manete freio a tambor", "Manete de freio a tambor"), (r"^manete embreagem", "Manete de embreagem"),
    (r"^pedaleira traseira/dianteira esquerda", "Pedaleira esquerda"), (r"^pedaleira traseira/dianteira direita", "Pedaleira direita"),
    (r"^pedaleira traseira ?esquerda", "Pedaleira traseira esquerda"), (r"^pedaleira traseira ?direita", "Pedaleira traseira direita"),
    (r"^pedaleira traseira esquerda", "Pedaleira traseira esquerda"), (r"^pedaleira traseira direita", "Pedaleira traseira direita"), (r"^pedaleira traseira", "Pedaleira traseira"),
    (r"^retrovisor", "Retrovisor"),
    # 25/11 (catálogo ampliado): tipos que antes não tinham nome pela moto
    (r"^pastilha freio (diant|dia)\w*\s*/\s*tra", "Pastilha de freio dianteira ou traseira"),
    (r"^patim freio (dianteiro|diant|dia)\w*\s*/\s*tra", "Lona de freio dianteira ou traseira"),
    (r"^patim freio traseir", "Lona de freio traseira"), (r"^patim freio dianteir", "Lona de freio dianteira"), (r"^patim freio", "Lona de freio"),
    (r"^filtro do ar", "Filtro de ar"), (r"^vela de ignicao iridium", "Vela de ignição iridium"), (r"^vela de ignicao", "Vela de ignição"),
    (r"^pedaleira dianteira esquerda", "Pedaleira dianteira esquerda"), (r"^pedaleira dianteira direita", "Pedaleira dianteira direita"),
    (r"^pedaleira traseira/dianteira esquerda", "Pedaleira esquerda"), (r"^pedaleira traseira/dianteira direita", "Pedaleira direita"),
    (r"^pedaleira traseira ?esquerda", "Pedaleira traseira esquerda"), (r"^pedaleira traseira ?direita", "Pedaleira traseira direita"), (r"^pedaleira", "Pedaleira traseira"),
    (r"^retentor (garfo|bengala)", "Retentor de bengala"), (r"^retentor haste valvula", "Retentor de válvula"),
    (r"^retentor (pedal cambio|cambio|seletor marcha|eixo seletor)", "Retentor do pedal de câmbio"),
    (r"^retentor (eixo )?pedal partida", "Retentor do pedal de partida"),
    (r"^retentor (cubo )?roda traseir", "Retentor da roda traseira"), (r"^retentor (cubo )?roda dianteir", "Retentor da roda dianteira"), (r"^retentor cubo roda", "Retentor do cubo da roda"),
    (r"^retentor (haste )?embreagem", "Retentor da haste da embreagem"), (r"^retentor pinhao", "Retentor do pinhão"),
    (r"^retentor (reparo )?mesa magneto", "Retentor do magneto"), (r"^retentor virabrequim", "Retentor do virabrequim"),
    (r"^lampada (de )?farol milha", "Lâmpada do farol de milha"), (r"^lampada (de )?farol", "Lâmpada do farol"),
    (r"^lampada (de )?sinaliz\w*", "Lâmpada de sinalização"), (r"^lampada", "Lâmpada"),
]

# 25/11 (catálogo de 1000): tipos novos. (começo da descrição da Real sem acento, nome do tipo). O resto da descrição vem depois, arrumado.
FRASES = [
    (r"^disco (de )?freio", "Disco de freio"), (r"^chave (de )?ignicao", "Chave de ignição"), (r"^chave (de )?luz", "Chave de luz"),
    (r"^chave comutadora", "Chave comutadora"), (r"^interruptor (de )?freio", "Interruptor de freio"),
    (r"^interruptor (de )?partida", "Interruptor de partida"), (r"^interruptor (de )?neutro", "Interruptor de neutro"),
    (r"^interruptor (de )?pisca", "Interruptor do pisca"), (r"^interruptor (de )?embreagem", "Interruptor de embreagem"),
    (r"^regulador[ /]retificador", "Regulador retificador"), (r"^tubo interno( bengala)?", "Tubo interno da bengala"),
    (r"^amortecedor para suspensao", "Amortecedor"), (r"^amortecedor", "Amortecedor"),
    (r"^junta guarnicao tampa valvula", "Junta da tampa de válvula"), (r"^junta tampa valvula", "Junta da tampa de válvula"),
    (r"^junta motor", "Jogo de juntas do motor"), (r"^kit a junta superior motor", "Jogo de juntas superior do motor"),
    (r"^kit b junta inferior motor", "Jogo de juntas inferior do motor"), (r"^kit vedacao tampa valvula", "Kit de vedação da tampa de válvula"),
    (r"^junta estator tampa lateral esquerda", "Junta da tampa do estator, lado esquerdo"),
    (r"^junta embreagem tampa lateral direita", "Junta da tampa de embreagem, lado direito"),
    (r"^junta (do )?cilindro", "Junta do cilindro"), (r"^junta (do )?cabecote", "Junta do cabeçote"),
    (r"^junta acionador tensor", "Junta do acionador do tensor"), (r"^junta (da )?carcaca", "Junta da carcaça"),
    (r"^junta (do )?escap\w*", "Junta do escapamento"), (r"^junta (do )?carburador", "Junta do carburador"), (r"^junta", "Junta"),
    (r"^kit tensor corrente comando", "Kit tensor da corrente de comando"), (r"^tensor corrente comando", "Tensor da corrente de comando"),
    (r"^guia corrente comando", "Guia da corrente de comando"), (r"^corrente (do |de )?comando", "Corrente de comando"),
    (r"^corrente (de )?transmissao", "Corrente de transmissão"),
    (r"^rolamento (de |da )?roda", "Rolamento de roda"), (r"^rolamento (do )?virabrequim", "Rolamento do virabrequim"),
    (r"^rolamento (do )?comando", "Rolamento do comando"), (r"^rolamento (da |de )?(caixa )?direcao", "Rolamento da caixa de direção"),
    (r"^rolamento esfera", "Rolamento"), (r"^rolamento", "Rolamento"),
    (r"^rele (de )?partida", "Relé de partida"), (r"^rele (de |do )?pisca", "Relé do pisca"), (r"^rele (de )?carga", "Relé de carga"), (r"^rele", "Relé"),
    (r"^bobina (de )?pulso", "Bobina de pulso"), (r"^bobina (de )?ignicao", "Bobina de ignição"), (r"^bobina (de )?forca", "Bobina de força"),
    (r"^cdi( modulo)?( de)?( ignicao)?", "CDI"), (r"^coxim (da )?coroa( transmissao)?", "Coxim da coroa"), (r"^bucha (da )?coroa", "Bucha da coroa"),
    (r"^cubo (da )?roda", "Cubo da roda"), (r"^soquete (do )?farol", "Soquete do farol"), (r"^soquete (da )?lanterna", "Soquete da lanterna"),
    (r"^lente (do )?pisca( seta)?", "Lente do pisca"), (r"^lente (da )?lanterna", "Lente da lanterna"),
    (r"^guarda po( do)? garfo", "Guarda-pó da bengala"), (r"^caixa de direcao", "Caixa de direção"),
    (r"^carenagem (do )?farol", "Carenagem do farol"), (r"^carenagem lateral (do )?farol", "Carenagem lateral do farol"),
    (r"^cabo (do |de )?velocimetro", "Cabo do velocímetro"), (r"^cabo (do |de )?freio", "Cabo do freio"), (r"^cabo (do |de )?afogador", "Cabo do afogador"),
    (r"^coroa", "Coroa"), (r"^pinhao", "Pinhão"), (r"^pisca", "Pisca"), (r"^manopla", "Manopla"), (r"^carburador", "Carburador"),
    (r"^kit (de )?embreagem", "Kit de embreagem"), (r"^disco (de )?embreagem", "Discos de embreagem"),
    (r"^estator( volante)?", "Estator"), (r"^pistao c/ ?anel( cofap)?", "Pistão com anéis"), (r"^pistao e aneis", "Pistão com anéis"), (r"^motor (de )?partida", "Motor de partida"),
    (r"^fiacao principal( \(chicote\))?", "Chicote elétrico principal"), (r"^suporte e escovas( motor de partida)?", "Suporte e escovas do motor de partida"),
    (r"^reparo escova mola", "Reparo de escova e mola"), (r"^sensor nivel medidor combustivel", "Sensor de nível de combustível"),
    (r"^eixo secundario", "Eixo secundário do câmbio"), (r"^eixo primario", "Eixo primário do câmbio"),
    (r"^bomba combustivel elet\w* refil", "Refil da bomba de combustível"), (r"^bomba (de )?combustivel", "Bomba de combustível"),
    (r"^cachimbo( de)? vela", "Cachimbo de vela"), (r"^embreagem placa partida", "Embreagem de partida"),
    (r"^coletor (de )?admissao", "Coletor de admissão"), (r"^volante magnetico( rotor)?", "Volante magnético"),
    (r"^bucha garfo traseir[oa] kit", "Kit de buchas da balança traseira"), (r"^tripe cavalete lateral", "Descanso lateral"),
    (r"^caixa direcao", "Caixa de direção"), (r"^kit motor( cofap)?", "Kit motor"),
    (r"^filtro (do |de )?combustivel", "Filtro de combustível"), (r"^bujao (do |de )?oleo", "Bujão do óleo"),
    (r"^arvore (de )?comando", "Comando de válvulas"), (r"^pedal (de )?cambio", "Pedal de câmbio"), (r"^pedal (de )?freio", "Pedal de freio"),
    (r"^terminal cachimbo vela", "Terminal do cachimbo de vela"), (r"^flange (do )?(cubo )?(da )?roda", "Flange da roda"),
    (r"^bucha quadro elastico garfo traseiro kit", "Kit de buchas do quadro elástico"), (r"^mola (do )?cavalete", "Mola do cavalete"),
    (r"^suporte escova", "Suporte de escovas"), (r"^kit reparo mesa magneto", "Kit reparo da mesa do magneto"),
    (r"^parafuso (do )?disco (de )?freio", "Parafuso do disco de freio"), (r"^raio", "Raio"), (r"^guidao", "Guidão"), (r"^buzina", "Buzina"),
]
PALAVRAS = {"ignicao": "ignição", "valvula": "válvula", "cabecote": "cabeçote", "guarnicao": "guarnição", "vedacao": "vedação",
            "direcao": "direção", "transmissao": "transmissão", "suspensao": "suspensão", "pinhao": "pinhão", "lampada": "lâmpada",
            "modulo": "módulo", "emergencia": "emergência", "aco": "aço", "po": "pó", "oleo": "óleo", "embreagem": "embreagem",
            "velocimetro": "velocímetro", "camara": "câmara", "carcaca": "carcaça", "eletrico": "elétrico", "eletrica": "elétrica",
            "fume": "fumê", "cambio": "câmbio", "traseiro": "traseiro", "regulagem": "regulagem", "pressao": "pressão", "sinalizacao": "sinalização",
            "plastico": "plástico", "aluminio": "alumínio", "nylon": "náilon", "combustivel": "combustível", "injecao": "injeção", "eletronica": "eletrônica",
            "dian": "dianteiro", "diant": "dianteiro", "tras": "traseiro", "tra": "traseiro", "le": "lado esquerdo", "ld": "lado direito",
            "esq": "esquerdo", "dir": "direito", "az": "azul", "verm": "vermelho", "pto": "preto", "injet": "injetado", "cromad": "cromado",
            "c/": "com", "s/": "sem", "p/": "para", "secundario": "secundário", "primario": "primário", "magnetico": "magnético",
            "admissao": "admissão", "nivel": "nível", "fiacao": "fiação", "tripe": "tripé", "elet": "elétrica", "aneis": "anéis", "pistao": "pistão",
            "optico": "óptico", "macico": "maciço", "reforcado": "reforçado", "zincado": "zincado", "guidao": "guidão", "padrao": "padrão", "elastico": "elástico", "bujao": "bujão", "arvore": "árvore",
            "tubular-mod": "tubular modelo", "pe": "pé", "balanca": "balança", "mao": "mão", "cubico": "cúbico", "ceramica": "cerâmica", "organica": "orgânica", "lamp": "lâmpada", "univ": "universal", "comp": "completo", "sup": "superior", "inf": "inferior"}

def _arruma(resto):
    """'DIAN LE TRAS LD C/LAMPADA (404SV-96L)' -> 'dianteiro lado esquerdo traseiro lado direito com lâmpada (404SV-96L)'"""
    resto = re.sub(r"\b([CSP])/\s*", lambda g: g.group(1).lower() + "/ ", resto, flags=re.I)
    out = []
    for w in resto.split():
        nu = _n(w).strip(".,")
        if re.search(r"\d", w):
            out.append(w.upper())
        elif nu in PALAVRAS:
            out.append(PALAVRAS[nu])
        elif w.strip("()").upper() in SIGLAS or w.upper() in ("CBS", "ABS", "LED", "DOT3", "DOT4"):
            out.append(w.upper())
        else:
            out.append(w.lower())
    return " ".join(out)

def tipo_generico(desc):
    """Tipo de peça que não está em TIPOS_PECA: usa FRASES no começo e arruma o resto da descrição da Real."""
    nd = re.sub(r"\s+", " ", _n(desc)).strip()
    for pat, rep in FRASES:
        g = re.match(pat, nd)
        if g:
            resto = _arruma(re.sub(r"\s+", " ", desc).strip()[g.end():].strip(" -"))
            return (rep + (" " + resto if resto else "")).strip()
    t = _arruma(desc)
    return t[:1].upper() + t[1:]

def _medida(desc):
    """'RETENTOR BENGALA 27X39X10,5' -> 'Medida 27 x 39 x 10,5 mm'"""
    g = re.search(r"(\d+(?:[.,]\d+)?)\s*X\s*(\d+(?:[.,]\d+)?)\s*X\s*(\d+(?:[.,]\d+)?)(?:\s*X\s*(\d+(?:[.,]\d+)?))?", desc.upper())
    if not g:
        return ""
    return "Medida " + " x ".join(re.sub(r"[.,]0$", "", x).replace(".", ",") for x in g.groups() if x) + " mm"

def _lampada(desc):
    """'LAMPADA DE SINALIZACAO 12V 5W PINO DESENCONTRADO 2 POLOS' -> ' 12V 5W pino desencontrado 2 polos'"""
    r = re.sub(r"^L[AÂ]MPADA( DE)?( FAROL( MILHA)?| SINALIZ\w*)?(\s+HALOWAY)?", "", desc.strip(), flags=re.I)
    r = re.sub(r"\bALTO, FAROL BAIXO\b|\bMOTO\b", "", r, flags=re.I)
    pal = [w.upper() if re.search(r"\d", w) else {"pingao": "pingão", "ambar": "âmbar", "polos": "polos"}.get(w.lower(), w.lower()) for w in r.split()]
    return (" " + " ".join(pal)) if pal else ""

def spec_relacao(desc):
    """'KIT TRANSMISSAO ORING 428HPOX118L/44X15' -> dict(corrente='428H', elos=118, coroa=44, pinhao=15, retentor=True)"""
    g = re.search(r"(\d{3})([A-Z]*?)X(\d{2,3})L?/(\d{2})X(\d{2})", desc.upper().replace(" ", ""))
    if not g:
        return None
    return {"corrente": g.group(1) + ("H" if "H" in g.group(2) else ""), "elos": int(g.group(3)), "coroa": int(g.group(4)), "pinhao": int(g.group(5)),
            "retentor": bool(re.search(r"O.?RING", desc.upper()))}

def nome_por_moto(nome_real, categoria, veiculos, fallback, primeiro=()):
    """Devolve (nome, spec_curta). Se não reconhecer o tipo da peça, devolve o nome antigo (fallback)."""
    nome_real = re.sub(r"\bSNAP ?- ?ON\b( \(CAR ?80\))?", "SNAP-ON", nome_real, flags=re.I)  # 'SNAP - ON' quebrava a marca em 'ON'
    partes = [x.strip() for x in nome_real.split(" - ")]
    if len(partes) < 3:
        return fallback, ""
    desc, cod, marca = partes[0], partes[1], partes[-1]
    marca = re.sub(r"\s+(INDUSTRIA|IND\.?|MOTO PE[CÇ]AS|LTDA)\b.*$", "", marca, flags=re.I)  # 'POLIMET INDUSTRIA METALURGICA' -> 'Polimet'
    marca = marca if len(marca) <= 3 else marca.title()
    nd = _n(desc)
    tipo = next((rep for pat, rep in TIPOS_PECA if re.match(pat, nd)), None)
    g = re.match(r"^camara ar ([\d./-]+)\s*(tr\d+)?", nd)
    if g:
        return f"Câmara de ar {g.group(1)} {marca}", (f"Válvula {g.group(2).upper()}" if g.group(2) else "")
    g = re.match(r"^oleo fluido de freio (dot\d)( lv classe 6)? ?(\d+) ?ml", nd)
    if g:
        return f"Fluido de freio {g.group(1).upper()}{' LV classe 6' if g.group(2) else ''} {g.group(3)} ml {marca}", ""
    g = re.match(r"^bateria (premium )?(\d+)ah", nd)
    if g:
        return f"Bateria de moto {g.group(2)}Ah 12V {marca} {cod}", ("Linha premium" if g.group(1) else "")
    generico = not tipo
    if generico:
        if not nd or categoria == "kit":
            return fallback, ""
        tipo = tipo_generico(desc)
    extra, spec = "", ""
    if categoria == "transmissao" and not generico:
        s = spec_relacao(desc)
        if s:
            spec = f"Coroa {s['coroa']}, pinhão {s['pinhao']}, corrente {s['corrente']} com {s['elos']} elos"
    elif categoria == "ignicao" and tipo.startswith("Vela"):
        extra = f" {marca} {cod}"; marca = ""
    elif tipo == "Lâmpada do farol" and re.match(r"^lampada farol (alto, farol baixo|moto)", nd):
        g = re.search(r"H4\s*[\d/]+W", nome_real.upper()); extra = f" {g.group(0)}" if g else ""
    elif tipo.startswith("Manete") or tipo == "Retrovisor":
        resto = re.sub(r"^(manete (freio a disco|freio a tambor|embreagem)|retrovisor)\s*", "", nd).strip()
        resto = re.sub(r"haste (\d+)mm", r"haste \1 mm", resto)
        for de, para in ((r"\ble\b", "lado esquerdo"), (r"\bld\b", "lado direito"), (r"\bartic\b", "articulado"), (r"\bc/mola ret\b", "com mola de retorno"), (r"\b360o\b", "360 graus")):
            resto = re.sub(de, para, resto)
        extra = f" {resto}" if resto else ""
    elif tipo.startswith("Retentor"):
        spec = _medida(desc)
        if "guarda po" in nd:
            extra = " com guarda-pó"
    elif tipo.startswith("Lona de freio"):
        spec = ", ".join(x for x in ("Cerâmica, com mola" if "ceramica" in nd else "", "Sobremedida 0,25 mm" if re.search(r"sob ?med", nd) else "") if x)
    elif tipo.startswith("Lâmpada"):
        extra = _lampada(desc)
    elif tipo.startswith("Pistão"):  # a medida vem no fim do código: PA9825STD, PA9825025 (0,25 mm), PA4101150 (1,50 mm)
        g = re.search(r"(STD|025|050|075|100|125|150)$", re.sub(r"[^A-Z0-9]", "", cod.upper()))  # 'PA90231,00' também
        if g:
            extra = " medida padrão (STD)" if g.group(1) == "STD" else f" sobremedida {g.group(1)[0]},{g.group(1)[1:]} mm"
    if "organica" in nd and not spec:
        spec = "Orgânica"
    elif "ceramica" in nd and not spec:
        spec = "Cerâmica"
    motos = resumo_motos(veiculos, primeiro=primeiro)
    nome = f"{tipo}{extra}" + (f" {motos}" if motos else "") + (f" {marca}" if marca else "")
    return re.sub(r"\s+", " ", nome).strip(), spec

def veiculo_legivel(v, ano_atual=2026):
    """'CG 160 FAN 2016-2026' -> 'CG 160 Fan, 2016 em diante'. O que não tiver ano fica como veio."""
    p = _parse(v)
    if not p:
        return v
    f, var = moto_amigavel(p[0]) if not CARRO.search(p[0]) else (p[0].title(), "")
    ini, fim = p[1], p[2]
    anos = f"{ini} em diante" if (fim is None or fim >= ano_atual) else (str(ini) if ini == fim else f"{ini} a {fim}")
    return f"{f}{' ' + var if var else ''}, {anos}"
