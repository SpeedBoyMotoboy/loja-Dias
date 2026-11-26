// Loja Dias: painel de pedidos (só o Luan). Lê vendas/{txid}, que o carrinho grava com ou sem login.
// Quem pode abrir: e-mails da loja nas regras do Firestore (função loja()).
// Tudo que veio do celular do cliente é NÃO confiável: todo texto passa por esc() e o total é recalculado pelo catálogo.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, connectAuthEmulator, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
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
// próximo passo mais comum: Pix agora = novo > Pix caiu > saiu > entregue; Pix na entrega = novo > saiu > Pix caiu > entregue
const proximo = o => o.pagamento === "entrega"
  ? ({ novo: "saiu", saiu: "pix_caiu", pix_caiu: "entregue" })[o.status]
  : ({ novo: "pix_caiu", pix_caiu: "saiu", saiu: "entregue" })[o.status];

let VENDAS = [], filtro = "abertos", busca = "", primeira = true, som = false, actx = null, vistos = new Set(), parar = null;

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
  const freteCat = o.entrega === "retirada" || !cid ? 0 : (sub >= (cid.gratis_acima || C.frete_gratis_acima || Infinity) ? 0 : cid.normal);
  const sem = Math.round((sub - descPix - descInd) * 100) / 100, com = Math.round((sem + freteCat) * 100) / 100;
  // o 6º pedido (fidelidade) pode vir sem frete: só aceita "sem frete" se o cliente tinha conta
  const aceitos = o.uid ? [com, sem] : [com];
  const confere = conhecido && aceitos.some(v => Math.abs(v - Number(o.total)) < 0.011);
  return { linhas, sub, freteCat, esperado: com, confere, conhecido, ref, descInd, comissao };
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
  const mapa = cli.endereco ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(cli.endereco + ", " + ((CID.find(c => c.slug === cli.cidade) || {}).nome || "") + ", ES")}` : "";
  const cidadeNome = o.entrega === "retirada" ? "Retirada na loja" : esc((CID.find(c => c.slug === cli.cidade) || {}).nome || cli.cidade || "");
  const nx = proximo(o);
  const hist = Array.isArray(o.historico) ? o.historico.filter(h => h && typeof h === "object") : [];
  const nf = o.nf && typeof o.nf === "object" ? o.nf : null;
  const cnpj = nf ? so(nf.cnpj).replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5") : "";
  return `<article class="pcard" data-id="${esc(o.txid)}">
  <div class="ptop">${chip(o.status)} <b class="mono">${esc(o.txid)}</b> <span class="note">${fmt(o.criado)}${o.origem === "whatsapp" ? " · lançado à mão" : ""}</span></div>
  <div class="pcli"><b>${esc(cli.nome) || "(sem nome)"}</b>${tel ? ` · ${esc(cli.telefone)}` : ""}
    <div class="pacts">${wa ? `<a class="btn wa sm" href="${wa}" target="_blank" rel="noopener">WhatsApp</a><a class="btn ghost sm" href="tel:${tel}">Ligar</a>` : ""}${mapa ? `<a class="btn ghost sm" href="${mapa}" target="_blank" rel="noopener">Mapa</a>` : ""}</div>
    <div>${o.entrega === "retirada" ? "" : esc(cli.endereco) + " · "}${cidadeNome}</div>
    <div>Pagamento: <b>${o.pagamento === "entrega" ? "Pix na entrega" : "Pix antes"}</b></div></div>
  <div class="pitens">${k.linhas.map(({ i, p, q }) => `<div class="pit"><span>${q}x ${esc(p ? p.nome : i.nome)}</span><b>${p ? brl(p.preco * q) : "?"}</b></div>`).join("")}
    <div class="preal"><span class="lbl">Comprar na Real</span>${real.map(r => `<div class="pit"><span><b class="mono">${esc(r.sku)}</b> · ${r.q}x ${esc(r.nome)}${r.desconhecida ? ` <em class="err">não está no catálogo</em>` : ""}</span><button class="btn ghost sm" data-copia="${esc(r.sku)}">Copiar</button></div>`).join("")}</div></div>
  <div class="ptot">Total <b>${brl(o.total)}</b>${k.confere ? ` <span class="stock">confere ✓</span>` : ` <span class="err">não bate com a loja (esperado ${k.conhecido ? brl(k.esperado) : "peça desconhecida"}). Confira antes.</span>`}</div>
  ${k.ref ? `<div class="note">Indicado por <b>${esc(k.ref)}</b> ${k.descInd ? `· desconto ${brl(k.descInd)} ` : ""}· comissão a pagar ${brl(k.comissao)}</div>` : ""}
  ${nf ? `<div class="pnf"><span class="lbl">Nota fiscal pedida</span>CNPJ <b class="mono">${esc(cnpj)}</b> <button class="btn ghost sm" data-copia="${esc(so(nf.cnpj))}">Copiar</button><br>${esc(nf.razao)}<br>${esc(nf.email)}</div>` : ""}
  <div class="petapas">${nx ? `<button class="btn" data-st="${nx}">${esc(ETAPAS[nx])}</button>` : ""}
    <select data-st-sel aria-label="Mudar etapa"><option value="">Outra etapa…</option>${Object.keys(ETAPAS).filter(s => s !== o.status).map(s => `<option value="${s}">${esc(ETAPAS[s])}</option>`).join("")}</select></div>
  <details class="pmais"><summary>Anotação e histórico</summary>
    <textarea data-obs maxlength="500" rows="2" placeholder="Ex.: troca combinada para sexta">${esc(o.obs)}</textarea><button class="btn ghost sm" data-salva-obs>Salvar anotação</button>
    <div class="note">${hist.map(h => `${esc(ETAPAS[h.s] || h.s)} · ${fmt(h.em)}`).join("<br>") || "Sem mudanças ainda."}</div></details>
</article>`;
}

function listaReal() {
  const abertos = VENDAS.filter(o => o.status === "novo" || o.status === "pix_caiu");
  const soma = new Map();
  for (const o of abertos) for (const r of codigosReal(conferir(o).linhas)) {
    const x = soma.get(r.sku) || { ...r, q: 0 }; x.q += r.q; soma.set(r.sku, x);
  }
  const linhas = [...soma.values()];
  const texto = linhas.map(r => `${r.sku}  ${r.q}x  ${r.nome}`).join("\n");
  return { linhas, texto, n: abertos.length };
}

function desenhar() {
  const cont = s => VENDAS.filter(o => o.status === s).length;
  const abertos = VENDAS.filter(o => !["entregue", "cancelado"].includes(o.status));
  const abas = [["abertos", `Em aberto (${abertos.length})`], ...Object.keys(ETAPAS).map(s => [s, `${ETAPAS[s]} (${cont(s)})`]), ["todos", `Todos (${VENDAS.length})`]];
  const b = busca.trim().toLowerCase();
  let vis = filtro === "todos" ? VENDAS : filtro === "abertos" ? abertos : VENDAS.filter(o => o.status === filtro);
  if (b) vis = vis.filter(o => [o.txid, o.cliente && o.cliente.nome, o.cliente && o.cliente.telefone, ...(o.itens || []).map(i => i && i.sku)].join(" ").toLowerCase().includes(b));
  const hoje = new Date().toDateString();
  const vendHoje = VENDAS.filter(o => o.criado && o.criado.toDate && o.criado.toDate().toDateString() === hoje && o.status !== "cancelado");
  const R = listaReal();
  document.title = (cont("novo") ? `(${cont("novo")}) ` : "") + "Pedidos | Loja Dias";
  box.innerHTML = `
  <div class="pbar"><button class="btn ${som ? "ghost" : ""}" id="psom">${som ? "Aviso ligado ✓" : "Ligar aviso de pedido novo"}</button>
    <button class="btn ghost" id="pnovo">+ Pedido do WhatsApp</button><a class="btn ghost" href="moderar.html">Avaliações</a></div>
  <div class="presumo"><div><b>${vendHoje.length}</b><span>pedidos hoje</span></div><div><b>${brl(vendHoje.reduce((s, o) => s + (Number(o.total) || 0), 0))}</b><span>vendido hoje</span></div><div><b>${cont("novo")}</b><span>novos</span></div></div>
  ${R.linhas.length ? `<details class="pcompra"><summary><b>Lista para comprar na Real</b> (${R.linhas.length} códigos, ${R.n} pedidos novos ou com Pix caiu)</summary>
    ${R.linhas.map(r => `<div class="pit"><span><b class="mono">${esc(r.sku)}</b> · ${r.q}x ${esc(r.nome)}</span></div>`).join("")}
    <button class="btn ghost sm" id="pcopialista">Copiar a lista</button></details>` : ""}
  <div class="pabas">${abas.map(([k, t]) => `<button class="${k === filtro ? "on" : ""}" data-aba="${k}">${esc(t)}</button>`).join("")}</div>
  <input id="pbusca" type="search" placeholder="Buscar nome, telefone, código" value="${esc(busca)}">
  <div id="plista">${vis.map(cartao).join("") || `<p class="note">Nenhum pedido aqui.</p>`}</div>
  <p class="note">Mostra os 300 pedidos mais novos. Pedido que o cliente mandou direto pelo WhatsApp (sem o carrinho do site) não entra sozinho: use "+ Pedido do WhatsApp".</p>
  <button class="btn ghost" id="asair">Sair</button>`;
  const bi = document.querySelector("#pbusca");
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
  if (st === "pix_caiu" && !confirm("Confirmar que o Pix CAIU na conta da loja? (print não vale)")) return;
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
  const s = e.target.closest("[data-st]"); if (s && card) { s.disabled = true; return mudar(card.dataset.id, s.dataset.st); }
  const ob = e.target.closest("[data-salva-obs]");
  if (ob && card) { ob.textContent = "Salvando…";
    try { await setDoc(doc(db, "vendas", card.dataset.id), { obs: card.querySelector("[data-obs]").value.slice(0, 500), atualizado: serverTimestamp() }, { merge: true }); }
    catch (err) { alert("Não salvou."); } return; }
  if (e.target.id === "psom") return ligarAviso();
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
    <label class="lbl">Pagamento</label><select id="mpag"><option value="pix">Pix antes</option><option value="entrega">Pix na entrega</option></select>
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
onAuthStateChanged(auth, u => {
  if (parar) { parar(); parar = null; }
  if (!u) {
    box.innerHTML = `<p>Painel da loja. Entre com a conta Google da Loja Dias.</p><button class="btn" id="alogin">Entrar com Google</button>`;
    document.querySelector("#alogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider());
    return;
  }
  box.innerHTML = `<p class="note">Carregando pedidos…</p>`;
  primeira = true; vistos = new Set();
  parar = onSnapshot(query(collection(db, "vendas"), orderBy("criado", "desc"), limit(300)), snap => {
    VENDAS = snap.docs.map(d => ({ ...d.data(), txid: d.id }));
    for (const ch of snap.docChanges()) {
      if (ch.type === "added" && !primeira && !vistos.has(ch.doc.id) && ch.doc.data().status === "novo" && ch.doc.data().origem !== "whatsapp") avisar(ch.doc.data());
      vistos.add(ch.doc.id);
    }
    primeira = false;
    // não redesenha enquanto o Luan escreve uma anotação
    const ativo = document.activeElement;
    if (ativo && ativo.matches && ativo.matches("[data-obs]")) return;
    desenhar();
  }, () => {
    box.innerHTML = `<p class="err">Sem acesso. Entre com a conta Google da loja.</p><button class="btn ghost" id="asair">Sair</button>`;
    document.querySelector("#asair").onclick = () => signOut(auth);
  });
});
