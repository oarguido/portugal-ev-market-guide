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

test("escapa os cinco caracteres que quebram HTML e atributos", () => {
  assert.equal(escapeHtml("Silva & Filhos"), "Silva &amp; Filhos");
  assert.equal(escapeHtml("<script>"), "&lt;script&gt;");
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
});

test("converte números e não perde o zero", () => {
  assert.equal(escapeHtml(0), "0");
  assert.equal(escapeHtml(23990), "23990");
});

test("um valor já escapado volta a escapar o & (sem dupla descodificação silenciosa)", () => {
  // Documenta a regra: escapar exatamente uma vez, na fronteira do render.
  assert.equal(escapeHtml("&amp;"), "&amp;amp;");
});

test("as fotografias dos cartões são adiadas e descodificadas fora da thread principal", () => {
  // 54 fotografias a 23 MB: sem lazy loading o browser descarrega todas as que
  // estão abaixo da dobra antes de o utilizador chegar lá.
  const imageTag = appSource.match(/<img[^>]*class="card-car-image"[^>]*>/);
  assert.ok(imageTag, "o cartão tem de continuar a renderizar uma <img>");
  assert.match(imageTag[0], /loading="lazy"/);
  assert.match(imageTag[0], /decoding="async"/);
});

test("o render do cartão escapa os campos vindos do catálogo", () => {
  for (const field of [
    "escapeHtml(car.brand)",
    "escapeHtml(car.model)",
    "escapeHtml(car.variant)",
    "escapeHtml(imagePath)",
    "escapeHtml(car.official_link)",
  ]) {
    assert.ok(appSource.includes(field), `app.js tem de escapar ${field}`);
  }
});
