"""Testes de falha: python -B -W error::ResourceWarning -m unittest -v."""
import contextlib
import io
import socket
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cliente


class FalhasCliente(unittest.TestCase):
    def setUp(self):
        self.saida = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.saida)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def test_conexao_recusada_fecha_socket(self):
        sock = Mock()
        sock.connect.side_effect = ConnectionRefusedError()
        with patch('cliente.socket.socket', return_value=sock):
            self.assertEqual(cliente.executar_cliente(), 1)
        sock.close.assert_called_once()
        self.assertIn('Não foi possível conectar ao servidor.', self.saida.getvalue())

    def test_falha_ao_criar_socket(self):
        with patch('cliente.socket.socket', side_effect=OSError()):
            self.assertEqual(cliente.executar_cliente(), 1)

    def test_timeout_de_conexao(self):
        sock = Mock()
        sock.connect.side_effect = socket.timeout()
        with patch('cliente.socket.socket', return_value=sock):
            self.assertEqual(cliente.executar_cliente(), 1)
        sock.close.assert_called_once()

    def test_falha_send_e_nova_tentativa(self):
        sock = Mock()
        sock.sendall.side_effect = BrokenPipeError()
        conexao = cliente.ConexaoCliente(sock)
        self.assertFalse(conexao.enviar('mensagem'))
        self.assertFalse(conexao.enviar('apos desconexao'))
        sock.sendall.assert_called_once()
        sock.close.assert_called_once()
        self.assertTrue(conexao.encerrado.is_set())
        self.assertIn('Conexão perdida ao enviar mensagem.', self.saida.getvalue())

    def test_reset_recv_sem_excecao_na_thread(self):
        sock = Mock()
        sock.recv.side_effect = ConnectionResetError()
        conexao = cliente.ConexaoCliente(sock)
        cliente.receber_mensagens(conexao)
        self.assertTrue(conexao.encerrado.is_set())
        sock.close.assert_called_once()
        self.assertIn('Conexão interrompida', self.saida.getvalue())

    def test_timeout_recv_nao_desconecta_e_preserva_utf8(self):
        sock = Mock()
        sock.recv.side_effect = [socket.timeout(), b'ol\xc3', b'\xa1\n', b'']
        cliente.receber_mensagens(cliente.ConexaoCliente(sock))
        self.assertIn('olá', self.saida.getvalue())
        self.assertIn('Conexão encerrada pelo servidor.', self.saida.getvalue())

    def test_fechamento_repetido_e_erros_de_limpeza(self):
        sock = Mock()
        sock.shutdown.side_effect = OSError()
        sock.close.side_effect = OSError()
        conexao = cliente.ConexaoCliente(sock)
        conexao.encerrar()
        conexao.encerrar()
        sock.close.assert_called_once()

    def test_socket_real_servidor_desconecta(self):
        local, remoto = socket.socketpair()
        self.addCleanup(remoto.close)
        conexao = cliente.ConexaoCliente(local)
        self.addCleanup(conexao.encerrar)
        thread = threading.Thread(target=cliente.receber_mensagens, args=(conexao,))
        thread.start()
        remoto.close()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(local.fileno(), -1)
        self.assertFalse(conexao.enviar('mensagem tardia'))
        self.assertIn('Conexão encerrada pelo servidor.', self.saida.getvalue())

    def test_encerramento_local_desbloqueia_recv(self):
        local, remoto = socket.socketpair()
        self.addCleanup(remoto.close)
        conexao = cliente.ConexaoCliente(local)
        self.addCleanup(conexao.encerrar)
        thread = threading.Thread(target=cliente.receber_mensagens, args=(conexao,))
        thread.start()
        conexao.encerrar()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertNotIn('interrompida', self.saida.getvalue())

    def test_quit_eof_ctrl_c_encerram_thread(self):
        for entrada in (':quit', EOFError(), KeyboardInterrupt()):
            with self.subTest(entrada=repr(entrada)):
                sock = Mock()
                fechado = threading.Event()
                sock.recv.side_effect = lambda _: (fechado.wait(3), b'')[1]
                sock.shutdown.side_effect = lambda _: fechado.set()
                with patch('cliente.socket.socket', return_value=sock), patch(
                    'builtins.input', side_effect=[entrada]
                ):
                    self.assertEqual(cliente.executar_cliente(), 0)
                sock.sendall.assert_called_once_with(b':quit\n')
                sock.close.assert_called_once()
                self.assertTrue(fechado.is_set())

    def test_entrada_apos_queda_nao_envia(self):
        sock = Mock()
        liberado = threading.Event()
        fechado = threading.Event()
        sock.recv.side_effect = lambda _: (liberado.wait(3), b'')[1]
        sock.close.side_effect = fechado.set

        def entrada():
            liberado.set()
            self.assertTrue(fechado.wait(3))
            return 'mensagem depois da queda'

        with patch('cliente.socket.socket', return_value=sock), patch('builtins.input', side_effect=entrada):
            self.assertEqual(cliente.executar_cliente(), 0)
        sock.sendall.assert_not_called()
        sock.close.assert_called_once()

    def test_cliente2_processo_servidor_fecha_conexao(self):
        with socket.socket() as servidor:
            servidor.bind(('127.0.0.1', 0))
            servidor.listen()
            servidor.settimeout(5)
            processo = subprocess.Popen(
                [sys.executable, '-B', '-W', 'error::ResourceWarning', '-u', 'cliente2.py',
                 '--porta', str(servidor.getsockname()[1])],
                cwd=str(Path(__file__).parent), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                remoto, _ = servidor.accept()
                remoto.close()
                saida, erros = processo.communicate(timeout=5)
                self.assertEqual(processo.returncode, 0)
                self.assertEqual(erros, b'', erros.decode('utf-8', errors='replace'))
                self.assertIn(b'[CLIENTE]', saida)
            finally:
                if processo.poll() is None:
                    processo.kill()
                    processo.communicate()


if __name__ == '__main__':
    unittest.main()

