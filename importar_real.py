#!/usr/bin/env python3
"""Converte o CSV do robô da Real (real_catalogo_ultimo.csv) em dados/produtos.csv.

Uso: python3 importar_real.py caminho/real_catalogo_ultimo.csv [--max 100]
     python3 importar_real.py --so-kits   (refaz só os kits em cima do produtos.csv atual)
Preço de venda = regra de margem do build.py (coluna custo). Só entra peça com custo > 0 e em estoque.
"""
import csv, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from build import preco_de_custo, eh_isca  # mesma regra de margem do site
import json
SO_MOTO = json.load(open(RAIZ / "dados/config.json", encoding="utf-8")).get("so_moto", False)
ESTOQUE_MIN = 3   # mínimo na Real para a peça entrar no site
# Kits (Mesa 24/11): só entram se todas as peças estão no site. Preço = soma das peças com 5% off.
# 25/11: kits no formato das lojas grandes (kit relação + freio, kit revisão, par dianteira + traseira).
# A lista de motos do kit NÃO é escrita à mão: é o que todas as peças do kit têm em comum (modelo e ano).
# 4º campo (opcional): mostra só os modelos que começam assim, para o kit não aparecer em moto que o nome dele não cita.
KITS = [
    ("KIT-FREIO-CG", "Kit Freio CG 150/160: pastilha dianteira Cobreq + fluido de freio DOT3 TRW", ["N949MO", "RCLF00021"], ("CG ",)),
    ("KIT-IGNICAO-CG", "Kit Ignição e Ar CG 150/160: vela NGK + filtro de ar Wega + lâmpada H4", ["CPR8EA9", "JFA0M72", "90208030"]),
    ("KIT-MANETES-BROS", "Kit Manetes reserva Bros 150 / XRE 300: manete de freio + manete de embreagem", ["001497", "001499"], ("NXR 150 BROS", "XRE 300")),
    ("KIT-MANUTENCAO-CG160", "Kit Manutenção CG 160 Fan/Titan 2019 em diante: kit relação + pastilha dianteira + vela NGK + filtro de ar", ["0009KR", "DFP20906", "CPR8EA9", "JFA0M72"]),
    ("KIT-RELACAO-FREIO-CG160", "Kit Relação + Freio CG 160 Fan/Titan 2019 em diante: kit relação Cobreq + pastilha dianteira Diafrag", ["0009KR", "DFP20906"]),
    ("KIT-RELACAO-FREIO-CG150", "Kit Relação + Freio CG 150 Titan/Fan 2010 a 2015: kit relação Cobreq + pastilha dianteira Cobreq", ["0008KR", "N949MO"]),
    ("KIT-MANUTENCAO-BROS160", "Kit Manutenção Bros 160: kit relação + pastilha dianteira + filtro de ar", ["0003KR", "N917MO", "FAP1002"]),
    ("KIT-RELACAO-FREIO-BROS160", "Kit Relação + Freio Bros 160 / XRE 190: kit relação Cobreq + pastilha dianteira Cobreq", ["0003KR", "N917MO"]),
    ("KIT-RELACAO-FREIO-BROS150", "Kit Relação + Freio Bros 150: kit relação Cobreq + pastilha dianteira Cobreq", ["0004KR", "N917MO"]),
    ("KIT-FREIO-BROS", "Kit Freio Bros / XRE: pastilha dianteira Cobreq + fluido de freio DOT3 TRW", ["N917MO", "RCLF00021"], ("NXR ", "XRE ")),
    ("KIT-REVISAO-FAZER150", "Kit Revisão Fazer 150 / Crosser 150: vela NGK + filtro de ar Wega + filtro de óleo Wega", ["MR8D9", "JFA0M89", "JFO0019"]),
    ("KIT-PASTILHAS-LANDER", "Kit Pastilhas Lander 250 / Ténéré 250: pastilha dianteira Cobreq + pastilha traseira Diafrag", ["N1834MO", "DFP20839"]),
    ("KIT-RELACAO-VELA-BIZ", "Kit Relação + Vela Biz 110i: kit relação Cobreq + vela NGK", ["0002KR", "CPR6EA9S"]),
    ("KIT-PEDALEIRAS-CG160", "Kit Pedaleiras traseiras CG 160: direita + esquerda", ["MMPD012", "MMPD011"], ("CG ",)),
]

def motos_em_comum(listas):
    """Modelos (com faixa de ano) que aparecem em TODAS as peças. Peça universal não restringe. Fim em branco = até hoje."""
    mapas = []
    for veic in listas:
        if veic.lower().startswith("universal"):
            continue
        d = {}
        for v in veic.split(";"):
            m = re.match(r"^(.*?)\s+(\d{4})-(\d{4})?$", v.strip())
            if m:
                d[m.group(1)] = (int(m.group(2)), int(m.group(3) or 2026))
        mapas.append(d)
    if not mapas:
        return []
    out = []
    for modelo in mapas[0]:
        if all(modelo in d for d in mapas):
            ini, fim = max(d[modelo][0] for d in mapas), min(d[modelo][1] for d in mapas)
            if ini <= fim:
                out.append(f"{modelo} {ini}-{fim}")
    return out

def montar_kits(por):
    """por = {sku: linha do produtos.csv}. Devolve as linhas dos kits que dá para montar."""
    from build import _noventa
    kits = []
    for ksku, knome, partes, *so in KITS:
        if not all(p in por for p in partes):
            print("kit fora (peça ausente):", ksku)
            continue
        veic = motos_em_comum([por[p]["veiculos"] for p in partes])
        if so:
            veic = [v for v in veic if v.startswith(so[0])]
        if not veic:
            print("kit fora (peças sem moto em comum):", ksku)
            continue
        custo = sum(float(por[p]["custo"]) for p in partes)
        soma = sum(preco_de_custo(float(por[p]["custo"]), por[p]["categoria"], por[p]["nome"], float(por[p]["ml_medio"]) if (por[p].get("ml_medio") or "").strip() else None) for p in partes)
        preco = _noventa(soma * 0.95 - 1)
        if preco - custo < 8:
            preco = _noventa(custo + 8)
        if preco >= soma:  # kit que não sai mais barato que separado não é kit
            print("kit fora (não fica mais barato):", ksku)
            continue
        kits.append({"sku": ksku, "nome": knome, "tipo": "moto", "categoria": "kit", "marca": "Loja Dias",
                     "veiculos": ";".join(veic), "preco": f"{preco:.2f}", "custo": f"{custo:.2f}",
                     "estoque": min(int(por[p]["estoque"]) for p in partes), "imagem": "", "partes": ";".join(partes),
                     "descricao": knome + f". Sai mais barato que comprar separado (R$ {soma:.2f}). Entrega por motoboy no mesmo dia na Grande Vitória."})
    return kits

CAMPOS = ["sku", "nome", "tipo", "categoria", "marca", "veiculos", "preco", "custo", "ml_medio", "estoque", "imagem", "descricao", "partes"]

def so_kits():
    """Refaz só os kits em cima do dados/produtos.csv que já existe (sem precisar do CSV do robô)."""
    arq = RAIZ / "dados/produtos.csv"
    linhas = [r for r in csv.DictReader(open(arq, encoding="utf-8")) if r["categoria"] != "kit"]
    saida = montar_kits({r["sku"]: r for r in linhas}) + linhas
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        w.writerows(saida)
    print(f"{len(saida) - len(linhas)} kits, {len(linhas)} peças em dados/produtos.csv")

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
    ("filtro", ["filtro", "tela de oleo", "tela oleo", "tela filtro"]),
    ("oleo", ["oleo", "lubrificante"]),
    ("ignicao", ["vela", "bobina", "cdi"]),
    ("eletrica", ["bateria", "lampada", "farol", "pisca", "regulador", "estator", "chicote", "rele"]),
    ("cabo", ["cabo "]),
    ("pneu", ["pneu", "camara"]),
    ("palheta", ["palheta"]),
    ("acessorio", ["retrovisor", "manete", "pedaleira"]),
    ("suspensao", ["retentor", "bengala", "amortecedor"]),
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

def carregar_tetos():
    """dados/teto.csv: preço médio da concorrência (Mesa). Coluna marca = média daquela marca/linha; vazia = média geral."""
    f = RAIZ / "dados/teto.csv"
    if not f.exists():
        return []
    return [(t["palavras"].split("|"), [m for m in t["modelos"].split("|") if m], norm(t.get("marca") or "").strip(), float(t["medio"]))
            for t in csv.DictReader(open(f, encoding="utf-8"))]

# Mesa 25/11/2026 (Pauta 3): o teto compara com a MESMA marca/linha, e vale média + R$ 10 (build.TETO_FOLGA).
# A média geral não serve para linha própria (iridium, titanium, com retentor, cerâmica): era ela que derrubava NGK e Riffel.
LINHA_PROPRIA = re.compile(r"iridium|titanium|c/ ?ret\b|com retentor|o.?ring|ceramica|premium|sinteriz")

def teto_de(nome, apl, tetos, marca=""):
    """Devolve a média de referência (sem os R$ 10) ou None. Linha do teto.csv com marca ganha da média geral."""
    n, a, m = norm(nome), norm(nome + " " + apl), norm(marca)
    geral = None
    for pals, mods, mk, medio in tetos:
        # a palavra tem de abrir o nome ("vela" não pega "cachimbo vela"); medida/viscosidade (tem número) vale em qualquer lugar
        if any(n.startswith(p) or (re.search(r"\d", p) and p in n) for p in pals) and (not mods or any(x in a for x in mods)):
            if mk:
                if any(x and (x in m or x in n) for x in mk.split("|")):
                    return medio
            elif geral is None:
                geral = medio
    return None if LINHA_PROPRIA.search(n) else geral

# Mesa 25/11/2026: estoque mínimo na Real para a peça entrar (ou voltar) no site.
# Curva A (relação, pastilha, lona, bateria, câmara) gira rápido e a Real repõe: 5. O resto: 10.
CURVA_A = re.compile(r"(kit transmissao|kit relacao|pastilha|lona|sapata|patim|bateria|camara)\b")
def estoque_min(nome):
    n = norm(nome)
    return 5 if CURVA_A.match(n) and "primaria" not in n else 10  # kit de transmissão primária (CVT de scooter) não é relação

FORA_NOME = ["bateria 3v", "cr2032"]  # pilha de controle de alarme, não é peça de moto
# custo na Real muito acima do normal para o tipo de peça (parece caixa fechada ou erro de cadastro): não entra até alguém conferir
FORA_SKU = {"N1619MO", "12066CP"}

def serve_em_moto(nome, apl):
    """Fica: peça com pelo menos uma moto na aplicação, ou universal que serve em moto (câmara, bateria, lâmpada, fluido)."""
    from nomes import familias
    n, a = norm(nome), norm(apl)
    if any(w in n for w in FORA_NOME):
        return False
    if familias(modelos(apl)):
        return True
    if "universal" in a:
        return "moto" in a or not re.search(r"automov|caminh|utilit|onibus|agricol", a)
    return False

# 25/11 (catálogo de 1000): tipos novos, decididos pelo COMEÇO da descrição. Vale antes da lista CATS, que olha a frase toda.
CATS_INICIO = [
    ("acessorio", r"mola (do )?cavalete|kit cavalete"),
    ("eletrica", r"suporte escova|suporte e escovas"),
    ("motor", r"corrente (do |de )?comando|kit tensor|tensor|guia corrente|junta|kit [ab] junta|kit vedacao|carburador|pistao|anel|aneis|kit cilindro|"
              r"cilindro motor|valvula|comando|balancim|bomba (de )?oleo|disco (de )?embreagem|kit (de )?embreagem|plato|virabrequim|biela|"
              r"rolamento (do )?(virabrequim|comando)|diafragma|boia|agulha|gicle|reparo (do )?carburador|bico injetor|bomba (de )?combustivel|torneira|"
              r"engrenagem|eixo (do )?(comando|balancim|cambio|partida)|eixo (secundario|primario)|pedal (de )?(partida|cambio)|mola (da )?embreagem|"
              r"capa (da )?corrente|kit motor|embreagem|coletor (de )?admissao|arvore comando|tensionador|guia valvula|separador embreagem|"
              r"cubo embreagem|kit comando|ressalto comando|kit reparo mesa|bujao"),
    ("oleo", r"graxa|aditivo|silicone spray|vaselina spray|desengripante"),
    ("roda", r"rolamento|cubo|flange|cinta|eixo|raio|aro |espacador"),
    ("suspensao", r"amortecedor|tubo interno|bengala|caixa (de )?direcao|guarda po|mola|bucha (da )?balanca|kit bucha|bucha garfo|bucha (do )?quadro"),
    ("freio", r"disco (de )?freio|cilindro mestre|pinca|flexivel|reparo (do |da )?(freio|cilindro mestre|pinca)|burrinho|pedal (de )?freio|vareta|"
              r"interruptor (de )?freio"),
    ("ignicao", r"cdi|bobina|cachimbo|terminal cachimbo"),
    ("eletrica", r"chave|interruptor|rele|regulador|pisca|lente|lanterna|farol|soquete|estator|buzina|sensor|chicote|conector|fusivel|"
                 r"motor (de )?partida|escova|painel|velocimetro|bloco optico|punho|sonda|reparo escova|suporte e escovas|fiacao|carcaca|"
                 r"volante magnetico|controle remoto"),
    ("transmissao", r"coroa|pinhao|corrente|coxim (da )?coroa|bucha (da )?coroa|correia|rolete|variador"),
    ("acessorio", r"manopla|guidao|carenagem|paralama|para-lama|bagageiro|protetor|capa|bau|cavalete|descanso|pedal|espelho|banco|tampa|suporte|"
                  r"alca|slider|antena|trava|alarme|borracha|sanfona|peso (de )?guidao|tripe|kit cavalete|estribo"),
]

def categoria(txt):
    t = norm(txt) + " "
    ja = next((c for c, ws in CATS if any(w in t for w in ws)), "")
    # peça que a lista antiga já conhecia pelo começo do nome (pastilha, vela, filtro, cabo...) continua onde estava
    if not re.match(r"(pastilha|lona|sapata|patim|kit transmissao|kit relacao|filtro|tela|oleo|vela|bateria|lampada|cabo |pneu|camara|palheta|"
                    r"retrovisor|manete|pedaleira|retentor)", t):
        for c, pat in CATS_INICIO:
            if re.match(pat, t):
                return c
    return ja

def main():
    if "--so-kits" in sys.argv:
        return so_kits()
    src = Path(sys.argv[1])
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 100
    saida, vistos, revisao, fora = [], set(), [], []
    tetos = carregar_tetos()
    for r in csv.DictReader(open(src, encoding="utf-8-sig")):
        sku = col(r, "codigo", "sku", "cod")
        nome = col(r, "nome", "descricao", "produto")
        custo = numero(col(r, "preco_custo", "custo", "preco"))
        est = col(r, "estoque", "disponibilidade")
        if not sku or not nome or custo <= 0 or sku in vistos:
            continue
        nome = re.sub(r"(\S)- ", r"\1 - ", nome)  # 'FILTRO DO AR MOTOR- JFA0M79 - WEGA'
        if len(nome.split(" - ")) < 3:
            nome = re.sub(r"(\D)-(\d{6,})\b", r"\1 - \2", re.sub(r" -(\S)", r" - \1", nome))  # 'ESTRIBO ... PRETO-100502302 -POLIMET'
        marca_r = col(r, "marca")
        if "¿" in nome:  # 'PASTILHA DE FREIO DIANTEIRA DIAFRAG DFP-20905 ¿ SISTEMA CBS'
            desc = re.sub(r"\s+", " ", re.sub(r"\b[A-Z]{2,4}-?\d{3,}\b", "", nome.replace("¿", " ").replace(marca_r, " "))).strip()
            nome = f"{desc} - {sku} - {marca_r}"
        elif len(nome.split(" - ")) < 3 and marca_r:  # nome veio sem a marca no fim
            nome = f"{nome} - {marca_r}"
        if sku in FORA_SKU:
            revisao.append(f"{sku};{nome};custo {custo:.2f};custo fora do normal, conferir na Real")
            continue
        if not serve_em_moto(nome, col(r, "aplicacao")):  # 25/11: catálogo ampliado só com peça que o cliente sabe em que moto serve
            fora.append(f"{sku};{nome};{col(r, 'aplicacao')[:80]}")
            continue
        if est and norm(est) in ("0", "indisponivel", "sem estoque", "esgotado", "false", "nao"):
            continue
        if est.isdigit() and int(est) < ESTOQUE_MIN:  # estoque baixo na Real: risco de faltar
            continue
        cat = categoria(nome + " " + col(r, "categoria"))
        if not cat:
            continue
        teto = teto_de(nome, col(r, "aplicacao"), tetos, marca_r)
        pv = preco_de_custo(custo, cat, nome, teto)  # ml_medio = média da mesma marca/linha; o build soma a folga
        if pv is None:
            if teto:
                revisao.append(f"{sku};{nome};custo {custo:.2f};média da marca/linha {teto:.2f}")
            continue
        veic = col(r, "aplicacao", "veiculos", "aplicacao/veiculos")
        cr = norm(col(r, "categoria"))
        tipo = "carro" if cr.startswith("carro") else "moto" if cr.startswith("moto") else "carro" if any(w in norm(nome + " " + veic) + " " for w in CARRO) or "carro" in norm(col(r, "categoria")) else "moto"
        if SO_MOTO and tipo == "carro":  # Luan 24/11: por enquanto só 2 rodas
            continue
        vistos.add(sku)
        saida.append({"sku": sku, "nome": nome[:120], "tipo": tipo, "categoria": cat, "marca": col(r, "marca") or "",
                      "veiculos": ";".join(modelos(veic))[:400] or "Consultar aplicação no WhatsApp",
                      "preco": "", "custo": f"{custo:.2f}", "ml_medio": f"{teto:.2f}" if teto else "", "estoque": 10 if not est or not est.isdigit() else est,
                      "imagem": "", "descricao": f"{nome}. Entrega por motoboy no mesmo dia na Grande Vitória."})
        if len(saida) >= mx:
            break
    saida = montar_kits({s["sku"]: s for s in saida}) + saida
    campos = CAMPOS
    with open(RAIZ / "dados/produtos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(saida)
    print(f"{len(saida)} peças importadas para dados/produtos.csv")
    (RAIZ / "dados/fora_sem_moto.txt").write_text("\n".join(fora) + ("\n" if fora else ""), encoding="utf-8")
    if fora:
        print(f"{len(fora)} peças ficaram de fora por não terem moto na aplicação: ver dados/fora_sem_moto.txt")
    (RAIZ / "dados/revisao.txt").write_text("\n".join(revisao) + ("\n" if revisao else ""), encoding="utf-8")
    if revisao:
        print(f"{len(revisao)} peças acima do preço médio da concorrência: ver dados/revisao.txt")

if __name__ == "__main__":
    main()
