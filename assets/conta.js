// Loja Dias: conta do cliente com login Google (Firebase Auth + Firestore).
// Só é carregado quando dados/config.json tem "firebase". Cada cliente só lê e grava os próprios dados
// (regras em firestore.rules). Não guarda senha, cartão nem dado de pagamento.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, reauthenticateWithPopup, signOut, deleteUser, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc, deleteDoc, collection, addDoc, getDocs, query, orderBy, limit, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const app = initializeApp(C.firebase);
if (C.appcheck) initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(C.appcheck), isTokenAutoRefreshEnabled: true });  // bloqueia robôs
const TERMO = "v1";  // versão da página de privacidade aceita
const auth = getAuth(app), db = getFirestore(app);
const $ = s => document.querySelector(s);
const brl = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const txt = (s, n) => String(s || "").trim().slice(0, n);
let user = null, perfil = null, nPedidos = 0;
const hoje = () => new Date().toISOString().slice(0, 10);
const num = (v, min, max) => { const n = Math.round(Number(String(v).replace(",", "."))); return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : 0; };

async function carregarPerfil() {
  const snap = await getDoc(doc(db, "clientes", user.uid));
  perfil = snap.exists() ? snap.data() : null;  // null = ainda não aceitou a privacidade
  if (perfil) { try { nPedidos = (await getDocs(collection(db, "clientes", user.uid, "pedidos"))).size; } catch (e) { nPedidos = 0; } }
  return perfil;
}
async function salvarPerfil(p) {
  const a = perfil || {};
  const ult = p.ultimas || a.ultimas || {};
  perfil = { nome: txt(p.nome ?? a.nome, 80), telefone: txt(p.telefone ?? a.telefone, 20), endereco: txt(p.endereco ?? a.endereco, 200), cidade: txt(p.cidade ?? a.cidade, 30),
    // fidelidade (Mesa 25/11, opção A): moto, uso e datas das últimas trocas para o lembrete
    moto: txt(p.moto ?? a.moto, 60), km_dia: num(p.km_dia ?? a.km_dia ?? 0, 0, 1000), intervalo_oleo: num(p.intervalo_oleo ?? a.intervalo_oleo ?? 1000, 300, 10000),
    lembrete: !!(p.lembrete ?? a.lembrete),
    ultimas: { oleo: txt(ult.oleo, 10), relacao: txt(ult.relacao, 10), pastilha: txt(ult.pastilha, 10) },
    ...(a.pedidos_pagos !== undefined ? { pedidos_pagos: a.pedidos_pagos } : {}),  // só a loja grava; aqui só preserva
    aceite: TERMO, atualizado: serverTimestamp() };
  await setDoc(doc(db, "clientes", user.uid), perfil);
}
// 6º pedido com frete grátis: a cada 5 pedidos registrados, o próximo não paga frete
const pagos = () => (perfil && Number.isInteger(perfil.pedidos_pagos)) ? perfil.pedidos_pagos : 0;  // contado pela loja, pedidos com Pix confirmado
const freteFidelidade = () => !!(user && perfil && pagos() > 0 && pagos() % 6 === 5);
async function salvarPedido(pd) {  // histórico do próprio cliente; o pedido real é confirmado no WhatsApp
  if (!user || !perfil) return;
  await addDoc(collection(db, "clientes", user.uid, "pedidos"), {
    txid: txt(pd.txid, 25), total: Math.round(pd.total * 100) / 100, cidade: txt(pd.cidade, 30),
    itens: pd.itens.slice(0, 30).map(i => ({ sku: txt(i.sku, 40), nome: txt(i.nome, 90), qtd: Math.min(99, i.qtd | 0), preco: Math.round(i.preco * 100) / 100 })),
    criado: serverTimestamp()
  });
  nPedidos++;
  // marca a data das trocas pelo que veio no pedido (para o lembrete)
  const cats = pd.itens.map(i => i.categoria || ""), u = { ...(perfil.ultimas || {}) };
  if (cats.includes("oleo")) u.oleo = hoje();
  if (cats.includes("transmissao")) u.relacao = hoje();
  if (pd.itens.some(i => /pastilha|lona|sapata|patim/i.test(i.nome))) u.pastilha = hoje();
  if (pd.itens.some(i => i.sku === "KIT-REVISAO-CG")) u.oleo = hoje();
  await salvarPerfil({ ultimas: u });
}
async function apagarConta() {  // LGPD: apaga histórico, perfil e o login
  const ps = await getDocs(collection(db, "clientes", user.uid, "pedidos"));
  for (const d of ps.docs) await deleteDoc(d.ref);
  await deleteDoc(doc(db, "clientes", user.uid));
  try { await deleteUser(user); }
  catch (e) { if (e.code === "auth/requires-recent-login") { await reauthenticateWithPopup(user, new GoogleAuthProvider()); await deleteUser(auth.currentUser); } else throw e; }
}
window.LojaConta = { salvarPedido, freteFidelidade, get user() { return user; }, get perfil() { return perfil; }, get pedidos() { return nPedidos; } };

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
      <h2 style="margin-top:22px">Minha moto</h2>
      <div class="field"><label class="lbl" for="cmoto">Moto e ano</label><input id="cmoto" placeholder="Ex.: CG 160 Fan 2021"></div>
      <div class="field"><label class="lbl" for="ckm">Quantos km roda por dia</label><input id="ckm" inputmode="numeric" placeholder="Ex.: 120"></div>
      <div class="field"><label class="lbl" for="cint">Troca o óleo a cada quantos km</label><input id="cint" inputmode="numeric" placeholder="Ex.: 1000"></div>
      <div class="field"><span class="lbl">Últimas trocas</span><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px">
        <label>Óleo<input type="date" id="uoleo"></label><label>Relação<input type="date" id="urel"></label><label>Pastilha<input type="date" id="upast"></label></div></div>
      <label class="opt"><input type="checkbox" id="clemb"><span>Quero lembrete no WhatsApp quando chegar a hora da troca<small>Pode desligar quando quiser.</small></span></label>
      <p class="note" id="cprox"></p>
      <p class="note" id="cfid"></p>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="button" id="csalvar">Salvar</button><button class="btn ghost" type="button" id="csair">Sair</button></div>
      <p class="note" id="cok" hidden>Salvo ✓</p>
      <h2 style="margin-top:28px">Meus pedidos</h2><div id="chist" class="note">Carregando…</div>
      <h2 style="margin-top:28px">Apagar minha conta</h2><p class="note">Apaga seus dados, seu histórico e o login. Não dá para desfazer.</p>
      <button class="btn ghost" type="button" id="capagar">Apagar minha conta</button><p class="err" id="cerr2" hidden></p>`;
    $("#cnome").value = p.nome || ""; $("#ctel").value = p.telefone || ""; $("#ccid").value = p.cidade || ""; $("#cend").value = p.endereco || "";
    $("#cmoto").value = p.moto || ""; $("#ckm").value = p.km_dia || ""; $("#cint").value = p.intervalo_oleo || "";
    const ul = p.ultimas || {}; $("#uoleo").value = ul.oleo || ""; $("#urel").value = ul.relacao || ""; $("#upast").value = ul.pastilha || "";
    $("#clemb").checked = !!p.lembrete;
    if (p.ultimas && p.ultimas.oleo && p.km_dia && p.intervalo_oleo) {
      const d = new Date(p.ultimas.oleo + "T12:00:00"); d.setDate(d.getDate() + Math.max(1, Math.floor(p.intervalo_oleo / p.km_dia)));
      $("#cprox").textContent = `Próxima troca de óleo: por volta de ${d.toLocaleDateString("pt-BR")}.`;
    }
    const faltam = 5 - (pagos() % 6);
    $("#cfid").textContent = freteFidelidade() ? "Seu próximo pedido sai com frete grátis (6º pedido)." : `A cada 5 pedidos pagos, o 6º sai com frete grátis. Faltam ${faltam < 0 ? 0 : faltam}.`;
    $("#csalvar").onclick = async () => { await salvarPerfil({ nome: $("#cnome").value, telefone: $("#ctel").value, cidade: $("#ccid").value, endereco: $("#cend").value,
      moto: $("#cmoto").value, km_dia: $("#ckm").value, intervalo_oleo: $("#cint").value, lembrete: $("#clemb").checked,
      ultimas: { oleo: $("#uoleo").value, relacao: $("#urel").value, pastilha: $("#upast").value } }); $("#cok").hidden = false; render(); };
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
