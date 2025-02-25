import socket

from typing import Dict, Union, Generator, List
from requests.exceptions import HTTPError
from pydactyl import PterodactylClient
from os import path, _exit, makedirs
from rich.console import Console
from time import sleep, strftime
from datetime import datetime
from threading import Thread
from json import load, dumps
from queue import Queue

class Linux():
    def __init__(self) -> None:
        """Инициализация класса Linux"""
        with open("config.json", 'r', encoding="utf-8") as file:
            self.config = load(file)
        self.server = self.config["server_ip"]
        self.port = self.config["server_port"]
        self.header = self.config["header"]
        self.format = self.config["format"]
        self.latest_version = self.config["version"]
        self.update_file_path = self.config["paths"]["update_file"]
        self.app_icon_file_path = self.config["paths"]["app_icon_file"]
        self.info_button_icon_path = self.config["paths"]["info_button_icon"]
        self.blocked_ips_file = self.config["paths"]["blocked_ips_file"]
        self.pterodactyl = PterodactylControl(self.config)
        self.console = Console()
        self.blocked_ips = set()

    def get_current_time(self) -> str:
        """Возвращает текущее время и дату"""
        return f"[#a0a0a0][{datetime.now().date()} {strftime('%X')}][/] "

    def load_blocked_ips(self) -> None:
        """Загружает заблокированные IP из файла"""
        if path.exists(self.blocked_ips_file):
            with open(self.blocked_ips_file, "r") as file:
                for line in file:
                    ip = line.strip()
                    self.blocked_ips.add(ip)

    def save_blocked_ip(self, client_ip) -> None:
        """Сохраняет заблокированный IP в файл"""
        with open(self.blocked_ips_file, "a") as file:
            file.write(f"{client_ip}\n")

    def is_ip_blocked(self, client_ip) -> bool:
        """Проверяет IP на блокировку"""
        return client_ip in self.blocked_ips

    def block_ip(self, client_ip) -> None:
        """Блокирует IP и записывает в файл"""
        self.blocked_ips.add(client_ip)
        self.save_blocked_ip(client_ip)
        self.console.print(f"{self.get_current_time()}[{client_ip}] Был заблокирован")

    def checker_dirs(self, attr_path: str = None) -> None:
        """Проверяет, существуют ли директории"""
        paths_to_check = []
        try:
            if attr_path is not None:
                paths_to_check.append(path.join(attr_path))
            paths_to_check.append(path.join("logs"))
            paths_to_check.append(path.join("updates"))
            for path_to_check in paths_to_check:
                if not path.exists(path_to_check):
                    try:
                        makedirs(path_to_check, exist_ok=True)
                    except OSError as error:
                        self.console.print(f"\n{self.get_current_time()}[bold red][Ошибка][/] Не удалось создать директорию: {path_to_check}")
                    self.console.print(f"{self.get_current_time()}[blue][Инфо][/] Был создан каталог: {path_to_check}")
        except OSError as error:
            self.console.print(f"\n{self.get_current_time()}[bold red][Ошибка][/] Не удалось проверить директорию или файл: {error}")

    def checker_files(self, attr_path: str = None) -> None:
        """Проверяет, существуют ли файлы"""
        files_to_check = []
        try:
            if attr_path is not None:
                files_to_check.append(path.join(attr_path))
            files_to_check.append(self.update_file_path)
            for file_to_check in files_to_check:
                if not path.exists(file_to_check):
                    self.console.print(f"{self.get_current_time()}[bold red][Ошибка][/] Не найден файл: {file_to_check}")
        except OSError as error:
            self.console.print(f"\n{self.get_current_time()}[bold red][Ошибка][/] Не удалось проверить файл: {error}")

    def send_file(self, client_socket, client_ip) -> None:
        """Отправляет файл GUI SLCW.exe клиенту"""
        try:
            with open(self.update_file_path, 'rb') as f:
                while (bytes_read := f.read(self.header)):
                    client_socket.sendall(bytes_read)
            sleep(1)
            client_socket.sendall(b"END_OF_FILE")
            confirmation = client_socket.recv(self.header).decode(self.format)
            if confirmation == "Download complete":
                self.console.print(f"{self.get_current_time()}[{client_ip}] Подтвердил завершение загрузки обновления")
                client_socket.sendall("Transfer complete".encode(self.format))
            else:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Не подтвердил завершение загрузки обновления")
        except OSError as error:
            if error == FileNotFoundError:
                self.console.print(f"{self.get_current_time()}Файл SLCW.exe не найден")
                client_socket.sendall("File not found".encode(self.format))
            elif error.errno == 104:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Отключился при загрузке обновления")
            else:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Ошибка при отправке обновления: {error}")

    def send_app_icon_file(self, client_socket, client_ip) -> None:
        """Отправляет иконку SLCW.ico клиенту"""
        client_socket.sendall("OK".encode(self.format))
        try:
            with open(self.app_icon_file_path, 'rb') as f:
                while (bytes_read := f.read(self.header)):
                    client_socket.sendall(bytes_read)
            sleep(1)
            client_socket.sendall(b"END_OF_FILE")
            confirmation = client_socket.recv(self.header).decode(self.format)
            if confirmation == "Download icon complete":
                self.console.print(f"{self.get_current_time()}[{client_ip}] Подтвердил завершение загрузки иконки")
                client_socket.sendall("Transfer complete".encode(self.format))
            else:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Не подтвердил завершение загрузки иконки")
        except OSError as error:
            if error == FileNotFoundError:
                self.console.print(f"{self.get_current_time()}Файл SLCW.ico не найден")
                client_socket.sendall("File not found".encode(self.format))
            elif error.errno == 104:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Отключился при загрузке обновления")
            else:
                self.console.print(f"{self.get_current_time()}Ошибка при отправке иконки: {error}")

    def send_info_button_icon_file(self, client_socket, client_ip) -> None:
        """Отправляет иконку кнопки информации клиенту"""
        client_socket.sendall("OK".encode(self.format))
        try:
            with open(self.info_button_icon_path, 'rb') as f:
                while (bytes_read := f.read(self.header)):
                    client_socket.sendall(bytes_read)
            sleep(1)
            client_socket.sendall(b"END_OF_FILE")
            confirmation = client_socket.recv(self.header).decode(self.format)
            if confirmation == "Download complete":
                self.console.print(f"{self.get_current_time()}[{client_ip}] Подтвердил завершение загрузки иконки")
                client_socket.sendall("Transfer complete".encode(self.format))
            else:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Не подтвердил завершение загрузки иконки")
        except OSError as error:
            if error == FileNotFoundError:
                self.console.print(f"{self.get_current_time()}Файл иконки кнопки информации не найден")
                client_socket.sendall("File not found".encode(self.format))
            elif error.errno == 104:
                self.console.print(f"{self.get_current_time()}[{client_ip}] Отключился при загрузке обновления")
            else:
                self.console.print(f"{self.get_current_time()}Ошибка при отправке иконки: {error}")

    def get_log_file_path(self, client_ip) -> str:
        """Возвращает путь к лог файлу"""
        current_date = datetime.now().strftime("%d-%m-%y")
        return path.join(f"logs/{current_date}-{client_ip}.log")

    def download_client_log(self, client_socket, client_ip) -> None:
        """Получает лог от клиента"""
        save_path = self.get_log_file_path(client_ip)
        try:
            with open(save_path, 'wb') as log_file:
                while True:
                    bytes_read = client_socket.recv(self.header)
                    if bytes_read == b"END_OF_FILE":
                        self.console.print(f"{self.get_current_time()}[{client_ip}] Загрузка логов завершена")
                        break
                    if not bytes_read:
                        self.console.print(f"{self.get_current_time()}[{client_ip}] Соединение закрыто клиентом")
                        break
                    log_file.write(bytes_read)
                if bytes_read == "Файл логов не найден":
                    self.console.print(f"{self.get_current_time()}[{client_ip}] Клиента не может отправить нам файл")
                    return
            client_socket.sendall("Download complete".encode(self.format))
            client_confirmation = client_socket.recv(self.header).decode(self.format)
            if client_confirmation != "Transfer complete":
                self.console.print(f"{self.get_current_time()}[{client_ip}] Клиент не подтвердил скачивание")
        except Exception as error:
            self.console.print(f"{self.get_current_time()}[{client_ip}] Не удалось сохранить обновление: {error}")

    def handle_client(self, client_socket, client_ip) -> None:
        """Обрабатывает клиента на команды"""
        connected = True
        version_sent = False
        command_queue = Queue()

        def command_worker():
            while True:
                command = command_queue.get()
                if command is None:
                    break
                self.handle_command(client_socket, client_ip, command)
                command_queue.task_done()
        command_thread = Thread(target=command_worker)
        command_thread.start()

        try:
            while connected:
                if not version_sent:
                    file_size = path.getsize(self.update_file_path) / (1024 * 1024)
                    client_socket.sendall(f"New version: {self.latest_version}; File size: {file_size}".encode(self.format))
                    response = client_socket.recv(self.header).decode(self.format)
                    if response == "Ready for update":
                        self.send_file(client_socket, client_ip)
                        version_sent = True
                    elif response == "Do not need":
                        version_sent = True
                    else:
                        self.console.print(f"{self.get_current_time()}[{client_ip}] Неправильный ответ: {response}")
                else:
                    try:
                        response = client_socket.recv(self.header).decode(self.format)
                        if not response:
                            self.console.print(f"{self.get_current_time()}[{client_ip}] Отключился от SLCW")
                            break
                        if response == "heartbeat":
                            client_socket.sendall("ack".encode(self.format))
                        elif response == "ICON_TRAY":
                            self.console.print(f"{self.get_current_time()}[{client_ip}] Отправляем иконку трея")
                            self.send_app_icon_file(client_socket, client_ip)
                        elif response == "INFO_BUTTON":
                            self.console.print(f"{self.get_current_time()}[{client_ip}] Отправляем иконку кнопки информации")
                            self.send_info_button_icon_file(client_socket, client_ip)
                        elif response == "LOG_FILE":
                            self.console.print(f"{self.get_current_time()}[{client_ip}] Скачиваем лог файл")
                            self.download_client_log(client_socket, client_ip)
                        else:
                            command_queue.put(response)
                    except OSError as error:
                        if error.errno in (9, 104):
                            self.console.print(f"{self.get_current_time()}[{error.errno}] [{client_ip}] Возможно, отключился от SLCW")
                            break
                        else:
                            self.console.print(f"{self.get_current_time()}[{error.errno}] [{client_ip}] Ошибка сокета: {error}")
                            break
        except UnicodeDecodeError:
            self.console.print(f"{self.get_current_time()}[{client_ip}] Неправильный формат ответа")
        except FileNotFoundError:
            self.console.print(f"{self.get_current_time()}[{client_ip}] Файл для обновления SLCW не найден")
            client_socket.sendall("File not found".encode(self.format))
        except Exception as error:
            self.console.print(f"{self.get_current_time()}[{client_ip}] Ошибка при обработке сокета: {error}")
        finally:
            command_queue.put(None)
            command_thread.join()
            if client_socket:
                try:
                    client_socket.close()
                except Exception as error:
                    self.console.print(f"{self.get_current_time()}[{client_ip}] Ошибка при закрытии сокета: {error}")

    def handle_command(self, client_socket, client_ip, command) -> None:
        """Обрабатывает команды от клиента"""
        if not command or command == "EXIT":
            return
        elif command == "SERVER_STATUS":
            self.console.print(f"{self.get_current_time()}[{client_ip}] Клиент запросил статус всех серверов")
            server_status = self.pterodactyl.stat_all()
            client_socket.sendall(dumps(server_status).encode(self.format))
            return

        command = command.lower()

        self.console.print(f"{self.get_current_time()}[{client_ip}] {command}")
        parts = command.split()
        if len(parts) < 2:
            client_socket.sendall("Неверный формат команды. Посмотрите список команд введя - help".encode(self.format))
            return
        
        command, server_name = parts[0], parts[1]
        servers_list = self.pterodactyl.get_server_list()
        if not any(server_name == server_name for server in servers_list):
            client_socket.sendall("Неверный сервер или его не существует".encode(self.format))
            return
        
        command_map = {
            "start": self.command_start,
            "restart": self.command_restart,
            "stop": self.command_stop,
            "stat": self.command_stat,
            "status": self.command_stat,
        }

        if command in command_map:
            Thread(target=self.execute_command, args=(command_map[command], client_socket, client_ip, server_name)).start()

    def execute_command(self, command_func, client_socket, client_ip, server_name) -> None:
        """Вызывает функцию опред. команды от клиента"""
        try:
            server_status = command_func(server_name)
            for status in server_status:
                server_name, server_info = next(iter(status.items()))
                message = server_info.get("message")
                port = server_info.get("port")
                core_name = server_info.get("core_name")
                core_version = server_info.get("core_version")
                response_lines = []
                if message is not None:
                    if command_func.__name__ in ["command_start", "command_restart", "command_stop"]:
                        response_lines.append(message)
                    else:
                        response_lines.append(f"        Статус: {message}")
                        response_lines.append(f"        IP: dillertm.ru")
                if port is not None:
                    response_lines.append(f"        Порт: {port}")
                if core_name is not None:
                    response_lines.append(f"        Ядро игры: {core_name}")
                if core_version is not None:
                    response_lines.append(f"        Версия игры: {core_version}")

                response_message = "\n".join(response_lines)
                client_socket.sendall(response_message.encode(self.format))
        except OSError as error:
            if error.errno == 9:
                self.console.print(f"{self.get_current_time()}[{error.errno}] [{client_ip}] Отключился от SLCW")
            else:
                self.console.print(f"{self.get_current_time()}[{error.errno}] [{client_ip}] Ошибка при вызове команды: {error}")

    def command_start(self, server_name) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Возвращает функцию запуск сервера"""
        return self.pterodactyl.server_start(server_name)
    
    def command_restart(self, server_name) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Возвращает функцию перезапуск сервера"""
        return self.pterodactyl.server_restart(server_name)

    def command_stop(self, server_name) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Возвращает функцию остановку сервера"""
        return self.pterodactyl.server_stop(server_name)

    def command_stat(self, server_name: str = None) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Возвращает функцию статус сервера"""
        return self.pterodactyl.server_status(server_name)

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.server, self.port))
            server_socket.listen()
            self.console.print(f"Сервер работает на {self.server}:{self.port}")
            self.checker_dirs()
            self.checker_files()
            self.load_blocked_ips()
            while True:
                try:
                    client_socket, client_addr = server_socket.accept()
                    client_ip = client_addr[0]
                    client_port = client_addr[1]
                    if self.is_ip_blocked(client_ip):
                        self.console.print(f"{self.get_current_time()}[{client_ip}] Подключение отклонено для заблокировано IP")
                        client_socket.close()
                        continue
                    self.console.print(f"{self.get_current_time()}[{client_ip}:{client_port}] Подключился")
                    check_client = client_socket.recv(self.header).decode(self.format)
                    if check_client == "SLCW_CLIENT":
                        self.console.print(f"{self.get_current_time()}[{client_ip}] Прошел проверку")
                        Thread(target=self.handle_client, args=(client_socket, client_ip)).start()
                    else:
                        self.console.print(f"{self.get_current_time()}[{client_ip}:{client_port}] Не прошёл проверку")
                        self.block_ip(client_ip)
                        client_socket.close()
                except KeyboardInterrupt:
                    print("Сервер остановлен")
                    _exit(0)
                except UnicodeDecodeError:
                    self.console.print(f"{self.get_current_time()}[{client_ip}:{client_port}] Не прошли проверку")
                    self.block_ip(client_ip)
                    client_socket.close()
                except OSError as error:
                    if error.errno == 32:
                        self.console.print(f"{self.get_current_time()}[{error.errno}] [{client_ip}] Преждевременное отключение")
                    elif error.errno == 104:
                        self.console.print(f"{self.get_current_time()}[{error.errno}] [{client_ip}] Разрывает соединение до того, как ответит")
                    else:
                        self.console.print(f"{self.get_current_time()}Ошибка при закрытии сервера: {error}")

class PterodactylControl():
    def __init__(self, config) -> None:
        self.config = config
        self.api = PterodactylClient(self.config["urls"]["game_server"], self.config["pterodactyl"]["ptero_api"])
        self.no_server = {"message": f"Ошибка, не удалось найти сервер. Возможно, проблема в конфигурации сервера или у сервера SLCW"}
        self._cached_server_list = None

    def handle_error(self, server_status: dict, server_name: str, server_error: Exception) -> None:
        """Обрабатывает ошибки"""
        error_messages = {
            403: "Ошибка 403, нет доступа к игровому серверу, обратитесь к администратору",
            404: "Ошибка 404, сервер не найден, возможно, проблема в конфигурации сервера",
            409: "Ошибка 409, не удается обработать запрос из-за конфликта в текущем состоянии сервера",
            429: "Ошибка 429, слишком много запросов на сервер за единицу времени",
            500: "Ошибка 500, неисправность конфигурации сервера или запрос был отказан"
        }
        if isinstance(server_error, HTTPError):
            error_code = server_error.response.status_code
            message = error_messages.get(error_code, f"Ошибка {error_code} при извлечении данных из сервера")
        elif isinstance(server_error, KeyError):
            message = "Ошибка, не найдена конфигурация для Pterodactyl на сервере или у сервера SLCW"
        else:
            message = f"Не известная ошибка: {server_error}"
        server_status[server_name] = {"message": message}
    
    def get_server_list(self) -> List[Dict[str, str]]:
        """Возвращает список серверов"""
        if self._cached_server_list is None:
            server_list = self.api.client.servers.list_servers()
            servers = []
            for inner_list in server_list:
                for server in inner_list:
                    server_name = server['attributes']['name']
                    server_uuid = server['attributes']['uuid']
                    servers.append({"name": server_name, "uuid": server_uuid})
            self._cached_server_list = servers
        return self._cached_server_list
    
    def server_status(self, server_name: str) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Возвращает статус сервера"""
        server_status = {}
        try:
            server_list = self.get_server_list()
            for server in server_list:
                server_uuid = next((server['uuid'] for server in server_list if server['name'].lower() == server_name.lower()), None)
            if server_uuid is not None:
                try:
                    server_data = self.api.client.servers.get_server_utilization(server_uuid)
                    parameters = self.api.client.servers.get_server(server_uuid)
                    for variable in parameters['relationships']['variables']['data']:
                        if variable['attributes']['name'] == 'Forge Version':
                            core_name = parameters['relationships']['variables']['data'][3]['attributes']['name']
                            core_version = parameters['relationships']['variables']['data'][3]['attributes']['server_value']
                            break
                        elif variable['attributes']['name'] =='Server Version':
                            core_name = parameters['relationships']['variables']['data'][1]['attributes']['name']
                            core_version = parameters['relationships']['variables']['data'][1]['attributes']['server_value']
                            break
                    else:
                        core_name = None
                        core_version = None
                    port = parameters['relationships']['allocations']['data'][0]['attributes']['port']
                    server_status[server_name] = {
                        "message": 'Запущен' if server_data['current_state'] == 'running' else 'Остановлен',
                        "port": port,
                        "core_name": core_name,
                        "core_version": core_version
                    }
                except Exception as server_error:
                    self.handle_error(server_status, server_name, server_error)
            else:
                server_status[server_name] = self.no_server
        except Exception as server_error:
            self.handle_error(server_status, server_name, server_error)
        yield server_status

    def server_start(self, server_name) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Запускает сервер"""
        server_status_generator = self.server_status(server_name)
        server_status = next(server_status_generator)
        current_state = server_status[server_name]['message']
        if "core_name" in server_status[server_name]:
            core_name = server_status[server_name]['core_name']
        else:
            core_name = None
        if "core_version" in server_status[server_name]:
            core_version = server_status[server_name]['core_version']
        else:
            core_version = None
        if "port" in server_status[server_name]:
            port = server_status[server_name]['port']
        else:
            port = None
        try:
            server_list = self.get_server_list()
            for server in server_list:
                server_uuid = next((server['uuid'] for server in server_list if server['name'].lower() == server_name.lower()), None)
            if server_uuid is not None:
                try:
                    if current_state == 'Запущен':
                        server_status[server_name] = {
                        "message": 'Уже запущен',
                        "port": port,
                        "core_name": core_name,
                        "core_version": core_version
                        }
                    else:
                        self.api.client.servers.send_power_action(server_uuid, 'start')
                        server_status[server_name] = {"message": "Запускается..."}
                        yield server_status
                        while self.api.client.servers.get_server_utilization(server_uuid)['current_state'] != 'running':
                            self.api.client.servers.get_server_utilization(server_uuid)['current_state']
                        server_status[server_name] = {
                        "message": 'Запущен',
                        "port": port,
                        "core_name": core_name,
                        "core_version": core_version
                        }
                except Exception as server_error:
                    self.handle_error(server_status, server_name, server_error)
            else:
                server_status[server_name] = self.no_server
        except Exception as server_error:
            self.handle_error(server_status, server_name, server_error)
        yield server_status

    def server_restart(self, server_name) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        """Перезапускает сервер"""
        server_status_generator = self.server_status(server_name)
        server_status = next(server_status_generator)
        core_name = server_status[server_name]['core_name']
        core_version = server_status[server_name]['core_version']
        port = server_status[server_name]['port']
        try:
            server_list = self.get_server_list()
            for server in server_list:
                server_uuid = next((server['uuid'] for server in server_list if server['name'].lower() == server_name.lower()), None)
            if server_uuid is not None:
                try:
                    if self.api.client.servers.get_server_utilization(server_uuid)['current_state'] == 'starting':
                        server_status[server_name] = {"message": "Уже перезапускается..."}
                    else:
                        self.api.client.servers.send_power_action(server_uuid, 'restart')
                        server_status[server_name] = {"message": "Перезапускается..."}
                        yield server_status
                        while self.api.client.servers.get_server_utilization(server_uuid)['current_state'] != 'running':
                            self.api.client.servers.get_server_utilization(server_uuid)['current_state']
                        server_status[server_name] = {
                        "message": 'Запущен',
                        "port": port,
                        "core_name": core_name,
                        "core_version": core_version
                        }
                except Exception as server_error:
                    self.handle_error(server_status, server_name, server_error)
            else:
                server_status[server_name] = self.no_server
        except Exception as server_error:
            self.handle_error(server_status, server_name, server_error)
        yield server_status

    def server_stop(self, server_name) -> Generator[Dict[str, Dict[str, Union[str, None]]], None, None]:
        """Останавливает сервер"""
        server_status_generator = self.server_status(server_name)
        server_status = next(server_status_generator)
        current_state = server_status[server_name]['message']
        try:
            server_list = self.get_server_list()
            for server in server_list:
                server_uuid = next((server['uuid'] for server in server_list if server['name'].lower() == server_name.lower()), None)
            if server_uuid is not None:
                try:
                    if current_state == 'Остановлен':
                        server_status[server_name] = {"message": "Уже остановлен"}
                    else:
                        self.api.client.servers.send_power_action(server_uuid, 'stop')
                        server_status[server_name] = {"message": "Останавливается..."}
                        yield server_status
                        while self.api.client.servers.get_server_utilization(server_uuid)['current_state'] != 'offline':
                            self.api.client.servers.get_server_utilization(server_uuid)['current_state']
                        server_status[server_name] = {"message": "Остановлен"}
                except Exception as server_error:
                    self.handle_error(server_status, server_name, server_error)
            else:
                server_status[server_name] = self.no_server
        except Exception as server_error:
            self.handle_error(server_status, server_name, server_error)
        yield server_status

    def stat_all(self) -> Dict[str, Dict[str, Union[str, None]]]:
        """Возвращает статистику всех серверов"""
        server_list = self.get_server_list()
        server_statuses = {}
        excluded_servers = self.config["pterodactyl"]["excluded_servers"]
        for server in server_list:
            server_name = server['name']
            server_uuid = server['uuid']
            if server_name in excluded_servers:
                continue
            try:
                server_data = self.api.client.servers.get_server_utilization(server_uuid)
                parameters = self.api.client.servers.get_server(server_uuid)
                for variable in parameters['relationships']['variables']['data']:
                    if variable['attributes']['name'] == 'Forge Version':
                        core_name = parameters['relationships']['variables']['data'][3]['attributes']['name']
                        core_version = parameters['relationships']['variables']['data'][3]['attributes']['server_value']
                        break
                    elif variable['attributes']['name'] =='Server Version':
                        core_name = parameters['relationships']['variables']['data'][1]['attributes']['name']
                        core_version = parameters['relationships']['variables']['data'][1]['attributes']['server_value']
                        break
                else:
                    core_name = None
                    core_version = None
                port = parameters['relationships']['allocations']['data'][0]['attributes']['port']
                server_statuses[server_name] = {
                    "message": 'Запущен' if server_data['current_state'] == 'running' else 'Остановлен',
                    "port": port,
                    "core_name": core_name,
                    "core_version": core_version
                }
            except HTTPError as server_error:
                self.handle_error(server_statuses, server_name, server_error)
        return server_statuses

if __name__ == "__main__":
    linux = Linux()
    linux.run()