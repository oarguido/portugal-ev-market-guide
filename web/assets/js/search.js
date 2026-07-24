/* Pesquisa tolerante para o catálogo automóvel. */
(function exposeVehicleSearch(root) {
  "use strict";

  function normalizeSearchText(value) {
    return String(value ?? "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("pt-PT")
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .replace(/\s+/g, " ");
  }

  function editDistanceWithin(left, right, maximumDistance) {
    if (Math.abs(left.length - right.length) > maximumDistance) return false;

    let previous = Array.from({ length: right.length + 1 }, (_, index) => index);

    for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
      const current = [leftIndex];
      let rowMinimum = current[0];

      for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
        const substitutionCost = left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1;
        const distance = Math.min(
          previous[rightIndex] + 1,
          current[rightIndex - 1] + 1,
          previous[rightIndex - 1] + substitutionCost
        );
        current.push(distance);
        rowMinimum = Math.min(rowMinimum, distance);
      }

      if (rowMinimum > maximumDistance) return false;
      previous = current;
    }

    return previous[right.length] <= maximumDistance;
  }

  function tokenMatches(queryToken, targetToken) {
    if (queryToken === targetToken) return true;
    if (queryToken.length >= 2 && targetToken.includes(queryToken)) return true;

    const maximumDistance = queryToken.length >= 9 ? 2 : queryToken.length >= 5 ? 1 : 0;
    return maximumDistance > 0 && editDistanceWithin(queryToken, targetToken, maximumDistance);
  }

  function matchesVehicleSearch(vehicle, query) {
    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) return true;

    const searchableText = [
      vehicle.brand,
      vehicle.model,
      vehicle.variant,
      vehicle.segment
    ].filter(Boolean).join(" ");
    const normalizedTarget = normalizeSearchText(searchableText);

    if (normalizedTarget.includes(normalizedQuery)) return true;

    const compactQuery = normalizedQuery.replace(/\s/g, "");
    const compactTarget = normalizedTarget.replace(/\s/g, "");
    if (compactQuery.length >= 2 && compactTarget.includes(compactQuery)) return true;

    const targetTokens = normalizedTarget.split(" ");
    return normalizedQuery
      .split(" ")
      .every(queryToken => targetTokens.some(targetToken => tokenMatches(queryToken, targetToken)));
  }

  const api = {
    normalizeSearchText,
    matchesVehicleSearch
  };

  root.VehicleSearch = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
