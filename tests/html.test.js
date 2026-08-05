"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { escapeHtml } = require("../web/assets/js/html.js");

const root = path.resolve(__dirname, "..");
const appSource = fs.readFileSync(
  path.join(root, "web/assets/js/app.js"),
  "utf8",
);
const indexHtml = fs.readFileSync(
  path.join(root, "web/index.html"),
  "utf8",
);

test("escapa os cinco caracteres que quebram HTML e atributos", () => {
  assert.equal(escapeHtml("Silva & Filhos"), "Silva &amp; Filhos");
  assert.equal(escapeHtml("<script>alert('xss')</script>"), "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;");
  assert.equal(escapeHtml('aspas " duplas'), "aspas &quot; duplas");
  assert.equal(escapeHtml("aspas ' simples"), "aspas &#39; simples");
});

test("ausência de dados não imprime undefined nem null", () => {
  assert.equal(escapeHtml(undefined), "");
  assert.equal(escapeHtml(null), "");
});

test("preserva acentos e símbolos do português e das unidades", () => {
  assert.equal(
    escapeHtml("Citroën ë-C3 — 23.990 €"),
    "Citroën ë-C3 — 23.990 €",
  );
  assert.equal(escapeHtml("Autonomia 427 km"), "Autonomia 427 km");
  assert.equal(escapeHtml("Bagageira 350 L"), "Bagageira 350 L");
  assert.equal(escapeHtml("Comp: 4200 mm x Larg: 1780 mm"), "Comp: 4200 mm x Larg: 1780 mm");
});

test("converte números e não perde o zero", () => {
  assert.equal(escapeHtml(0), "0");
  assert.equal(escapeHtml(23990), "23990");
});

test("um valor já escapado volta a escapar o & (sem dupla descodificação silenciosa)", () => {
  // Documenta a regra: escapar exatamente uma vez, na fronteira do render.
  assert.equal(escapeHtml("&amp;"), "&amp;amp;");
});

test("escapa HTML em elementos das listas de prós e contras", () => {
  const proInjetado = "Design elegante & moderno <script>";
  const conInjetado = 'Espaço "reduzido" para pernas & bagagem';
  assert.equal(escapeHtml(proInjetado), "Design elegante &amp; moderno &lt;script&gt;");
  assert.equal(escapeHtml(conInjetado), "Espaço &quot;reduzido&quot; para pernas &amp; bagagem");
});

test("as fotografias dos cartões são adiadas e descodificadas fora da thread principal", () => {
  const imageTag = appSource.match(/<img[^>]*class="card-car-image"[^>]*>/);
  assert.ok(imageTag, "o cartão tem de continuar a renderizar uma <img>");
  assert.match(imageTag[0], /loading="lazy"/);
  assert.match(imageTag[0], /decoding="async"/);
});

test("o render do cartão escapa os campos vindos do catálogo incluindo pros e cons", () => {
  for (const field of [
    "escapeHtml(car.brand)",
    "escapeHtml(car.model)",
    "escapeHtml(car.variant)",
    "escapeHtml(imagePath)",
    "escapeHtml(car.official_link)",
    "escapeHtml(pro)",
    "escapeHtml(con)",
  ]) {
    assert.ok(appSource.includes(field), `app.js tem de escapar ${field}`);
  }
});

test("o render de elementos e atributos no app.js escapa identificadores e labels", () => {
  assert.ok(
    appSource.includes('data-car-id="${escapeHtml(car.id)}"'),
    "app.js tem de escapar data-car-id com escapeHtml",
  );
  assert.ok(
    appSource.includes('data-id="${escapeHtml(c.id)}"'),
    "app.js tem de escapar data-id dos chips com escapeHtml",
  );
  assert.ok(
    appSource.includes('<span>${escapeHtml(label)}</span>'),
    "renderTCOBar no app.js tem de escapar label com escapeHtml",
  );
});

test("cumprimento de aplicação estática e offline (sem pedidos de rede remotos)", () => {
  // web/index.html não pode carregar recursos remotos externos (ex: CDNs, fontes Google)
  const scripts = indexHtml.match(/<script[^>]+src="([^"]+)"/g) || [];
  const stylesheets = indexHtml.match(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"/g) || [];

  for (const tag of [...scripts, ...stylesheets]) {
    assert.ok(
      !tag.includes("http://") && !tag.includes("https://") && !tag.includes("//"),
      `Recurso remoto detetado em index.html: ${tag}`,
    );
  }
});
