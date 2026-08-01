#!/usr/bin/env python3
"""Serve the offline web application, recovering automatically from port clashes."""

from __future__ import annotations

import argparse
import functools
import http.server
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
DEFAULT_PORT = 8000
DEFAULT_PORT_ATTEMPTS = 50
HOST = "127.0.0.1"


class ProjectHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Servir sempre a versão do disco.

    O handler da biblioteca padrão envia Last-Modified sem Cache-Control, o que
    autoriza o browser a guardar o bundle por heurística. Numa aplicação cujo
    objetivo é mostrar dados acabados de atualizar, isso mostra os antigos.
    """

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


def create_server(
    preferred_port: int,
    attempts: int = DEFAULT_PORT_ATTEMPTS,
) -> tuple[ProjectHTTPServer, int]:
    """Return a server on the preferred port or the next available one."""
    if not 0 <= preferred_port <= 65_535:
        raise ValueError("a porta tem de estar entre 0 e 65535")
    if attempts < 1:
        raise ValueError("o número de tentativas tem de ser positivo")

    handler = functools.partial(
        NoCacheHandler,
        directory=str(WEB_DIR),
    )
    last_error: OSError | None = None

    for port in range(preferred_port, min(preferred_port + attempts, 65_536)):
        try:
            server = ProjectHTTPServer((HOST, port), handler)
            return server, int(server.server_address[1])
        except OSError as error:
            last_error = error
            if error.errno not in {
                getattr(socket, "EADDRINUSE", 48),
                48,  # macOS
                98,  # Linux
                10048,  # Windows
            }:
                raise

    raise OSError(
        f"não foi encontrada uma porta livre entre {preferred_port} "
        f"e {min(preferred_port + attempts - 1, 65_535)}"
    ) from last_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"porta preferencial (predefinição: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--port-attempts",
        type=int,
        default=DEFAULT_PORT_ATTEMPTS,
        help="quantas portas consecutivas experimentar",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        server, selected_port = create_server(args.port, args.port_attempts)
    except (OSError, ValueError) as error:
        print(f"ERRO: {error}", flush=True)
        return 1

    if selected_port != args.port:
        print(
            f"Porta {args.port} ocupada; corrigido automaticamente para "
            f"{selected_port}.",
            flush=True,
        )
    print(f"Aplicação disponível em http://localhost:{selected_port}", flush=True)
    print("Prima Ctrl+C para parar.", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor terminado.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
