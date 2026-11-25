# Firebase: avaliações de peças

- `avaliacoes.rules`: bloco que entra no firestore.rules da loja, antes de `match /{doc=**}`.
- `storage.rules`: só para vídeo de avaliação. Precisa do plano Blaze (desligado: Luan escolheu só fotos em 25/11).
- `teste-regras.mjs`: testes das regras no emulador (`npx firebase emulators:exec --only firestore,storage "node teste-regras.mjs"`, com firestore.rules e storage.rules na mesma pasta).
- Ligar vídeo depois: plano Blaze + publicar storage.rules + `"video_avaliacao": true` no dados/config.json.

# Firebase: painel de pedidos (25/11)

- `vendas.rules`: bloco que entra no firestore.rules da loja, antes de `match /{doc=**}`. Qualquer pessoa cria pedido novo; só a loja lê, muda etapa ou apaga.
- `teste-vendas.mjs`: 28 testes no emulador (`npx firebase emulators:exec --only firestore "node teste-vendas.mjs"`).
- No computador (localhost) o site usa o simulador do Firebase (auth 9099, firestore 8080) e não liga o App Check.
