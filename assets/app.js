// Loja Dias Peças: carrinho, filtros do catálogo e pedido pelo WhatsApp.
// Depende de window.LOJA (gerado em assets/loja.js pelo build.py).
(function(){
  const L = window.LOJA, P = L.produtos, C = L.config;
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const brl = v => v.toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase();
  let cart = {};
  try{ cart = JSON.parse(localStorage.getItem("dias-cart")||"{}") }catch(e){}
  const save = () => { try{ localStorage.setItem("dias-cart",JSON.stringify(cart)) }catch(e){} };
  const count = () => Object.values(cart).reduce((a,b)=>a+b,0);
  const badge = () => $$(".cartcount").forEach(b=>b.textContent=count());


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
    const b = e.target.closest("[data-add]"); if(!b) return;
    const s = b.dataset.add; cart[s]=(cart[s]||0)+1; save(); badge();
    const t = b.textContent; b.textContent = "Adicionado ✓"; setTimeout(()=>b.textContent=t, 900);
  });

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
      P.filter(p=>t==="todos"||p.tipo===t).forEach(p=>p.modelos.forEach(m=>set.add(m)));
      veic.innerHTML = `<option value="">Todos os veículos</option>` + [...set].sort().map(m=>`<option>${m}</option>`).join("");
    };
    const apply = () => {
      const terms = norm(q.value.trim()).split(/\s+/).filter(Boolean), t=tipo.value, v=veic.value;
      let n=0;
      $$("#grid .card").forEach(c=>{
        const p = P.find(x=>x.sku===c.dataset.sku);
        const ok = (t==="todos"||p.tipo===t) && (cat==="todas"||p.categoria===cat)
          && (!v || p.modelos.includes(v))
          && terms.every(w => norm(p.nome+" "+p.sku+" "+p.marca+" "+p.veiculos.join(" ")).includes(w));
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
    const upd = () => { const c = C.cidades.find(x=>x.slug===shipSel.value);
      out.innerHTML = c ? `Frete: <b>${brl(c.normal)}</b>${(c.gratis_acima||C.frete_gratis_acima)?` (grátis a partir de ${brl(c.gratis_acima||C.frete_gratis_acima)})`:""}. Pedido até ${C.corte_mesmo_dia}: entrega até as ${C.entrega_ate} do mesmo dia. Depois disso, no dia seguinte.` : "Escolha a cidade para ver o frete."; };
    shipSel.addEventListener("change", upd); upd();
  }

  // carrinho
  const lines = $("#lines");
  if(lines){
    $("#city").innerHTML = `<option value="">Escolha a cidade</option>` + C.cidades.map(c=>`<option value="${c.slug}">${c.nome}</option>`).join("");
    const totals = () => {
      const items = Object.entries(cart).map(([s,q])=>({p:P.find(p=>p.sku===s),q})).filter(i=>i.p);
      const sub = items.reduce((a,i)=>a+i.p.preco*i.q,0);
      const pix = true;
      const ship = $('input[name="ship"]:checked').value;
      const city = C.cidades.find(c=>c.slug===$("#city").value);
      const lim = city ? (city.gratis_acima||C.frete_gratis_acima) : null;
      const gratis = !!(lim && sub>=lim);
      const frete = ship==="retirada"||gratis?0:(city?city[ship]:null);
      const desc = pix ? sub*C.desconto_pix : 0;
      return {items,sub,desc,frete,ship,city,pix,gratis,lim,total:sub-desc+(frete||0)};
    };
    const refresh = () => {
      const t = totals(); badge();
      lines.innerHTML = t.items.length ? t.items.map(i=>`
        <div class="line"><a href="${i.p.url}">${i.p.nome}</a><b>${brl(i.p.preco*i.q)}</b>
          <span class="qty"><button type="button" data-dec="${i.p.sku}" aria-label="Diminuir">−</button><span>${i.q}</span><button type="button" data-inc="${i.p.sku}" aria-label="Aumentar">+</button></span></div>`).join("")
        : `<p class="note">Seu carrinho está vazio. <a href="catalogo.html">Ver peças</a></p>`;
      $("#feeN").textContent = t.gratis?"Grátis":t.city?brl(t.city.normal):"escolha a cidade";
      $("#tot").innerHTML = `<span>Peças</span><span>${brl(t.sub)}</span>`
        + (t.desc?`<span>Desconto Pix</span><span>− ${brl(t.desc)}</span>`:"")
        + `<span>Entrega</span><span>${t.gratis?"Grátis":t.frete===null?"—":brl(t.frete)}</span>`
        + (t.lim&&!t.gratis&&t.items.length&&t.ship!=="retirada"?`<span class="note" style="grid-column:1/-1">Faltam ${brl(t.lim-t.sub)} para frete grátis em ${t.city.nome}.</span>`:"")
        + `<span class="big">Total</span><span class="big">${brl(t.total)}</span>`;
      const ent = t.ship!=="retirada";
      $("#addrbox").hidden = !ent; $("#citybox").hidden = !ent;
      let err = "";
      if(!t.items.length) err = "Adicione pelo menos uma peça.";
      else if(t.items.every(i=>i.p.addon) && t.sub < (C.frete_gratis_acima||0)) err = `Essas são peças de complemento. Junte com outra peça ou complete ${brl(C.frete_gratis_acima)}.`;
      else if(ent && !t.city) err = "Escolha a cidade para calcular a entrega.";
      else if(ent && !$("#addr").value.trim()) err = "Informe o endereço de entrega.";
      else if(!$("#name").value.trim()) err = "Informe seu nome.";
      $("#err").hidden = !err; $("#err").textContent = err;
      const send = $("#send"); send.setAttribute("aria-disabled", !!err);
      $("#pixbox").hidden = !!err;
      if(err){ send.href = "#"; return; }
      const txid = "LD" + Date.now().toString(36).toUpperCase().slice(-8);
      $("#pixcode").value = pixCode(t.total, txid);
      const msg = [`*Pedido Loja Dias* (${txid})`, `Cliente: ${$("#name").value.trim()}`,
        ...t.items.map(i=>`• ${i.q}x ${i.p.nome} (${i.p.sku}) = ${brl(i.p.preco*i.q)}`),
        `Peças: ${brl(t.sub)}`, t.desc?`Desconto Pix: -${brl(t.desc)}`:null,
        `Entrega: ${ent?"motoboy para "+t.city.nome:"retirada"} = ${t.gratis?"grátis":brl(t.frete||0)}`,
        ent?`Endereço: ${$("#addr").value.trim()}`:null,
        `Pagamento: Pix (copia e cola) R$ ${t.total.toFixed(2)}`, `*Total: ${brl(t.total)}*`].filter(Boolean).join("\n");
      send.href = `https://wa.me/${C.whatsapp}?text=${encodeURIComponent(msg)}`;
      ultimo = {txid, total:t.total, cidade: ent?t.city.slug:"retirada", itens:t.items.map(i=>({sku:i.p.sku,nome:i.p.nome,qtd:i.q,preco:i.p.preco}))};
    };
    let ultimo = null;
    $("#send").addEventListener("click", ()=>{ if(ultimo && window.LojaConta) window.LojaConta.salvarPedido(ultimo).catch(()=>{}); });
    $("#pixcopy").addEventListener("click", async e=>{ const ta=$("#pixcode");
      try{ await navigator.clipboard.writeText(ta.value); e.target.textContent="Copiado ✓"; }catch(_){ ta.select(); e.target.textContent="Selecione e copie"; }
      setTimeout(()=>e.target.textContent="Copiar código Pix",1500); });
    lines.addEventListener("click", e=>{ const d=e.target.dataset;
      if(d.inc) cart[d.inc]++; else if(d.dec){ cart[d.dec]--; if(cart[d.dec]<=0) delete cart[d.dec]; } else return;
      save(); refresh(); });
    $$(".cartpage input,.cartpage select").forEach(el=>el.addEventListener("input", refresh));
    refresh();
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

  badge();
})();
