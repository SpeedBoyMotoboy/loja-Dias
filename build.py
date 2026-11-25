#!/usr/bin/env python3
"""Gera o site estático da Loja Dias a partir de dados/produtos.csv e dados/config.json.

Uso: python3 build.py            -> gera dist/
Cada página é HTML pronto (rápido e legível pelo Google), com dados estruturados,
sitemap.xml, robots.txt e feed de produtos para o Google Merchant Center.
"""
from urllib.parse import quote
import csv, json, re, shutil, unicodedata, html
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xesc
from nomes import nome_por_moto, familias, veiculo_legivel

RAIZ = Path(__file__).resolve().parent
DIST = RAIZ / "dist"
CFG = json.loads((RAIZ / "dados/config.json").read_text(encoding="utf-8"))
URL = CFG["site_url"].rstrip("/")
import os
EXEMPLO = os.environ.get("LOJA_EXEMPLO") == "1"  # usa dados/produtos_exemplo.csv (só para prévia)
DEMO = EXEMPLO
VITRINE = False  # definido em main(): sem peças reais, o site vira vitrine com pedido pelo WhatsApp
FRETE_OK = CFG.get("fretes_confirmados", False)
GRATIS = CFG.get("frete_gratis_acima") or 0
FIREBASE = CFG.get("firebase")  # login Google do cliente; vazio = sem conta
NA_ENTREGA = CFG.get("pagar_na_entrega", False)  # Pix ao motoboy na entrega; só liga com ok do Luan
# Programa de indicação (25/11): link por pessoa (?ref=CODIGO). Desconto para quem compra e comissão para quem indica,
# só nas peças em que ainda sobra o lucro mínimo depois dos dois (nunca prejuízo).
IND = CFG.get("indicacao") if (CFG.get("indicacao") or {}).get("ligada") else None
GARANTIA = "Garantia de 90 dias contra defeito de fabricação"  # garantia legal (CDC, art. 26)

CATS = {"freio": "Freios", "transmissao": "Relação e correias", "filtro": "Filtros", "oleo": "Óleo, graxa e aditivos",
        "ignicao": "Velas e ignição", "eletrica": "Bateria e elétrica", "cabo": "Cabos",
        "pneu": "Pneus e câmaras", "palheta": "Palhetas", "acessorio": "Retrovisor, manete e acessórios", "kit": "Kits prontos", "suspensao": "Suspensão e retentores",
        "motor": "Motor e embreagem", "roda": "Rolamentos e rodas"}
SO_MOTO = CFG.get("so_moto", False)  # Luan 24/11: por enquanto só 2 rodas
TIPOS = {"moto": "Moto", "carro": "Carro"}
ICON = {
 "transmissao": '<circle cx="20" cy="32" r="12"/><circle cx="20" cy="32" r="3"/><circle cx="48" cy="32" r="7"/><path d="M20 20 48 25M20 44l28-5"/>',
 "freio": '<circle cx="32" cy="32" r="22"/><circle cx="32" cy="32" r="7"/><path d="M14 22a22 22 0 0 1 18-12" stroke-width="7"/>',
 "eletrica": '<rect x="10" y="20" width="44" height="30" rx="3"/><path d="M18 20v-5h8v5M38 20v-5h8v5M20 35h8M40 31v8M36 35h8"/>',
 "ignicao": '<path d="M32 8v10M26 18h12l4 8v14H22V26z"/><path d="M28 40v8h8v-8M32 48v8"/>',
 "filtro": '<rect x="16" y="12" width="32" height="40" rx="5"/><path d="M22 20v24M28 20v24M34 20v24M40 20v24"/>',
 "pneu": '<circle cx="32" cy="32" r="24"/><circle cx="32" cy="32" r="13"/><path d="M32 8v6M32 50v6M8 32h6M50 32h6"/>',
 "oleo": '<path d="M22 14h14l8 8v30H18V18z"/><path d="M36 14v8h8M26 34c0 4 3 6 5 6s5-2 5-6c0-3-5-9-5-9s-5 6-5 9z"/>',
 "cabo": '<path d="M10 50c10 0 10-14 22-14s12-20 22-20"/><rect x="6" y="46" width="8" height="8"/><rect x="50" y="10" width="8" height="8"/>',
 "palheta": '<path d="M8 48 52 14"/><path d="M14 52 56 20" stroke-width="5"/><circle cx="8" cy="48" r="4"/>',
 "suspensao": '<path d="M32 6v10M32 48v10"/><rect x="24" y="16" width="16" height="32" rx="3"/><path d="M24 26h16M24 36h16"/>',
 "kit": '<rect x="10" y="22" width="44" height="30" rx="3"/><path d="M24 22v-8h16v8M10 34h44"/>',
 "motor": '<rect x="16" y="22" width="32" height="26" rx="3"/><path d="M24 22v-8h16v8M16 32H8v8h8M48 32h8v8h-8M26 48v8M38 48v8"/>',
 "roda": '<circle cx="32" cy="32" r="22"/><circle cx="32" cy="32" r="9"/><circle cx="32" cy="15" r="3"/><circle cx="32" cy="49" r="3"/><circle cx="15" cy="32" r="3"/><circle cx="49" cy="32" r="3"/>',
 "acessorio": '<ellipse cx="38" cy="22" rx="16" ry="11"/><path d="M28 30 12 54"/>',
}
FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap">'

e = lambda s: html.escape(str(s), quote=True)
brl = lambda v: ("R$ %.2f" % v).replace(".", ",")

def slug(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def icon(cat):
    return f'<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">{ICON.get(cat, ICON["filtro"])}</svg>'

# Margem (Mesa Loja, Pauta 1, 24/11/2026): tabela base por faixa de custo; itens-isca entre x1,25 e x1,35;
# teto = 10% acima do preço médio do Mercado Livre (coluna ml_medio, quando houver);
# se depois do teto a margem ficar abaixo de 20% sobre o custo, a peça não entra no site.
MARGEM = [(30, 1.8), (100, 1.6), (250, 1.45), (float("inf"), 1.3)]
ISCA = 1.30
ISCA_PALAVRAS = ["oleo", "camara", "vela", "pastilha", "relacao cg 160", "kit relacao cg", "kit transmissao cg"]
MARGEM_MIN = 0.20
LUCRO_MIN_CARRINHO = 8.0  # peça com lucro menor só vai junto com outra (ou carrinho >= frete grátis)

def _n(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

def eh_isca(nome):
    t = _n(nome)
    if "filtro" in t or "fluido" in t:  # filtro de óleo e fluido de freio não são isca
        return False
    return any(w in t for w in ISCA_PALAVRAS)

def _noventa(x):
    import math
    n = math.floor(x)
    return round(n + 0.90 if x <= n + 0.90 else n + 1.90, 2)

def preco_de_custo(custo, categoria, nome="", ml_medio=None):
    f = ISCA if eh_isca(nome) else next(m for lim, m in MARGEM if custo <= lim)
    p = max(_noventa(custo * f), 9.90)
    if ml_medio:
        teto = ml_medio * 1.10
        if p > teto:
            p = _noventa(teto - 1) if _noventa(teto - 1) <= teto else round(teto, 2)
    if p < custo * (1 + MARGEM_MIN):
        return None
    return p

def _fsku(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")

def fotos_de(sku, partes=""):
    """Fotos reais baixadas em img/<sku>-N.webp. Kit usa a 1a foto de cada peca do kit."""
    fs = sorted((RAIZ / "img").glob(f"{_fsku(sku)}-*.webp"), key=lambda f: int(f.stem.rsplit("-", 1)[1]))
    out = [f"img/{f.name}" for f in fs]
    for pt in [x for x in (partes or "").split(";") if x]:
        out += [f"img/{f.name}" for f in sorted((RAIZ / "img").glob(f"{_fsku(pt)}-*.webp"))[:1]]
    return out

ACENTOS = {"organica": "orgânica", "camara": "câmara", "ignicao": "ignição", "lampada": "lâmpada", "transmissao": "transmissão",
           "oleo": "óleo", "fluído": "fluido", "eletrica": "elétrica", "suspensao": "suspensão", "relacao": "relação", "valvula": "válvula",
           "tras": "trás", "embreagem": "embreagem", "acelerador": "acelerador", "velocimetro": "velocímetro", "pneumatico": "pneumático", "sinalizacao": "sinalização", "dianteiro": "dianteiro"}

def nome_vitrine(nome, cat=""):
    """Nome da Real vem em maiúsculas com código e marca. Na loja mostra frase normal + marca; o código fica no SKU."""
    partes = [x.strip() for x in nome.split(" - ")]
    if len(partes) < 3:
        return nome
    desc, marca = partes[0], partes[-1]
    desc = re.sub(r"^ÓLEO FLUÍDO DE FREIO", "FLUIDO DE FREIO", desc, flags=re.I)
    pal = []
    for w in desc.split():
        lw = w.lower()
        pal.append(w if re.search(r"\d", w) else ACENTOS.get(lw, lw))
    txt = " ".join(pal)
    txt = txt[:1].upper() + txt[1:]
    marca = marca if len(marca) <= 3 else marca.title()
    cod = f" {partes[1]}" if cat in ("ignicao", "eletrica") and not re.search(r"\d", desc) else ""
    return f"{txt}{cod} {marca}"

def carregar():
    ps = []
    for r in csv.DictReader(open(RAIZ / ("dados/produtos_exemplo.csv" if EXEMPLO else "dados/produtos.csv"), encoding="utf-8")):
        if not r["sku"].strip():
            continue
        veic = [v.strip() for v in r["veiculos"].split(";") if v.strip()]
        p = dict(sku=r["sku"].strip(), nome=r["nome"].strip(), tipo=r["tipo"].strip(), categoria=r["categoria"].strip(),
                 marca=r["marca"].strip(), veiculos=veic, modelos=sorted({re.sub(r"\s*\(.*?\)", "", v) for v in veic}),
                 preco=float(r["preco"]) if r.get("preco", "").strip() else preco_de_custo(float(r["custo"]), r["categoria"].strip(), r["nome"], float(r["ml_medio"]) if (r.get("ml_medio") or "").strip() else None), estoque=int(r["estoque"] or 0), imagem=r["imagem"].strip(),
                 descricao=r["descricao"].strip())
        custo = float(r["custo"]) if (r.get("custo") or "").strip() else None
        p["addon"] = bool(custo is not None and p["preco"] is not None and p["preco"] - custo < LUCRO_MIN_CARRINHO)
        # participa da indicação: depois do desconto e da comissão, a peça ainda deixa o lucro mínimo
        p["ind"] = bool(IND and custo is not None and p["preco"] is not None
                        and p["preco"] - custo - (IND["desconto"] + IND["comissao"]) * p["preco"] >= IND.get("lucro_min", LUCRO_MIN_CARRINHO))
        if p["preco"] is None:
            continue
        p["fotos"] = fotos_de(p["sku"], r.get("partes", ""))
        p["partes"] = [x for x in (r.get("partes") or "").split(";") if x]
        p["slug"] = slug(p["nome"] + " " + p["sku"])
        p["url"] = f"peca-{p['slug']}.html"
        p["nome_real"], p["nome"] = p["nome"], nome_vitrine(p["nome"], p["categoria"])  # slug/URL continuam do nome original
        # Pesquisa 25/11: as grandes lojas dão à peça o nome da moto e do ano; o código técnico vira detalhe.
        p["nome"], p["spec"] = nome_por_moto(p["nome_real"], p["categoria"], veic, p["nome"])
        p["fams"] = [f[0] for f in familias(veic)]
        p["marca"] = re.sub(r"\s+(INDUSTRIA|IND\.?|MOTO PE[CÇ]AS|LTDA)\b.*$", "", p["marca"], flags=re.I)  # 'POLIMET INDUSTRIA METALURGICA' -> 'POLIMET'
        if p["marca"].isupper() and len(p["marca"]) > 3:
            p["marca"] = p["marca"].title()
        p["universal"] = not p["fams"] and any("universal" in v.lower() for v in veic)
        if p["categoria"] != "kit":  # a descrição da distribuidora é só o nome em maiúsculas; no site vai frase que o cliente entende
            p["descricao"] = f'{p["nome"]}. {(p["spec"] + ". ") if p["spec"] else ""}Peça nova, marca {p["marca"]}, código {p["sku"]}. Entrega por motoboy no mesmo dia na Grande Vitória.'
        ps.append(p)
    # Catálogo de 1000 (25/11): peças diferentes que ficaram com o mesmo nome (ex.: pistão em medidas diferentes) ganham o código no nome.
    rep = {}
    for p in ps:
        rep[p["nome"]] = rep.get(p["nome"], 0) + 1
    for p in ps:
        if p["categoria"] != "kit" and rep[p["nome"]] > 1 and p["sku"] not in p["nome"]:
            p["nome"] += f' (cód. {p["sku"]})'
    # Kit (25/11, modelo das lojas grandes): lista do que vem dentro e a conta real "separado x no kit".
    por = {p["sku"]: p for p in ps}
    for p in ps:
        p["itens"] = [por[x] for x in p["partes"] if x in por] if p["categoria"] == "kit" else []
        if p["itens"]:
            p["separado"] = round(sum(x["preco"] for x in p["itens"]), 2)
            p["economia"] = round(p["separado"] - p["preco"], 2)  # nunca inventada: é a soma das peças no site menos o preço do kit
            # dentro do kit da Bros, o filtro aparece como "Filtro de ar Bros 160", não com o nome de outra moto
            p["itens"] = [dict(x, nome=nome_por_moto(x["nome_real"], x["categoria"], x["veiculos"], x["nome"], primeiro=tuple(p["fams"]))[0]) for x in p["itens"]]
            nomes = [x["nome"] for x in p["itens"]]
            p["descricao"] = (f'{p["nome"]}. Vem com {len(nomes)} peças: {"; ".join(nomes)}. '
                              + (f'Comprando separado sai {brl(p["separado"])}; no kit sai {brl(p["preco"])}. ' if p["economia"] > 0 else "")
                              + "Entrega por motoboy no mesmo dia na Grande Vitória.")
    for p in ps:
        if p["itens"] and ":" in p["nome"]:
            p["titulo"], p["conteudo"] = [x.strip() for x in p["nome"].split(":", 1)]
            p["conteudo"] = p["conteudo"][0].upper() + p["conteudo"][1:]
    for p in ps:  # a peça sabe em que kits ela entra, para oferecer o kit na página dela
        p["em_kits"] = [k for k in ps if p["sku"] in k.get("partes", []) and k.get("economia", 0) > 0] if p["categoria"] != "kit" else []
    return ps

# ---------- moldura comum ----------
def head(title, desc, path, extra_ld=None, artifact=False):
    canon = f"{URL}/{'' if path == 'index.html' else path}"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (extra_ld or []))
    gid = CFG.get("google_ads_id", "")  # tag do Google Ads: liga sozinha quando o config tiver o ID (ex.: AW-123)
    ga = CFG.get("ga4_id", "")  # contador de visitas (Google Analytics, G-XXXX): liga sozinho quando o config tiver o ID
    tags = [t for t in (ga, gid) if t]
    if tags and not artifact:
        ld += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={e(tags[0])}"></script>'
               f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag("js",new Date());'
               + "".join(f'gtag("config","{e(t)}");' for t in tags) + '</script>')
    meta = (f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<link rel="canonical" href="{canon}"><meta property="og:title" content="{e(title)}">'
            f'<meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website">'
            f'<meta property="og:locale" content="pt_BR"><meta property="og:url" content="{canon}"><meta property="og:image" content="{URL}/img/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:site_name" content="Loja Dias Peças"><meta name="theme-color" content="#002776">'
            f'{FONTS}<link rel="stylesheet" href="assets/style.css">{ld}')
    if artifact:
        return meta
    return f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{meta}</head><body>'

def topo():
    demo = '<div class="demo">Prévia: peças, preços e fretes são exemplos. O catálogo real virá das distribuidoras.</div>' if DEMO else ""
    faixa = f'<div class="demo">Frete grátis acima de {brl(GRATIS)} <span class="demo2">(Serra e Viana: <span class="pc">acima de </span>R$ 89,90)</span></div>' if GRATIS and FRETE_OK else ""
    return f'''{demo}{faixa}<header class="top"><div class="wrap">
<a class="logo" href="index.html">Loja <span>Dias</span> Peças</a>
<nav class="nav" aria-label="Principal"><a href="{lk("moto")}">Peças de moto</a>{"" if SO_MOTO else f'<a href="{lk("carro")}">Carro</a>'}
<a href="entrega.html">Entrega</a><a href="index.html#duvidas">Dúvidas</a>{'<a id="contalink" href="minha-conta.html">Entrar</a>' if FIREBASE and not VITRINE else ""}
{'<a class="cartlink" href="pedido.html">Fazer pedido</a>' if VITRINE else '<a class="cartlink" href="carrinho.html">Carrinho <b class="cartcount">0</b></a>'}</nav></div></header>{catbar()}'''

# Luan 24/11: no lugar da faixa pontilhada, atalhos de categoria e as motos que mais saem (pesquisa de giro, CG primeiro).
ATALHOS = [("Kits prontos", "catalogo.html?cat=kit"), ("Freio dianteiro", "catalogo.html?cat=freio&q=dianteira"),
           ("Freio traseiro", "catalogo.html?cat=freio&q=traseira"), ("Fluido de freio", "catalogo.html?cat=freio&q=fluido"),
           ("Relação", "catalogo.html?cat=transmissao"), ("Filtros", "catalogo.html?cat=filtro"), ("Vela", "catalogo.html?cat=ignicao"),
           ("Câmara e pneu", "catalogo.html?cat=pneu"), ("Bateria e lâmpada", "catalogo.html?cat=eletrica"),
           ("Cabos", "catalogo.html?cat=cabo"), ("Retrovisor e manete", "catalogo.html?cat=acessorio")]
MOTOS_BARRA = ["CG 160", "CG 150", "CG 125", "Biz", "Pop", "Bros", "Fazer", "XRE", "Factor", "PCX"]

# Página por moto: (nome na tela, endereço, famílias do catálogo que entram nela, marca)
MOTOS = [("CG 160", "pecas-cg-160", ["CG 160"], "Honda"), ("CG 150", "pecas-cg-150", ["CG 150"], "Honda"), ("CG 125", "pecas-cg-125", ["CG 125"], "Honda"),
         ("Biz", "pecas-biz", ["Biz 125", "Biz 110i", "Biz 100"], "Honda"), ("Pop", "pecas-pop", ["Pop 100", "Pop 110i"], "Honda"),
         ("Bros 160", "pecas-bros-160", ["Bros 160"], "Honda"), ("Bros 150", "pecas-bros-150", ["Bros 150", "Bros 125"], "Honda"),
         ("Fazer 150", "pecas-fazer-150", ["Fazer 150", "Fazer FZ15"], "Yamaha"), ("Factor", "pecas-factor", ["Factor 150", "Factor 125"], "Yamaha"),
         ("Crosser 150", "pecas-crosser-150", ["Crosser 150"], "Yamaha"), ("XRE 300", "pecas-xre-300", ["XRE 300"], "Honda"),
         ("XRE 190", "pecas-xre-190", ["XRE 190"], "Honda"), ("Fazer 250", "pecas-fazer-250", ["Fazer 250"], "Yamaha"),
         ("Lander e Ténéré 250", "pecas-lander-tenere-250", ["Lander 250", "Ténéré 250"], "Yamaha"),
         ("Twister e CB 300", "pecas-twister-cb-300", ["Twister 250", "Twister 300", "CB 300"], "Honda"), ("PCX 150", "pecas-pcx-150", ["PCX 150"], "Honda")]
# Foto de cada moto (25/11, pedido do Luan). O Luan pediu (25/11) foto do modelo mais novo, 2020 em diante, e liberou foto oficial
# de divulgação da Honda e da Yamaha, sabendo que o fabricante pode pedir para tirar.
# Se pedirem: apagar o .webp e a linha em FOTOS_OFICIAIS (o card volta ao desenho).
# Moto que saiu de linha antes de 2020 (CG 150, CG 125, Bros 150) usa a foto do último modelo que existiu.
# FOTOS_MOTO fica para foto com licença livre do Wikimedia Commons. slug: (arquivo no Commons, autor, licença, link da licença)
FOTOS_MOTO = {}
# slug: (fabricante, modelo que aparece na foto, página de onde veio)
FOTOS_OFICIAIS = {
    "cg-160": ("Honda", "CG 160 Titan (modelo atual)", "https://www.honda.com.br/motos/street/city/cg160-titan"),
    "cg-150": ("Honda", "CG 150 Titan 2015 (último ano da CG 150)", "https://brosmotoclube.blogspot.com/2014/08/nova-honda-cg-150-titan-2015-vem-com.html"),
    "cg-125": ("Honda", "CG 125i Fan 2016 a 2018 (última CG 125)", "https://fichatecnica.motosblog.com.br/FichaTecnica/Honda/CG_125_i_FAN_2016"),
    "biz": ("Honda", "Biz 125 (modelo atual)", "https://www.honda.com.br/motos/street/city/biz125"),
    "pop": ("Honda", "Pop 110i ES (modelo atual)", "https://www.honda.com.br/motos/street/city/pop110i-es"),
    "bros-160": ("Honda", "NXR 160 Bros (modelo atual)", "https://www.honda.com.br/motos/adventure/trail/nxr160-bros"),
    "bros-150": ("Honda", "NXR 150 Bros 2014 (último ano da Bros 150)", "http://patriciahonda.blogspot.com/2013/12/nxr-bros-150-modelo-2014-nas-cores.html"),
    "xre-300": ("Honda", "XRE 300 2023 (último ano da XRE 300)", "https://www.motoo.com.br/galeria/honda-xre-300-2023-preco-ficha-tecnica-versoes-cores/"),
    "xre-190": ("Honda", "XRE 190 (modelo atual)", "https://www.honda.com.br/motos/adventure/trail/xre-190"),
    "twister-cb-300": ("Honda", "CB 300F Twister (modelo atual)", "https://www.honda.com.br/motos/street/naked/cb300f-twister"),
    "pcx-150": ("Honda", "PCX (modelo atual, motor 160)", "https://www.honda.com.br/motos/street/scooter/pcx"),
    "factor": ("Yamaha", "Factor 150 (modelo atual)", "https://www.yamaha-motor.com.br/product/factor-759373"),
    "fazer-150": ("Yamaha", "Fazer FZ15 (modelo atual)", "https://www.yamaha-motor.com.br/product/nova-fazer-fz15-abs-connected-770617"),
    "fazer-250": ("Yamaha", "Fazer FZ25 (modelo atual)", "https://www.yamaha-motor.com.br/product/fazer-fz25-connected-774117"),
    "crosser-150": ("Yamaha", "Crosser 150 Z (modelo atual)", "https://www.yamaha-motor.com.br/product/crosser-z-abs-connected-770797"),
    "lander-tenere-250": ("Yamaha", "Lander 250 (modelo atual)", "https://www.yamaha-motor.com.br/product/lander-connected-150305"),
}
MOTO_DESENHO = ('<svg viewBox="0 0 64 44" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<circle cx="12" cy="32" r="8.500"/><circle cx="52" cy="32" r="8.500"/>'
                '<path d="M12 32l9-8h12l5 8H24"/><path d="M52 32L44 12"/><path d="M40 10h7"/>'
                '<path d="M26 16h11l5 7H24z" fill="currentColor"/><path d="M10 17h15l-1 5H14z" fill="currentColor"/>'
                '<path d="M21 34h13" stroke-width="3.400"/><circle cx="47" cy="17" r="2.200" fill="currentColor"/></svg>')

def foto_moto(sl):
    """Caminho da foto da moto (img/motos/<slug>.webp) ou None. slug vem como 'pecas-cg-150'."""
    k = sl.replace("pecas-", "", 1)
    return f"img/motos/{k}.webp" if (RAIZ / "img/motos" / f"{k}.webp").exists() and (k in FOTOS_MOTO or k in FOTOS_OFICIAIS or (RAIZ / "img/motos" / f"{k}.propria").exists()) else None

def creditos():
    linhas = "".join(
        f'<li><b>{e(n)}</b>: foto de {e(FOTOS_MOTO[k][1])}, <a href="https://commons.wikimedia.org/wiki/File:{quote(FOTOS_MOTO[k][0])}" rel="noopener nofollow">Wikimedia Commons</a>, '
        + (f'licença <a href="{FOTOS_MOTO[k][3]}" rel="noopener nofollow">{e(FOTOS_MOTO[k][2])}</a>.' if FOTOS_MOTO[k][3] else f'{e(FOTOS_MOTO[k][2].lower())}.') + '</li>'
        for n, sl, _, _ in MOTOS for k in [sl.replace("pecas-", "", 1)] if k in FOTOS_MOTO and foto_moto(sl))
    oficiais = "".join(
        f'<li><b>{e(n)}</b>: {e(FOTOS_OFICIAIS[k][1])}, foto de divulgação da {e(FOTOS_OFICIAIS[k][0])}'
        + (f' (<a href="{FOTOS_OFICIAIS[k][2]}" rel="noopener nofollow">{"site do fabricante" if ("honda.com.br" in FOTOS_OFICIAIS[k][2] or "yamaha-motor.com.br" in FOTOS_OFICIAIS[k][2]) else "página onde a foto foi achada"}</a>)' if FOTOS_OFICIAIS[k][2] else "") + '.</li>'
        for n, sl, _, _ in MOTOS for k in [sl.replace("pecas-", "", 1)] if k in FOTOS_OFICIAIS and foto_moto(sl))
    corpo = f'''<section><div class="wrap prose"><h1>Créditos das fotos</h1>
{f"<h2>Fotos com uso liberado</h2><p>Estas fotos são de fotógrafos que liberaram o uso no Wikimedia Commons. Elas foram recortadas e reduzidas para caber no site. As versões recortadas das fotos com licença CC BY-SA ficam disponíveis sob a mesma licença.</p><ul>{linhas}</ul>" if linhas else ""}
{f"<h2>Fotos de divulgação dos fabricantes</h2><p>Estas fotos pertencem aos fabricantes das motos e aparecem aqui só para identificar o modelo. Se você representa o fabricante e quer que uma foto saia do site, chame no WhatsApp {e(CFG['whatsapp_exibir'])} que a gente tira.</p><ul>{oficiais}</ul>" if oficiais else ""}
<p>As fotos servem só para você reconhecer o modelo. A Loja Dias não tem ligação com os fabricantes das motos. Honda e Yamaha são marcas dos seus donos.</p></div></section>'''
    pagina("creditos.html", "Créditos das fotos | Loja Dias Peças", "Autores e licenças das fotos de motos usadas no site da Loja Dias.", corpo)

MOTOS_ATIVAS = []  # preenchido em main(): só moto com 3 peças próprias ou mais ganha página

def pecas_da_moto(ps, fams):
    return [p for p in ps if set(p.get("fams", [])) & set(fams)]

def catbar():
    if VITRINE:
        return ""
    a = "".join(f'<a href="{u}">{e(t)}</a>' for t, u in ATALHOS)
    m = "".join(f'<a class="moto" href="{sl}.html">{e(n)}</a>' for n, sl, _, _ in MOTOS_ATIVAS) or "".join(f'<a class="moto" href="catalogo.html?q={quote(n)}">{e(n)}</a>' for n in MOTOS_BARRA)
    vai = 'onchange="if(this.value){var u=this.value;this.selectedIndex=0;location.href=u}"'  # volta para a primeira opção: ao voltar a página, a lista não fica presa
    escolhas = (f'<div class="pick"><select aria-label="Escolha a sua moto" {vai}><option value="">Qual é a sua moto?</option>'
                + "".join(f'<option value="{sl}.html">{e(n)}</option>' for n, sl, _, _ in MOTOS_ATIVAS)
                + f'</select><select aria-label="Escolha o tipo de peça" {vai}><option value="">Tipo de peça</option>'
                + "".join(f'<option value="{e(u)}">{e(t)}</option>' for t, u in ATALHOS) + '</select></div>') if MOTOS_ATIVAS else ""
    return (f'<nav class="catbar{" tem-pick" if escolhas else ""}" aria-label="Categorias e motos"><div class="wrap">{escolhas}'
            f'<div class="rail">{a}</div><div class="rail motos"><span class="lbl2">Sua moto</span>{m}</div></div></nav>')

def lk(t):
    return f"pedido.html?tipo={t}" if VITRINE else f"catalogo.html?tipo={t}"

def rodape(artifact=False):
    cid = "".join(f'<a href="entrega-{c["slug"]}.html">Peças em {e(c["nome"])}</a>' for c in CFG["cidades"])
    wa = f'https://wa.me/{CFG["whatsapp"]}?text={xesc("Olá! Quero saber de uma peça.").replace(" ", "%20")}'
    tail = "" if artifact else "</body></html>"
    return f'''<footer><div class="wrap">
<div><b>Loja Dias Peças</b>Peças de moto e carro com entrega por motoboy na Grande Vitória, ES.<br>{e(CFG["horario"])}<br>WhatsApp {e(CFG["whatsapp_exibir"])}<br>CNPJ {e(CFG.get("cnpj",""))}</div>
<div><b>Entregamos em</b>{cid}</div>
<div><b>Comprar</b><a href="{lk("moto")}">Peças de moto</a>{"" if SO_MOTO else f'<a href="{lk("carro")}">Peças de carro</a>'}<a href="{"pedido.html" if VITRINE else "carrinho.html"}">{"Fazer pedido" if VITRINE else "Carrinho"}</a><a href="entrega.html">Prazos e fretes</a>{'<a href="indique.html">Indique e ganhe</a>' if IND and not VITRINE else ""}<a href="privacidade.html">Privacidade</a>{'<a href="creditos.html">Créditos das fotos</a>' if not VITRINE else ""}</div>
</div></footer>
<a class="wafloat" href="{wa}" target="_blank" rel="noopener" aria-label="Falar com a loja no WhatsApp"><svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.200 8.200 0 0 1-4.200-1.150l-.300-.180-3 .790.800-2.900-.200-.300A8.200 8.200 0 1 1 12 20.200zm4.500-6.100c-.250-.120-1.460-.720-1.690-.800-.230-.080-.390-.120-.560.120-.160.250-.640.800-.780.970-.140.160-.290.180-.530.060-.250-.120-1.040-.380-1.980-1.220-.730-.650-1.230-1.460-1.370-1.700-.140-.250-.020-.380.110-.500.110-.110.250-.290.370-.430.120-.140.160-.250.250-.410.080-.160.040-.310-.020-.430-.060-.120-.560-1.340-.760-1.840-.200-.480-.410-.420-.560-.420h-.480c-.160 0-.430.060-.660.310-.230.250-.860.840-.860 2.050 0 1.210.880 2.380 1 2.540.120.160 1.740 2.650 4.200 3.720.590.250 1.050.400 1.400.520.590.190 1.130.160 1.550.100.470-.070 1.460-.600 1.670-1.170.200-.580.200-1.070.140-1.170-.060-.110-.220-.170-.470-.290z"/></svg><span>WhatsApp</span></a>
<div class="buybar" id="buybar" hidden></div>
<script src="assets/loja.js"></script><script src="assets/app.js"></script>{'<script type="module" src="assets/conta.js"></script>' if FIREBASE and not VITRINE else ""}{tail}'''

def selo(p):
    if GRATIS and p["preco"] < 20:
        return f'<div class="stock">Compre junto e ganhe frete grátis</div>'
    return ""

def colagem(p, grande=False):
    """Foto do kit = as peças lado a lado (até 4), como a foto montada das lojas grandes."""
    fs = [x["fotos"][0] for x in p["itens"] if x["fotos"]][:4]
    if not fs:
        return icon("kit")
    return (f'<span class="colagem n{len(fs)}" role="img" aria-label="{e(p["nome"])}">'
            + "".join(f'<img src="{f}" alt=""{"" if grande else " loading=lazy"}>' for f in fs) + "</span>")

def card(p, foco=()):
    if foco and p["categoria"] != "kit":  # na página da Bros, a peça aparece como "Filtro de ar Bros 160, ..." e não com o nome de outra moto
        p = dict(p, nome=nome_por_moto(p["nome_real"], p["categoria"], p["veiculos"], p["nome"], primeiro=foco)[0])
    img = f'<img src="{p["fotos"][0]}" alt="{e(p["nome"])}" loading="lazy">' if p["fotos"] else icon(p["categoria"])
    kit = p.get("itens")
    if kit:
        img = colagem(p)
    low = p["estoque"] <= 3
    # O nome já diz a moto. Embaixo vai só o que ajuda a escolher: medida da relação ou "serve em qualquer moto".
    sub = p.get("spec") or ("Serve em qualquer moto" if p.get("universal") else "")
    if kit:
        sub = p.get("conteudo") or f'{len(kit)} peças no kit'
    selo_kit = f'<span class="kitselo">Economize {brl(p["economia"])}</span>' if kit and p["economia"] > 0 else ""
    return f'''<article class="card{" kit" if kit else ""}" data-sku="{e(p["sku"])}"><a class="ph" href="{p["url"]}" tabindex="-1">{img}{selo_kit}</a>
<div class="body"><h3><a href="{p["url"]}">{e(p.get("titulo") or p["nome"])}</a></h3>{f'<div class="fit">{e(sub)}</div>' if sub else ""}
{f'<div class="stock low">Últimas {p["estoque"]} unidades</div>' if low else ""}
<div class="row"><div class="price">{f'<s>{brl(p["separado"])}</s>' if kit and p["economia"] > 0 else ""}{brl(p["preco"])}<small>no Pix</small></div>
<button class="add" type="button" data-add="{e(p["sku"])}" aria-label="Adicionar {e(p["nome"])} ao carrinho">Adicionar</button></div></div></article>'''

def painel_mais(pecas, titulo, rodape, foco=()):
    """Painel da primeira tela: até 4 peças com foto, preço e botão Adicionar (home e página da moto)."""
    linhas = ""
    for p in pecas[:4]:
        nome = p.get("titulo") or p["nome"]
        if foco and p["categoria"] != "kit":
            nome = nome_por_moto(p["nome_real"], p["categoria"], p["veiculos"], p["nome"], primeiro=foco)[0]
        linhas += (f'<li><a class="mvf" href="{p["url"]}" tabindex="-1"><img src="{p["fotos"][0]}" alt="" width="72" height="72"></a>'
                   f'<a class="mvn" href="{p["url"]}">{e(nome)}</a>'
                   f'<span class="mvp">{brl(p["preco"])}<small>no Pix</small></span>'
                   f'<button class="add" type="button" data-add="{e(p["sku"])}" aria-label="Adicionar {e(nome)} ao carrinho">Adicionar</button></li>')
    return f'<aside class="maisv" aria-labelledby="mvh"><h2 id="mvh">{e(titulo)}</h2><ul>{linhas}</ul>{rodape}</aside>' if linhas else ""

def uma_por_tipo(pecas, n=4):
    """Uma peça de cada tipo, na ordem em que vieram (giro), só com foto. Completa com as seguintes se faltar."""
    out, vistos = [], set()
    for p in pecas:
        if p["fotos"] and p["categoria"] != "kit" and p["categoria"] not in vistos:
            out.append(p); vistos.add(p["categoria"])
    out += [p for p in pecas if p["fotos"] and p["categoria"] != "kit" and p not in out]
    return out[:n]

def tabela_frete():
    if not FRETE_OK:
        rows = "".join(f'<tr><td><a href="entrega-{c["slug"]}.html">{e(c["nome"])}</a></td><td>mesmo dia</td><td>informado no pedido</td></tr>' for c in CFG["cidades"])
        return f'<div class="tablebox"><table><thead><tr><th>Cidade</th><th>Prazo</th><th>Frete</th></tr></thead><tbody>{rows}</tbody></table></div>'
    rows = "".join(f'<tr><td><a href="entrega-{c["slug"]}.html">{e(c["nome"])}</a></td><td>{brl(c["normal"])}</td><td>{brl(c.get("gratis_acima") or GRATIS) if GRATIS else "—"}</td><td>até {CFG["entrega_ate"]} do mesmo dia</td></tr>' for c in CFG["cidades"])
    return f'<div class="tablebox"><table><thead><tr><th>Cidade</th><th>Frete</th><th>Grátis acima de</th><th>Prazo</th></tr></thead><tbody>{rows}</tbody></table></div>' + (f'<p class="note"><b>Frete grátis</b> a partir de {brl(GRATIS)} em Vitória, Vila Velha e Cariacica, e a partir de R$ 89,90 em Serra e Viana.</p>' if GRATIS else "")

FAQ = [
 ("Vocês entregam no mesmo dia?", f"Sim. Pedidos confirmados até {CFG['corte_mesmo_dia']} chegam até as {CFG['entrega_ate']} do mesmo dia em toda a Grande Vitória. Pedidos depois desse horário chegam no dia seguinte."),
 ("Como sei se a peça serve na minha moto ou carro?", "Informe o modelo e o ano do veículo. Se ficar em dúvida, mande o modelo, o ano e uma foto da peça antiga no WhatsApp que a gente confere antes de enviar."),
 ("Tem frete grátis?", f"Sim. Frete grátis a partir de {brl(GRATIS)} em Vitória, Vila Velha e Cariacica, e a partir de R$ 89,90 em Serra e Viana." if GRATIS else "Não no momento."),
 ("Quais formas de pagamento?", ("Pix. Você pode pagar na hora, com o Pix copia e cola do pedido, ou pagar no Pix ao motoboy quando a peça chegar." if NA_ENTREGA else "Por enquanto só Pix. Você recebe o Pix copia e cola com o valor exato do pedido.")),
 ("E se a peça vier errada?", "Se não servir, o motoboy busca e troca. Peça sem uso e na embalagem tem troca garantida em até 7 dias."),
 ("A peça tem garantia?", "Sim. Toda peça é nova e tem garantia de 90 dias contra defeito de fabricação."),
 ("Não achei minha peça. E agora?", "Trabalhamos com grandes distribuidoras do ES. Chame no WhatsApp com o modelo do veículo e a peça que você precisa."),
]

def faq_html():
    return "".join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in FAQ)

def loja_ld():
    return {"@context": "https://schema.org", "@type": "AutoPartsStore", "name": CFG["nome_loja"], "url": URL + "/",
            "telephone": "+" + CFG["whatsapp"], "taxID": CFG.get("cnpj", ""), "priceRange": "R$",
            "areaServed": [{"@type": "City", "name": c["nome"], "containedInPlace": {"@type": "State", "name": "Espírito Santo"}} for c in CFG["cidades"]],
            "paymentAccepted": "Pix", "openingHours": "Mo-Sa 08:00-18:00"}

# ---------- páginas ----------
def pagina(path, title, desc, corpo, ld=None, artifact=False):
    out = head(title, desc, path, ld, artifact) + topo() + "<main>" + corpo + "</main>" + rodape(artifact)
    (DIST / path).write_text(out, encoding="utf-8")

def mais_barata(ps, cat, termo=""):
    xs = [p for p in ps if p["categoria"] == cat and termo in p["nome"].lower()]
    return min(xs, key=lambda p: p["preco"]) if xs else None

def black_friday(ps, destaque):
    """Faixa Black Friday. Nada de desconto inventado: mostra preço real das peças que mais saem e a entrega no mesmo dia.
    (25/11: saiu a linha 'economiza R$ 2,90' dos kits; perto dos -40% das lojas grandes ela enfraquecia a faixa.)"""
    if not CFG.get("black_friday"):
        return ""
    kits = sorted([p for p in ps if p["categoria"] == "kit"], key=lambda k: -k.get("economia", 0))[:4]
    ja = {p["sku"] for p in destaque}
    extra, usadas = [], set()  # uma peça por categoria, para a faixa não ficar só de pastilha
    for p in ps:
        if p["categoria"] != "kit" and p["sku"] not in ja and p["fotos"] and p["categoria"] not in usadas and len(extra) < 8 - len(kits):
            extra.append(p); usadas.add(p["categoria"])
    rel = next((p for p in ps if p["categoria"] == "transmissao" and "CG 160" in p.get("fams", [])), None)
    past = mais_barata(ps, "freio", "pastilha")
    fatos = []
    if rel: fatos.append(f"Kit relação da CG 160 por {brl(rel['preco'])}")
    if past: fatos.append(f"pastilha de freio a partir de {brl(past['preco'])}")
    banner = (f'<img class="bfimg" src="img/banner-black-friday.webp" alt="" width="1920" height="480">'
              if (RAIZ / "img/banner-black-friday.webp").exists() else "")
    return f'''<section class="bf" aria-labelledby="bft"><div class="wrap">{banner}
<div class="bfhead"><h2 id="bft">Black Friday</h2><p>Sem preço inflado para fingir desconto. {", ".join(fatos) + ". " if fatos else ""}Frete grátis acima de {brl(GRATIS)} e entrega hoje para pedido até {CFG["corte_mesmo_dia"]}.</p></div>
<div class="grid">{"".join(card(p) for p in kits)}{"".join(card(p) for p in extra)}</div>
<p><a class="btn" href="catalogo.html?cat=kit">Ver todos os kits</a></p></div></section>'''

PORTAS = '''<section><div class="wrap split">
<a class="door" href="catalogo.html?tipo=moto"><span class="eyebrow">Peças de</span><b>Moto</b><span>Relação, freio, bateria, vela, cabos, pneus e óleo para CG, Biz, Pop, Bros, Factor, Fazer e mais.</span></a>
<a class="door" href="catalogo.html?tipo=carro"><span class="eyebrow">Peças de</span><b>Carro</b><span>Pastilha e disco, filtros, velas, palhetas, bateria e correia para Onix, HB20, Gol, Argo e mais.</span></a>
</div></section>'''

def home(ps, artifact=False):
    if VITRINE:
        return home_vitrine(artifact)
    if SO_MOTO:  # uma peça de cada tipo, na ordem do giro; antes eram 8 kits de relação seguidos
        destaque, vistos = [], set()
        for cat in ("transmissao", "freio", "filtro", "ignicao", "eletrica", "cabo", "pneu", "acessorio"):
            # kit relação: o da CG 160 vem primeiro (moto que mais roda e nosso melhor preço contra as lojas grandes)
            x = (next((p for p in ps if cat == "transmissao" and p["categoria"] == cat and p["fotos"] and "CG 160" in p.get("fams", [])), None)
                 or next((p for p in ps if p["categoria"] == cat and p["fotos"]), None))
            if x: destaque.append(x); vistos.add(x["sku"])
        for p in ps:  # completa com a segunda mais vendida de relação e freio
            if len(destaque) >= 12: break
            if p["sku"] not in vistos and p["categoria"] in ("transmissao", "freio") and p["fotos"]:
                destaque.append(p); vistos.add(p["sku"])
    else:
        destaque = [p for p in ps if p["tipo"] == "moto"][:4] + [p for p in ps if p["tipo"] == "carro"][:4]
    motos_tiles = "".join(
        f'<a href="{sl}.html"><span class="mf">{f"""<img src="{foto_moto(sl)}" alt="{e(marca)} {e(n)}" width="480" height="360" loading="lazy">""" if foto_moto(sl) else MOTO_DESENHO}</span>'
        f'<span class="mt"><b>{e(n)}</b><span>{len(pecas_da_moto(ps, fams))} peças</span></span></a>' for n, sl, fams, marca in MOTOS_ATIVAS)
    cats = lambda t: "".join(f'<a href="catalogo.html?tipo={t}&cat={c}">{n}</a>' for c, n in CATS.items() if any(p["tipo"] == t and p["categoria"] == c for p in ps))
    # Primeira tela (25/11, cenário do Luan): peça com foto, preço e botão aparecem sem rolar, no celular e no PC.
    topo4, destaque = destaque[:4], destaque[4:] or destaque
    corpo = f'''<div class="hero hero2"><div class="wrap">
<div class="hl"><h1>Peça de moto e carro na sua porta, hoje</h1>
<p><span class="pc">Entrega por motoboy no mesmo dia em Vitória, Vila Velha, Serra, Cariacica e Viana. {"Pague no Pix, agora ou na entrega." if NA_ENTREGA else "Pagamento no Pix."}</span><span class="cel">Motoboy entrega no mesmo dia na Grande Vitória.</span></p>
<form class="search" action="catalogo.html" role="search"><input name="q" id="hq" placeholder="Ex.: pastilha CG 160, filtro de ar Bros" aria-label="Buscar peça"><button class="btn" type="submit">Buscar</button></form>
<div class="chips"><span class="chip u"><i></i><span data-corte>Pedido até {CFG["corte_mesmo_dia"]}, entrega até {CFG["entrega_ate"]}</span></span></div></div>
{painel_mais(topo4, "Mais procuradas", f'<a class="mvt" href="catalogo.html">Ver todas as {len(ps)} peças</a>')}
<div class="chips c2">{f'<span class="chip"><i></i>Frete grátis acima de {brl(GRATIS)}</span>' if GRATIS and FRETE_OK else ""}<span class="chip"><i></i>{"Pix agora ou na entrega" if NA_ENTREGA else "Pix copia e cola"}</span><span class="chip"><i></i>Troca em 7 dias</span><span class="chip"><i></i>Garantia de 90 dias</span></div>
</div></div>
{"" if SO_MOTO else PORTAS}
{black_friday(ps, destaque)}
<section style="padding-top:0"><div class="wrap"><h2>Também saem muito</h2><div class="grid">{"".join(card(p) for p in destaque)}</div>
<p><a class="btn dark" href="catalogo.html">Ver todas as peças</a></p></div></section>
{f'<section><div class="wrap"><h2>Peças para a sua moto</h2><div class="mototiles">{motos_tiles}</div></div></section>' if motos_tiles else ""}
<section><div class="wrap split"><div><h2>Por tipo de peça</h2><div class="cats">{cats("moto")}</div></div>{"" if SO_MOTO else f'<div><h2>Carro</h2><div class="cats">{cats("carro")}</div></div>'}</div></section>
<section><div class="wrap"><h2>Como funciona</h2><ol class="steps">
<li><b>Escolha a peça</b><span>Busque pelo nome ou pelo modelo do seu veículo. Na dúvida, mande foto no WhatsApp.</span></li>
<li><b>Feche pelo WhatsApp</b><span>O pedido vai pronto com peças, frete e total. {"Pague no Pix agora ou ao motoboy, na entrega." if NA_ENTREGA else "Pague no Pix copia e cola."}</span></li>
<li><b>Receba com o motoboy</b><span>Pedido até {CFG["corte_mesmo_dia"]}: entrega até as {CFG["entrega_ate"]} do mesmo dia. Acompanhe pelo WhatsApp.</span></li></ol></div></section>
<section><div class="wrap"><h2>Frete por cidade</h2>{tabela_frete()}</div></section>
<section id="duvidas"><div class="wrap faq prose"><h2>Dúvidas</h2>{faq_html()}</div></section>'''
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    pagina("_artifact_index.html" if artifact else "index.html",
           "Loja Dias Peças | Peças de moto e carro com entrega na Grande Vitória",
           "Peças de moto e carro com entrega por motoboy no mesmo dia em Vitória, Vila Velha, Serra, Cariacica e Viana. Pagamento no Pix.",
           corpo, [loja_ld(), faq_ld], artifact)

def catalogo(ps):
    botoes = '<button type="button" data-c="todas">Todas</button>' + "".join(f'<button type="button" data-c="{c}">{n}</button>' for c, n in CATS.items())
    corpo = f'''<section><div class="wrap"><h1>Peças de moto e carro</h1>
<p class="note">Entrega por motoboy em toda a Grande Vitória. Não achou? Chame no WhatsApp.</p>
<div class="filters"><input id="q" type="search" placeholder="Buscar peça, código ou modelo" aria-label="Buscar">
<select id="tipo" aria-label="Moto ou carro"{" hidden" if SO_MOTO else ""}><option value="todos">Moto e carro</option><option value="moto">Moto</option>{"" if SO_MOTO else '<option value="carro">Carro</option>'}</select>
<select id="veic" aria-label="Seu veículo"></select></div>
<div class="cats" id="cats" style="margin-bottom:16px">{botoes}</div>
<div class="grid" id="grid">{"".join(card(p) for p in ps)}<p class="empty" id="none" hidden>Nenhuma peça encontrada com esses filtros. Mande o modelo e a peça no WhatsApp que a gente procura.</p></div>
</div></section>'''
    pagina("catalogo.html", "Catálogo de peças de moto e carro | Loja Dias Peças",
           "Todas as peças de moto e carro da Loja Dias com preço, compatibilidade e entrega por motoboy na Grande Vitória.", corpo)

def confianca():
    """O que loja nova precisa mostrar perto do botão: quem entrega, o que acontece se não servir, garantia e CNPJ."""
    itens = [f"Entrega pelo motoboy da loja. Pedido até {CFG['corte_mesmo_dia']} chega até as {CFG['entrega_ate']}"]
    if NA_ENTREGA:
        itens.append("Pague no Pix só quando a peça chegar, se preferir")
    itens += ["Não serviu? O motoboy busca e troca em até 7 dias", GARANTIA,
              f"Loja de {CFG['cidade_base']}, CNPJ {CFG.get('cnpj','')}"]
    return '<ul class="trust">' + "".join(f"<li>{e(t)}</li>" for t in itens) + "</ul>"

def leve_junto(p, ps):
    """Peças baratas que servem na mesma moto (ou em qualquer uma), de outras categorias: ajudam a fechar o frete grátis."""
    if p["categoria"] == "kit":
        return []
    fams = set(p.get("fams", []))
    cand = [x for x in ps if x["sku"] != p["sku"] and x["categoria"] not in (p["categoria"], "kit") and x["fotos"]
            and ((fams and set(x.get("fams", [])) & fams) or (x.get("universal") and x["categoria"] in ("pneu", "freio", "eletrica") and x["preco"] < 60))]
    ordem = ["freio", "filtro", "ignicao", "transmissao", "pneu", "eletrica", "cabo", "acessorio"]  # o que mais se troca vem primeiro
    cand.sort(key=lambda x: (not (set(x.get("fams", [])) & fams), x["preco"] > 60, ordem.index(x["categoria"]) if x["categoria"] in ordem else 9))
    out, usadas = [], set()
    for x in cand:
        if x["categoria"] not in usadas:
            out.append(x); usadas.add(x["categoria"])
        if len(out) == 4:
            break
    return out

def ficha(p):
    """Medidas legíveis. Hoje só o kit relação traz medida no nome da distribuidora."""
    from nomes import spec_relacao
    if p["categoria"] != "transmissao":
        return ""
    sp = spec_relacao(p["nome_real"].split(" - ")[0])
    if not sp:
        return ""
    return (f'<dt>Coroa</dt><dd>{sp["coroa"]} dentes</dd><dt>Pinhão</dt><dd>{sp["pinhao"]} dentes</dd>'
            f'<dt>Corrente</dt><dd>{sp["corrente"]}, {sp["elos"]} elos{", com retentor (O-ring)" if sp["retentor"] else ", sem retentor"}</dd>')

def kit_lista(p):
    """'O que vem no kit': cada peça com foto, preço dela e a conta no fim. É a 'Produtos do kit' das lojas grandes, com a soma à vista."""
    linhas = "".join(
        f'<li><a class="kfoto" href="{x["url"]}" tabindex="-1">{f"""<img src="{x["fotos"][0]}" alt="" loading="lazy">""" if x["fotos"] else icon(x["categoria"])}</a>'
        f'<div class="knome"><a href="{x["url"]}">{e(x["nome"])}</a><span>1 unidade{(". " + e(x["spec"])) if x.get("spec") else ""}</span></div>'
        f'<div class="kpreco">{brl(x["preco"])}</div></li>' for x in p["itens"])
    conta = (f'<div class="kconta"><div><span>Comprando separado</span><s>{brl(p["separado"])}</s></div>'
             f'<div class="kfinal"><span>No kit</span><b>{brl(p["preco"])}</b></div>'
             f'<p>Você economiza {brl(p["economia"])} e recebe tudo na mesma entrega.</p></div>') if p["economia"] > 0 else ""
    return f'<section class="kitbox" aria-labelledby="kitt"><h2 id="kitt">O que vem no kit</h2><ul>{linhas}</ul>{conta}</section>'

def no_kit(p):
    """Na página da peça: o kit que já traz essa peça, com a economia real."""
    ks = sorted(p.get("em_kits", []), key=lambda k: -k["economia"])[:2]
    if not ks:
        return ""
    return '<div class="nokit"><b>Leve no kit e pague menos</b>' + "".join(
        f'<a href="{k["url"]}"><span>{e(k.get("titulo") or k["nome"])}</span><span class="nk">{brl(k["preco"])}<small>economize {brl(k["economia"])}</small></span></a>' for k in ks) + "</div>"

def produto(p, ps=()):
    img = f'<img id="fotomain" src="{p["fotos"][0]}" alt="{e(p["nome"])}">' if p["fotos"] else icon(p["categoria"])
    kit = p.get("itens")
    thumbs = "".join(f'<button type="button" class="thumb" data-foto="{f}" aria-label="Foto {i+1}"><img src="{f}" alt="" loading="lazy"></button>' for i, f in enumerate(p["fotos"])) if len(p["fotos"]) > 1 else ""
    if kit:
        img, thumbs = colagem(p, grande=True), ""
    opts = "".join(f'<option value="{c["slug"]}">{e(c["nome"])}</option>' for c in CFG["cidades"])
    veic = "".join(f"<li>{e(veiculo_legivel(v))}</li>" for v in p["veiculos"])
    zap = lambda t: f'https://wa.me/{CFG["whatsapp"]}?text=' + quote(t)
    wa_compra = zap(f"Olá! Quero comprar: {p['nome']} (cód. {p['sku']}) por {brl(p['preco'])}. Minha moto é: ")
    wa_serve = zap(f"Olá! Essa peça serve na minha moto? {p['nome']} (cód. {p['sku']}). Minha moto é: ")
    junto = leve_junto(p, ps)
    falta = GRATIS - p["preco"] if GRATIS and p["preco"] < GRATIS else 0
    junto_html = (f'<section class="junto"><h2>Leve junto</h2><p class="note">{("Faltam " + brl(falta) + " para o frete grátis. ") if falta else ""}Servem na mesma moto e vão na mesma entrega.</p><div class="grid">{"".join(card(x) for x in junto)}</div></section>' if junto else "")
    motos_links = "".join(f'<a href="{sl}.html">Todas as peças para {e(n)}</a>' for n, sl, fams, _ in MOTOS_ATIVAS if set(fams) & set(p.get("fams", [])))
    desc = p["descricao"]
    corpo = f'''<div class="wrap"><nav class="crumbs" aria-label="Caminho"><a href="index.html">Início</a> › <a href="catalogo.html?tipo={p["tipo"]}">Peças de {TIPOS[p["tipo"]].lower()}</a> › <a href="catalogo.html?tipo={p["tipo"]}&cat={p["categoria"]}">{CATS[p["categoria"]]}</a></nav>
<div class="pdp"><div><div class="ph">{img}</div>{f'<div class="thumbs">{thumbs}</div>' if thumbs else ""}</div>
<div class="buy" data-produto="{e(p["sku"])}"><h1>{e(p.get("titulo") or p["nome"])}</h1>
{f'<p class="specline">{e(p.get("conteudo") or p["spec"])}</p>' if p.get("spec") or p.get("conteudo") else ""}
<div class="pricebox">{f'<div class="de">Separado: <s>{brl(p["separado"])}</s></div>' if kit and p["economia"] > 0 else ""}<div class="bigprice">{brl(p["preco"])}</div><div class="pixprice">no Pix{", agora ou na entrega" if NA_ENTREGA else ""}</div>{f'<div class="eco">Você economiza {brl(p["economia"])}</div>' if kit and p["economia"] > 0 else ""}</div>
{f'<div class="stock low">Últimas {p["estoque"]} unidades</div>' if p["estoque"] <= 3 else ""}
<p class="corte" data-corte>Pedido até {CFG["corte_mesmo_dia"]} chega hoje até as {CFG["entrega_ate"]}.</p>
{'<p class="note">Peça de complemento: vai junto com outra peça do pedido.</p>' if p["addon"] else ""}
<div class="cta"><button class="btn big" type="button" data-buy="{e(p["sku"])}">Comprar agora</button>
<a class="btn wa" href="{wa_compra}" target="_blank" rel="noopener">Comprar pelo WhatsApp</a>
<button class="btn ghost" type="button" data-add="{e(p["sku"])}">Adicionar ao carrinho</button></div>
<div class="ship"><label class="lbl" for="shipcity">Frete para</label><select id="shipcity">{opts}</select><div id="shipout" class="note"></div></div>
{confianca()}
{no_kit(p)}
<a class="serve" href="{wa_serve}" target="_blank" rel="noopener">Não sabe se serve? Mande o modelo e o ano no WhatsApp</a>
{f'<button class="btn ghost share" type="button" data-share="{e(p["url"])}" data-share-txt="{e(p["nome"] + " por " + brl(p["preco"]) + ", entrega no mesmo dia na Grande Vitória")}">Compartilhar esta peça no WhatsApp</button>' if IND else ""}
</div></div>
{kit_lista(p) if kit else ""}
{junto_html}
<section class="prose"><h2>Detalhes</h2><p>{e(desc)}</p>
<dl class="facts">{ficha(p)}<dt>Serve em</dt><dd><ul>{veic}</ul></dd><dt>Marca</dt><dd>{e(", ".join(dict.fromkeys(x["marca"] for x in kit)) if kit else p["marca"])}</dd><dt>Código</dt><dd>{e(p["sku"])}</dd><dt>Garantia</dt><dd>90 dias contra defeito de fabricação. Troca em até 7 dias se não servir.</dd></dl>
{f'<p class="motolinks">{motos_links}</p>' if motos_links else ""}</section>
</div>'''
    ld = [{"@context": "https://schema.org", "@type": "Product", "name": p["nome"], "sku": p["sku"], "mpn": p["sku"], "description": desc,
           "brand": {"@type": "Brand", "name": p["marca"]}, "category": f"{CATS[p['categoria']]} de {TIPOS[p['tipo']].lower()}",
           **({"image": [f"{URL}/{f}" for f in p["fotos"]]} if p["fotos"] else {}),
           "offers": {"@type": "Offer", "price": f"{p['preco']:.2f}", "priceCurrency": "BRL", "url": f"{URL}/{p['url']}",
                      "availability": "https://schema.org/InStock" if p["estoque"] > 0 else "https://schema.org/OutOfStock",
                      "itemCondition": "https://schema.org/NewCondition", "seller": {"@type": "Organization", "name": CFG["nome_loja"]}}},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Início", "item": URL + "/"},
              {"@type": "ListItem", "position": 2, "name": f"Peças de {TIPOS[p['tipo']].lower()}", "item": f"{URL}/catalogo.html?tipo={p['tipo']}"},
              {"@type": "ListItem", "position": 3, "name": p["nome"]}]}]
    pagina(p["url"], f"{p['nome']} | {brl(p['preco'])} com entrega na Grande Vitória",
           f"{p['nome']} por {brl(p['preco'])} no Pix. Serve em {', '.join(p['modelos'][:3])}. Entrega por motoboy hoje em Vitória, Vila Velha, Serra, Cariacica e Viana.",
           corpo, ld)

def home_vitrine(artifact=False):
    corpo = f'''<div class="hero"><div class="wrap">
<span class="eyebrow" style="color:var(--road-muted)">Grande Vitória · ES</span>
<h1>Peça de moto e carro na sua porta, hoje</h1>
<p>Diga a peça e o modelo do veículo. A gente confere, manda o valor e entrega por motoboy no mesmo dia em Vitória, Vila Velha, Serra, Cariacica e Viana. Pagamento no Pix.</p>
<div style="display:flex;flex-wrap:wrap;gap:8px"><a class="btn" href="pedido.html">Fazer pedido</a></div>
<div class="chips"><span class="chip"><i></i>Pedido até {CFG["corte_mesmo_dia"]}, entrega até {CFG["entrega_ate"]}</span>{f'<span class="chip"><i></i>Frete grátis acima de {brl(GRATIS)}</span>' if GRATIS and FRETE_OK else ""}<span class="chip"><i></i>Pix copia e cola</span><span class="chip"><i></i>Troca garantida</span></div>
</div></div>
<section><div class="wrap split">
<a class="door" href="pedido.html?tipo=moto"><span class="eyebrow">Peças de</span><b>Moto</b><span>Relação, freio, bateria, vela, cabos, pneus, óleo, filtros e elétrica para CG, Biz, Pop, Bros, Factor, Fazer, NMax e mais.</span></a>{"" if SO_MOTO else '\n<a class="door" href="pedido.html?tipo=carro"><span class="eyebrow">Peças de</span><b>Carro</b><span>Pastilha e disco, filtros, velas, palhetas, bateria, lâmpadas e correia para Onix, HB20, Gol, Argo, Strada e mais.</span></a>'}
</div></section>
<section><div class="wrap"><h2>Como funciona</h2><ol class="steps">
<li><b>Diga o que precisa</b><span>Peça, modelo e ano do veículo. Se tiver, mande foto da peça antiga.</span></li>
<li><b>Receba o valor e o Pix</b><span>A gente confere na distribuidora e manda o preço com frete e o Pix copia e cola.</span></li>
<li><b>Receba com o motoboy</b><span>Pedido até {CFG["corte_mesmo_dia"]}: entrega até as {CFG["entrega_ate"]} do mesmo dia. Depois disso, no dia seguinte.</span></li></ol></div></section>
<section><div class="wrap"><h2>Onde entregamos</h2>{tabela_frete()}</div></section>
<section id="duvidas"><div class="wrap faq prose"><h2>Dúvidas</h2>{faq_html()}</div></section>'''
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    pagina("_artifact_index.html" if artifact else "index.html",
           "Loja Dias Peças | Peças de moto e carro com entrega na Grande Vitória",
           "Peças de moto e carro com entrega por motoboy no mesmo dia em Vitória, Vila Velha, Serra, Cariacica e Viana. Pagamento no Pix.",
           corpo, [loja_ld(), faq_ld], artifact)

def pedido():
    opts = "".join(f'<option value="{e(c["nome"])}">{e(c["nome"])}</option>' for c in CFG["cidades"])
    corpo = f'''<div class="wrap" style="padding-block:24px 40px;max-width:640px"><div class="panel">
<h1 style="font-size:36px">Fazer pedido</h1>
<p class="note">Preencha e toque no botão. A mensagem abre pronta no WhatsApp da loja. A gente responde com o valor, o frete e o Pix copia e cola.</p>
<form id="pedidoform" style="display:grid;gap:12px">
<fieldset><legend class="lbl">Peça para</legend>
<label class="opt"><input type="radio" name="ptipo" id="ptMoto" value="moto" checked><span>Moto</span></label>
{"" if SO_MOTO else '<label class="opt"><input type="radio" name="ptipo" id="ptCarro" value="carro"><span>Carro</span></label>'}</fieldset>
<div class="field"><label class="lbl" for="pveic">Modelo e ano</label><input id="pveic" placeholder="Ex.: CG 160 Fan 2020, Onix 1.0 2018" required></div>
<div class="field"><label class="lbl" for="ppeca">Peça</label><input id="ppeca" placeholder="Ex.: pastilha de freio dianteira, kit relação" required></div>
<div class="field"><label class="lbl" for="pcid">Cidade</label><select id="pcid"><option value="">Escolha a cidade</option>{opts}</select></div>
<div class="field"><label class="lbl" for="pbairro">Bairro</label><input id="pbairro" placeholder="Seu bairro"></div>
<div class="field"><label class="lbl" for="pnome">Seu nome</label><input id="pnome" autocomplete="name" placeholder="Nome"></div>
<p class="err" id="perr" hidden></p>
<a class="btn wa" id="psend" href="#" target="_blank" rel="noopener" aria-disabled="true">Enviar pedido no WhatsApp</a>
<p class="note">WhatsApp da loja: {e(CFG["whatsapp_exibir"])}</p>
</form></div></div>'''
    pagina("pedido.html", "Fazer pedido | Loja Dias Peças",
           "Peça de moto ou carro com entrega por motoboy no mesmo dia na Grande Vitória. Envie o pedido pelo WhatsApp.", corpo)

def cidade(c, ps):
    mais = [p for p in ps if p["estoque"] > 3][:8]
    corpo = f'''<div class="hero"><div class="wrap"><span class="eyebrow" style="color:var(--road-muted)">Entrega em {e(c["nome"])}, ES</span>
<h1>Peças de moto e carro em {e(c["nome"])} com entrega por motoboy</h1>
<p>Entrega {("por " + brl(c["normal"]) + ", ") if FRETE_OK else ""}até as {CFG["entrega_ate"]} do mesmo dia para pedidos até {CFG["corte_mesmo_dia"]}. Depois disso, no dia seguinte. Pagamento no Pix.</p>
<div><a class="btn" href="{"pedido.html" if VITRINE else "catalogo.html"}">{"Fazer pedido" if VITRINE else "Ver peças"}</a></div></div></div>
{"" if VITRINE else f'<section><div class="wrap"><h2>Peças prontas para entregar em {e(c["nome"])}</h2><div class="grid">{"".join(card(p) for p in mais)}</div></div></section>'}
<section><div class="wrap prose"><h2>Como é a entrega em {e(c["nome"])}</h2>
<p>A peça sai separada e conferida com a rede de motoboys da Loja Dias. Você recebe o aviso no WhatsApp quando o motoboy sai e quando ele está chegando. Para oficinas de {e(c["nome"])}, a peça vai direto para a bancada.</p>
{tabela_frete()}</div></section>'''
    ld = [dict(loja_ld(), areaServed={"@type": "City", "name": c["nome"]})]
    pagina(f"entrega-{c['slug']}.html", f"Peças de moto e carro em {c['nome']} | Entrega hoje | Loja Dias",
           f"Peças de moto e carro com entrega por motoboy em {c['nome']}, ES. Entrega no mesmo dia para pedidos até {CFG['corte_mesmo_dia']}. Pagamento no Pix.",
           corpo, ld)

def pagina_moto(nome, sl, fams, marca, ps):
    proprias = pecas_da_moto(ps, fams)
    kits = sorted([p for p in proprias if p["categoria"] == "kit"], key=lambda k: -k.get("economia", 0))
    proprias = [p for p in proprias if p["categoria"] != "kit"]
    gerais = [p for p in ps if p.get("universal") and p["tipo"] == "moto"]
    tipos = []
    for p in proprias:
        t = CATS[p["categoria"]].lower()
        if p["categoria"] != "kit" and t not in tipos: tipos.append(t)
    lista = ", ".join(tipos[:5])
    outras = "".join(f'<a href="{s2}.html">{e(n2)}</a>' for n2, s2, _, _ in MOTOS_ATIVAS if s2 != sl)
    painel = painel_mais(uma_por_tipo(proprias), f"Mais procuradas da {nome}", f'<a class="mvt" href="#todas">Ver as {len(proprias)} peças da {e(nome)}</a>', fams)
    corpo = f'''<div class="hero hero2 heromoto"><div class="wrap"><div class="hl"><h1>Peças para {e(nome)} com entrega hoje</h1>
<p><span class="pc">{len(proprias)} peças que servem na {e(marca)} {e(nome)}: {e(lista)}. Entrega por motoboy em Vitória, Vila Velha, Serra, Cariacica e Viana.</span><span class="cel">{len(proprias)} peças que servem na {e(marca)} {e(nome)}. Motoboy entrega no mesmo dia na Grande Vitória.</span></p>
<div class="chips"><span class="chip u"><i></i><span data-corte>Pedido até {CFG["corte_mesmo_dia"]}, entrega até {CFG["entrega_ate"]}</span></span></div></div>
{painel}
<div class="chips c2">{f'<span class="chip"><i></i>Frete grátis acima de {brl(GRATIS)}</span>' if GRATIS and FRETE_OK else ""}<span class="chip"><i></i>{"Pix agora ou na entrega" if NA_ENTREGA else "Pix copia e cola"}</span><span class="chip"><i></i>Troca em 7 dias</span></div></div></div>
{f'<section class="kitsmoto"><div class="wrap"><h2>Kits prontos para a {e(nome)}</h2><p class="note">Peças que se trocam juntas, já separadas. O kit sai mais barato que comprar uma por uma.</p><div class="grid">{"".join(card(p, fams) for p in kits)}</div></div></section>' if kits else ""}
<section{' style="padding-top:0"' if kits else ""}><div class="wrap"><h2 id="todas">Feitas para a {e(nome)}</h2><div class="grid">{"".join(card(p, fams) for p in proprias)}</div></div></section>
{f'<section style="padding-top:0"><div class="wrap"><h2>Servem em qualquer moto</h2><div class="grid">{"".join(card(p) for p in gerais)}</div></div></section>' if gerais else ""}
<section style="padding-top:0"><div class="wrap prose"><h2>Não achou a peça da sua {e(nome)}?</h2><p>Mande o ano da moto e a peça no WhatsApp {e(CFG["whatsapp_exibir"])}. A gente confere na distribuidora e responde com o preço.</p>
<h2 style="margin-top:28px">Outras motos</h2><div class="cats">{outras}</div></div></section>'''
    ld = [{"@context": "https://schema.org", "@type": "ItemList", "name": f"Peças para {marca} {nome}",
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{URL}/{p['url']}", "name": p["nome"]} for i, p in enumerate(kits + proprias)]}]
    pagina(f"{sl}.html", f"Peças para {marca} {nome} com entrega hoje na Grande Vitória | Loja Dias",
           f"Peças para {marca} {nome}: {lista}. Entrega por motoboy no mesmo dia em Vitória, Vila Velha, Serra, Cariacica e Viana. Frete grátis acima de {brl(GRATIS)}.",
           corpo, ld)

def indique(ps):
    """Página do programa de indicação: a pessoa cria o link dela, avisa a loja (para receber a comissão) e compartilha."""
    pct = lambda x: f"{round(x * 100):g}%"
    d, c, dias = pct(IND["desconto"]), pct(IND["comissao"]), IND.get("dias", 30)
    n = sum(1 for p in ps if p["ind"])
    ex = next((p for p in sorted(ps, key=lambda p: -p["preco"]) if p["ind"] and p["categoria"] == "kit" and p["preco"] < 120), None)
    exemplo = (f'<p class="note">Exemplo: o cliente compra o {e(ex.get("titulo") or ex["nome"])} de {brl(ex["preco"])} pelo seu link. '
               f'Ele paga {brl(ex["preco"] * (1 - IND["desconto"]))} e você ganha {brl(ex["preco"] * IND["comissao"])} no Pix.</p>') if ex else ""
    corpo = f'''<section><div class="wrap prose indique" style="max-width:720px">
<h1>Indique e ganhe</h1>
<p class="lead">Mande o seu link para os amigos e grupos de motoboy. Quem compra pelo seu link ganha <b>{d} de desconto</b>. Você ganha <b>{c} de comissão no Pix</b> em cada venda.</p>
<div class="panel" id="indbox">
<h2>1. Crie o seu link</h2>
<div class="field"><label class="lbl" for="inome">Seu nome</label><input id="inome" autocomplete="given-name" placeholder="Ex.: João"></div>
<div class="field"><label class="lbl" for="itel">Seu WhatsApp com DDD</label><input id="itel" inputmode="tel" autocomplete="tel" placeholder="Ex.: 27 99999-1234"></div>
<div class="field"><label class="lbl" for="ipix">Sua chave Pix (para receber a comissão)</label><input id="ipix" placeholder="CPF, celular, e-mail ou chave aleatória"></div>
<p class="err" id="ierr" hidden></p>
<a class="btn wa big" id="iativar" href="#" target="_blank" rel="noopener" aria-disabled="true">Criar meu link e avisar a loja</a>
<p class="note">Abre o WhatsApp da loja com seus dados prontos. É só apertar enviar. Assim a loja sabe para quem pagar.</p>
</div>
<div class="panel" id="indlink" hidden>
<h2>2. Compartilhe</h2>
<p>Seu código: <b class="codigo" id="icod"></b></p>
<div class="linkbox"><input id="ilink" readonly aria-label="Seu link"><button class="btn dark" type="button" id="icopiar">Copiar link</button></div>
<a class="btn wa big" id="izap" href="#" target="_blank" rel="noopener">Mandar no WhatsApp (grupos e contatos)</a>
<button class="btn ghost" type="button" id="imais" hidden>Mandar por outro app</button>
<span class="lbl" style="margin-top:14px">Mensagem pronta</span>
<textarea id="imsg" rows="6" readonly></textarea>
<button class="btn ghost" type="button" id="icopmsg">Copiar mensagem</button>
<p class="note">Dica: em qualquer peça do site tem o botão <b>Compartilhar esta peça no WhatsApp</b>. Neste celular ele já manda com o seu link.</p>
<button class="btn ghost" type="button" id="itrocar">Não sou eu / criar outro link</button>
</div>
<h2>Como funciona</h2>
<ol>
<li>Quem abre o seu link fica com o desconto por {dias} dias naquele celular, em qualquer página do site.</li>
<li>O desconto de {d} vale para {n} peças e kits (a maioria). No carrinho aparece quanto o cliente economizou.</li>
<li>O pedido chega na loja com o seu código. Depois que o cliente paga e recebe a peça, a loja manda {c} do valor dessas peças para a sua chave Pix.</li>
<li>Não vale compra feita no seu próprio link.</li>
</ol>
{exemplo}
<p class="note">Dúvida? Chame a loja no WhatsApp {e(CFG["whatsapp_exibir"])}.</p>
</div></section>'''
    pagina("indique.html", "Indique e ganhe | Loja Dias Peças",
           f"Mande o seu link da Loja Dias: quem compra ganha {d} de desconto e você ganha {c} de comissão no Pix.", corpo)

def entrega():
    corpo = f'''<section><div class="wrap prose"><h1>Entrega e fretes</h1>
<p>Entregamos com motoboy em toda a Grande Vitória. Pedidos confirmados até {CFG["corte_mesmo_dia"]} chegam até as {CFG["entrega_ate"]} do mesmo dia. Pedidos depois desse horário chegam no dia seguinte.</p>
{tabela_frete()}
<h2 style="margin-top:28px">Peças grandes</h2><p>Peças que não cabem no baú da moto, como escapamento, para-choque e par de amortecedores, são combinadas pelo WhatsApp para retirada ou frete de carro.</p></div></section>'''
    pagina("entrega.html", "Entrega e fretes na Grande Vitória | Loja Dias Peças",
           "Fretes e prazos de entrega por motoboy em Vitória, Vila Velha, Serra, Cariacica e Viana.", corpo)

def carrinho():
    corpo = f'''<div class="wrap cartpage"><div class="panel"><h1 style="font-size:36px">Seu pedido</h1><div id="lines"></div><div id="meta" class="meta" hidden></div><div id="sugest" class="sugest" hidden></div><div class="tot" id="tot"></div></div>
<div class="panel">
<fieldset><legend class="lbl">Entrega</legend>
<label class="opt"><input type="radio" name="ship" id="shipN" value="normal" checked><span>Motoboy<small>Pedido até {CFG["corte_mesmo_dia"]}, entrega até {CFG["entrega_ate"]}{(". Frete grátis acima de " + brl(GRATIS)) if GRATIS else ""}</small></span><em id="feeN">—</em></label>
<label class="opt"><input type="radio" name="ship" id="shipR" value="retirada"><span>Retirar<small>Combinar pelo WhatsApp</small></span><em>R$ 0,00</em></label></fieldset>
<div class="field" id="citybox"><label class="lbl" for="city">Cidade</label><select id="city"></select></div>
<div class="field" id="addrbox"><label class="lbl" for="addr">Endereço e bairro</label><input id="addr" placeholder="Rua, número, bairro" autocomplete="street-address"></div>
<div class="field"><label class="lbl" for="name">Seu nome</label><input id="name" placeholder="Nome para a entrega" autocomplete="name"></div>
{('<fieldset><legend class="lbl">Pagamento</legend>'
'<label class="opt"><input type="radio" name="pay" value="agora" checked><span>Pix agora<small>O código copia e cola aparece aqui com o valor exato</small></span></label>'
'<label class="opt"><input type="radio" name="pay" value="entrega"><span>Pix na entrega<small>Você paga ao motoboy quando a peça chegar</small></span></label></fieldset>') if NA_ENTREGA else '<div class="field"><span class="lbl">Pagamento</span><span>Pix. O código copia e cola aparece aqui com o valor exato.</span></div>'}
<p class="err" id="err" hidden></p>
<div id="pixbox" class="ship" hidden><span class="lbl">Pix copia e cola</span><textarea id="pixcode" readonly rows="4" style="width:100%;font-family:var(--mono);font-size:12px;border:1px solid var(--line);border-radius:9px;padding:8px;background:var(--bg);color:var(--ink);resize:none"></textarea><button class="btn dark" type="button" id="pixcopy">Copiar código Pix</button><span class="note">Pague no app do seu banco (Pix › Copia e cola) e depois envie o pedido com o comprovante.</span></div>
<a class="btn wa big" id="send" href="#" target="_blank" rel="noopener" aria-disabled="true">Enviar pedido e comprovante no WhatsApp</a>
<p class="note">O pedido abre pronto no WhatsApp da loja. A gente confirma a peça e o horário de entrega na hora.</p>
{confianca()}</div></div>'''
    head_ = head("Carrinho | Loja Dias Peças", "Seu pedido na Loja Dias Peças.", "carrinho.html")
    out = head_.replace("<title>", '<meta name="robots" content="noindex"><title>', 1) + topo() + "<main>" + corpo + "</main>" + rodape()
    (DIST / "carrinho.html").write_text(out, encoding="utf-8")

def admin():
    corpo = '''<section><div class="wrap prose" style="max-width:760px"><h1>Pedidos da loja</h1><div id="admin"><p class="note">Carregando…</p></div></div></section>'''
    out = head("Pedidos | Loja Dias", "Tela da loja.", "admin.html").replace("<title>", '<meta name="robots" content="noindex,nofollow"><title>', 1) \
        + topo() + "<main>" + corpo + "</main>" + rodape().replace('<script type="module" src="assets/conta.js"></script>', '<script type="module" src="assets/admin.js"></script>')
    (DIST / "admin.html").write_text(out, encoding="utf-8")

def minha_conta():
    corpo = '''<section><div class="wrap prose" style="max-width:640px"><h1>Minha conta</h1>
<div id="conta" class="panel"><p class="note">Carregando…</p></div>
<p class="note">Seus dados ficam guardados com segurança no Google e só você vê. A loja usa o endereço só para a entrega.</p></div></section>'''
    head_ = head("Minha conta | Loja Dias Peças", "Sua conta na Loja Dias Peças.", "minha-conta.html")
    out = head_.replace("<title>", '<meta name="robots" content="noindex"><title>', 1) + topo() + "<main>" + corpo + "</main>" + rodape()
    (DIST / "minha-conta.html").write_text(out, encoding="utf-8")

def privacidade():
    corpo = f'''<section><div class="wrap prose" style="max-width:760px"><h1>Privacidade</h1>
<p>Esta página explica, conforme a LGPD (Lei 13.709/2018), quais dados a {e(CFG["nome_loja"])} (CNPJ {e(CFG.get("cnpj",""))}) guarda, para quê e por quanto tempo.</p>
<h2>Comprar sem conta</h2><p>Criar conta é opcional. Sem conta, a loja não guarda nada seu: o carrinho fica só no seu aparelho e o pedido vai direto para o nosso WhatsApp.</p>
<h2>O que guardamos se você criar conta</h2><ul>
<li>Do login Google: nome, e-mail e um código interno da conta. Nunca vemos sua senha.</li>
<li>O que você preencher: nome para entrega, WhatsApp, cidade e endereço.</li>
<li>Histórico dos seus pedidos: peças, quantidades, valores, data e código do pedido.</li>
<li>Se você preencher: modelo da moto, km por dia, intervalo de troca de óleo e datas das últimas trocas (óleo, relação, pastilha).</li></ul>
<p>Não guardamos CPF, dados de cartão nem dados bancários. O pagamento é por Pix, feito no app do seu banco.</p>
<h2>Para quê</h2><p>Só para entregar seus pedidos, preencher o endereço automaticamente, mostrar seu histórico, contar os pedidos do programa de fidelidade (6º pedido com frete grátis) e, <b>só se você marcar</b>, lembrar no WhatsApp quando chegar a hora da troca. Você pode desmarcar o lembrete quando quiser. Não vendemos nem compartilhamos seus dados para propaganda.</p>
{'<h2>Anúncios do Google</h2><p>O site usa a tag do Google Ads para saber se um anúncio trouxe uma venda. O Google pode gravar cookies no seu navegador para isso. Quando um pedido é enviado, mandamos ao Google só o valor e o código do pedido, sem nome, telefone ou endereço. Você pode bloquear esses cookies no navegador ou desligar anúncios personalizados em <a href="https://adssettings.google.com" target="_blank" rel="noopener">adssettings.google.com</a>.</p>' if CFG.get("google_ads_id") else ""}
{'<h2>Contador de visitas</h2><p>O site usa o Google Analytics para contar visitas: quantas pessoas entram, de onde vêm e quais páginas e peças abrem. O Google grava cookies no seu navegador para isso. Não mandamos nome, telefone nem endereço. Você pode bloquear esses cookies no navegador ou instalar o <a href="https://tools.google.com/dlpage/gaoptout?hl=pt-BR" target="_blank" rel="noopener">bloqueador do Google Analytics</a>.</p>' if CFG.get("ga4_id") else ""}
{'<h2>Proteção contra robôs</h2><p>Na conta e no login, o site usa o Google reCAPTCHA para barrar acessos automáticos. Ele analisa sinais do navegador e do uso da página, segundo a <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">política de privacidade do Google</a>.</p>' if CFG.get("appcheck_site_key") else ""}
<h2>Onde ficam</h2><p>No Google Firebase (servidor em São Paulo). Cada cliente só consegue ver os próprios dados.</p>
<h2>Por quanto tempo</h2><p>Enquanto sua conta existir. Você pode apagar tudo quando quiser em <a href="minha-conta.html">Minha conta</a> › Apagar minha conta. Isso apaga seus dados, seu histórico e o acesso de login na hora. Conversas no WhatsApp seguem as regras do WhatsApp.</p>
<h2>Seus direitos</h2><p>Você pode pedir acesso, correção ou exclusão dos seus dados a qualquer momento pelo WhatsApp {e(CFG["whatsapp_exibir"])}.</p>
<p class="note">Versão 1, novembro de 2026.</p></div></section>'''
    pagina("privacidade.html", "Privacidade | Loja Dias Peças", "Como a Loja Dias Peças trata seus dados (LGPD).", corpo)

def extras(ps):
    hoje = date.today().isoformat()
    urls = ["", "pedido.html" if VITRINE else "catalogo.html", "entrega.html"] + (["indique.html"] if IND and not VITRINE else []) + [f"entrega-{c['slug']}.html" for c in CFG["cidades"]] + [f"{sl}.html" for _, sl, _, _ in MOTOS_ATIVAS] + [p["url"] for p in ps]
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{URL}/{u}</loc><lastmod>{hoje}</lastmod></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nDisallow: /carrinho.html\nDisallow: /minha-conta.html\nDisallow: /admin.html\nDisallow: /_artifact_index.html\nSitemap: {URL}/sitemap.xml\n", encoding="utf-8")
    itens = "".join(f'''<item><g:id>{xesc(p["sku"])}</g:id><g:title>{xesc(p["nome"])}</g:title><g:description>{xesc(p["descricao"])}</g:description>
<g:link>{URL}/{p["url"]}</g:link>{f"<g:image_link>{URL}/{p['fotos'][0]}</g:image_link>" if p["fotos"] else ""}{"".join(f"<g:additional_image_link>{URL}/{f}</g:additional_image_link>" for f in p["fotos"][1:10])}<g:availability>{"in_stock" if p["estoque"] > 0 else "out_of_stock"}</g:availability>
<g:price>{p["preco"]:.2f} BRL</g:price><g:brand>{xesc(p["marca"])}</g:brand><g:mpn>{xesc(p["sku"])}</g:mpn><g:condition>new</g:condition>
<g:google_product_category>{"Vehicles &amp; Parts &gt; Vehicle Parts &amp; Accessories &gt; Motor Vehicle Parts"}</g:google_product_category></item>
''' for p in ps)
    (DIST / "feed-google.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel><title>{xesc(CFG["nome_loja"])}</title><link>{URL}/</link><description>Peças de moto e carro</description>\n{itens}</channel></rss>\n', encoding="utf-8")
    pub = [dict({k: p[k] for k in ("sku", "nome", "nome_real", "tipo", "categoria", "marca", "veiculos", "modelos", "preco", "url", "addon", "fams", "universal", "ind")},
                foto=p["fotos"][0] if p["fotos"] else "") for p in ps]
    cfg = {k: CFG[k] for k in ("whatsapp", "desconto_pix", "pix", "corte_mesmo_dia", "entrega_ate", "cidades")}
    cfg["ads"] = {"id": CFG.get("google_ads_id", ""), "label": CFG.get("google_ads_label", "")}
    cfg["ga"] = CFG.get("ga4_id", "")
    cfg["frete_gratis_acima"] = GRATIS
    cfg["na_entrega"] = NA_ENTREGA
    cfg["site"] = URL
    if IND:
        cfg["ind"] = {"desconto": IND["desconto"], "comissao": IND["comissao"], "dias": IND.get("dias", 30)}
    if FIREBASE:
        cfg["firebase"] = FIREBASE
        cfg["appcheck"] = CFG.get("appcheck_site_key", "")
    (DIST / "assets/loja.js").write_text("window.LOJA=" + json.dumps({"produtos": pub, "config": cfg}, ensure_ascii=False) + ";\n", encoding="utf-8")

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    if (RAIZ / "img").exists():
        shutil.copytree(RAIZ / "img", DIST / "img")
    for f in ("style.css", "app.js", "conta.js", "admin.js"):
        shutil.copy(RAIZ / "assets" / f, DIST / "assets" / f)
    global VITRINE
    ps = carregar()
    VITRINE = not ps
    MOTOS_ATIVAS[:] = [m for m in MOTOS if len([p for p in pecas_da_moto(ps, m[2]) if p["categoria"] != "kit"]) >= 3]
    home(ps); home(ps, artifact=True); entrega(); privacidade(); creditos()
    if VITRINE:
        pedido()
    else:
        catalogo(ps); carrinho()
        if IND:
            indique(ps)
        if FIREBASE:
            minha_conta(); admin()
    for p in ps: produto(p, ps)
    for c in CFG["cidades"]: cidade(c, ps)
    for n, sl, fams, marca in MOTOS_ATIVAS: pagina_moto(n, sl, fams, marca, ps)
    extras(ps)
    if CFG.get("dominio"):
        (DIST / "CNAME").write_text(CFG["dominio"] + "\n", encoding="utf-8")  # domínio próprio no GitHub Pages
    if SO_MOTO:
        for f in DIST.glob("*.html"):
            t = f.read_text(encoding="utf-8")
            for a, z in (("Peça de moto e carro", "Peça de moto"), ("Peças de moto e carro", "Peças de moto"), ("peças de moto e carro", "peças de moto"),
                         ("moto ou carro", "moto"), ("Moto ou carro", "Moto"), ("Moto e carro", "Moto"), ("moto e carro", "moto")):
                t = t.replace(a, z)
            f.write_text(t, encoding="utf-8")
    print(f"{len(ps)} produtos, {len(list(DIST.glob('*.html')))} páginas em {DIST}")

if __name__ == "__main__":
    main()
