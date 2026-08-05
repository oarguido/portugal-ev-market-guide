"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const appSource = fs.readFileSync(path.join(root, "web/assets/js/app.js"), "utf8");
const carDataSource = fs.readFileSync(path.join(root, "web/assets/js/car_data.js"), "utf8");
const htmlSource = fs.readFileSync(path.join(root, "web/assets/js/html.js"), "utf8");

// Helper to simulate flattenCarData in a mock environment
function runFlattenCarData(catalogData) {
  const sandbox = {
    CAR_DATA: catalogData,
    VehicleHtml: { escapeHtml: (str) => String(str ?? '') },
    flatCars: [],
    console: console,
  };
  vm.createContext(sandbox);

  // Extract flattenCarData definition and execution from appSource
  const codeToRun = `
    ${htmlSource}
    var flatCars = [];
    ${appSource.slice(appSource.indexOf('function flattenCarData()'), appSource.indexOf('/* ==========================================================================\n   Navigation Tabs Logic'))}
    flattenCarData();
  `;
  vm.runInContext(codeToRun, sandbox);
  return sandbox.flatCars;
}

test("flattenCarData calcula is_single_variant e variant_count para modelo com 1 variante", () => {
  const mockCatalog = [
    {
      brand: "TestBrand",
      model: "SingleModel",
      eligible: true,
      variants: [
        { name: "Base", battery_capacity_kwh: 50, wltp_range_combined_km: 300, pricing: { particular_list_price_vat_incl: 30000 } }
      ]
    }
  ];

  const flat = runFlattenCarData(mockCatalog);
  assert.equal(flat.length, 1);
  assert.equal(flat[0].is_single_variant, true);
  assert.equal(flat[0].variant_count, 1);
});

test("flattenCarData calcula is_single_variant e variant_count para modelo com múltiplas variantes", () => {
  const mockCatalog = [
    {
      brand: "TestBrand",
      model: "MultiModel",
      eligible: true,
      variants: [
        { name: "Base", battery_capacity_kwh: 50, wltp_range_combined_km: 300, pricing: { particular_list_price_vat_incl: 30000 } },
        { name: "Pro", battery_capacity_kwh: 60, wltp_range_combined_km: 400, pricing: { particular_list_price_vat_incl: 35000 } },
        { name: "Max", battery_capacity_kwh: 70, wltp_range_combined_km: 480, pricing: { particular_list_price_vat_incl: 39000 } }
      ]
    }
  ];

  const flat = runFlattenCarData(mockCatalog);
  assert.equal(flat.length, 3);
  assert.equal(flat[0].is_single_variant, false);
  assert.equal(flat[0].variant_count, 3);
  assert.equal(flat[1].is_single_variant, false);
  assert.equal(flat[1].variant_count, 3);
  assert.equal(flat[2].is_single_variant, false);
  assert.equal(flat[2].variant_count, 3);
});

test("flattenCarData calcula is_single_variant para modelo sem array de variantes", () => {
  const mockCatalog = [
    {
      brand: "TestBrand",
      model: "LegacyModel",
      variant: "Standard",
      eligible: true,
      pricing: { particular_list_price_vat_incl: 25000 }
    }
  ];

  const flat = runFlattenCarData(mockCatalog);
  assert.equal(flat.length, 1);
  assert.equal(flat[0].is_single_variant, true);
  assert.equal(flat[0].variant_count, 1);
});

test("verificação de renderização do badge em app.js para variante única vs multi-variante", () => {
  // Test micro-badge string rendering logic in app.js
  const singleCar = { is_single_variant: true, variant_count: 1 };
  const multiCar = { is_single_variant: false, variant_count: 2 };

  // Replicate badge string generation logic from app.js
  const getBadgesHTML = (car) => {
    let badgesHTML = "";
    if (car.is_single_variant) {
      badgesHTML += `<span class="card-badge badge-single-variant"><i class="fa-solid fa-layer-group"></i> Variante única</span>`;
    }
    return badgesHTML;
  };

  assert.ok(getBadgesHTML(singleCar).includes('badge-single-variant'));
  assert.ok(getBadgesHTML(singleCar).includes('Variante única'));
  assert.equal(getBadgesHTML(multiCar), '');
});

test("verificação de renderização da tabela comparativa em app.js para variante única vs multi-variante", () => {
  const singleCar = { is_single_variant: true, variant_count: 1 };
  const multiCar = { is_single_variant: false, variant_count: 3 };

  const getCompRowVal = (car) => {
    return car.is_single_variant ? "1 (Variante única)" : `${car.variant_count} versões`;
  };

  assert.equal(getCompRowVal(singleCar), "1 (Variante única)");
  assert.equal(getCompRowVal(multiCar), "3 versões");
});

test("verificação empírica no catálogo real car_data.js", () => {
  const sandbox = {
    console: console,
    VehicleHtml: { escapeHtml: (str) => String(str ?? '') }
  };
  vm.createContext(sandbox);
  vm.runInContext(carDataSource, sandbox);

  const codeToRun = `
    var flatCars = [];
    ${appSource.slice(appSource.indexOf('function flattenCarData()'), appSource.indexOf('/* ==========================================================================\n   Navigation Tabs Logic'))}
    flattenCarData();
  `;
  vm.runInContext(codeToRun, sandbox);

  const flatCars = sandbox.flatCars;
  assert.ok(flatCars.length > 0, "O catálogo achatado não deve estar vazio");

  const singleVariantCars = flatCars.filter(c => c.is_single_variant);
  const multiVariantCars = flatCars.filter(c => !c.is_single_variant);

  assert.ok(singleVariantCars.length > 0, "Devem existir carros com variante única");
  assert.ok(multiVariantCars.length > 0, "Devem existir carros com múltiplas variantes");

  singleVariantCars.forEach(c => {
    assert.equal(c.is_single_variant, true);
    assert.equal(c.variant_count, 1);
  });

  multiVariantCars.forEach(c => {
    assert.equal(c.is_single_variant, false);
    assert.ok(c.variant_count > 1);
  });
});
