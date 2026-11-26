# Robô do Mercado Livre da Loja Dias. Roda no PC do Luan (a nuvem não alcança a API do ML).
# Uso:
#   python ml_robo.py login            -> abre o link de login do ML; Luan entra; cola o código
#   python ml_robo.py taxas            -> mostra tarifa real e custo fixo dos 10 do teste (não publica)
#   python ml_robo.py publicar --teste -> publica os 10 do teste (PAUSADOS, para conferir antes)
#   python ml_robo.py estoque          -> ajusta estoque/pausa pelo real_tudo.csv do robô da Real
# Arquivos: ml_app.json {"client_id","client_secret","redirect_uri"} e ml_token.json (fora do git, nunca no chat).
import csv, json, sys, time, subprocess, urllib.parse, pathlib, webbrowser

AQUI = pathlib.Path(__file__).parent
API = "https://api.mercadolibre.com"
APP = AQUI / "ml_app.json"
TOK = AQUI / "ml_token.json"
LISTA = AQUI / "piloto-60-pc.csv"
FEITOS = AQUI / "ml_anuncios.csv"   # sku -> id do anúncio
MAX_QTD = 2

def curl(metodo, url, dados=None, token=None, form=False):
    # Python do PC não valida TLS; usar curl.exe (ver memória loja-dias-pendencias-pc)
    cmd = ["curl.exe", "-s", "-X", metodo, url]
    if token: cmd += ["-H", f"Authorization: Bearer {token}"]
    if dados is not None:
        if form:
            for k, v in dados.items(): cmd += ["--data-urlencode", f"{k}={v}"]
        else:
            cmd += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(dados)]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").stdout
    try: return json.loads(out)
    except Exception: return {"erro_bruto": out[:500]}

def app(): return json.loads(APP.read_text(encoding="utf-8"))

def token():
    t = json.loads(TOK.read_text(encoding="utf-8"))
    if time.time() > t["vence"] - 300:
        a = app()
        n = curl("POST", f"{API}/oauth/token", {"grant_type": "refresh_token", "client_id": a["client_id"],
                 "client_secret": a["client_secret"], "refresh_token": t["refresh_token"]}, form=True)
        if "access_token" not in n: sys.exit(f"Falha ao renovar token: {n}")
        n["vence"] = time.time() + n["expires_in"]; TOK.write_text(json.dumps(n)); t = n
    return t["access_token"]

def login():
    a = app()
    url = "https://auth.mercadolivre.com.br/authorization?" + urllib.parse.urlencode(
        {"response_type": "code", "client_id": a["client_id"], "redirect_uri": a["redirect_uri"]})
    webbrowser.open(url)
    cod = input("Depois de entrar, copie o código (code=TG-...) da barra de endereço e cole aqui: ").strip()
    cod = cod.split("code=")[-1].split("&")[0]
    t = curl("POST", f"{API}/oauth/token", {"grant_type": "authorization_code", "client_id": a["client_id"],
             "client_secret": a["client_secret"], "code": cod, "redirect_uri": a["redirect_uri"]}, form=True)
    if "access_token" not in t: sys.exit(f"Login falhou: {t}")
    t["vence"] = time.time() + t["expires_in"]; TOK.write_text(json.dumps(t))
    eu = curl("GET", f"{API}/users/me", token=t["access_token"])
    print("OK. Conta:", eu.get("nickname"), "| tipo:", eu.get("user_type"), "| reputação:",
          (eu.get("seller_reputation") or {}).get("level_id"))

def lista(teste=False):
    rs = list(csv.DictReader(open(LISTA, encoding="utf-8")))
    return [r for r in rs if r["teste_10"] == "sim"] if teste else rs

def categoria(nome):
    r = curl("GET", f"{API}/sites/MLB/domain_discovery/search?limit=1&q=" + urllib.parse.quote(nome))
    return r[0]["category_id"] if isinstance(r, list) and r else None

def taxas():
    for r in lista(True):
        cat = categoria(r["nome"]); p = float(r["preco_ml"])
        lp = curl("GET", f"{API}/sites/MLB/listing_prices?price={p}&category_id={cat}&listing_type_id=gold_special")
        fee = lp.get("sale_fee_amount") if isinstance(lp, dict) else None
        det = lp.get("sale_fee_details", {}) if isinstance(lp, dict) else {}
        print(f"{r['sku']};{cat};{p};tarifa_total={fee};pct={det.get('percentage_fee')};fixo={det.get('fixed_fee')}")

def publicar(teste=True):
    tk = token(); feitos = {}
    if FEITOS.exists(): feitos = {x["sku"]: x["id"] for x in csv.DictReader(open(FEITOS, encoding="utf-8"))}
    for r in lista(teste):
        if r["sku"] in feitos: continue
        cat = categoria(r["nome"])
        fotos = [r["foto1"]]
        item = {"title": r["nome"][:60], "category_id": cat, "price": float(r["preco_ml"]), "currency_id": "BRL",
                "available_quantity": min(MAX_QTD, int(float(r["estoque_real"]))), "buying_mode": "buy_it_now",
                "listing_type_id": "gold_special", "condition": "new",
                "pictures": [{"source": f} for f in fotos if f],
                "attributes": [{"id": "SELLER_SKU", "value_name": r["sku"]}]}
        res = curl("POST", f"{API}/items", item, token=tk)
        if "id" not in res:
            print("ERRO", r["sku"], json.dumps(res, ensure_ascii=False)[:600]); continue
        curl("PUT", f"{API}/items/{res['id']}", {"status": "paused"}, token=tk)   # nasce pausado; Luan confere e libera
        desc = f"{r['nome']}\n\nServe em: {r['motos'].replace(';', ', ')}\n\nPeça nova. Entrega no mesmo dia na Grande Vitória para pedidos até 12h."
        curl("POST", f"{API}/items/{res['id']}/description", {"plain_text": desc}, token=tk)
        feitos[r["sku"]] = res["id"]; print("OK", r["sku"], res["id"], res.get("permalink"))
        with open(FEITOS, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["sku", "id"]); w.writerows(feitos.items())

def estoque(real_csv):
    tk = token(); feitos = {x["sku"]: x["id"] for x in csv.DictReader(open(FEITOS, encoding="utf-8"))}
    real = {x.get("codigo") or x.get("sku"): x for x in csv.DictReader(open(real_csv, encoding="utf-8"))}
    for sku, iid in feitos.items():
        x = real.get(sku)
        if not x: continue  # kit: estoque vem das peças (fazer depois)
        e = int(float(x.get("estoque") or 0))
        if e < 5: curl("PUT", f"{API}/items/{iid}", {"status": "paused"}, token=tk); print("pausa", sku, e)
        else: curl("PUT", f"{API}/items/{iid}", {"available_quantity": min(MAX_QTD, e)}, token=tk)

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "login": login()
    elif c == "taxas": taxas()
    elif c == "publicar": publicar("--teste" in sys.argv)
    elif c == "estoque": estoque(sys.argv[2])
    else: print(__doc__ or "use: login | taxas | publicar --teste | estoque real_tudo.csv")
