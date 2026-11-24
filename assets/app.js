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
      out.innerHTML = c ? `Frete: <b>${brl(c.normal)}</b>. Pedido até ${C.corte_mesmo_dia} chega hoje; depois, no dia seguinte.` : "Escolha a cidade para ver o frete."; };
    shipSel.addEventListener("change", upd); upd();
  }

  // carrinho
  const lines = $("#lines");
  if(lines){
    $("#city").innerHTML = `<option value="">Escolha a cidade</option>` + C.cidades.map(c=>`<option value="${c.slug}">${c.nome}</option>`).join("");
    const totals = () => {
      const items = Object.entries(cart).map(([s,q])=>({p:P.find(p=>p.sku===s),q})).filter(i=>i.p);
      const sub = items.reduce((a,i)=>a+i.p.preco*i.q,0);
      const pix = $('input[name="pay"]:checked').value==="pix";
      const ship = $('input[name="ship"]:checked').value;
      const city = C.cidades.find(c=>c.slug===$("#city").value);
      const frete = ship==="retirada"?0:(city?city[ship]:null);
      const desc = pix ? sub*C.desconto_pix : 0;
      return {items,sub,desc,frete,ship,city,pix,total:sub-desc+(frete||0)};
    };
    const refresh = () => {
      const t = totals(); badge();
      lines.innerHTML = t.items.length ? t.items.map(i=>`
        <div class="line"><a href="${i.p.url}">${i.p.nome}</a><b>${brl(i.p.preco*i.q)}</b>
          <span class="qty"><button type="button" data-dec="${i.p.sku}" aria-label="Diminuir">−</button><span>${i.q}</span><button type="button" data-inc="${i.p.sku}" aria-label="Aumentar">+</button></span></div>`).join("")
        : `<p class="note">Seu carrinho está vazio. <a href="catalogo.html">Ver peças</a></p>`;
      $("#feeN").textContent = t.city?brl(t.city.normal):"escolha a cidade";
      $("#tot").innerHTML = `<span>Peças</span><span>${brl(t.sub)}</span>`
        + (t.desc?`<span>Desconto Pix</span><span>− ${brl(t.desc)}</span>`:"")
        + `<span>Entrega</span><span>${t.frete===null?"—":brl(t.frete)}</span>`
        + `<span class="big">Total</span><span class="big">${brl(t.total)}</span>`;
      const ent = t.ship!=="retirada";
      $("#addrbox").hidden = !ent; $("#citybox").hidden = !ent;
      let err = "";
      if(!t.items.length) err = "Adicione pelo menos uma peça.";
      else if(ent && !t.city) err = "Escolha a cidade para calcular a entrega.";
      else if(ent && !$("#addr").value.trim()) err = "Informe o endereço de entrega.";
      else if(!$("#name").value.trim()) err = "Informe seu nome.";
      $("#err").hidden = !err; $("#err").textContent = err;
      const send = $("#send"); send.setAttribute("aria-disabled", !!err);
      if(err){ send.href = "#"; return; }
      const msg = [`*Pedido Loja Dias*`, `Cliente: ${$("#name").value.trim()}`,
        ...t.items.map(i=>`• ${i.q}x ${i.p.nome} (${i.p.sku}) = ${brl(i.p.preco*i.q)}`),
        `Peças: ${brl(t.sub)}`, t.desc?`Desconto Pix: -${brl(t.desc)}`:null,
        `Entrega: ${ent?"motoboy para "+t.city.nome:"retirada"} = ${brl(t.frete||0)}`,
        ent?`Endereço: ${$("#addr").value.trim()}`:null,
        `Pagamento: ${t.pix?"Pix":"Cartão na entrega"}`, `*Total: ${brl(t.total)}*`].filter(Boolean).join("\n");
      send.href = `https://wa.me/${C.whatsapp}?text=${encodeURIComponent(msg)}`;
    };
    lines.addEventListener("click", e=>{ const d=e.target.dataset;
      if(d.inc) cart[d.inc]++; else if(d.dec){ cart[d.dec]--; if(cart[d.dec]<=0) delete cart[d.dec]; } else return;
      save(); refresh(); });
    $$(".cartpage input,.cartpage select").forEach(el=>el.addEventListener("input", refresh));
    refresh();
  }
  badge();
})();
