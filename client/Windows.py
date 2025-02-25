import socket

from psutil import process_iter, NoSuchProcess, AccessDenied, TimeoutExpired
from os import path, system, remove, makedirs, getpid
from threading import Thread, Event, current_thread
from webbrowser import open as web_open
from sys import executable, exit, argv
from time import time, sleep, strftime
from rich.console import Console
from datetime import datetime
from shutil import move, copy
from subprocess import Popen
from json import load, dump

class WindowsClient():
    def __init__(self) -> None:
        """Инициализации класса WindowsClient"""
        self.config = self.config_handler()
        self.server = self.config["server_ip"]
        self.port = self.config["server_port"]
        self.header = self.config["header"]
        self.format = self.config["format"]
        self.current_version = self.config["version"]
        self.created_by = self.config["created_by"]
        self.github = self.config["urls"]["github"]
        self.github_releases = self.config["urls"]["github_releases"]
        self.console = Console()
        self.client_socket = None
        self.client_status = None
        self.heartbeat_thread = None
        self.heartbeat_thread_stop = Event()
        self.send_log_file_thread = None
        self.send_log_file_thread_stop = Event()
        self.running = True
        self.time_to_connect = 10
        self._cache_get_log_file_path = None

    def config_handler(self, update: bool = False) -> dict:
        config_path = path.join(path.expanduser("~"), "SLCW", "config.json")
        config = {
                "version": "1.4.0",
                "created_by": "Diller™",
                "server_ip": "connecting ip(str) server",
                "server_port": "listening port(int) server",
                "header": 4096,
                "format": "utf-8",
                "paths":{
                    "log_dir": "logs",
                    "icon_file": "SLCW.ico"
                },
                "urls": {
                    "github": "https://github.com/dilleron3425",
                    "github_releases": "https://github.com/dilleron3425/SLCW/releases"
                }
            }
        def write_config():
            try:
                remove(config_path)
            except FileNotFoundError:
                pass
            except Exception as error:
                print(f"Ошибка при удалении файла конфигурации: {error}")
            try:
                with open(config_path, 'w', encoding="utf-8") as file:
                    dump(config, file, indent=4)
                    return
            except Exception as error:
                print(f"Ошибка при записи файла конфигурации {config_path}: {error}")
        if update:
            try:
                write_config()
                self.log_message("Конфигурация config.json обновлена")
            except FileNotFoundError:
                write_config()
                self.log_message(f"Создали новый config.json, так как не был найден")
            except PermissionError:
                self.handle_error(f"Доступ к файлу {config_path} запрещён, пожалуйста, запустите программу от имени администратора")
            except Exception as error:
                self.handle_error(f"Ошибка при загрузке конфигурационного файла config.json", error)
        try:
            with open(config_path, 'r', encoding="utf-8") as file:
                config = load(file)
        except FileNotFoundError:
            try:
                write_config()
            except PermissionError:
                print("Отказано в доступе при запуске программы. Пожалуйста, запустите программу от имени администратора")
            except Exception as error:
                print(f"Произошла ошибка при создании конфигурационного файла config.json: {error}")
        except Exception as error:
            print(f"Ошибка при загрузке конфигурационного файла config.json: {error}")
        finally:
            return config

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
            self.log_message(f"[{message_type.capitalize()}] {message}{error_message}")
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

    def print_sys_logo(self) -> str:
        """Выводит логотип программы в консоль"""
        self.log_message("[Info] Вывод логотипа")
        system("cls")
        return self.handle_print(f"""[#a0a0a0]
 ____    _       ____ __        __
/ ___|  | |     / ___ \\ \\      / /
\\___ \\  | |    | |     \\ \\ /\\ / / 
 ___) | | |___ | |___   \\ V  V / V{self.current_version} 
|____/  |_____| \\____|   \\_/\\_/  By:{self.created_by}
                    [/]""")

    def connect(self)  -> None:
        """Подключает клиента к серверу"""
        start_time = time()
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.client_socket:
                    self.client_socket.connect((self.server, self.port))
                    self.log_message("[Info] Подключился")
                    self.client_socket.sendall("SLCW_CLIENT".encode(self.format))
                    self.print_sys_logo()
                    self.available_update()
                    self.client_status = 200
                    self.start_func_thread(self.send_log_file_thread, self.send_log_file_thread_stop, self.send_log_file)
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
                    self.commands()
                    return

    def available_update(self) -> None:
        """Проверяет доступность обновления"""
        command = self.client_socket.recv(self.header).decode(self.format)
        current_executable_path = path.abspath(executable)
        if not command.startswith("New version:"):
            self.handle_warn("Не пришли данные об обновлении")
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
            self.client_socket.sendall("Ready for update".encode(self.format))
            save_path = path.join(path.abspath(path.dirname(executable)), f"NEW_SLCW.exe")
            if save_path:
                self.download_handler(save_path, new_version_size, latest_version)
                self.replace_executable(save_path, current_executable_path)
                self.config_handler(update=True)
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
                    self.handle_error(f"Нет доступа к старому файлу [#808080]{target_executable_path}[/], чтобы удалить файл")
                else:
                    self.handle_error(f"Не удалось удалить старый файл {target_executable_path}", error)
            except PermissionError:
                self.handle_warn(f"Нет доступа к старому файлу [#808080]{target_executable_path}[/], чтобы удалить файл")
            try:
                move(current_executable_path, target_executable_path)
                self.handle_info(f"Текущий файл переименован в {application}")
            except OSError as error:
                if error.winerror == 1920: # Нет доступа
                    self.handle_error(f"Нет доступа к файлу {current_executable_path}, чтобы переименовать файл")
                elif error.winerror == 32: # Файл занят другим процессом
                    self.handle_warn(f"Не удалось переименовать текущий файл {current_executable_path}, так как занят другим процессом")
                elif error.winerror == 2: # Нету файл или папки
                    self.handle_error(f"Не удалось найти текущий файл {current_executable_path}, чтобы переименовать файл")
                else:
                    self.handle_error(f"Не удалось переименовать текущий файл {current_executable_path} на {application}", error)
            except PermissionError:
                self.handle_error(f"Нет доступа к новому файлу [#808080]{current_executable_path}[/], чтобы переименовать файл")
            try:
                app_folder = path.join(path.expanduser("~"), "SLCW")
                target_path = path.join(app_folder, "SLCW.exe")
                current_executable_path = path.join(path.abspath(path.dirname(executable)), f"SLCW.exe")
                if not path.exists(target_path):
                    copy(current_executable_path, target_path)
                    self.log_message(f"[Info] Успешно скопирован файл {current_executable_path} в {target_path}")
                else:
                    remove(target_path)
                    copy(current_executable_path, target_path)
                    self.log_message(f"[Info] Успешно заменен файл в {target_path}")
            except OSError as error:
                if error.winerror == 2: # Нету файл или папки
                    self.log_message(f"[Error] Не удалось найти текущий файл {current_executable_path}, чтобы скопировать файл")
                else:
                    self.log_message(f"[Error] Не удалось скопировать текущий файл {current_executable_path} в {target_path} - {str(error)}")
            except PermissionError:
                self.log_message(f"[Error] Нет доступа к файлу {current_executable_path}, чтобы скопировать файл")
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
                remove(path.join(path.expanduser("~"), "SLCW/config.json"))
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
            web_open(self.github_releases)
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
                        self.handle_error(f"Не удалось создать директорию: {path_to_check}", error)
        except OSError as error:
            self.handle_error(f"Не удалось проверить директорию: {path_to_check}", error)

    def get_log_file_path(self) -> str:
        """Возвращает путь к лог файлу"""
        self.checker_dirs()
        if self._cache_get_log_file_path is None:
            current_date = datetime.now().strftime("%d-%m-%y")
            self._cache_get_log_file_path = path.join(path.expanduser("~"), "SLCW\\logs", f"{current_date}.log")
        return self._cache_get_log_file_path

    def log_message(self, message: str) -> None:
        """Записывает сообщение в лог в файл"""
        try:
            log_file_path = self.get_log_file_path()
            with open(log_file_path, "a", encoding=self.format) as log_file:
                log_file.write(self.get_current_time() + message + "\n")
                log_file.close()
        except Exception as error:
            self.handle_error("Не удалось записать сообщение в лог", error)

    def send_log_file(self) -> None:
        """Отправляет лог файл на сервер"""
        while self.client_socket is None:
            sleep(1)
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
                else:
                    self.log_message(f"Сервер не ответил на завершение загрузки лог файла")
        except Exception as error:
            if error == FileNotFoundError:
                self.log_message("Файл логов не найден")
                self.client_socket.sendall("Файл логов не найден".encode(self.format))
            else:
                self.log_message(f"[Error] Ошибка при отправке лог файла: {str(error)}")
        finally:
            self.start_func_thread(self.heartbeat_thread, self.heartbeat_thread_stop, self.heartbeat)

    def download_handler(self, save_path: str, new_version_size: float = None, latest_version: str = None) -> None:
        """Обработчик загрузок"""
        if new_version_size:
            self.open_url()
            current_version_size = int(path.getsize("SLCW.exe")) / (1024 * 1024)
            diff_versions = new_version_size - current_version_size
            self.handle_info(f"Размер версий: [white]{current_version_size:.2f}[/] МБ -> [white]{new_version_size:.2f}[/] МБ | Разница: [white]{diff_versions:.2f}[/] МБ")
        self.handle_info("Загрузка...")
        try:
            with open(save_path, 'wb') as file:
                while True:
                    bytes_read = self.client_socket.recv(self.header)
                    if bytes_read == "File not found":
                        self.handle_server("Сервер не может отправить вам файл, пожалуйста, сообщите администратору")
                        if latest_version:
                            self.current_version = latest_version
                        return
                    if not bytes_read:
                        self.handle_error("Соединение закрыто сервером")
                        break
                    if bytes_read == b"END_OF_FILE":
                        self.handle_done("Загрузка завершена")
                        break
                    file.write(bytes_read)
            self.client_socket.sendall("Download complete".encode(self.format))
            server_confirmation = self.client_socket.recv(self.header).decode(self.format)
            if server_confirmation != "Transfer complete":
                self.handle_warn("Сервер не подтвердил завершение скачивания")
        except Exception as error:
            self.handle_error("Не удалось сохранить файл", error)
        finally:
            if new_version_size:
                self.close_client_socket()

    def start_func_thread(self, func_thread, func_thread_stop, target_func, target_args: tuple = None) -> None:
        """Запускает поток для выполнения функции"""
        try:
            if func_thread is None or not func_thread.is_alive():
                self.log_message(f"[Info] Запуск потока {target_func.__name__}")
                func_thread_stop.clear()
                if not target_args:
                    func_thread = Thread(target=target_func)
                else:
                    func_thread = Thread(target=target_func, args=target_args)
                func_thread.start()
        except Exception as error:
            self.log_message(f"[Error] Ошибка при запуске потока {target_func.__name__} - {error}")

    def stop_func_thread(self, func_thread: Thread, func_thread_stop: bool) -> None:
        """Останавливает поток для выполнения функции"""
        try:
            if func_thread is not None:
                self.log_message(f"[Info] Остановка потока {func_thread.__name__}")
                func_thread_stop.set()
                if func_thread is not current_thread():
                    func_thread.join()
                    func_thread = None
        except Exception as error:
            self.log_message(f"[Error] Ошибка при остановке потока {func_thread.__name__} - {error}")

    def heartbeat(self) -> None:
        """Отправляет heartbeat на сервер"""
        max_attempts = 3
        while not self.heartbeat_thread_stop.is_set():
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
                        break
                    self.handle_server(response)
                except UnicodeDecodeError:
                    self.handle_error("Не правильный формат ответ от сервера. Повторная попытка...")
                    attempts += 1
                    break
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
                return

    def commands(self) -> None:
        """Обрабатывает команды и отправляет их на сервер"""
        while self.running:
            while self.client_status == 500:
                self.stop_func_thread(self.heartbeat_thread, self.heartbeat_thread_stop)
                self.close_client_socket()
                command = self.console.input("[blue][Инфо][/]Попробовать снова? [Д/Н]: ").lower()
                if command in ["д", "да", "y", "yes"]:
                    self.handle_print("Переподключение...")
                    self.connect()
                elif command in ["н", "нет", "n", "no", "exit", "quit"]:
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
                    self.console.print(f'[#a0a0a0]Разработчик[/]: {self.created_by}')
                    self.console.print(f'[#a0a0a0]GitHub[/]: {self.github}\n')
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
                elif command == "info":
                    self.console.print(self.config)
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
            self.log_message("Программа уже запущена, закрываю дубликаты...")
            for proc in same_processes:
                self.terminate_process(proc)

    def terminate_process(self, proc):
        """Закрывает процесс"""
        try:
            proc.terminate()
            proc.wait(timeout=3)
            self.log_message(f"Процесс с PID {str(proc.pid)} завершен")
        except (NoSuchProcess, AccessDenied, TimeoutExpired) as error:
            error_msg = f"Не удалось завершить процесс с PID {proc.pid}"
            if isinstance(error, TimeoutExpired):
                error_msg = f"Процесс с PID {proc.pid} не завершился вовремя"
            self.log_message(str(error_msg), str(error))

    def close_client_socket(self):
        """Закрывает сокет"""
        if self.client_socket:
            try:
                self.client_socket.close()
            except AttributeError:
                pass
            except Exception as error:
                self.handle_error("Ошибка при закрытии сокета", error)
            finally:
                self.client_socket = None
                self.log_message("[Info] Сокет закрыт")

    def run(self) -> None:
        """Запускает клиент"""
        self.log_message(f"[Info] Версия SLCW: {self.current_version}")
        self.log_message(f"[Info] Путь журнала: {self.get_log_file_path()}")
        self.get_processes()
        try:
            while self.running:
                if self.client_socket is None and self.client_status is None:
                    self.handle_print("Подключение...")
                    self.connect()
        except KeyboardInterrupt:
            self.close_client_socket()
            exit()
        except Exception as error:
            self.handle_error("Произошла ошибка", error)
        finally:
            self.close_client_socket()
            exit()

if __name__ == "__main__":
    windows = WindowsClient()
    windows.run()