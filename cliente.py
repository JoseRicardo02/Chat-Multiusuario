import codecs
import socket
import sys
import threading
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000


class ConexaoCliente:
    """Coordena o encerramento entre o teclado e a thread de recebimento."""

    def __init__(self, sock):
        self.sock = sock
        self.encerrado = threading.Event()
        self._lock = threading.Lock()

    def encerrar(self, mensagem=None):
        # Apenas a primeira chamada avisa e fecha a conexão.
        with self._lock:
            if self.encerrado.is_set():
                return
            self.encerrado.set()
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                try:
                    self.sock.close()
                except OSError:
                    pass
            if mensagem:
                print(f"\n[CLIENTE] {mensagem}")
                print("[CLIENTE] Pressione ENTER para finalizar a aplicação.")

    def enviar(self, texto):
        if self.encerrado.is_set():
            return False
        try:
            self.sock.sendall((texto + "\n").encode("utf-8"))
            return True
        except OSError:
            self.encerrar("Conexão perdida ao enviar mensagem.")
            return False


def receber_mensagens(conexao):
    buffer = ""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    try:
        while not conexao.encerrado.is_set():
            try:
                dados = conexao.sock.recv(1024)
            except socket.timeout:
                continue
            if not dados:
                conexao.encerrar("Conexão encerrada pelo servidor.")
                break
            buffer += decoder.decode(dados)
            while "\n" in buffer:
                linha, buffer = buffer.split("\n", 1)
                linha = linha.strip()
                if linha == ": CONECTADO!!":
                    print(f"{datetime.now():%H:%M:%S}{linha}")
                elif linha:
                    print(linha)
    except OSError:
        conexao.encerrar("Conexão interrompida durante o recebimento.")
    finally:
        conexao.encerrar()


def executar_cliente(host=HOST, porta=PORT):
    # Terminais com codificação limitada ainda devem exibir mensagens sem falhar.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    cliente = None
    conexao = None
    receptora = None
    try:
        try:
            cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cliente.settimeout(5)
            cliente.connect((host, porta))
        except (OSError, OverflowError, ValueError):
            print("[CLIENTE] Não foi possível conectar ao servidor.")
            return 1

        # Limita envios bloqueados e permite revisar o evento no recebimento.
        cliente.settimeout(1)
        conexao = ConexaoCliente(cliente)
        receptora = threading.Thread(target=receber_mensagens, args=(conexao,))
        try:
            receptora.start()
        except RuntimeError:
            receptora = None
            print("[CLIENTE] Não foi possível iniciar o recebimento de mensagens.")
            return 1

        while not conexao.encerrado.is_set():
            texto = input()
            # input pode retornar depois de a thread detectar a desconexão.
            if conexao.encerrado.is_set():
                break
            if not texto:
                continue
            if not conexao.enviar(texto) or texto.strip() == ":quit":
                break
    except (KeyboardInterrupt, EOFError):
        if conexao is not None:
            conexao.enviar(":quit")
    except OSError:
        print("[CLIENTE] Não foi possível continuar a comunicação ou ler o terminal.")
        return 1
    finally:
        if conexao is not None:
            conexao.encerrar()
        elif cliente is not None:
            try:
                cliente.close()
            except OSError:
                pass
        if receptora is not None:
            receptora.join()
        if conexao is not None:
            print("[CLIENTE] Cliente encerrado.")
    return 0


def main():
    return executar_cliente()


if __name__ == "__main__":
    raise SystemExit(main())
