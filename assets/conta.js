// Loja Dias: conta do cliente com login Google (Firebase Auth + Firestore).
// Só é carregado quando dados/config.json tem "firebase". Cada cliente só lê e grava os próprios dados
// (regras em firestore.rules). Não guarda senha, cartão nem dado de pagamento.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaV3Provider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, reauthenticateWithPopup, signOut, deleteUser, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc, deleteDoc, collection, addDoc, getDocs, query, orderBy, limit, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const app = initializeApp(C.firebase);
if (C.appcheck) initializeAppCheck(app, { provider: new ReCaptchaV3Provider(C.appcheck), isTokenAutoRefreshEnabled: true });  // bloqueia robôs
const TERMO = "v1";  // versão da página de privacidade aceita
const auth = getAuth(app), db = getFirestore(app);
const $ = s => document.querySelector(s);
const brl = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const txt = (s, n) => String(s || "").trim().slice(0, n);
let user = null, perfil = null;

async function carregarPerfil() {
  const snap = await getDoc(doc(db, "clientes", user.uid));
  perfil = snap.exists() ? snap.data() : null;  // null = ainda não aceitou a privacidade
  return perfil;
}
async function salvarPerfil(p) {
  perfil = { nome: txt(p.nome, 80), telefone: txt(p.telefone, 20), endereco: txt(p.endereco, 200), cidade: txt(p.cidade, 30), aceite: TERMO, atualizado: serverTimestamp() };
  await setDoc(doc(db, "clientes", user.uid), perfil);
}
async function salvarPedido(pd) {  // histórico do próprio cliente; o pedido real é confirmado no WhatsApp
  if (!user || !perfil) return;
  await addDoc(collection(db, "clientes", user.uid, "pedidos"), {
    txid: txt(pd.txid, 25), total: Math.round(pd.total * 100) / 100, cidade: txt(pd.cidade, 30),
    itens: pd.itens.slice(0, 30).map(i => ({ sku: txt(i.sku, 40), nome: txt(i.nome, 90), qtd: Math.min(99, i.qtd | 0), preco: Math.round(i.preco * 100) / 100 })),
    criado: serverTimestamp()
  });
}
async function apagarConta() {  // LGPD: apaga histórico, perfil e o login
  const ps = await getDocs(collection(db, "clientes", user.uid, "pedidos"));
  for (const d of ps.docs) await deleteDoc(d.ref);
  await deleteDoc(doc(db, "clientes", user.uid));
  try { await deleteUser(user); }
  catch (e) { if (e.code === "auth/requires-recent-login") { await reauthenticateWithPopup(user, new GoogleAuthProvider()); await deleteUser(auth.currentUser); } else throw e; }
}
window.LojaConta = { salvarPedido, get user() { return user; }, get perfil() { return perfil; } };

// botão no topo
const btn = $("#contalink");
onAuthStateChanged(auth, async u => {
  user = u;
  if (btn) btn.textContent = u ? "Minha conta" : "Entrar";
  if (u) await carregarPerfil(); else perfil = null;
  document.dispatchEvent(new CustomEvent("loja-conta", { detail: { user, perfil } }));
});

// carrinho: preenche nome, endereço e cidade
document.addEventListener("loja-conta", () => {
  if (!perfil || !$("#lines")) return;
  if (!$("#name").value) $("#name").value = perfil.nome || "";
  if (!$("#addr").value) $("#addr").value = perfil.endereco || "";
  if (!$("#city").value && perfil.cidade) $("#city").value = perfil.cidade;
  $("#name").dispatchEvent(new Event("input", { bubbles: true }));
});

// página Minha conta
const box = $("#conta");
if (box) {
  const cidades = C.cidades.map(c => `<option value="${c.slug}">${c.nome}</option>`).join("");
  const render = async () => {
    if (!user) {
      box.innerHTML = `<p>Entre com sua conta Google para salvar o endereço e ver seus pedidos. A loja não vê sua senha. Conta é opcional: dá para comprar sem ela.</p>
        <button class="btn" type="button" id="glogin">Entrar com Google</button><p class="err" id="cerr" hidden></p>`;
      $("#glogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider()).catch(e => { $("#cerr").hidden = false; $("#cerr").textContent = "Não deu para entrar. Tente de novo."; });
      return;
    }
    const p = perfil || await carregarPerfil();
    if (!p) {  // primeiro login: aceite da privacidade
      box.innerHTML = `<p>Antes de salvar seus dados, leia a <a href="privacidade.html" target="_blank">página de privacidade</a>. Guardamos só nome, WhatsApp, cidade, endereço e seus pedidos. Nada de CPF ou cartão.</p>
        <label class="opt"><input type="checkbox" id="caceite"><span>Li e aceito</span></label>
        <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="button" id="cok1" disabled>Continuar</button><button class="btn ghost" type="button" id="csair0">Não quero conta</button></div>`;
      $("#caceite").onchange = e => $("#cok1").disabled = !e.target.checked;
      $("#cok1").onclick = async () => { await salvarPerfil({ nome: user.displayName || "" }); render(); };
      $("#csair0").onclick = () => deleteUser(user).catch(() => signOut(auth));
      return;
    }
    box.innerHTML = `<p>Olá, <b>${(user.displayName || "").replace(/[<>&]/g, "")}</b>.</p>
      <div class="field"><label class="lbl" for="cnome">Nome</label><input id="cnome" autocomplete="name"></div>
      <div class="field"><label class="lbl" for="ctel">WhatsApp</label><input id="ctel" inputmode="tel" autocomplete="tel"></div>
      <div class="field"><label class="lbl" for="ccid">Cidade</label><select id="ccid"><option value="">Escolha</option>${cidades}</select></div>
      <div class="field"><label class="lbl" for="cend">Endereço e bairro</label><input id="cend" autocomplete="street-address"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="button" id="csalvar">Salvar</button><button class="btn ghost" type="button" id="csair">Sair</button></div>
      <p class="note" id="cok" hidden>Salvo ✓</p>
      <h2 style="margin-top:28px">Meus pedidos</h2><div id="chist" class="note">Carregando…</div>
      <h2 style="margin-top:28px">Apagar minha conta</h2><p class="note">Apaga seus dados, seu histórico e o login. Não dá para desfazer.</p>
      <button class="btn ghost" type="button" id="capagar">Apagar minha conta</button><p class="err" id="cerr2" hidden></p>`;
    $("#cnome").value = p.nome || ""; $("#ctel").value = p.telefone || ""; $("#ccid").value = p.cidade || ""; $("#cend").value = p.endereco || "";
    $("#csalvar").onclick = async () => { await salvarPerfil({ nome: $("#cnome").value, telefone: $("#ctel").value, cidade: $("#ccid").value, endereco: $("#cend").value }); $("#cok").hidden = false; };
    $("#csair").onclick = () => signOut(auth);
    $("#capagar").onclick = async () => {
      if (!confirm("Apagar sua conta e todos os seus dados? Não dá para desfazer.")) return;
      try { await apagarConta(); box.innerHTML = "<p>Conta apagada. Seus dados foram removidos.</p>"; }
      catch (e) { $("#cerr2").hidden = false; $("#cerr2").textContent = "Não deu para apagar agora. Tente de novo ou chame no WhatsApp."; }
    };
    const qs = await getDocs(query(collection(db, "clientes", user.uid, "pedidos"), orderBy("criado", "desc"), limit(20)));
    const h = $("#chist");
    h.innerHTML = qs.empty ? "Nenhum pedido ainda." : qs.docs.map(d => { const o = d.data(); const dt = o.criado ? o.criado.toDate().toLocaleDateString("pt-BR") : "";
      const it = o.itens.map(i => `${i.qtd}x ${i.nome}`.replace(/[<>&]/g, "")).join(", ");
      return `<div class="line"><span>${dt} · ${it}</span><b>${brl(o.total)}</b></div>`; }).join("");
  };
  document.addEventListener("loja-conta", render);
}
