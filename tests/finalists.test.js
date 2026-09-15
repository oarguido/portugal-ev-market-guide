"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
require("../web/assets/js/html.js");
const { render, rows, reviews, sources } = require("../web/assets/js/finalists.js");

test("finalistas mantêm versões exatas, referências e origens sem alterar o catálogo", () => {
  const catalog = [{ brand: "BYD", model: "Dolphin", image_path: "assets/images/vehicles/byd-dolphin/official.webp", variants: [] }];
  const original = JSON.stringify(catalog);
  const html = render(catalog, {});
  assert.equal((html.match(/class="finalist-card"/g) || []).length, 3);
  for (const name of ["Design ProMax", "Luxury", "Comfort MY25", "Referência — versão/condições por confirmar", "3.810", "pré-série", "outro modelo"]) assert.ok(html.includes(name), name);
  assert.equal(JSON.stringify(catalog), original);
  assert.match(html, /loading="lazy"/);
  assert.ok(!html.includes("Dolphin Surf ·"));
});

test("campos externos são escapados e URLs perigosos não geram ligações nem imagens", () => {
  const html = render([{ brand: "BYD", model: "Dolphin", image_path: 'https://bad.invalid/" onerror="alert(1)' }], { BYD: { name: '<img src=x onerror="alert(1)">', address: 'Silva & Filhos', official_url: 'javascript:alert(1)', maps_url: 'https://example.org/?a="&b=1' } });
  assert.ok(!html.includes('<img src=x'));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(!html.includes('src="https://bad.invalid'));
  assert.ok(html.includes("Silva &amp; Filhos"));
  assert.ok(html.includes("&quot;&amp;b=1"));
});

test("todas as afirmações ligadas têm fonte existente e âncora resolvida", () => {
  const html = render();
  for (const row of rows) for (const value of row.slice(2)) for (const ref of value.refs) assert.ok(sources[ref], ref);
  for (const review of reviews) for (const ref of review.refs) assert.ok(sources[ref], ref);
  for (const [, id] of html.matchAll(/href="#([^"]+)"/g)) assert.ok(html.includes(`id="${id}"`), id);
});

test("pesquisa envelhecida avisa e nunca apresenta propostas como confirmadas", () => {
  assert.match(render([], {}, new Date("2026-11-01")), /mais de 45 dias/);
  assert.doesNotMatch(render([], {}, new Date("2026-09-14")), /Esta pesquisa tem mais de 45 dias/);
  assert.doesNotMatch(render(), /class="finalists-status">Confirmado/);
});

test("citações abrem a fonte real num novo separador, não uma âncora do site", () => {
  const html = render();
  assert.doesNotMatch(html, /href="#finalists-source-/);
  for (const ref of ["b05", "byd", "aionmanual", "autocar", "fdm"]) {
    const url = globalThis.VehicleHtml.escapeHtml(sources[ref][1]);
    assert.ok(html.includes(`href="${url}" target="_blank" rel="noopener noreferrer"`), ref);
  }
  assert.match(html, /Manual de utilização PT: ligação pública não identificada/);
});

test("preços ficam recolhidos e Comfort não apresenta tejadilho de vidro", () => {
  const html = render();
  assert.match(html, /<details class="finalists-section finalists-price-details">/);
  const cards = [...html.matchAll(/<article class="finalist-card">([\s\S]*?)<\/article>/g)];
  assert.equal(cards.length, 3);
  for (const card of cards) assert.doesNotMatch(card[1], /€|finalist-price/);
  const roof = rows.find(row => row[1] === "Tejadilho de vidro / panorâmico");
  assert.match(roof[4].text, /^Não — Comfort/);
  assert.match(roof[4].text, /utilizador/);
  assert.doesNotMatch(html, /pagar mais só com uma vantagem/);
});
