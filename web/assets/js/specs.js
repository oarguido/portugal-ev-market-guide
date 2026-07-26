"use strict";

// Rotulagem de especificações para a tabela de comparação.
//
// Regra central: um campo ausente não é uma negação. O catálogo só regista o
// que foi confirmado em fonte oficial portuguesa, por isso um dado que não
// existe tem de aparecer como "N/A" e nunca como "Não" — caso contrário a
// tabela afirma factos que ninguém verificou.
(function (root) {
  function boolLabel(value) {
    if (value === true) return "Sim";
    if (value === false) return "Não";
    return "N/A";
  }

  function v2lLabel(car) {
    const bidi =
      car &&
      car.technology_advantages &&
      car.technology_advantages.bidirectional_charging;
    const supported = bidi ? bidi.v2l_supported : undefined;
    if (supported !== true) return boolLabel(supported);
    return bidi.v2l_max_power_kw ? `Sim (${bidi.v2l_max_power_kw} kW)` : "Sim";
  }

  function cellValue(value) {
    return value === null || value === undefined ? "N/A" : value;
  }

  const api = {
    boolLabel,
    v2lLabel,
    cellValue,
  };

  root.VehicleSpecs = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
