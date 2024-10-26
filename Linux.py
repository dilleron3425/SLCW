import socket

from typing import Dict, Union, Generator, List
from threading import Thread
from requests.exceptions import HTTPError
from pydactyl import PterodactylClient
from os import path
from queue import Queue
from time import sleep
from json import load

class Linux():
    def __init__(self) -> None:
        with open("config.json", 'r', encoding="utf-8") as file:
            self.config = load(file)
        self.server = self.config["server_ip"]
        self.port = self.config["server_port"]
        self.header = self.config["header"]
        self.format = self.config["format"]
        self.latest_version = self.config["version"]
        self.update_file_path = self.config["paths"]["update_file"]
        self.blocked_ips_file = self.config["paths"]["blocked_ips_file"]
        self.pterodactyl = PterodactylControl(self.config)

    def is_ip_blocked(self, ip):
        if path.exists(self.blocked_ips_file):
            with open(self.blocked_ips_file, "r") as file:
                blocked_ips = file.read().splitlines()
                return ip in blocked_ips
        return False
    
    def block_ip(self, ip):
        with open(self.blocked_ips_file, "a") as file:
            file.write(ip + "\n")
        print(f"IP {ip} был заблокирован.")


    def send_file(self, client_socket):
        try:
            with open(self.update_file_path, 'rb') as f:
                while (bytes_read := f.read(self.header)):
                    client_socket.sendall(bytes_read)
            sleep(1)
            client_socket.sendall(b"END_OF_FILE")
            confirmation = client_socket.recv(self.header).decode(self.format)
            if confirmation == "Download complete":
                print("Клиент подтвердил завершение загрузки.")
                client_socket.sendall("Transfer complete".encode(self.format))
        except Exception as error:
            print(f"Ошибка при отправке файла: {error}")

    def handle_client(self, client_socket, client_addr):
        connected = True
        version_sent = False
        command_queue = Queue()

        def command_worker():
            while True:
                command = command_queue.get()
                if command is None:
                    break
                self.handle_command(client_socket, client_addr, command)
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
                        self.send_file(client_socket)
                        version_sent = True
                    elif response == "Do not need":
                        version_sent = True
                    else:
                        print(f"Неправильный ответ от клиента: {response}")
                else:
                    try:
                        response = client_socket.recv(self.header).decode(self.format)
                        if not response:
                            print(f"{client_addr} отключился от SLW")
                            break
                        if response == "heartbeat":
                            client_socket.sendall("ack".encode(self.format))
                        else:
                            command_queue.put(response)
                    except OSError as e:
                        if e.errno == 9:
                            break
                        else:
                            print(f"[{client_addr}] socket error: {e}")
                            break
        except Exception as error:
            print(f"[{client_addr}] ошибка: {error}")
        finally:
            command_queue.put(None)
            command_thread.join()
            if client_socket:
                try:
                    client_socket.close()
                except Exception as error:
                    print(f"Ошибка при закрытии сокета {client_addr}: {error}")

    def handle_command(self, client_socket, client_addr, command):
            if not command or command == "exit":
                return
            
            print(f"{client_addr} - {command}")
            parts = command.split()
            if len(parts) < 2:
                client_socket.sendall("Неверный формат команды. Используйте: <команда> <имя_сервера>".encode(self.format))
                return
            
            command, server_name = parts[0], parts[1]
            if server_name not in self.config['pterodactyl']['server_uuid']:
                print("Неверный сервер или его не существует!")
                return
            
            command_map = {
                "start": self.command_start,
                "restart": self.command_restart,
                "stop": self.command_stop,
                "stat": self.command_stat,
            }

            if command in command_map:
                Thread(target=command_map[command], args=(client_socket, client_addr, server_name)).start()
        
    def command_start(self, client_socket, client_addr, server_name):
        self.execute_command(client_socket, client_addr, server_name)
    
    def command_restart(self, client_socket, client_addr, server_name):
        self.execute_command(client_socket, client_addr, server_name)

    def command_stop(self, client_socket, client_addr, server_name):
        self.execute_command(client_socket, client_addr, server_name)

    def command_stat(self, client_socket, client_addr, server_name):
        self.execute_command(client_socket, client_addr, server_name)
    
    def execute_command(self, client_socket, client_addr, server_name):
        try:
            server_status = self.pterodactyl.server_status(server_name)
            for status in server_status:
                server_name, server_info = next(iter(status.items()))
                client_socket.sendall(f"{server_info['message']}".encode(self.format))
        except OSError as error:
            if error.errno == 9:
                print(f"[{client_addr}] Отключился от SLCW")
            else:
                print(f"[{client_addr}] Ошибка: {error}")

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.server, self.port))
            server_socket.listen()
            print(f"Сервер работает на {self.server}:{self.port}")
            while True:
                try:
                    client_socket, client_addr = server_socket.accept()
                    client_ip = client_addr[0]
                    if self.is_ip_blocked(client_ip):
                        print(f"Подключение отклонено для заблокированного IP: {client_ip}")
                        client_socket.close()
                        continue  
                    print(f"Подключен клиент: {client_addr[0]}:{client_addr[1]}")
                    check_client = client_socket.recv(self.header).decode(self.format)
                    if check_client == "SLCW_CLIENT":
                        print(f"Клиент {client_ip} прошел проверку.")
                        Thread(target=self.handle_client, args=(client_socket, client_addr)).start()
                    else:
                        print(f"Неправильный клиент: {client_ip}:{client_addr[1]}")
                        self.block_ip(client_ip)
                        client_socket.close()
                except KeyboardInterrupt:
                    print("Сервер остановлен!")
                    break
                except OSError as error:
                    if error.errno == 32:
                        print(f"[{error.errno}] [{client_addr}] Преждевременное отключение клиента")
                    elif error.errno == 104:
                        print(f"[{error.errno}] [{client_addr}] Разрывает соединение до того, как ответит")
                    else:
                        print(f"Ошибка при закрытии сервера: {error}")

class PterodactylControl():
    def __init__(self, config) -> None:
        self.config = config
        self.api = PterodactylClient(self.config["urls"]["game_server"], self.config["pterodactyl"]["ptero_api"])
        self.no_server = {"message": f"Ошибка, не удалось найти сервер. Возможно, проблема в конфигурации сервера или у сервера SLW!", "color": None}

    def handle_error(self, server_status: dict, server_name: str, server_error: Exception) -> None:
        error_messages = {
            409: "Ошибка 409, не удается обработать запрос из-за конфликта в текущем состоянии сервера.",
            429: "Ошибка 429, слишком много запросов на сервер за единицу времени.",
            500: "Ошибка 500, неисправность конфигурации сервера или запрос был отказан."
        }
        if isinstance(server_error, HTTPError):
            error_code = server_error.response.status_code
            message = error_messages.get(error_code, f"Ошибка {error_code} при извлечении данных из сервера.")
        elif isinstance(server_error, KeyError):
            message = "Ошибка, не найдена конфигурация для Pterodactyl на сервере или у сервера SLW!"
        else:
            message = f"Не известная ошибка: {server_error}"
        server_status[server_name] = {"message": message, "color": None}
    
    def get_server_list(self) -> List[Dict[str, str]]:
        server_list = self.api.client.servers.list_servers()
        servers = []
        for inner_list in server_list:
            for server in inner_list:
                server_name = server['attributes']['name']
                server_uuid = server['attributes']['uuid']
                servers.append({"name": server_name, "uuid": server_uuid})
        return servers
    
    def server_status(self, server_name: str) -> Generator[Dict[str, Dict[str, Union[str, None, int]]], None, None]:
        server_status = {}
        try:
            server_uuid = self.config['pterodactyl']['server_uuid'].get(server_name)
            if server_uuid:
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
                        "color": None if server_data['current_state'] == 'running' else None,
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
            server_uuid = self.config['pterodactyl']['server_uuid'].get(server_name)
            if server_uuid:
                try:
                    if current_state == 'Запущен':
                        server_status[server_name] = {
                        "message": 'Уже запущен',
                        "color": None,
                        "port": port,
                        "core_name": core_name,
                        "core_version": core_version
                        }
                    else:
                        self.api.client.servers.send_power_action(server_uuid, 'start')
                        server_status[server_name] = {"message": "Запускается...", "color": None}
                        yield server_status
                        while self.api.client.servers.get_server_utilization(server_uuid)['current_state'] != 'running':
                            self.api.client.servers.get_server_utilization(server_uuid)['current_state']
                        server_status[server_name] = {
                        "message": 'Запущен',
                        "color": None,
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
        server_status_generator = self.server_status(server_name)
        server_status = next(server_status_generator)
        core_name = server_status[server_name]['core_name']
        core_version = server_status[server_name]['core_version']
        port = server_status[server_name]['port']
        try:
            server_uuid = self.config['pterodactyl']['server_uuid'].get(server_name)
            if server_uuid:
                try:
                    if self.api.client.servers.get_server_utilization(server_uuid)['current_state'] == 'starting':
                        server_status[server_name] = {"message": "Уже перезапускается...", "color": None}
                    else:
                        self.api.client.servers.send_power_action(server_uuid, 'restart')
                        server_status[server_name] = {"message": "Перезапускается...", "color": None}
                        yield server_status
                        while self.api.client.servers.get_server_utilization(server_uuid)['current_state'] != 'running':
                            self.api.client.servers.get_server_utilization(server_uuid)['current_state']
                        server_status[server_name] = {
                        "message": 'Запущен',
                        "color": None,
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
        server_status_generator = self.server_status(server_name)
        server_status = next(server_status_generator)
        current_state = server_status[server_name]['message']
        try:
            server_uuid = self.config['pterodactyl']['server_uuid'].get(server_name)
            if server_uuid:
                try:
                    if current_state == 'Остановлен':
                        server_status[server_name] = {"message": "Уже остановлен", "color": None}
                    else:
                        self.api.client.servers.send_power_action(server_uuid, 'stop')
                        server_status[server_name] = {"message": "Останавливается...", "color": None}
                        yield server_status
                        while self.api.client.servers.get_server_utilization(server_uuid)['current_state'] != 'offline':
                            self.api.client.servers.get_server_utilization(server_uuid)['current_state']
                        server_status[server_name] = {"message": "Остановлен", "color": None}
                except Exception as server_error:
                    self.handle_error(server_status, server_name, server_error)
            else:
                server_status[server_name] = self.no_server
        except Exception as server_error:
            self.handle_error(server_status, server_name, server_error)
        yield server_status

    def stat_all(self) -> Dict[str, Dict[str, Union[str, None]]]:
        server_list = self.get_server_list()
        server_statuses = {}
        for server in server_list:
            server_name = server['name']
            server_uuid = server['uuid']
            try:
                server_info = self.api.client.servers.get_server_utilization(server_uuid)
                server_statuses[server_name] = {
                    "message": 'Запущен' if server_info['current_state'] == 'running' else 'Остановлен',
                    "color": None if server_info['current_state'] == 'running' else None
                }  
            except HTTPError as server_error:
                self.handle_error(server_statuses, server_name, server_error)
        return server_statuses

if __name__ == "__main__":
    linux = Linux()
    linux.run()