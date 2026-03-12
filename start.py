from tkinter import *
from tkinter import ttk
import sys
import os
import subprocess
import uuid


def ensure_project_venv():
    """Relaunch with .venv interpreter when launched from a different Python."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base_dir, ".venv", "Scripts", "python.exe")

    if not os.path.exists(venv_python):
        return

    current = os.path.normcase(os.path.abspath(sys.executable))
    expected = os.path.normcase(os.path.abspath(venv_python))
    already_bootstrapped = os.environ.get("CFIS_VENV_BOOTSTRAPPED") == "1"

    if current != expected and not already_bootstrapped:
        env = os.environ.copy()
        env["CFIS_VENV_BOOTSTRAPPED"] = "1"
        subprocess.Popen([venv_python, os.path.abspath(__file__)], env=env)
        sys.exit(0)


class ModuleLoadingOverlay:
    """Animated loading popup shown while a module process starts."""

    def __init__(self, parent, module_name, messages=None):
        self.parent = parent
        self.module_name = module_name
        self.start_ms = 0
        self.spinner_frames = ["|", "/", "-", "\\"]
        self.spinner_index = 0
        self._messages = messages if messages else [f"Loading {module_name}..."]
        self._msg_index = 0

        self.top = Toplevel(parent)
        self.top.title("Loading")
        self.top.resizable(False, False)
        self.top.configure(bg="#050B1A")
        self.top.attributes("-topmost", True)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.attributes("-alpha", 0.0)

        width = 420
        height = 210
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        pos_x = (screen_w - width) // 2
        pos_y = (screen_h - height) // 2
        self.top.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

        container = Frame(
            self.top,
            bg="#0A152A",
            highlightthickness=1,
            highlightbackground="#1E3A8A",
        )
        container.place(x=12, y=12, width=396, height=186)

        Label(
            container,
            text="INITIALIZING SYSTEM",
            bg="#0A152A",
            fg="#27B1FF",
            font=("Segoe UI Semibold", 12),
        ).place(x=18, y=14)

        self.message_label = Label(
            container,
            text=self._messages[0] if self._messages else f"Loading {module_name}...",
            bg="#0A152A",
            fg="#E6F1FF",
            font=("Segoe UI", 11),
            anchor="w",
        )
        self.message_label.place(x=18, y=46)

        self.spinner_label = Label(
            container,
            text="|",
            bg="#0A152A",
            fg="#86A4D9",
            font=("Consolas", 14),
            anchor="w",
        )
        self.spinner_label.place(x=18, y=74)

        style = ttk.Style(self.top)
        style.theme_use("clam")
        style.configure(
            "Launch.Horizontal.TProgressbar",
            troughcolor="#071226",
            bordercolor="#1E3A8A",
            background="#27B1FF",
            lightcolor="#27B1FF",
            darkcolor="#1A6CB0",
        )

        self.progress = ttk.Progressbar(
            container,
            orient=HORIZONTAL,
            length=356,
            mode="indeterminate",
            style="Launch.Horizontal.TProgressbar",
        )
        self.progress.place(x=18, y=122)
        self.progress.start(10)

        self._fade_in()
        self._animate_spinner()
        self._animate_messages()

    def _animate_messages(self):
        if not self.top.winfo_exists():
            return
        # Advance to next message; stay on the last one once exhausted
        next_index = self._msg_index + 1
        if next_index < len(self._messages):
            self._msg_index = next_index
            self.message_label.configure(text=self._messages[self._msg_index])
            self.top.after(1200, self._animate_messages)

    def watch_process(self, process, ready_file, on_finished):
        self._poll(process, ready_file, on_finished, wait_ticks=0)

    def _poll(self, process, ready_file, on_finished, wait_ticks):
        if os.path.exists(ready_file):
            try:
                os.remove(ready_file)
            except OSError:
                pass
            self.close()
            on_finished()
            return

        if process.poll() is not None and wait_ticks > 10:
            self.close()
            on_finished()
            return

        self.top.after(120, lambda: self._poll(process, ready_file, on_finished, wait_ticks + 1))

    def _fade_in(self):
        try:
            alpha = float(self.top.attributes("-alpha"))
        except Exception:
            return
        if alpha < 1.0:
            self.top.attributes("-alpha", min(alpha + 0.08, 1.0))
            self.top.after(16, self._fade_in)

    def _animate_spinner(self):
        self.spinner_label.configure(text=self.spinner_frames[self.spinner_index])
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
        self.top.after(90, self._animate_spinner)

    def close(self):
        try:
            self.progress.stop()
        except Exception:
            pass
        try:
            self.top.grab_release()
        except Exception:
            pass
        if self.top.winfo_exists():
            self.top.destroy()


def launch_script(script_name, current_window=None, module_name="Module", messages=None):
    if current_window is None:
        subprocess.Popen([sys.executable, script_name])
        return

    token = uuid.uuid4().hex
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    ready_file = os.path.join(temp_dir, f"launch_ready_{token}.flag")

    env = os.environ.copy()
    env["CFIS_READY_FILE"] = ready_file

    loader = ModuleLoadingOverlay(current_window, module_name, messages=messages)
    process = subprocess.Popen([sys.executable, script_name], env=env)
    loader.watch_process(process, ready_file, on_finished=lambda: current_window.destroy())


def register(current_window=None):
    launch_script(
        "registerGUI.py",
        current_window,
        module_name="Registration Module",
        messages=[
            "Initializing system...",
            "Loading face recognition model...",
            "Preparing registration module...",
        ],
    )


def video_surveillance(current_window=None):
    launch_script(
        "surveillance.py",
        current_window,
        module_name="Video Surveillance",
        messages=[
            "Initializing system...",
            "Starting camera interface...",
            "Preparing surveillance module...",
        ],
    )


def detect_criminal(current_window=None):
    launch_script(
        "detect.py",
        current_window,
        module_name="Photo Match",
        messages=[
            "Initializing system...",
            "Loading face recognition model...",
            "Preparing photo match module...",
        ],
    )


class AnimatedDashboard:
    """Modernized CFIS dashboard with dark theme and startup/button animations."""

    def __init__(self):
        self.root = Tk()
        self.root.title("Criminal Registration System")
        self.root.geometry("800x500")
        self.root.minsize(800, 500)
        self.root.maxsize(800, 500)
        self.root.configure(bg="#050B1A")
        self._center_window(800, 500)

        # Fade-in starts from transparent to make startup feel smoother.
        self.root.attributes("-alpha", 0.0)

        self.colors = {
            "bg_top": "#030814",
            "bg_bottom": "#0B1D3A",
            "nav": "#081224",
            "panel": "#0A152A",
            "panel_border": "#1E3A8A",
            "text": "#E6F1FF",
            "muted": "#86A4D9",
            "btn": "#0A2A5A",
            "btn_hover": "#0E4D9C",
            "btn_pressed": "#123C73",
            "accent": "#27B1FF",
        }

        self.bg_canvas = Canvas(self.root, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_background)

        self._build_header()
        self._build_content_panel()

        self._fade_in_window()
        self._slide_panel_up()

    def _build_header(self):
        self.header = Frame(self.root, bg=self.colors["nav"], height=62)
        self.header.place(x=0, y=0, relwidth=1)

        Label(
            self.header,
            text="CRIMINAL REGISTRATION SYSTEM",
            bg=self.colors["nav"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 12),
        ).pack(side=LEFT, padx=18, pady=16)

        Label(
            self.header,
            text="SECURITY DASHBOARD",
            bg=self.colors["nav"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(side=RIGHT, padx=18, pady=18)

    def _build_content_panel(self):
        self.panel = Frame(
            self.root,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )

        # Panel starts slightly lower and slides upward on startup.
        self.panel_target_y = 0.56
        self.panel_current_y = 0.70
        self.panel.place(relx=0.5, rely=self.panel_current_y, anchor=CENTER, width=560, height=320)

        Label(
            self.panel,
            text="Criminal Registration System",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 24),
        ).pack(pady=(28, 10))

        Label(
            self.panel,
            text="Intelligent recognition and surveillance command center",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 11),
        ).pack(pady=(0, 18))

        self._create_action_button("Register Criminal", lambda: register(self.root)).pack(pady=7)
        self._create_action_button("Photo Match", lambda: detect_criminal(self.root)).pack(pady=7)
        self._create_action_button("Video Surveillance", lambda: video_surveillance(self.root)).pack(pady=7)

    def _create_action_button(self, text, command):
        button = Button(
            self.panel,
            text=text,
            command=command,
            width=30,
            height=1,
            relief=FLAT,
            bd=0,
            bg=self.colors["btn"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            cursor="hand2",
            font=("Segoe UI Semibold", 12),
            padx=16,
            pady=8,
        )

        # Hover glow and slight scaling with font/padding changes.
        button.bind("<Enter>", lambda event, b=button: self._on_hover_in(b))
        button.bind("<Leave>", lambda event, b=button: self._on_hover_out(b))
        button.bind("<ButtonPress-1>", lambda event, b=button: self._on_press(b))
        button.bind("<ButtonRelease-1>", lambda event, b=button: self._on_release(b))
        return button

    def _on_hover_in(self, button):
        button.configure(
            bg=self.colors["btn_hover"],
            font=("Segoe UI Semibold", 13),
            padx=18,
            pady=9,
            highlightthickness=1,
            highlightbackground=self.colors["accent"],
        )

    def _on_hover_out(self, button):
        button.configure(
            bg=self.colors["btn"],
            font=("Segoe UI Semibold", 12),
            padx=16,
            pady=8,
            highlightthickness=0,
        )

    def _on_press(self, button):
        button.configure(bg=self.colors["btn_pressed"], font=("Segoe UI Semibold", 11), padx=14, pady=7)

    def _on_release(self, button):
        button.configure(bg=self.colors["btn_hover"], font=("Segoe UI Semibold", 13), padx=18, pady=9)

    def _fade_in_window(self):
        alpha = self.root.attributes("-alpha")
        if alpha < 1.0:
            self.root.attributes("-alpha", min(alpha + 0.05, 1.0))
            self.root.after(22, self._fade_in_window)

    def _slide_panel_up(self):
        if self.panel_current_y > self.panel_target_y:
            self.panel_current_y -= 0.015
            self.panel.place_configure(rely=self.panel_current_y)
            self.root.after(18, self._slide_panel_up)
        else:
            self.panel.place_configure(rely=self.panel_target_y)

    def _draw_background(self, event):
        self.bg_canvas.delete("all")
        width = max(event.width, 1)
        height = max(event.height, 1)

        # Gradient background to mimic a cyber-security interface.
        r1, g1, b1 = self._hex_to_rgb(self.colors["bg_top"])
        r2, g2, b2 = self._hex_to_rgb(self.colors["bg_bottom"])

        for y in range(height):
            ratio = y / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.bg_canvas.create_line(0, y, width, y, fill=color)

        # Subtle grid and scan lines for futuristic dashboard mood.
        for x in range(0, width, 40):
            self.bg_canvas.create_line(x, 62, x, height, fill="#0D2A52")
        for y in range(62, height, 34):
            self.bg_canvas.create_line(0, y, width, y, fill="#0A2344")

        self.bg_canvas.create_rectangle(0, 61, width, 62, fill="#1A4A8A", outline="")

    def _center_window(self, width, height):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        pos_x = (screen_width - width) // 2
        pos_y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    @staticmethod
    def _hex_to_rgb(value):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ensure_project_venv()
    app = AnimatedDashboard()
    app.run()
