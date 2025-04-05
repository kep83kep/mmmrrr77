from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.core.audio import SoundLoader  # Для воспроизведения звука
from kivy.uix.filechooser import FileChooserListView  # Для выбора файлов
import requests
import hmac
import hashlib
import time
import os
import json
import pickle  # Для сохранения пути к файлу

# Установка размера окна (для тестирования на ПК)
Window.size = (400, 600)


class MRRBotApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = os.getenv("MRR_API_KEY", "9ccfafdca2396a2874790b9f6202369948d5c3eb529893906329aef990019860")
        self.api_secret = os.getenv("MRR_API_SECRET",
                                    "b21e40d607c274a1be456d663a8c2dbf70fe93c1ad0e46fe309fa0f9fbcd6a90")
        self.root_uri = "https://www.miningrigrentals.com/api/v2"
        self.update_interval = 10  # Интервал обновления по умолчанию (в секундах)
        self.update_event = None  # Ссылка на событие Clock
        self.rented_rigs = set()  # Трекер арендованных ригов
        self.sound_path = self.load_sound_path()  # Загрузка пути к звуковому файлу
        self.initialized = False  # Флаг для отслеживания первой инициализации

    def build(self):
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Верхняя панель с кнопками
        top_panel = BoxLayout(size_hint_y=0.1, spacing=10)
        key_button = Button(
            text="API Keys",
            background_color=(0.8, 0.6, 0.2, 1),
            on_press=self.open_key_popup,
        )
        whoami_button = Button(
            text="Whoami",
            background_color=(0, 0.47, 0.85, 1),
            on_press=self.test_whoami,
        )
        rig_mine_button = Button(
            text="My Rigs",
            background_color=(0, 0.47, 0.85, 1),
            on_press=self.refresh_rented_rigs,
        )
        settings_button = Button(
            text="Settings",
            background_color=(0.8, 0.6, 0.2, 1),
            on_press=self.open_settings_popup,  # Теперь метод существует
        )
        sound_button = Button(
            text="Sound",
            background_color=(0.8, 0.6, 0.2, 1),
            on_press=self.open_sound_popup,
        )
        top_panel.add_widget(key_button)
        top_panel.add_widget(whoami_button)
        top_panel.add_widget(rig_mine_button)
        top_panel.add_widget(settings_button)
        top_panel.add_widget(sound_button)
        layout.add_widget(top_panel)

        # Центральное текстовое поле для вывода данных
        self.output_text = TextInput(
            readonly=True,
            size_hint_y=0.8,
            multiline=True,
            background_color=(0.12, 0.12, 0.12, 1),
            foreground_color=(1, 1, 1, 1),
        )
        layout.add_widget(self.output_text)
        return layout

    def log_message(self, message):
        """Добавляет сообщение в текстовое поле."""
        self.output_text.text += f"{message}\n"

    def open_key_popup(self, instance):
        """Открывает диалоговое окно для ввода API ключей."""
        popup_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.key_input = TextInput(hint_text="Enter API Key", multiline=False, text=self.api_key)
        self.secret_input = TextInput(hint_text="Enter Secret Key", multiline=False, text=self.api_secret)
        save_button = Button(
            text="Save Keys",
            background_color=(0, 0.47, 0.85, 1),
            on_press=self.save_keys,
        )
        popup_layout.add_widget(Label(text="API Key Settings", font_size=16))
        popup_layout.add_widget(self.key_input)
        popup_layout.add_widget(self.secret_input)
        popup_layout.add_widget(save_button)
        self.popup = Popup(
            title="Set API Keys",
            content=popup_layout,
            size_hint=(0.8, 0.6),
        )
        self.popup.open()

    def save_keys(self, instance):
        """Сохраняет введенные API ключи."""
        self.api_key = self.key_input.text.strip()
        self.api_secret = self.secret_input.text.strip()
        if self.api_key and self.api_secret:
            self.log_message("API keys saved successfully.")
        else:
            self.log_message("Error: API keys cannot be empty.")
        self.popup.dismiss()

    def open_sound_popup(self, instance):
        """Открывает диалоговое окно для выбора звукового файла."""
        popup_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.sound_input = TextInput(hint_text="Enter path to sound file", multiline=False, text=self.sound_path)
        browse_button = Button(
            text="Browse...",
            background_color=(0, 0.47, 0.85, 1),
            on_press=self.browse_sound_file,
        )
        save_button = Button(
            text="Save Path",
            background_color=(0, 0.47, 0.85, 1),
            on_press=self.save_sound_path,
        )
        popup_layout.add_widget(Label(text="Sound Settings", font_size=16))
        popup_layout.add_widget(self.sound_input)
        popup_layout.add_widget(browse_button)
        popup_layout.add_widget(save_button)
        self.sound_popup = Popup(
            title="Set Sound File",
            content=popup_layout,
            size_hint=(0.8, 0.6),
        )
        self.sound_popup.open()

    def browse_sound_file(self, instance):
        """Открывает диалоговое окно для выбора звукового файла."""
        file_chooser = FileChooserListView(filters=["*.mp3", "*.wav"])
        file_popup = Popup(
            title="Select a sound file",
            content=file_chooser,
            size_hint=(0.8, 0.8),
        )
        file_chooser.bind(on_submit=lambda _, path: self.select_sound_file(path, file_popup))
        file_popup.open()

    def select_sound_file(self, path, popup):
        """Обрабатывает выбор звукового файла."""
        if path:
            self.sound_input.text = path[0]  # Обновляем поле ввода с выбранным путем
        popup.dismiss()

    def save_sound_path(self, instance):
        """Сохраняет путь к звуковому файлу."""
        new_path = self.sound_input.text.strip()
        if os.path.isfile(new_path):  # Проверяем, существует ли файл
            self.sound_path = new_path
            self.save_sound_path_to_file()
            self.log_message(f"Sound path saved: {self.sound_path}")
        else:
            self.log_message("Error: File does not exist.")
        self.sound_popup.dismiss()

    def load_sound_path(self):
        """Загружает путь к звуковому файлу из файла конфигурации."""
        try:
            with open("sound_config.pkl", "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            return ""  # Возвращаем пустую строку, если файл не найден

    def save_sound_path_to_file(self):
        """Сохраняет путь к звуковому файлу в файл конфигурации."""
        with open("sound_config.pkl", "wb") as f:
            pickle.dump(self.sound_path, f)

    def open_settings_popup(self, instance):
        """Открывает диалоговое окно для настройки интервала обновления."""
        popup_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.interval_input = TextInput(
            hint_text="Enter update interval (seconds)", multiline=False, text=str(self.update_interval)
        )
        save_button = Button(
            text="Save Interval",
            background_color=(0, 0.47, 0.85, 1),
            on_press=self.save_interval,
        )
        popup_layout.add_widget(Label(text="Update Interval Settings", font_size=16))
        popup_layout.add_widget(self.interval_input)
        popup_layout.add_widget(save_button)
        self.settings_popup = Popup(
            title="Settings",
            content=popup_layout,
            size_hint=(0.8, 0.6),
        )
        self.settings_popup.open()

    def save_interval(self, instance):
        """Сохраняет интервал обновления и перезапускает таймер."""
        try:
            new_interval = int(self.interval_input.text.strip())
            if new_interval > 0:
                self.update_interval = new_interval
                self.log_message(f"Update interval set to {self.update_interval} seconds.")
                self.restart_auto_update()
            else:
                self.log_message("Error: Interval must be greater than 0.")
        except ValueError:
            self.log_message("Error: Please enter a valid number.")
        self.settings_popup.dismiss()

    def restart_auto_update(self):
        """Перезапускает автоматическое обновление с новым интервалом."""
        if self.update_event:
            self.update_event.cancel()
        self.update_event = Clock.schedule_interval(self.auto_refresh_rented_rigs, self.update_interval)

    def auto_refresh_rented_rigs(self, dt):
        """Автоматически обновляет данные арендованных ригов."""
        self.clear_log()  # Очищаем лог перед обновлением
        self.refresh_rented_rigs(None)

    def clear_log(self):
        """Очищает текстовое поле лога."""
        self.output_text.text = ""

    def refresh_rented_rigs(self, instance):
        """Обновляет список арендованных ригов."""
        result = self.make_request("GET", "/rig/mine")
        if not result or "data" not in result:
            self.log_message("No rigs found or invalid response.")
            return
        current_rented_rigs = set()
        for rig in result["data"]:
            name = rig.get("name", "Unknown Rig")
            if rig.get("status", {}).get("rented", False):
                current_rented_rigs.add(name)
        # Если это первая инициализация, просто сохраняем текущее состояние
        if not self.initialized:
            self.rented_rigs = current_rented_rigs
            self.initialized = True
            self.log_message("Initial rented rigs loaded.")
            # Воспроизводим звук для каждого арендованного рига при запуске
            if current_rented_rigs and self.sound_path:
                for _ in current_rented_rigs:
                    self.play_sound()
            return
        # Определяем новые арендованные риги
        new_rented_rigs = current_rented_rigs - self.rented_rigs
        if new_rented_rigs and self.sound_path:
            for _ in new_rented_rigs:
                self.play_sound()
        # Обновляем трекер арендованных ригов
        self.rented_rigs = current_rented_rigs
        # Отображаем список арендованных ригов
        self.log_message("\n".join(current_rented_rigs) if current_rented_rigs else "No rented rigs found.")

    def play_sound(self):
        """Воспроизводит звуковой файл с использованием Kivy SoundLoader."""
        if self.sound_path and os.path.isfile(self.sound_path):
            try:
                sound = SoundLoader.load(self.sound_path)
                if sound:
                    sound.play()
            except Exception as e:
                self.log_message(f"Error playing sound: {str(e)}")
        else:
            self.log_message("Error: Sound file does not exist.")

    def sign_request(self, endpoint, nonce):
        """Подписывает запрос с использованием HMAC-SHA1."""
        sign_string = self.api_key + nonce + endpoint
        return hmac.new(self.api_secret.encode(), sign_string.encode(), hashlib.sha1).hexdigest()

    def make_request(self, method, endpoint, params=None):
        """Выполняет HTTP-запрос к API."""
        if not self.api_key or not self.api_secret:
            self.log_message("Error: API keys are not set.")
            return None
        url = self.root_uri + endpoint
        nonce = str(int(time.time() * 1000))
        signature = self.sign_request(endpoint, nonce)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "x-api-sign": signature,
            "x-api-nonce": nonce,
        }
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params)
            else:
                raise ValueError("Unsupported HTTP method")
            if response.status_code != 200:
                self.log_message(f"Error: {response.status_code} - {response.text}")
                return None
            return response.json()
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            return None

    def test_whoami(self, instance):
        """Выполняет запрос GET /whoami и отображает результат."""
        result = self.make_request("GET", "/whoami")
        if result:
            self.log_message(json.dumps(result, indent=2))

    def on_start(self):
        """Запускает автоматическое обновление при старте программы."""
        self.update_event = Clock.schedule_interval(self.auto_refresh_rented_rigs, self.update_interval)


if __name__ == "__main__":
    MRRBotApp().run()
