import socket

from psutil import process_iter, NoSuchProcess, AccessDenied, TimeoutExpired
from os import path, system, remove, makedirs, getpid
from pystray import Icon, MenuItem, Menu
from webbrowser import open as web_open
from sys import executable, exit, argv
from threading import Thread, Event
from signal import signal, SIGINT
from rich.console import Console
from subprocess import Popen
from time import time, sleep
from ctypes import windll
from shutil import move
from PIL import Image

class WindowsClient():
    def __init__(self, server: str, port: int) -> None:
        self.console = Console()
        self.server = server
        self.port = port
        self.header = 4096
        self.format = "utf-8"
        self.current_version = "1.3.0"
        self.client_socket = None
        self.client_status = None
        self.heartbeat_thread = None
        self.heartbeat_thread_stop = Event()
        self.tray_thread = None
        self.tray_thread_stop = Event()
        self.running = True
        self.time_to_connect = 10
        self.icon_path = path.join(path.expanduser("~"), "SLCW", "SLCW.ico")

    def signal_handler(self, sig, frame) -> None:
        """Обработчик сигналов"""
        self.hide_app()

    def print_sys_logo(self) -> str:
        """Выводит логотип программы в консоль"""
        system("cls")
        return (f"""[#a0a0a0]
 ____    _       ____ __        __
/ ___|  | |     / ___ \\ \\      / /
\\___ \\  | |    | |     \\ \\ /\\ / / 
 ___) | | |___ | |___   \\ V  V / V{self.current_version} 
|____/  |_____| \\____|   \\_/\\_/  By:Diller™
                    [/]""")

    def hide_app(self) -> None:
        """Скрывает приложение"""
        hwnd = windll.kernel32.GetConsoleWindow()
        if hwnd:
            windll.user32.ShowWindow(hwnd, 0)

    def show_app(self) -> None:
        """Показывает приложение"""
        hwnd = windll.kernel32.GetConsoleWindow()
        if hwnd:
            windll.user32.ShowWindow(hwnd, 5)
            windll.user32.ShowWindow(hwnd, 9)

    def handle_error(self, message: str, error: any) -> None:
        """Обработка ошибок и вывод сообщение в консоль"""
        self.console.print(f"\n[bold red][Ошибка][/]{message}: {error}")

    def connect(self)  -> None:
        """Подключает клиента к серверу"""
        start_time = time()
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.client_socket:
                    self.client_socket.connect((self.server, self.port))
                    self.client_socket.sendall("SLCW_CLIENT".encode(self.format))
                    self.console.print(self.print_sys_logo())
                    self.available_update()
                    self.client_status = 200
                    self.start_heartbeat_thread()
                    self.commands()
                    break
            except OSError as error:
                if time() - start_time > self.time_to_connect:
                    if error.errno == 111 or 10061: # Не удалось установить соединение
                        self.console.print(f"[bold red][Ошибка][/]Не удалось подключиться к серверу в течение {self.time_to_connect} секунд, возможно, сервер не работает")
                    else:
                        self.console.print(f"[blue][Инфо][/]Не удалось подключиться к серверу в течение {self.time_to_connect} секунд")
                        self.console.print(f"[bold red][Ошибка][/]Ошибка подключения: {error}")
                    self.client_status = 500
                    if self.client_socket:
                        self.client_socket.close()
                        self.client_socket = None
                    self.commands()
                    return

    def available_update(self) -> None:
        """Проверяет доступность обновления"""
        command = self.client_socket.recv(self.header).decode(self.format)
        current_executable_path = path.abspath(executable)
        if not command.startswith("New version:"):
            return
        try:
            parts = command.split(";")
            latest_version = parts[0].split(": ")[1]
            new_version_size = float(parts[1].split(": ")[1])
        except (IndexError, ValueError) as error:
            self.handle_error("Не удаётся получить информацию о новой версии", error)
            return
        if latest_version == self.current_version:
            self.handle_latest_version(current_executable_path)
            return
        self.console.print(f"[blue][Инфо][/]Доступно обновление: [white]{self.current_version}[/] -> [white]{latest_version}[/]")
        try:
            current_version_size = int(path.getsize("SLCW.exe")) / (1024 * 1024)
            diff_version = current_version_size - new_version_size
            self.console.print(f"[blue][Инфо][/]Размер версий: [white]{current_version_size:.2f}[/] МБ -> [white]{new_version_size:.2f}[/] МБ | Разница: [white]{diff_version:.2f}[/] МБ")
            self.client_socket.sendall("Ready for update".encode(self.format))
            save_path = path.join(path.abspath(path.dirname(executable)), f"NEW_SLCW.exe")
            if save_path:
                self.download_update(save_path, latest_version)
                self.replace_executable(save_path, current_executable_path)
                self.launch_new_app(save_path)
            else:
                self.console.print(f"[bold red][Ошибка][/]Не удалось сохранить файл обновления по пути: {save_path}")
        except Exception as error:
            self.handle_error("Не удалось скачать обновление", error)
            return

    def handle_latest_version(self, current_executable_path: str) -> None:
        """Обрабатывает ситуацию, когда новая версия не доступна"""
        application = "SLCW.exe"
        target_executable_path = path.abspath(application)
        if current_executable_path != target_executable_path:
            sleep(1)
            try:
                remove(target_executable_path)
                self.console.print(f"[blue][Инфо][/]Старый файл {application} удалён")
            except OSError as error:
                if error.errno == 2: # Нету файл или папки
                    self.console.print(f"[bold yellow][Предупреждение][/]Не удалось найти старый файл [#808080]{application}[/]")
                elif error.errno == 5:  # Нет доступа
                    self.console.print(f"[bold yellow][Предупреждение][/]Нет доступа к старому файлу [#808080]{application}[/], чтобы удалить файл")
                else:
                    self.handle_error(f"Не удалось удалить старый файл {application}", error)
            except PermissionError:
                self.console.print(f"[bold yellow][Предупреждение][/]Нет доступа к старому файлу [#808080]{application}[/], чтобы удалить файл")
            try:
                move(current_executable_path, target_executable_path)
                self.console.print(f"[blue][Инфо][/]Текущий файл переименован в {application}")
            except OSError as error:
                if error.winerror == 32: # Файл занят другим процессом
                    self.console.print(f"[bold yellow][Предупреждение][/]Не удалось переименовать текущий файл {application}, так как занят другим процессом")
                else:
                    self.handle_error(f"Не удалось переименовать текущий файл на {application}", error)
            except PermissionError:
                self.console.print(f"[bold yellow][Предупреждение][/]Нет доступа к новому файлу [#808080]{application}[/], чтобы переименовать файл")
        self.client_socket.sendall("Do not need".encode(self.format))
        self.console.print("[blue][Инфо][/]У вас установлена последняя версия")
        return

    def replace_executable(self, save_path: str, current_executable_path: str) -> None:
        """Заменяет текущий исполняемый файл на скачанный"""
        try:
            move(save_path, current_executable_path)
            self.console.print(f"[#008000][Готово][/]Обновление загружено и сохранено по пути: [#808080]{save_path}[/]")
        except OSError as error:
            if error.winerror == 32:
                self.console.print(f"[bold yellow][Предупреждение][/]Не удалось переместить или переименовать файл [#808080]{save_path}[/], так как занят другим процессом")
            else:
                self.console.print(f"[bold yellow][Предупреждение][/] Не удалось переместить или переименовать файл: {error}")

    def launch_new_app(self, save_path: str) -> None:
        """Запускает скачанный исполняемый файл"""
        self.console.print(f"[blue][Инфо][/]Запуск нового приложения...")
        sleep(2)
        if path.exists(save_path):
            try:
                Popen([save_path])
                exit()
            except Exception as error:
                self.handle_error("Не удалось запустить новое приложение", error)
                return
        else:
            self.console.print(f"[bold red][Ошибка][/]Файл не найден: {save_path}")
            return

    def open_url(self) -> None:
        """Открывает ссылку на проект в браузере"""
        try:
            web_open("https://github.com/dilleron3425/SLCW/releases")
        except Exception as error:
            self.handle_error("При открывание ссылки на проект в браузере", error)

    def download_update(self, save_path, latest_version) -> None:
        """Загружает новое обновление"""
        self.console.print("[blue][Инфо][/]Загрузка обновления...")
        self.open_url()
        try:
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = self.client_socket.recv(self.header)
                    if bytes_read == b"END_OF_FILE":
                        self.console.print("[#008000][Готово][/]Загрузка завершена")
                        break
                    if not bytes_read:
                        self.console.print("[bold red][Ошибка][/]Соединение закрыто сервером")
                        break
                    f.write(bytes_read)
                if bytes_read == "Файл не найден":
                    self.console.print(f"\n[#8000FF][Сервер][/]Сервер не может отправить вам файл, пожалуйста, сообщите администратору")
                    self.current_version = latest_version
                    return
            self.client_socket.sendall("Download complete".encode(self.format))
            server_confirmation = self.client_socket.recv(self.header).decode(self.format)
            if server_confirmation != "Transfer complete":
                self.console.print(f"[bold red][Ошибка][/]Сервер не подтвердил скачивание")
        except Exception as error:
            self.handle_error("Не удалось сохранить обновление", error)
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

    def start_heartbeat_thread(self) -> None:
        """Запускает поток для отправки heartbeat"""
        if self.heartbeat_thread is None or not self.heartbeat_thread.is_alive():
            self.heartbeat_thread_stop.clear()
            self.heartbeat_thread = Thread(target=self.heartbeat)
            self.heartbeat_thread.start()

    def stop_heartbeat_thread(self) -> None:
        """Останавливает поток heartbeat"""
        if self.heartbeat_thread is not None:
            self.heartbeat_thread_stop.set()
            self.heartbeat_thread.join()
            self.heartbeat_thread = None

    def handle_connection_error(self, time_to_connect: int, error: OSError) -> None:
        """Обрабатывает ошибку соединения"""
        if error.errno == 111 or 10061: # Не удалось установить соединение
            self.console.print(f"[bold red][Ошибка][/]Не удалось подключиться к серверу в течение {time_to_connect} секунд, возможно, сервер не работает")
        else:
            self.console.print(f"[blue][Инфо][/]Не удалось подключиться к серверу в течение {time_to_connect} секунд")
            self.console.print(f"[bold red][Ошибка][/]Ошибка подключения: {error}")
        self.client_status = 500
        self.commands()

    def heartbeat(self) -> None:
        """Отправляет heartbeat на сервер"""
        max_attempts = 3
        while not self.heartbeat_thread_stop.is_set():
            if self.client_socket is not None and self.client_status == 200:
                attempts = 0
                while attempts < max_attempts:
                    try:
                        sleep(1)
                        self.client_socket.sendall("heartbeat".encode(self.format))
                        response = self.client_socket.recv(self.header).decode(self.format)
                        if response == "ack":
                            attempts = 0
                            break
                        response = response.replace("ack", "").strip()
                        if response == "":
                            attempts += 1
                        else:
                            self.console.print(f"\n[#8000FF][Сервер][/]{response}", end="")
                    except UnicodeDecodeError:
                        self.console.print("\n[bold red]Ошибка[/]Не правильный формат ответ от сервера. Повторная попытка...")
                        attempts += 1
                    except socket.error as error:
                        if error.errno == 10038:
                            self.console.print(f"\n[bold red][Ошибка][/]Потеря соединение с сервером ошибка 10038 \nНажмите Enter, чтобы перезапустить")
                        else:
                            self.console.print(f"\n[bold red][Ошибка][/]Потеря соединение с сервером: {error}\nНажмите Enter, чтобы перезапустить")
                        self.client_status = 500
                        break
                if attempts == max_attempts:
                    self.console.print("\n[bold red][Ошибка][/]Соединение потеряно после нескольких попыток\nНажмите Enter, чтобы перезапустить")
                    self.client_status = 500
                    if self.client_socket:
                        self.client_socket.close()
                        self.client_socket = None
                    return
            else:
                sleep(1)

    def commands(self) -> None:
        """Обрабатывает команды и отправляет их на сервер"""
        while self.running:
            while self.client_status == 500:
                command = self.console.input("[blue][Инфо][/]Попробовать снова? [Д/Н]: ").lower()
                if command in ["д", "да", "y", "yes"]:
                    print("Переподключение...")
                    self.connect()
                elif command in ["н", "нет", "n", "no", "exit", "quit", "выйти"]:
                    self.hide_app()
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
                    self.console.print(f"    | exit / quit           | Выйти из SLCW                            |")
                    self.console.print(f"    | start (имя сервера)   | Запустить игровой сервер                 |")
                    self.console.print(f"    | stop (имя сервера)    | Остановить игровой сервер                |")
                    self.console.print(f"    | status (имя сервера)  | Узнать статус игрового сервера           |")
                    self.console.print(f"    | restart (имя сервера) | Перезапустить игровой сервер             |")
                    self.console.print(f'    --------------------------------------------------------------------')
                elif command in ["exit", "quit"]:
                    self.running = False
                    if self.client_socket:
                        try:
                            self.client_socket.sendall("exit".encode(self.format))
                        except socket.error as error:
                            self.console.print(f"[bold red][Ошибка][/]Ошибка при отправке команды exit: {error}")
                        finally:
                            self.client_socket.close()
                            self.client_socket = None
                    exit()
                elif command in ["clear", "cls"]:
                    self.console.print(self.print_sys_logo())
                else:
                    self.client_socket.sendall(command.encode(self.format))
                    self.console.print("[#008000][Готово][/]Команда отправлена")

    def start_tray_thread(self) -> None:
        """Запускает поток для работы с трей"""
        if self.tray_thread is None or not self.tray_thread.is_alive():
            self.tray_thread = Thread(target=self.start_tray)
            self.tray_thread.start()

    def stop_tray_thread(self) -> None:
        """Останавливает поток heartbeat"""
        if self.tray_thread is not None:
            self.tray_thread_stop.set()
            self.tray_thread.join()
            self.tray_thread = None

    def start_tray(self) -> None:
        """Запускает трей"""
        try:
            self.icon = Image.open(self.icon_path)
            self.icon = Icon("SLCW", icon=self.icon, title="SLCW", menu=Menu(MenuItem("Открыть SLCW", self.show_app)))
            self.icon.run()
        except OSError as error:
            if error.errno == 2: # Нету файл или папки
                while self.client_status != 200:
                    sleep(1)
                self.console.print(f"\n[bold yellow][Предупреждение][/]Не найден файл SLCW.ico Скачивается...")
                current_executable_dir = path.dirname(path.abspath(executable))
                current_executable_path = path.join(current_executable_dir, 'SLCW.exe')
                self.download_icon_tray()
                self.launch_new_app(current_executable_path)
            elif isinstance(error, IOError):
                if self.client_socket:
                    self.client_socket.sendall("Не открывается файл SLCW.ico".encode(self.format))
                else:
                    pass
            else:
                self.handle_error("Не удалось создать иконку для трей", error)

    def download_icon_tray(self) -> None:
        """Загружает иконку для трей"""
        self.stop_heartbeat_thread()
        try:
            self.client_socket.sendall("Download icon tray".encode(self.format))
            response = self.client_socket.recv(self.header).decode(self.format)
            if response == "OK":
                save_icon_path = path.join(path.expanduser("~"), "SLCW")
                save_path = path.join(save_icon_path, "SLCW.ico")
                try:
                    makedirs(save_icon_path, exist_ok=True)
                except Exception as error:
                    self.handle_error(f"Не удалось создать директорию для иконки по пути {save_path}", error)
                if save_path:
                    try:
                        with open(save_path, 'wb') as f:
                            while True:
                                bytes_read = self.client_socket.recv(self.header)
                                if bytes_read == b"END_OF_FILE":
                                    self.console.print("[#008000][Готово][/]Загрузка завершена")
                                    break
                                if not bytes_read:
                                    self.console.print("[bold red][Ошибка][/]Соединение закрыто сервером")
                                    return
                                f.write(bytes_read)
                            if bytes_read == "Файл не найден":
                                self.console.print(f"\n[bold red][Ошибка][/]Сервер не может отправить вам файл, пожалуйста, сообщите администратору")
                                return
                        f.close()
                        self.client_socket.sendall("Download icon complete".encode(self.format))
                        server_confirmation = self.client_socket.recv(self.header).decode(self.format)
                        if server_confirmation != "Transfer complete":
                            self.console.print(f"[bold yellow][Предупреждение][/]Сервер не подтвердил скачивание")
                    except Exception as error:
                        self.handle_error(f"Не удалось сохранить иконку по пути {save_path}", error)
                    if self.client_socket:
                        self.client_socket.close()
                        self.client_socket = None
                else:
                    self.console.print(f"[bold red][Ошибка][/]Не удалось сохранить иконку приложения по пути {save_path}")
                    return
            else:
                self.console.print(f"[bold red][Ошибка][/]Сервер не подтвердил скачивание иконки трей")
        except Exception as error:
            self.handle_error("Не удалось скачать иконку для трей", error)
            return

    def handle_processes(self) -> None:
        """Обрабатывает процессы и закрывает дубликаты"""
        current_process_name = path.basename(argv[0])
        current_pid = getpid()
        same_processes = []
        process_names_to_check = [current_process_name, "SLCW.exe"]
        for proc in process_iter(['name', 'pid', "create_time"]):
            try:
                if proc.info['name'] in process_names_to_check and proc.info['pid'] != current_pid:
                    elapsed_time = time() - proc.info['create_time']
                    if elapsed_time > 3:
                        same_processes.append(proc)
            except (NoSuchProcess, AccessDenied):
                continue
        if same_processes:
            self.console.print(f"[blue][Инфо][/]Программа уже запущена, закрываю дубликаты...")
            for proc in same_processes:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                    self.console.print(f"[#008000][Готово][/] Процесс с PID {proc.pid} завершен.")
                except (NoSuchProcess, AccessDenied):
                    self.console.print(f"[bold red][Ошибка][/] Не удалось завершить процесс с PID {proc.pid}.")
                except TimeoutExpired:
                    self.console.print(f"[bold red][Ошибка][/] Процесс с PID {proc.pid} не завершился вовремя.")

    def run(self) -> None:
        self.handle_processes()
        signal(SIGINT, self.signal_handler)
        self.start_tray_thread()
        try:
            while self.running:
                if self.client_socket is None and self.client_status is None:
                    print("Подключение...")
                    self.connect()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                if self.client_socket:
                    self.client_socket.close()
                self.stop_tray_thread()
            except AttributeError:
                pass
            except Exception as error:
                self.handle_error("Ошибка при закрытии сокета", error)
            exit()

if __name__ == "__main__":
    windows = WindowsClient(server=IP, port=PORT)
    windows.run()
