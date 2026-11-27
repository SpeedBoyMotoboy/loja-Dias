#!/usr/bin/env python3
"""Varredura diária da Real (pedido do Luan 25/11/2026): atualiza custo e estoque das peças do site.

Uso: python3 atualizar_real.py real_tudo.csv [--data 2026-11-26]
     python3 atualizar_real.py --delta delta.txt [--data ...]   (só as linhas que mudaram: codigo;custo;estoque,
     geradas no PC por robo-real/delta_site.py; o que não veio fica como está)
Entrada: CSV do robô do PC (colunas codigo, preco_custo, estoque). Mexe em dados/produtos.csv e dados/pausados.csv.
Saída: dados/varredura.txt (relatório curto para o Luan) e código de saída 2 quando a varredura não é confiável.

Regras:
- Preço de venda continua saindo do custo pela regra de margem do build.py (lucro mínimo, 20% de margem mínima).
- Estoque na Real abaixo de 3: a peça sai do site (vai para pausados.csv). Volta sozinha quando a Real tiver 10 ou mais
  (5 ou mais na curva A: relação, pastilha, lona, bateria e câmara; Mesa de 25/11).
- Peça que a varredura não achou: fica no site como está (pode ser falha do robô), mas entra no relatório.
- Se a varredura achou menos de 80% das peças do site, nada é mudado (robô provavelmente falhou ou o login caiu).
- Custo que subiu mais de 10% entra no relatório. Kits são refeitos com os custos novos (lucro mínimo R$ 8).
"""
import csv, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from importar_real import CAMPOS, montar_kits, numero, estoque_min
from build import preco_de_custo

SAI, VOLTA, ALTA, COBERTURA = 3, 10, 0.10, 0.80


def ler(arq):
    return list(csv.DictReader(open(arq, encoding="utf-8"))) if arq.exists() else []


def gravar(arq, linhas):
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def preco(r, custo):
    ml = float(r["ml_medio"]) if (r.get("ml_medio") or "").strip() else None
    return preco_de_custo(custo, r["categoria"], r["nome"], ml, r.get("tipo") or "moto")


def main():
    data = sys.argv[sys.argv.index("--data") + 1] if "--data" in sys.argv else ""
    real = {}
    if "--delta" in sys.argv:
        for r in ler(RAIZ / "dados/produtos.csv") + ler(RAIZ / "dados/pausados.csv"):
            if r["categoria"] != "kit" and r.get("tipo") != "carro":
                real[r["sku"]] = (float(r["custo"] or 0), int(r["estoque"]) if str(r["estoque"]).isdigit() else None)
        for ln in open(sys.argv[sys.argv.index("--delta") + 1], encoding="utf-8"):
            p = ln.strip().split(";")
            if len(p) == 3 and p[0]:
                real[p[0]] = (numero(p[1]), int(p[2]) if p[2].isdigit() else None)
    for r in ([] if "--delta" in sys.argv else csv.DictReader(open(Path(sys.argv[1]), encoding="utf-8-sig"))):
        cod = (r.get("codigo") or r.get("sku") or "").strip()
        if cod and cod not in real:
            est = (r.get("estoque") or "").strip()
            real[cod] = (numero(r.get("preco_custo") or r.get("custo") or "0"), int(est) if est.isdigit() else None)
    todas = ler(RAIZ / "dados/produtos.csv")
    carro = [r for r in todas if r.get("tipo") == "carro"]  # peças da Laguna: a varredura da Real não mexe nelas
    pecas = [r for r in todas if r["categoria"] != "kit" and r.get("tipo") != "carro"]
    kits_antes = {r["sku"]: r for r in ler(RAIZ / "dados/produtos.csv") if r["categoria"] == "kit"}
    pausados = ler(RAIZ / "dados/pausados.csv")
    achadas = [r for r in pecas if r["sku"] in real]
    rel = [f"Varredura da Real {data}".strip()]
    if not pecas or len(achadas) < COBERTURA * len(pecas):
        rel.append(f"NÃO CONFIÁVEL: a varredura achou só {len(achadas)} de {len(pecas)} peças do site. Nada foi mudado.")
        (RAIZ / "dados/varredura.txt").write_text("\n".join(rel) + "\n", encoding="utf-8")
        print("\n".join(rel))
        sys.exit(2)
    fica, sai, altas, baixas, sem_margem, sumiu = [], [], [], [], [], []
    for r in pecas:
        if r["sku"] not in real:
            sumiu.append(r["sku"]); fica.append(r); continue
        custo, est = real[r["sku"]]
        velho = float(r["custo"] or 0)
        if custo <= 0 or (est is not None and est < SAI):
            sai.append(r); continue
        if velho and custo > velho * (1 + ALTA):
            altas.append(f'{r["sku"]} {r["nome"].split(" - ")[0][:40]}: custo R$ {velho:.2f} -> R$ {custo:.2f}')
        elif velho and custo < velho * (1 - ALTA):
            baixas.append(r["sku"])
        r = dict(r, custo=f"{custo:.2f}", estoque=str(est if est is not None else r["estoque"]))
        if not (r.get("preco") or "").strip() and preco(r, custo) is None:
            sem_margem.append(f'{r["sku"]} (custo R$ {custo:.2f})'); sai.append(r); continue
        fica.append(r)
    volta = []
    resto = []
    for r in pausados:
        custo, est = real.get(r["sku"], (0, None))
        if custo > 0 and est is not None and est >= min(VOLTA, estoque_min(r["nome"])) and preco(r, custo) is not None:
            volta.append(dict(r, custo=f"{custo:.2f}", estoque=str(est)))
        else:
            resto.append(r)
    novos_paus = {r["sku"]: r for r in resto + sai}
    fica += volta
    kits = montar_kits({r["sku"]: r for r in fica})
    kits_fora = sorted(set(kits_antes) - {k["sku"] for k in kits})
    muda_kit = [f'{k["sku"]}: R$ {float(kits_antes[k["sku"]]["preco"]):.2f} -> R$ {float(k["preco"]):.2f}'
                for k in kits if k["sku"] in kits_antes and abs(float(k["preco"]) - float(kits_antes[k["sku"]]["preco"])) >= 0.01]
    gravar(RAIZ / "dados/produtos.csv", kits + fica + carro)
    gravar(RAIZ / "dados/pausados.csv", list(novos_paus.values()))
    rel.append(f"Peças no site: {len(fica)} + {len(kits)} kits. Conferidas na Real: {len(achadas)}.")
    if sai:
        rel.append(f"Saíram do site (estoque da Real abaixo de {SAI} ou sem margem): {len(sai)}: " + ", ".join(r["sku"] for r in sai[:30]))
    if volta:
        rel.append(f"Voltaram ao site (Real com {VOLTA}+ de estoque, ou 5+ na curva A): {len(volta)}: " + ", ".join(r["sku"] for r in volta[:30]))
    if altas:
        rel.append(f"Custo subiu mais de 10% ({len(altas)}); o preço do site subiu junto:")
        rel += ["  " + a for a in altas[:30]]
    if baixas:
        rel.append(f"Custo caiu mais de 10%: {len(baixas)} peças (preço do site caiu junto).")
    if sem_margem:
        rel.append("Saíram por não dar mais margem: " + ", ".join(sem_margem[:20]))
    if muda_kit:
        rel.append("Kits com preço novo: " + "; ".join(muda_kit))
    if kits_fora:
        rel.append("Kits que saíram (peça faltando ou sem desconto): " + ", ".join(kits_fora))
    if sumiu:
        rel.append(f"Não achadas na varredura (ficaram como estavam): {len(sumiu)}: " + ", ".join(sumiu[:20]))
    (RAIZ / "dados/varredura.txt").write_text("\n".join(rel) + "\n", encoding="utf-8")
    print("\n".join(rel))


if __name__ == "__main__":
    main()
