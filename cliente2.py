"""Segundo cliente para testes, baseado em cliente.py.
Instruções para testes:
No mesmo computador: python cliente2.py
Em outro computador: python cliente2.py IP_DO_SERVIDOR
Porta opcional: python cliente2.py IP_DO_SERVIDOR --porta 5000
Comandos: :nome <nome>, :quit. Demais textos sao mensagens do chat.
"""
import argparse
import socket
import threading
import sys
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000

def receber_mensagens(sock, encerrado):
    buffer = ""
    try:
        while True:
            dados = sock.recv(1024)
            if not dados:
                print("\n[CLIENTE] Conexão encerrada pelo servidor.")
                break
            
            buffer += dados.decode("utf-8", errors="ignore")
            
            while "\n" in buffer:
                linha, buffer = buffer.split("\n", 1)
                linha = linha.strip()

                if linha:
                    if linha == ": CONECTADO!!":
                        hora_str = datetime.now().strftime("%H:%M:%S")
                        print(f"{hora_str}{linha}")
                    else:
                        print(linha)
    except OSError:
        print("\n[CLIENTE] Conexão interrompida.")
    finally:
        encerrado.set()
        print("\n[CLIENTE] Pressione ENTER para finalizar a aplicação.")
        sock.close()

def main():
    parser = argparse.ArgumentParser(description="Segundo cliente do chat multiusuario.")
    parser.add_argument("host", nargs="?", default=HOST, help="IP do servidor (padrao: 127.0.0.1)")
    parser.add_argument("--porta", type=int, default=PORT, help="Porta do servidor (padrao: 5000)")
    args = parser.parse_args()
    if not 1 <= args.porta <= 65535:
        parser.error("a porta deve estar entre 1 e 65535")
    encerrado = threading.Event()
    # Cria o socket
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        cliente.connect((args.host, args.porta))
    except OSError as e:
        print(f"[ERRO] Não foi possível conectar ao servidor {args.host}:{args.porta}\nMotivo: {e}")
        cliente.close()
        sys.exit(1)

    # Inicia a Thread 2 para escutar o servidor
    t2 = threading.Thread(
        target=receber_mensagens,
        args=(cliente, encerrado),
        daemon=True
    )
    t2.start()

    
    try:
        while not encerrado.is_set():
            texto = input()
            if encerrado.is_set():
                break
            
            if not texto:
                continue
            
            # Envia para o servidor
            try:
                cliente.sendall((texto + "\n").encode("utf-8"))
            except OSError:
                break
            
            # Se o usuário digitou :quit, desconecta
            if texto.strip() == ":quit":
                break

    except (KeyboardInterrupt, EOFError):
        # Ctrl+C
        try:
            cliente.sendall(":quit\n".encode("utf-8"))
        except OSError:
            pass

    print("Encerrando cliente...")
    cliente.close()

if __name__ == "__main__":
    main()