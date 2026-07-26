"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { boolLabel, cellValue, v2lLabel } = require("../web/assets/js/specs.js");

const root = path.resolve(__dirname, "..");
const catalog = JSON.parse(
  fs.readFileSync(path.join(root, "data/vehicles/pt_market.json"), "utf8"),
);
const appSource = fs.readFileSync(
  path.join(root, "web/assets/js/app.js"),
  "utf8",
);

test("boolLabel afirma Sim/Não apenas quando o dado existe", () => {
  assert.equal(boolLabel(true), "Sim");
  assert.equal(boolLabel(false), "Não");
  assert.equal(boolLabel(undefined), "N/A");
  assert.equal(boolLabel(null), "N/A");
});

test("v2lLabel só mostra potência quando o suporte está confirmado", () => {
  assert.equal(v2lLabel({}), "N/A");
  assert.equal(v2lLabel({ technology_advantages: {} }), "N/A");
  assert.equal(
    v2lLabel({
      technology_advantages: {
        bidirectional_charging: { v2l_supported: false },
      },
    }),
    "Não",
  );
  assert.equal(
    v2lLabel({
      technology_advantages: {
        bidirectional_charging: { v2l_supported: true },
      },
    }),
    "Sim",
  );
  assert.equal(
    v2lLabel({
      technology_advantages: {
        bidirectional_charging: { v2l_supported: true, v2l_max_power_kw: 3.6 },
      },
    }),
    "Sim (3.6 kW)",
  );
});

test("cellValue converte ausência em N/A sem imprimir undefined", () => {
  assert.equal(cellValue(null), "N/A");
  assert.equal(cellValue(undefined), "N/A");
  assert.equal(cellValue(0), 0);
  assert.equal(cellValue("Sim"), "Sim");
});

// Regressão: o catálogo não regista estes blocos, por isso qualquer fallback
// que os traduza para um valor concreto está a inventar dados.
test("o catálogo não contém os blocos que a tabela costumava assumir", () => {
  const raw = JSON.stringify(catalog);
  assert.equal(raw.includes("technology_advantages"), false);
  assert.equal(raw.includes("specifications_common"), false);
  for (const model of catalog.models) {
    for (const variant of model.variants) {
      assert.equal(
        "ac_max_kw" in variant,
        false,
        `${model.model} ${variant.name}`,
      );
    }
  }
});

test("app.js não repõe valores inventados para campos ausentes", () => {
  assert.equal(
    appSource.includes('|| "LFP"'),
    false,
    "battery_type não pode assumir LFP",
  );
  assert.equal(
    appSource.includes("|| 11.0"),
    false,
    "ac_max_kw não pode assumir 11 kW",
  );
  assert.equal(
    appSource.includes("|| 140.0"),
    false,
    "dc_max_kw não pode assumir 140 kW",
  );
  assert.equal(
    appSource.includes('"Traseira (RWD)" : "Dianteira (FWD)"'),
    false,
    "tração não pode ser adivinhada pela marca",
  );
});
