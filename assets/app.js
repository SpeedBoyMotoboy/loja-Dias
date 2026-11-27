// Loja Dias Peças: carrinho, filtros do catálogo e pedido pelo WhatsApp.
// Depende de window.LOJA (gerado em assets/loja.js pelo build.py).
(function(){
  const L = window.LOJA, P = L.produtos, C = L.config;
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  // CNPJ: confere os 2 dígitos verificadores (pedido de nota fiscal no carrinho)
  const cnpjOk = c => { if(!/^\d{14}$/.test(c) || /^(\d)\1+$/.test(c)) return false;
    const dv = n => { let s=0, w=n-7; for(let i=0;i<n;i++){ s += +c[i]*w--; if(w<2) w=9; } const r=s%11; return r<2?0:11-r; };
    return dv(12)===+c[12] && dv(13)===+c[13]; };
  const brl = v => v.toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase();
  let cart = {};
  try{ cart = JSON.parse(localStorage.getItem("dias-cart")||"{}") }catch(e){}
  const save = () => { try{ localStorage.setItem("dias-cart",JSON.stringify(cart)) }catch(e){} };
  const count = () => Object.values(cart).reduce((a,b)=>a+b,0);
  const badge = () => $$(".cartcount").forEach(b=>b.textContent=count());
  // contador de visitas (Google Analytics): só manda evento quando o config tiver o ID
  // Indicação (25/11): quem abre lojadias.com.br/?ref=CODIGO fica com o desconto por alguns dias neste celular.
  // Desconto só nas peças marcadas "ind" pelo build (as que ainda deixam o lucro mínimo). Não vale no próprio link.
  const IND = C.ind;
  const okRef = s => /^[A-Z0-9]{3,12}$/.test(s || "");
  const lsGet = k => { try{ return localStorage.getItem(k) }catch(e){ return null } };
  const lsSet = (k,v) => { try{ v===null ? localStorage.removeItem(k) : localStorage.setItem(k,v) }catch(e){} };
  let meuRef = null; try{ meuRef = JSON.parse(lsGet("dias-meu-ref")||"null"); if(meuRef && !okRef(meuRef.c)) meuRef = null; }catch(e){}
  if(IND){ const q = (new URLSearchParams(location.search).get("ref")||"").toUpperCase().replace(/[^A-Z0-9]/g,"");
    if(okRef(q)) lsSet("dias-ref", JSON.stringify({c:q, t:Date.now()})); }
  const refAtivo = () => { if(!IND) return null; let r = null; try{ r = JSON.parse(lsGet("dias-ref")||"null") }catch(e){}
    if(!r || !okRef(r.c) || !(Date.now()-r.t < IND.dias*864e5)) return null;
    return (meuRef && meuRef.c===r.c) ? null : r.c; };
  const pctInd = IND ? Math.round(IND.desconto*100)+"%" : "", pctCom = IND ? Math.round(IND.comissao*100)+"%" : "";
  const linkCom = path => (C.site||location.origin) + "/" + (path||"") + (meuRef ? ((path||"").includes("?")?"&":"?") + "ref=" + meuRef.c : "");
  { const r = refAtivo(), top = document.querySelector("header.top");
    if(r && top && !$("#lines") && IND.desconto>0){ const f = document.createElement("div"); f.className = "indfaixa";
      f.innerHTML = `Indicação de <b></b>: ${pctInd} de desconto já aparece no carrinho`; f.querySelector("b").textContent = r; top.before(f); } }
  // botão "Compartilhar esta peça": vai pelo WhatsApp, com o link da pessoa quando ela já criou o dela
  document.addEventListener("click", e => { const b = e.target.closest("[data-share]"); if(!b) return;
    const msg = (b.dataset.shareTxt||"") + (meuRef && IND.desconto>0 ? `. Pelo meu link tem ${pctInd} de desconto` : "") + ":\n" + linkCom(b.dataset.share);
    window.open("https://wa.me/?text=" + encodeURIComponent(msg), "_blank", "noopener"); });

  const ga = (nome, dados) => { try{ if(C.ga && window.gtag) gtag("event", nome, Object.assign({send_to:C.ga}, dados||{})); }catch(e){} };


  // Pix copia e cola (BR Code estático, padrão do Banco Central) com valor fixo
  const tlv = (id,v) => id + String(v.length).padStart(2,"0") + v;
  const clean = (s,n) => s.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9 ]/g,"").toUpperCase().slice(0,n);
  const crc16 = s => { let c=0xFFFF; for(const ch of s){ c^=ch.charCodeAt(0)<<8; for(let i=0;i<8;i++) c = (c&0x8000)?((c<<1)^0x1021)&0xFFFF:(c<<1)&0xFFFF; } return c.toString(16).toUpperCase().padStart(4,"0"); };
  const pixCode = (valor, txid) => {
    const p = C.pix;
    const s = tlv("00","01") + tlv("26", tlv("00","br.gov.bcb.pix") + tlv("01",p.chave))
      + tlv("52","0000") + tlv("53","986") + tlv("54",valor.toFixed(2)) + tlv("58","BR")
      + tlv("59",clean(p.nome,25)) + tlv("60",clean(p.cidade,15)) + tlv("62", tlv("05",txid)) + "6304";
    return s + crc16(s);
  };
  window.pixCode = pixCode;

  // botões "Adicionar"
  document.addEventListener("click", e => {
    const c = e.target.closest("[data-buy]");
    const enc = x => { const q = P.find(p=>p.sku===x); return !q || q.enc; };
    if(c && enc(c.dataset.buy)) return;
    if(c){ const s = c.dataset.buy; if(!cart[s]) cart[s]=1; save(); ga("add_to_cart", {items:[{item_id:s}]}); location.href="carrinho.html"; return; }  // comprar agora: vai direto fechar o pedido
    const b = e.target.closest("[data-add]"); if(!b || enc(b.dataset.add)) return;
    const s = b.dataset.add; cart[s]=(cart[s]||0)+1; save(); badge(); bar();
    ga("add_to_cart", {items:[{item_id:s}]});
    document.dispatchEvent(new Event("dias-cart"));
    const t = b.textContent; b.textContent = "Adicionado ✓"; setTimeout(()=>b.textContent=t, 900);
  });

  // Prazo com relógio (hora de Brasília): quanto falta para o corte do mesmo dia. Domingo e depois do corte, diz quando chega.
  const corte = parseInt(C.corte_mesmo_dia,10) || 12;
  const prazo = () => {
    const p = new Intl.DateTimeFormat("en-US",{timeZone:"America/Sao_Paulo",weekday:"short",hour:"2-digit",minute:"2-digit",hour12:false}).formatToParts(new Date());
    const g = t => p.find(x=>x.type===t).value;
    const dia = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].indexOf(g("weekday")), min = (+g("hour")%24)*60 + (+g("minute"));
    const falta = corte*60 - min;
    if(dia>=1 && dia<=6 && falta>0){ const h=Math.floor(falta/60), m=falta%60;
      return `Peça em até <b>${h?h+"h":""}${String(m).padStart(h?2:1,"0")}${h?"":" min"}</b> e receba hoje até as ${C.entrega_ate}`; }
    const quando = (dia===6 || dia===0) ? "segunda-feira" : "amanhã";
    return `Pedido agora chega <b>${quando}</b>, até as ${C.entrega_ate}`;
  };
  const tick = () => $$("[data-corte]").forEach(el => el.innerHTML = prazo());
  if($("[data-corte]")){ tick(); setInterval(tick, 30000); }

  // Barra fixa: na página da peça mostra o preço e "Comprar agora"; com peça no carrinho, mostra o total e "Fechar pedido".
  const lim0 = Math.min(...C.cidades.map(c=>c.gratis_acima||C.frete_gratis_acima||Infinity));
  const limMax = Math.max(...C.cidades.map(c=>c.gratis_acima||C.frete_gratis_acima||0));
  // Carro (Mesa Pauta 6/6B): pedido com peça de carro usa o frete de carro; peça grande ou carrinho pesado vai de Fiorino
  const CR = C.carro || null;
  const crG = slug => (CR && CR.gratis_cidade && slug && CR.gratis_cidade[slug]) || (CR && CR.gratis_acima);
  const temCarro = its => !!CR && its.some(i=>i.p.tipo==="carro");
  const vaiFiorino = its => !!CR && (its.some(i=>i.p.fiorino) || its.reduce((a,i)=>a+(i.p.kg||0)*i.q,0) > (CR.fiorino_kg||Infinity));
  for(const s of Object.keys(cart)){ const q = P.find(p=>p.sku===s); if(q && q.enc) delete cart[s]; }  // encomenda não vai para o carrinho
  const itensCart = () => Object.entries(cart).map(([s,q])=>({p:P.find(p=>p.sku===s),q})).filter(i=>i.p);
  const subtotal = () => Object.entries(cart).reduce((a,[s,q])=>{ const p=P.find(x=>x.sku===s); return a+(p?p.preco*q:0); },0);
  function bar(){
    const el = $("#buybar"); if(!el || $("#lines")) return;
    const n = count(), sub = subtotal(), pd = $("[data-produto]");
    const p = pd && P.find(x=>x.sku===pd.dataset.produto);
    let html = "", soCel = false;
    if(n){
      const its = itensCart(), fio = vaiFiorino(its), lc = temCarro(its) ? CR.gratis_acima : 0;
      const falta = fio ? "vai de Fiorino" : lc ? (sub<lc ? `Faltam ${brl(lc-sub)} para frete grátis` : "Frete grátis") : !isFinite(lim0) ? "" : sub<lim0 ? `Faltam ${brl(lim0-sub)} para frete grátis` : sub>=limMax ? "Frete grátis" : "Frete grátis em Vitória, Vila Velha e Cariacica";
      html = `<div class="txt"><span>${n} ${n>1?"peças":"peça"} no carrinho${falta?" · "+falta:""}</span><b>${brl(sub)}</b></div><a class="btn" href="carrinho.html">Fechar pedido</a>`;
    } else if(p){
      soCel = true;
      html = `<div class="txt"><span>no Pix</span><b>${brl(p.preco)}</b></div><button class="btn" type="button" data-buy="${p.sku}">Comprar agora</button>`;
    }
    el.hidden = !html; el.innerHTML = html ? `<div class="in">${html}</div>` : "";
    el.classList.toggle("so-celular", soCel);
    document.body.classList.toggle("hasbar", !!html); document.body.classList.toggle("so-celular", soCel);
  }

  // filtros do catálogo
  const grid = $("#grid");
  if(grid){
    const q=$("#q"), tipo=$("#tipo"), veic=$("#veic"), cats=$("#cats");
    const params = new URLSearchParams(location.search);
    let cat = params.get("cat") || "todas";
    if(params.get("q")) q.value = params.get("q");
    if(params.get("tipo")) tipo.value = params.get("tipo");
    const fillVeic = () => {
      const t = tipo.value, set = new Set();
      P.filter(p=>t==="todos"||p.tipo===t).forEach(p=>(p.fams||[]).forEach(m=>set.add(m)));
      veic.innerHTML = `<option value="">${t==="carro"?"Qual é o seu carro?":t==="todos"&&P.some(p=>p.tipo==="carro")?"Qual é o seu veículo?":"Qual é a sua moto?"}</option>` + [...set].sort().map(m=>`<option>${m}</option>`).join("");
    };
    const apply = () => {
      const terms = norm(q.value.trim()).split(/\s+/).filter(Boolean), t=tipo.value, v=veic.value;
      let n=0;
      $$("#grid .card").forEach(c=>{
        const p = P.find(x=>x.sku===c.dataset.sku);
        const ok = (t==="todos"||p.tipo===t) && (cat==="todas"||p.categoria===cat)
          && (!v || (p.fams||[]).includes(v) || p.universal)
          && terms.every(w => norm(p.nome+" "+(p.nome_real||"")+" "+p.sku+" "+p.marca+" "+p.veiculos.join(" ")+" "+(p.fams||[]).join(" ")+(p.categoria==="transmissao"?" transmissao coroa pinhao corrente":"")).includes(w));
        c.hidden = !ok; if(ok) n++;
      });
      $("#none").hidden = n>0;
      $$("#cats button").forEach(b=>b.setAttribute("aria-pressed", b.dataset.c===cat));
    };
    cats.addEventListener("click", e=>{ const b=e.target.closest("button"); if(!b) return; cat=b.dataset.c; apply(); });
    q.addEventListener("input", apply); veic.addEventListener("change", apply);
    tipo.addEventListener("change", ()=>{ fillVeic(); apply(); });
    fillVeic(); apply();
  }

  // frete na página do produto
  const shipSel = $("#shipcity");
  if(shipSel){
    const out = $("#shipout");
    const pd = $("[data-produto]"), pp = pd && P.find(x=>x.sku===pd.dataset.produto);
    const upd = () => { const c = C.cidades.find(x=>x.slug===shipSel.value);
      if(c && CR && pp && pp.tipo==="carro"){
        out.innerHTML = pp.fiorino ? `Peça grande, vai de Fiorino: frete <b>${brl(CR.fiorino[c.slug])}</b>, sem frete grátis. Pix antes da entrega.`
          : `Frete de carro: <b>${brl(CR.frete[c.slug])}</b> (grátis a partir de ${brl(crG(c.slug))}). Entrega no mesmo dia de segunda a sexta, para pedido até ${C.corte_mesmo_dia}.`;
        return; }
      out.innerHTML = c ? `Frete: <b>${brl(c.normal)}</b>${(c.gratis_acima||C.frete_gratis_acima)?` (grátis a partir de ${brl(c.gratis_acima||C.frete_gratis_acima)})`:""}. Pedido até ${C.corte_mesmo_dia}: entrega até as ${C.entrega_ate} do mesmo dia. Depois disso, no dia seguinte.` : "Escolha a cidade para ver o frete."; };
    shipSel.addEventListener("change", upd); upd();
  }

  // carrinho
  // catálogo aberto em ?tipo=carro: a escolha do topo marca Carro
  if(new URLSearchParams(location.search).get("tipo")==="carro") $$(".veic a").forEach(el=>el.setAttribute("aria-current", el.textContent.startsWith("Carro") ? "true" : "false"));
  const lines = $("#lines");
  if(lines){
    $("#city").innerHTML = `<option value="">Escolha a cidade</option>` + C.cidades.map(c=>`<option value="${c.slug}">${c.nome}</option>`).join("");
    const totals = () => {
      const items = Object.entries(cart).map(([s,q])=>({p:P.find(p=>p.sku===s),q})).filter(i=>i.p);
      const sub = items.reduce((a,i)=>a+i.p.preco*i.q,0);
      const pix = true;
      // Mesa 25/11: peça cara (giro lento) só com Pix antecipado
      const carro = temCarro(items), fior = vaiFiorino(items);
      const caro = (C.antecipado && items.some(i=>i.p.preco>=C.antecipado)) || fior, rEnt = $('input[name="pay"][value="entrega"]');
      if(rEnt){ rEnt.disabled = !!caro; if(caro && rEnt.checked){ rEnt.checked = false; const rAg = $('input[name="pay"][value="agora"]'); if(rAg) rAg.checked = true; }
        const pe = $("#payentrega"); if(pe) pe.textContent = fior ? "Não vale para entrega de Fiorino: o Pix é antes, depois que a loja confere a placa." : caro ? `Não vale para peça de ${brl(C.antecipado)} ou mais: ela é separada só para você, então o Pix é antes.` : (C.entrega_limite ? `Até ${brl(C.entrega_limite)} você paga tudo quando o motoboy chegar. Acima disso, paga ${brl(C.entrega_sinal)} de sinal no Pix agora e o resto na entrega. Às 11h45 a loja confirma seu endereço no WhatsApp.` : "Você paga o Pix quando o motoboy chegar. Ele entrega a peça assim que o Pix cair na conta da loja."); }
      const payEl = $('input[name="pay"]:checked'), naEntrega = !!(payEl && payEl.value==="entrega");
      const ship = $('input[name="ship"]:checked').value;
      const city = C.cidades.find(c=>c.slug===$("#city").value);
      const lim = fior ? null : carro ? crG(city&&city.slug) : city ? (city.gratis_acima||C.frete_gratis_acima) : null;
      const fidel = !fior && !!(window.LojaConta && window.LojaConta.freteFidelidade && window.LojaConta.freteFidelidade());
      const gratis = !fior && (fidel || !!(lim && sub>=lim));
      const base = city ? (fior ? CR.fiorino[city.slug] : carro ? CR.frete[city.slug] : city[ship==="retirada"?"normal":ship]) : null;
      const frete = ship==="retirada"||gratis?0:base;
      const desc = pix ? sub*C.desconto_pix : 0;
      const ref = refAtivo(), baseInd = ref ? items.filter(i=>i.p.ind).reduce((a,i)=>a+i.p.preco*i.q,0) : 0;
      const descInd = Math.round(baseInd*(IND?IND.desconto:0)*100)/100, comInd = Math.round(baseInd*(IND?IND.comissao:0)*100)/100;  // frete grátis continua contando pelo valor das peças sem o desconto
      return {items,sub,desc,descInd,comInd,ref,frete,base,carro,fior,ship,city,pix,gratis,fidel,lim,naEntrega,total:Math.round((sub-desc-descInd+(frete||0))*100)/100};
    };
    const refresh = () => {
      const t = totals(); badge();
      lines.innerHTML = t.items.length ? t.items.map(i=>`
        <div class="line"><a class="lfoto" href="${i.p.url}" tabindex="-1" aria-hidden="true">${i.p.foto?`<img src="${i.p.foto}" alt="" loading="lazy" width="64" height="64">`:""}</a><a class="lnome" href="${i.p.url}">${i.p.nome}</a><b>${brl(i.p.preco*i.q)}${t.ref&&i.p.ind&&IND.desconto>0?` <small class="indtag">−${pctInd}</small>`:""}</b>
          <span class="qty"><button type="button" data-dec="${i.p.sku}" aria-label="Diminuir">−</button><span>${i.q}</span><button type="button" data-inc="${i.p.sku}" aria-label="Aumentar">+</button></span></div>`).join("")
        : `<p class="note">Seu carrinho está vazio. <a href="catalogo.html">Ver peças</a></p>`;
      $("#feeN").textContent = t.gratis?"Grátis":t.city?brl(t.base):"escolha a cidade";
      const sn = $("#shipNnota"), st = $("#shipNtit");
      if(sn){ if(!sn.dataset.orig) sn.dataset.orig = sn.textContent;
        sn.textContent = t.fior ? "Peça grande: entrega agendada, sem frete grátis" : t.carro ? `Seg. a sex., pedido até ${C.corte_mesmo_dia}. Frete grátis acima de ${brl(CR.gratis_acima)}` : sn.dataset.orig;
        if(st && st.firstChild) st.firstChild.textContent = t.fior ? "Fiorino" : "Motoboy"; }
      const pb = $("#placabox"); if(pb) pb.hidden = !t.carro;
      const cn = $("#carronota"); if(cn){ cn.hidden = !t.carro;
        cn.textContent = t.carro ? (t.fior ? "Peça grande vai de Fiorino, com entrega agendada no mesmo dia ou no seguinte. " : "Peça de carro: entrega no mesmo dia de segunda a sexta. Pedido de sábado chega na segunda até as 14h. ")
          + "Você envia o pedido, a loja confere a peça pela placa no WhatsApp e só então manda o Pix." : ""; }
      $("#tot").innerHTML = `<span>Peças</span><span>${brl(t.sub)}</span>`
        + (t.desc?`<span>Desconto Pix</span><span>− ${brl(t.desc)}</span>`:"")
        + (t.descInd?`<span>Desconto indicação (${t.ref})</span><span>− ${brl(t.descInd)}</span>`:"")
        + `<span>Entrega${t.fior?" (Fiorino)":""}</span><span>${t.fidel?"Grátis (6º pedido)":t.gratis?"Grátis":t.frete===null?"—":brl(t.frete)}</span>`
        + `<span class="big">Total</span><span class="big">${brl(t.total)}</span>`;
      const ent = t.ship!=="retirada";
      $("#addrbox").hidden = !ent; $("#citybox").hidden = !ent;
      // meta do frete grátis: usa o valor da cidade escolhida; sem cidade, o menor valor (Vitória, Vila Velha, Cariacica)
      const meta = $("#meta"), sug = $("#sugest"), alvo = t.fior ? 0 : t.lim || (isFinite(lim0)?lim0:0);
      const mostra = ent && !t.fidel && alvo>0 && t.items.length>0;
      meta.hidden = !mostra; sug.hidden = true;
      if(mostra){
        const falta = alvo - t.sub, onde = t.city ? ` em ${t.city.nome}` : "";
        meta.classList.toggle("ok", falta<=0);
        meta.innerHTML = falta>0
          ? `<span>Faltam ${brl(falta)} para o frete grátis${onde}</span><div class="trilho"><i style="width:${Math.max(6,Math.round(t.sub/alvo*100))}%"></i></div>`
          : `<span>Frete grátis liberado${onde}${(t.city||t.carro||t.sub>=limMax)?"":" (Vitória, Vila Velha e Cariacica)"}</span>`;
        if(falta>0){
          const ordem = ["freio","filtro","ignicao","transmissao","pneu","eletrica","cabo","acessorio"], rank = p => { const i = ordem.indexOf(p.categoria); return i<0?9:i; };  // o que mais se troca vem primeiro
          const no = new Set(t.items.map(i=>i.p.sku)), fams = new Set(t.items.flatMap(i=>i.p.fams||[])), cats = new Set(t.items.map(i=>i.p.categoria));
          const cand = P.filter(p=>!no.has(p.sku) && !p.enc && p.foto && p.categoria!=="kit" && (!t.carro || p.tipo==="carro") && ((p.fams||[]).some(f=>fams.has(f)) || p.universal))
            .sort((a,b)=> (cats.has(a.categoria)-cats.has(b.categoria)) || (((b.fams||[]).some(f=>fams.has(f)))-((a.fams||[]).some(f=>fams.has(f)))) || (rank(a)-rank(b)) || (Math.abs(a.preco-falta)-Math.abs(b.preco-falta)));
          const pick = [], usados = new Set();
          for(const p of cand){ if(usados.has(p.categoria)) continue; pick.push(p); usados.add(p.categoria); if(pick.length===3) break; }
          sug.hidden = !pick.length;
          sug.innerHTML = pick.length ? `<span class="lbl">Leve junto e feche o frete grátis</span>` + pick.map(p=>`<div class="s"><img src="${p.foto}" alt="" loading="lazy"><span><a href="${p.url}">${p.nome}</a><b>${brl(p.preco)}</b></span><button class="add" type="button" data-add="${p.sku}">Adicionar</button></div>`).join("") : "";
        }
      }
      let err = "";
      if(!t.items.length) err = "Adicione pelo menos uma peça.";
      else if(t.items.every(i=>i.p.addon) && t.sub < (C.addon_min||C.frete_gratis_acima||0)) err = `Essas são peças de complemento. Junte com outra peça ou complete ${brl(C.addon_min||C.frete_gratis_acima)}.`;
      else if(ent && !t.city) err = "Escolha a cidade para calcular a entrega.";
      else if(ent && !$("#addr").value.trim()) err = "Informe o endereço de entrega.";
      else if(t.carro && !/^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/.test(($("#placa").value||"").toUpperCase().replace(/[^A-Z0-9]/g,""))) err = "Informe a placa do carro (ex.: ABC1D23).";
      else if(!$("#name").value.trim()) err = "Informe seu nome.";
      else if($("#tel") && $("#tel").value.replace(/\D/g,"").length<10) err = "Informe seu WhatsApp com DDD.";
      const nf = $("#nfq") && $("#nfq").checked;
      if($("#nfbox")) $("#nfbox").hidden = !nf;
      const nfCnpj = nf ? $("#nfcnpj").value.replace(/\D/g,"") : "", nfRazao = nf ? $("#nfrazao").value.trim().slice(0,120) : "", nfMail = nf ? $("#nfmail").value.trim().slice(0,120) : "";
      if(!err && nf){
        if(!cnpjOk(nfCnpj)) err = "CNPJ inválido. Confira os 14 números.";
        else if(nfRazao.length < 3) err = "Informe a razão social da empresa.";
        else if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(nfMail)) err = "Informe o e-mail para a nota.";
      }
      $("#err").hidden = !err; $("#err").textContent = err;
      const send = $("#send"); send.setAttribute("aria-disabled", !!err);
      // trava do Pix na entrega (Luan, 25/11): acima do limite, sinal no Pix agora e o resto na entrega
      const sinal = t.naEntrega && C.entrega_limite && C.entrega_sinal && t.total > C.entrega_limite ? Math.min(C.entrega_sinal, t.total) : 0;
      $("#pixbox").hidden = !!err || (t.naEntrega && !sinal) || t.carro;  // carro: Pix só depois de conferir a placa
      const pn = $("#pixnota"); if(pn) pn.textContent = sinal ? `Pague agora só o sinal de ${brl(sinal)}. O resto, ${brl(t.total-sinal)}, você paga no Pix quando o motoboy chegar. Depois envie o pedido com o comprovante.` : "Pague no app do seu banco (Pix › Copia e cola) e depois envie o pedido com o comprovante.";
      send.textContent = t.carro ? "Enviar pedido no WhatsApp" : sinal ? "Enviar pedido e comprovante do sinal no WhatsApp" : t.naEntrega ? "Enviar pedido no WhatsApp" : "Enviar pedido e comprovante no WhatsApp";
      if(err){ send.href = "#"; return; }
      const txid = "LD" + Date.now().toString(36).toUpperCase().slice(-8) + Math.random().toString(36).toUpperCase().replace(/[^A-Z0-9]/g,"").slice(0,3).padEnd(3,"0");
      const tel = $("#tel") ? $("#tel").value.trim().slice(0,20) : "";
      $("#pixcode").value = pixCode(sinal || t.total, txid);
      const pv = $("#pixvalor"); if(pv) pv.textContent = brl(sinal || t.total);
      const msg = [`*Pedido Loja Dias* (${txid})`, `Cliente: ${$("#name").value.trim()}`, tel?`WhatsApp: ${tel}`:null,
        ...t.items.map(i=>`• ${i.q}x ${i.p.nome} (${i.p.sku}) = ${brl(i.p.preco*i.q)}`),
        `Peças: ${brl(t.sub)}`, t.desc?`Desconto Pix: -${brl(t.desc)}`:null,
        t.ref?`Indicado por: ${t.ref}${t.descInd?` (desconto -${brl(t.descInd)})`:""}${t.comInd?` · comissão do indicador: ${brl(t.comInd)}`:""}`:null,
        `Entrega: ${ent?(t.fior?"Fiorino para ":"motoboy para ")+t.city.nome:"retirada"} = ${t.fidel?"grátis (6º pedido fidelidade)":t.gratis?"grátis":brl(t.frete||0)}`,
        ent?`Endereço: ${$("#addr").value.trim()}`:null,
        t.carro?`Placa do carro: ${($("#placa").value||"").toUpperCase().replace(/[^A-Z0-9]/g,"")}`:null,
        t.fior?`Entrega de Fiorino (peça grande): Pix antecipado`:null,
        nf?`*Nota fiscal (NF-e)*: CNPJ ${nfCnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,"$1.$2.$3/$4-$5")} · ${nfRazao} · ${nfMail}`:null,
        t.carro ? `Pagamento: Pix ${t.naEntrega ? (sinal ? `(sinal de ${brl(sinal)} + ${brl(t.total-sinal)} na entrega)` : "na entrega") : `de ${brl(t.total)}`}, depois que a loja conferir a peça pela placa` : sinal ? `Pagamento: sinal de ${brl(sinal)} no Pix agora (comprovante anexo) + ${brl(t.total-sinal)} no Pix na entrega` : t.naEntrega ? `Pagamento: Pix na entrega (pago quando o motoboy chegar; a peça é entregue depois que o Pix cair)` : `Pagamento: Pix (copia e cola) R$ ${t.total.toFixed(2)}`, `*Total: ${brl(t.total)}*`].filter(Boolean).join("\n");
      send.href = `https://wa.me/${C.whatsapp}?text=${encodeURIComponent(msg)}`;
      ultimo = {txid, total:t.total, cidade: ent?t.city.slug:"retirada", pagamento: t.naEntrega?"entrega":"pix", ref:t.ref||"", itens:t.items.map(i=>({sku:i.p.sku,nome:i.p.nome,categoria:i.p.categoria,qtd:i.q,preco:i.p.preco})),
        sub:t.sub, frete:t.frete||0, desconto:Math.round(((t.desc||0)+(t.descInd||0))*100)/100,
        cliente:{nome:$("#name").value.trim(), telefone:tel, endereco: ent?$("#addr").value.trim():""},
        nf: nf ? {cnpj:nfCnpj, razao:nfRazao, email:nfMail} : null};
    };
    let ultimo = null;
    $("#send").addEventListener("click", e=>{
      if(e.currentTarget.getAttribute("aria-disabled")==="true"){ e.preventDefault(); return; }
      if(ultimo && window.LojaConta && window.LojaConta.registrarVenda) window.LojaConta.registrarVenda(ultimo).catch(()=>{});  // painel de pedidos da loja
      if(ultimo && window.LojaConta) window.LojaConta.salvarPedido(ultimo).catch(()=>{});
      // conversão do Google Ads (só quando o config tiver ID e label)
      if(ultimo) ga("purchase", {transaction_id:ultimo.txid, value:ultimo.total, currency:"BRL", items:ultimo.itens.map(i=>({item_id:i.sku, item_name:i.nome, item_category:i.categoria, quantity:i.qtd, price:i.preco}))});
      if(ultimo && C.ads && C.ads.id && C.ads.label && window.gtag) gtag("event","conversion",{send_to:`${C.ads.id}/${C.ads.label}`, value:ultimo.total, currency:"BRL", transaction_id:ultimo.txid});
    });
    $("#pixcopy").addEventListener("click", async e=>{ const ta=$("#pixcode");
      try{ await navigator.clipboard.writeText(ta.value); e.target.textContent="Copiado ✓"; }catch(_){ ta.select(); e.target.textContent="Selecione e copie"; }
      setTimeout(()=>e.target.textContent="Copiar código Pix",1500); });
    lines.addEventListener("click", e=>{ const d=e.target.dataset;
      if(d.inc) cart[d.inc]++; else if(d.dec){ cart[d.dec]--; if(cart[d.dec]<=0) delete cart[d.dec]; } else return;
      save(); refresh(); });
    $$(".cartpage input,.cartpage select").forEach(el=>el.addEventListener("input", refresh));
    document.addEventListener("dias-cart", refresh);
    refresh();
  }
  // página Indique e ganhe: cria o código (nome + 3 últimos números do WhatsApp), avisa a loja e mostra o link para compartilhar
  const ib = $("#indbox");
  if(ib && IND){
    const codigo = () => { const n = (norm($("#inome").value).toUpperCase().match(/[A-Z]+/)||[""])[0].slice(0,8), d = $("#itel").value.replace(/\D/g,"");
      return n.length>=2 && d.length>=10 ? n + d.slice(-3) : ""; };
    const mostrar = () => {
      $("#indlink").hidden = !meuRef; ib.hidden = !!meuRef;
      if(!meuRef) return;
      const link = linkCom(""), gr = C.frete_gratis_acima;
      $("#icod").textContent = meuRef.c; $("#ilink").value = link;
      const msg = `Peça de moto com entrega no mesmo dia na Grande Vitória (pedido até ${C.corte_mesmo_dia}).\n${IND.desconto>0?`Pelo meu link você ganha ${pctInd} de desconto:`:"Compre pelo meu link:"}\n${link}\n${C.na_entrega?"Pix agora ou na entrega":"Pagamento no Pix"}${gr?". Frete grátis acima de "+brl(gr):""}.`;
      $("#imsg").value = msg; $("#izap").href = "https://wa.me/?text=" + encodeURIComponent(msg);
      if(navigator.share){ $("#imais").hidden = false; $("#imais").onclick = () => navigator.share({text: msg}).catch(()=>{}); }
    };
    const upd = () => {
      const c = codigo(), pix = $("#ipix").value.trim();
      const err = !$("#inome").value.trim() ? "Informe seu nome." : $("#itel").value.replace(/\D/g,"").length<10 ? "Informe o WhatsApp com DDD." : !c ? "Use letras no nome." : pix.length<5 ? "Informe a chave Pix para receber." : "";
      $("#ierr").hidden = !err; $("#ierr").textContent = err;
      const a = $("#iativar"); a.setAttribute("aria-disabled", !!err);
      a.href = err ? "#" : `https://wa.me/${C.whatsapp}?text=` + encodeURIComponent([`*Quero ser indicador da Loja Dias*`, `Nome: ${$("#inome").value.trim().slice(0,60)}`,
        `WhatsApp: ${$("#itel").value.trim().slice(0,20)}`, `Chave Pix: ${pix.slice(0,80)}`, `Meu código: ${c}`].join("\n"));
    };
    ib.addEventListener("input", upd); upd();
    $("#iativar").addEventListener("click", e => { const c = codigo();
      if(e.currentTarget.getAttribute("aria-disabled")==="true"){ e.preventDefault(); $("#ierr").hidden = false; return; }
      meuRef = {c, t: Date.now()}; lsSet("dias-meu-ref", JSON.stringify(meuRef)); setTimeout(mostrar, 200); });
    const copiar = async (txt, b, volta) => { try{ await navigator.clipboard.writeText(txt); b.textContent = "Copiado ✓"; }catch(_){ b.textContent = "Selecione e copie"; } setTimeout(()=>b.textContent = volta, 1500); };
    $("#icopiar").addEventListener("click", e => copiar($("#ilink").value, e.target, "Copiar link"));
    $("#icopmsg").addEventListener("click", e => copiar($("#imsg").value, e.target, "Copiar mensagem"));
    $("#itrocar").addEventListener("click", () => { meuRef = null; lsSet("dias-meu-ref", null); mostrar(); });
    mostrar();
  }

  // formulário de pedido (modo vitrine, sem catálogo)
  const pf = $("#pedidoform");
  if(pf){
    const tp = new URLSearchParams(location.search).get("tipo");
    if(tp==="carro") $("#ptCarro").checked = true;
    const upd = () => {
      const tipo = $('input[name="ptipo"]:checked').value, v=$("#pveic").value.trim(), pc=$("#ppeca").value.trim(),
        cid=$("#pcid").value, b=$("#pbairro").value.trim(), n=$("#pnome").value.trim();
      let err = !v ? "Informe o modelo e o ano." : !pc ? "Informe a peça." : !cid ? "Escolha a cidade." : !n ? "Informe seu nome." : "";
      $("#perr").hidden = !err; $("#perr").textContent = err;
      const s = $("#psend"); s.setAttribute("aria-disabled", !!err);
      if(err){ s.href="#"; return; }
      const msg = [`*Pedido Loja Dias*`, `Peça de ${tipo}: ${pc}`, `Veículo: ${v}`, `Entrega: ${cid}${b?" - "+b:""}`, `Nome: ${n}`].join("\n");
      s.href = `https://wa.me/${C.whatsapp}?text=${encodeURIComponent(msg)}`;
    };
    pf.addEventListener("input", upd); pf.addEventListener("submit", e=>e.preventDefault()); upd();
  }

  // galeria de fotos na pagina da peca
  document.addEventListener("click", e => { const t = e.target.closest(".thumb"); if(!t) return;
    $("#fotomain").src = t.dataset.foto; $$(".thumb").forEach(x=>x.setAttribute("aria-pressed", x===t)); });

  badge(); bar();
  const cta = $(".cta");
  if(cta && "IntersectionObserver" in window){
    new IntersectionObserver(es => document.body.classList.toggle("cta-visivel", es[0].isIntersecting)).observe(cta);
  }
})();
