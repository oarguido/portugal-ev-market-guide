"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const appSource = fs.readFileSync(path.join(root, "web/assets/js/app.js"), "utf8");

test("contrato de renderização de cartões em app.js inclui pros, cons e imagens com lazy loading", () => {
  // Check pros and cons rendering block in app.js
  assert.ok(
    appSource.includes("const prosHTML = car.pros.map"),
    "app.js deve mapear os elementos de car.pros",
  );
  assert.ok(
    appSource.includes("const consHTML = car.cons.map"),
    "app.js deve mapear os elementos de car.cons",
  );

  // Check HTML escaping on pros and cons
  assert.ok(
    appSource.includes("escapeHtml(pro)"),
    "app.js deve aplicar escapeHtml a cada pro",
  );
  assert.ok(
    appSource.includes("escapeHtml(con)"),
    "app.js deve aplicar escapeHtml a cada con",
  );

  // Check lazy loading and async decoding on images
  assert.ok(
    appSource.includes('loading="lazy"'),
    "app.js deve incluir loading=\"lazy\" em <img>",
  );
  assert.ok(
    appSource.includes('decoding="async"'),
    "app.js deve incluir decoding=\"async\" em <img>",
  );
});

test("contrato do comparador técnico inclui dimensões e capacidades de mala e frunk", () => {
  const requiredLabels = [
    "Comprimento Exterior",
    "Largura Exterior",
    "Altura Exterior",
  ];

  for (const label of requiredLabels) {
    assert.ok(
      appSource.includes(label),
      `app.js comparador técnico deve incluir a métrica '${label}'`,
    );
  }
});

test("contrato de suporte a variante única inclui badge badge-single-variant e legenda 'Variante única'", () => {
  assert.ok(
    appSource.includes("badge-single-variant"),
    "app.js deve incluir a classe de badge 'badge-single-variant'",
  );
  assert.ok(
    appSource.includes("Variante única"),
    "app.js deve incluir o texto 'Variante única'",
  );
  assert.ok(
    appSource.includes("is_single_variant"),
    "app.js deve calcular e anexar a propriedade 'is_single_variant'",
  );
  assert.ok(
    appSource.includes("variant_count"),
    "app.js deve calcular e anexar a propriedade 'variant_count'",
  );
  assert.ok(
    appSource.includes("Variantes Elegíveis (< 40k €)"),
    "app.js comparador técnico deve incluir a linha 'Variantes Elegíveis (< 40k €)'",
  );
});

test("todos os ficheiros JavaScript da aplicação usam 'use strict' ou módulos ESM estritos", () => {
  const jsDir = path.join(root, "web/assets/js");
  const jsFiles = fs.readdirSync(jsDir).filter((f) => f.endsWith(".js"));

  for (const file of jsFiles) {
    const content = fs.readFileSync(path.join(jsDir, file), "utf8");
    // car_data.js is auto-generated data, other JS files are app scripts
    if (file !== "car_data.js") {
      assert.ok(
        content.startsWith('"use strict";') || content.startsWith("'use strict';"),
        `${file} deve iniciar com 'use strict';`,
      );
    }
  }
});
