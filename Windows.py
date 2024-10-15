import subprocess
import threading
import socket
import time
import sys
import os

class Windows():
    def __init__(self):
        self.server = IP
        self.port = PORT
        self.header = 4096
        self.format = "utf-8"
        self.current_version = "1.0.0"
        self.client_socket = None
        self.client_status = None
        self.heartbeat_thread = False
        self.running = True

    def connect(self):
        start_time = time.time()
        max_time = 10
        while True:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.server, self.port))
                print("Подключение установлено.")
                self.client_status = 200
                if self.client_socket and self.client_status == 200:
                    self.available_update(self.client_socket)
                    if self.heartbeat_thread is False or self.heartbeat_thread.is_alive() is False:
                        self.heartbeat_thread = threading.Thread(target=self.heartbeat)
                        self.heartbeat_thread.start()
                    self.commands()
                break
            except socket.error as e:
                if time.time() - start_time > max_time:
                    print(f"Не удалось подключиться к серверу в течение {max_time} секунд.")
                    print(f"Ошибка подключения: {e}")
                    self.client_status = 500
                    self.commands()
                    break
    
    def available_update(self, client_socket):
        command = client_socket.recv(self.header).decode(self.format)
        if command.startswith("New version:"):
            latest_version = command.split(": ")[1]
            if latest_version != self.current_version:
                print(f"Доступно обновление: {self.current_version} -> {latest_version}")
                client_socket.sendall("Ready for update".encode(self.format))
                save_path = os.path.join(os.path.dirname(__file__), f"WindowsV{latest_version}.py")
                self.download_update(client_socket, save_path)
                print(f"Обновление загружено и сохранено по пути: {save_path}")
            else:
                client_socket.sendall("Do not need".encode(self.format))
                print("У вас установлена последняя версия.")
    
    def download_update(self, client_socket, save_path):
        print("Начало загрузки обновления...")
        with open(save_path, 'wb') as f:
            while True:
                bytes_read = client_socket.recv(self.header)
                if bytes_read == b"END_OF_FILE":
                    print("Загрузка завершена.")
                    break
                if not bytes_read:
                    print("Соединение закрыто сервером.")
                    break
                f.write(bytes_read)
        client_socket.sendall("Download complete".encode(self.format))
        server_confirmation = client_socket.recv(self.header).decode(self.format)
        if server_confirmation == "Transfer complete":
            try:
                command = input(f"Запуск нового приложения: {save_path}\nПодтвердить: [Д/Н]: ")
                if command in ["д", "да", "y", "yes"]:
                    subprocess.Popen([sys.executable, save_path])
                else:
                    os._exit(0)
            except Exception as e:
                print(f"Ошибка при запуске нового приложения: {e}")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        os._exit(0)

    def heartbeat(self):
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
                            time.sleep(1)
                            break
                        else:
                            print(response)
                    except socket.error as error:
                        print(f"Ошибка при отправке heartbeat: {error}\nНажмите Enter, чтобы перезапустить!")
                        self.client_status = 500
                        break
                    attempts += 1
                    time.sleep(1)
                if attempts == max_attempts:
                    print("Соединение потеряно после нескольких попыток.")
                    self.client_status = 500
                    if self.client_socket:
                        self.client_socket.close()
                        self.client_socket = None
                    return
            else:
                time.sleep(1)
  
    def commands(self):
        while self.running:
            if self.client_socket is not None:
                while self.client_status == 500:
                    command = input("Попробовать снова? [Д/Н]: ").lower()
                    if command in ["д", "да", "y", "yes"]:
                        print("Переподключение...")
                        self.connect()
                    elif command in ["н", "нет", "n", "no", "exit", "quit", "выйти"]:
                        os._exit(0)
                    else:
                        pass
                while self.client_status == 200:
                    print(f"SLCW> ", end="")
                    command = input().lower()
                    if not command:
                        continue
                    elif command == "":
                        continue
                    if command in ["exit", "quit", "выйти"]:
                        self.running = False
                        if self.client_socket:
                            try:
                                self.client_socket.sendall("exit".encode(self.format))
                            except socket.error as error:
                                print(f"Ошибка при отправке команды exit: {error}")
                            finally:
                                self.client_socket.close()
                                self.client_socket = None
                        os._exit(0)
                    else:
                        self.client_socket.sendall(command.encode(self.format))
                        print("Команда отправлена.")

    def run(self):
        try:
            while self.running:
                if self.client_socket is None and self.client_status is None:
                    print("Подключение...")
                    self.connect()
        except KeyboardInterrupt:
            os._exit(0)
        finally:
            self.client_socket.close()
            os._exit(0)

if __name__ == "__main__":
    windows = Windows()
    windows.run()
