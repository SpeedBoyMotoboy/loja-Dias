---
name: cenario-de-projeto
description: Use quando Luan pedir para montar, planejar ou estruturar qualquer projeto: monta o cenário em 5 etapas fiéis à frase dele (situação, ameaças/oportunidades, soluções, execução, resultados), mínimo 1.000 caracteres.
---

# Cenário de Projeto — Método da Frase do Luan

## Frase base (não alterar)

> "E eu faço isso analisando situações, avaliando ameaças e oportunidades, encontrando soluções e executando opções para gerenciar resultados."

Toda a skill sai desta frase. São 5 etapas, sempre nesta ordem:

1. Analisando situações
2. Avaliando ameaças e oportunidades
3. Encontrando soluções
4. Executando opções
5. Gerenciando resultados

## Quando usar

- Luan pede para montar, planejar, estruturar ou "montar o cenário" de qualquer projeto: site, app, loja, cliente, proposta, contratação, rota, compra, campanha, problema do dia a dia.
- Luan traz uma situação e pergunta "o que eu faço?" e a resposta pede um plano, não uma frase só.

## Regras de fidelidade (não delirar)

- Usar SÓ as 5 etapas da frase. Não trocar por outro método (SWOT, OKR, Canvas, 5W2H etc.) nem acrescentar etapas novas.
- Não inventar fatos, números, preços, prazos ou nomes. Dado que Luan não deu e que não foi pesquisado/verificado = escrever "[a confirmar]".
- Dado atual do mundo (preço, lei, concorrente, taxa) → pesquisar antes de afirmar; citar a fonte.
- Usar o que já se sabe do Luan e do repositório (negócio, clientes, região, ferramentas, código) só quando muda o cenário.
- Cada etapa precisa ter conteúdo real do projeto. Nada de texto genérico que serviria para qualquer coisa.

## Tamanho mínimo

- O cenário completo tem NO MÍNIMO 1.000 caracteres (contando espaços).
- Se houver shell, contar com código (ex.: `python3 -c "print(len(open('cenario.md', encoding='utf-8').read()))"`). Sem shell, estimar com folga (≈ 170 palavras ou mais).
- Se ficar abaixo de 1.000: aprofundar as etapas com detalhes reais do projeto (mais riscos, mais opções, passos mais específicos). Nunca encher com repetição ou frase vazia.

## As 5 etapas em detalhe

### 1. Analisando situações
Objetivo: retratar o "hoje" do projeto.
- O que é o projeto e qual o objetivo final, em uma frase.
- Onde está agora: o que já existe, o que já foi feito.
- Recursos disponíveis: dinheiro, tempo, pessoas, ferramentas, contatos.
- Restrições: prazo, orçamento, regra, limitação técnica.
- Quem está envolvido: Luan, clientes, fornecedores, parceiros.
Saída: um retrato curto e claro da situação atual.

### 2. Avaliando ameaças e oportunidades
Objetivo: ver o que pode atrapalhar e o que pode ajudar.
- Ameaças: o que pode dar errado. Para cada uma: impacto (alto/médio/baixo) e chance (alta/média/baixa).
- Oportunidades: o que pode ser aproveitado (demanda, momento, recurso parado, parceria, ferramenta).
- Ordenar as duas listas da mais importante para a menos importante.
Saída: duas listas classificadas — Ameaças e Oportunidades.

### 3. Encontrando soluções
Objetivo: transformar ameaças e oportunidades em respostas.
- Para cada ameaça principal: como evitar ou diminuir.
- Para cada oportunidade principal: como aproveitar.
- Para o problema central do projeto: no mínimo 2 opções diferentes, cada uma com prós, contras, custo e prazo ("[a confirmar]" se não souber).
Saída: lista de soluções e as opções lado a lado.

### 4. Executando opções
Objetivo: escolher e colocar em prática.
- Escolher a opção e dizer o critério da escolha (mais barata, mais rápida, menos risco…).
- Plano de ação em passos: o quê, quem, até quando, com qual recurso.
- Primeiro passo concreto, que dá para fazer hoje ou amanhã.
- Luan diz "eu só falo, vocês executam": o que Claude pode executar, Claude executa. O que só Luan pode fazer, dar instrução mínima e literal (ex.: "manda esta mensagem", "clica aqui").
- Decisão difícil de desfazer (gastar dinheiro, assinar, publicar, enviar para cliente) → mostrar e esperar o OK do Luan.
Saída: opção escolhida + plano de ação + primeiro passo.

### 5. Gerenciando resultados
Objetivo: saber se deu certo e corrigir o rumo.
- Indicadores: como medir (ex.: visitas no site, pedidos, faturamento, clientes novos, prazo cumprido).
- Meta de cada indicador e data de checagem.
- Se o resultado sair do esperado: voltar à etapa 1 com os dados novos (o método é um ciclo).
Saída: lista de indicadores, metas, datas e plano de correção.

## Formato de saída

```
# Cenário — <nome do projeto>

## 1. Situação
<retrato do hoje>

## 2. Ameaças e oportunidades
Ameaças:
- <ameaça> — impacto <A/M/B>, chance <A/M/B>
Oportunidades:
- <oportunidade>

## 3. Soluções
- <ameaça/oportunidade> → <solução>
Opções para <problema central>:
- Opção A: prós / contras / custo / prazo
- Opção B: prós / contras / custo / prazo

## 4. Execução
Escolha: <opção> — motivo: <critério>
Passos:
1. <o quê> — <quem> — <até quando>
Primeiro passo: <ação concreta>

## 5. Resultados
- <indicador> — meta <valor> — checar em <data>
Se sair do esperado: <correção> → volta à etapa 1.
```

- Texto em português do Brasil, frases curtas e diretas.
- Se o cenário for para cliente ou outra pessoa ler, português normal e profissional.
- Se Luan quiser guardar o cenário no repositório, salvar em `docs/cenarios/<nome-do-projeto>.md`.

## Checklist antes de entregar

- [ ] As 5 etapas estão presentes, na ordem da frase.
- [ ] Nenhum método ou etapa extra foi inventado.
- [ ] Nenhum dado inventado; lacunas marcadas "[a confirmar]".
- [ ] Cenário com 1.000 caracteres ou mais, sem enchimento.
- [ ] Pelo menos 2 opções para o problema central.
- [ ] Primeiro passo concreto definido.
- [ ] Indicadores com meta e data de checagem.
