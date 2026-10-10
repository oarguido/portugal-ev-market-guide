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

  // Potência: mostra apenas os valores confirmados; um deles pode ser null.
  function formatPower(specs, withKw = false) {
    const hp = specs && specs.power_hp;
    const kw = specs && specs.power_kw;
    if (hp && kw && withKw) return `${hp} cv (${kw} kW)`;
    if (hp) return `${hp} cv`;
    if (kw) return `${kw} kW`;
    return "N/A";
  }

  const api = {
    boolLabel,
    v2lLabel,
    cellValue,
    formatPower,
  };

  root.VehicleSpecs = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
