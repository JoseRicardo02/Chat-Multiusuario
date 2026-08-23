import socket
import threading
import sys
from datetime import datetime

# Configurações do servidor ao qual vamos conectar
HOST = "127.0.0.1"  # Se o servidor estiver em outra máquina, mude para o IP dele
PORT = 5000

def thread2_recebe(sock):
    """
    Thread 2 (Cliente):
    Fica em loop contínuo aguardando mensagens vindas do servidor.
    Tudo que chega é impresso na tela.
    """
    buffer = ""
    try:
        while True:
            # Recebe dados do servidor em blocos
            dados = sock.recv(1024)
            if not dados:
                print("\n[CLIENTE] Conexão encerrada pelo servidor.")
                break
            
            buffer += dados.decode("utf-8", errors="ignore")
            
            # Processa as linhas recebidas
            while "\n" in buffer:
                linha, buffer = buffer.split("\n", 1)
                linha = linha.strip()
                if linha:
                    # Se for a MSG1 de conexão, formatamos com o horário exigido no diagrama
                    if linha == ": CONECTADO!!":
                        hora_str = datetime.now().strftime("%H:%M:%S")
                        print(f"{hora_str}{linha}")
                    else:
                        print(linha)
    except OSError:
        # Erro de SO normalmente acontece quando o socket é fechado
        pass
    finally:
        print("\n[CLIENTE] Pressione ENTER para finalizar a aplicação.")
        sock.close()

def main():
    # Cria o socket TCP do cliente
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        cliente.connect((HOST, PORT))
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor {HOST}:{PORT}\nMotivo: {e}")
        sys.exit(1)

    # Inicia a Thread 2 para escutar o servidor em segundo plano
    t2 = threading.Thread(target=thread2_recebe, args=(cliente,), daemon=True)
    t2.start()

    # Thread 1 (Main do Cliente): Fica lendo a entrada do usuário e enviando
    try:
        while True:
            # Lê o que o usuário digita no terminal
            texto = input()
            
            if not texto:
                continue
            
            # Envia para o servidor
            try:
                cliente.sendall((texto + "\n").encode("utf-8"))
            except OSError:
                break
            
            # Se o usuário digitou :quit, encerramos o loop e o programa
            if texto.strip() == ":quit":
                break

    except KeyboardInterrupt:
        # Se o usuário apertar Ctrl+C, tentamos avisar o servidor antes de sair
        try:
            cliente.sendall(":quit\n".encode("utf-8"))
        except:
            pass

    print("Encerrando cliente...")
    cliente.close()

if __name__ == "__main__":
    main()