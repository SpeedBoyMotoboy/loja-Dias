#!/usr/bin/env python3
"""Converte o CSV do robô da Real (real_catalogo_ultimo.csv) em dados/produtos.csv.

Uso: python3 importar_real.py caminho/real_catalogo_ultimo.csv [--max 400]
Preço de venda = regra de margem do build.py (coluna custo). Só entra peça com custo > 0 e em estoque.
"""
import csv, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from build import preco_de_custo  # mesma regra de margem do site
ESTOQUE_MIN = 3   # mínimo na Real para a peça entrar no site
LUCRO_MIN = 8.0   # lucro mínimo por peça, em R$ (frete é cobrado à parte)

def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

def col(row, *nomes):
    for n in nomes:
        for k, v in row.items():
            if k and norm(k).strip() == n:
                return (v or "").strip()
    return ""

def numero(s):
    s = re.sub(r"[^\d,.-]", "", s or "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

CATS = [  # (categoria, palavras)
    ("freio", ["pastilha", "lona", "sapata", "disco de freio", "freio"]),
    ("transmissao", ["relacao", "coroa", "pinhao", "corrente", "correia", "kit transmissao"]),
    ("filtro", ["filtro"]),
    ("oleo", ["oleo", "lubrificante"]),
    ("ignicao", ["vela", "bobina", "cdi"]),
    ("eletrica", ["bateria", "lampada", "farol", "pisca", "regulador", "estator", "chicote", "rele"]),
    ("cabo", ["cabo "]),
    ("pneu", ["pneu", "camara"]),
    ("palheta", ["palheta"]),
]
CARRO = ["onix", "hb20", "gol", "palio", "uno", "argo", "strada", "kwid", "corolla", "celta", "prisma", "fiesta", "ka ", "sandero", "civic", "fox", "polo", "saveiro"]

def categoria(txt):
    t = norm(txt) + " "
    for c, ws in CATS:
        if any(w in t for w in ws):
            return c
    return ""

def main():
    src = Path(sys.argv[1])
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
    saida, vistos = [], set()
    for r in csv.DictReader(open(src, encoding="utf-8-sig")):
        sku = col(r, "codigo", "sku", "cod")
        nome = col(r, "nome", "descricao", "produto")
        custo = numero(col(r, "preco_custo", "custo", "preco"))
        est = col(r, "estoque", "disponibilidade")
        if not sku or not nome or custo <= 0 or sku in vistos:
            continue
        if est and norm(est) in ("0", "indisponivel", "sem estoque", "esgotado", "false", "nao"):
            continue
        if est.isdigit() and int(est) < ESTOQUE_MIN:  # estoque baixo na Real: risco de faltar
            continue
        cat = categoria(nome + " " + col(r, "categoria"))
        if not cat:
            continue
        if preco_de_custo(custo, cat) - custo < LUCRO_MIN:  # lucro pequeno demais por peça
            continue
        veic = col(r, "aplicacao", "veiculos", "aplicacao/veiculos")
        tipo = "carro" if any(w in norm(nome + " " + veic) + " " for w in CARRO) or "carro" in norm(col(r, "categoria")) else "moto"
        vistos.add(sku)
        saida.append({"sku": sku, "nome": nome[:90], "tipo": tipo, "categoria": cat, "marca": col(r, "marca") or "",
                      "veiculos": ";".join(v.strip() for v in re.split(r"[;/|]", veic) if v.strip())[:300] or "Consultar aplicação no WhatsApp",
                      "preco": "", "custo": f"{custo:.2f}", "estoque": 10 if not est or not est.isdigit() else est,
                      "imagem": col(r, "url_imagem", "imagem"), "descricao": f"{nome}. Entrega por motoboy no mesmo dia na Grande Vitória."})
        if len(saida) >= mx:
            break
    campos = ["sku", "nome", "tipo", "categoria", "marca", "veiculos", "preco", "custo", "estoque", "imagem", "descricao"]
    with open(RAIZ / "dados/produtos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(saida)
    print(f"{len(saida)} peças importadas para dados/produtos.csv")

if __name__ == "__main__":
    main()
