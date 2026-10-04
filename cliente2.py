"""Segundo cliente: python cliente2.py [IP_DO_SERVIDOR] [--porta 5000]."""
import argparse

from cliente import HOST, PORT, executar_cliente


def main():
    parser = argparse.ArgumentParser(description="Segundo cliente do chat multiusuario.")
    parser.add_argument("host", nargs="?", default=HOST, help="IP do servidor (padrao: 127.0.0.1)")
    parser.add_argument("--porta", type=int, default=PORT, help="Porta do servidor (padrao: 5000)")
    args = parser.parse_args()
    if not 1 <= args.porta <= 65535:
        parser.error("a porta deve estar entre 1 e 65535")
    return executar_cliente(args.host, args.porta)


if __name__ == "__main__":
    raise SystemExit(main())
