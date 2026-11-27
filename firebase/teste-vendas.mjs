// Testes das regras do painel de pedidos (vendas/{txid}) no emulador:
// npx firebase emulators:exec --only firestore "node teste-vendas.mjs"  (firestore.rules na mesma pasta)
import { initializeTestEnvironment, assertSucceeds as ok, assertFails as no } from "@firebase/rules-unit-testing";
import { readFileSync } from "fs";
import { doc, setDoc, getDoc, updateDoc, deleteDoc, collection, getDocs, query, orderBy, serverTimestamp } from "firebase/firestore";
const env = await initializeTestEnvironment({ projectId: "demo-loja",
  firestore: { rules: readFileSync("firestore.rules", "utf8"), host: "127.0.0.1", port: 8080 } });
const A = env.authenticatedContext("uidA", { email: "a@x.com", email_verified: true }).firestore();
const L = env.authenticatedContext("uidL", { email: "luanvieiradiaas17@gmail.com", email_verified: true }).firestore();
const N = env.unauthenticatedContext().firestore();
const v = (id, x = {}) => ({ txid: id, criado: serverTimestamp(), status: "novo", origem: "site", entrega: "motoboy", pagamento: "pix",
  cliente: { nome: "João", telefone: "27999990000", endereco: "Rua A, 1", cidade: "vila-velha" },
  itens: [{ sku: "CPR8EA9", nome: "Vela", qtd: 1, preco: 30 }], sub: 30, frete: 10, desconto: 0, total: 40, ...x });
let n = 0, falhas = 0; const t = async (nome, p) => { n++; try { await p; console.log("ok  ", nome); } catch (e) { falhas++; console.log("FALHOU", nome, e.message.slice(0, 120)); } };
await t("anônimo cria pedido", ok(setDoc(doc(N, "vendas", "LDABCDEFGH123"), v("LDABCDEFGH123"))));
await t("anônimo não lê o pedido", no(getDoc(doc(N, "vendas", "LDABCDEFGH123"))));
await t("anônimo não lista", no(getDocs(collection(N, "vendas"))));
await t("cliente logado não lista", no(getDocs(collection(A, "vendas"))));
await t("anônimo não sobrescreve", no(setDoc(doc(N, "vendas", "LDABCDEFGH123"), v("LDABCDEFGH123", { total: 1 }))));
await t("anônimo não muda status", no(updateDoc(doc(N, "vendas", "LDABCDEFGH123"), { status: "entregue" })));
await t("anônimo não apaga", no(deleteDoc(doc(N, "vendas", "LDABCDEFGH123"))));
await t("nega status pago na criação", no(setDoc(doc(N, "vendas", "LDABCDEFGH124"), v("LDABCDEFGH124", { status: "pix_caiu" }))));
await t("nega id diferente do txid", no(setDoc(doc(N, "vendas", "LDABCDEFGH125"), v("LDOUTRO12345"))));
await t("nega id fora do formato", no(setDoc(doc(N, "vendas", "<script>"), v("<script>"))));
await t("nega campo extra", no(setDoc(doc(N, "vendas", "LDABCDEFGH126"), v("LDABCDEFGH126", { pago_em: serverTimestamp() }))));
await t("nega nome gigante", no(setDoc(doc(N, "vendas", "LDABCDEFGH127"), v("LDABCDEFGH127", { cliente: { nome: "a".repeat(81) } }))));
await t("nega 31 itens", no(setDoc(doc(N, "vendas", "LDABCDEFGH128"), v("LDABCDEFGH128", { itens: Array(31).fill({ sku: "X" }) }))));
await t("nega sem itens", no(setDoc(doc(N, "vendas", "LDABCDEFGH129"), v("LDABCDEFGH129", { itens: [] }))));
await t("nega uid de outro cliente", no(setDoc(doc(N, "vendas", "LDABCDEFGH130"), v("LDABCDEFGH130", { uid: "uidA" }))));
await t("cliente logado grava o próprio uid", ok(setDoc(doc(A, "vendas", "LDABCDEFGH131"), v("LDABCDEFGH131", { uid: "uidA" }))));
await t("nota fiscal com CNPJ ok", ok(setDoc(doc(N, "vendas", "LDABCDEFGH132"), v("LDABCDEFGH132", { nf: { cnpj: "46178859000196", razao: "Empresa", email: "a@b.com" } }))));
await t("nega CNPJ com letra", no(setDoc(doc(N, "vendas", "LDABCDEFGH133"), v("LDABCDEFGH133", { nf: { cnpj: "4617885900019X", razao: "E", email: "a@b.com" } }))));
await t("nega criado com data falsa", no(setDoc(doc(N, "vendas", "LDABCDEFGH134"), v("LDABCDEFGH134", { criado: new Date(2020, 1, 1) }))));
await t("loja lista em ordem", ok(getDocs(query(collection(L, "vendas"), orderBy("criado", "desc")))));
await t("loja muda etapa", ok(updateDoc(doc(L, "vendas", "LDABCDEFGH123"), { status: "pix_caiu", historico: [{ s: "pix_caiu", em: new Date() }], pago_em: serverTimestamp(), atualizado: serverTimestamp() })));
await t("loja anota", ok(updateDoc(doc(L, "vendas", "LDABCDEFGH123"), { obs: "troca sexta" })));
await t("loja não muda total", no(updateDoc(doc(L, "vendas", "LDABCDEFGH123"), { total: 1 })));
await t("loja não muda cliente", no(updateDoc(doc(L, "vendas", "LDABCDEFGH123"), { cliente: { nome: "x" } })));
await t("nega etapa inventada", no(updateDoc(doc(L, "vendas", "LDABCDEFGH123"), { status: "qualquer" })));
await t("nega Pix na entrega (desligado 26/11)", no(setDoc(doc(N, "vendas", "LDABCDEFGH135"), v("LDABCDEFGH135", { pagamento: "entrega" }))));
await t("loja lança pedido do WhatsApp", ok(setDoc(doc(L, "vendas", "LDABCDEFGHWA0"), v("LDABCDEFGHWA0", { origem: "whatsapp" }))));
await t("loja apaga pedido falso", ok(deleteDoc(doc(L, "vendas", "LDABCDEFGH132"))));
await t("clientes continua fechado", no(getDoc(doc(N, "clientes", "uidA"))));
await env.cleanup();
console.log(`${n - falhas} de ${n} passaram`); process.exit(falhas ? 1 : 0);
