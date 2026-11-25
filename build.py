#!/usr/bin/env python3
"""Gera o site estático da Loja Dias a partir de dados/produtos.csv e dados/config.json.

Uso: python3 build.py            -> gera dist/
Cada página é HTML pronto (rápido e legível pelo Google), com dados estruturados,
sitemap.xml, robots.txt e feed de produtos para o Google Merchant Center.
"""
import csv, json, re, shutil, unicodedata, html
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xesc

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

CATS = {"freio": "Freios", "transmissao": "Relação e correias", "filtro": "Filtros", "oleo": "Óleo",
        "ignicao": "Velas e ignição", "eletrica": "Bateria e elétrica", "cabo": "Cabos",
        "pneu": "Pneus e câmaras", "palheta": "Palhetas", "acessorio": "Retrovisor e manetes", "kit": "Kits prontos"}
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
 "kit": '<rect x="10" y="22" width="44" height="30" rx="3"/><path d="M24 22v-8h16v8M10 34h44"/>',
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
        if p["preco"] is None:
            continue
        p["slug"] = slug(p["nome"] + " " + p["sku"])
        p["url"] = f"peca-{p['slug']}.html"
        ps.append(p)
    return ps

# ---------- moldura comum ----------
def head(title, desc, path, extra_ld=None, artifact=False):
    canon = f"{URL}/{'' if path == 'index.html' else path}"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (extra_ld or []))
    meta = (f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<link rel="canonical" href="{canon}"><meta property="og:title" content="{e(title)}">'
            f'<meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website">'
            f'<meta property="og:locale" content="pt_BR"><meta name="theme-color" content="#1d232a">'
            f'{FONTS}<link rel="stylesheet" href="assets/style.css">{ld}')
    if artifact:
        return meta
    return f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{meta}</head><body>'

def topo():
    demo = '<div class="demo">Prévia: peças, preços e fretes são exemplos. O catálogo real virá das distribuidoras.</div>' if DEMO else ""
    faixa = f'<div class="demo">Frete grátis acima de {brl(GRATIS)} (Serra e Viana: acima de R$ 89,90)</div>' if GRATIS and FRETE_OK else ""
    return f'''{demo}{faixa}<header class="top"><div class="wrap">
<a class="logo" href="index.html">Loja <span>Dias</span> Peças</a>
<nav class="nav" aria-label="Principal"><a href="{lk("moto")}">Moto</a><a href="{lk("carro")}">Carro</a>
<a href="entrega.html">Entrega</a><a href="index.html#duvidas">Dúvidas</a>{'<a id="contalink" href="minha-conta.html">Entrar</a>' if FIREBASE and not VITRINE else ""}
{'<a class="cartlink" href="pedido.html">Fazer pedido</a>' if VITRINE else '<a class="cartlink" href="carrinho.html">Carrinho <b class="cartcount">0</b></a>'}</nav></div></header>'''

def lk(t):
    return f"pedido.html?tipo={t}" if VITRINE else f"catalogo.html?tipo={t}"

def rodape(artifact=False):
    cid = "".join(f'<a href="entrega-{c["slug"]}.html">Peças em {e(c["nome"])}</a>' for c in CFG["cidades"])
    wa = f'https://wa.me/{CFG["whatsapp"]}?text={xesc("Olá! Quero saber de uma peça.").replace(" ", "%20")}'
    tail = "" if artifact else "</body></html>"
    return f'''<footer><div class="wrap">
<div><b>Loja Dias Peças</b>Peças de moto e carro com entrega por motoboy na Grande Vitória, ES.<br>{e(CFG["horario"])}<br>WhatsApp {e(CFG["whatsapp_exibir"])}<br>CNPJ {e(CFG.get("cnpj",""))}</div>
<div><b>Entregamos em</b>{cid}</div>
<div><b>Comprar</b><a href="{lk("moto")}">Peças de moto</a><a href="{lk("carro")}">Peças de carro</a><a href="{"pedido.html" if VITRINE else "carrinho.html"}">{"Fazer pedido" if VITRINE else "Carrinho"}</a><a href="entrega.html">Prazos e fretes</a></div>
</div></footer>
<a class="wafloat" href="{wa}" target="_blank" rel="noopener">WhatsApp</a>
<script src="assets/loja.js"></script><script src="assets/app.js"></script>{'<script type="module" src="assets/conta.js"></script>' if FIREBASE and not VITRINE else ""}{tail}'''

def selo(p):
    if GRATIS and p["preco"] < 20:
        return f'<div class="stock">Compre junto e ganhe frete grátis</div>'
    return ""

def card(p):
    img = f'<img src="{e(p["imagem"])}" alt="{e(p["nome"])}" loading="lazy">' if p["imagem"] else icon(p["categoria"])
    fit = ", ".join(p["modelos"][:3]) + ("…" if len(p["modelos"]) > 3 else "")
    low = p["estoque"] <= 3
    return f'''<article class="card" data-sku="{e(p["sku"])}"><a class="ph" href="{p["url"]}" tabindex="-1"><span class="tag">{TIPOS[p["tipo"]]} · {CATS[p["categoria"]]}</span>{img}</a>
<div class="body"><h3><a href="{p["url"]}">{e(p["nome"])}</a></h3><div class="fit">Serve: {e(fit)}</div>
<div class="sku">{e(p["marca"])} · {e(p["sku"])}</div><div class="stock{' low' if low else ''}">{'Últimas %d unidades' % p['estoque'] if low else 'Em estoque'}</div>
{selo(p)}<div class="row"><div class="price">{brl(p["preco"])}<small>no Pix</small></div>
<button class="add" type="button" data-add="{e(p["sku"])}">Adicionar</button></div></div></article>'''

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
 ("Quais formas de pagamento?", "Por enquanto só Pix. Você recebe o Pix copia e cola com o valor exato do pedido."),
 ("E se a peça vier errada?", "Se não servir, o motoboy busca e troca. Peça sem uso e na embalagem tem troca garantida em até 7 dias."),
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

def home(ps, artifact=False):
    if VITRINE:
        return home_vitrine(artifact)
    destaque = [p for p in ps if p["tipo"] == "moto"][:4] + [p for p in ps if p["tipo"] == "carro"][:4]
    cats = lambda t: "".join(f'<a href="catalogo.html?tipo={t}&cat={c}">{n}</a>' for c, n in CATS.items() if any(p["tipo"] == t and p["categoria"] == c for p in ps))
    corpo = f'''<div class="hero"><div class="wrap">
<span class="eyebrow" style="color:var(--road-muted)">Grande Vitória · ES</span>
<h1>Peça de moto e carro na sua porta, hoje</h1>
<p>Entrega por motoboy no mesmo dia em Vitória, Vila Velha, Serra, Cariacica e Viana. Pagamento no Pix.</p>
<form class="search" action="catalogo.html" role="search"><input name="q" id="hq" placeholder="Ex.: pastilha CG 160, filtro de óleo Onix" aria-label="Buscar peça"><button class="btn" type="submit">Buscar</button></form>
<div class="chips"><span class="chip"><i></i>Pedido até {CFG["corte_mesmo_dia"]}, entrega até {CFG["entrega_ate"]}</span>{f'<span class="chip"><i></i>Frete grátis acima de {brl(GRATIS)}</span>' if GRATIS and FRETE_OK else ""}<span class="chip"><i></i>Pix copia e cola</span><span class="chip"><i></i>Troca garantida</span></div>
</div></div>
<section><div class="wrap split">
<a class="door" href="catalogo.html?tipo=moto"><span class="eyebrow">Peças de</span><b>Moto</b><span>Relação, freio, bateria, vela, cabos, pneus e óleo para CG, Biz, Pop, Bros, Factor, Fazer e mais.</span></a>
<a class="door" href="catalogo.html?tipo=carro"><span class="eyebrow">Peças de</span><b>Carro</b><span>Pastilha e disco, filtros, velas, palhetas, bateria e correia para Onix, HB20, Gol, Argo e mais.</span></a>
</div></section>
<section style="padding-top:0"><div class="wrap"><h2>Mais procuradas</h2><div class="grid">{"".join(card(p) for p in destaque)}</div>
<p><a class="btn dark" href="catalogo.html">Ver todas as peças</a></p></div></section>
<section><div class="wrap split"><div><h2>Moto</h2><div class="cats">{cats("moto")}</div></div><div><h2>Carro</h2><div class="cats">{cats("carro")}</div></div></div></section>
<section><div class="wrap"><h2>Como funciona</h2><ol class="steps">
<li><b>Escolha a peça</b><span>Busque pelo nome ou pelo modelo do seu veículo. Na dúvida, mande foto no WhatsApp.</span></li>
<li><b>Feche pelo WhatsApp</b><span>O pedido vai pronto com peças, frete e total. Pague no Pix copia e cola.</span></li>
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
<select id="tipo" aria-label="Moto ou carro"><option value="todos">Moto e carro</option><option value="moto">Moto</option><option value="carro">Carro</option></select>
<select id="veic" aria-label="Seu veículo"></select></div>
<div class="cats" id="cats" style="margin-bottom:16px">{botoes}</div>
<div class="grid" id="grid">{"".join(card(p) for p in ps)}<p class="empty" id="none" hidden>Nenhuma peça encontrada com esses filtros. Mande o modelo e a peça no WhatsApp que a gente procura.</p></div>
</div></section>'''
    pagina("catalogo.html", "Catálogo de peças de moto e carro | Loja Dias Peças",
           "Todas as peças de moto e carro da Loja Dias com preço, compatibilidade e entrega por motoboy na Grande Vitória.", corpo)

def produto(p):
    pix = p["preco"] * (1 - CFG["desconto_pix"])
    img = f'<img src="{e(p["imagem"])}" alt="{e(p["nome"])}">' if p["imagem"] else icon(p["categoria"])
    opts = "".join(f'<option value="{c["slug"]}">{e(c["nome"])}</option>' for c in CFG["cidades"])
    veic = "".join(f"<li>{e(v)}</li>" for v in p["veiculos"])
    wa = f'https://wa.me/{CFG["whatsapp"]}?text=' + re.sub(r" ", "%20", xesc(f"Olá! Essa peça serve no meu veículo? {p['nome']} ({p['sku']})"))
    corpo = f'''<div class="wrap"><nav class="crumbs" aria-label="Caminho"><a href="index.html">Início</a> › <a href="catalogo.html?tipo={p["tipo"]}">Peças de {TIPOS[p["tipo"]].lower()}</a> › <a href="catalogo.html?tipo={p["tipo"]}&cat={p["categoria"]}">{CATS[p["categoria"]]}</a></nav>
<div class="pdp"><div class="ph">{img}</div>
<div class="buy"><span class="eyebrow">{e(p["marca"])} · cód. {e(p["sku"])}</span><h1>{e(p["nome"])}</h1>
<div><div class="bigprice">{brl(p["preco"])}</div><div class="pixprice">no Pix</div></div>
<div class="stock{' low' if p['estoque']<=3 else ''}">{'Últimas %d unidades' % p['estoque'] if p['estoque']<=3 else 'Em estoque, pronta para entrega'}</div>
{selo(p)}{'<p class="note">Peça de complemento: vai junto com outra peça do pedido.</p>' if p["addon"] else ""}
<div style="display:flex;flex-wrap:wrap;gap:8px"><button class="btn" type="button" data-add="{e(p["sku"])}">Adicionar ao carrinho</button><a class="btn ghost" href="carrinho.html">Ir para o carrinho</a></div>
<div class="ship"><label class="lbl" for="shipcity">Calcular entrega</label><select id="shipcity">{opts}</select><div id="shipout" class="note"></div></div>
<a class="btn wa" href="{wa}" target="_blank" rel="noopener">Perguntar se serve no meu veículo</a>
</div></div>
<section class="prose"><h2>Detalhes</h2><p>{e(p["descricao"])}</p>
<dl class="facts"><dt>Serve em</dt><dd><ul>{veic}</ul></dd><dt>Marca</dt><dd>{e(p["marca"])}</dd><dt>Código</dt><dd>{e(p["sku"])}</dd><dt>Categoria</dt><dd>{CATS[p["categoria"]]} de {TIPOS[p["tipo"]].lower()}</dd></dl></section>
</div>'''
    ld = [{"@context": "https://schema.org", "@type": "Product", "name": p["nome"], "sku": p["sku"], "description": p["descricao"],
           "brand": {"@type": "Brand", "name": p["marca"]}, "category": f"{CATS[p['categoria']]} de {TIPOS[p['tipo']].lower()}",
           **({"image": p["imagem"]} if p["imagem"] else {}),
           "offers": {"@type": "Offer", "price": f"{p['preco']:.2f}", "priceCurrency": "BRL", "url": f"{URL}/{p['url']}",
                      "availability": "https://schema.org/InStock" if p["estoque"] > 0 else "https://schema.org/OutOfStock",
                      "itemCondition": "https://schema.org/NewCondition", "seller": {"@type": "Organization", "name": CFG["nome_loja"]}}},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Início", "item": URL + "/"},
              {"@type": "ListItem", "position": 2, "name": f"Peças de {TIPOS[p['tipo']].lower()}", "item": f"{URL}/catalogo.html?tipo={p['tipo']}"},
              {"@type": "ListItem", "position": 3, "name": p["nome"]}]}]
    pagina(p["url"], f"{p['nome']} | {brl(p['preco'])} com entrega na Grande Vitória",
           f"{p['nome']} {p['marca']} por {brl(p['preco'])} no Pix. Serve em {', '.join(p['modelos'][:3])}. Entrega por motoboy hoje em Vitória, Vila Velha, Serra e Cariacica.",
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
<a class="door" href="pedido.html?tipo=moto"><span class="eyebrow">Peças de</span><b>Moto</b><span>Relação, freio, bateria, vela, cabos, pneus, óleo, filtros e elétrica para CG, Biz, Pop, Bros, Factor, Fazer, NMax e mais.</span></a>
<a class="door" href="pedido.html?tipo=carro"><span class="eyebrow">Peças de</span><b>Carro</b><span>Pastilha e disco, filtros, velas, palhetas, bateria, lâmpadas e correia para Onix, HB20, Gol, Argo, Strada e mais.</span></a>
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
<label class="opt"><input type="radio" name="ptipo" id="ptCarro" value="carro"><span>Carro</span></label></fieldset>
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

def entrega():
    corpo = f'''<section><div class="wrap prose"><h1>Entrega e fretes</h1>
<p>Entregamos com motoboy em toda a Grande Vitória. Pedidos confirmados até {CFG["corte_mesmo_dia"]} chegam até as {CFG["entrega_ate"]} do mesmo dia. Pedidos depois desse horário chegam no dia seguinte.</p>
{tabela_frete()}
<h2 style="margin-top:28px">Peças grandes</h2><p>Peças que não cabem no baú da moto, como escapamento, para-choque e par de amortecedores, são combinadas pelo WhatsApp para retirada ou frete de carro.</p></div></section>'''
    pagina("entrega.html", "Entrega e fretes na Grande Vitória | Loja Dias Peças",
           "Fretes e prazos de entrega por motoboy em Vitória, Vila Velha, Serra, Cariacica e Viana.", corpo)

def carrinho():
    corpo = f'''<div class="wrap cartpage"><div class="panel"><h1 style="font-size:36px">Seu pedido</h1><div id="lines"></div><div class="tot" id="tot"></div></div>
<div class="panel">
<fieldset><legend class="lbl">Entrega</legend>
<label class="opt"><input type="radio" name="ship" id="shipN" value="normal" checked><span>Motoboy<small>Pedido até {CFG["corte_mesmo_dia"]}, entrega até {CFG["entrega_ate"]}{(". Frete grátis acima de " + brl(GRATIS)) if GRATIS else ""}</small></span><em id="feeN">—</em></label>
<label class="opt"><input type="radio" name="ship" id="shipR" value="retirada"><span>Retirar<small>Combinar pelo WhatsApp</small></span><em>R$ 0,00</em></label></fieldset>
<div class="field" id="citybox"><label class="lbl" for="city">Cidade</label><select id="city"></select></div>
<div class="field" id="addrbox"><label class="lbl" for="addr">Endereço e bairro</label><input id="addr" placeholder="Rua, número, bairro" autocomplete="street-address"></div>
<div class="field"><label class="lbl" for="name">Seu nome</label><input id="name" placeholder="Nome para a entrega" autocomplete="name"></div>
<div class="field"><span class="lbl">Pagamento</span><span>Pix. O código copia e cola aparece aqui com o valor exato.</span></div>
<p class="err" id="err" hidden></p>
<div id="pixbox" class="ship" hidden><span class="lbl">Pix copia e cola</span><textarea id="pixcode" readonly rows="4" style="width:100%;font-family:var(--mono);font-size:12px;border:1px solid var(--line);border-radius:9px;padding:8px;background:var(--bg);color:var(--ink);resize:none"></textarea><button class="btn dark" type="button" id="pixcopy">Copiar código Pix</button><span class="note">Pague no app do seu banco (Pix › Copia e cola) e depois envie o pedido com o comprovante.</span></div>
<a class="btn wa" id="send" href="#" target="_blank" rel="noopener" aria-disabled="true">Enviar pedido e comprovante no WhatsApp</a>
<p class="note">O pedido abre pronto no WhatsApp da loja. A gente confirma a peça e o horário de entrega na hora.</p></div></div>'''
    head_ = head("Carrinho | Loja Dias Peças", "Seu pedido na Loja Dias Peças.", "carrinho.html")
    out = head_.replace("<title>", '<meta name="robots" content="noindex"><title>', 1) + topo() + "<main>" + corpo + "</main>" + rodape()
    (DIST / "carrinho.html").write_text(out, encoding="utf-8")

def minha_conta():
    corpo = '''<section><div class="wrap prose" style="max-width:640px"><h1>Minha conta</h1>
<div id="conta" class="panel"><p class="note">Carregando…</p></div>
<p class="note">Seus dados ficam guardados com segurança no Google e só você vê. A loja usa o endereço só para a entrega.</p></div></section>'''
    head_ = head("Minha conta | Loja Dias Peças", "Sua conta na Loja Dias Peças.", "minha-conta.html")
    out = head_.replace("<title>", '<meta name="robots" content="noindex"><title>', 1) + topo() + "<main>" + corpo + "</main>" + rodape()
    (DIST / "minha-conta.html").write_text(out, encoding="utf-8")

def extras(ps):
    hoje = date.today().isoformat()
    urls = ["", "pedido.html" if VITRINE else "catalogo.html", "entrega.html"] + [f"entrega-{c['slug']}.html" for c in CFG["cidades"]] + [p["url"] for p in ps]
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{URL}/{u}</loc><lastmod>{hoje}</lastmod></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nDisallow: /carrinho.html\nDisallow: /minha-conta.html\nDisallow: /_artifact_index.html\nSitemap: {URL}/sitemap.xml\n", encoding="utf-8")
    itens = "".join(f'''<item><g:id>{xesc(p["sku"])}</g:id><g:title>{xesc(p["nome"])}</g:title><g:description>{xesc(p["descricao"])}</g:description>
<g:link>{URL}/{p["url"]}</g:link>{f"<g:image_link>{xesc(p['imagem'])}</g:image_link>" if p["imagem"] else ""}<g:availability>{"in_stock" if p["estoque"] > 0 else "out_of_stock"}</g:availability>
<g:price>{p["preco"]:.2f} BRL</g:price><g:brand>{xesc(p["marca"])}</g:brand><g:mpn>{xesc(p["sku"])}</g:mpn><g:condition>new</g:condition>
<g:google_product_category>{"Vehicles &amp; Parts &gt; Vehicle Parts &amp; Accessories &gt; Motor Vehicle Parts"}</g:google_product_category></item>
''' for p in ps)
    (DIST / "feed-google.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel><title>{xesc(CFG["nome_loja"])}</title><link>{URL}/</link><description>Peças de moto e carro</description>\n{itens}</channel></rss>\n', encoding="utf-8")
    pub = [{k: p[k] for k in ("sku", "nome", "tipo", "categoria", "marca", "veiculos", "modelos", "preco", "url", "addon")} for p in ps]
    cfg = {k: CFG[k] for k in ("whatsapp", "desconto_pix", "pix", "corte_mesmo_dia", "entrega_ate", "cidades")}
    cfg["frete_gratis_acima"] = GRATIS
    if FIREBASE:
        cfg["firebase"] = FIREBASE
    (DIST / "assets/loja.js").write_text("window.LOJA=" + json.dumps({"produtos": pub, "config": cfg}, ensure_ascii=False) + ";\n", encoding="utf-8")

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    for f in ("style.css", "app.js", "conta.js"):
        shutil.copy(RAIZ / "assets" / f, DIST / "assets" / f)
    global VITRINE
    ps = carregar()
    VITRINE = not ps
    home(ps); home(ps, artifact=True); entrega()
    if VITRINE:
        pedido()
    else:
        catalogo(ps); carrinho()
        if FIREBASE:
            minha_conta()
    for p in ps: produto(p)
    for c in CFG["cidades"]: cidade(c, ps)
    extras(ps)
    print(f"{len(ps)} produtos, {len(list(DIST.glob('*.html')))} páginas em {DIST}")

if __name__ == "__main__":
    main()
