# Firebase: avaliações de peças

- `avaliacoes.rules`: bloco que entra no firestore.rules da loja, antes de `match /{doc=**}`.
- `storage.rules`: só para vídeo de avaliação. Precisa do plano Blaze (desligado: Luan escolheu só fotos em 25/11).
- `teste-regras.mjs`: testes das regras no emulador (`npx firebase emulators:exec --only firestore,storage "node teste-regras.mjs"`, com firestore.rules e storage.rules na mesma pasta).
- Ligar vídeo depois: plano Blaze + publicar storage.rules + `"video_avaliacao": true` no dados/config.json.
