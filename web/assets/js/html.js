"use strict";

// Escape de texto para interpolação em HTML.
//
// A aplicação constrói cartões e tabelas com template strings e innerHTML a
// partir do catálogo. Nenhum valor do catálogo é escrito por um estranho, mas o
// catálogo é editado à mão e um nome perfeitamente legítimo — "Silva & Filhos",
// uma condição de campanha com "<" ou aspas — passa a produzir HTML inválido ou
// atributos truncados. Escapar na fronteira torna o render independente do
// conteúdo dos dados.
(function (root) {
  const REPLACEMENTS = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };

  // Serve texto e atributos entre aspas: as cinco substituições cobrem os dois
  // contextos, por isso não há uma segunda função a escolher errado.
  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(
      /[&<>"']/g,
      (character) => REPLACEMENTS[character],
    );
  }

  const api = {
    escapeHtml,
  };

  root.VehicleHtml = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
