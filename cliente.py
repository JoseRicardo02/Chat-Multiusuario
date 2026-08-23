import socket
import threading
import sys
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000

def receber_mensagens(sock):
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

def main():
    # Cria o socket
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        cliente.connect((HOST, PORT))
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor {HOST}:{PORT}\nMotivo: {e}")
        sys.exit(1)

    # Inicia a Thread 2 para escutar o servidor
    t2 = threading.Thread(
        target=receber_mensagens,
        args=(cliente,),
        daemon=True
    )
    t2.start()

    
    try:
        while True:
            texto = input()
            
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

    except KeyboardInterrupt:
        # Ctrl+C
        try:
            cliente.sendall(":quit\n".encode("utf-8"))
        except:
            pass

    print("Encerrando cliente...")
    cliente.close()

if __name__ == "__main__":
    main()