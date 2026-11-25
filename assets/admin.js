// Loja Dias: tela só do Luan para marcar "Pix recebido". Quem pode: e-mails da loja nas regras do Firestore.
// Marcar como pago soma 1 em clientes/{uid}.pedidos_pagos (conta o 6º pedido com frete grátis).
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, collectionGroup, query, orderBy, limit, getDocs, doc, writeBatch, increment, serverTimestamp, getDoc } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const app = initializeApp(C.firebase);
if (C.appcheck) initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(C.appcheck), isTokenAutoRefreshEnabled: true });
const auth = getAuth(app), db = getFirestore(app);
const box = document.querySelector("#admin");
const brl = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const esc = s => String(s ?? "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));

let CAMINHOS = [];
async function listar() {
  box.innerHTML = `<p class="note">Carregando pedidos…</p>`;
  let qs;
  try { qs = await getDocs(query(collectionGroup(db, "pedidos"), orderBy("criado", "desc"), limit(60))); }
  catch (e) { box.innerHTML = `<p class="err">Sem acesso. Entre com a conta Google da loja.</p><button class="btn ghost" id="asair">Sair</button>`; document.querySelector("#asair").onclick = () => signOut(auth); return; }
  const linhas = [], caminhos = [], comissoes = {};
  const IND = C.ind, okRef = r => typeof r === "string" && /^[A-Z0-9]{3,12}$/.test(r);
  const P = window.LOJA.produtos, CID = C.cidades || [];
  for (const d of qs.docs) {
    const o = d.data(), uid = d.ref.parent.parent.id;
    const itens = Array.isArray(o.itens) ? o.itens.filter(i => i && typeof i === "object") : [];
    let cli = {};
    try { cli = (await getDoc(doc(db, "clientes", uid))).data() || {}; } catch (e) {}
    const dt = o.criado ? o.criado.toDate().toLocaleString("pt-BR") : "";
    const it = itens.map(i => `${Number(i.qtd) | 0}x ${esc(i.nome)}`).join(", ");
    // auditoria 25/11: o total vem do celular do cliente; confere com o preço da loja + frete da cidade
    const sub = itens.reduce((s, i) => { const p = P.find(x => x.sku === i.sku); return s + (p ? p.preco * (Number(i.qtd) | 0) : NaN); }, 0);
    const cid = CID.find(c => c.slug === o.cidade);
    const frete = cid ? (sub >= (cid.gratis_acima || C.frete_gratis_acima || Infinity) ? 0 : cid.normal) : 0;
    // indicação: desconto e comissão recalculados pelo catálogo (o código vem do celular do cliente: só letras e números)
    const ref = okRef(o.ref) ? o.ref : "";
    const baseInd = ref && IND ? itens.reduce((s, i) => { const p = P.find(x => x.sku === i.sku); return s + (p && p.ind ? p.preco * (Number(i.qtd) | 0) : 0); }, 0) : 0;
    const descInd = Math.round(baseInd * (IND ? IND.desconto : 0) * 100) / 100, comissao = Math.round(baseInd * (IND ? IND.comissao : 0) * 100) / 100;
    if (ref && o.status === "pago") comissoes[ref] = (comissoes[ref] || 0) + comissao;
    const semFreteOk = o.cidade === "retirada" || (Number(cli.pedidos_pagos) | 0) % 6 === 5;
    const confere = Number.isFinite(sub) && (semFreteOk ? [sub, sub + frete] : [sub + frete]).some(v => Math.abs(v - descInd - Number(o.total)) < 0.011);
    caminhos.push({ path: d.ref.path, uid });
    const pago = o.status === "pago";
    linhas.push(`<div class="panel" style="margin-bottom:10px"><b>${esc(o.txid)}</b> · ${dt} · <b>${brl(Number(o.total) || 0)}</b><br>
      ${esc(cli.nome)} · ${esc(cli.telefone)} · ${esc(o.cidade)}<br><span class="note">${it}</span><br>
      ${ref ? `<span class="note">Indicado por <b>${esc(ref)}</b> · desconto ${brl(descInd)} · comissão a pagar ${brl(comissao)}</span><br>` : ""}
      ${confere ? "" : `<p class="err">Atenção: total não bate com os preços da loja (esperado ${Number.isFinite(sub) ? brl(sub - descInd + frete) : "peça desconhecida"}). Confira antes de marcar.</p>`}
      ${pago ? `<span class="stock">Pago ✓</span>` : `<button class="btn" data-i="${caminhos.length - 1}">Pix recebido</button>`}
      <span class="note"> Pedidos pagos do cliente: ${Number(cli.pedidos_pagos) | 0}</span></div>`);
  }
  CAMINHOS = caminhos;
  const resumo = Object.keys(comissoes).length ? `<div class="panel" style="margin-bottom:14px"><b>Comissões dos pedidos pagos (últimos 60 pedidos)</b><br>`
    + Object.entries(comissoes).sort((a, b) => b[1] - a[1]).map(([r, v]) => `${esc(r)}: ${brl(v)}`).join("<br>")
    + `<br><span class="note">Só conta pedido de cliente com conta no site. Pedido só pelo WhatsApp: a comissão é o mesmo valor do "desconto" escrito na mensagem.</span></div>` : "";
  box.innerHTML = resumo + (linhas.join("") || "<p>Nenhum pedido ainda.</p>") + `<button class="btn ghost" id="asair">Sair</button>`;
  document.querySelector("#asair").onclick = () => signOut(auth);
}

box.addEventListener("click", async e => {
  const b = e.target.closest("[data-i]"); if (!b) return;
  const alvo = CAMINHOS[Number(b.dataset.i)]; if (!alvo) return;
  if (!confirm("Confirmar que o Pix deste pedido caiu na conta?")) return;
  b.disabled = true; b.textContent = "Salvando…";
  const batch = writeBatch(db);
  batch.update(doc(db, alvo.path), { status: "pago", pago_em: serverTimestamp() });
  batch.update(doc(db, "clientes", alvo.uid), { pedidos_pagos: increment(1) });
  try { await batch.commit(); listar(); } catch (err) { b.disabled = false; b.textContent = "Erro. Tente de novo"; }
});

onAuthStateChanged(auth, u => {
  if (u) return listar();
  box.innerHTML = `<p>Tela da loja. Entre com a conta Google da Loja Dias.</p><button class="btn" id="alogin">Entrar com Google</button>`;
  document.querySelector("#alogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider());
});
