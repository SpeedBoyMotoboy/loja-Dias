// Loja Dias: tela só do Luan para marcar "Pix recebido". Quem pode: e-mails da loja nas regras do Firestore.
// Marcar como pago soma 1 em clientes/{uid}.pedidos_pagos (conta o 6º pedido com frete grátis).
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, collectionGroup, query, orderBy, limit, getDocs, doc, writeBatch, increment, serverTimestamp, getDoc } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const app = initializeApp(C.firebase);
const auth = getAuth(app), db = getFirestore(app);
const box = document.querySelector("#admin");
const brl = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const esc = s => String(s ?? "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));

async function listar() {
  box.innerHTML = `<p class="note">Carregando pedidos…</p>`;
  let qs;
  try { qs = await getDocs(query(collectionGroup(db, "pedidos"), orderBy("criado", "desc"), limit(60))); }
  catch (e) { box.innerHTML = `<p class="err">Sem acesso. Entre com a conta Google da loja.</p><button class="btn ghost" id="asair">Sair</button>`; document.querySelector("#asair").onclick = () => signOut(auth); return; }
  const linhas = [];
  for (const d of qs.docs) {
    const o = d.data(), uid = d.ref.parent.parent.id;
    let cli = {};
    try { cli = (await getDoc(doc(db, "clientes", uid))).data() || {}; } catch (e) {}
    const dt = o.criado ? o.criado.toDate().toLocaleString("pt-BR") : "";
    const it = (o.itens || []).map(i => `${i.qtd}x ${esc(i.nome)}`).join(", ");
    const pago = o.status === "pago";
    linhas.push(`<div class="panel" style="margin-bottom:10px"><b>${esc(o.txid)}</b> · ${dt} · <b>${brl(o.total || 0)}</b><br>
      ${esc(cli.nome)} · ${esc(cli.telefone)} · ${esc(o.cidade)}<br><span class="note">${it}</span><br>
      ${pago ? `<span class="stock">Pago ✓</span>` : `<button class="btn" data-pago="${d.ref.path}" data-uid="${uid}">Pix recebido</button>`}
      <span class="note"> Pedidos pagos do cliente: ${cli.pedidos_pagos || 0}</span></div>`);
  }
  box.innerHTML = (linhas.join("") || "<p>Nenhum pedido ainda.</p>") + `<button class="btn ghost" id="asair">Sair</button>`;
  document.querySelector("#asair").onclick = () => signOut(auth);
}

box.addEventListener("click", async e => {
  const b = e.target.closest("[data-pago]"); if (!b) return;
  if (!confirm("Confirmar que o Pix deste pedido caiu na conta?")) return;
  b.disabled = true; b.textContent = "Salvando…";
  const batch = writeBatch(db);
  batch.update(doc(db, b.dataset.pago), { status: "pago", pago_em: serverTimestamp() });
  batch.update(doc(db, "clientes", b.dataset.uid), { pedidos_pagos: increment(1) });
  try { await batch.commit(); listar(); } catch (err) { b.disabled = false; b.textContent = "Erro. Tente de novo"; }
});

onAuthStateChanged(auth, u => {
  if (u) return listar();
  box.innerHTML = `<p>Tela da loja. Entre com a conta Google da Loja Dias.</p><button class="btn" id="alogin">Entrar com Google</button>`;
  document.querySelector("#alogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider());
});
