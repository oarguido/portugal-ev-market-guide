"""Camada única sobre o `agent-browser`.

Quatro scripts passaram a precisar de um browser a sério — o update_catalog para
as fontes que devolvem 403, o refresh_prices para ler preços, o discover_models
para radares em JavaScript e o capture_photos para as fotografias. Cada um
inventou a sua própria invocação, e os tempos limite acabaram em 90, 90, 120 e
120 segundos sem que ninguém tivesse decidido isso.

Aqui fica uma só. Quem precisar de outro tempo limite passa-o; quem não precisar
fica com o mesmo que todos os outros.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 120


def run(*arguments: str, timeout: int = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Executar um comando do agent-browser, sem nunca levantar exceção."""
    return subprocess.run(
        ["agent-browser", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def open_page(url: str, *, settle_ms: int = 1800, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """Abrir a página e dar-lhe tempo para assentar. False se não abriu."""
    if run("open", url, timeout=timeout).returncode:
        return False
    run("wait", str(settle_ms), timeout=timeout)
    return True


def evaluate(script: str, *, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Correr JavaScript e devolver a saída já sem as aspas exteriores.

    O agent-browser devolve o resultado como JSON, por isso uma string vem
    envolvida em aspas. Descascar aqui evita que cada chamador se lembre — ou se
    esqueça — de o fazer.
    """
    result = run("eval", script, timeout=timeout)
    if result.returncode:
        return ""
    saida = result.stdout.strip()
    try:
        descodificado = json.loads(saida)
    except (json.JSONDecodeError, ValueError):
        return saida
    return descodificado if isinstance(descodificado, str) else saida


def page_text(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """Texto visível de uma página, aberta num browser real.

    É isto que resolve as fontes onde o urllib não entra: 403 da Stellantis, da
    Tesla, da Volvo e da Hyundai, e a mini.pt que fecha a ligação sem responder.
    """
    if not open_page(url, timeout=timeout):
        return None
    result = run("get", "text", "body", timeout=timeout)
    texto = result.stdout.strip() if result.returncode == 0 else ""
    return texto or None
