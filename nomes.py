# -*- coding: utf-8 -*-
"""Nome da peça pela moto (pesquisa 25/11: as grandes lojas escrevem 'Kit relação CG 160 Titan/Fan 2016 a 2025').
O nome da Real vem como 'KIT TRANSMISSAO 428HX118/44X15 - 0009KR - COBREQ'; cliente não busca assim."""
import re, unicodedata

def _n(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

SIGLAS = {"CG", "XRE", "PCX", "CB", "CBX", "SH", "XR", "NX", "XLR", "CRF", "XT", "YBR", "XTZ", "NXR", "YS", "FZ15", "FZ25", "NX4", "T115"}
CARRO = re.compile(r"\b(8V|16V|AUDI)\b", re.I)
PRIORIDADE = ["CG 160", "CG 150", "CG 125", "Biz 125", "Biz 110i", "Biz 100", "Pop 110i", "Pop 100", "Bros 160", "Bros 150", "Bros 125",
              "Fazer 150", "Factor 150", "Crosser 150", "XRE 300", "XRE 190", "Fazer 250", "Lander 250", "Twister 250", "CB 300", "PCX 150", "NMax 160"]

def _cap(w):
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
        return f"CG {g.group(1)}", g.group(2).capitalize()
    return " ".join(_cap(w) for w in m.split()), ""

def _parse(v):
    g = re.match(r"^(.*?)\s+(\d{4})-(\d{4})?$", v.strip())
    if not g:
        return None
    return g.group(1), int(g.group(2)), int(g.group(3)) if g.group(3) else None

def familias(veiculos):
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
    def chave(f):
        return (PRIORIDADE.index(f) if f in PRIORIDADE else 99, list(fam).index(f))
    out = []
    for f in sorted(fam, key=chave):
        d = fam[f]
        ini, fim = (next(iter(d["anos"])) if len(d["anos"]) == 1 else (None, None))
        ordem = ["Fan", "Titan", "Start", "Cargo"]
        out.append((f, sorted(d["vars"], key=lambda x: ordem.index(x) if x in ordem else 9), ini, fim))
    return out

def resumo_motos(veiculos, max_fam=2, ano_atual=2026):
    fs = familias(veiculos)
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
    (r"^pedaleira traseira esquerda", "Pedaleira traseira esquerda"), (r"^pedaleira traseira direita", "Pedaleira traseira direita"), (r"^pedaleira traseira", "Pedaleira traseira"),
    (r"^retrovisor", "Retrovisor"),
]

def spec_relacao(desc):
    """'KIT TRANSMISSAO ORING 428HPOX118L/44X15' -> dict(corrente='428H', elos=118, coroa=44, pinhao=15, retentor=True)"""
    g = re.search(r"(\d{3})([A-Z]*?)X(\d{2,3})L?/(\d{2})X(\d{2})", desc.upper().replace(" ", ""))
    if not g:
        return None
    return {"corrente": g.group(1) + ("H" if "H" in g.group(2) else ""), "elos": int(g.group(3)), "coroa": int(g.group(4)), "pinhao": int(g.group(5)),
            "retentor": bool(re.search(r"O.?RING", desc.upper()))}

def nome_por_moto(nome_real, categoria, veiculos, fallback):
    """Devolve (nome, spec_curta). Se não reconhecer o tipo da peça, devolve o nome antigo (fallback)."""
    partes = [x.strip() for x in nome_real.split(" - ")]
    if len(partes) < 3:
        return fallback, ""
    desc, cod, marca = partes[0], partes[1], partes[-1]
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
    if not tipo:
        return fallback, ""
    extra, spec = "", ""
    if categoria == "transmissao":
        s = spec_relacao(desc)
        if s:
            spec = f"Coroa {s['coroa']}, pinhão {s['pinhao']}, corrente {s['corrente']} com {s['elos']} elos"
    elif categoria == "ignicao":
        extra = f" {marca} {cod}"; marca = ""
    elif tipo == "Lâmpada do farol":
        g = re.search(r"H4\s*[\d/]+W", nome_real.upper()); extra = f" {g.group(0)}" if g else ""
    elif tipo.startswith("Manete") or tipo == "Retrovisor":
        resto = re.sub(r"^(manete (freio a disco|freio a tambor|embreagem)|retrovisor)\s*", "", nd).strip()
        resto = re.sub(r"haste (\d+)mm", r"haste \1 mm", resto)
        extra = f" {resto}" if resto else ""
    elif "organica" in nd:
        spec = "Orgânica"
    motos = resumo_motos(veiculos)
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
