import socket

from subprocess import Popen
from threading import Thread
from time import time, sleep
from sys import executable
from os import _exit, path, system, remove
from rich.console import Console
from shutil import move

class WindowsClient():
    def __init__(self, server: str, port: int) -> None:
        self.console = Console()
        self.server = server
        self.port = port
        self.header = 4096
        self.format = "utf-8"
        self.current_version = "1.2.1"
        self.client_socket = None
        self.client_status = None
        self.heartbeat_thread = False
        self.running = True

    def print_sys_logo(self) -> str:
        system("cls")
        return (f"""[#a0a0a0]
 ____    _       ____ __        __
/ ___|  | |     / ___ \\ \\      / /
\\___ \\  | |    | |     \\ \\ /\\ / / 
 ___) | | |___ | |___   \\ V  V / V{self.current_version} 
|____/  |_____| \\____|   \\_/\\_/  By:Diller™
                    [/]""")

    def connect(self, time_to_connect: int)  -> None:
        start_time = time()
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.client_socket:
                    self.client_socket.connect((self.server, self.port))
                    self.client_socket.sendall("SLCW_CLIENT".encode(self.format))
                    self.client_status = 200
                    self.console.print(self.print_sys_logo())
                    self.available_update(self.client_socket)
                    self.start_heartbeat_thread()
                    self.commands()
                    break
            except OSError as error:
                if time() - start_time > time_to_connect:
                    self.handle_connection_error(time_to_connect, error)
                    break

    def available_update(self, client_socket) -> None:
        command = client_socket.recv(self.header).decode(self.format)
        current_executable_path = path.abspath(executable)
        if not command.startswith("New version:"):
            return
        try:
            parts = command.split(";")
            latest_version = parts[0].split(": ")[1]
            new_version_size = float(parts[1].split(": ")[1])
        except (IndexError, ValueError) as error:
            self.console.print(f"[bold red][Ошибка][/]Не удаётся получить информацию о новой версии: {error}")
            return
        if latest_version == self.current_version:
            self.handle_latest_version(client_socket, current_executable_path)
            return
        self.console.print(f"[blue][Инфо][/]Доступно обновление: [white]{self.current_version}[/] -> [white]{latest_version}[/]")
        try:
            current_version_size = int(path.getsize("SLCW.exe")) / (1024 * 1024)
            diff_version = current_version_size - new_version_size
            self.console.print(f"[blue][Инфо][/]Размер версий: [white]{current_version_size:.2}[/] МБ -> [white]{new_version_size:.2f}[/] МБ | Разница: [white]{diff_version:.2}[/] МБ")
            client_socket.sendall("Ready for update".encode(self.format))
            save_path = path.join(path.abspath(path.dirname(executable)), f"NEW_SLCW.exe")
            self.download_update(client_socket, save_path)
            self.replace_executable(save_path, current_executable_path)
            self.launch_new_app(save_path)
        except Exception as error:
            self.console.print(f"[bold red][Ошибка][/]Не удалось скачать обновление: {error}")
            return

    def handle_latest_version(self, client_socket, current_executable_path: str):
        application = "SLCW.exe"
        target_executable_path = path.abspath(application)
        if current_executable_path != target_executable_path:
            try:
                remove(target_executable_path)
                self.console.print(f"[blue][Инфо][/]Старый файл {application} удалён")
            except Exception as error:
                if error.errno == 2:
                    self.console.print(f"[bold red][Ошибка][/]Не удалось найти старый файл [#808080]{application}[/]")
                else:
                    self.console.print(f"[bold red][Ошибка][/]Не удалось удалить старый файл {application}: {error}")
            try:
                move(current_executable_path, target_executable_path)
                self.console.print(f"[blue][Инфо][/]Текущий файл переименован в {application}")
            except Exception as error:
                self.console.print(f"[bold red][Ошибка][/]Не удалось переименовать текущий файл на {application}: {error}")
        client_socket.sendall("Do not need".encode(self.format))
        self.console.print("[blue][Инфо][/]У вас установлена последняя версия")
        return

    def replace_executable(self, save_path: str, current_executable_path: str):
        try:
            move(save_path, current_executable_path)
            self.console.print(f"[#008000][Готово][/]Обновление загружено и сохранено по пути: [#808080]{save_path}[/]")
        except Exception as error:
            self.console.print(f"[bold yellow][Предупреждение][/] Не удалось переместить или переименовать файл: {error}")

    def launch_new_app(self, save_path: str):
        self.console.print(f"[blue][Инфо][/]Запуск нового приложения...")
        sleep(2)
        if path.exists(save_path):
            try:
                Popen([save_path])
                _exit(0)
            except Exception as error:
                self.console.print(f"[bold red][Ошибка][/]Не удалось запустить новое приложение: {error}")
                return
        else:
            self.console.print(f"[bold red][Ошибка][/]Файл не найден: {save_path}")
            return

    def download_update(self, client_socket, save_path) -> None:
        self.console.print("[blue][Инфо][/]Загрузка обновления...")
        try:
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = client_socket.recv(self.header)
                    if bytes_read == b"END_OF_FILE":
                        self.console.print("[#008000][Готово][/]Загрузка завершена")
                        self.console.print("[blue][Инфо][/]Подождите...")
                        break
                    if not bytes_read:
                        self.console.print("[bold red][Ошибка][/]Соединение закрыто сервером")
                        break
                    f.write(bytes_read)
            client_socket.sendall("Download complete".encode(self.format))
            server_confirmation = client_socket.recv(self.header).decode(self.format)
            if server_confirmation != "Transfer complete":
                self.console.print(f"[bold red][Ошибка][/]Сервер не подтвердил скачивание")
        except Exception as error:
            self.console.print(f"[bold red][Ошибка][/]Не удалось сохранить обновление: {error}")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

    def start_heartbeat_thread(self) -> None:
        if self.heartbeat_thread is False or not self.heartbeat_thread.is_alive():
            self.heartbeat_thread = Thread(target=self.heartbeat)
            self.heartbeat_thread.start()

    def handle_connection_error(self, time_to_connect: int, error: OSError) -> None:
        if error.errno == 111:
            self.console.print(f"[bold red][Ошибка][/]Не удалось подключиться к серверу в течение {time_to_connect} секунд, возможно, сервер не работает")
        else:
            self.console.print(f"[bold red][Ошибка][/]Не удалось подключиться к серверу в течение {time_to_connect} секунд")
            self.console.print(f"[bold red][Ошибка][/]Ошибка подключения: {error}")
        self.client_status = 500
        self.commands()

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
                        self.console.print(f"[bold red][Ошибка][/]Ошибка при отправке heartbeat: {error}\nНажмите Enter, чтобы перезапустить")
                        self.client_status = 500
                        break
                    attempts += 1
                    sleep(1)
                if attempts == max_attempts:
                    self.console.print("\n[bold red][Ошибка][/]Соединение потеряно после нескольких попыток")
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
                        self.connect(10)
                    elif command in ["н", "нет", "n", "no", "exit", "quit", "выйти"]:
                        _exit(0)
                    else:
                        pass
                while self.client_status == 200:
                    self.console.print(f"[#a0a0a0]SLCW>[/] ", end="")
                    command = input().lower()
                    if not command or command == "":
                        continue
                    elif command == "help":
                        self.console.print(f'\n[#a0a0a0]SLCW: первая версия программы клиент-сервер[/]')
                        self.console.print(f'[#a0a0a0]Версия[/]: {self.current_version}')
                        self.console.print(f'[#a0a0a0]Разработчик[/]: Diller™')
                        self.console.print(f'[#a0a0a0]GitHub[/]: https://github.com/dilleron3425\n')
                        self.console.print(f'    --------------------------------------------------------------------')
                        self.console.print(f"    |         Команда       |                  Описание                |\n")
                        self.console.print(f"    | help                  | Вывести список команд                    |")
                        self.console.print(f"    | clear / cls           | Очистить консоль                         |")
                        self.console.print(f"    | exit / quit / выйти   | Выйти из SLCW                            |")
                        self.console.print(f"    | start (server-name)   | Запустить игровой сервер                 |")
                        self.console.print(f"    | stop (server-name)    | Остановить игровой сервер                |")
                        self.console.print(f"    | status (server-name)  | Вывести статус игровой сервер            |")
                        self.console.print(f"    | restart (server-name) | Перезапустить игровой сервер             |")
                        self.console.print(f'    --------------------------------------------------------------------')
                    elif command in ["exit", "quit", "выйти"]:
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
                    elif command in ["clear", "cls"]:
                        self.console.print(self.print_sys_logo())
                    else:
                        self.client_socket.sendall(command.encode(self.format))
                        self.console.print("[#008000][Готово][/]Команда отправлена")

    def run(self) -> None:
        try:
            while self.running:
                if self.client_socket is None and self.client_status is None:
                    print("Подключение...")
                    self.connect(10)
        except KeyboardInterrupt:
            _exit(0)
        finally:
            sleep(5)
            self.client_socket.close()
            _exit(0)

if __name__ == "__main__":
    windows = WindowsClient(server=IP, port=PORT)
    windows.run()
