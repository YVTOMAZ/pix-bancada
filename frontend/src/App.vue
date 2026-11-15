<template>
  <div class="app">
    <h1>pix-bancada</h1>
    <nav>
      <button @click="aba='banco'">Banco</button>
      <button @click="aba='painel'">Painel</button>
    </nav>
    <section v-if="aba==='banco'">
      <h2>Banco ficticio</h2>
      <textarea v-model="brcode" placeholder="Cole o copia-e-cola"></textarea>
      <button @click="pagar">Pagar</button>
      <pre>{{ resultado }}</pre>
    </section>
    <section v-else>
      <h2>Painel</h2>
      <button @click="avancar">Avancar relogio (60s)</button>
      <pre>{{ painel }}</pre>
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue";

const aba = ref("banco");
const brcode = ref("");
const resultado = ref("");
const painel = ref("");

async function pagar() {
  const r = await fetch("/_bancada/banco/pagar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pixCopiaECola: brcode.value }),
  });
  resultado.value = await r.text();
}

async function avancar() {
  const r = await fetch("/_bancada/relogio/avancar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ segundos: 60 }),
  });
  painel.value = await r.text();
}
</script>

<style>
.app { font-family: sans-serif; max-width: 720px; margin: 2rem auto; }
textarea { width: 100%; height: 120px; }
</style>
