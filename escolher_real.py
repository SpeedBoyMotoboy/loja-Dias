#!/usr/bin/env python3
"""Escolhe as peças do catálogo grande (1000) a partir do levantamento largo da Real (real_tudo.csv, feito no PC por pesquisa_tudo.py).

Uso: python3 escolher_real.py real_tudo.csv escolhidas.csv [alvo=1000] [estoque_min=10] [teto_por_tipo=40]
Depois: python3 importar_real.py escolhidas.csv --max 1300

Regras (25/11/2026, pedido do Luan "chegar a 1000 peças"): só peça com estoque e preço na Real, com moto conhecida na aplicação
(ou universal de moto), que a Real vende por unidade, de tipo que o site conhece e com margem que fecha. Nada de aplicação inventada.
Quem já está no site (dados/produtos.csv) continua enquanto tiver estoque.
Peça que a Real só vende em caixa ou pacote fica fora, mesmo se já estava no site (ok do Luan em 25/11 15h28)."""
import csv, collections, re, statistics, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from importar_real import serve_em_moto, modelos, categoria, FORA_SKU, norm
from nomes import familias
from build import preco_de_custo

src, dst = sys.argv[1], sys.argv[2]
ALVO = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
EMIN = int(sys.argv[4]) if len(sys.argv) > 4 else 10
POP = ["CG 160", "CG 150", "CG 125", "Biz 125", "Biz 110i", "Biz 100", "Pop 110i", "Pop 100", "Bros 160", "Bros 150", "Bros 125",
       "Fazer 150", "Factor 150", "Factor 125", "Crosser 150", "XRE 300", "XRE 190", "Fazer 250", "Lander 250", "Twister 250", "Twister 300",
       "CB 300", "PCX 150", "PCX 160", "NMax 160", "Tornado 250", "YBR 125", "XTZ 125", "Ténéré 250", "Elite 125", "Lead 110", "Neo 125", "Biz 125i", "CG 125I"]
MARCAS_BOAS = {"HONDA", "RIFFEL", "COBREQ", "FRAS-LE", "FRASLE", "NGK", "VEDAMOTORS", "WEGA", "LEVORIN", "PIRELLI", "MOBIL", "LUBRAX", "HELIAR", "MOURA",
               "MAGNETRON", "COFAP", "DIAFRAG", "CORTECO", "WGK", "GVS", "NAKATA", "TRW", "PHILIPS", "OSRAM", "HELLA", "INA", "FAG", "SKF", "DID", "TEC", "KMC"}
# a Real põe "motos" na aplicação, mas é produto de carro: aditivo de radiador, lâmpada H15/H3, silicone de painel, relé duplo de farol,
# controle de alarme avulso, buzina caracol. Dizer "serve na maioria das motos" seria enganar o cliente.
FORA_CARRO = {"MDAD001", "RL10010", "H15HELLA", "12336BVB1", "CAR80SILSPRLA", "DNI8135", "11490000PX32", "0986AH0706"}
atual = {r["sku"] for r in csv.DictReader(open(RAIZ / 'dados/produtos.csv', encoding='utf-8')) if r["categoria"] != "kit"}

rs = list(csv.DictReader(open(src, encoding='utf-8-sig')))
motivo = collections.Counter()
cand = []
for r in rs:
    cod = r["codigo"]
    nome = re.sub(r"(\S)- ", r"\1 - ", r["nome"])
    est = int(float(r["estoque"] or 0))
    custo = float(r["preco_custo"] or 0)
    if r["disponibilidade"] != "Disponível" or est < 1 or custo <= 0:
        motivo["sem estoque ou sem preço"] += 1; continue
    if est < EMIN:
        motivo[f"estoque abaixo de {EMIN}"] += 1; continue
    if "¿" in nome:
        pass
    elif len(nome.split(" - ")) < 3 and r["marca"]:
        nome = f"{nome} - {r['marca']}"
    if re.search(r"\bEMB\.? ?C/", nome, re.I):
        motivo["embalagem com várias unidades"] += 1; continue
    if cod in FORA_CARRO:
        motivo["produto de carro (a Real marca moto, mas quase nenhuma usa)"] += 1; continue
    if cod in FORA_SKU:
        motivo["custo fora do normal (lista)"] += 1; continue
    if not serve_em_moto(nome, r["aplicacao"]):
        motivo["sem moto na aplicação"] += 1; continue
    if (r["qtd_minima"] or "1") not in ("1", "1.0", ""):
        motivo["a Real só vende em pacote"] += 1; continue
    cat = categoria(nome)
    if not cat:
        motivo["tipo de peça que o site não conhece"] += 1; continue
    if preco_de_custo(custo, cat, nome) is None:
        motivo["margem não fecha"] += 1; continue
    fams = [f[0] for f in familias(modelos(r["aplicacao"]))]
    pos = min([POP.index(f) for f in fams if f in POP] or [99])
    univ = not fams
    # moto pouco comum (Falcon, Yes, Intruder...): entra por último, só se couber no alvo
    tipo = " ".join(norm(nome.split(" - ")[0]).split()[:2])
    cand.append(dict(r, nome_ok=nome, cat=cat, pos=pos, univ=univ, tipo=tipo, est=est, custo=custo))

# custo muito acima do normal para o mesmo tipo de peça: fica para conferir
por_tipo = collections.defaultdict(list)
for c in cand:
    por_tipo[c["tipo"]].append(c["custo"])
revisao, bons = [], []
for c in cand:
    xs = por_tipo[c["tipo"]]
    if len(xs) >= 6 and c["custo"] > 4 * statistics.median(xs) and c["codigo"] not in atual:
        revisao.append(c); motivo["custo 4x acima do normal do tipo"] += 1
    else:
        bons.append(c)

def nota(c):
    return (c["codigo"] in atual, -c["pos"] if c["pos"] < 99 else (-50 if c["univ"] else -60), c["marca"].upper().strip() in MARCAS_BOAS, min(c["est"], 200))

bons.sort(key=nota, reverse=True)
# equilíbrio: no máximo N peças por tipo (as que já estão no site entram sempre)
TETO_TIPO = int(sys.argv[5]) if len(sys.argv) > 5 else 40
conta = collections.Counter(); esc = []; sobra = []
for c in bons:
    if c["codigo"] in atual or conta[c["tipo"]] < (TETO_TIPO // 2 if c["tipo"].startswith("pistao") else TETO_TIPO):
        esc.append(c); conta[c["tipo"]] += 1
    else:
        sobra.append(c)
if len(esc) > ALVO:
    fixo = [c for c in esc if c["codigo"] in atual]
    resto = [c for c in esc if c["codigo"] not in atual][:max(0, ALVO - len(fixo))]
    sobra = [c for c in esc if c not in fixo and c not in resto] + sobra
    esc = fixo + resto
elif len(esc) < ALVO:
    esc += sobra[:ALVO - len(esc)]; sobra = sobra[ALVO - len(esc):]

CAMPOS = ["codigo", "codigo_real", "sku", "nome", "marca", "categoria", "aplicacao", "preco_custo", "estoque", "disponibilidade",
          "filial_estoque", "unidade", "qtd_minima", "url_imagem", "url_produto"]
with open(dst, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
    w.writeheader()
    for c in esc:
        w.writerow(dict(c, categoria="MOTO - GERAL"))
print("lidas", len(rs), "| candidatas", len(cand), "| boas", len(bons), "| escolhidas", len(esc), "| sobra", len(sobra))
print("das atuais do site, continuam:", sum(c["codigo"] in atual for c in esc), "de", len(atual))
print("faltaram das atuais:", sorted(atual - {c["codigo"] for c in esc})[:30])
for k, v in motivo.most_common(): print(f"  fora: {v:5d} {k}")
print("por categoria:", collections.Counter(c["cat"] for c in esc).most_common())
print("por tipo (top 40):", collections.Counter(c["tipo"] for c in esc).most_common(40))
print("estoque: >=20", sum(c["est"] >= 20 for c in esc), "| 10-19", sum(10 <= c["est"] < 20 for c in esc), "| 5-9", sum(c["est"] < 10 for c in esc))
print("revisao:", [(c["codigo"], c["nome"][:40], c["custo"]) for c in revisao][:15])
