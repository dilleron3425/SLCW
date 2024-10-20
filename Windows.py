import socket

from subprocess import Popen
from threading import Thread
from time import time, sleep
from sys import executable
from os import _exit, path, system
from rich.console import Console

class Windows():
    def __init__(self, server, port) -> None:
        self.console = Console()
        self.server = server
        self.port = port
        self.header = 4096
        self.format = "utf-8"
        self.current_version = "1.0.0"
        self.client_socket = None
        self.client_status = None
        self.heartbeat_thread = False
        self.running = True

    def connect(self)  -> None:
        start_time = time()
        max_time = 10
        while True:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.server, self.port))
                self.console.print("[#008000]Подключение установлено![/]")
                self.client_status = 200
                if self.client_socket and self.client_status == 200:
                    system("clear")
                    self.console.print(f"""[#a0a0a0]
 ____    _       ____ __        __
/ ___|  | |     / ___ \ \      / /
\___ \  | |    | |     \ \ /\ / / 
 ___) | | |___ | |___   \ V  V / V{self.current_version} 
|____/  |_____| \____|   \_/\_/  By:Diller™
                    [/]""")
                    self.available_update(self.client_socket)
                    if self.heartbeat_thread is False or self.heartbeat_thread.is_alive() is False:
                        self.heartbeat_thread = Thread(target=self.heartbeat)
                        self.heartbeat_thread.start()
                    self.commands()
                break
            except socket.error as error:
                if time() - start_time > max_time:
                    self.console.print(f"[bold red][Ошибка][/]Не удалось подключиться к серверу в течение {max_time} секунд")
                    self.console.print(f"[bold red][Ошибка][/]Ошибка подключения: {error}")
                    self.client_status = 500
                    self.commands()
                    break
    
    def available_update(self, client_socket) -> None:
        command = client_socket.recv(self.header).decode(self.format)
        if command.startswith("New version:"):
            parts = command.split(";")
            latest_version = parts[0].split(": ")[1]
            file_size = parts[1].split(": ")[1]
            if latest_version != self.current_version:
                self.console.print(f"[blue][Инфо][/]Доступно обновление: [white]{self.current_version}[/] -> [white]{latest_version}[/]")
                current_version_size = int(path.getsize("Windows.py")) / (1024 * 1024)
                new_version_size = int(command.split()[5]) / (1024 * 1024)
                diff_version = current_version_size - new_version_size
                self.console.print(f"[blue][Инфо][/]Размер версий: [white]{current_version_size:.2}[/] МБ -> [white]{new_version_size:.2f}[/] МБ | Разница: [white]{diff_version:.2}[/] МБ")
                client_socket.sendall("Ready for update".encode(self.format))
                save_path = path.join(path.abspath(path.dirname(__file__)), f"WindowsV{latest_version}.exe")
                self.download_update(client_socket, save_path)
                self.console.print(f"[#008000][Готово][/]Обновление загружено и сохранено по пути: [#808080]{save_path}[/]")
            else:
                client_socket.sendall("Do not need".encode(self.format))
                self.console.print("[blue][Инфо][/]У вас установлена последняя версия.")
    
    def download_update(self, client_socket, save_path) -> None:
        self.console.print("[blue][Инфо][/]Начало загрузки обновления...")
        with open(save_path, 'wb') as f:
            while True:
                bytes_read = client_socket.recv(self.header)
                if bytes_read == b"END_OF_FILE":
                    self.console.print("[#008000][Готово][/]Загрузка завершена.")
                    break
                if not bytes_read:
                    self.console.print("[bold red][Ошибка][/]Соединение закрыто сервером.")
                    break
                f.write(bytes_read)
        client_socket.sendall("Download complete".encode(self.format))
        server_confirmation = client_socket.recv(self.header).decode(self.format)
        if server_confirmation == "Transfer complete":
            try:
                command = self.console.input(f"[blue][Инфо][/]Запуск нового приложения: {save_path}\nПодтвердить: [Д/Н]: ")
                if command in ["д", "да", "y", "yes"]:
                    Popen([executable, save_path])
                else:
                    _exit(0)
            except Exception as error:
                self.console.print(f"[bold red][Ошибка][/]Ошибка при запуске нового приложения: {error}")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        _exit(0)

    def heartbeat(self) -> None:
        max_attempts = 3
        while self.running:
            if self.client_socket is not None and self.client_status == 200:
                attempts = 0
                while attempts < max_attempts:
                    try:
                        self.client_socket.sendall("heartbeat".encode(self.format))
                        response = self.client_socket.recv(self.header).decode(self.format)
                        response = response.replace("ack", "").strip()
                        if not response:
                            attempts = 0
                            sleep(1)
                            break
                        else:
                            self.console.print(f"\n[#8000FF][Сервер][/]{response}", end="")
                    except UnicodeDecodeError:
                        attempts += 1
                        sleep(1)
                        break
                    except socket.error as error:
                        self.console.print(f"[bold red][Ошибка][/]Ошибка при отправке heartbeat: {error}\nНажмите Enter, чтобы перезапустить!")
                        self.client_status = 500
                        break
                    attempts += 1
                    sleep(1)
                if attempts == max_attempts:
                    self.console.print("\n[bold red][Ошибка][/]Соединение потеряно после нескольких попыток.")
                    self.client_status = 500
                    if self.client_socket:
                        self.client_socket.close()
                        self.client_socket = None
                    return
            else:
                sleep(1)
  
    def commands(self) -> None:
        while self.running:
            if self.client_socket is not None:
                while self.client_status == 500:
                    command = self.console.input("[blue][Инфо][/]Попробовать снова? [Д/Н]: ").lower()
                    if command in ["д", "да", "y", "yes"]:
                        print("Переподключение...")
                        self.connect()
                    elif command in ["н", "нет", "n", "no", "exit", "quit", "выйти"]:
                        _exit(0)
                    else:
                        pass
                while self.client_status == 200:
                    self.console.print(f"[#a0a0a0]SLCW>[/] ", end="")
                    command = input().lower()
                    if not command:
                        continue
                    elif command == "":
                        continue
                    elif command == "help":
                        self.console.print(f'\n------------------------------------------------')
                        self.console.print(f'[#a0a0a0]SLCW - первая версия программы клиент-сервер[/]')
                        self.console.print(f'[#a0a0a0]Версия[/]: {self.config["version"]}')
                        self.console.print(f'[#a0a0a0]Разработчик[/]: {self.config["created_by"]}')
                        self.console.print(f'[#a0a0a0]GitHub[/]: {self.config["urls"]["url_github"]}')
                        self.console.print(f'------------------------------------------------')
                        self.console.print(f"    |         Command       |                Description               |\n")
                        self.console.print(f"    | clear / cls           | Console cleaner                          |")
                        self.console.print(f"    | help                  | Output help window                       |")
                        self.console.print(f"    | exit                  | Out George?                              |\n")
                    if command in ["exit", "quit", "выйти"]:
                        self.running = False
                        if self.client_socket:
                            try:
                                self.client_socket.sendall("exit".encode(self.format))
                            except socket.error as error:
                                self.console.print(f"[bold red][Ошибка][/]Ошибка при отправке команды exit: {error}")
                            finally:
                                self.client_socket.close()
                                self.client_socket = None
                        _exit(0)
                    else:
                        self.client_socket.sendall(command.encode(self.format))
                        self.console.print("[#008000][Готово][/]Команда отправлена.")

    def run(self) -> None:
        try:
            while self.running:
                if self.client_socket is None and self.client_status is None:
                    print("Подключение...")
                    self.connect()
        except KeyboardInterrupt:
            _exit(0)
        finally:
            self.client_socket.close()
            _exit(0)

if __name__ == "__main__":
    windows = Windows(server=IP, port=PORT)
    windows.run()
