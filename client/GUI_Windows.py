import customtkinter as ctk
import socket

from threading import Thread, Event, current_thread
from json import load, loads, dump, JSONDecodeError
from os import path, remove, makedirs
from webbrowser import open as web_open
from sys import executable, exit
from time import time, sleep, strftime
from requests import get as req_get
from PIL import Image as PIL_Image
from datetime import datetime
from shutil import move, copy
from subprocess import Popen
from queue import Queue

RUNNING = True
WS_THREAD = None
WS_THREAD_STOP = Event()
HEARTBEAT_THREAD = None
HEARTBEAT_THREAD_STOP = Event()
SEND_LOG_FILE_THREAD = None
SEND_LOG_FILE_THREAD_STOP = Event()
DOWNLOAD_INFO_ICON_BTN = None
DOWNLOAD_INFO_ICON_BTN_STOP = Event()

ctk.set_appearance_mode("Dark")

class GUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.configure_class = Configure(self.message_handler)
        self.config = self.configure_class.config_handler()

        self.logger = Logger(self.config, self.message_handler)
        self.log_message = self.logger.log_message

        self.log_message(f"[Info] Версия SLCW: {self.config["version"]}")
        self.log_message(f"[Info] Путь журнала: {self.logger.get_log_file_path()}")
        self.app_title = self.config["app_names"]["GUI_app"]
        self.app_version = self.config["version"]
        self.info_icon_button_url = self.config["urls"]["info_icon_button"]
        self.sent_error_msg = False
        self.selected_frame = None
        self.sidebar_frame = None
        self.conn_label = None
        self.game_server_data = {}
        self.button_frames = []
        global WS_THREAD
        global WS_THREAD_STOP

        start_time = time()
        self.threader = Threader(self.log_message)
        WS_THREAD = self.threader.start_func_thread(WS_THREAD, WS_THREAD_STOP, self.start_class_windows_client)
        self.log_message(f"[Info] Threader & WindowsClient: {time() - start_time}")

        self.title(self.app_title)
        self.geometry(f"{550}x{500}")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        start_time = time()
        self.run()
        self.log_message(f"[Info] GUI & run: {time() - start_time}")

    def start_class_windows_client(self):
        self.windows = WindowsClient(self.message_handler, self.conn_server_label_creator, self.find_button_frame_by_name, self.frame_color_changer, self.on_info_btn_click, self.threader, self.logger, self.configure_class)
        self.windows.run()

    def sidebar_creator(self):
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")

        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        logo_label = ctk.CTkLabel(self.sidebar_frame, text=self.app_title, font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.grid(row=0, column=0, padx=20, pady=(10, 10))

        version_label = ctk.CTkLabel(self.sidebar_frame, text=f"Версия {self.app_version}", font=ctk.CTkFont(size=15))
        version_label.grid(row=3, column=0, padx=20, pady=(10, 5), sticky="s")

    def conn_server_label_creator(self, connected: bool = False) -> None:
        if self.sidebar_frame is None:
            sleep(1)

        if connected is True:
            if self.conn_label is not None:
                self.conn_label.after(0, self.conn_label.destroy())
                self.conn_label = None
                return
        
        if connected == "Connecting...":
            if self.conn_label is not None:
                self.conn_label.configure(text=connected, font=ctk.CTkFont(size=15), fg_color="orange")
            else:            
                self.conn_label = ctk.CTkLabel(
                    self.sidebar_frame,
                    text="Подключение...",
                    font=ctk.CTkFont(size=15),
                    fg_color="orange")
                self.conn_label.grid(row=1, column=0, padx=20, pady=0)
            return

        if connected is False:
            if self.conn_label is not None:
                self.conn_label.configure(text="Не подключён\nк серверу!\nНажмите\n'Обновить'", font=ctk.CTkFont(size=15), fg_color="red")
            else:
                self.conn_label = ctk.CTkLabel(
                    self.sidebar_frame,
                    text="Не подключён\nк серверу!\nНажмите\n'Обновить'",
                    font=ctk.CTkFont(size=15),
                    fg_color="red")
                self.conn_label.grid(row=1, column=0, padx=20, pady=0)

    def center_bar_creator(self):
        center_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        center_frame.grid(row=0, column=1, rowspan=2, columnspan=2, sticky="nsew")

        center_frame.grid_columnconfigure(1, weight=1)
        center_frame.grid_columnconfigure(2, weight=1)

        servers_label = ctk.CTkLabel(center_frame, text="Сервера", font=ctk.CTkFont(size=20, weight="bold"))
        servers_label.grid(row=0, column=1, columnspan=2, pady=10)

        refresh_button = ctk.CTkButton(center_frame, text="Обновить", corner_radius=10, width=80, height=30, fg_color="#0047AB", hover_color="#0096FF", command=self.refresh_servers)
        refresh_button.grid(row=0, column=2, padx=10, pady=10, sticky="ne")

        kbld11_frame = self.create_button_frame(center_frame, "KBLD11")
        kbld11_frame.grid(row=1, column=1, padx=20, pady=20, sticky="ew")
        self.button_frames.append(kbld11_frame)

        kblda_frame = self.create_button_frame(center_frame, "KBLDA")
        kblda_frame.grid(row=1, column=2, padx=20, pady=20, sticky="ew")
        self.button_frames.append(kblda_frame)

        dima_leo_frame = self.create_button_frame(center_frame, "Dima-Leo")
        dima_leo_frame.grid(row=2, column=1, padx=20, pady=20, sticky="ew")
        self.button_frames.append(dima_leo_frame)

        self.buttons_creator()

    def create_button_frame(self, center_frame, text):
        button_frame = ctk.CTkFrame(center_frame, width=150, height=150, corner_radius=15, border_width=2, border_color="black", fg_color="transparent")
        button_frame.pack_propagate(False)
        button_frame._name = text

        button_frame.bind("<Button-1>", lambda event: self.on_frame_click(button_frame))
        button_frame.bind("<Enter>", lambda event: self.on_frame_enter(button_frame))
        button_frame.bind("<Leave>", lambda event: self.on_frame_leave(button_frame))

        server_name_label = ctk.CTkLabel(button_frame, text=text, font=ctk.CTkFont(size=15))
        server_name_label.place(relx=.5, y=30, anchor="center")

        try:
            image_path = path.join(path.expanduser("~"), "SLCW", "Images", "info-button.ico")
            load_info_image = PIL_Image.open(image_path)
            info_image = ctk.CTkImage(load_info_image)
            info_button = ctk.CTkButton(button_frame, image=info_image, text="", width=0, height=0, fg_color="transparent", hover_color="#5a5a5a")
            info_button.place(relx=1, x=-10, y=15, anchor="ne")
        except OSError as error:
            if error.errno == 2:
                if self.sent_error_msg is False:
                    self.message_handler("Error", "Отсутствует изображение info-button.ico. Пожалуйста обратитесь к администратору.")
                    self.sent_error_msg = True
            else:
                self.log_message(f"[Error] Не удалось загрузить изображение info-button.ico: {error}")

        horizontal_line = ctk.CTkFrame(button_frame, height=2, fg_color="black")
        horizontal_line.pack(fill="x", pady=(100, 0))

        players_label = ctk.CTkLabel(button_frame, text="Игроки: ", font=ctk.CTkFont(size=15))
        players_label.pack(side="bottom", anchor="sw", padx=10, pady=(0, 3))

        status_label = ctk.CTkLabel(button_frame, text="Статус: ", font=ctk.CTkFont(size=15))
        status_label.pack(side="bottom", anchor="sw", padx=10, pady=(0, 0))

        return button_frame

    def on_info_btn_click(self, button_frame, info_text):
        self.log_message(f"[Info] Кнопка информации {button_frame._name} была нажата")
        self.message_handler(f"{button_frame._name}'s information", info_text)

    def on_frame_click(self, button_frame):
        self.log_message(f"[Info] {button_frame._name} фрейм был нажат")
        if self.selected_frame and self.selected_frame != button_frame:
            self.selected_frame.configure(fg_color="transparent")

        self.selected_frame = button_frame
        button_frame.configure(fg_color="gray")

    def on_frame_enter(self, button_frame):
        if button_frame != self.selected_frame:
            button_frame.configure(fg_color="gray")

    def on_frame_leave(self, button_frame):
        if button_frame != self.selected_frame:
            button_frame.configure(fg_color="transparent")

    def buttons_creator(self):
        buttons_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        buttons_frame.grid(row=3, column=1, sticky="ew")

        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)

        start_button = ctk.CTkButton(buttons_frame,
                                     width=70,
                                     height=30,
                                     text="Старт",
                                     corner_radius=10,
                                     fg_color="#008000",
                                     hover_color="#00CC00",
                                     command=self.start_server)
        start_button.grid(row=0, column=0, padx=10, pady=20, sticky="ew")

        stop_button = ctk.CTkButton(buttons_frame,
                                     width=70,
                                     height=30,
                                     text="Стоп",
                                     corner_radius=10,
                                     fg_color="#CC0000",
                                     hover_color="#FF3333",
                                     command=self.stop_server)
        stop_button.grid(row=0, column=1, padx=10, pady=20, sticky="ew")

    def start_server(self):
        self.log_message(f"[Info] Кнопка старт была нажата")
        if self.selected_frame:
            self.windows.add_task(f"start {self.selected_frame._name}")
            self.selected_frame.configure(fg_color="transparent", border_color="#808080")

    def stop_server(self):
        self.log_message(f"[Info] Кнопка стоп была нажата")
        if self.selected_frame:
            self.windows.add_task(f"stop {self.selected_frame._name}")
            self.selected_frame.configure(fg_color="transparent", border_color="#808080")

    def frame_color_changer(self, server_name: str, status: bool = False):
        button_frame = self.find_button_frame_by_name(server_name)
        if button_frame:
            if status:
                button_frame.configure(fg_color="transparent", border_color="#008000")
                self.log_message(f"[Info] Цвет {button_frame._name} был изменён на зелёный")
            else:
                button_frame.configure(fg_color="transparent", border_color="#CC0000")
                self.log_message(f"[Info] Цвет {button_frame._name} был изменён на красный")

    def find_button_frame_by_name(self, server_name: str):
        if server_name == "Selected":
            server_name = self.selected_frame._name
        for button_frame in self.button_frames:
            if button_frame._name == server_name:
                return button_frame
        return None

    def refresh_servers(self):
        if self.windows.client_status == 500:
            self.log_message(f"[Info] Кнопка установить соединение с сервером была нажата")
            self.conn_server_label_creator("Connecting...")
            self.windows.add_task("connect")
        else:
            self.log_message(f"[Info] Кнопка обновить данные серверов была нажата")
            self.windows.add_task("get_game_server_date")

    def message_handler(self, type_message, message, error = None):
        handler = ctk.CTkToplevel()
        handler.title(type_message)
        handler.geometry("300x200")
        handler.resizable(False, False)
        handler.attributes('-topmost', True)

        text_area = ctk.CTkTextbox(handler)
        text_area.pack(expand=True, fill="both")
        text_area.insert("end", (message + f": {error}" if error else message) + "\n")

    def download_info_icon_btn(self):
        if not path.exists(path.join(path.expanduser("~"), "SLCW", "Images")):
            try:
                makedirs(path.join(path.expanduser("~"), "SLCW", "Images"), exist_ok=True)
            except OSError as error:
                self.message_handler("Error", "Не удалось создать папку для изображений", error)
        response = req_get(self.info_icon_button_url, verify=False)
        if response.status_code == 200:
            with open(path.join(path.expanduser("~"), "SLCW", "Images", "info-button.ico"), "wb") as file:
                file.write(response.content)
        

    def on_closing(self):
        global SEND_LOG_FILE_THREAD
        global SEND_LOG_FILE_THREAD_STOP

        try:
            self.log_message("[Info] Закрытие программы...")
            SEND_LOG_FILE_THREAD = self.threader.start_func_thread(SEND_LOG_FILE_THREAD, SEND_LOG_FILE_THREAD_STOP, self.logger.send_log_file, (self.threader, self.windows.client_socket, ))

            if SEND_LOG_FILE_THREAD is not None:
                while SEND_LOG_FILE_THREAD.is_alive():
                    SEND_LOG_FILE_THREAD.join(timeout=0.1)

            self.log_message("[Info] Отправка логов завершена")
            self.quit()
        except Exception as error:
            try:
                self.log_message(f"[Error] {str(error)}")
                self.message_handler("Error", "При закрытии программы произошла ошибка", str(error))
            except Exception as error:
                pass

    def run(self):
        if not path.exists(path.join(path.expanduser("~"), "SLCW", "Images", "info-button.ico")): 
            global DOWNLOAD_INFO_ICON_BTN
            global DOWNLOAD_INFO_ICON_BTN_STOP
            DOWNLOAD_INFO_ICON_BTN = self.threader.start_func_thread(DOWNLOAD_INFO_ICON_BTN, DOWNLOAD_INFO_ICON_BTN_STOP, self.download_info_icon_btn)
            if DOWNLOAD_INFO_ICON_BTN.is_alive():
                DOWNLOAD_INFO_ICON_BTN.join(timeout=0.1)
        self.sidebar_creator()
        self.center_bar_creator()

class WindowsClient():
    def __init__(self, msg_handler_gui, conn_srv_label_creator, find_button_frame_by_name, frame_color_changer, on_info_btn_click, threader, logger, configure) -> None:
        """Инициализации класса WindowsClient"""
        self.message_handler_gui = msg_handler_gui
        self.conn_server_label_creator = conn_srv_label_creator
        self.find_button_frame_by_name = find_button_frame_by_name
        self.frame_color_changer = frame_color_changer
        self.on_info_btn_click = on_info_btn_click
        self.threader = threader
        self.logger = logger
        self.log_message = self.logger.log_message
        self.configure = configure
        self.config = self.configure.config_handler()
        self.server = self.config["server_ip"]
        self.port = self.config["server_port"]
        self.header = self.config["header"]
        self.format = self.config["format"]
        self.current_version = self.config["version"]
        self.conn_time = self.config["connection_time"]
        self.github_releases = self.config["urls"]["github_releases"]
        self.client_socket = None
        self.client_status = None
        self.task_queue = Queue()

    def handle_message(self, message: str, message_type: str, error: Exception = None) -> None:
        """Обработка сообщений и вывод их в консоль"""
        if message_type == "error":
            error_message = f": {error}" if error else ""
            self.message_handler_gui([message_type.capitalize()], message, error_message)
            self.log_message(f"[{message_type.capitalize()}] {message}{error_message}")
        else:
            self.message_handler_gui([message_type.capitalize()], message, None)
            self.log_message(f"[{message_type.capitalize()}] {message}")

    def handle_server(self, message: str) -> None:
        """Обработчик сообщений от сервера"""
        running_keywords = {"Запущен", "Уже запущен"}
        processing_keywords = {"Запускается...", "Останавливается..."}
        stopped_keywords = {"Остановлен", "Уже остановлен"}
        servers = {}

        try:
            servers = loads(message)
        except JSONDecodeError:
            if any(keyword in message for keyword in running_keywords):
                self.frame_color_changer("Selected", True)
            elif any(keyword in message for keyword in stopped_keywords):
                self.frame_color_changer("Selected", False)
            elif any(keyword in message for keyword in processing_keywords):
                pass
            else:
                self.handle_message(message, "server")
            return

        for server_name, server_data in servers.items():
                server_msg = server_data.get("message", "")
                port = server_data.get("port", "")
                core_name = server_data.get("core_name", "Неизвестно")
                core_version = server_data.get("core_version", "Неизвестно")
                button_frame = self.find_button_frame_by_name(server_name)
                if button_frame:
                    for widget in button_frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            if widget.cget("text").startswith("Игроки:"):
                                if server_msg in running_keywords:
                                    widget.configure(text=f"Игроки: 1-?")
                                elif server_msg in processing_keywords or server_msg in stopped_keywords:
                                    widget.configure(text=f"Игроки: 0")
                            elif widget.cget("text").startswith("Статус:"):
                                widget.configure(text=f"Статус: {server_msg}")
                        elif isinstance(widget, ctk.CTkButton) and widget.cget("text") == "":
                            if server_name == button_frame._name:
                                info_text = f"IP: dillertm.ru\nПорт: {port}\nЯдро: {core_name}\nВерсия ядра: {core_version}"
                                widget.configure(command=lambda bt=button_frame, txt=info_text: self.on_info_btn_click(bt, txt))
                if any(keyword in server_msg for keyword in running_keywords):
                    self.frame_color_changer(server_name, True)
                elif any(keyword in server_msg for keyword in stopped_keywords):
                    self.frame_color_changer(server_name, False)
                elif any(keyword in server_msg for keyword in processing_keywords):
                    pass
                else:
                    self.handle_message(server_msg, "server")

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

    def add_task(self, task: str):
        """Добавляет задачу в очередь для выполнения в потоке"""
        self.log_message(f"[Info] Добавлена задача в очередь для выполнения в потоке: {task}")
        self.task_queue.put(task)

    def connect(self)  -> None:
        """Подключает клиента к серверу"""
        start_time = time()
        sent_error = False
        global HEARTBEAT_THREAD
        global HEARTBEAT_THREAD_STOP
        while True:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.server, self.port))
                self.log_message("[Info] Подключился")
                self.client_socket.sendall("SLCW_CLIENT".encode(self.format))
                self.available_update()
                self.client_status = 200
                self.conn_server_label_creator(True)
                self.client_socket.sendall("SERVER_STATUS".encode(self.format))
                self.threader.start_func_thread(HEARTBEAT_THREAD, HEARTBEAT_THREAD_STOP, self.heartbeat)
                break
            except OSError as error:
                if error.errno in (111, 10061) or ((time() - start_time) > self.conn_time): # Не удалось установить соединение
                    if not sent_error:
                        self.handle_error(f"Не удалось подключиться к серверу в течение {self.conn_time} секунд, возможно, сервер не работает. Нажмите 'Обновить', что бы заново подключиться!")
                        self.client_status = 500
                        self.conn_server_label_creator(False)
                        sent_error = True
                else:
                    self.handle_error(f"Не удалось подключиться к серверу в течение {self.conn_time} секунд", error)
                    self.client_status = 500
                    self.conn_server_label_creator(False)
                break

    def available_update(self) -> None:
        """Проверяет доступность обновления"""
        command = self.client_socket.recv(self.header).decode(self.format)
        current_executable_path = path.abspath(executable)
        if not command.startswith("New version:"):
            self.handle_warn("Не пришли данные об обновлении")
            return
        try:
            parts = command.split(";")
            latest_version = parts[0].split(": ")[1]
            new_version_size = float(parts[1].split(": ")[1])
            if latest_version == self.current_version:
                self.log_message(f"[Info] Получены данные о версиях. Версия SLCW у клиента: {self.current_version}, Версия SLCW у сервера: {latest_version}")
                self.handle_latest_version(current_executable_path)
                return
            current_version_size = int(path.getsize("GUI SLCW.exe")) / (1024 * 1024)
            diff_versions = new_version_size - current_version_size
            self.log_message(f"[Info] Получены данные об обновлении: версия {latest_version}, размер {new_version_size:.2f} MB")
        except OSError as error:
            self.handle_error("Не удалось получить информацию о новой версии", error)
            return
        self.handle_info(f"Доступно обновление: {self.current_version} -> {latest_version}\nРазмер версий: {current_version_size:.2f} МБ -> {new_version_size:.2f} МБ | Разница: {diff_versions:.2f} МБ\nЗагрузка...")
        try:
            self.client_socket.sendall("Ready for update".encode(self.format))
            save_path = path.join(path.abspath(path.dirname(executable)), f"NEW GUI SLCW.exe")
            if save_path:
                self.download_handler("UPDATE", save_path, latest_version)
                self.replace_executable(save_path, current_executable_path)
                self.configure.config_handler(update=True)
                self.launch_new_app(save_path)
            else:
                self.handle_error(f"Не удалось сохранить файл обновления по пути: {save_path}")
        except Exception as error:
            self.handle_error("Не удалось скачать обновление", error)
            return

    def handle_latest_version(self, current_executable_path: str) -> None:
        """Обрабатывает ситуацию, когда новая версия не доступна"""
        application = "GUI SLCW.exe"
        target_executable_path = path.abspath(application)

        if path.basename(current_executable_path) == "SLCW.exe":
            new_path = path.join(path.dirname(current_executable_path), application)
            try:
                move(current_executable_path, new_path)
                current_executable_path = new_path
                self.log_message(f"[Info] Файл переименован в {application}")
            except Exception as error:
                self.handle_error(f"Не удалось переименовать файл: {error}")
                return

        if current_executable_path != target_executable_path:
            sleep(1)
            try:
                remove(target_executable_path)
                self.log_message(f"[Info] Старый файл {target_executable_path} удалён")
            except OSError as error:
                if error.winerror == 2: # Нету файл или папки
                    self.log_message(f"[Warn] Не удалось найти старый файл {target_executable_path}")
                elif error.winerror == 5:  # Нет доступа
                    self.handle_error(f"Нет доступа к старому файлу {target_executable_path}, чтобы удалить файл")
                else:
                    self.handle_error(f"Не удалось удалить старый файл {target_executable_path}", error)
            except PermissionError:
                self.handle_warn(f"Нет доступа к старому файлу {target_executable_path}, чтобы удалить файл")
            try:
                move(current_executable_path, target_executable_path)
                self.log_message(f"[Info] Текущий файл переименован в {application}")
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
                self.handle_error(f"Нет доступа к новому файлу {current_executable_path}, чтобы переименовать файл")
            try:
                app_folder = path.join(path.expanduser("~"), "SLCW")
                target_path = path.join(app_folder, "GUI SLCW.exe")
                current_executable_path = path.join(path.abspath(path.dirname(executable)), f"GUI SLCW.exe")
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
        return

    def replace_executable(self, save_path: str, current_executable_path: str) -> None:
        """Заменяет текущий исполняемый файл на скачанный"""
        try:
            move(save_path, current_executable_path)
            self.handle_done(f"Обновление загружено и сохранено по пути: {save_path}")
        except OSError as error:
            if error.winerror == 32:
                self.handle_warn(f"Не удалось заменить файл {save_path} -> {current_executable_path}, так как занят другим процессом")
            elif error.winerror == 5:
                self.handle_error(f"Нет доступа к файлу {save_path}, чтобы заменить файл")
            else:
                self.handle_warn(f"Не удалось заменить файл: {error}")

    def launch_new_app(self, save_path: str) -> None:
        """Запускает скачанный исполняемый файл"""
        self.handle_info("Запуск нового приложения...")
        sleep(1)
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

    def download_handler(self, type: str, save_path: str, latest_version: str = None) -> None:
        """Обработчик загрузок"""
        if type == "UPDATE":
            self.open_url()
        self.log_message("[Info] Загрузка...")
        try:
            with open(save_path, 'wb') as file:
                while True:
                    bytes_read = self.client_socket.recv(self.header)
                    if bytes_read == "File not found":
                        self.handle_error("Сервер не может отправить вам файл, пожалуйста, сообщите администратору")
                        if latest_version:
                            self.current_version = latest_version
                        return
                    if not bytes_read:
                        self.handle_error("Соединение закрыто сервером")
                        break
                    if bytes_read == b"END_OF_FILE":
                        self.log_message("[Info] Загрузка завершена")
                        break
                    file.write(bytes_read)
            self.client_socket.sendall("Download complete".encode(self.format))
            server_confirmation = self.client_socket.recv(self.header).decode(self.format)
            if server_confirmation != "Transfer complete":
                self.handle_warn("Сервер не подтвердил завершение скачивания")
        except Exception as error:
            self.handle_error("Не удалось сохранить файл", error)
        finally:
            if type == "UPDATE":
                self.close_client_socket()

    def heartbeat(self) -> None:
        """Отправляет heartbeat на сервер"""
        global HEARTBEAT_THREAD_STOP
        max_attempts = 3
        attempts = 0
        while not HEARTBEAT_THREAD_STOP.is_set():
            while attempts < max_attempts:
                try:
                    sleep(1)
                    if self.client_socket is None or not isinstance(self.client_socket, socket.socket):
                        self.handle_error("Подключение не правильно инициализировано. Отключён от сервера!")
                        return
                    self.client_socket.sendall("heartbeat".encode(self.format))
                    response = self.client_socket.recv(self.header).decode(self.format)
                    if "ack" in response:
                        response = response.replace("ack", "").strip()
                        if response != "":
                            self.handle_server(response)
                        attempts = 0
                        break
                    else:
                        if response == "":
                            attempts += 1
                            break
                        attempts = 0
                        self.handle_server(response)
                        break
                except UnicodeDecodeError:
                    self.handle_error("Не правильный формат ответ от сервера. Повторная попытка...")
                    attempts += 1
                except JSONDecodeError:
                    pass
                except socket.error as error:
                    if error.errno == 10038: # Приложение пытается выполнить операцию на объекте, не являющийся сокетом
                        self.handle_error("Потеря соединение с сервером ошибка 10038.\nВозможно проблема в программе, обратитесь к разработчику")
                        return
                    elif error.errno == 10053:
                        self.handle_error("Программа SLCW разорвало соединение с сервером\nНажмите 'Обновить', чтобы переподключиться")
                        return
                    elif error.errno == 10054:
                        self.handle_error("Сервер SLCW разорвал соединение\nНажмите 'Обновить', чтобы переподключиться")
                        return
                    elif error.errno == 10060: # Превышено время ожидания подключения
                        pass
                    else:
                        self.handle_error(f"Потеря соединение с сервером: {error}\nНажмите 'Обновить', чтобы переподключиться")
                    self.client_status = 500
                    attempts += 1
            if attempts >= max_attempts:
                self.handle_error("Соединение потеряно после нескольких попыток\nНажмите 'Обновить', чтобы переподключиться")
                self.client_status = 500
                self.conn_server_label_creator(False)
                return

    def get_game_server_data(self):
        """Отправляет запрос на сервер за данными игрового сервера"""
        self.client_socket.sendall("SERVER_STATUS".encode(self.format))

    def commands(self, command_gui: str = None) -> None:
        """Обрабатывает команды и отправляет их на сервер"""
        while RUNNING:
            if self.client_socket is not None:
                while self.client_status == 500:
                    self.close_client_socket()
                    self.handle_info("Переподключение...")
                    self.conn_server_label_creator("Connecting...")
                    self.connect()
                    return
                while self.client_status == 200:
                    if not command_gui or command_gui == "":
                        continue
                    else:
                        self.client_socket.sendall(command_gui.encode(self.format))
                        self.log_message(f"[Info] Команда ({command_gui}) отправлена")
                        return

    def process_tasks(self):
        if not self.task_queue.empty():
            task = self.task_queue.get()
            if task == "connect":
                self.connect()
            elif task == "get_game_server_date":
                self.get_game_server_data()
            elif task.startswith("command:"):
                command = task.split(":", 1)[1]
                self.commands(command)
            else:
                self.commands(task)
            self.task_queue.task_done()

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
        try:
            while RUNNING:
                if self.client_socket is None and self.client_status is None:
                    self.log_message("[Info] Подключение...")
                    self.connect()
                self.process_tasks()
                sleep(.1)
        except Exception as error:
            self.handle_error("Произошла ошибка", error)
        finally:
            print("WindowsClient closed")
            self.close_client_socket()
            exit()

class Configure():
    def __init__(self, message_handler_gui):
        self.config_path = path.join(path.expanduser("~"), "SLCW", "config.json")
        self.message_handler_gui = message_handler_gui
        self._cache_config_loader = None
        self.config_data = {
            "app_names": {
                "CLI_app": "SLCW",
                "GUI_app": "GUI SLCW"
            },
            "version": "1.4.0",
            "created_by": "Diller™",
            "server_ip": "connecting ip(str) server",
            "server_port": "listening port(int) server",
            "header": 4096,
            "format": "utf-8",
            "connection_time": 5,
            "paths":{
                "log_dir": "logs",
                "icon_file": "SLCW.ico"
            },
            "urls": {
                "github": "https://github.com/dilleron3425",
                "github_releases": "https://github.com/dilleron3425/SLCW/releases",
                "info_icon_button": "https://dillertm.ru/files/info-button.ico"
            }
        }


    def config_handler(self, update: bool = False) -> dict:
        if update:
            self.config_writer()

        return self.config_loader()

    def config_loader(self) -> dict:
        config = self._cache_config_loader
        if config is None:
            try:
                with open(self.config_path, 'r', encoding="utf-8") as file:
                    config = load(file)
            except FileNotFoundError:
                config = self.config_data
                self.config_writer()
            except Exception as error:
                self.message_handler_gui("Error", f"Ошибка при загрузке конфигурационного файла {self.config_path}", error)
                config = self.config_data
            finally:
                self._cache_config_loader = config
        return config

    def config_writer(self):
        try:
            if path.exists(self.config_path):
                remove(self.config_path)

            with open(self.config_path, 'w', encoding="utf-8") as file:
                dump(self.config_data, file, indent=4)
                return
        except PermissionError:
            self.message_handler_gui("Error", f"Доступ к файлу {self.config_path} запрещён, пожалуйста, запустите программу от имени администратора")
        except Exception as error:
            self.message_handler_gui("Error", f"Ошибка при записи конфигурационного файла {self.config_path}", error)

class Threader():
    def __init__(self, log_message):
        self.log_message = log_message

    def start_func_thread(self, func_thread, func_thread_stop, target_func, target_args: tuple = None) -> None:
        """Запускает поток для выполнения функции"""
        try:
            if func_thread is None or not func_thread.is_alive():
                self.log_message(f"[Info] Запуск потока {target_func.__name__}")
                func_thread_stop.clear()
                if not target_args:
                    func_thread = Thread(target=target_func, name=target_func.__name__)
                else:
                    func_thread = Thread(target=target_func, args=target_args, name=target_func.__name__)
                func_thread.daemon = True
                func_thread.start()
                return func_thread
        except Exception as error:
            self.log_message(f"[Error] Ошибка при запуске потока {target_func.__name__} - {error}")

    def stop_func_thread(self, func_thread: Thread, func_thread_stop: bool) -> None:
        """Останавливает поток для выполнения функции"""
        try:
            if func_thread is not None:
                self.log_message(f"[Info] Остановка потока {func_thread.name}")
                func_thread_stop.set()
                if func_thread is not current_thread():
                    func_thread.join()
                    func_thread = None
        except Exception as error:
            self.log_message(f"[Error] Ошибка при остановке потока {func_thread.name} - {error}")

class Logger():
    def __init__(self, config, message_handler_gui):
        self.message_handler_gui = message_handler_gui
        self.config = config
        self.format = self.config["format"]
        self.header = self.config["header"]
        self._cache_get_log_file_path = None

    def checker_dirs(self):
        """Проверяет, существуют ли директории"""
        paths_to_check = []
        home_directory = path.expanduser("~")
        try:
            paths_to_check.append(path.join(home_directory, "SLCW"))
            paths_to_check.append(path.join(home_directory, "SLCW", "logs"))
            for path_to_check in paths_to_check:
                if not path.exists(path_to_check):
                    try:
                        makedirs(path_to_check, exist_ok=True)
                    except OSError as error:
                        self.message_handler_gui("Error", f"Не удалось создать директорию: {path_to_check}", error)
        except OSError as error:
            self.message_handler_gui("Error", f"Не удалось проверить директорию: {path_to_check}", error)

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
                log_file.write(f"[{datetime.now().date()} {strftime('%X')}] " + message + "\n")
                print(f"[{datetime.now().date()} {strftime('%X')}] " + message)
                log_file.close()
        except PermissionError:
            self.message_handler_gui("Error", f"Доступ к файлу {log_file_path} запрещён, пожалуйста, запустите программу от имени администратора")
        except Exception as error:
            self.message_handler_gui("Error", f"Не удалось записать в лог файл {log_file_path}", error)

    def send_log_file(self, threader, client_socket: socket.socket) -> None:
        """Отправляет лог файл на сервер"""
        global HEARTBEAT_THREAD
        global HEARTBEAT_THREAD_STOP
        threader = threader

        try:
            if client_socket is None or not isinstance(client_socket, socket.socket):
                self.log_message("Соединение с сервером не установлено при отправке лог файла")
                return
            
            client_socket.sendall("LOG_FILE".encode(self.format))

            if HEARTBEAT_THREAD is not None and HEARTBEAT_THREAD.is_alive():
                HEARTBEAT_THREAD = self.threader.stop_func_thread(HEARTBEAT_THREAD, HEARTBEAT_THREAD_STOP)

            log_file_path = self.get_log_file_path()
            
            with open(log_file_path, "rb") as log_file:
                while (bytes_read := log_file.read(self.header)):
                    client_socket.sendall(bytes_read)
                sleep(1)
                client_socket.sendall(b"END_OF_FILE")
                server_confirmation = client_socket.recv(self.header).decode(self.format)
                if server_confirmation == "Download complete":
                    client_socket.sendall("Transfer complete".encode(self.format))
                else:
                    self.log_message(f"Сервер не ответил на завершение загрузки лог файла")
        except Exception as error:
            if error == FileNotFoundError:
                self.log_message("Файл логов не найден")
                client_socket.sendall("Файл логов не найден".encode(self.format))
            else:
                self.log_message(f"[Error] Ошибка при отправке лог файла: {str(error)}")

if __name__ == "__main__":
    try:
        gui = GUI()
        gui.mainloop()
    except KeyboardInterrupt:
        gui.on_closing
    except Exception as error:
        print(f"[Error] {error}")