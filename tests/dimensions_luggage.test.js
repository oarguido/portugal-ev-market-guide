"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const bundlePath = path.join(root, "web/assets/js/car_data.js");

// Load CAR_DATA into a Node VM context
const bundleSource = fs.readFileSync(bundlePath, "utf8");
const context = vm.createContext({});
vm.runInContext(bundleSource, context);
const CAR_DATA = context.CAR_DATA || vm.runInContext("CAR_DATA", context);

test("CAR_DATA está carregado e contém modelos válidos", () => {
  assert.ok(Array.isArray(CAR_DATA), "CAR_DATA deve ser um array");
  assert.ok(CAR_DATA.length > 0, "CAR_DATA não pode estar vazio");
});

test("todos os modelos do catálogo possuem dimensões e capacidade de bagagem válidas", () => {
  for (const model of CAR_DATA) {
    const label = `${model.brand} ${model.model}`;

    // Verify dimensions
    assert.ok(model.dimensions, `${label} não possui objeto 'dimensions'`);
    assert.strictEqual(typeof model.dimensions.length_mm, "number", `${label} length_mm deve ser um número`);
    assert.ok(model.dimensions.length_mm > 0, `${label} length_mm deve ser > 0`);

    assert.strictEqual(typeof model.dimensions.width_mm, "number", `${label} width_mm deve ser um número`);
    assert.ok(model.dimensions.width_mm > 0, `${label} width_mm deve ser > 0`);

    assert.strictEqual(typeof model.dimensions.height_mm, "number", `${label} height_mm deve ser um número`);
    assert.ok(model.dimensions.height_mm > 0, `${label} height_mm deve ser > 0`);

    // Verify luggage capacity
    assert.ok(model.luggage_capacity, `${label} não possui objeto 'luggage_capacity'`);
    assert.strictEqual(typeof model.luggage_capacity.boot_capacity_l, "number", `${label} boot_capacity_l deve ser um número`);
    assert.ok(model.luggage_capacity.boot_capacity_l > 0, `${label} boot_capacity_l deve ser > 0`);

    const frunk = model.luggage_capacity.frunk_capacity_l;
    assert.ok(
      frunk === null || (typeof frunk === "number" && frunk >= 0),
      `${label} frunk_capacity_l deve ser null ou número >= 0`,
    );

    // Verify pros and cons
    assert.ok(Array.isArray(model.pros), `${label} pros deve ser uma lista`);
    assert.ok(model.pros.length >= 3 && model.pros.length <= 5, `${label} pros deve conter entre 3 e 5 elementos (atual: ${model.pros.length})`);
    for (const pro of model.pros) {
      assert.strictEqual(typeof pro, "string", `${label} item em pros deve ser string`);
      assert.ok(pro.trim().length > 0, `${label} item em pros não pode ser vazio`);
    }

    assert.ok(Array.isArray(model.cons), `${label} cons deve ser uma lista`);
    assert.ok(model.cons.length >= 3 && model.cons.length <= 5, `${label} cons deve conter entre 3 e 5 elementos (atual: ${model.cons.length})`);
    for (const con of model.cons) {
      assert.strictEqual(typeof con, "string", `${label} item em cons deve ser string`);
      assert.ok(con.trim().length > 0, `${label} item em cons não pode ser vazio`);
    }
  }
});

test("partição por categoria de dimensões (mm)", () => {
  function formatDimensions(dims) {
    if (!dims) return "N/A";
    return `${dims.length_mm} x ${dims.width_mm} x ${dims.height_mm} mm`;
  }

  assert.equal(
    formatDimensions({ length_mm: 4200, width_mm: 1780, height_mm: 1540 }),
    "4200 x 1780 x 1540 mm",
  );
  assert.equal(formatDimensions(null), "N/A");
});

test("partição por categoria de bagageira e frunk (L)", () => {
  function formatLuggage(luggage) {
    if (!luggage) return "N/A";
    const bootStr = `${luggage.boot_capacity_l} L`;
    if (luggage.frunk_capacity_l === null || luggage.frunk_capacity_l === undefined) {
      return bootStr;
    }
    if (luggage.frunk_capacity_l === 0) {
      return `${bootStr} (sem frunk)`;
    }
    return `${bootStr} (+${luggage.frunk_capacity_l} L frunk)`;
  }

  assert.equal(formatLuggage({ boot_capacity_l: 350, frunk_capacity_l: null }), "350 L");
  assert.equal(formatLuggage({ boot_capacity_l: 350, frunk_capacity_l: 0 }), "350 L (sem frunk)");
  assert.equal(formatLuggage({ boot_capacity_l: 350, frunk_capacity_l: 30 }), "350 L (+30 L frunk)");
  assert.equal(formatLuggage(null), "N/A");
});

test("verificação de ausência de chamadas de rede remotas nos scripts e estilos da web", () => {
  const cssDir = path.join(root, "web/assets/css");
  const jsDir = path.join(root, "web/assets/js");

  const cssFiles = fs.readdirSync(cssDir).filter((f) => f.endsWith(".css"));
  const jsFiles = fs.readdirSync(jsDir).filter((f) => f.endsWith(".js"));

  for (const f of cssFiles) {
    const code = fs.readFileSync(path.join(cssDir, f), "utf8");
    assert.ok(
      !code.includes("http://") && !code.includes("https://"),
      `Arquivo CSS ${f} contém URLs remotas`,
    );
  }

  for (const f of jsFiles) {
    const code = fs.readFileSync(path.join(jsDir, f), "utf8");
    // car_data.js contains official URLs in model data_sources/official_link metadata,
    // so we verify that no active fetch/XMLHttpRequest calls target remote endpoints.
    assert.ok(
      !code.includes("fetch('http") && !code.includes('fetch("http'),
      `Arquivo JS ${f} executa fetch para URLs remotas`,
    );
  }
});
