import customtkinter as ctk
from customtkinter import *
from CTkColorPicker import *
from CTkMenuBar import *
from miio import Yeelight
from miio.exceptions import DeviceException
from PIL import ImageColor
import threading
from functools import partial
import json
import os
import speech_recognition as sr
from speech_recognition.recognizers import google
from google.cloud import dialogflow_v2 as df
from google.protobuf.json_format import MessageToDict

# UI Colors and settings
BG_COLOR = "#343541"           # Background color for the window
FRAME_COLOR = "#40414F"        # Color for internal frames
ACCENT_COLOR = "#10A37F"        # Accent green color
TEXT_COLOR = "#ECECF1"         # Light font color
SIZE = "300x350"
CONFIG_FILE = "config.json"


class VoiceProcessor:
    """
    Processes voice commands by sending text to Dialogflow.
    """
    def __init__(self):
        self.project_id = "smartbulbproject"  # Replace with your Google Cloud Project ID
        self.credentials_path = "smartbulbproject-2955748c5ce9.json"  # Path to the service account file

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
        self.session_client = df.SessionsClient()
        self.session_id = "1-session"  # Unique session identifier

    def process_query(self, text):
        try:
            session = self.session_client.session_path(self.project_id, self.session_id)
            text_input = df.TextInput(text=text, language_code="ru-RU")
            query_input = df.QueryInput(text=text_input)
            response = self.session_client.detect_intent(request={"session": session, "query_input": query_input})
            result = MessageToDict(response._pb)

            intent = result["queryResult"]["intent"]["displayName"]
            parameters = result["queryResult"].get("parameters", {})
            confidence = result["queryResult"].get("intentDetectionConfidence", 0)

            return {"intent": intent, "parameters": parameters, "confidence": confidence}

        except Exception as e:
            print(f"Dialogflow error: {str(e)}")
            return None


class MiHomeApp:
    """
    Main application class for the smart bulb control UI.
    """
    def __init__(self, root):
        self.root = root
        self.load_config()

        self.root.title("Mi Home")
        self.root.geometry(SIZE)
        self.root.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.root.configure(fg_color=BG_COLOR)

        self.device = None
        self.connect_device()

        # Initialize voice control
        self.voice_enabled = True
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.voice_thread = threading.Thread(target=self.voice_loop, daemon=True)
        self.voice_thread.start()
        self.voice_processor = VoiceProcessor()

        self.setup_advanced_commands()

        self.timer = None

        # Create UI widgets
        self.create_widgets()
        self.update_status()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.DEVICE_IP = config.get("DEVICE_IP")
                    self.DEVICE_TOKEN = config.get("DEVICE_TOKEN")
                    self.MODEL = config.get("MODEL")
            except json.JSONDecodeError:
                print("Error reading config.json.")
        else:
            print("config.json not found.")

    def save_config(self):
        config = {
            "DEVICE_IP": self.DEVICE_IP,
            "DEVICE_TOKEN": self.DEVICE_TOKEN,
            "MODEL": self.MODEL
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("Settings saved successfully.")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def connect_device(self):
        try:
            self.device = Yeelight(ip=self.DEVICE_IP, token=self.DEVICE_TOKEN, model=self.MODEL)
            print("Device connected successfully.")
        except DeviceException as e:
            print(f"Connection error: {e}")
            self.device = None

    def create_widgets(self):
        # Menu bar with settings option
        menu = CTkTitleMenu(master=self.root, x_offset=105, title_bar_color='black')
        menu.add_cascade("⚙", command=self.open_settings, fg_color='black')

        # Header frame
        header_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR, corner_radius=10)
        header_frame.pack(pady=7, fill="x", padx=10)

        header_label = ctk.CTkLabel(
            header_frame,
            text="SMART BULB",
            text_color="lightblue",
            font=("Impact", 30)
        )
        header_label.pack(anchor="center", pady=8)

        # Power toggle button frame
        control_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR, corner_radius=10)
        control_frame.pack(pady=5, padx=10)

        self.power_btn = ctk.CTkButton(
            control_frame,
            text="ON",
            font=("Arial", 20, 'bold'),
            command=self.toggle_power,
            width=120,
            height=40,
            corner_radius=8,
            fg_color=ACCENT_COLOR,
            text_color=TEXT_COLOR
        )
        self.power_btn.pack(pady=8, padx=30)

        # Main frame for controls
        self.main_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR, corner_radius=10)
        self.main_frame.pack()

        # Brightness slider frame
        brightness_frame = ctk.CTkFrame(self.main_frame, fg_color=FRAME_COLOR, corner_radius=10)
        brightness_frame.pack(pady=5, fill="x", padx=10)

        brightness_label = ctk.CTkLabel(
            brightness_frame,
            text="Brightness:",
            font=("Arial", 20, 'bold'),
            anchor="w",
            text_color=TEXT_COLOR
        )
        brightness_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.brightness_scale = ctk.CTkSlider(
            brightness_frame,
            from_=1,
            to=100,
            number_of_steps=99,
            command=partial(self.on_change, self.set_brightness),
            progress_color=ACCENT_COLOR,
            button_color=ACCENT_COLOR
        )
        self.brightness_scale.pack(fill="x", padx=10, pady=5)

        # Color picker frame
        color_frame = ctk.CTkFrame(self.main_frame, fg_color=FRAME_COLOR, corner_radius=10)
        color_frame.pack(pady=5, padx=10, fill="x")

        color_button = ctk.CTkButton(
            color_frame,
            text="Color",
            font=("Arial", 20, 'bold'),
            command=self.choose_color,
            width=120,
            height=40,
            corner_radius=8,
            fg_color=ACCENT_COLOR,
            text_color=TEXT_COLOR
        )
        color_button.pack(side="left", padx=20, pady=10)

        self.color_patt = ctk.CTkFrame(
            color_frame,
            height=45,
            corner_radius=10,
            fg_color='white',
            border_width=3,
            border_color="#343520"
        )
        self.color_patt.pack(fill="x", padx=20, pady=10)

        # Color temperature slider frame
        temp_frame = ctk.CTkFrame(self.main_frame, fg_color=FRAME_COLOR, corner_radius=10)
        temp_frame.pack(pady=5, padx=10, fill="x")

        temp_label = ctk.CTkLabel(
            temp_frame,
            text="Temperature (K):",
            font=("Arial", 20, 'bold'),
            anchor="w",
            text_color=TEXT_COLOR
        )
        temp_label.pack(anchor="w", padx=10, pady=(5, 0))

        self.temp_scale = ctk.CTkSlider(
            temp_frame,
            from_=1700,
            to=6500,
            number_of_steps=4800,
            command=partial(self.on_change, self.set_temp),
            progress_color=ACCENT_COLOR,
            button_color=ACCENT_COLOR
        )
        self.temp_scale.pack(fill="x", padx=10, pady=5)

    def open_settings(self):
        """
        Opens a settings window to update device configuration.
        """
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("280x310")
        settings_window.resizable(False, False)
        settings_window.configure(fg_color=FRAME_COLOR)
        settings_window.lift()
        settings_window.attributes("-topmost", True)
        settings_window.grab_set()

        settings_label = ctk.CTkLabel(
            settings_window,
            text="SETTINGS",
            font=("Arial", 20, 'bold'),
            text_color=TEXT_COLOR
        )
        settings_label.pack(pady=5)

        input_frame = ctk.CTkFrame(settings_window, fg_color=FRAME_COLOR, corner_radius=10)
        input_frame.pack(padx=20, fill="both", expand=True)

        # DEVICE_IP entry
        ip_label = ctk.CTkLabel(
            input_frame,
            text="DEVICE_IP:",
            font=("Arial", 14),
            anchor="w",
            text_color=TEXT_COLOR
        )
        ip_label.pack(fill="x", padx=20, pady=(10, 0))

        self.ip_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Enter device IP",
            fg_color=BG_COLOR,
            text_color=TEXT_COLOR,
            border_color=ACCENT_COLOR,
            corner_radius=5
        )
        self.ip_entry.pack(fill="x", padx=20, pady=5)
        self.ip_entry.insert(0, self.DEVICE_IP or "")

        # DEVICE_TOKEN entry
        token_label = ctk.CTkLabel(
            input_frame,
            text="DEVICE_TOKEN:",
            font=("Arial", 14),
            anchor="w",
            text_color=TEXT_COLOR
        )
        token_label.pack(fill="x", padx=20, pady=(10, 0))

        self.token_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Enter device token",
            fg_color=BG_COLOR,
            text_color=TEXT_COLOR,
            border_color=ACCENT_COLOR,
            corner_radius=5,
        )
        self.token_entry.pack(fill="x", padx=20, pady=5)
        self.token_entry.insert(0, self.DEVICE_TOKEN or "")

        # MODEL entry
        model_label = ctk.CTkLabel(
            input_frame,
            text="MODEL:",
            font=("Arial", 14),
            anchor="w",
            text_color=TEXT_COLOR
        )
        model_label.pack(fill="x", padx=20, pady=(10, 0))

        self.model_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Enter device model",
            fg_color=BG_COLOR,
            text_color=TEXT_COLOR,
            border_color=ACCENT_COLOR,
            corner_radius=5
        )
        self.model_entry.pack(fill="x", padx=20, pady=5)
        self.model_entry.insert(0, self.MODEL or "")

        save_button = ctk.CTkButton(
            settings_window,
            text="SAVE",
            font=("Arial", 16, 'bold'),
            fg_color=ACCENT_COLOR,
            text_color=TEXT_COLOR,
            command=lambda: self.save_settings(settings_window)
        )
        save_button.pack(pady=10)

    def save_settings(self, window):
        new_ip = self.ip_entry.get().strip()
        new_token = self.token_entry.get().strip()
        new_model = self.model_entry.get().strip()

        if not new_ip or not new_token or not new_model:
            self.show_error("All fields are required.")
            return

        self.DEVICE_IP = new_ip
        self.DEVICE_TOKEN = new_token
        self.MODEL = new_model

        self.save_config()
        self.connect_device()
        self.update_status()

        window.destroy()

    def show_error(self, message):
        """
        Displays an error dialog.
        """
        error_window = ctk.CTkToplevel(self.root)
        error_window.title("Error")
        error_window.geometry("300x100")
        error_window.resizable(False, False)
        error_window.configure(fg_color=FRAME_COLOR)

        error_label = ctk.CTkLabel(
            error_window,
            text=message,
            font=("Arial", 14),
            text_color="red"
        )
        error_label.pack(pady=20, padx=20)

        ok_button = ctk.CTkButton(
            error_window,
            text="OK",
            command=error_window.destroy,
            fg_color=ACCENT_COLOR,
            text_color=TEXT_COLOR
        )
        ok_button.pack(pady=10)

    def update_status(self):
        """
        Updates UI based on device status.
        """
        if not self.device:
            self.power_btn.configure(text="ON")
            self.main_frame.forget()
            return

        try:
            status = self.device.status()
        except DeviceException as e:
            print(f"Status error: {e}")
            self.device = None
            self.power_btn.configure(text="ON")
            self.main_frame.forget()
            return

        if status.is_on:
            self.root.geometry(SIZE)
            self.power_btn.configure(text="OFF")
            self.brightness_scale.set(int(status.brightness))
            if status.color_temp is not None:
                self.temp_scale.set(int(status.color_temp))
            else:
                self.temp_scale.set(1700)
                self.color_patt.configure(fg_color=self.rgb_to_hex(status.rgb))
            self.main_frame.pack()
        else:
            self.root.geometry("300x150")
            self.power_btn.configure(text="ON")
            self.main_frame.forget()

    def toggle_power(self):
        """
        Toggles the power state of the device.
        """
        if self.device:
            try:
                if self.device.status().is_on:
                    self.device.off()
                else:
                    self.device.on()
                self.update_status()
            except DeviceException as e:
                print(f"Error: {e}")

    def on_change(self, setter_function, value):
        """
        Debounce slider value changes before applying them.
        """
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(0.5, setter_function, args=(value,))
        self.timer.start()

    def set_brightness(self, value):
        """
        Sets brightness based on slider value.
        """
        if self.device:
            try:
                self.device.set_brightness(int(float(value)))
            except DeviceException as e:
                print(f"Error: {e}")

    def set_temp(self, value):
        """
        Sets color temperature based on slider value.
        """
        if self.device:
            try:
                self.device.set_color_temp(int(float(value)))
                self.color_patt.configure(fg_color='white')
            except DeviceException as e:
                print(f"Error: {e}")

    def choose_color(self):
        """
        Opens a color picker to choose a color for the device.
        """
        pick_color = AskColor(width=300, font=("Helvetica", 16, "bold"))
        pick_color.button.configure(height=30)
        pick_color.label.pack_forget()
        pick_color.slider.pack_forget()
        pick_color.minsize(200, 200)
        color = pick_color.get()  # Returns a string in the format '#RRGGBB'
        if color and self.device:
            try:
                rgb = ImageColor.getcolor(color, "RGB")
                self.device.set_rgb(rgb)
                self.color_patt.configure(fg_color=color)
                self.temp_scale.set(1700)
            except DeviceException as e:
                print(f"Error: {e}")

    @staticmethod
    def rgb_to_hex(rgb):
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def voice_loop(self):
        """
        Runs continuous background speech recognition.
        """
        def callback(recognizer, audio):
            try:
                text = google.recognize_legacy(recognizer, audio, language="ru-RU")
                print(f"Recognized text: {text}")
                if "лампа" in text.lower():  # If "lamp" is mentioned, process the command
                    self.process_voice_command(text)
            except sr.UnknownValueError:
                pass
            except Exception as e:
                print(f"Voice callback error: {e}")

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        self.stop_listening = self.recognizer.listen_in_background(self.microphone, callback)

    def setup_advanced_commands(self):
        """
        Maps intents to advanced command methods.
        """
        self.advanced_commands = {
            'brightness.adjust': self.adjust_brightness,
            'color.set': self.set_advanced_color,
            'preset.activate': self.activate_preset,
            'temperature.set': self.advanced_set_temp,
        }

    def process_voice_command(self, text):
        """
        Processes voice commands via Dialogflow and executes the corresponding function.
        """
        try:
            response = self.voice_processor.process_query(text)
            if response:
                intent = response['intent']
                params = response['parameters']
                confidence = response['confidence']
                print(f"Dialogflow Intent: {intent}, Params: {params}, Conf: {confidence}")
                if intent in self.advanced_commands:
                    self.advanced_commands[intent](params)
                    self.root.bell()
        except Exception as e:
            print(f"Processing error: {e}")

    def adjust_brightness(self, params):
        """
        Adjusts brightness based on the provided parameters.
        """
        if not self.device:
            return
        try:
            operation = params.get('operation', 'value')
            new_value = 0
            current = self.device.status().brightness
            if operation == 'выше':
                new_value = min(current + 10, 100)
            elif operation == 'ниже':
                new_value = max(current - 10, 1)
            else:
                value = int(params.get('value', 0))
                if 1 <= value <= 100:
                    new_value = value

            self.device.set_brightness(new_value)
            self.update_status()
            print(f"Brightness set to: {new_value}")
        except DeviceException as e:
            print(f"Error: {e}")

    def russian_color_to_codes(self, color_name: str) -> dict | None:
        """
        Converts a Russian color name to its HEX and RGB codes.
        """
        color_dictionary = {
            "белый": {"hex": "#FFFFFF", "rgb": (255, 255, 255)},
            "черный": {"hex": "#000000", "rgb": (0, 0, 0)},
            "красный": {"hex": "#FF0000", "rgb": (255, 0, 0)},
            "зеленый": {"hex": "#00FF00", "rgb": (0, 255, 0)},
            "синий": {"hex": "#0000FF", "rgb": (0, 0, 255)},
            "желтый": {"hex": "#FFFF00", "rgb": (255, 255, 0)},
            "голубой": {"hex": "#00FFFF", "rgb": (0, 255, 255)},
            "фиолетовый": {"hex": "#800080", "rgb": (128, 0, 128)},
            "розовый": {"hex": "#FFC0CB", "rgb": (255, 192, 203)},
            "оранжевый": {"hex": "#FFA500", "rgb": (255, 165, 0)},
            "коричневый": {"hex": "#A52A2A", "rgb": (165, 42, 42)},
            "серый": {"hex": "#808080", "rgb": (128, 128, 128)},
        }
        return color_dictionary.get(color_name.lower().strip())

    def set_advanced_color(self, params):
        """
        Sets the device color using a provided color name.
        """
        if not self.device:
            return
        color = params.get('color')
        try:
            code = self.russian_color_to_codes(color)
            self.device.set_rgb(code['rgb'])
            self.color_patt.configure(fg_color=code['hex'])
            print(f"Color set to: {color}, RGB={code['rgb']}")
        except (ValueError, KeyError):
            print(f"Unknown color format: {color}")
        except DeviceException as e:
            print(f"Error: {e}")

    def activate_preset(self, params):
        """
        Activates a preset configuration.
        """
        if not self.device:
            return
        presets = {
            'ночь': {'brightness': 30, 'rgb': (255, 0, 0)},
            'день': {'brightness': 100, 'temp': 6500}
        }
        preset_name = params.get('preset')
        preset = presets.get(preset_name)
        if preset:
            try:
                self.device.set_brightness(preset['brightness'])
                if 'rgb' in preset:
                    self.device.set_rgb(preset['rgb'])
                else:
                    self.device.set_color_temp(preset['temp'])
                self.update_status()
            except DeviceException as e:
                print(f"Error: {e}")
        else:
            print(f"Unknown preset: {preset_name}")

    def advanced_set_temp(self, params):
        """
        Sets the color temperature using voice command parameters.
        """
        if not self.device:
            return
        try:
            temp = params.get('temp')
            self.device.set_color_temp(temp)
            self.color_patt.configure(fg_color='white')
            print(f"Temperature set to: {temp}K")
        except DeviceException as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    app_window = CTk()
    MiHomeApp(app_window)
    app_window.mainloop()
