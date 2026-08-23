"""
Fluxo (conforme diagrama):
    Cria socket, faz bind, listen e accept.
    Ao aceitar uma conexão, envia imediatamente a MSG1: ": CONECTADO!!"
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
from datetime import datetime

# Endereço e porta do servidor para aceitar conexões dos clientes.
HOST = "0.0.0.0"
PORT = 5000

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
    # Envia uma mensagem em formato de linha para o cliente atual.
    try:
        conn.sendall((texto + "\n").encode("utf-8"))
    except OSError:
        pass


def broadcast(texto, exceto_handle=None):
    """Envia uma mensagem a todos os usuários conectados, exceto quem enviou (opcional)."""
    # Copia a lista de clientes para evitar alteração durante a iteração.
    with clients_lock:
        destinatarios = list(clients.items())
    for handle, info in destinatarios:
        # Ignora o remetente caso tenha sido pedido.
        if handle == exceto_handle:
            continue
        enviar_linha(info.conn, texto)


def thread1_recebe(handle, info):
    """Thread 1 (servidor): lê do socket e apenas empilha os comandos na fila compartilhada."""
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
            buffer += dados.decode("utf-8", errors="ignore")
            # Se chegou ao caractere de quebra de linha, processa a linha completa.
            while "\n" in buffer:
                linha, buffer = buffer.split("\n", 1)
                linha = linha.strip()
                if linha:
                    # Guarda cada comando ou mensagem na fila para ser processado pela thread 2.
                    info.fila_comandos.put(linha)
    except OSError:
        pass


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
                enviar_linha(info.conn, f"Voce digitou: {texto}")
                enviar_linha(info.conn, f"[SERVIDOR] Nome alterado de '{antigo}' para '{arg}'")
            else:
                # Explica como usar o comando quando ele for invocado sem argumento.
                enviar_linha(info.conn, "[SERVIDOR] Uso: :nome <novo_nome>")

        elif cmd == "quit":
            # Comando para encerrar a sessão do cliente no servidor.
            enviar_linha(info.conn, f"Voce digitou: {texto}")
            enviar_linha(info.conn, "[SERVIDOR] Encerrando conexao...")
            info.ativo = False

        else:
            # Qualquer comando desconhecido é informado ao usuário.
            enviar_linha(info.conn, f"[SERVIDOR] Comando desconhecido: {texto}")
    else:
        # Mensagem comum do chat: envia para todos os clientes e ecoa para o remetente.
        hora_str = datetime.now().strftime("%H:%M:%S")
        mensagem_formatada = f"{info.nome} ({hora_str}): {texto}"
        broadcast(mensagem_formatada, exceto_handle=handle)
        enviar_linha(info.conn, f"Voce digitou: {texto}")


def thread2_processa(handle, info):
    """
    Thread 2 (servidor):
    - Varre periodicamente a fila de comandos e executa a ação solicitada.
    - Envia data/hora ao cliente a cada 60 segundos, independente de atividade.
    """
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

    # Limpeza ao desconectar o cliente: remove da lista e fecha a conexão.
    with clients_lock:
        clients.pop(handle, None)
    try:
        info.conn.close()
    except OSError:
        pass
    print(f"Cliente '{info.nome}' desconectado.")


def main():
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

            # Armazena as informações do cliente em um registro do servidor.
            info = ClienteInfo(conn, addr)
            with clients_lock:
                clients[handle] = info

            # Envia imediatamente a MSG1 de confirmação de conexão.
            enviar_linha(conn, ": CONECTADO!!")
            print(f"Novo cliente conectado: {info.nome} (handle={handle})")

            # Cria as duas threads do cliente: recebimento e processamento.
            t1 = threading.Thread(target=thread1_recebe, args=(handle, info), daemon=True)
            t2 = threading.Thread(target=thread2_processa, args=(handle, info), daemon=True)
            t1.start()
            t2.start()
    # Encerra o servidor com Ctrl+C.
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        servidor.close()

# Inicializa o servidor quando o arquivo é executado diretamente.
if __name__ == "__main__":
    main()
