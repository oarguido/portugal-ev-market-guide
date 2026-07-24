"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { matchesVehicleSearch, normalizeSearchText } = require("../web/assets/js/search.js");

const root = path.resolve(__dirname, "..");
const catalog = JSON.parse(fs.readFileSync(path.join(root, "data/vehicles/pt_market.json"), "utf8"));
const vehicles = catalog.models.flatMap(model =>
  model.variants.map(variant => ({
    brand: model.brand,
    model: model.model,
    variant: variant.name,
    segment: model.segment
  }))
);

function resultsFor(query) {
  return vehicles.filter(vehicle => matchesVehicleSearch(vehicle, query));
}

test("cada modelo do catálogo é encontrado pelo nome oficial", () => {
  for (const model of catalog.models) {
    assert.ok(
      resultsFor(`${model.brand} ${model.model}`).some(
        result => result.brand === model.brand && result.model === model.model
      ),
      `${model.brand} ${model.model} não foi encontrado`
    );
  }
});

test("a pesquisa normaliza acentos e pontuação frequentes", () => {
  assert.ok(resultsFor("Citroen e-C3").some(result => result.model === "ë-C3"));
  assert.ok(resultsFor("Megane").some(result => result.model === "Mégane E-Tech elétrico"));
  assert.ok(resultsFor("Skoda Elroq").some(result => result.brand === "Škoda"));
  assert.ok(resultsFor("ID3").some(result => result.model === "ID.3"));
  assert.ok(resultsFor("E2008").some(result => result.model === "E-2008"));
});

test("uma pequena gralha não esconde um modelo", () => {
  assert.ok(resultsFor("Dolphyn").some(result => result.model === "Dolphin"));
  assert.ok(resultsFor("Meggane").some(result => result.model === "Mégane E-Tech elétrico"));
  assert.ok(resultsFor("Avengerr").some(result => result.model === "Avenger elétrico"));
});

test("a versão e a capacidade da bateria também são pesquisáveis", () => {
  const results = resultsFor("Dolphyn 60.4");
  assert.equal(results.length, 1);
  assert.equal(results[0].model, "Dolphin");
  assert.equal(results[0].variant, "Comfort 60.4 kWh");
});

test("todos os tokens longos de modelos toleram uma substituição", () => {
  for (const model of catalog.models) {
    const tokens = normalizeSearchText(model.model).split(" ").filter(token => token.length >= 5);
    for (const token of tokens) {
      const replacement = token.endsWith("x") ? "z" : "x";
      const typo = `${token.slice(0, -1)}${replacement}`;
      assert.ok(
        resultsFor(typo).some(result => result.brand === model.brand && result.model === model.model),
        `${model.brand} ${model.model} deixou de ser encontrado com ${typo}`
      );
    }
  }
});

test("texto sem relação não produz falsos resultados", () => {
  assert.deepEqual(resultsFor("motorizacao diesel"), []);
});
