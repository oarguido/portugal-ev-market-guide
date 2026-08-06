"use strict";

/* Única fronteira de preço da aplicação. O bundle de produção usa schema v3. */
(function exposeVehiclePrices(root) {
  const LIMIT = 40000;

  function amount(offer) {
    const value = offer?.amount_eur ?? offer?.amount ?? offer?.price_eur;
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  function dateValue(offer) {
    return offer?.validity?.valid_until || offer?.valid_until || offer?.campaign_valid_until || null;
  }

  function isExpired(offer, today = new Date()) {
    const date = dateValue(offer);
    return Boolean(date && new Date(`${date}T23:59:59`) < today);
  }

  function isActive(offer, today = new Date()) {
    const from = offer?.validity?.valid_from || offer?.valid_from || null;
    if (from && new Date(`${from}T00:00:00`) > today) return false;
    return !isExpired(offer, today);
  }

  function isStale(offer, today = new Date()) {
    const verifiedOn = offer?.proof?.verified_on || offer?.verified_on;
    if (!verifiedOn) return true;
    const verified = new Date(`${verifiedOn}T23:59:59`);
    return !Number.isFinite(verified.valueOf()) || today - verified > 45 * 24 * 60 * 60 * 1000;
  }

  function audience(offer) {
    const raw = String(offer?.customer || offer?.audience || offer?.public || "").trim().toLowerCase();
    if (["private", "particular", "consumer"].includes(raw)) return "private";
    if (["business", "company", "companies", "empresa", "empresas"].includes(raw)) return "business";
    return "unknown";
  }

  function vatState(offer) {
    if (offer?.vat === "included" || offer?.vat === "derived") return "included";
    if (offer?.vat === "excluded") return "excluded";
    if (offer?.vat_included === true || offer?.vat?.included === true) return "included";
    if (offer?.vat_included === false || offer?.vat?.included === false) return "excluded";
    return "unknown";
  }

  function offerVariantMatches(offer, car) {
    const variant = offer?.variant ?? offer?.variant_name ?? offer?.variant_id;
    if (!variant) return true;
    return String(variant).toLowerCase() === String(car.variant || "").toLowerCase();
  }

  function blockers(offer, car, today) {
    const result = [];
    const aud = audience(offer);
    const vat = vatState(offer);
    if (vat === "excluded") result.push("IVA excluído");
    else if (vat === "unknown") result.push("IVA por confirmar");
    if (aud === "unknown") result.push("Público por confirmar");
    else if (aud === "business") result.push("Apenas empresas");
    if (!offerVariantMatches(offer, car)) result.push("Versão por confirmar");
    if (isExpired(offer, today)) result.push("Oferta expirada");
    if (!offer?.source_url && !offer?.url && !offer?.evidence?.url && !offer?.proof?.source_url) result.push("Fonte por confirmar");
    if (isStale(offer, today)) result.push("Frescura por confirmar");
    if (String(offer?.kind || offer?.type || "").toLowerCase().includes("campaign") &&
        (typeof offer?.conditions !== "string" || !offer.conditions.trim())) {
      result.push("Condições por confirmar");
    }
    return result;
  }

  function rawOffers(car) {
    return Array.isArray(car?.pricing?.offers) ? car.pricing.offers : [];
  }

  function normalize(offer, car, today = new Date()) {
    const blockersList = blockers(offer, car, today);
    const kind = String(offer.kind || offer.type || "").toLowerCase();
    const confirmed = offer.classification === "confirmed" && ["list", "list_price", "campaign", "campaign_price"].includes(kind) &&
      offer.proof?.status !== "legacy_unverified" && vatState(offer) === "included" &&
      /^(private|particular|consumer)$/.test(audience(offer)) && blockersList.length === 0;
    return {
      ...offer,
      amount: amount(offer),
      type: String(offer.kind || offer.type || "list").toLowerCase().replace("_price", ""),
      confirmed,
      classification: offer.classification === "confirmed" || offer.classification === "reference"
        ? offer.classification : "unknown",
      blockers: blockersList,
      source: offer.proof?.source_url || offer.source_url || offer.url || offer.evidence?.url || null,
      verifiedOn: offer.proof?.verified_on || offer.verified_on || null,
      recordedOn: offer.proof?.recorded_on || offer.recorded_on || null,
      validUntil: dateValue(offer),
      conditions: offer.conditions ?? offer.campaign_conditions ?? null,
      vat: vatState(offer),
      audience: audience(offer),
      eligible: confirmed && amount(offer) <= LIMIT && isActive(offer, today),
    };
  }

  function getOffers(car, today) {
    return rawOffers(car).map(offer => normalize(offer, car, today)).filter(offer => offer.amount !== null);
  }

  function getPrice(car, { allowReference = false, today } = {}) {
    const offers = getOffers(car, today);
    const reference = offer => offer.classification === "reference";
    const pool = offers.filter(offer => isActive(offer, today || new Date()) &&
      (allowReference ? reference(offer) : offer.eligible));
    return pool.find(offer => offer.type === "campaign") || pool.find(offer => offer.type === "list") || null;
  }

  function getReferenceOffers(car, today) {
    return getOffers(car, today).filter(offer => offer.classification === "reference" && isActive(offer, today || new Date()));
  }

  function getFilterPrice(car, priceStatus = "all", today) {
    if (priceStatus === "confirmed_eligible") return getPrice(car, { today });
    if (priceStatus === "potential_reference") return getPrice(car, { allowReference: true, today });
    if (status(car, today) === "confirmed_eligible") return getPrice(car, { today });
    return getPrice(car, { allowReference: true, today });
  }

  function status(car, today) {
    const offers = getOffers(car, today);
    if (offers.some(offer => offer.eligible)) return "confirmed_eligible";
    if (offers.some(offer => offer.classification === "reference" && isActive(offer, today || new Date()))) return "potential_reference";
    return "not_demonstrated";
  }

  function hasConfirmedBudgetPrice(car, today) {
    const price = getPrice(car, { today });
    return Boolean(price && price.amount <= LIMIT);
  }

  const api = Object.freeze({ LIMIT, getOffers, getPrice, getReferenceOffers, getFilterPrice, status, hasConfirmedBudgetPrice, isExpired, isActive });
  root.VehiclePrices = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
