import socket
import threading
import sys
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000


def receber_mensagens(sock):
    """
    Thread 2 (Cliente):
    Fica em loop contínuo aguardando mensagens vindas do servidor.
    Tudo que chega é impresso na tela.
    """
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

    finally:
        print("\n[CLIENTE] Pressione ENTER para finalizar a aplicação.")
        sock.close()
