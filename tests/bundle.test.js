"use strict";

// A aplicação não tem build step: o que está em web/assets/js/ é exatamente o que
// o browser executa. Um erro de sintaxe em app.js não é apanhado por nenhum teste
// que só leia o ficheiro como texto — quebra a página inteira em silêncio, e o
// `make validate` continua verde porque os dados estão bem.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const jsDir = path.join(root, "web/assets/js");
const modules = fs
  .readdirSync(jsDir)
  .filter((name) => name.endsWith(".js"))
  .sort();

test("existem módulos para verificar", () => {
  assert.ok(
    modules.length >= 5,
    `apenas ${modules.length} módulos encontrados`,
  );
});

for (const name of modules) {
  test(`${name} é JavaScript sintaticamente válido`, () => {
    const source = fs.readFileSync(path.join(jsDir, name), "utf8");
    // new vm.Script compila sem executar: apanha o erro de sintaxe sem precisar
    // de um DOM.
    assert.doesNotThrow(() => new vm.Script(source, { filename: name }));
  });
}

test("o bundle compilado declara os dois catálogos que a aplicação espera", () => {
  const bundle = fs.readFileSync(path.join(jsDir, "car_data.js"), "utf8");
  assert.match(
    bundle,
    /^\/\/ Gerado automaticamente/,
    "o bundle perdeu o aviso de ficheiro gerado",
  );
  assert.match(bundle, /const CAR_DATA = \[/);
  assert.match(bundle, /const DEALER_DATA = \{/);
});

test("os módulos correm no browser e expõem a sua API global", () => {
  // Executar a cadeia real de scripts num contexto vazio, pela mesma ordem do
  // index.html, prova que cada módulo expõe o global de que o próximo depende.
  const html = fs.readFileSync(path.join(root, "web/index.html"), "utf8");
  const ordered = [
    ...html.matchAll(/<script src="assets\/js\/([^"]+)"><\/script>/g),
  ].map((match) => match[1]);
  assert.deepEqual(
    ordered.slice(0, 2),
    ["car_data.js", "html.js"],
    "html.js tem de carregar logo após o bundle",
  );

  const context = vm.createContext({ console });
  for (const name of ordered) {
    if (name === "app.js") break; // app.js precisa de document; os módulos não.
    vm.runInContext(fs.readFileSync(path.join(jsDir, name), "utf8"), context, {
      filename: name,
    });
  }

  for (const global of [
    "CAR_DATA",
    "DEALER_DATA",
    "VehicleHtml",
    "VehicleSearch",
    "VehicleRanking",
    "VehicleSpecs",
  ]) {
    assert.ok(
      vm.runInContext(`typeof ${global} !== "undefined"`, context),
      `${global} não ficou disponível`,
    );
  }
  assert.equal(
    vm.runInContext('VehicleHtml.escapeHtml("a & b")', context),
    "a &amp; b",
  );
});
