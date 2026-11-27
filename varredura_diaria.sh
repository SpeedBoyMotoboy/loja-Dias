#!/bin/bash
# Varredura diária da Real (25/11/2026). Uso: bash varredura_diaria.sh delta.txt AAAA-MM-DD
# 1) dados de verdade ficam em /mnt/project-files/loja-dias/privado/ (produtos.csv, pausados.csv)
# 2) aplica o delta, gera o site, publica no gh-pages e devolve os CSV para privado/ com cópia datada.
set -e
cd "$(dirname "$0")"
PRIV=/mnt/project-files/loja-dias/privado
DELTA="$1"; DIA="$2"
cp "$PRIV/produtos.csv" dados/produtos.csv
[ -f "$PRIV/pausados.csv" ] && cp "$PRIV/pausados.csv" dados/pausados.csv || rm -f dados/pausados.csv
cp dados/produtos.csv "/tmp/produtos_antes_$DIA.csv"
python3 atualizar_real.py --delta "$DELTA" --data "$DIA"
python3 build.py | tail -1
cp dados/produtos.csv "$PRIV/produtos.csv"; cp dados/produtos.csv "$PRIV/produtos_$DIA.csv"
[ -f dados/pausados.csv ] && cp dados/pausados.csv "$PRIV/pausados.csv"
cp dados/varredura.txt "$PRIV/varredura_$DIA.txt"
echo "OK: agora publicar dist/ no gh-pages (sem _artifact_index.html)"
