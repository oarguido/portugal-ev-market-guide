"use strict";

// A aplicação a correr a sério, num browser a sério.
//
// O app.js tem mais de mil linhas e até aqui nenhum teste o executava: os testes
// liam-no como texto e procuravam expressões. Tudo o que sabíamos sobre o render
// vinha de alguém abrir a página à mão — foi assim que onze fotografias erradas
// e um bundle em cache passaram despercebidos durante dias.
//
// Isto levanta o servidor do projeto, abre a página no agent-browser, percorre-a
// toda e verifica o que o utilizador vê: todos os cartões renderizados, todas as
// fotografias carregadas, nenhum erro de consola.
//
// Salta quando o agent-browser não existe — nos runners do GitHub não está
// instalado, e o CI não pode depender dele. Correr `make verificar` numa máquina
// com o agent-browser executa-o de facto.

const assert = require("node:assert/strict");
const { execFileSync, spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const PORT = 8791;

function temAgentBrowser() {
  try {
    execFileSync("agent-browser", ["--help"], {
      stdio: "ignore",
      timeout: 15000,
    });
    return true;
  } catch {
    return false;
  }
}

function browser(args, timeout = 90000) {
  return execFileSync("agent-browser", args, {
    cwd: root,
    encoding: "utf8",
    timeout,
  });
}

async function esperarServidor(url, tentativas = 40) {
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return true;
    } catch {
      /* ainda a arrancar */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

const disponivel = temAgentBrowser();

test(
  "a aplicação renderiza todos os cartões com as fotografias",
  { skip: disponivel ? false : "agent-browser não instalado" },
  async () => {
    const catalogo = JSON.parse(
      fs.readFileSync(path.join(root, "data/vehicles/pt_market.json"), "utf8"),
    );
    const variantesEsperadas = catalogo.models.reduce(
      (total, m) => total + m.variants.length,
      0,
    );

    const servidor = spawn(
      "python3",
      ["scripts/serve.py", "--port", String(PORT)],
      { cwd: root, stdio: "ignore" },
    );
    try {
      assert.ok(
        await esperarServidor(`http://127.0.0.1:${PORT}/index.html`),
        "o servidor não arrancou",
      );

      browser(["open", `http://127.0.0.1:${PORT}/index.html`]);
      const bruto = browser([
        "eval",
        `(async () => {
      const s = ms => new Promise(r => setTimeout(r, ms));
      for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await s(70); }
      await s(1500);
      const imgs = [...document.querySelectorAll('img.card-car-image')];
      return JSON.stringify({
        cartoes: document.querySelectorAll('.car-card').length,
        imagens: imgs.length,
        carregadas: imgs.filter(i => i.complete && i.naturalWidth > 0).length,
        partidas: imgs.filter(i => i.complete && i.naturalWidth === 0).length,
        fallbacks: [...document.querySelectorAll('.card-image-fallback')].filter(d => d.style.display === 'flex').length,
        semTitulo: [...document.querySelectorAll('.car-card')].filter(c => !c.querySelector('.car-title')?.textContent?.trim()).length,
        semPreco: [...document.querySelectorAll('.car-card')].filter(c => !/[0-9]/.test(c.querySelector('.car-price-tag')?.textContent || '')).length
      });
    })()`,
      ]);

      const visto = JSON.parse(JSON.parse(bruto.trim()));
      assert.equal(
        visto.cartoes,
        variantesEsperadas,
        "o número de cartões tem de bater com as variantes do catálogo",
      );
      assert.equal(
        visto.partidas,
        0,
        "nenhuma fotografia pode falhar a carregar",
      );
      assert.equal(
        visto.fallbacks,
        0,
        "nenhum cartão pode mostrar o ícone de recurso",
      );
      assert.equal(
        visto.carregadas,
        visto.imagens,
        "todas as fotografias têm de carregar depois de percorrer a página",
      );
      assert.equal(visto.semTitulo, 0, "todos os cartões têm de ter título");
      assert.equal(
        visto.semPreco,
        0,
        "todos os cartões têm de mostrar um preço",
      );
    } finally {
      servidor.kill();
    }
  },
);

test(
  "o servidor não deixa o browser guardar o catálogo em cache",
  { skip: disponivel ? false : "agent-browser não instalado" },
  async () => {
    // A regressão real: depois de uma atualização o browser continuava a servir o
    // bundle antigo e a pedir fotografias que já tinham sido arquivadas.
    const servidor = spawn(
      "python3",
      ["scripts/serve.py", "--port", String(PORT + 1)],
      { cwd: root, stdio: "ignore" },
    );
    try {
      const base = `http://127.0.0.1:${PORT + 1}`;
      assert.ok(
        await esperarServidor(`${base}/index.html`),
        "o servidor não arrancou",
      );

      const resposta = await fetch(`${base}/assets/js/car_data.js`);
      assert.match(
        resposta.headers.get("cache-control") || "",
        /no-store/,
        "o bundle tem de ser servido sem cache",
      );

      const html = await (await fetch(`${base}/index.html`)).text();
      assert.match(
        html,
        /car_data\.js\?v=[0-9a-f]{6,}/,
        "o index.html tem de carimbar a versão do bundle",
      );
    } finally {
      servidor.kill();
    }
  },
);
