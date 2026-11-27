// Loja Dias: conta do cliente com login Google (Firebase Auth + Firestore).
// Só é carregado quando dados/config.json tem "firebase". Cada cliente só lê e grava os próprios dados
// (regras em firestore.rules). Não guarda senha, cartão nem dado de pagamento.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getAuth, connectAuthEmulator, GoogleAuthProvider, signInWithPopup, reauthenticateWithPopup, signOut, deleteUser, onAuthStateChanged, sendSignInLinkToEmail, isSignInWithEmailLink, signInWithEmailLink } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, connectFirestoreEmulator, doc, getDoc, setDoc, deleteDoc, collection, addDoc, getDocs, query, where, orderBy, limit, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const app = initializeApp(C.firebase);
const EMU = ["localhost", "127.0.0.1"].includes(location.hostname);  // teste no computador: usa o simulador do Firebase
if (C.appcheck && !EMU) initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(C.appcheck), isTokenAutoRefreshEnabled: true });  // bloqueia robôs
const TERMO = "v1";  // versão da página de privacidade aceita
const auth = getAuth(app), db = getFirestore(app);
if (EMU) { connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true }); connectFirestoreEmulator(db, "127.0.0.1", 8080); }
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
    moto: txt(p.moto ?? a.moto, 60), km_dia: num(p.km_dia ?? a.km_dia ?? 0, 0, 1000), tipo_oleo: (p.tipo_oleo ?? a.tipo_oleo) === "semi" ? "semi" : "mineral",
    ...(((p.intervalo_oleo ?? a.intervalo_oleo) || "") !== "" ? { intervalo_oleo: num(p.intervalo_oleo ?? a.intervalo_oleo, 300, 10000) } : {}),  // opcional: vazio = regra do tipo de óleo
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
    ...(/^[A-Z0-9]{3,12}$/.test(pd.ref || "") ? { ref: pd.ref } : {}),  // código de quem indicou (programa de indicação)
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
  try {  // avaliações e fotos do cliente também saem
    const av = await getDocs(query(collection(db, "avaliacoes"), where("uid", "==", user.uid)));
    for (const d of av.docs) { for (let i = 0; i < 4; i++) await deleteDoc(doc(db, "avaliacoes", d.id, "fotos", String(i))).catch(() => {}); await deleteDoc(d.ref); }
  } catch (e) {}
  try { await deleteUser(user); }
  catch (e) {
    if (e.code !== "auth/requires-recent-login") throw e;
    if (!user.providerData.some(x => x.providerId === "google.com")) throw new Error("Por segurança, saia, entre de novo pelo link do e-mail e apague a conta em seguida.");
    await reauthenticateWithPopup(user, new GoogleAuthProvider()); await deleteUser(auth.currentUser);
  }
}
// Painel de pedidos (25/11): todo pedido do carrinho vai para vendas/{txid}, com ou sem login. Só a loja lê.
// Se a internet cair na hora, fica guardado neste aparelho e tenta de novo na próxima página aberta.
const PEND = "dias-venda-pendente";
const lsG = () => { try { return JSON.parse(localStorage.getItem(PEND) || "null"); } catch (e) { return null; } };
const lsS = v => { try { v ? localStorage.setItem(PEND, JSON.stringify(v)) : localStorage.removeItem(PEND); } catch (e) {} };
const r2 = v => Math.round((Number(v) || 0) * 100) / 100;
function montarVenda(pd) {
  const v = {
    txid: txt(pd.txid, 25), status: "novo", origem: "site", entrega: pd.cidade === "retirada" ? "retirada" : "motoboy",
    pagamento: pd.pagamento === "entrega" ? "entrega" : "pix",
    cliente: { nome: txt(pd.cliente && pd.cliente.nome, 80), telefone: txt(pd.cliente && pd.cliente.telefone, 20),
      endereco: txt(pd.cliente && pd.cliente.endereco, 200), cidade: txt(pd.cidade, 30) },
    itens: pd.itens.slice(0, 30).map(i => ({ sku: txt(i.sku, 40), nome: txt(i.nome, 90), qtd: Math.min(99, i.qtd | 0), preco: r2(i.preco) })),
    sub: r2(pd.sub), frete: r2(pd.frete), desconto: r2(pd.desconto), total: r2(pd.total)
  };
  if (/^[A-Z0-9]{3,12}$/.test(pd.ref || "")) v.ref = pd.ref;
  if (pd.nf && /^\d{14}$/.test(pd.nf.cnpj || "")) v.nf = { cnpj: pd.nf.cnpj, razao: txt(pd.nf.razao, 120), email: txt(pd.nf.email, 120) };
  return v;
}
async function gravarVenda(v) {
  const d = { ...v, criado: serverTimestamp() };
  if (auth.currentUser) d.uid = auth.currentUser.uid;
  await setDoc(doc(db, "vendas", v.txid), d);
}
async function registrarVenda(pd) {
  const v = montarVenda(pd);
  lsS(v);  // guarda antes; apaga quando gravar
  await gravarVenda(v);
  lsS(null);
}
setTimeout(() => { const v = lsG(); if (v && v.txid) gravarVenda(v).then(() => lsS(null), e => { if (e && e.code === "permission-denied") lsS(null); }); }, 1500);
window.LojaConta = { salvarPedido, registrarVenda, freteFidelidade, get user() { return user; }, get perfil() { return perfil; }, get pedidos() { return nPedidos; } };

// Login por link no e-mail (Luan 26/11): sem senha, funciona também dentro do WhatsApp e do Instagram
const EMAIL_KEY = "dias-email-login";
const linkUrl = () => location.origin + location.pathname;
if (C.login_email && isSignInWithEmailLink(auth, location.href)) {
  const finalizar = async email => {
    try { await signInWithEmailLink(auth, email, location.href); try { localStorage.removeItem(EMAIL_KEY); } catch (e) {} history.replaceState(null, "", linkUrl()); }
    catch (e) { window.__diasLinkPendente = null; window.__diasLinkErro = e.code === "auth/invalid-action-code" || e.code === "auth/expired-action-code" ? "Esse link já foi usado ou venceu. Peça um novo abaixo." : "Não deu para entrar com esse link. Confira o e-mail e peça um novo.";
      history.replaceState(null, "", linkUrl()); document.dispatchEvent(new CustomEvent("loja-conta", { detail: { user: null, perfil: null } })); }
  };
  let em = null; try { em = localStorage.getItem(EMAIL_KEY); } catch (e) {}
  if (em) finalizar(em); else window.__diasLinkPendente = finalizar;  // aberto em outro aparelho: pede o e-mail de novo
}
const appInterno = /FBAN|FBAV|Instagram|WhatsApp|Line\/|; wv\)/i.test(navigator.userAgent);

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
  if ($("#tel") && !$("#tel").value) $("#tel").value = perfil.telefone || "";
  if (!$("#city").value && perfil.cidade) $("#city").value = perfil.cidade;
  $("#name").dispatchEvent(new Event("input", { bubbles: true }));
});

// página Minha conta
const box = $("#conta");
if (box) {
  const cidades = C.cidades.map(c => `<option value="${c.slug}">${c.nome}</option>`).join("");
  const render = async () => {
    if (!user) {
      const pend = !!window.__diasLinkPendente;
      box.classList.add("login");
      box.innerHTML = `<div class="lgtopo"><h2>${pend ? "Confirme seu e-mail" : "Entre para comprar mais rápido"}</h2>
        <p>${pend ? "Você abriu o link em outro aparelho. Digite o mesmo e-mail para terminar de entrar." : "Conta é opcional. Dá para comprar sem ela."}</p></div>
        ${pend ? "" : `<ul class="lgvant"><li>Endereço e WhatsApp já preenchidos no carrinho</li><li>Seus pedidos guardados num lugar só</li><li>A cada 5 pedidos pagos, o 6º sai com frete grátis</li><li>Aviso no WhatsApp na hora de trocar o óleo, se você quiser</li></ul>`}
        ${appInterno && !pend ? `<p class="lgaviso">Você está dentro do WhatsApp ou do Instagram, e o Google não deixa entrar por aqui. ${C.login_email ? "Use seu e-mail abaixo, ou abra o site no Chrome." : "Toque nos três pontinhos e escolha abrir no Chrome."}</p>` : ""}
        ${pend ? "" : `<button class="btn gbtn" type="button" id="glogin"><svg viewBox="0 0 48 48" width="20" height="20" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.8 6C12.4 13.7 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.8c4.3-4 6.9-9.9 6.9-17.1z"/><path fill="#FBBC05" d="M10.5 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.8-6A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.7l7.9-6z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.8c-2.1 1.4-4.8 2.3-8.5 2.3-6.3 0-11.6-4.2-13.5-9.9l-7.9 6C6.6 42.6 14.6 48 24 48z"/></svg>Entrar com Google</button>`}
        ${C.login_email ? `${pend ? "" : `<div class="lgou"><span>ou entre com seu e-mail</span></div>`}
          <form id="eform" class="lgemail" novalidate><label class="lbl" for="email">Seu e-mail</label>
          <input id="email" type="email" inputmode="email" autocomplete="email" placeholder="voce@gmail.com" required>
          <button class="btn dark" type="submit" id="esend">${pend ? "Entrar" : "Receber link para entrar"}</button></form>
          <p class="note" id="eok" hidden></p>` : ""}
        <p class="err" id="cerr" hidden></p>
        <p class="lgseg">Sem senha para criar ou lembrar. A loja nunca vê sua senha do Google nem do e-mail. Guardamos só o que você preencher. <a href="privacidade.html">Privacidade</a></p>`;
      const erro = m => { $("#cerr").hidden = false; $("#cerr").textContent = m; };
      if (window.__diasLinkErro) { erro(window.__diasLinkErro); window.__diasLinkErro = null; }
      if ($("#glogin")) $("#glogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider()).catch(e => {
        if (e.code === "auth/popup-closed-by-user" || e.code === "auth/cancelled-popup-request") return;
        erro(e.code === "auth/popup-blocked" ? "O navegador bloqueou a janela do Google. Permita pop-ups para lojadias.com.br e tente de novo." : appInterno ? "O Google não deixa entrar dentro deste app. Abra o site no Chrome ou use seu e-mail." : "Não deu para entrar com o Google. Tente de novo ou use seu e-mail.");
      });
      if ($("#eform")) $("#eform").onsubmit = async ev => {
        ev.preventDefault(); $("#cerr").hidden = true;
        const email = $("#email").value.trim().toLowerCase();
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return erro("Digite um e-mail válido, como voce@gmail.com.");
        $("#esend").disabled = true;
        try {
          if (pend) { await window.__diasLinkPendente(email); window.__diasLinkPendente = null; return; }
          await sendSignInLinkToEmail(auth, email, { url: linkUrl(), handleCodeInApp: true });
          try { localStorage.setItem(EMAIL_KEY, email); } catch (e) {}
          $("#eform").hidden = true; $("#eok").hidden = false;
          $("#eok").innerHTML = `Pronto. Mandamos um link para <b>${email.replace(/[<>&"]/g, "")}</b>. Abra seu e-mail e toque no link para entrar. Se não aparecer em 2 minutos, olhe no spam ou nas promoções.`;
        } catch (e) { $("#esend").disabled = false; erro(e.code === "auth/too-many-requests" ? "Muitas tentativas. Espere alguns minutos e tente de novo." : "Não deu para mandar o link agora. Tente de novo ou entre com o Google."); }
      };
      return;
    }
    box.classList.remove("login");
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
      <div class="field"><label class="lbl" for="ctipo">Óleo que você usa</label><select id="ctipo"><option value="mineral">Mineral 20W50 (o mais comum)</option><option value="semi">Semissintético 10W30</option></select></div>
      <div class="field"><label class="lbl" for="cint">Troca o óleo a cada quantos km (opcional)</label><input id="cint" inputmode="numeric" placeholder="Deixe vazio que a gente calcula"></div>
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
    $("#cmoto").value = p.moto || ""; $("#ckm").value = p.km_dia || ""; $("#cint").value = p.intervalo_oleo || ""; $("#ctipo").value = p.tipo_oleo === "semi" ? "semi" : "mineral";
    const ul = p.ultimas || {}; $("#uoleo").value = ul.oleo || ""; $("#urel").value = ul.relacao || ""; $("#upast").value = ul.pastilha || "";
    $("#clemb").checked = !!p.lembrete;
    if (p.ultimas && p.ultimas.oleo && p.km_dia) {
      // mineral: 900 km ou 5 dias; semi: 1.400 km ou 8 dias (o que vier primeiro). Se o cliente digitou o intervalo, vale o dele.
      const semi = p.tipo_oleo === "semi", km = p.intervalo_oleo || (semi ? 1400 : 900), dias = p.intervalo_oleo ? 999 : (semi ? 8 : 5);
      const d = new Date(p.ultimas.oleo + "T12:00:00"); d.setDate(d.getDate() + Math.max(1, Math.min(dias, Math.floor(km / p.km_dia))));
      $("#cprox").textContent = `Próxima troca de óleo: por volta de ${d.toLocaleDateString("pt-BR")}.`;
    }
    const faltam = 5 - (pagos() % 6);
    $("#cfid").textContent = freteFidelidade() ? "Seu próximo pedido sai com frete grátis (6º pedido)." : `A cada 5 pedidos pagos, o 6º sai com frete grátis. Faltam ${faltam < 0 ? 0 : faltam}.`;
    $("#csalvar").onclick = async () => { await salvarPerfil({ nome: $("#cnome").value, telefone: $("#ctel").value, cidade: $("#ccid").value, endereco: $("#cend").value,
      moto: $("#cmoto").value, km_dia: $("#ckm").value, intervalo_oleo: $("#cint").value.trim(), tipo_oleo: $("#ctipo").value, lembrete: $("#clemb").checked,
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
