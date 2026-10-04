"""
Fluxo (conforme diagrama):
    Cria socket, faz bind, listen e accept.
    A thread de trabalho verifica a vaga antes de enviar a MSG1: ": CONECTADO!!"
    Cria duas threads por cliente:
    Thread 1: fica lendo do socket os comandos/mensagens vindos do cliente
        e apenas os armazena numa fila (memória compartilhada).
    Thread 2: varre periodicamente essa fila e executa a ação pedida
        (mudar nome, enviar mensagem a todos ou desconectar),
        além de enviar a data/hora ao cliente a cada 1 minuto,
        independente do chat estar em idle ou não.
Para rodar:
    Primeiro é preciso ligar o servidor (server.py) e depois o cliente (client.py).
    Verificar no terminal cada um dos programas ativos e realizar testes na sessão do cliente.
    Fazer de acordo com o formulário:
            ":nome <novo_nome>" -> muda o nome do usuário
            ":quit"             -> sai do aplicativo 
"""
import socket
import threading
import queue
import time
import sys
from datetime import datetime

# Endereço e porta do servidor para aceitar conexões dos clientes.
HOST = "0.0.0.0"
PORT = 5000

# Variável global (Necessária para a sua parte enxergar o limite do Integrante 1)
MAX_CLIENTES = 0 

# Lock para proteger o dicionário de clientes no acesso concorrente.
clients_lock = threading.Lock()
clients = {}  # handle -> ClienteInfo


class ClienteInfo:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.nome = f"{addr[0]}:{addr[1]}"  # nome padrão: IP:porta
        self.fila_comandos = queue.Queue()  # "memória compartilhada" entre thread1 e thread2
        self.ativo = True
        self.ultimo_envio_hora = time.time()


def enviar_linha(conn, texto):
    """Envia uma mensagem ao cliente e informa se houve falha."""
    try:
        conn.sendall((texto + "\n").encode("utf-8"))
        return True
    except (BrokenPipeError, ConnectionResetError,
            ConnectionAbortedError, TimeoutError, OSError):
        return False

def enviar_cliente(info, texto):
    """Envia mensagem e sinaliza falha de comunicação."""
    if not info.ativo:
        return False

    if enviar_linha(info.conn, texto):
        return True

    info.fila_comandos.put(None)
    return False


def broadcast(texto, exceto_handle=None):
    # Envia uma mensagem a todos os usuários conectados, exceto quem enviou (opcional).
    # Copia a lista de clientes para evitar alteração durante a iteração.
    with clients_lock:
        destinatarios = list(clients.items())
    for handle, info in destinatarios:
        # Ignora o remetente caso tenha sido pedido.
        if handle == exceto_handle:
            continue
        enviar_cliente(info, texto)


def thread1_recebe(handle, info):
    # Thread 1 (servidor): lê do socket e apenas empilha os comandos na fila compartilhada.
    # Buffer para agrupar mensagens recebidas que podem chegar em pedaços.
    buffer = ""
    try:
        while info.ativo:
            # Lê dados do cliente em blocos de 1024 bytes.
            dados = info.conn.recv(1024)
            if not dados:
                # Se o cliente fechou a conexão, simula um comando de saída.
                info.fila_comandos.put(":quit")
                break
            buffer += dados.decode("utf-8", errors="replace")
            # Se chegou ao caractere de quebra de linha, processa a linha completa.
            while "\n" in buffer:
                linha, buffer = buffer.split("\n", 1)
                linha = linha.strip()
                if linha:
                    # Guarda cada comando ou mensagem na fila para ser processado pela thread 2.
                    info.fila_comandos.put(linha)
    except (ConnectionResetError, ConnectionAbortedError,
            BrokenPipeError, TimeoutError, OSError) as exc:
        print(
            f"[CONEXAO] Cliente {info.nome} desconectado "
            f"durante o recebimento ({type(exc).__name__})."
        )
        info.fila_comandos.put(None)

    except Exception as exc:
        print(
            f"[ERRO] Falha ao receber dados de {info.nome}: "
            f"{type(exc).__name__}: {exc}"
        )
        info.fila_comandos.put(None)


def processar_comando(handle, info, texto):
    """
    Interpreta o que veio do cliente:
    -Se começa com ':' -> comando (:nome, :quit)
    -Caso contrário -> mensagem a ser enviada a todos
    """
    # Comandos começam com ':' e são tratados separadamente.
    if texto.startswith(":"):
        partes = texto[1:].split(" ", 1)
        cmd = partes[0].lower()
        arg = partes[1].strip() if len(partes) > 1 else ""

        if cmd == "nome":
            # Comando para alterar o nome exibido do cliente.
            if arg:
                antigo = info.nome
                info.nome = arg
                enviar_cliente(info, f"Voce digitou: {texto}")
                enviar_cliente(info, f"[SERVIDOR] Nome alterado de '{antigo}' para '{arg}'")
            else:
                 enviar_cliente(info, "[SERVIDOR] Uso: :nome <novo_nome>")

        elif cmd == "quit":
            enviar_cliente(info, f"Voce digitou: {texto}")
            enviar_cliente(info, "[SERVIDOR] Encerrando conexao...")
            info.ativo = False

        else:
            enviar_cliente(info, f"[SERVIDOR] Comando desconhecido: {texto}")

    else:
        # Mensagem comum do chat: envia para todos os clientes e ecoa para o remetente.
        hora_str = datetime.now().strftime("%H:%M:%S")
        mensagem_formatada = f"{info.nome} ({hora_str}): {texto}"
        broadcast(mensagem_formatada, exceto_handle=handle)
        enviar_cliente(info, f"Voce digitou: {texto}")

def limpar_cliente(handle, info):
    """Remove o cliente e fecha a conexão uma única vez."""

    with clients_lock:
        if info.limpeza_iniciada:
            return

        info.limpeza_iniciada = True
        info.ativo = False
        clients.pop(handle, None)
        clientes_ativos = len(clients)

    try:
        info.conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass

    try:
        info.conn.close()
    except OSError:
        pass

    print(f"Cliente '{info.nome}' desconectado.")
    print(
        f"[VAGA LIBERADA] Ocupação atual do servidor: "
        f"{clientes_ativos}/{MAX_CLIENTES} cliente(s)."
    )



def thread2_processa(handle, info):
    """
    Thread 2 (servidor):
    - Varre periodicamente a fila de comandos e executa a ação solicitada.
    - Envia data/hora ao cliente a cada 60 segundos, independente de atividade.
    """
    global MAX_CLIENTES # Necessário paraler o limite global
    
    while info.ativo:
        # Processa todos os comandos pendentes na fila compartilhada.
        try:
            while True:
                comando = info.fila_comandos.get_nowait()
                processar_comando(handle, info, comando)
        except queue.Empty:
            pass

        # Envia horário/data ao cliente a cada 60 segundos.
        agora = time.time()
        if agora - info.ultimo_envio_hora >= 60:
            hora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            enviar_linha(info.conn, f"[SERVIDOR] Data/Hora: {hora_str}")
            info.ultimo_envio_hora = agora

        time.sleep(0.2)
    
    with clients_lock:
        clients.pop(handle, None) # Remove o usuário e libera a vaga
        clientes_ativos = len(clients) # Faz a recontagem
        
    try:
        info.conn.close()
    except OSError:
        pass
        
    print(f"Cliente '{info.nome}' desconectado.")
    print(f"[VAGA LIBERADA] Ocupação atual do servidor: {clientes_ativos}/{MAX_CLIENTES} cliente(s).")
   


def atender_cliente(handle, conn, addr):
    # Verifica a vaga e executa o atendimento dentro da thread de trabalho.
    with clients_lock:
        servidor_cheio = len(clients) >= MAX_CLIENTES
        if not servidor_cheio:
            info = ClienteInfo(conn, addr)
            clients[handle] = info

    if servidor_cheio:
        try:
            enviar_linha(conn, "[SERVIDOR] Servidor cheio. Nao ha vagas disponiveis. Tente novamente mais tarde.")
        finally:
            try:
                conn.close()
            except OSError:
                pass

        print(f"[SEM VAGA] Conexao recusada: {addr[0]}:{addr[1]}")
        return

    if not enviar_cliente(info, ": CONECTADO!!"):
        limpar_cliente(handle, info)
        return

    print(f"Novo cliente conectado: {info.nome} (handle={handle})")

    t1 = threading.Thread(
        target=thread1_recebe,
        args=(handle, info),
        daemon=True
    )
    t1.start()

    thread2_processa(handle, info)



def main():
    global MAX_CLIENTES # Declara para alterar a variável global
    
    if len(sys.argv) != 2:
        print("Uso: python server.py <numero_maximo_clientes>")
        sys.exit(1)

    try:
        
        MAX_CLIENTES = int(sys.argv[1])

        if MAX_CLIENTES <= 0:
            print("O numero maximo de clientes deve ser maior que 0.")
            sys.exit(1)

    except ValueError:
        print("O numero maximo de clientes deve ser um numero inteiro.")
        sys.exit(1)

    print(f"Limite maximo de clientes: {MAX_CLIENTES}")
    
    # Cria o socket TCP do servidor para receber conexões.
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permite reutilizar a porta mesmo que a conexão anterior tenha sido fechada.
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Associa o socket ao host e à porta configurados.
    servidor.bind((HOST, PORT))
    # Coloca o servidor em modo de escuta, aceitando até 5 conexões em fila.
    servidor.listen(5)
    print(f"Servidor escutando em {HOST}:{PORT}")

    handle_contador = 0
    try:
        while True:
            # Aceita uma nova conexão de cliente.
            conn, addr = servidor.accept()

            handle_contador += 1
            handle = handle_contador

            # A thread de trabalho decide se existe vaga; a principal volta ao accept.
            trabalho = threading.Thread(
                target=atender_cliente, args=(handle, conn, addr), daemon=True
            )
            trabalho.start()

    # Encerra o servidor com Ctrl+C.
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        servidor.close()

# Inicializa o servidor quando o arquivo é executado diretamente.
if __name__ == "__main__":
    main()