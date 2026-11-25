#!/usr/bin/env python3
"""Converte o CSV do robô da Real (real_catalogo_ultimo.csv) em dados/produtos.csv.

Uso: python3 importar_real.py caminho/real_catalogo_ultimo.csv [--max 100]
Preço de venda = regra de margem do build.py (coluna custo). Só entra peça com custo > 0 e em estoque.
"""
import csv, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from build import preco_de_custo, eh_isca  # mesma regra de margem do site
ESTOQUE_MIN = 3   # mínimo na Real para a peça entrar no site
# Kits (Mesa 24/11): só entram se todas as peças estão no site. Preço = soma das peças com 5% off.
KITS = [
    ("KIT-FREIO-CG", "Kit Freio CG 150/160: pastilha dianteira Cobreq + fluido de freio DOT3 TRW", "freio", ["N949MO", "RCLF00021"],
     "HONDA CG 160 FAN 2015-2026 CG 150 FAN 2010-2015 CG 150 TITAN 2009-2015"),
    ("KIT-IGNICAO-CG", "Kit Ignição e Ar CG 150/160: vela NGK + filtro de ar Wega + lâmpada H4", "ignicao", ["CPR8EA9", "JFA0M72", "90208030"],
     "HONDA CG 160 FAN 2019-2026 CG 160 TITAN 2019-2026 CG 150 FAN 2014-2026"),
    ("KIT-MANETES-BROS", "Kit Manetes reserva Bros 150 / XRE 300: manete de freio + manete de embreagem", "acessorio", ["001497", "001499"],
     "HONDA NXR 150 BROS 2006-2015 XRE 300 2009-2026"),
]

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
    ("acessorio", ["retrovisor", "manete", "pedaleira"]),
]
CARRO = ["onix", "hb20", "gol", "palio", "uno", "argo", "strada", "kwid", "corolla", "celta", "prisma", "fiesta", "ka ", "sandero", "civic", "fox", "polo", "saveiro"]

MARCAS = r"^(HONDA|YAMAHA|SUZUKI|DAFRA|KASINSKI|SHINERAY|FIAT|VOLKSWAGEN|CHEVROLET|FORD|RENAULT|HYUNDAI|TOYOTA|NISSAN|PEUGEOT|CITROEN|JEEP)\s+"

# imagem fica vazia: sem hotlink do fornecedor (decisão da Mesa); foto baixada vira img/<sku>.webp
def modelos(apl):
    """'HONDA CG 150 TITAN 2004-2026 CG 150 FAN 2009-2026' -> ['CG 150 TITAN 2004-2026', 'CG 150 FAN 2009-2026']"""
    if "UNIVERSAL" in apl.upper():
        return ["Universal (serve na maioria das motos)"]
    ms = re.findall(r"(.+?\s(?:19|20)\d{2}-(?:(?:19|20)\d{2})?)(?=\s|$)", apl.strip())
    out = []
    for m in ms or [apl]:
        m = m.strip()
        while re.match(MARCAS, m):
            m = re.sub(MARCAS, "", m)
        if m and m not in out:
            out.append(m)
    return out

def categoria(txt):
    t = norm(txt) + " "
    for c, ws in CATS:
        if any(w in t for w in ws):
            return c
    return ""

def main():
    src = Path(sys.argv[1])
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 100
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
        pv = preco_de_custo(custo, cat, nome)
        if pv is None:
            continue
        veic = col(r, "aplicacao", "veiculos", "aplicacao/veiculos")
        cr = norm(col(r, "categoria"))
        tipo = "carro" if cr.startswith("carro") else "moto" if cr.startswith("moto") else "carro" if any(w in norm(nome + " " + veic) + " " for w in CARRO) or "carro" in norm(col(r, "categoria")) else "moto"
        vistos.add(sku)
        saida.append({"sku": sku, "nome": nome[:90], "tipo": tipo, "categoria": cat, "marca": col(r, "marca") or "",
                      "veiculos": ";".join(modelos(veic))[:400] or "Consultar aplicação no WhatsApp",
                      "preco": "", "custo": f"{custo:.2f}", "estoque": 10 if not est or not est.isdigit() else est,
                      "imagem": "", "descricao": f"{nome}. Entrega por motoboy no mesmo dia na Grande Vitória."})
        if len(saida) >= mx:
            break
    from build import _noventa
    por = {s["sku"]: s for s in saida}
    kits = []
    for ksku, knome, kcat, partes, apl in KITS:
        if not all(p in por for p in partes):
            print("kit fora (peça ausente):", ksku)
            continue
        custo = sum(float(por[p]["custo"]) for p in partes)
        soma = sum(preco_de_custo(float(por[p]["custo"]), por[p]["categoria"], por[p]["nome"]) for p in partes)
        preco = _noventa(soma * 0.95 - 1)
        if preco - custo < 8:
            preco = _noventa(custo + 8)
        kits.append({"sku": ksku, "nome": knome, "tipo": "moto", "categoria": "kit", "marca": "Loja Dias",
                     "veiculos": ";".join(modelos(apl)), "preco": f"{preco:.2f}", "custo": f"{custo:.2f}",
                     "estoque": min(int(por[p]["estoque"]) for p in partes), "imagem": "", "partes": ";".join(partes),
                     "descricao": knome + f". Sai mais barato que comprar separado (R$ {soma:.2f}). Entrega por motoboy no mesmo dia na Grande Vitória."})
    saida = kits + saida
    campos = ["sku", "nome", "tipo", "categoria", "marca", "veiculos", "preco", "custo", "estoque", "imagem", "descricao", "partes"]
    with open(RAIZ / "dados/produtos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(saida)
    print(f"{len(saida)} peças importadas para dados/produtos.csv")

if __name__ == "__main__":
    main()
