"use strict";

/* Ordenação transparente por preço, autonomia e recência. */
(function exposeVehicleRanking(root) {
  const WEIGHTS = Object.freeze({
    price: 0.45,
    range: 0.45,
    recency: 0.1,
  });

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function getPriceRangeBreakdown(
    car,
    referenceYear = new Date().getFullYear(),
  ) {
    const priceOffer = globalThis.VehiclePrices?.getPrice(car, {
      allowReference: true,
    });
    const price = priceOffer?.amount || null;
    const range =
      car.specifications?.wltp_range_combined_km ||
      car.specifications?.wltp_range_urban_km ||
      null;
    const releaseYear = Number.isFinite(car.release_year)
      ? car.release_year
      : null;

    // 15.000 € = 100 pontos de preço; 45.000 € = 0 pontos.
    const priceFactor = price
      ? clamp(((45_000 - price) / 30_000) * 100, 0, 100)
      : 0;

    // 150 km = 0 pontos de autonomia; 600 km = 100 pontos.
    const rangeFactor = range ? clamp(((range - 150) / 450) * 100, 0, 100) : 0;

    // Janela móvel de cinco anos. A recência vale no máximo 10 pontos.
    const recencyFactor = releaseYear
      ? clamp(((releaseYear - (referenceYear - 5)) / 5) * 100, 0, 100)
      : 0;

    const pricePoints = priceFactor * WEIGHTS.price;
    const rangePoints = rangeFactor * WEIGHTS.range;
    const recencyPoints = recencyFactor * WEIGHTS.recency;

    return {
      pricePoints,
      rangePoints,
      recencyPoints,
      total: pricePoints + rangePoints + recencyPoints,
    };
  }

  function getPriceRangeScore(car, referenceYear) {
    return getPriceRangeBreakdown(car, referenceYear).total;
  }

  const api = {
    WEIGHTS,
    getPriceRangeBreakdown,
    getPriceRangeScore,
  };

  root.VehicleRanking = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
