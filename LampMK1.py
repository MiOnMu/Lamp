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

#Color Palette
BG_COLOR = "#343541"      # Background color
FRAME_COLOR = "#40414F"   # Frame background color
ACCENT_COLOR = "#10A37F"
TEXT_COLOR = "#ECECF1"

SIZE = "300x350"
CONFIG_FILE = "config.json"

class MiHomeApp:
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
        self.timer = None

        self.create_widgets()
        self.update_status()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
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
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            print("Settings saved successfully.")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def connect_device(self):
        try:
            self.device = Yeelight(
                ip=self.DEVICE_IP,
                token=self.DEVICE_TOKEN,
                model=self.MODEL
            )
            print("Device connected successfully.")
        except DeviceException as e:
            print(f"Connection error: {e}")
            self.device = None

    def create_widgets(self):
        # Menu bar with settings and reload buttons
        menu = CTkTitleMenu(master=self.root, x_offset=105, title_bar_color='black')
        menu.add_cascade("⚙", command=self.open_settings, fg_color='black')
        menu.add_cascade("⟳", command=self.connect_device, fg_color='black')

        # Header
        header_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR, corner_radius=10)
        header_frame.pack(pady=7, fill="x", padx=10)

        header_label = ctk.CTkLabel(header_frame, text="SMART BULB", text_color="lightblue", font=("Impact", 30))
        header_label.pack(anchor="center", pady=8)

        # Power button
        control_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR, corner_radius=10)
        control_frame.pack(pady=5, padx=10)

        self.power_btn = ctk.CTkButton(
            control_frame, text="ON", font=("Arial", 20, 'bold'),
            command=self.toggle_power, width=120, height=40, corner_radius=8,
            fg_color=ACCENT_COLOR, text_color=TEXT_COLOR
        )
        self.power_btn.pack(pady=8, padx=30)

        # Main frame for controls
        self.main_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR, corner_radius=10)
        self.main_frame.pack()

        # Brightness slider
        brightness_frame = ctk.CTkFrame(self.main_frame, fg_color=FRAME_COLOR, corner_radius=10)
        brightness_frame.pack(pady=5, fill="x", padx=10)

        brightness_label = ctk.CTkLabel(
            brightness_frame, text="Brightness:", font=("Arial", 20, 'bold'),
            anchor="w", text_color=TEXT_COLOR
        )
        brightness_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.brightness_scale = ctk.CTkSlider(
            brightness_frame, from_=1, to=100, number_of_steps=99,
            command=partial(self.on_change, self.set_brightness),
            progress_color=ACCENT_COLOR, button_color=ACCENT_COLOR
        )
        self.brightness_scale.pack(fill="x", padx=10, pady=5)

    def toggle_power(self):
        if self.device:
            try:
                if self.device.status().is_on:
                    self.device.off()
                else:
                    self.device.on()
                self.update_status()
            except DeviceException as e:
                print(f"Error: {e}")

    def update_status(self):
        if not self.device:
            self.power_btn.configure(text="ON")
            self.main_frame.forget()
            return

        try:
            status = self.device.status()
        except DeviceException as e:
            print(f"Error getting status: {e}")
            self.device = None
            self.power_btn.configure(text="ON")
            self.main_frame.forget()
            return

        if status.is_on:
            self.root.geometry(SIZE)
            self.power_btn.configure(text="OFF")
            self.brightness_scale.set(int(status.brightness))
            self.main_frame.pack()
        else:
            self.root.geometry("300x150")
            self.power_btn.configure(text="ON")
            self.main_frame.forget()

    def on_change(self, setter_function, value):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(0.5, setter_function, args=(value,))
        self.timer.start()

    def set_brightness(self, value):
        if self.device:
            try:
                self.device.set_brightness(int(float(value)))
            except DeviceException as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    app_window = CTk()
    MiHomeApp(app_window)
    app_window.mainloop()
