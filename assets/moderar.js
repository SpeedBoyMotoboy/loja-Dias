// Loja Dias: tela só da loja para aprovar ou recusar avaliações antes de aparecerem no site.
// Quem pode: e-mails da loja nas regras do Firestore. Tudo aqui foi escrito por cliente: sempre esc().
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, collection, query, where, limit, getDocs, getDoc, doc, updateDoc, deleteDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const app = initializeApp(C.firebase);
if (C.appcheck) initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(C.appcheck), isTokenAutoRefreshEnabled: true });
const auth = getAuth(app), db = getFirestore(app);
const box = document.querySelector("#moderar");
const esc = s => String(s ?? "").replace(/[<>&"']/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c]));
const okImg = s => typeof s === "string" && /^data:image\/(webp|jpeg);base64,[A-Za-z0-9+/=]+$/.test(s);
const P = window.LOJA.produtos || [];
let ABA = "pendente", LISTA = [];

async function compraConfirmada(a) {  // pedido do site, com esta peça, que a loja já marcou como pago
  if (typeof a.pedido !== "string" || !/^[A-Za-z0-9]{20}$/.test(a.pedido)) return "sem";
  try {
    const o = (await getDoc(doc(db, "clientes", a.uid, "pedidos", a.pedido))).data();
    if (!o || !(o.itens || []).some(i => i && i.sku === a.sku)) return "sem";
    return o.status === "pago" ? "pago" : "aberto";
  } catch (e) { return "sem"; }
}

async function listar() {
  box.innerHTML = `<p class="note">Carregando…</p>`;
  let qs;
  try { qs = await getDocs(query(collection(db, "avaliacoes"), where("status", "==", ABA), limit(50))); }
  catch (e) { box.innerHTML = `<p class="err">Sem acesso. Entre com a conta Google da loja.</p><button class="btn ghost" id="msair">Sair</button>`; document.querySelector("#msair").onclick = () => signOut(auth); return; }
  LISTA = qs.docs.map(d => ({ id: d.id, ...d.data() })).sort((a, b) => (b.criado?.seconds || 0) - (a.criado?.seconds || 0));
  const abas = [["pendente", "Para conferir"], ["aprovada", "Aprovadas"], ["recusada", "Recusadas"]]
    .map(([k, t]) => `<button class="btn ${k === ABA ? "" : "ghost"}" data-aba="${k}">${t}</button>`).join(" ");
  const linhas = [];
  for (const [i, a] of LISTA.entries()) {
    const p = P.find(x => x.sku === a.sku);
    const compra = await compraConfirmada(a);
    const n = Math.min(5, Math.max(1, Number(a.estrelas) | 0));
    const dt = a.criado?.toDate ? a.criado.toDate().toLocaleString("pt-BR") : "";
    const minis = (Array.isArray(a.fotos) ? a.fotos : []).filter(okImg).map((f, k) => `<button type="button" class="avthumb" data-foto="${i}:${k}"><img src="${f}" alt=""></button>`).join("");
    linhas.push(`<div class="panel" style="margin-bottom:12px">
      <b>${"★".repeat(n)}${"☆".repeat(5 - n)}</b> · <b>${esc(a.nome)}</b> · <span class="note">${dt}</span><br>
      Peça: ${p ? `<a href="${esc(p.url)}" target="_blank">${esc(p.nome)}</a>` : `<span class="err">código ${esc(a.sku)} não está no catálogo</span>`}<br>
      ${compra === "pago" ? '<span class="stock">Comprou pelo site e o Pix foi confirmado ✓</span>' : compra === "aberto" ? '<span class="note">Pedido pelo site com esta peça, Pix ainda não marcado</span>' : '<span class="note">Sem pedido pelo site com esta peça (confira no WhatsApp)</span>'}<br>
      <p style="white-space:pre-wrap">${esc(a.texto)}</p>
      ${minis ? `<div class="avfotos">${minis}</div>` : ""}${a.video === true ? '<p class="note">Tem vídeo (abre na página da peça depois de aprovar).</p>' : ""}
      <p class="note">${a.uso_fotos === true ? "<b>Autorizou usar as fotos no site e nas redes.</b>" : "Não autorizou usar as fotos fora da avaliação."}</p>
      <div id="mfotos-${i}"></div>
      ${ABA !== "aprovada" ? `<label class="opt"><input type="checkbox" id="mver-${i}" ${compra === "pago" ? "checked" : ""}><span>Marcar como compra confirmada<small>Só se você conferiu que a pessoa comprou esta peça.</small></span></label>` : ""}
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${ABA !== "aprovada" ? `<button class="btn" data-ok="${i}">Aprovar</button>` : ""}
        ${ABA !== "recusada" ? `<button class="btn ghost" data-nao="${i}">${ABA === "aprovada" ? "Tirar do site" : "Recusar"}</button>` : ""}
        <button class="btn ghost" data-apagar="${i}">Apagar de vez</button></div></div>`);
  }
  box.innerHTML = `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">${abas}</div>
    <p class="note">Recuse propaganda, link, palavrão, foto que não é da peça e dado pessoal (telefone, placa, rosto de terceiro).</p>
    ${linhas.join("") || "<p>Nada aqui.</p>"}<button class="btn ghost" id="msair">Sair</button>`;
  document.querySelector("#msair").onclick = () => signOut(auth);
}

box.addEventListener("click", async e => {
  const t = e.target.closest("button"); if (!t) return;
  if (t.dataset.aba) { ABA = t.dataset.aba; return listar(); }
  if (t.dataset.foto) {  // foto grande, com botão para baixar (para usar no site só se o cliente autorizou)
    const [i, k] = t.dataset.foto.split(":").map(Number), a = LISTA[i];
    const f = (await getDoc(doc(db, "avaliacoes", a.id, "fotos", String(k))).catch(() => null))?.data();
    const alvo = document.querySelector(`#mfotos-${i}`);
    if (!f || !okImg(f.img)) { alvo.innerHTML = '<p class="err">Foto grande não encontrada.</p>'; return; }
    const ext = f.img.startsWith("data:image/webp") ? "webp" : "jpg";
    alvo.innerHTML = `<img src="${f.img}" alt="" style="max-width:100%;border-radius:8px"><br>${a.uso_fotos === true ? `<a class="btn ghost" download="cliente-${esc(a.sku).replace(/[^A-Za-z0-9.-]/g, "-")}-${k + 1}.${ext}" href="${f.img}">Baixar foto</a>` : ""}`;
    return;
  }
  const i = Number(t.dataset.ok ?? t.dataset.nao ?? t.dataset.apagar); const a = LISTA[i]; if (!a) return;
  t.disabled = true;
  try {
    if (t.dataset.ok !== undefined) {
      const ver = !!document.querySelector(`#mver-${i}`)?.checked;
      await updateDoc(doc(db, "avaliacoes", a.id), { status: "aprovada", verificada: ver, moderado_em: serverTimestamp() });
    } else if (t.dataset.nao !== undefined) {
      await updateDoc(doc(db, "avaliacoes", a.id), { status: "recusada", verificada: false, moderado_em: serverTimestamp() });
    } else {
      if (!confirm("Apagar esta avaliação e as fotos de vez?")) { t.disabled = false; return; }
      for (let k = 0; k < 4; k++) await deleteDoc(doc(db, "avaliacoes", a.id, "fotos", String(k))).catch(() => {});
      if (a.video === true) { try { const m = await import("https://www.gstatic.com/firebasejs/10.12.2/firebase-storage.js"); await m.deleteObject(m.ref(m.getStorage(app), `avaliacoes/${a.id}/video`)); } catch (er) {} }
      await deleteDoc(doc(db, "avaliacoes", a.id));
    }
    listar();
  } catch (err) { t.disabled = false; t.textContent = "Erro. Tente de novo"; }
});

onAuthStateChanged(auth, u => {
  if (u) return listar();
  box.innerHTML = `<p>Tela da loja. Entre com a conta Google da Loja Dias.</p><button class="btn" id="mlogin">Entrar com Google</button>`;
  document.querySelector("#mlogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider());
});
