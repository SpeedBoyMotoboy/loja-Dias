// Loja Dias: painel de pedidos (só o Luan). Lê vendas/{txid}, que o carrinho grava com ou sem login.
// Quem pode abrir: e-mails da loja nas regras do Firestore (função loja()).
// Tudo que veio do celular do cliente é NÃO confiável: todo texto passa por esc() e o total é recalculado pelo catálogo.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, connectAuthEmulator, GoogleAuthProvider, signInWithPopup, signInWithRedirect, getRedirectResult, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, connectFirestoreEmulator, collection, query, orderBy, limit, onSnapshot, doc, getDoc, setDoc, writeBatch, increment, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config, P = window.LOJA.produtos, CID = C.cidades || [], IND = C.ind;
const app = initializeApp(C.firebase);
const EMU = ["localhost", "127.0.0.1"].includes(location.hostname);  // teste no computador: usa o simulador do Firebase
if (C.appcheck && !EMU) initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(C.appcheck), isTokenAutoRefreshEnabled: true });
const auth = getAuth(app), db = getFirestore(app);
if (EMU) { connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true }); connectFirestoreEmulator(db, "127.0.0.1", 8080); }
const box = document.querySelector("#admin");
const brl = v => (Number(v) || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const esc = s => String(s ?? "").replace(/[<>&"']/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c]));
const so = s => String(s ?? "").replace(/\D/g, "");
const PROD = new Map(P.map(p => [p.sku, p]));
const okRef = r => typeof r === "string" && /^[A-Z0-9]{3,12}$/.test(r);

const ETAPAS = { novo: "Novo", pix_caiu: "Pix caiu", saiu: "Saiu com motoboy", entregue: "Entregue", troca: "Troca", cancelado: "Cancelado" };
const COR = { novo: "#C62828", pix_caiu: "#1565C0", saiu: "#EF6C00", entregue: "#2E7D32", troca: "#6A1B9A", cancelado: "#616161" };
// próximo passo, pelo que já aconteceu com o pedido
const pago = o => !!o.pago_em || o.status === "pix_caiu";
const saiu = o => o.status === "saiu" || (Array.isArray(o.historico) && o.historico.some(h => h && h.s === "saiu"));
// Luan 26/11: Pix na entrega desligado (C.na_entrega false). Pedido que ainda diz "entrega" (forjado ou antigo) vira Pix antes.
const ENT_OK = !!C.na_entrega;
const naEnt = o => ENT_OK && o.pagamento === "entrega";
const entForjada = o => !ENT_OK && o.pagamento === "entrega";
const sinalDe = o => (naEnt(o) && C.entrega_limite && C.entrega_sinal && Number(o.total) > C.entrega_limite) ? Math.min(C.entrega_sinal, Number(o.total)) : 0;
function proximo(o) {
  if (!["novo", "pix_caiu", "saiu"].includes(o.status)) return null;
  if (o.entrega === "retirada") return pago(o) ? "entregue" : "pix_caiu";
  if (!naEnt(o)) return !pago(o) ? "pix_caiu" : !saiu(o) ? "saiu" : "entregue";
  return !saiu(o) ? "saiu" : !pago(o) ? "pix_caiu" : "entregue";
}
// o que o Luan faz agora, em uma frase
function agora(o, k) {
  // valor que não bate: a frase usa o valor certo pelo catálogo, não o que veio do celular do cliente
  const nx = proximo(o), sn = sinalDe(o), t = k && !k.confere && k.conhecido ? `${brl(k.esperado)} (o pedido diz ${brl(o.total)})` : brl(o.total);
  if (o.status === "entregue") return "Pronto. Pedido entregue.";
  if (o.status === "cancelado") return "Pedido cancelado.";
  if (o.status === "troca") return "Combine a troca com o cliente no WhatsApp.";
  if (nx === "pix_caiu" && o.entrega === "retirada") return `Veja no banco se caiu o Pix de ${t}.`;
  if (nx === "pix_caiu" && !naEnt(o)) return `Veja no app do banco se caiu o Pix de ${t}. Print não vale.`;
  if (nx === "pix_caiu") return `Na porta, o cliente faz o Pix${sn ? ` do resto, ${brl(Number(o.total) - sn)}` : ` de ${t}`}. Só entregue quando cair no banco.`;
  if (nx === "saiu") return (naEnt(o) ? (sn ? `Veja se caiu o sinal de ${brl(sn)}. ` : "O cliente paga na entrega. ") : "Pix recebido. ") + "Compre as peças na Real e mande o motoboy.";
  if (nx === "entregue") return o.entrega === "retirada" ? "Quando o cliente buscar, marque entregue." : "Quando o motoboy entregar, marque entregue.";
  return "";
}
const BOTAO = { pix_caiu: "Caiu o Pix ✓", saiu: "Saiu com o motoboy", entregue: "Entregue ✓" };

let VENDAS = [], filtro = "fazer", busca = "", primeira = true, som = false, actx = null, vistos = new Set(), parar = null;

// ---------- conferência pelo catálogo ----------
function conferir(o) {
  const itens = Array.isArray(o.itens) ? o.itens.filter(i => i && typeof i === "object") : [];
  let sub = 0, conhecido = true, baseInd = 0;
  const linhas = itens.map(i => {
    const p = PROD.get(String(i.sku)), q = Math.max(0, Math.min(99, Number(i.qtd) | 0));
    if (!p) { conhecido = false; return { i, p: null, q }; }
    sub += p.preco * q; if (p.ind) baseInd += p.preco * q;
    return { i, p, q };
  });
  const ref = okRef(o.ref) ? o.ref : "";
  const descInd = ref && IND ? Math.round(baseInd * IND.desconto * 100) / 100 : 0;
  const comissao = ref && IND ? Math.round(baseInd * IND.comissao * 100) / 100 : 0;
  const descPix = sub * (C.desconto_pix || 0);
  const cid = CID.find(c => c.slug === (o.cliente && o.cliente.cidade));
  const CR = C.carro, ps = linhas.filter(l => l.p);
  const carro = !!CR && ps.some(l => l.p.tipo === "carro");
  const fior = !!CR && (ps.some(l => l.p.fiorino) || ps.reduce((a, l) => a + (l.p.kg || 0) * l.q, 0) > (CR.fiorino_kg || Infinity));
  const freteCat = o.entrega === "retirada" || !cid ? 0
    : fior ? (CR.fiorino[cid.slug] || 0)
    : carro ? (sub >= CR.gratis_acima ? 0 : (CR.frete[cid.slug] || 0))
    : (sub >= (cid.gratis_acima || C.frete_gratis_acima || Infinity) ? 0 : cid.normal);
  const sem = Math.round((sub - descPix - descInd) * 100) / 100, com = Math.round((sem + freteCat) * 100) / 100;
  // o 6º pedido (fidelidade) pode vir sem frete: só aceita "sem frete" se o cliente tinha conta
  const aceitos = o.uid && !fior ? [com, sem] : [com];
  const confere = conhecido && aceitos.some(v => Math.abs(v - Number(o.total)) < 0.011);
  const semFrete = confere && freteCat > 0 && Math.abs(sem - Number(o.total)) < 0.011;  // tirou o frete: Luan confere se é o 6º pedido
  return { linhas, sub, freteCat, esperado: com, confere, conhecido, ref, descInd, comissao, semFrete };
}

// códigos para comprar na Real: kit vira as peças dele
function codigosReal(linhas) {
  const out = [];
  for (const { p, q, i } of linhas) {
    if (!p) { out.push({ sku: String(i.sku), nome: String(i.nome || "peça desconhecida"), q, desconhecida: true }); continue; }
    if (p.categoria === "kit" && Array.isArray(p.partes) && p.partes.length) {
      for (const s of p.partes) { const x = PROD.get(s); out.push({ sku: s, nome: x ? (x.nome_real || x.nome) : s, q }); }
    } else out.push({ sku: p.sku, nome: p.nome_real || p.nome, q });
  }
  const junto = new Map();  // mesma peça avulsa + dentro de kit vira uma linha só
  for (const r of out) { const x = junto.get(r.sku); if (x) x.q += r.q; else junto.set(r.sku, { ...r }); }
  return [...junto.values()];
}

// ---------- tela ----------
const fmt = t => t && t.toDate ? t.toDate().toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "agora";
const chip = s => `<span class="pchip" style="background:${COR[s] || "#616161"}">${esc(ETAPAS[s] || s)}</span>`;

function cartao(o) {
  const k = conferir(o), cli = o.cliente || {}, tel = so(cli.telefone), real = codigosReal(k.linhas);
  const wa = tel.length >= 10 ? `https://wa.me/55${tel.replace(/^55(?=\d{10,11}$)/, "")}` : "";
  const cidN = (CID.find(c => c.slug === cli.cidade) || {}).nome || "";
  const mapa = cli.endereco ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(cli.endereco + ", " + cidN + ", ES")}` : "";
  const onde = o.entrega === "retirada" ? "Vai buscar na loja" : `${esc(cli.endereco)}${cidN ? " · " + esc(cidN) : ""}`;
  const nx = proximo(o), sn = sinalDe(o);
  const hist = Array.isArray(o.historico) ? o.historico.filter(h => h && typeof h === "object") : [];
  const nf = o.nf && typeof o.nf === "object" ? o.nf : null;
  const cnpj = nf ? so(nf.cnpj).replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5") : "";
  const pagTxt = entForjada(o) ? "Pix antes de sair (o pedido pedia entrega, a loja não aceita)" : naEnt(o) ? (sn ? `Sinal de ${brl(sn)} no Pix + resto na entrega` : "Pix na entrega") : "Pix antes de sair";
  return `<article class="pcard st-${esc(o.status)}" data-id="${esc(o.txid)}">
  <div class="ptop">${chip(o.status)}<span class="note">${fmt(o.criado)}</span></div>
  <div class="pnome"><b>${esc(cli.nome) || "(sem nome)"}</b><b class="pval">${brl(o.total)}</b></div>
  <div class="pitens">${k.linhas.map(({ i, p, q }) => `<div>${q}x ${esc(p ? p.nome : i.nome)}</div>`).join("")}</div>
  ${k.confere ? "" : `<p class="palerta">⚠ O valor não bate com os preços da loja (o certo seria ${k.conhecido ? brl(k.esperado) : "?"}). Confira com o cliente antes.</p>`}
  ${nf ? `<p class="pinfo">🧾 Pediu nota fiscal (veja em Detalhes)</p>` : ""}
  ${entForjada(o) ? `<p class="palerta">⚠ Pedido diz pagar na entrega, mas a loja não aceita. Exija o Pix antes.</p>` : ""}
  ${k.semFrete ? `<p class="palerta">⚠ Veio sem frete. Confira se é o 6º pedido do cliente (fidelidade).</p>` : ""}
  <p class="pagora">${esc(agora(o, k))}</p>
  ${nx ? `<button class="btn pbig" data-st="${nx}"${k.confere ? "" : ` data-confirma="O valor não bate com os preços da loja. O certo seria ${k.conhecido ? brl(k.esperado) : "?"}. Marcar mesmo assim?"`}>${esc(BOTAO[nx])}</button>` : ""}
  <div class="pacts">${wa ? `<a class="btn wa" href="${wa}" target="_blank" rel="noopener">WhatsApp</a>` : ""}${mapa ? `<a class="btn ghost" href="${mapa}" target="_blank" rel="noopener">Mapa</a>` : ""}</div>
  <details class="pmais"><summary>Detalhes</summary>
    <div class="pbloco"><span class="lbl">Cliente</span>${esc(cli.nome)}${tel ? ` · ${esc(cli.telefone)}` : ""}<br>${onde}<br>Pagamento: ${esc(pagTxt)}<br>Pedido <span class="mono">${esc(o.txid)}</span>${o.origem === "whatsapp" ? " (lançado à mão)" : ""}</div>
    <div class="pbloco"><span class="lbl">Códigos para comprar na Real</span>${real.map(r => `<div class="pit"><span><b class="mono">${esc(r.sku)}</b> · ${r.q}x ${esc(r.nome)}${r.desconhecida ? ` <em class="err">não está no catálogo</em>` : ""}</span><button class="btn ghost sm" data-copia="${esc(r.sku)}">Copiar</button></div>`).join("")}</div>
    ${k.ref ? `<div class="pbloco"><span class="lbl">Indicação</span>Código <b>${esc(k.ref)}</b> · comissão a pagar ${brl(k.comissao)}</div>` : ""}
    ${nf ? `<div class="pbloco"><span class="lbl">Nota fiscal</span>CNPJ <b class="mono">${esc(cnpj)}</b> <button class="btn ghost sm" data-copia="${esc(so(nf.cnpj))}">Copiar</button><br>${esc(nf.razao)}<br>${esc(nf.email)}</div>` : ""}
    <div class="pbloco"><span class="lbl">Anotação</span><textarea data-obs maxlength="500" rows="2" placeholder="Ex.: troca combinada para sexta">${esc(o.obs)}</textarea><button class="btn ghost sm" data-salva-obs>Salvar anotação</button></div>
    <div class="pbloco"><span class="lbl">Mudar etapa à mão</span><select data-st-sel aria-label="Mudar etapa"><option value="">Escolha…</option>${Object.keys(ETAPAS).filter(x => x !== o.status).map(x => `<option value="${x}">${esc(ETAPAS[x])}</option>`).join("")}</select>
      <div class="note">${hist.map(h => `${esc(ETAPAS[h.s] || h.s)} · ${fmt(h.em)}`).join("<br>")}</div></div>
  </details>
</article>`;
}

function listaReal() {
  const abertos = VENDAS.filter(o => (o.status === "novo" || o.status === "pix_caiu") && !saiu(o));
  const soma = new Map();
  for (const o of abertos) for (const r of codigosReal(conferir(o).linhas)) {
    const x = soma.get(r.sku) || { ...r, q: 0 }; x.q += r.q; soma.set(r.sku, x);
  }
  const linhas = [...soma.values()];
  const texto = linhas.map(r => `${r.sku}  ${r.q}x  ${r.nome}`).join("\n");
  return { linhas, texto, n: abertos.length };
}

const GRUPOS = { fazer: ["novo", "pix_caiu", "saiu", "troca"], entregues: ["entregue"], cancelados: ["cancelado"] };
function desenhar() {
  const de = g => VENDAS.filter(o => GRUPOS[g].includes(o.status));
  const abas = [["fazer", `A fazer (${de("fazer").length})`], ["entregues", `Entregues (${de("entregues").length})`], ["cancelados", `Cancelados (${de("cancelados").length})`]];
  const b = busca.trim().toLowerCase();
  let vis = de(filtro).slice().reverse();  // a fazer: o mais antigo primeiro
  if (filtro !== "fazer") vis.reverse();
  if (b) vis = VENDAS.filter(o => [o.txid, o.cliente && o.cliente.nome, o.cliente && o.cliente.telefone, ...(o.itens || []).map(i => i && i.sku)].join(" ").toLowerCase().includes(b));
  const hoje = new Date().toDateString();
  const vendHoje = VENDAS.filter(o => o.criado && o.criado.toDate && o.criado.toDate().toDateString() === hoje && o.status !== "cancelado");
  const novos = VENDAS.filter(o => o.status === "novo").length;
  const R = listaReal();
  document.title = (novos ? `(${novos}) ` : "") + "Pedidos | Loja Dias";
  box.innerHTML = `
  <div class="presumo"><div><b>${novos}</b><span>novos</span></div><div><b>${vendHoje.length}</b><span>pedidos hoje</span></div><div><b>${brl(vendHoje.reduce((s, o) => s + (Number(o.total) || 0), 0))}</b><span>vendido hoje</span></div></div>
  ${som ? "" : `<button class="btn pbig ghost" id="psom">🔔 Tocar som quando chegar pedido</button>`}
  <div class="pabas">${abas.map(([k, t]) => `<button class="${k === filtro && !b ? "on" : ""}" data-aba="${k}">${esc(t)}</button>`).join("")}</div>
  <div id="plista">${vis.map(cartao).join("") || `<p class="pvazio">${b ? "Nada encontrado." : filtro === "fazer" ? "Nenhum pedido para fazer agora. 👍" : "Nenhum pedido aqui."}</p>`}</div>
  <details class="pmais pfim"><summary>Mais opções</summary>
    <input id="pbusca" type="search" placeholder="Buscar pelo nome, telefone ou código" value="${esc(busca)}">
    <button class="btn ghost" id="pnovo">+ Lançar pedido que veio pelo WhatsApp</button>
    ${R.linhas.length ? `<div class="pbloco"><span class="lbl">Lista para comprar na Real (pedidos ainda não enviados)</span>${R.linhas.map(r => `<div class="pit"><span><b class="mono">${esc(r.sku)}</b> · ${r.q}x ${esc(r.nome)}</span></div>`).join("")}<button class="btn ghost sm" id="pcopialista">Copiar a lista</button></div>` : ""}
    <a class="btn ghost" href="moderar.html">Avaliações de clientes</a>
    <p class="note">Você entrou como ${esc(auth.currentUser && auth.currentUser.email)}.</p>
    <button class="btn ghost" id="asair">Sair</button>
  </details>`;
  const bi = document.querySelector("#pbusca");
  if (busca) document.querySelector(".pfim").open = true;
  bi.oninput = () => { busca = bi.value; const pos = bi.selectionStart; desenhar(); const n = document.querySelector("#pbusca"); n.focus(); n.setSelectionRange(pos, pos); };
  document.querySelector("#asair").onclick = () => signOut(auth);
  const cl = document.querySelector("#pcopialista"); if (cl) cl.onclick = e => copiar(R.texto, e.target);
}

async function copiar(t, el) {
  try { await navigator.clipboard.writeText(t); el.textContent = "Copiado ✓"; } catch (e) { prompt("Copie:", t); }
  setTimeout(() => { el.textContent = el.id === "pcopialista" ? "Copiar a lista" : "Copiar"; }, 1500);
}

// ---------- mudar etapa ----------
async function mudar(id, st) {
  const o = VENDAS.find(v => v.txid === id); if (!o || !ETAPAS[st] || st === o.status) return;
  if (st === "pix_caiu" && !confirm("O Pix apareceu no app do banco da loja? (print do cliente não vale)")) return;
  if (st === "cancelado" && !confirm("Cancelar este pedido?")) return;
  const hist = (Array.isArray(o.historico) ? o.historico : []).concat([{ s: st, em: new Date() }]).slice(-40);
  const b = writeBatch(db), up = { status: st, historico: hist, atualizado: serverTimestamp() };
  // 6º pedido com frete grátis: conta 1 pedido pago no cliente com conta, só na primeira vez que o Pix cai
  if (st === "pix_caiu" && !o.pago_em) {
    up.pago_em = serverTimestamp();
    if (o.uid && typeof o.uid === "string") {
      try { if ((await getDoc(doc(db, "clientes", o.uid))).exists()) b.update(doc(db, "clientes", o.uid), { pedidos_pagos: increment(1) }); } catch (e) {}
    }
  }
  b.update(doc(db, "vendas", id), up);
  try { await b.commit(); } catch (e) { alert("Não salvou. Confira a internet e tente de novo."); }
}

box.addEventListener("click", async e => {
  const a = e.target.closest("[data-aba]"); if (a) { filtro = a.dataset.aba; return desenhar(); }
  const c = e.target.closest("[data-copia]"); if (c) return copiar(c.dataset.copia, c);
  const card = e.target.closest(".pcard");
  const s = e.target.closest("[data-st]"); if (s && card) { if (s.dataset.confirma && !confirm(s.dataset.confirma)) return; s.disabled = true; return mudar(card.dataset.id, s.dataset.st); }
  const ob = e.target.closest("[data-salva-obs]");
  if (ob && card) { ob.textContent = "Salvando…";
    try { await setDoc(doc(db, "vendas", card.dataset.id), { obs: card.querySelector("[data-obs]").value.slice(0, 500), atualizado: serverTimestamp() }, { merge: true }); }
    catch (err) { alert("Não salvou."); } return; }
  if (e.target.closest("#psom")) return ligarAviso();
  if (e.target.id === "pnovo") return formManual();
});
box.addEventListener("change", e => { const s = e.target.closest("[data-st-sel]"); const card = e.target.closest(".pcard"); if (s && card && s.value) mudar(card.dataset.id, s.value); });

// ---------- aviso de pedido novo (com o painel aberto) ----------
function ligarAviso() {
  som = true;
  try { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); actx.resume(); } catch (e) {}
  if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
  apito(); desenhar();
}
function apito() {
  if (!actx) return;
  [0, .25, .5].forEach(t => { const o = actx.createOscillator(), g = actx.createGain(); o.frequency.value = 880; o.connect(g); g.connect(actx.destination);
    g.gain.setValueAtTime(.25, actx.currentTime + t); g.gain.exponentialRampToValueAtTime(.001, actx.currentTime + t + .2); o.start(actx.currentTime + t); o.stop(actx.currentTime + t + .21); });
}
function avisar(o) {
  if (som) apito();
  if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
  if ("Notification" in window && Notification.permission === "granted") {
    try { new Notification("Pedido novo na Loja Dias", { body: `${String((o.cliente && o.cliente.nome) || "").slice(0, 40)} · ${brl(o.total)}`, tag: String(o.txid) }); } catch (e) {}
  }
}

// ---------- pedido que chegou só pelo WhatsApp ----------
function formManual() {
  const cid = CID.map(c => `<option value="${esc(c.slug)}">${esc(c.nome)}</option>`).join("");
  const f = document.createElement("div"); f.className = "pmodal";
  f.innerHTML = `<div class="panel"><h2>Pedido do WhatsApp</h2>
    <label class="lbl">Nome</label><input id="mnome" maxlength="80">
    <label class="lbl">WhatsApp</label><input id="mtel" type="tel" maxlength="20">
    <label class="lbl">Cidade</label><select id="mcid"><option value="retirada">Retirada na loja</option>${cid}</select>
    <label class="lbl">Endereço</label><input id="mend" maxlength="200">
    <label class="lbl">Pagamento</label><select id="mpag"><option value="pix">Pix antes</option>${ENT_OK ? `<option value="entrega">Pix na entrega</option>` : ""}</select>
    <label class="lbl">Peças: um código por linha, com a quantidade (ex.: CPR8EA9 2)</label><textarea id="mitens" rows="4"></textarea>
    <p class="err" id="merr" hidden></p><div class="note" id="mtot"></div>
    <div class="pbar"><button class="btn" id="mok">Salvar pedido</button><button class="btn ghost" id="mx">Fechar</button></div></div>`;
  document.body.appendChild(f);
  const $m = s => f.querySelector(s);
  const ler = () => {
    const itens = [], faltam = [];
    for (const l of $m("#mitens").value.split("\n")) {
      const [sku, q] = l.trim().split(/\s+/); if (!sku) continue;
      const p = PROD.get(sku) || PROD.get(sku.toUpperCase());
      if (!p) { faltam.push(sku); continue; }
      itens.push({ sku: p.sku, nome: p.nome, qtd: Math.max(1, Math.min(99, parseInt(q) || 1)), preco: p.preco });
    }
    const sub = itens.reduce((s, i) => s + i.preco * i.qtd, 0), c = CID.find(x => x.slug === $m("#mcid").value);
    const frete = !c ? 0 : (sub >= (c.gratis_acima || Infinity) ? 0 : c.normal);
    return { itens, faltam, sub, frete, total: Math.round((sub + frete) * 100) / 100 };
  };
  f.addEventListener("input", () => { const r = ler(); $m("#mtot").textContent = `Peças ${brl(r.sub)} + frete ${brl(r.frete)} = ${brl(r.total)}${r.faltam.length ? " · não achei: " + r.faltam.join(", ") : ""}`; });
  $m("#mx").onclick = () => f.remove();
  $m("#mok").onclick = async () => {
    const r = ler(), err = !$m("#mnome").value.trim() ? "Falta o nome." : !r.itens.length ? "Falta pelo menos uma peça com código certo." : r.faltam.length ? "Tem código que não achei: " + r.faltam.join(", ") : "";
    $m("#merr").hidden = !err; $m("#merr").textContent = err; if (err) return;
    const txid = "LD" + Date.now().toString(36).toUpperCase().slice(-8) + "WA0", ret = $m("#mcid").value === "retirada";
    try {
      await setDoc(doc(db, "vendas", txid), { txid, criado: serverTimestamp(), status: "novo", origem: "whatsapp", entrega: ret ? "retirada" : "motoboy",
        pagamento: $m("#mpag").value === "entrega" ? "entrega" : "pix",
        cliente: { nome: $m("#mnome").value.trim().slice(0, 80), telefone: $m("#mtel").value.trim().slice(0, 20), endereco: ret ? "" : $m("#mend").value.trim().slice(0, 200), cidade: $m("#mcid").value },
        itens: r.itens.slice(0, 30), sub: Math.round(r.sub * 100) / 100, frete: r.frete, desconto: 0, total: r.total });
      f.remove();
    } catch (e) { $m("#merr").hidden = false; $m("#merr").textContent = "Não salvou. Tente de novo."; }
  };
}

// ---------- entrar e ouvir os pedidos ao vivo ----------
// Login: janela do Google (popup). Se o celular bloquear a janela, tenta pela página inteira (redirect).
// Navegador de dentro de app (WhatsApp, Instagram, Facebook) o Google recusa: pede para abrir no Chrome.
const dentroDeApp = /; wv\)|FBAN|FBAV|Instagram|Line\/|WhatsApp|GSA\//i.test(navigator.userAgent);
const prov = () => { const p = new GoogleAuthProvider(); p.setCustomParameters({ prompt: "select_account" }); return p; };
const MSG = {
  "auth/popup-closed-by-user": "A janela do Google fechou antes de terminar. Toque de novo em Entrar.",
  "auth/cancelled-popup-request": "Toque só uma vez em Entrar e espere a janela do Google.",
  "auth/network-request-failed": "Sem internet. Confira a conexão e tente de novo.",
  "auth/unauthorized-domain": "Este endereço não está liberado no login. Abra por lojadias.com.br/admin.html.",
  "auth/web-storage-unsupported": "Este navegador bloqueia o login. Abra no Chrome.",
  "auth/operation-not-supported-in-this-environment": "Este navegador bloqueia o login. Abra no Chrome."
};
function telaEntrar(erro) {
  const link = location.href.split("#")[0];
  box.innerHTML = `<div class="plogin">
    <h2>Entrar no painel</h2>
    <p>Use a <b>conta Google da loja</b>. Outras contas não abrem os pedidos.</p>
    ${dentroDeApp ? `<p class="palerta">Você abriu o link dentro de outro app. O Google não deixa entrar por aqui. Abra no Chrome:</p>
      <a class="btn pbig" href="intent://${esc(link.replace(/^https?:\/\//, ""))}#Intent;scheme=https;package=com.android.chrome;end">Abrir no Chrome</a>
      <button class="btn ghost pbig" id="acopia">Copiar o link</button>` : ""}
    <button class="btn pbig" id="alogin">Entrar com Google</button>
    ${erro ? `<p class="palerta">${esc(erro)}</p>` : ""}
    <p class="note">Dica: depois de entrar, salve esta página na tela inicial do celular (Chrome › ⋮ › Adicionar à tela inicial). Você continua conectado.</p></div>`;
  const c = document.querySelector("#acopia"); if (c) c.onclick = () => copiar(link, c);
  document.querySelector("#alogin").onclick = async e => {
    e.target.disabled = true; e.target.textContent = "Abrindo o Google…";
    try { await signInWithPopup(auth, prov()); }
    catch (err) {
      if (err && err.code === "auth/popup-blocked") { try { return await signInWithRedirect(auth, prov()); } catch (e2) { err = e2; } }
      telaEntrar(MSG[err && err.code] || `Não deu para entrar (${String(err && err.code || "erro").replace("auth/", "")}). Tente de novo ou mande um print para o Claude.`);
    }
  };
}
function telaSemAcesso(u) {
  box.innerHTML = `<div class="plogin"><h2>Essa conta não é da loja</h2>
    <p>Você entrou com <b>${esc(u && u.email)}</b>. Os pedidos só abrem com a conta Google da loja.</p>
    <button class="btn pbig" id="atroca">Entrar com outra conta</button></div>`;
  document.querySelector("#atroca").onclick = async () => { await signOut(auth); telaEntrar(); document.querySelector("#alogin").click(); };
}
getRedirectResult(auth).catch(err => telaEntrar(MSG[err && err.code] || "Não deu para entrar. Tente de novo."));

onAuthStateChanged(auth, u => {
  if (parar) { parar(); parar = null; }
  if (!u) return telaEntrar();
  box.innerHTML = `<p class="note">Carregando pedidos…</p>`;
  primeira = true; vistos = new Set();
  parar = onSnapshot(query(collection(db, "vendas"), orderBy("criado", "desc"), limit(300)), snap => {
    VENDAS = snap.docs.map(d => ({ ...d.data(), txid: d.id }));
    for (const ch of snap.docChanges()) {
      if (ch.type === "added" && !primeira && !vistos.has(ch.doc.id) && ch.doc.data().status === "novo" && ch.doc.data().origem !== "whatsapp") avisar(ch.doc.data());
      vistos.add(ch.doc.id);
    }
    primeira = false;
    // não redesenha enquanto o Luan escreve uma anotação ou busca
    const ativo = document.activeElement;
    if (ativo && ativo.matches && ativo.matches("[data-obs]")) return;
    desenhar();
  }, err => (err && err.code === "permission-denied") ? telaSemAcesso(u) : (box.innerHTML = `<p class="palerta">Não deu para carregar os pedidos. Confira a internet e recarregue a página.</p>`));
});
