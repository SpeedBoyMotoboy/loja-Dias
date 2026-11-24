# Site da Loja Dias Peças

- `dados/produtos.csv`: catálogo (uma linha por peça). O robô das distribuidoras vai preencher este arquivo.
- `dados/config.json`: WhatsApp, desconto Pix, fretes por cidade. Valores atuais são EXEMPLO.
- `assets/`: visual (style.css) e carrinho/filtros (app.js).
- `python3 build.py` gera `dist/`: páginas de produto, páginas por cidade, catálogo, carrinho, sitemap.xml, robots.txt e feed-google.xml (Merchant Center).
- `dist/_artifact_index.html` é só para a prévia no Claude; no ar vale `dist/index.html`.
- Antes de publicar: trocar `site_url`, `whatsapp`, fretes e colocar `DEMO = False` no build.py.
