#!/usr/bin/env python3
"""Peças de carro da Laguna Autopeças (pedido do Luan 26/11/2026; Mesa Pauta 6 e 6B).

Uso: python3 importar_laguna.py laguna_carros.tsv [mais.tsv ...]
Entrada: TSV do robô do PC (robo-laguna), com as colunas codigo, nome, marca, categoria, preco_custo, aplicacao,
imagem_url, peso_kg e, quando houver, aviao/prazo. Só entram peças com estoque na filial de Vitória (o robô já filtra).
Saída: troca as linhas tipo=carro de dados/produtos.csv. As de moto e os kits ficam como estão.
O preço sai do custo pelo build.py (MARGEM_CARRO). Peça com avião (encomenda/importada) entra com encomenda=sim.
Fica FORA (Pauta 6B): para-choque, capô, portas, tampa do porta-malas, para-lama, grade grande, motor completo,
para-brisa e vidros.
"""
import csv, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from importar_real import CAMPOS

FORA = re.compile(r"para.?choque|\bcapo\b|para.?brisa|\bvidro|\bporta\b|portas\b|para.?lama|\bgrade\b|tampa (do )?porta.?malas|"
                  r"motor (completo|parcial)|\balma\b|parabrisa|retrovisor externo completo")
FIORINO = re.compile(r"escapamento|silencioso|feixe de mola|\bcambio\b|caixa de cambio|tanque de combustivel|short block|\beixo\b|agregado")
CATS = [  # (palavras no nome ou na categoria da Laguna, categoria do site)
    (r"palheta", "palheta"),
    (r"filtro", "filtro"),
    (r"pastilha|disco de freio|disco freio|sapata|lona|cavalete|cilindro (de )?(roda|mestre)|flexivel|tambor de freio|pinca|freio", "freio"),
    (r"vela|bobina|cabo (de )?(vela|ignicao)|ignicao", "ignicao"),
    (r"correia|tensor|tensionador|polia|corrente de comando|distribuicao", "transmissao"),
    (r"oleo|fluido|aditivo|graxa|lubrificante", "oleo"),
    (r"amortecedor|bandeja|pivo|terminal|bieleta|barra (axial|estabilizadora)|bucha|coxim|batente|mola|suspensao|homocinetica|coifa", "suspensao"),
    (r"rolamento|cubo", "roda"),
    (r"lampada|bateria|alternador|motor de partida|sensor|rele|eletrica|chicote|interruptor|sonda", "eletrica"),
    (r"junta|bomba|pistao|anel|bronzina|valvula|comando|embreagem|radiador|cabecote|biela|retentor|motor|tbi|corpo de borboleta|bico injetor|injecao|arrefecimento|reservatorio|mangueira|valvula termostatica", "motor"),
    (r"cabo", "cabo"),
]
ABREV = [(r"\bdiant\b\.?", "dianteira"), (r"\btras\b\.?", "traseira"), (r"\bdiantº?\b", "dianteira"), (r"\bign\b\.?", "ignição"),
         (r"\bignicao\b", "ignição"), (r"\boleo\b", "óleo"), (r"\blampada\b", "lâmpada"), (r"\bsuspensao\b", "suspensão"),
         (r"\bdirecao\b", "direção"), (r"\bcambio\b", "câmbio"), (r"\bcombustivel\b", "combustível"), (r"\bbomba d agua\b", "bomba d'água"),
         (r"\bagua\b", "água"), (r"\bvalvula\b", "válvula"), (r"\bpistao\b", "pistão"), (r"\bcabecote\b", "cabeçote"),
         (r"\bcorreia dentada\b", "correia dentada"), (r"\bjg\b\.?", "jogo"), (r"\besq\b\.?", "esquerdo"), (r"\bdir\b\.?", "direito"),
         (r"\bc/\s*", "com "), (r"\bs/\s*", "sem "), (r"\bfluido freio\b", "fluido de freio"), (r"\bpastilha freio\b", "pastilha de freio"),
         (r"\bdisco freio\b", "disco de freio"), (r"\bfiltro ar\b", "filtro de ar"), (r"\bfiltro oleo\b", "filtro de óleo"),
         (r"\bfiltro óleo\b", "filtro de óleo"), (r"\bfiltro combustivel\b", "filtro de combustível"), (r"\bfiltro combustível\b", "filtro de combustível"),
         (r"\bvela ignição\b", "vela de ignição"), (r"\bcabo ignição\b", "cabo de vela"), (r"\bsapata freio\b", "sapata de freio")]


def _n(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def col(r, *nomes):
    for n in nomes:
        for k in r:
            if _n(k).strip() == n:
                return (r[k] or "").strip()
    return ""


def numero(s):
    s = (s or "").strip().replace("R$", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def nome_peca(nome):
    t = " " + re.sub(r"\s+", " ", (nome or "").strip()).lower() + " "
    t = unicodedata.normalize("NFC", t)
    for de, para in ABREV:
        t = re.sub(de, para, t)
    t = re.sub(r"\b\w*\d\w*\b", lambda m: m.group(0).upper(), t.strip())  # 12V, H4, 5W30
    return t[:1].upper() + t[1:]


def carros(apl, n=2):
    """'Onix 2013-2019; Prisma 2013-2019; HB20 2012-2022' -> 'Onix 2013-2019, Prisma 2013-2019 e outros'"""
    itens = [x.strip() for x in re.split(r"[;|]", apl or "") if x.strip()]
    if not itens:
        return ""
    txt = ", ".join(itens[:n])
    return txt + (" e outros" if len(itens) > n else "")


def categoria(nome, cat_laguna):
    t = _n(nome + " " + cat_laguna)
    return next((c for pat, c in CATS if re.search(pat, t)), "acessorio")


def ler_tsv(arqs):
    for a in arqs:
        with open(a, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader((ln for ln in f if not ln.startswith(("INICIO_PARTE", "FIM_PARTE"))), delimiter="\t"):
                yield r


def main():
    arqs = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    base = list(csv.DictReader(open(RAIZ / "dados/produtos.csv", encoding="utf-8")))
    moto = [r for r in base if r.get("tipo") != "carro"]
    skus_moto = {r["sku"] for r in moto}
    novos, fora, sem_preco, vistos = [], [], 0, set()
    for r in ler_tsv(arqs):
        cod = col(r, "codigo")
        nome = col(r, "nome")
        if not cod or cod in vistos:
            continue
        vistos.add(cod)
        t = _n(nome + " " + col(r, "categoria"))
        if FORA.search(t):
            fora.append(cod); continue
        custo = numero(col(r, "preco_custo"))
        if custo <= 0:
            sem_preco += 1; continue
        apl = col(r, "aplicacao")
        marca = col(r, "marca").strip()
        marca = marca if len(marca) <= 3 else marca.title() if marca.isupper() else marca
        peca = nome_peca(nome)
        cs = carros(apl)
        sku = cod if cod not in skus_moto else f"LG-{cod}"
        aviao = _n(col(r, "aviao")) in ("sim", "1", "true", "s", "x")
        peso = col(r, "peso_kg").replace(",", ".")
        novos.append(dict(
            sku=sku, nome=f"{peca} {cs} {marca}".replace("  ", " ").strip(), tipo="carro", categoria=categoria(nome, col(r, "categoria")),
            marca=marca, veiculos=";".join(x.strip() for x in re.split(r"[;|]", apl) if x.strip()), preco="", custo=f"{custo:.2f}",
            ml_medio="", estoque="10", imagem=col(r, "imagem_url"), descricao="", partes="", peso_kg=peso,
            fiorino="sim" if FIORINO.search(t) else "", encomenda="sim" if aviao else "", fornecedor="Laguna"))
    with open(RAIZ / "dados/produtos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        w.writerows(moto + novos)
    from collections import Counter
    print(f"Carro: {len(novos)} peças (encomenda {sum(1 for x in novos if x['encomenda'])}, Fiorino {sum(1 for x in novos if x['fiorino'])}). "
          f"Fora pela regra 6B: {len(fora)}. Sem preço: {sem_preco}.")
    print("Por categoria:", dict(Counter(x["categoria"] for x in novos).most_common()))


if __name__ == "__main__":
    main()
