"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  WEIGHTS,
  getPriceRangeBreakdown,
  getPriceRangeScore
} = require("../web/assets/js/ranking.js");

function car({ price = 30_000, range = 400, year = 2025, reviews, technology }) {
  return {
    pricing: { particular_list_price_vat_incl: price },
    specifications: { wltp_range_combined_km: range },
    release_year: year,
    user_reviews: reviews,
    technology_advantages: technology
  };
}

test("a fórmula dá 90% do peso ao preço e autonomia", () => {
  assert.deepEqual(WEIGHTS, { price: 0.45, range: 0.45, recency: 0.10 });
});

test("um modelo mais recente recebe um bónus pequeno e limitado", () => {
  const oldScore = getPriceRangeScore(car({ year: 2022 }), 2026);
  const newScore = getPriceRangeScore(car({ year: 2026 }), 2026);
  assert.ok(newScore > oldScore);
  assert.ok(newScore - oldScore <= 10);
});

test("preço e autonomia continuam a superar uma diferença apenas de idade", () => {
  const olderValue = car({ price: 25_000, range: 450, year: 2022 });
  const newerWeakValue = car({ price: 35_000, range: 300, year: 2026 });
  assert.ok(
    getPriceRangeScore(olderValue, 2026) > getPriceRangeScore(newerWeakValue, 2026)
  );
});

test("reviews e bónus tecnológicos não alteram a pontuação", () => {
  const base = car({});
  const legacyFields = car({
    reviews: { score: 5 },
    technology: {
      battery_tech: { heat_pump_included: true, chemistry: "LFP" },
      bidirectional_charging: { v2l_supported: true }
    }
  });
  assert.equal(
    getPriceRangeScore(base, 2026),
    getPriceRangeScore(legacyFields, 2026)
  );
});

test("a decomposição soma exatamente a pontuação total", () => {
  const breakdown = getPriceRangeBreakdown(car({}), 2026);
  assert.equal(
    breakdown.total,
    breakdown.pricePoints + breakdown.rangePoints + breakdown.recencyPoints
  );
});
