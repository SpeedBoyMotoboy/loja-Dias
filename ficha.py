"""Ficha técnica da peça (25/11/2026, pedido do Luan).

Regra: só entra dado que está no nome da peça na Real Motopeças (distribuidora) ou numa página do
fabricante/norma. O que não está confirmado aparece como "Não informado". Nunca inventar.

Fontes do aço dos kits de transmissão (conferidas em 25/11/2026):
- Cobreq: catálogo Kit Transmissão (jul/2024) https://cobreq.com.br/wp-content/uploads/2026/04/Catalogo-Kit-Transmissao.pdf
  "A coroa e o pinhão são produzidos em aço 1045 e a corrente é classe A."; coroa com tratamento de zinco.
- Cofap (Marelli Cofap): https://mmcofap.com.br/categoria-produtos/transmissao/kits-transmissao
  "coroa e pinhão produzidos em aço 1045 com tratamento térmico". Versões R têm corrente com retentor.
- Riffel: https://www.riffel.com.br/moto-pecas/kits-de-transmissao/  Titanium: coroa e pinhão aço 1045 e
  corrente reforçada. Todas as linhas Riffel (Titanium, Top, Carbon) têm coroa em aço 1045; o pinhão muda
  por linha, então no kit "com retentor" o pinhão fica "não informado".
- Nakata: declaração da Nakata publicada em O Mecânico (26/10/2016)
  https://omecanico.com.br/nakata-lanca-kit-coroa-e-pinhao-para-motocicletas-na-reposicao/
  "fabricadas com aço 1045, sendo que a coroa possui tratamento térmico nos dentes"; pinhão com tratamento térmico superficial.
Passo da corrente: numeração padrão ANSI/ISO (420 e 428 = 12,7 mm; 520, 525 e 530 = 15,875 mm).
Rolamento: medidas da norma ISO 15 para a série (6000, 6200, 6300).
"""
import re
import unicodedata

NI = "Não informado"

ACO_KIT = {
    "COBREQ": ("Aço 1045, com tratamento de zinco contra ferrugem", "Aço 1045", "Classe A, tipo rolete", "Catálogo Cobreq"),
    "COFAP": ("Aço 1045 com tratamento térmico", "Aço 1045 com tratamento térmico", NI, "Site da Cofap"),
    "NAKATA": ("Aço 1045, dentes com tratamento térmico", "Aço 1045 com tratamento térmico na superfície", NI, "Nakata"),
}
RIFFEL_TITANIUM = ("Aço 1045", "Aço 1045", "Reforçada", "Site da Riffel")
RIFFEL_OUTRA = ("Aço 1045", NI, NI, "Site da Riffel")

PASSO = {"415": "12,7 mm", "420": "12,7 mm", "428": "12,7 mm", "520": "15,875 mm", "525": "15,875 mm", "530": "15,875 mm"}

# ISO 15: diâmetro interno x externo x largura (mm)
ROLAMENTO = {
    "6000": (10, 26, 8), "6001": (12, 28, 8), "6002": (15, 32, 9), "6003": (17, 35, 10), "6004": (20, 42, 12), "6005": (25, 47, 12),
    "6200": (10, 30, 9), "6201": (12, 32, 10), "6202": (15, 35, 11), "6203": (17, 40, 12), "6204": (20, 47, 14), "6205": (25, 52, 15),
    "6300": (10, 35, 11), "6301": (12, 37, 12), "6302": (15, 42, 13), "6303": (17, 47, 14), "6304": (20, 52, 15),
}


def _n(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", s).strip()


def relacao(desc):
    """'KIT TRANSMISSÃO C/RET 428HOX118L/44X15' -> dict. Aceita '428H X 122L /48X14', '520H+106/37X13', '39TX13T'."""
    d = _n(desc)
    s = d.replace(" ", "")
    g = re.search(r"(\d{3})([A-Z]*?)[X+](\d{2,3})L?/(\d{2})T?X(\d{2})T?", s)
    if not g:
        return None
    corrente, letras = g.group(1), g.group(2)
    retentor = bool(re.search(r"O.?RING|C/ ?RET\b|COM RETENTOR", d) or "O" in letras)
    return {"corrente": corrente + ("H" if "H" in letras else ""), "passo": corrente, "elos": int(g.group(3)),
            "coroa": int(g.group(4)), "pinhao": int(g.group(5)), "retentor": retentor,
            "titanium": "TITANIUM" in d, "sem_ruido": "SEM RUIDO" in d}


def _medida_mm(d):
    g = re.search(r"(\d{1,3}(?:[.,]\d)?) ?X ?(\d{1,3}(?:[.,]\d)?) ?X ?(\d{1,3}(?:[.,]\d)?)", d)
    if g:
        return " x ".join(x.replace(".", ",") for x in g.groups()) + " mm"
    return None


_FAB = None


def _fabricante():
    """dados/ficha_fabricante.csv: codigo,rotulo,valor,fonte_url — dado lido na página do próprio fabricante."""
    global _FAB
    if _FAB is None:
        import csv, os
        _FAB = {}
        arq = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "ficha_fabricante.csv")
        if os.path.exists(arq):
            for r in csv.DictReader(open(arq, encoding="utf-8")):
                if r.get("codigo") and r.get("rotulo") and r.get("valor"):
                    _FAB.setdefault(_n(r["codigo"]).replace(" ", ""), []).append((r["rotulo"].strip(), r["valor"].strip()))
    return _FAB


def linhas(p):
    """Lista de (rótulo, valor) para a ficha técnica. Só dado confirmado."""
    if p["categoria"] == "kit":
        return []
    base = _linhas(p)
    partes = [x.strip() for x in p["nome_real"].split(" - ")]
    cod = partes[1] if len(partes) > 2 else p["sku"]
    fab = _fabricante().get(_n(cod).replace(" ", "")) or _fabricante().get(_n(p["sku"]).replace(" ", "")) or []
    if not fab:
        return base
    ja = {k for k, _ in base}
    tem_medida = any(k.lower().startswith(("medida", "altura", "diâmetro", "diametro", "comprimento", "largura", "rosca", "alcance", "sextavado")) for k, _ in fab)
    tem_mat = any(k.lower().startswith(("material", "eletrodo")) for k, _ in fab)
    base = [(k, v) for k, v in base if not ((k == "Medidas" and tem_medida or k == "Material" and tem_mat) and v == NI)]
    return base + [(k, v) for k, v in fab if k not in ja] + [("Fonte da medida", "Catálogo do fabricante")]


def _linhas(p):
    partes = [x.strip() for x in p["nome_real"].split(" - ")]
    desc, cod = partes[0], (partes[1] if len(partes) > 2 else p["sku"])
    d = _n(desc)
    marca_up = _n(p.get("marca", ""))
    out = []

    r = relacao(desc) if "KIT TRANSM" in d or "KIT RELA" in d else None
    if r:
        if marca_up == "RIFFEL":
            aco = RIFFEL_TITANIUM if r["titanium"] else RIFFEL_OUTRA
        else:
            aco = ACO_KIT.get(marca_up, (NI, NI, NI, ""))
        out += [("Coroa", f'{r["coroa"]} dentes'), ("Pinhão", f'{r["pinhao"]} dentes'),
                ("Corrente", f'{r["corrente"]}{" (reforçada)" if r["corrente"].endswith("H") else ""}, {r["elos"]} elos'),
                ("Passo da corrente", f'{r["passo"]} ({PASSO[r["passo"]]})' if r["passo"] in PASSO else r["passo"]),
                ("Retentor (O-ring)", "Com retentor (O-ring)" if r["retentor"] else "Sem retentor")]
        if r["sem_ruido"]:
            out.append(("Pinhão antirruído", "Sim (sem ruído)"))
        out += [("Aço da coroa", aco[0]), ("Aço do pinhão", aco[1]), ("Tipo da corrente", aco[2])]
        if aco[3]:
            out.append(("Fonte do aço", aco[3]))
        return out

    # corrente de comando: '(25H-90L)', '(0404SS 92L)', '(404SV-96L)'
    g = re.search(r"CORRENTE (DO |DE )?COMANDO \(?([0-9A-Z]+)[ -]?(\d{2,3})L\)?", d)
    if g:
        out += [("Corrente", g.group(2)), ("Elos", g.group(3))]
    g = re.match(r"ROLAMENTO.*?\b(6[023]0\d)\b", d + " " + _n(cod))
    if not g:
        g = re.search(r"\b(6[023]0\d)[.\-]?(2RS|2Z|ZZ|RS)", _n(cod))
    if g and g.group(1) in ROLAMENTO:
        a, b, c = ROLAMENTO[g.group(1)]
        out.append(("Medidas (interno x externo x largura)", f"{a} x {b} x {c} mm (norma da série {g.group(1)})"))
        cu = _n(cod)
        if re.search(r"2RS", cu):
            out.append(("Vedação", "Blindado dos dois lados com borracha (2RS)"))
        elif re.search(r"2Z|ZZ", cu):
            out.append(("Vedação", "Blindado dos dois lados com chapa de aço (2Z)"))
    elif d.startswith("RETENTOR") or "GUARDA PO" in d:
        m = _medida_mm(d)
        if m:
            out.append(("Medidas (interno x externo x altura)", m))
    else:
        m = _medida_mm(d)
        if m:
            out.append(("Medidas", m))
    g = re.match(r"CAMARA AR ([\d./-]+)\s*(TR\d+)?", d)
    if g:
        out.append(("Medida do pneu", g.group(1)))
        if g.group(2):
            out.append(("Válvula", g.group(2)))
    g = re.search(r"(\d+)AH", d)
    if g and d.startswith("BATERIA"):
        out.append(("Capacidade", f"{g.group(1)} Ah"))
    g = re.search(r"(\d+(?:[.,]\d+)?) ?(ML|G|KG|L)\b", d)
    if g and p["categoria"] == "oleo":
        out.append(("Conteúdo", f'{g.group(1).replace(".", ",")} {g.group(2).lower()}'))
    g = re.search(r"(\d+)G (\d+) ?PC", d)
    if g:
        out += [("Peso de cada rolete", f"{g.group(1)} g"), ("Quantidade", f"{g.group(2)} peças")]
    g = re.search(r"HASTE (\d+) ?MM", d)
    if g:
        out.append(("Rosca da haste", f"{g.group(1)} mm"))
    g = re.search(r"SOB ?MEDIDA (\d,\d+) ?MM", d)
    if g:
        out.append(("Medida", f"Sobremedida {g.group(1)} mm"))
    g = re.search(r"(\d+(?:/\d+)?) ?W\b", d)
    if g and d.startswith("LAMPADA"):
        out.append(("Potência", f"{g.group(1)} W"))
    if d.startswith("VELA"):
        out.append(("Código da vela", cod))
        if "IRIDIUM" in d:
            out.append(("Eletrodo", "Irídio (Iridium)"))
    if d.startswith(("PASTILHA", "PATIM", "LONA")):
        mat = ("Cerâmica" if "CERAM" in d else "Semimetálica" if "SEMI MET" in d else "Metálica (sinterizada)" if "METALI" in d
               else "Orgânica" if "ORGAN" in d else None)
        out.append(("Material de atrito", mat or NI))
    if d.startswith(("PASTILHA", "PATIM", "LONA", "DISCO FREIO", "CABO", "MANETE")) or "FREIO" in d.split()[:3]:
        pos = "Dianteira e traseira" if re.search(r"DIANT(EIR[OA])?/TRAS|DIANT.*E TRAS", d) else (
            "Dianteira" if "DIANT" in d else "Traseira" if "TRAS" in d else None)
        if pos:
            out.append(("Posição", pos))
    for cor in ("PRETO", "PRETA", "CROMADO", "CROMADA", "PRATA", "ZINCADO"):
        if re.search(rf"\b{cor}\b", d):
            out.append(("Acabamento", cor.capitalize().replace("Preta", "Preto").replace("Cromada", "Cromado")))
            break
    g = re.search(r"(STD|025|050|075|100|125|150)$", re.sub(r"[^A-Z0-9]", "", _n(cod)))
    if d.startswith("PISTAO") and g:
        out.append(("Medida do pistão", "Padrão (STD)" if g.group(1) == "STD" else f"Sobremedida {g.group(1)[0]},{g.group(1)[1:]} mm"))
    g = re.search(r"RAIO .*?(\d(?:[.,]\d)?) ?MM", d)
    if g:
        out.append(("Espessura do raio", f'{g.group(1).replace(".", ",")} mm'))
    for pal, mat in (("NYLON", "Nylon"), ("FERRO", "Ferro"), ("ACO", "Aço"), ("ALUMINIO", "Alumínio"), ("BORRACHA", "Borracha"), ("SILICONE", "Silicone")):
        if re.search(rf"(?<!C/)(?<!COM )\b{pal}\b", d) and not (pal == "ACO" and "BLINDAGEM ACO" in d):
            out.append(("Material", mat))
            break
    lado = "Lado direito" if re.search(r"\bLD\b|DIREIT", d) else "Lado esquerdo" if re.search(r"\bLE\b|ESQUERD", d) else None
    if lado:
        out.append(("Lado", lado))
    if not any(k.startswith("Medida") for k, _ in out) and not r:
        out.append(("Medidas", NI))
    if not any(k.startswith(("Material", "Aço")) for k, _ in out):
        out.append(("Material", NI))
    return out
