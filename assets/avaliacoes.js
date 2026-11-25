// Loja Dias: avaliações da peça (1 a 5 estrelas, texto, até 4 fotos e, se ligado, 1 vídeo curto).
// Só aparece no site depois que a loja aprova em moderar.html. Regras em firestore.rules (bloco avaliacoes).
// Tudo que vem do Firestore foi escrito por cliente: sempre passa por esc() antes de ir para a tela.
import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc, deleteDoc, collection, getDocs, query, where, limit, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const C = window.LOJA.config;
const box = document.querySelector("#avaliacoes[data-sku]");

// limites (para não pesar o site nem a cota grátis do Firebase)
export const LIM = { fotos: 4, ladoFoto: 1280, ladoMini: 240, maxFoto: 700000, maxMini: 38000, texto: 1000, nome: 40,
  videoMB: 20, videoSeg: 60 };
export const chave = sku => String(sku).replace(/[^A-Za-z0-9.-]/g, "-").slice(0, 40);
export const esc = s => String(s ?? "").replace(/[<>&"']/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c]));
const okImg = s => typeof s === "string" && /^data:image\/(webp|jpeg);base64,[A-Za-z0-9+/=]+$/.test(s);
const estrelas = n => "★★★★★".slice(0, n) + "☆☆☆☆☆".slice(0, 5 - n);

// reduz a foto no celular do cliente antes de enviar; redesenhar no canvas também apaga o GPS (EXIF) da foto
export async function reduzir(file, lado, maxChars) {
  const bmp = await createImageBitmap(file).catch(() => null);
  if (!bmp) throw new Error("foto");
  for (const [l, q] of [[lado, 0.82], [lado, 0.68], [Math.round(lado * 0.75), 0.62], [Math.round(lado * 0.55), 0.55]]) {
    const k = Math.min(1, l / Math.max(bmp.width, bmp.height));
    const cv = document.createElement("canvas");
    cv.width = Math.max(1, Math.round(bmp.width * k)); cv.height = Math.max(1, Math.round(bmp.height * k));
    const cx = cv.getContext("2d"); cx.fillStyle = "#fff"; cx.fillRect(0, 0, cv.width, cv.height); cx.drawImage(bmp, 0, 0, cv.width, cv.height);
    let u = cv.toDataURL("image/webp", q);
    if (!u.startsWith("data:image/webp")) u = cv.toDataURL("image/jpeg", q);  // iPhone antigo não gera webp
    if (u.length <= maxChars) return u;
  }
  throw new Error("grande");
}
const duracao = file => new Promise(ok => { const v = document.createElement("video"); v.preload = "metadata";
  v.onloadedmetadata = () => { URL.revokeObjectURL(v.src); ok(v.duration); }; v.onerror = () => ok(NaN); v.src = URL.createObjectURL(file); });

function iniciar() {
  const app = getApps().length ? getApp() : initializeApp(C.firebase);  // conta.js já abriu o app (e o App Check)
  const auth = getAuth(app), db = getFirestore(app);
  const SKU = box.dataset.sku, K = chave(SKU), NOME = box.dataset.nome || "";
  const VIDEO = !!C.video_avaliacao;
  let user = null, minha = null, carregou = false;
  const $ = s => box.querySelector(s);
  const store = async () => { const m = await import("https://www.gstatic.com/firebasejs/10.12.2/firebase-storage.js"); return { m, s: m.getStorage(app) }; };

  async function listar() {
    carregou = true;
    const lista = $("#avlista");
    let docs = [];
    try { docs = (await getDocs(query(collection(db, "avaliacoes"), where("chave", "==", K), where("status", "==", "aprovada"), limit(30)))).docs.map(d => ({ id: d.id, ...d.data() })); }
    catch (e) { lista.innerHTML = ""; return; }
    docs.sort((a, b) => (b.criado?.seconds || 0) - (a.criado?.seconds || 0));
    if (!docs.length) { $("#avmedia").textContent = "Ainda sem avaliações. Comprou esta peça? Seja o primeiro a contar como foi."; lista.innerHTML = ""; return; }
    const media = docs.reduce((s, d) => s + (Number(d.estrelas) || 0), 0) / docs.length;
    $("#avmedia").innerHTML = `<span class="avstars" aria-hidden="true">${estrelas(Math.round(media))}</span> <b>${media.toFixed(1).replace(".", ",")}</b> de 5 · ${docs.length} ${docs.length > 1 ? "avaliações" : "avaliação"}`;
    lista.innerHTML = docs.map(d => {
      const n = Math.min(5, Math.max(1, Number(d.estrelas) | 0));
      const dt = d.criado?.toDate ? d.criado.toDate().toLocaleDateString("pt-BR") : "";
      const fotos = (Array.isArray(d.fotos) ? d.fotos : []).filter(okImg).slice(0, LIM.fotos)
        .map((f, i) => `<button type="button" class="avthumb" data-av="${esc(d.id)}" data-n="${i}" aria-label="Ver foto ${i + 1}"><img src="${f}" alt="" loading="lazy"></button>`).join("");
      return `<article class="avitem"><div class="avtop"><span class="avstars" aria-label="${n} de 5 estrelas">${estrelas(n)}</span>
        <b>${esc(d.nome)}</b>${d.verificada === true ? ' <span class="avok">Compra confirmada</span>' : ""} <span class="note">${dt}</span></div>
        ${d.texto ? `<p>${esc(d.texto)}</p>` : ""}${fotos || d.video === true ? `<div class="avfotos">${fotos}${d.video === true ? `<button type="button" class="avthumb avvid" data-vid="${esc(d.id)}" aria-label="Ver vídeo">▶ Vídeo</button>` : ""}</div>` : ""}</article>`;
    }).join("");
  }

  // foto grande e vídeo só baixam quando o cliente toca (economiza dados e cota)
  box.addEventListener("click", async ev => {
    const t = ev.target.closest("[data-av],[data-vid]"); if (!t) return;
    const dlg = $("#avdlg"), alvo = $("#avdlgc");
    alvo.innerHTML = '<p class="note">Carregando…</p>'; dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", "");
    try {
      if (t.dataset.vid) {
        const { m, s } = await store();
        const url = await m.getDownloadURL(m.ref(s, `avaliacoes/${t.dataset.vid}/video`));
        alvo.innerHTML = ""; const v = document.createElement("video"); v.controls = true; v.playsInline = true; v.src = url; alvo.append(v);
      } else {
        const f = (await getDoc(doc(db, "avaliacoes", t.dataset.av, "fotos", t.dataset.n))).data();
        alvo.innerHTML = ""; if (f && okImg(f.img)) { const im = new Image(); im.src = f.img; im.alt = "Foto do cliente"; alvo.append(im); }
      }
    } catch (e) { alvo.innerHTML = '<p class="err">Não deu para abrir agora.</p>'; }
  });
  $("#avfechar").onclick = () => { const d = $("#avdlg"); d.close ? d.close() : d.removeAttribute("open"); $("#avdlgc").innerHTML = ""; };

  async function pedidoComEstaPeca() {  // liga a avaliação ao pedido feito pelo site (a loja confirma na moderação)
    try {
      const ps = await getDocs(collection(db, "clientes", user.uid, "pedidos"));
      const d = ps.docs.find(x => (x.data().itens || []).some(i => i && i.sku === SKU));
      return d ? d.id : "";
    } catch (e) { return ""; }
  }

  function form() {
    const f = $("#avform");
    if (!user) {
      f.innerHTML = `<p class="note">Para avaliar, entre com sua conta Google. Isso evita avaliação falsa.</p><button class="btn" type="button" id="avlogin">Entrar com Google e avaliar</button>`;
      $("#avlogin").onclick = () => signInWithPopup(auth, new GoogleAuthProvider()).catch(() => {});
      return;
    }
    if (minha && !f.dataset.editar) {
      const st = { pendente: "esperando a loja conferir", aprovada: "publicada", recusada: "não aprovada" }[minha.status] || "";
      f.innerHTML = `<p class="note">Sua avaliação desta peça está <b>${st}</b>.</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn ghost" type="button" id="aveditar">Refazer</button><button class="btn ghost" type="button" id="avapagar">Apagar</button></div>`;
      $("#aveditar").onclick = () => { f.dataset.editar = "1"; form(); };
      $("#avapagar").onclick = async () => { if (!confirm("Apagar sua avaliação e as fotos?")) return; await apagarMinha(); minha = null; form(); };
      return;
    }
    const primeiro = (user.displayName || "").trim().split(/\s+/)[0] || "";
    f.innerHTML = `<form id="avf" novalidate>
      <fieldset class="avnota"><legend class="lbl">Sua nota</legend>${[5, 4, 3, 2, 1].map(n => `<label><input type="radio" name="avn" value="${n}"><span aria-label="${n} estrela${n > 1 ? "s" : ""}">★</span></label>`).join("")}</fieldset>
      <div class="field"><label class="lbl" for="avtxt">Conte como foi (serviu na moto? qualidade? entrega?)</label><textarea id="avtxt" maxlength="${LIM.texto}" rows="4"></textarea></div>
      <div class="field"><label class="lbl" for="avnome">Nome que aparece</label><input id="avnome" maxlength="${LIM.nome}" value="${esc(primeiro)}"></div>
      <div class="field"><label class="lbl" for="avfoto">Fotos da peça (até ${LIM.fotos})</label><input type="file" id="avfoto" accept="image/*" multiple><div id="avprev" class="avfotos"></div>
        <small class="note">A foto é reduzida no seu celular antes de enviar.</small></div>
      ${VIDEO ? `<div class="field"><label class="lbl" for="avvideo">Vídeo curto (até ${LIM.videoSeg} segundos e ${LIM.videoMB} MB)</label><input type="file" id="avvideo" accept="video/mp4,video/quicktime,video/webm"></div>` : ""}
      <label class="opt"><input type="checkbox" id="avuso"><span>Autorizo a Loja Dias a usar minhas fotos${VIDEO ? " e vídeo" : ""} no site e nas redes sociais da loja<small>Opcional. Sem marcar, elas aparecem só nesta avaliação.</small></span></label>
      <label class="opt"><input type="checkbox" id="avtermo"><span>Li a <a href="privacidade.html" target="_blank">página de privacidade</a> e a avaliação é verdadeira</span></label>
      <p class="err" id="averr" hidden></p>
      <button class="btn" type="submit" id="avenviar">Enviar avaliação</button>
      <p class="note">A avaliação aparece depois que a loja conferir (para barrar propaganda e palavrão).</p></form>`;
    let fotos = [];
    $("#avfoto").onchange = async ev => {
      const err = $("#averr"); err.hidden = true;
      const files = [...ev.target.files].slice(0, LIM.fotos - fotos.length);
      for (const file of files) {
        try { fotos.push({ img: await reduzir(file, LIM.ladoFoto, LIM.maxFoto), mini: await reduzir(file, LIM.ladoMini, LIM.maxMini) }); }
        catch (e) { err.hidden = false; err.textContent = "Uma das fotos não abriu. Tente outra foto."; }
      }
      ev.target.value = "";
      $("#avprev").innerHTML = fotos.map((x, i) => `<button type="button" class="avthumb" data-tirar="${i}" aria-label="Tirar foto ${i + 1}"><img src="${x.mini}" alt=""><span>×</span></button>`).join("");
    };
    $("#avprev").onclick = ev => { const b = ev.target.closest("[data-tirar]"); if (!b) return; fotos.splice(Number(b.dataset.tirar), 1); b.remove();
      $("#avprev").innerHTML = fotos.map((x, i) => `<button type="button" class="avthumb" data-tirar="${i}" aria-label="Tirar foto ${i + 1}"><img src="${x.mini}" alt=""><span>×</span></button>`).join(""); };
    $("#avf").onsubmit = async ev => {
      ev.preventDefault();
      const err = $("#averr"), bt = $("#avenviar"); err.hidden = true;
      const fala = m => { err.hidden = false; err.textContent = m; };
      const n = Number((box.querySelector('input[name="avn"]:checked') || {}).value || 0);
      const texto = $("#avtxt").value.trim().slice(0, LIM.texto), nome = $("#avnome").value.trim().slice(0, LIM.nome);
      if (!n) return fala("Escolha de 1 a 5 estrelas.");
      if (!nome) return fala("Escreva o nome que vai aparecer.");
      if (!$("#avtermo").checked) return fala("Marque que leu a privacidade.");
      const vfile = VIDEO && $("#avvideo").files[0];
      if (vfile) {
        if (vfile.size > LIM.videoMB * 1024 * 1024) return fala(`Vídeo maior que ${LIM.videoMB} MB. Grave mais curto ou em qualidade menor (720p).`);
        const s = await duracao(vfile); if (!(s <= LIM.videoSeg + 1)) return fala(`Vídeo com mais de ${LIM.videoSeg} segundos. Grave um mais curto.`);
      }
      bt.disabled = true; bt.textContent = "Enviando…";
      try {
        const id = `${user.uid}_${K}`;
        if (minha) await apagarMinha();  // refazer: tira fotos/vídeo antigos
        const pedido = await pedidoComEstaPeca();
        await setDoc(doc(db, "avaliacoes", id), { uid: user.uid, sku: SKU.slice(0, 40), chave: K, produto: NOME.slice(0, 90), nome, estrelas: n, texto,
          fotos: fotos.map(x => x.mini), video: !!vfile, uso_fotos: $("#avuso").checked, ...(pedido ? { pedido } : {}), status: "pendente", criado: serverTimestamp() });
        for (let i = 0; i < fotos.length; i++) await setDoc(doc(db, "avaliacoes", id, "fotos", String(i)), { img: fotos[i].img });
        if (vfile) { const { m, s } = await store(); await m.uploadBytes(m.ref(s, `avaliacoes/${id}/video`), vfile, { contentType: vfile.type || "video/mp4" }); }
        minha = { status: "pendente", fotos: fotos.length, video: !!vfile }; delete f.dataset.editar;
        f.innerHTML = `<p class="avok" style="display:inline-block">Recebemos sua avaliação. Obrigado!</p><p class="note">Ela aparece aqui depois que a loja conferir.</p>`;
      } catch (e) { bt.disabled = false; bt.textContent = "Enviar avaliação"; fala("Não deu para enviar agora. Tente de novo ou mande no WhatsApp."); }
    };
  }

  async function apagarMinha() {
    const id = `${user.uid}_${K}`;
    for (let i = 0; i < LIM.fotos; i++) await deleteDoc(doc(db, "avaliacoes", id, "fotos", String(i))).catch(() => {});
    if (minha && minha.video) { try { const { m, s } = await store(); await m.deleteObject(m.ref(s, `avaliacoes/${id}/video`)); } catch (e) {} }
    await deleteDoc(doc(db, "avaliacoes", id));
  }

  onAuthStateChanged(auth, async u => {
    user = u; minha = null;
    if (u) { try { const s = await getDoc(doc(db, "avaliacoes", `${u.uid}_${K}`)); if (s.exists()) { const d = s.data(); minha = { status: d.status, video: d.video === true }; } } catch (e) {} }
    if (carregou) form();
  });

  // só busca as avaliações quando o cliente rola até elas (economiza leitura do Firebase)
  const abrir = () => { if (!carregou) { listar(); form(); } };
  if ("IntersectionObserver" in window) { const io = new IntersectionObserver(es => { if (es.some(x => x.isIntersecting)) { io.disconnect(); abrir(); } }, { rootMargin: "300px" }); io.observe(box); }
  else abrir();
  $("#avir").onclick = () => { abrir(); setTimeout(() => $("#avform").scrollIntoView({ behavior: "smooth", block: "start" }), 50); };
}

if (box) iniciar();  // no fim: as funções e limites acima já existem
