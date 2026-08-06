"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const Prices = require("../web/assets/js/prices.js");

function car(offers) {
  return { variant: "Base", pricing: { offers }, specifications: {} };
}

const confirmed = {
  kind: "list_price", classification: "confirmed", amount_eur: 31990,
  vat: "included", customer: "private", variant: "Base",
  proof: { status: "verified", source_url: "https://marca.pt/preco", recorded_on: "2026-08-01", verified_on: "2026-08-01" }
};

test("seleciona apenas preço confirmado para limite e ranking", () => {
  const vehicle = car([{ ...confirmed }, { ...confirmed, amount_eur: 22000, classification: "reference" }]);
  assert.equal(Prices.getPrice(vehicle).amount, 31990);
  assert.equal(Prices.hasConfirmedBudgetPrice(vehicle), true);
  assert.equal(Prices.status(vehicle), "confirmed_eligible");
});

test("referência mostra bloqueadores e não entra como preço confirmado", () => {
  const vehicle = car([{ kind: "campaign_price", classification: "reference", amount_eur: 18800, vat: "excluded", customer: "business", proof: { status: "legacy_unverified", source_url: "https://marca.pt/preco", recorded_on: "2026-08-01", verified_on: null } }]);
  assert.equal(Prices.getPrice(vehicle), null);
  const reference = Prices.getPrice(vehicle, { allowReference: true });
  assert.equal(reference.amount, 18800);
  assert.ok(reference.blockers.includes("IVA excluído"));
  assert.ok(reference.blockers.includes("Apenas empresas"));
  assert.equal(Prices.status(vehicle), "potential_reference");
});

test("campanha expirada não é usada", () => {
  const vehicle = car([{ ...confirmed, type: "campaign", valid_until: "2020-01-01" }]);
  assert.equal(Prices.getPrice(vehicle, { today: new Date("2026-08-01") }), null);
});

test("paridade Python: confirmação exige público, frescura 45 dias, atividade e limite", () => {
  const base = { ...confirmed, proof: { ...confirmed.proof, verified_on: "2026-06-01" } };
  const unknown = car([{ ...base, customer: undefined }]);
  const tooExpensive = car([{ ...confirmed, amount_eur: 40000.01 }]);
  const future = car([{ ...confirmed, validity: { valid_from: "2026-09-01", valid_until: null } }]);
  assert.equal(Prices.getPrice(unknown, { today: new Date("2026-08-01") }), null);
  assert.equal(Prices.getOffers(unknown, new Date("2026-08-01"))[0].blockers.includes("Público por confirmar"), true);
  for (const customer of ["unknown", ""]) {
    const emptyAudience = car([{ ...base, customer }]);
    assert.equal(Prices.getOffers(emptyAudience, new Date("2026-08-01"))[0].blockers.includes("Público por confirmar"), true);
  }
  assert.equal(Prices.getPrice(tooExpensive, { today: new Date("2026-08-01") }), null);
  assert.equal(Prices.getPrice(future, { today: new Date("2026-08-01") }), null);
});

test("confirmed expirado, antigo ou acima do limite não ganha fallback de referência", () => {
  for (const invalid of [
    { ...confirmed, validity: { valid_from: null, valid_until: "2026-07-01" } },
    { ...confirmed, proof: { ...confirmed.proof, verified_on: "2026-05-01" } },
    { ...confirmed, amount_eur: 40000.01 },
  ]) {
    const vehicle = car([invalid]);
    assert.equal(Prices.status(vehicle, new Date("2026-08-01")), "not_demonstrated");
    assert.equal(Prices.getPrice(vehicle, { allowReference: true, today: new Date("2026-08-01") }), null);
  }
});

test("modelo misto conserva coortes: referência só é referência e não substitui confirmado inválido", () => {
  const invalidConfirmed = { ...confirmed, amount_eur: 41000 };
  const reference = { ...confirmed, classification: "reference", amount_eur: 39000 };
  const vehicle = car([invalidConfirmed, reference]);
  const offers = Prices.getOffers(vehicle, new Date("2026-08-01"));
  assert.equal(offers[0].classification, "confirmed");
  assert.equal(offers[1].classification, "reference");
  assert.equal(Prices.status(vehicle, new Date("2026-08-01")), "potential_reference");
  assert.equal(Prices.getPrice(vehicle, { allowReference: true, today: new Date("2026-08-01") }).amount, 39000);
});

test("preserva fonte e data de registo para renderização", () => {
  const offer = Prices.getOffers(car([{ ...confirmed }]))[0];
  assert.equal(offer.source, "https://marca.pt/preco");
  assert.equal(offer.recordedOn, "2026-08-01");
});

test("teto usa referência atual em Todos e Referência, sem a promover", () => {
  const makeReference = amount => ({
    kind: "list_price", classification: "reference", amount_eur: amount,
    vat: "unknown", customer: "unknown",
    proof: { status: "legacy_unverified", source_url: "https://marca.pt/preco", recorded_on: "2026-08-01", verified_on: null }
  });
  const cars = [car([makeReference(31990)]), car([makeReference(25000)])];
  const matchingAll = cars.filter(vehicle => Prices.getFilterPrice(vehicle, "all")?.amount <= 31989);
  const matchingReferences = cars.filter(vehicle => Prices.getFilterPrice(vehicle, "potential_reference")?.amount <= 31989);
  assert.equal(matchingAll.length, 1);
  assert.equal(matchingReferences.length, 1);
  assert.equal(Prices.getFilterPrice(cars[0], "confirmed_eligible"), null);
  assert.equal(Prices.hasConfirmedBudgetPrice(cars[0]), false);
});
