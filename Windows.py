import socket

from psutil import process_iter, NoSuchProcess, AccessDenied, TimeoutExpired
from os import path, system, remove, makedirs, getpid
from webbrowser import open as web_open
from sys import executable, exit, argv
from time import time, sleep, strftime
from threading import Thread, Event
from rich.console import Console
from datetime import datetime
from subprocess import Popen
from shutil import move

class WindowsClient():
    def __init__(self, server: str, port: int) -> None:
        self.console = Console()
        self.server = server
        self.port = port
        self.header = 4096
        self.format = "utf-8"
        self.current_version = "1.3.2"
        self.client_socket = None
        self.client_status = None
        self.heartbeat_thread = None
        self.heartbeat_thread_stop = Event()
        self.send_log_file_thread = None
        self.send_log_file_thread_stop = Event()
        self.running = True
        self.time_to_connect = 10
        self.icon_path = path.join(path.expanduser("~"), "SLCW", "SLCW.ico")

    def print_sys_logo(self) -> str:
        """Выводит логотип программы в консоль"""
        self.log_message("[Info] Вывод логотипа")
        system("cls")
        return self.console.print(f"""[#a0a0a0]
 ____    _       ____ __        __
/ ___|  | |     / ___ \\ \\      / /
\\___ \\  | |    | |     \\ \\ /\\ / / 
 ___) | | |___ | |___   \\ V  V / V{self.current_version} 
|____/  |_____| \\____|   \\_/\\_/  By:Diller™
                    [/]""")

    def handle_message(self, message: str, message_type: str, error: Exception = None) -> None:
        """Обработка сообщений и вывод их в консоль"""
        message_color = {
            "server": "\n[#8000FF][Сервер][/]",
            "done": "[#008000][Готово][/]",
            "info": "[blue][Инфо][/]",
            "warn": "[bold yellow][Предупреждение][/]",
            "error": "\n[bold red][Ошибка][/]"
        }.get(message_type, "[white]")
        if message_type == "error":
            error_message = f": {error}" if error else ""
            self.console.print(f"{message_color}{message}{error_message}")
            self.log_message(f"[{message_type}] {message}{error_message}")
        elif message_type == "print":
            self.console.print(f"{message}")
            self.log_message(f"[Info] {message}")
        else:
            self.console.print(f"{message_color}{message}")
            self.log_message(f"[{message_type.capitalize()}] {message}")

    def get_current_time(self) -> str:
        """Возвращает текущее время и дату"""
        return f"[{datetime.now().date()} {strftime('%X')}] "

    def handle_print(self, message: str) -> None:
        """Обработчик вывода сообщений"""
        self.handle_message(message, "print")

    def handle_server(self, message: str) -> None:
        """Обработчик сообщений от сервера"""
        self.handle_message(message, "server")

    def handle_done(self, message: str) -> None:
        """Обработка завершений и вывод сообщение в консоль"""
        self.handle_message(message, "done")

    def handle_info(self, message: str) -> None:
        """Обработка информации и вывод сообщение в консоль"""
        self.handle_message(message, "info")

    def handle_warn(self, message: str) -> None:
        """Обработка предупреждений и вывод сообщение в консоль"""
        self.handle_message(message, "warn")

    def handle_error(self, message: str, error: Exception = None) -> None:
        """Обработка ошибок и вывод сообщение в консоль"""
        self.handle_message(message, "error", error)

    def connect(self)  -> None:
        """Подключает клиента к серверу"""
        start_time = time()
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.client_socket:
                    self.client_socket.connect((self.server, self.port))
                    self.client_socket.sendall("SLCW_CLIENT".encode(self.format))
                    self.print_sys_logo()
                    self.available_update()
                    self.client_status = 200
                    self.start_send_log_file_thread()
                    self.commands()
                    break
            except OSError as error:
                if time() - start_time > self.time_to_connect:
                    if error.errno == 111 or 10061: # Не удалось установить соединение
                        self.handle_error(f"Не удалось подключиться к серверу в течение {self.time_to_connect} секунд, возможно, сервер не работает")
                    else:
                        self.handle_info(f"Не удалось подключиться к серверу в течение {self.time_to_connect} секунд")
                        self.handle_error("Ошибка подключения", error)
                    self.client_status = 500
                    self.close_client_socket()
                    self.commands()
                    return

    def handle_connection_error(self, time_to_connect: int, error: OSError) -> None:
        """Обрабатывает ошибку соединения"""
        if error.errno == 111 or 10061: # Не удалось установить соединение
            self.handle_error(f"Не удалось подключиться к серверу в течение {time_to_connect} секунд, возможно, сервер не работает")
        else:
            self.handle_info(f"Не удалось подключиться к серверу в течение {time_to_connect} секунд")
            self.handle_error("Ошибка подключения", error)
        self.client_status = 500
        self.commands()

    def available_update(self) -> None:
        """Проверяет доступность обновления"""
        command = self.client_socket.recv(self.header).decode(self.format)
        current_executable_path = path.abspath(executable)
        if not command.startswith("New version:"):
            self.log_message("[Warn] Не пришло 'New version:' от сервера")
            return
        try:
            parts = command.split(";")
            latest_version = parts[0].split(": ")[1]
            new_version_size = float(parts[1].split(": ")[1])
            self.log_message(f"[Info] Получены данные об обновлении: версия {latest_version}, размер {new_version_size:.2f} MB")
        except (IndexError, ValueError) as error:
            self.handle_error("Не удаётся получить информацию о новой версии", error)
            return
        if latest_version == self.current_version:
            self.handle_latest_version(current_executable_path)
            return
        self.handle_info(f"Доступно обновление: [white]{self.current_version}[/] -> [white]{latest_version}[/]")
        try:
            current_version_size = int(path.getsize("SLCW.exe")) / (1024 * 1024)
            diff_version = new_version_size - current_version_size
            self.handle_info(f"Размер версий: [white]{current_version_size:.2f}[/] МБ -> [white]{new_version_size:.2f}[/] МБ | Разница: [white]{diff_version:.2f}[/] МБ")
            self.client_socket.sendall("Ready for update".encode(self.format))
            save_path = path.join(path.abspath(path.dirname(executable)), f"NEW_SLCW.exe")
            if save_path:
                self.download_update(save_path, latest_version)
                self.replace_executable(save_path, current_executable_path)
                self.launch_new_app(save_path)
            else:
                self.handle_error(f"Не удалось сохранить файл обновления по пути: {save_path}")
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
                self.handle_info(f"Старый файл {target_executable_path} удалён")
            except OSError as error:
                if error.winerror == 2: # Нету файл или папки
                    self.handle_warn(f"Не удалось найти старый файл [#808080]{target_executable_path}[/]")
                elif error.winerror == 5:  # Нет доступа
                    self.handle_warn(f"Нет доступа к старому файлу [#808080]{target_executable_path}[/], чтобы удалить файл")
                else:
                    self.handle_error(f"Не удалось удалить старый файл {target_executable_path}", error)
            except PermissionError:
                self.handle_warn(f"Нет доступа к старому файлу [#808080]{target_executable_path}[/], чтобы удалить файл")
            try:
                move(current_executable_path, target_executable_path)
                self.handle_info(f"Текущий файл переименован в {application}")
            except OSError as error:
                if error.winerror == 32: # Файл занят другим процессом
                    self.handle_warn(f"Не удалось переименовать текущий файл {current_executable_path}, так как занят другим процессом")
                elif error.winerror == 2: # Нету файл или папки
                    self.handle_warn(f"Не удалось найти текущий файл {current_executable_path}, чтобы переименовать файл")
                else:
                    self.handle_error(f"Не удалось переименовать текущий файл {current_executable_path} на {application}", error)
            except PermissionError:
                self.handle_warn(f"Нет доступа к новому файлу [#808080]{current_executable_path}[/], чтобы переименовать файл")
        self.client_socket.sendall("Do not need".encode(self.format))
        self.handle_info("У вас установлена последняя версия")
        return

    def replace_executable(self, save_path: str, current_executable_path: str) -> None:
        """Заменяет текущий исполняемый файл на скачанный"""
        try:
            move(save_path, current_executable_path)
            self.handle_done(f"Обновление загружено и сохранено по пути: [#808080]{save_path}[/]")
        except OSError as error:
            if error.winerror == 32:
                self.handle_warn(f"Не удалось переместить или переименовать файл [#808080]{save_path}[/], так как занят другим процессом")
            else:
                self.handle_warn(f"Не удалось переместить или переименовать файл: {error}")

    def launch_new_app(self, save_path: str) -> None:
        """Запускает скачанный исполняемый файл"""
        self.handle_info("Запуск нового приложения...")
        sleep(2)
        if path.exists(save_path):
            try:
                Popen([save_path])
                exit()
            except Exception as error:
                self.handle_error("Не удалось запустить новое приложение", error)
                return
        else:
            self.handle_error(f"Файл не найден: {save_path}")
            return

    def open_url(self) -> None:
        """Открывает ссылку на проект в браузере"""
        try:
            web_open("https://github.com/dilleron3425/SLCW/releases")
            self.log_message("[Info] Открыта ссылка на проект в браузере")
        except Exception as error:
            self.handle_error("При открывание ссылки на проект в браузере", error)

    def checker_dirs(self, attr_path: str = None):
        """Проверяет, существуют ли директории"""
        paths_to_check = []
        home_directory = path.expanduser("~")
        try:
            if attr_path is not None:
                paths_to_check.append(path.join(home_directory, attr_path))
            paths_to_check.append(path.join(home_directory, "SLCW"))
            paths_to_check.append(path.join(home_directory, "SLCW", "logs"))
            for path_to_check in paths_to_check:
                if not path.exists(path_to_check):
                    try:
                        makedirs(path_to_check, exist_ok=True)
                    except OSError as error:
                        self.log_message(f"Не удалось создать директорию: {path_to_check}")
        except OSError as error:
            self.log_message(f"Не удалось проверить директорию или файл: {error}")

    def get_log_file_path(self) -> str:
        """Возвращает путь к лог файлу"""
        current_date = datetime.now().strftime("%d-%m-%y")
        self.checker_dirs()
        return path.join(path.expanduser("~"), "SLCW\logs", f"log-file-{current_date}.txt")

    def log_message(self, message: str) -> None:
        """Записывает сообщение в лог"""
        log_file_path = self.get_log_file_path()
        with open(log_file_path, "a", encoding=self.format) as log_file:
            log_file.write(self.get_current_time() + message + "\n")
            log_file.close()

    def start_send_log_file_thread(self) -> None:
        """Запускает поток для отправки лог файла"""
        if self.send_log_file_thread is None or not self.send_log_file_thread.is_alive():
            self.log_message("[Info] Запуск отправки лог файла в потоке")
            self.send_log_file_thread_stop.clear()
            self.send_log_file_thread = Thread(target=self.send_log_file)
            self.send_log_file_thread.start()

    def stop_send_log_thread(self) -> None:
        """Останавливает поток отправки лог файла"""
        if self.send_log_file_thread is not None:
            self.log_message("[Info] Остановка отправки лог файла потока")
            self.send_log_file_thread_stop.set()
            self.send_log_file_thread.join()
            self.send_log_file_thread = None

    def send_log_file(self) -> None:
        """Отправляет лог файл на сервер"""
        while self.client_socket is None:
            sleep(1)
            break
        self.client_socket.sendall("LOG_FILE".encode(self.format))
        log_file_path = self.get_log_file_path()
        sleep(1)
        try:
            with open(log_file_path, "rb") as log_file:
                while (bytes_read := log_file.read(self.header)):
                    self.client_socket.sendall(bytes_read)
                sleep(1)
                self.client_socket.sendall(b"END_OF_FILE")
                server_confirmation = self.client_socket.recv(self.header).decode(self.format)
                if server_confirmation == "Download complete":
                    self.client_socket.sendall("Transfer complete".encode(self.format))
        except Exception as error:
            if error == FileNotFoundError:
                self.log_message("Файл логов не найден")
                self.client_socket.sendall("Файл логов не найден".encode(self.format))
            else:
                self.log_message(f"[Error] Ошибка при отправке лог файла: {str(error)}")
        finally:
            self.start_heartbeat_thread()

    def download_update(self, save_path, latest_version) -> None:
        """Загружает новое обновление"""
        self.handle_info("Загрузка обновления...")
        self.open_url()
        try:
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = self.client_socket.recv(self.header)
                    if bytes_read == b"END_OF_FILE":
                        self.handle_done("Загрузка обновление завершена")
                        break
                    if not bytes_read:
                        self.handle_error("Соединение закрыто сервером")
                        break
                    f.write(bytes_read)
                if bytes_read == "Файл не найден":
                    self.handle_server("Сервер не может отправить вам файл, пожалуйста, сообщите администратору")
                    self.current_version = latest_version
                    return
            self.client_socket.sendall("Download complete".encode(self.format))
            server_confirmation = self.client_socket.recv(self.header).decode(self.format)
            if server_confirmation != "Transfer complete":
                self.handle_warn("Сервер не подтвердил скачивание")
        except Exception as error:
            self.handle_error("Не удалось сохранить обновление", error)
        finally:
            self.close_client_socket()

    def start_heartbeat_thread(self) -> None:
        """Запускает поток для отправки heartbeat"""
        if self.heartbeat_thread is None or not self.heartbeat_thread.is_alive():
            self.log_message("[Info] Запуск heartbeat потока")
            self.heartbeat_thread_stop.clear()
            self.heartbeat_thread = Thread(target=self.heartbeat)
            self.heartbeat_thread.start()

    def stop_heartbeat_thread(self) -> None:
        """Останавливает поток heartbeat"""
        if self.heartbeat_thread is not None:
            self.log_message("[Info] Остановка heartbeat потока")
            self.heartbeat_thread_stop.set()
            self.heartbeat_thread.join()
            self.heartbeat_thread = None

    def heartbeat(self) -> None:
        """Отправляет heartbeat на сервер"""
        max_attempts = 3
        while not self.heartbeat_thread_stop.is_set():
            if self.client_socket is not None and self.client_status == 200:
                attempts = 0
                while attempts < max_attempts:
                    try:
                        sleep(1)
                        if self.client_socket is None:
                            return
                        self.client_socket.sendall("heartbeat".encode(self.format))
                        response = self.client_socket.recv(self.header).decode(self.format)
                        if response == "ack":
                            attempts = 0
                            break
                        response = response.replace("ack", "").strip()
                        if response == "":
                            attempts += 1
                        else:
                            self.handle_server(response)
                    except UnicodeDecodeError:
                        self.handle_error("Не правильный формат ответ от сервера. Повторная попытка...")
                        attempts += 1
                    except socket.error as error:
                        if error.errno == 10038:
                            self.handle_error("Потеря соединение с сервером ошибка 10038\nНажмите Enter, чтобы перезапустить")
                        elif error.errno == 10053:
                            self.handle_error("Программа SLCW разорвало соединение с сервером\nНажмите Enter, чтобы перезапустить")
                        elif error.errno == 10054:
                            self.handle_error("Сервер SLCW разорвал соединение\nНажмите Enter, чтобы перезапустить")
                        elif error.errno == 10060: # Превышено время ожидания подключения
                            pass
                        else:
                            self.handle_error(f"Потеря соединение с сервером: {error}\nНажмите Enter, чтобы перезапустить")
                        self.client_status = 500
                        break
                if attempts == max_attempts:
                    self.handle_error("Соединение потеряно после нескольких попыток\nНажмите Enter, чтобы перезапустить")
                    self.client_status = 500
                    self.close_client_socket()
                    return
            else:
                sleep(1)

    def commands(self) -> None:
        """Обрабатывает команды и отправляет их на сервер"""
        while self.running:
            while self.client_status == 500:
                command = self.console.input("[blue][Инфо][/]Попробовать снова? [Д/Н]: ").lower()
                if command in ["д", "да", "y", "yes"]:
                    self.handle_print("Переподключение...")
                    self.connect()
                elif command in ["н", "нет", "n", "no", "exit", "quit", "выйти"]:
                    self.close_client_socket()
                    exit()
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
                    self.console.print(f"    --------------------------------------------------------------------\n")
                elif command in ["exit", "quit"]:
                    self.running = False
                    if self.client_socket:
                        try:
                            self.client_socket.sendall("exit".encode(self.format))
                        except socket.error as error:
                            self.handle_error(f"При отправке команды exit", error)
                        finally:
                            self.close_client_socket()
                    exit()
                elif command in ["clear", "cls"]:
                    self.print_sys_logo()
                else:
                    self.client_socket.sendall(command.encode(self.format))
                    self.handle_done(f"Команда ({command}) отправлена")

    def get_processes(self) -> None:
        """Получает системные процессы"""
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
            self.handle_info("Программа уже запущена, закрываю дубликаты...")
            for proc in same_processes:
                self.terminate_process(proc)

    def terminate_process(self, proc):
        try:
            proc.terminate()
            proc.wait(timeout=3)
            self.handle_done(f"Процесс с PID {proc.pid} завершен")
        except (NoSuchProcess, AccessDenied, TimeoutExpired) as error:
            error_msg = f"Не удалось завершить процесс с PID {proc.pid}"
            if isinstance(error, TimeoutExpired):
                error_msg = f"Процесс с PID {proc.pid} не завершился вовремя"
            self.handle_error(error_msg, error)

    def close_client_socket(self):
        if self.client_socket:
            try:
                self.client_socket.close()
            except AttributeError:
                pass
            except Exception as error:
                self.handle_error("Ошибка при закрытии сокета", error)
            self.client_socket = None
            self.log_message("[Info] Сокет закрыт")

    def run(self) -> None:
        self.get_processes()
        try:
            while self.running:
                if self.client_socket is None and self.client_status is None:
                    self.handle_print("Подключение...")
                    self.connect()
        except KeyboardInterrupt:
            self.close_client_socket()
            exit()
        finally:
            self.close_client_socket()
            exit()

if __name__ == "__main__":
    windows = WindowsClient(server=IP, port=PORT)
    windows.run()