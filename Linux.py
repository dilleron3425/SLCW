import socket
import threading
import queue
from time import sleep
import json
import os

from typing import Dict, Union, Generator, List
from requests.exceptions import HTTPError
from pydactyl import PterodactylClient

class SLCW():
    def __init__(self) -> None:
        self.format = "utf-8"
        with open("config.json", 'r', encoding=self.format) as file:
            self.config = json.load(file)
        self.server = self.config["server_ip"]
        self.port = self.config["server_port"]
        self.header = 4096
        self.latest_version = "1.1.0"
        self.update_file_path = "./updates/WindowsV1.1.0.exe"
        self.pterodactyl = PterodactylControl(self.config)

    def send_file(self, client_socket):
        try:
            with open(self.update_file_path, 'rb') as f:
                while True:
                    bytes_read = f.read(self.header)
                    if not bytes_read:
                        break
                    client_socket.sendall(bytes_read)
            sleep(1)
            client_socket.sendall(b"END_OF_FILE")
            confirmation = client_socket.recv(self.header).decode(self.format)
            if confirmation == "Download complete":
                print("Клиент подтвердил завершение загрузки.")
                client_socket.sendall("Transfer complete".encode(self.format))
        except Exception as e:
            print(f"Ошибка при отправке файла: {e}")
        finally:
            client_socket.close()

    def command_start(self, client_socket, server_name):
        server_status = self.pterodactyl.server_start(server_name)
        for status in server_status:
            server_name, server_info = next(iter(status.items()))
            client_socket.sendall(f"{server_info['message']}".encode(self.format))
    
    def command_restart(self, client_socket, server_name):
        server_status = self.pterodactyl.server_restart(server_name)
        for status in server_status:
            server_name, server_info = next(iter(status.items()))
            client_socket.sendall(f"{server_info['message']}".encode(self.format))

    def command_stop(self, client_socket, server_name):
        server_status = self.pterodactyl.server_stop(server_name)
        for status in server_status:
            server_name, server_info = next(iter(status.items()))
            client_socket.sendall(f"{server_info['message']}".encode(self.format))

    def command_stat(self, client_socket, server_name):
        server_status = self.pterodactyl.server_status(server_name)
        for status in server_status:
            server_name, server_info = next(iter(status.items()))
            client_socket.sendall(f"{server_info['message']}".encode(self.format))

    def handle_client(self, client_socket, client_addr):
        connected = True
        version_sent = False
        command_queue = queue.Queue()

        def command_worker():
            while True:
                command = command_queue.get()
                if command is None:
                    break
                self.handle_command(client_socket, client_addr, command)
                command_queue.task_done()
        command_thread = threading.Thread(target=command_worker)
        command_thread.start()

        try:
            while connected:
                if not version_sent:
                    file_size = os.path.getsize(self.update_file_path)
                    client_socket.sendall(f"New version: {self.latest_version} File size: {file_size}".encode(self.format))
                    response = client_socket.recv(self.header).decode(self.format)
                    if response == "Ready for update":
                        self.send_file(client_socket)
                        version_sent = True
                    elif response == "Do not need":
                        version_sent = True
                    else:
                        print("Неправильный ответ от клиента!")
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
        except Exception as e:
            print(f"[{client_addr}] ошибка: {e}")
        finally:
            command_queue.put(None)
            command_thread.join()
            if client_socket:
                try:
                    client_socket.close()
                except Exception as e:
                    print(f"Ошибка при закрытии сокета {client_addr}: {e}")

    def handle_command(self, client_socket, client_addr, command):
        try:
            if not command:
                return
            if command == "exit":
                return
            else:
                print(f"{client_addr} - {command}")
                parts = command.split()
                if len(parts) < 2:
                    client_socket.sendall("Неверный формат команды. Используйте: <команда> <имя_сервера>".encode(self.format))
                    return
                command, server_name = parts[0], parts[1]
                if command in ["start", "stat", "stop", "restart"]:
                    if server_name not in self.config['pterodactyl']['server_uuid']:
                        print("Неверный сервер или его не существует!")
                        return
                    if command == "start":
                        command_start = threading.Thread(target=self.command_start, args=(client_socket, server_name))
                        command_start.start()
                    elif command == "restart":
                        command_restart = threading.Thread(target=self.command_restart, args=(client_socket, server_name))
                        command_restart.start()
                    elif command == "stop":
                        command_stop = threading.Thread(target=self.command_stop, args=(client_socket, server_name))
                        command_stop.start()
                    elif command == "stat":
                        if server_name == "all":
                            client_socket.sendall(f"Временно не работает!".encode(self.format))
                        else:
                            command_stat = threading.Thread(target=self.command_stat, args=(client_socket, server_name))
                            command_stat.start()
        except Exception as error:
            print(f"[{client_addr}] ошибка: {error}")
        finally:
            pass

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.server, self.port))
        server_socket.listen()
        print(f"Сервер работает на {self.server}:{self.port}")
        try:
            while True:
                try:
                    client_socket, client_addr = server_socket.accept()
                    print(f"Подключен клиент: {client_addr}")
                    try:
                        with open("connections.txt", "a", encoding=self.format) as file:
                            file.write(f"{client_addr}\n")
                    except FileNotFoundError:
                        with open("connections.txt", "w", encoding=self.format) as file:
                            file.write(f"{client_addr}\n")
                        print(f'Файл "connections.txt" был создан и запись добавлена.')
                    threading.Thread(target=self.handle_client, args=(client_socket, client_addr)).start()
                    print(f"Кол. активных подключений: {threading.active_count() - 1}")
                except KeyboardInterrupt:
                    print("SLW остановлен!")
                    os._exit(0)
                except Exception as error:
                    print(f"Ошибка при закрытии сервера: {error}")
        finally:
            server_socket.close()

class PterodactylControl():
    def __init__(self, config) -> None:
        self.config = config
        self.api = PterodactylClient(self.config["urls"]["game_server"], self.config["ptero_api"])
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
    slw = SLCW()
    slw.run()