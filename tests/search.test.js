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
  // Cada caso prova uma regra de normalização, não a presença de um carro:
  // trema, acento agudo, háček e ponto interior. Se o modelo citado sair do
  // catálogo, o caso é ignorado em vez de dar um falso alarme — o que se testa
  // é a regra, e um carro pode legitimamente deixar de existir.
  const casos = [
    { query: "Citroen e-C3", modelo: "ë-C3" },
    { query: "Megane", modelo: "Mégane E-Tech elétrico" },
    { query: "Skoda Elroq", modelo: "Elroq" },
    { query: "ID3", modelo: "ID.3" }
  ].filter(caso => vehicles.some(vehicle => vehicle.model === caso.modelo));

  assert.ok(casos.length >= 3, "o catálogo tem de manter casos acentuados suficientes para testar a regra");
  for (const caso of casos) {
    assert.ok(
      resultsFor(caso.query).some(result => result.model === caso.modelo),
      `"${caso.query}" devia encontrar ${caso.modelo}`
    );
  }
});

test("uma pequena gralha não esconde um modelo", () => {
  // Gralhas geradas a partir do próprio catálogo, duplicando a última letra do
  // nome. Antes esta prova citava modelos à mão e falhava assim que um deles
  // saía do catálogo por a campanha ter expirado — uma regressão inventada.
  const amostra = [...new Set(vehicles.map(vehicle => vehicle.model))]
    .filter(modelo => /^[\p{L}]{5,}$/u.test(modelo.split(" ")[0]))
    .slice(0, 8);

  assert.ok(amostra.length >= 3, "amostra insuficiente para testar tolerância a gralhas");
  for (const modelo of amostra) {
    const primeira = modelo.split(" ")[0];
    const gralha = primeira + primeira.slice(-1);
    assert.ok(
      resultsFor(gralha).some(result => result.model === modelo),
      `"${gralha}" devia continuar a encontrar ${modelo}`
    );
  }
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
