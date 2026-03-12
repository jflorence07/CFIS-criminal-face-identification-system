from tkinter import *
from tkinter import filedialog, ttk
from PIL import ImageTk, Image, ImageOps
import sqlite3
import shutil
import os
import re
import sys
import subprocess
import threading


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


ensure_project_venv()

import face_recognition as fr
import numpy as np

RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS


def notify_launcher_ready(root):
    ready_file = os.environ.get("CFIS_READY_FILE")
    if not ready_file:
        return

    def _write_when_viewable():
        if root.winfo_viewable():
            try:
                with open(ready_file, "w", encoding="ascii") as handle:
                    handle.write("ready")
            except OSError:
                pass
            return
        root.after(120, _write_when_viewable)

    root.after(120, _write_when_viewable)


class RegisterDashboard:
    """Modern registration UI for adding criminal profiles with image preview."""

    def __init__(self):
        self.root = Tk()
        self.root.title("Criminal Registration System - Register Criminal")
        self.root.geometry("1280x720")
        self.root.minsize(1100, 680)
        self.root.state("zoomed")
        self.root.configure(bg="#040B1A")
        self.root.attributes("-alpha", 0.0)

        self.colors = {
            "bg": "#040B1A",
            "header": "#081224",
            "panel": "#0B152A",
            "panel_border": "#1C3D76",
            "text": "#E6F1FF",
            "muted": "#89A8D8",
            "accent": "#2DB3FF",
            "field": "#0A1D3A",
            "field_border": "#295DA3",
            "btn": "#103A76",
            "btn_hover": "#1A58A8",
            "btn_pressed": "#0D2C58",
            "nav_btn": "#0D1C35",
            "nav_btn_hover": "#16335E",
            "nav_btn_pressed": "#102746",
            "nav_btn_border": "#2E7EDC",
        }

        self.fullname = StringVar()
        self.fathername = StringVar()
        self.mothername = StringVar()
        self.bodymark = StringVar()
        self.nationality = StringVar()
        self.crime = StringVar()
        self.gen = IntVar()
        self.rel = StringVar(value="Select Religion")
        self.blood = StringVar(value="Select Blood Group")
        self.selected_file = ""
        self.preview_photo = None
        self.crime_entry = None
        self.crime_suggestion_box = None
        self.crime_suggestion_y = 0
        self.crime_options = self._crime_catalog()
        self.crime_options_lookup = {item.lower(): item for item in self.crime_options}
        
        # Initialize face detection for duplicate checking
        self.known_encodings = []
        self.known_face_ids = []
        self._ensure_violations_table()
        self._ensure_aliases_table()
        self._seed_violations_from_people()
        self._load_known_faces()

        self.bg_canvas = Canvas(self.root, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_background)

        self._build_header()
        self._build_panels()
        self._fade_in_window()
        self._slide_in_panel()
        notify_launcher_ready(self.root)

    def _build_header(self):
        self.header = Frame(self.root, bg=self.colors["header"], height=64)
        self.header.place(x=0, y=0, relwidth=1)

        self._create_nav_button(self.header, "<  Back to Menu", self.go_back).pack(side=LEFT, padx=(18, 10), pady=14)

        Label(
            self.header,
            text="CRIMINAL REGISTRATION SYSTEM",
            bg=self.colors["header"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 13),
        ).pack(side=LEFT, padx=8, pady=18)

        Label(
            self.header,
            text="Add and verify criminal identity records",
            bg=self.colors["header"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(side=RIGHT, padx=20, pady=22)

    def _build_panels(self):
        self.form_panel = Frame(
            self.root,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        self.preview_panel = Frame(
            self.root,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )

        self.form_target_x = 0.35
        self.preview_target_x = 0.76
        self.form_x = 0.30
        self.preview_x = 0.81

        self.form_panel.place(relx=self.form_x, rely=0.55, anchor=CENTER, width=650, height=590)
        self.preview_panel.place(relx=self.preview_x, rely=0.55, anchor=CENTER, width=430, height=590)

        Label(
            self.form_panel,
            text="Criminal Registration System",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 22),
        ).place(x=24, y=18)

        Label(
            self.form_panel,
            text="Registration Form",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 11),
        ).place(x=26, y=54)

        y = 100
        self._field("Name *", self.fullname, y)
        y += 48
        self._field("Father Name", self.fathername, y)
        y += 48
        self._field("Mother Name", self.mothername, y)
        y += 48

        Label(self.form_panel, text="Gender *", bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI", 11)).place(x=28, y=y + 3)
        self._radio("Male", 1, 190, y)
        self._radio("Female", 2, 280, y)
        y += 48

        self._dropdown("Religion *", self.rel, ["Hindu", "Muslim", "Buddhist", "Christian", "Sikh", "Jain", "Others"], y)
        y += 48
        self._dropdown("Blood Group", self.blood, ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Not known"], y)
        y += 48

        self._field("Body Mark", self.bodymark, y)
        y += 48
        self._field("Nationality", self.nationality, y)
        y += 48
        self._crime_search_field("Crime convicted *", self.crime, y)
        y += 56

        self._action_button("Select Face Image *", self.open_file, 185, y)
        self._action_button("Register Criminal", self.ask_register, 375, y)

        Label(
            self.preview_panel,
            text="Face Preview",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 18),
        ).place(x=24, y=18)

        self.preview_box = Label(
            self.preview_panel,
            bg="#061124",
            fg=self.colors["muted"],
            text="No image selected",
            font=("Segoe UI", 12),
            relief=FLAT,
            anchor=CENTER,
        )
        self.preview_box.place(x=22, y=58, width=380, height=450)

        self.file_label = Label(
            self.preview_panel,
            text="",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            justify=LEFT,
            wraplength=380,
        )
        self.file_label.place(x=24, y=520)

    def _entry_style(self, entry):
        entry.configure(
            bg=self.colors["field"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief=FLAT,
            highlightthickness=1,
            highlightbackground=self.colors["field_border"],
            highlightcolor=self.colors["accent"],
            font=("Segoe UI", 10),
        )

    def _field(self, label, variable, y):
        Label(self.form_panel, text=label, bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI", 11)).place(x=28, y=y + 3)
        entry = Entry(self.form_panel, textvariable=variable, width=48)
        self._entry_style(entry)
        entry.place(x=190, y=y, height=30)

    def _crime_search_field(self, label, variable, y):
        Label(self.form_panel, text=label, bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI", 11)).place(x=28, y=y + 3)

        self.crime_entry = Entry(self.form_panel, textvariable=variable, width=48)
        self._entry_style(self.crime_entry)
        self.crime_entry.place(x=190, y=y, height=30)
        self.crime_suggestion_y = y + 31
        self.crime_entry.bind("<KeyRelease>", self._filter_crime_options)
        self.crime_entry.bind("<Down>", self._focus_crime_suggestions)
        self.crime_entry.bind("<FocusOut>", lambda _event: self.root.after(120, self._hide_crime_suggestions))

        self.crime_suggestion_box = Listbox(
            self.form_panel,
            bg=self.colors["field"],
            fg=self.colors["text"],
            selectbackground=self.colors["btn_hover"],
            selectforeground=self.colors["text"],
            highlightthickness=1,
            highlightbackground=self.colors["field_border"],
            relief=FLAT,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.crime_suggestion_box.bind("<ButtonRelease-1>", self._select_crime_from_suggestions)
        self.crime_suggestion_box.bind("<Return>", self._select_crime_from_suggestions)
        self.crime_suggestion_box.bind("<Escape>", lambda _event: self._hide_crime_suggestions())

    def _filter_crime_options(self, event=None):
        if self.crime_entry is None or self.crime_suggestion_box is None:
            return

        query = self.crime.get().strip().lower()
        if not query:
            self._hide_crime_suggestions()
            return
        else:
            filtered = [item for item in self.crime_options if item.lower().startswith(query)]

        if not filtered:
            self._hide_crime_suggestions()
            return

        self._show_crime_suggestions(filtered)

    def _show_crime_suggestions(self, options):
        self.crime_suggestion_box.delete(0, END)
        for item in options[:8]:
            self.crime_suggestion_box.insert(END, item)

        list_height = min(len(options), 8)
        box_height = (list_height * 24) + 6

        # Prefer showing suggestions below the field, but move above if buttons would overlap.
        below_y = self.crime_suggestion_y
        above_y = self.crime_suggestion_y - box_height - 31

        if below_y + box_height > 560:
            place_y = max(100, above_y)
        else:
            place_y = below_y

        self.crime_suggestion_box.place(x=190, y=place_y, width=386, height=box_height)
        self.crime_suggestion_box.lift()

    def _hide_crime_suggestions(self):
        if self.crime_suggestion_box is not None:
            self.crime_suggestion_box.place_forget()

    def _focus_crime_suggestions(self, event=None):
        if self.crime_suggestion_box is None:
            return "break"
        if self.crime_suggestion_box.size() == 0:
            return "break"
        self.crime_suggestion_box.focus_set()
        self.crime_suggestion_box.selection_clear(0, END)
        self.crime_suggestion_box.selection_set(0)
        self.crime_suggestion_box.activate(0)
        return "break"

    def _select_crime_from_suggestions(self, event=None):
        if self.crime_suggestion_box is None:
            return "break"

        selected = self.crime_suggestion_box.curselection()
        if not selected:
            return "break"

        value = self.crime_suggestion_box.get(selected[0])
        self.crime.set(value)
        self._hide_crime_suggestions()
        if self.crime_entry is not None:
            self.crime_entry.focus_set()
            self.crime_entry.icursor(END)
        return "break"

    def _canonical_crime(self, value):
        canonical = self.crime_options_lookup.get(str(value).strip().lower())
        return canonical.lower() if canonical else None

    @staticmethod
    def _crime_catalog():
        return [
            "Arson",
            "Assault",
            "Attempt to Murder",
            "Blackmail",
            "Bribery",
            "Burglary",
            "Car Theft",
            "Child Abuse",
            "Cyber Crime",
            "Cyber Fraud",
            "Domestic Violence",
            "Drug Possession",
            "Drug Trafficking",
            "Extortion",
            "Forgery",
            "Fraud",
            "Hit and Run",
            "Homicide",
            "Human Trafficking",
            "Identity Theft",
            "Illegal Possession of Weapon",
            "Kidnapping",
            "Looting",
            "Manslaughter",
            "Money Laundering",
            "Murder",
            "Organized Crime",
            "Public Disorder",
            "Rape",
            "Reckless Driving",
            "Robbery",
            "Sexual Harassment",
            "Shoplifting",
            "Smuggling",
            "Stalking",
            "Tax Evasion",
            "Terrorism",
            "Theft",
            "Trespassing",
            "Vandalism",
            "Vehicle Hijacking",
            "Weapons Trafficking",
        ]

    def _radio(self, text, value, x, y):
        Radiobutton(
            self.form_panel,
            text=text,
            variable=self.gen,
            value=value,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            selectcolor=self.colors["field"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            font=("Segoe UI", 10),
            cursor="hand2",
        ).place(x=x, y=y)

    def _dropdown(self, label, variable, values, y):
        Label(self.form_panel, text=label, bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI", 11)).place(x=28, y=y + 3)
        menu = OptionMenu(self.form_panel, variable, *values)
        menu.configure(
            width=42,
            bg=self.colors["field"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            highlightthickness=1,
            highlightbackground=self.colors["field_border"],
            relief=FLAT,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        menu["menu"].configure(
            bg=self.colors["field"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            font=("Segoe UI", 10),
        )
        menu.place(x=190, y=y, height=30)

    def _action_button(self, text, command, x, y):
        btn = Button(
            self.form_panel,
            text=text,
            command=command,
            width=20,
            bg=self.colors["btn"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            padx=12,
            pady=8,
        )
        btn.place(x=x, y=y)
        btn.bind("<Enter>", lambda event, b=btn: self._button_hover_in(b))
        btn.bind("<Leave>", lambda event, b=btn: self._button_hover_out(b))
        btn.bind("<ButtonPress-1>", lambda event, b=btn: self._button_press(b))
        btn.bind("<ButtonRelease-1>", lambda event, b=btn: self._button_release(b))

    def _create_nav_button(self, parent, text, command):
        button = Button(
            parent,
            text=text,
            command=command,
            bg=self.colors["nav_btn"],
            fg=self.colors["text"],
            activebackground=self.colors["nav_btn_hover"],
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=7,
            highlightthickness=1,
            highlightbackground=self.colors["nav_btn_border"],
            highlightcolor=self.colors["accent"],
        )
        button.bind("<Enter>", lambda event, b=button: self._nav_hover_in(b))
        button.bind("<Leave>", lambda event, b=button: self._nav_hover_out(b))
        button.bind("<ButtonPress-1>", lambda event, b=button: self._nav_press(b))
        button.bind("<ButtonRelease-1>", lambda event, b=button: self._nav_hover_in(b))
        return button

    def _button_hover_in(self, button):
        button.configure(bg=self.colors["btn_hover"], font=("Segoe UI Semibold", 11), padx=14, pady=9)

    def _button_hover_out(self, button):
        button.configure(bg=self.colors["btn"], font=("Segoe UI Semibold", 10), padx=12, pady=8)

    def _button_press(self, button):
        button.configure(bg=self.colors["btn_pressed"], font=("Segoe UI Semibold", 10), padx=10, pady=7)

    def _button_release(self, button):
        button.configure(bg=self.colors["btn_hover"], font=("Segoe UI Semibold", 11), padx=14, pady=9)

    def _nav_hover_in(self, button):
        button.configure(bg=self.colors["nav_btn_hover"], padx=16)

    def _nav_hover_out(self, button):
        button.configure(bg=self.colors["nav_btn"], padx=14)

    def _nav_press(self, button):
        button.configure(bg=self.colors["nav_btn_pressed"], padx=13)

    def open_file(self):
        selected = filedialog.askopenfilename(
            title="Select face image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")],
        )
        if not selected:
            return

        os.makedirs("temp", exist_ok=True)
        shutil.copy(selected, "temp/1.png")

        # Validate that at least one face is detectable in the image
        try:
            test_img = fr.load_image_file("temp/1.png")
            face_locations = fr.face_locations(test_img)
        except Exception:
            face_locations = []

        if not face_locations:
            os.remove("temp/1.png")
            self.selected_file = ""
            self.file_label.configure(text="")
            self.preview_photo = None
            self.preview_box.configure(image="", text="No face detected")
            self._show_notification(
                title="No Face Detected",
                message="No face was found in the selected image.\n\nPlease select a clear photo showing a human face.",
                kind="warning",
            )
            return

        self.selected_file = selected
        self.file_label.configure(text=selected)

        image = Image.open("temp/1.png")
        image = ImageOps.contain(image, (380, 450), RESAMPLE)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_box.configure(image=self.preview_photo, text="")

    def ask_register(self):
        proceed = self._show_notification(
            title="CFIS Confirmation",
            message="Mandatory fields: Name, Gender, Religion, Crime and Face Image.\n\nProceed with registration?",
            kind="confirm",
        )
        if not proceed:
            return

        self._show_loading_screen()
        self._register_result = None

        def _worker():
            self._register_result = self.database_enter()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        self.root.after(100, lambda: self._poll_register(t))

    def _poll_register(self, thread):
        if thread.is_alive():
            self.root.after(100, lambda: self._poll_register(thread))
            return

        success, payload = self._register_result
        self._hide_loading_screen()

        # Handle duplicate face detection
        if success == 2:
            self._show_duplicate_criminal_modal(
                existing_id=payload["id"],
                existing_name=payload["name"],
                existing_crime=payload["crime"],
                new_violation=payload["new_violation"],
                matches=payload.get("matches", []),
            )
        elif success == 1:
            self._show_notification(
                title="Success",
                message="Criminal registered successfully. Returning to the main menu.",
                kind="info",
            )
            self.go_back()
        else:
            self._show_notification(
                title="Validation Warning",
                message=payload,
                kind="warning",
            )

    def _show_loading_screen(self):
        self._loading_modal = Toplevel(self.root)
        self._loading_modal.transient(self.root)
        self._loading_modal.grab_set()
        self._loading_modal.resizable(False, False)
        self._loading_modal.overrideredirect(True)
        self._loading_modal.configure(bg=self.colors["panel"])

        width, height = 380, 210
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        self._loading_modal.geometry(f"{width}x{height}+{x}+{y}")

        frame = Frame(
            self._loading_modal,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        frame.place(x=0, y=0, width=width, height=height)

        Label(
            frame,
            text="REGISTERING CRIMINAL",
            bg=self.colors["panel"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 13),
        ).place(relx=0.5, y=26, anchor=CENTER)

        # Step message label that cycles through stages
        self._loading_step_var = StringVar(value="Validating form data...")
        self._loading_step_label = Label(
            frame,
            textvariable=self._loading_step_var,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Segoe UI", 10),
        )
        self._loading_step_label.place(relx=0.5, y=62, anchor=CENTER)

        # Indeterminate progress bar
        style = ttk.Style(self._loading_modal)
        style.theme_use("clam")
        style.configure(
            "Reg.Horizontal.TProgressbar",
            troughcolor=self.colors["field"],
            bordercolor=self.colors["panel_border"],
            background=self.colors["accent"],
            lightcolor=self.colors["accent"],
            darkcolor="#1A6CB0",
        )
        self._loading_bar = ttk.Progressbar(
            frame,
            orient=HORIZONTAL,
            length=330,
            mode="indeterminate",
            style="Reg.Horizontal.TProgressbar",
        )
        self._loading_bar.place(relx=0.5, y=108, anchor=CENTER)
        self._loading_bar.start(12)

        # Animated dot indicator
        self._loading_dot_index = 0
        self._loading_dot_label = Label(
            frame,
            text="",
            bg=self.colors["panel"],
            fg=self.colors["accent"],
            font=("Segoe UI", 16),
        )
        self._loading_dot_label.place(relx=0.5, y=158, anchor=CENTER)

        self._loading_anim_id = None
        self._loading_step_index = 0
        self._loading_steps = [
            "Validating form data...",
            "Analyzing face image...",
            "Comparing with existing records...",
            "Saving to database...",
        ]
        self._animate_loading_screen()
        self._loading_modal.update()

    def _animate_loading_screen(self):
        if not hasattr(self, "_loading_modal") or not self._loading_modal.winfo_exists():
            return

        # Cycle dots
        dot_frames = ["●  ○  ○", "●  ●  ○", "●  ●  ●", "○  ●  ●", "○  ○  ●", "○  ○  ○"]
        self._loading_dot_index = (self._loading_dot_index + 1) % len(dot_frames)
        self._loading_dot_label.configure(text=dot_frames[self._loading_dot_index])

        # Advance step message every ~1.2 s (6 dot frames × 200 ms)
        if self._loading_dot_index == 0:
            next_step = (self._loading_step_index + 1) % len(self._loading_steps)
            self._loading_step_index = next_step
            self._loading_step_var.set(self._loading_steps[next_step])

        self._loading_anim_id = self._loading_modal.after(200, self._animate_loading_screen)

    def _hide_loading_screen(self):
        if hasattr(self, "_loading_bar"):
            try:
                self._loading_bar.stop()
            except Exception:
                pass
        if hasattr(self, "_loading_anim_id") and self._loading_anim_id is not None:
            try:
                self._loading_modal.after_cancel(self._loading_anim_id)
            except Exception:
                pass
            self._loading_anim_id = None
        if hasattr(self, "_loading_modal") and self._loading_modal.winfo_exists():
            self._loading_modal.destroy()

    def _show_duplicate_criminal_modal(self, existing_id, existing_name, existing_crime, new_violation, matches=None):
        """Show duplicate warning with table view and admin actions."""
        matches = matches or []
        records = self._collect_duplicate_records(existing_id, matches)
        self._show_notification(
            title="Possible Existing Criminal",
            message="Possible existing criminal detected. This person may already have a record in the database.",
            kind="warning",
        )

        primary_match = next((m for m in matches if m.get("id") == existing_id), matches[0] if matches else {})
        similarity = primary_match.get("similarity", "-")
        similarity_text = f"{similarity}%" if isinstance(similarity, int) else "-"
        top_similarity = max([r.get("similarity", 0) for r in records], default=0)
        total_crimes = len([r for r in records if str(r.get("crime", "-")).strip() != "-"])

        latest_crime_row = None
        for row in records:
            if row.get("crime") and row.get("crime") != "-":
                if latest_crime_row is None or row.get("sort_key", "") > latest_crime_row.get("sort_key", ""):
                    latest_crime_row = row
        recent_text = f"{latest_crime_row['crime']} ({latest_crime_row['date']})" if latest_crime_row else "-"

        matched_ids = [m.get("id") for m in matches if m.get("id")]
        if existing_id not in matched_ids:
            matched_ids.append(existing_id)
        first_recorded_id = min(matched_ids) if matched_ids else existing_id
        other_ids = [cid for cid in matched_ids if cid != first_recorded_id][:3]
        admin_entered_name = self.fullname.get().strip()

        modal = Toplevel(self.root)
        modal.transient(self.root)
        modal.grab_set()
        modal.resizable(False, False)
        modal.title("Possible Existing Criminal Record")
        modal.configure(bg=self.colors["panel"])

        width = 1100
        height = 640
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        modal.geometry(f"{width}x{height}+{x}+{y}")

        frame = Frame(
            modal,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        frame.place(x=12, y=12, width=width - 24, height=height - 24)

        Label(
            frame,
            text="Warning: Criminal may already exist in the database",
            bg=self.colors["panel"],
            fg="#FFAD42",
            font=("Segoe UI Semibold", 14),
        ).place(x=18, y=12)

        Label(
            frame,
            text=(
                f"Matched Profile: {existing_name}  |  Criminal ID: {self._format_criminal_id(existing_id)}"
                f"  |  Similarity: {similarity_text}"
            ),
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Segoe UI", 10),
        ).place(x=18, y=44)

        Label(
            frame,
            text=(
                f"Total Crimes Recorded: {total_crimes}  |  Most Recent Crime: {recent_text}"
            ),
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).place(x=18, y=66)

        Label(
            frame,
            text="Related records for this person",
            bg=self.colors["panel"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 10),
        ).place(x=18, y=90)

        table_host = Frame(
            frame,
            bg=self.colors["field"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        table_host.place(x=18, y=114, width=760, height=404)

        style = ttk.Style(modal)
        style.theme_use("clam")
        style.configure(
            "Duplicate.Treeview",
            background=self.colors["field"],
            fieldbackground=self.colors["field"],
            foreground=self.colors["text"],
            rowheight=28,
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Duplicate.Treeview.Heading",
            background="#102746",
            foreground=self.colors["accent"],
            relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Duplicate.Treeview",
            background=[("selected", "#1E4D8A")],
            foreground=[("selected", self.colors["text"])],
        )

        columns = (
            "criminal_id",
            "name",
            "alias",
            "crime",
            "date",
            "location",
            "similarity",
        )
        table = ttk.Treeview(table_host, columns=columns, show="headings", height=14, style="Duplicate.Treeview")
        table.heading("criminal_id", text="Criminal ID")
        table.heading("name", text="Name")
        table.heading("alias", text="Possible Alias")
        table.heading("crime", text="Crime Type")
        table.heading("date", text="Date of Crime")
        table.heading("location", text="Location")
        table.heading("similarity", text="Similarity Accuracy")

        table.column("criminal_id", width=96, anchor=CENTER)
        table.column("name", width=136, anchor=W)
        table.column("alias", width=108, anchor=W)
        table.column("crime", width=146, anchor=W)
        table.column("date", width=112, anchor=CENTER)
        table.column("location", width=96, anchor=W)
        table.column("similarity", width=118, anchor=CENTER)

        table.tag_configure("odd", background="#0D2344")
        table.tag_configure("even", background="#0A1D3A")
        table.tag_configure("top_match", background="#173B6A", foreground="#F5FBFF")
        table.tag_configure("hover", background="#1A3F73")

        ybar = Scrollbar(table_host, orient=VERTICAL, command=table.yview)
        xbar = Scrollbar(table_host, orient=HORIZONTAL, command=table.xview)
        table.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        table.place(x=2, y=2, width=736, height=384)
        ybar.place(x=740, y=2, width=16, height=384)
        xbar.place(x=2, y=388, width=754, height=14)

        row_items = []
        for idx, row in enumerate(records):
            row_tags = ["odd" if idx % 2 else "even"]
            if row.get("similarity", 0) == top_similarity:
                row_tags.append("top_match")

            item_id = table.insert(
                "",
                END,
                values=(
                    self._format_criminal_id(row["id"]),
                    row["name"],
                    row["alias"],
                    row["crime"],
                    row["date"],
                    row["location"],
                    f"{row['similarity']}%",
                ),
                tags=tuple(row_tags),
            )
            row_items.append((item_id, tuple(row_tags)))

        hover_state = {"item": ""}

        def _on_table_hover(event):
            current_item = table.identify_row(event.y)
            if current_item == hover_state["item"]:
                return

            for item_id, base_tags in row_items:
                table.item(item_id, tags=base_tags)

            hover_state["item"] = current_item
            if current_item:
                current_tags = list(table.item(current_item, "tags"))
                if "hover" not in current_tags:
                    current_tags.append("hover")
                table.item(current_item, tags=tuple(current_tags))

        table.bind("<Motion>", _on_table_hover)
        table.bind("<Leave>", lambda _event: [table.item(item_id, tags=base_tags) for item_id, base_tags in row_items])

        # Map each Treeview item back to its record for click-to-compare
        item_record_map = {}
        for (item_id, _base_tags), record in zip(row_items, records):
            item_record_map[item_id] = record

        # ── Dynamic Photo Comparison & Similarity Analysis Panel ─────────────
        preview_host = Frame(
            frame,
            bg=self.colors["field"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        preview_host.place(x=792, y=114, width=284, height=404)

        Label(
            preview_host,
            text="PHOTO COMPARISON",
            bg=self.colors["field"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 10),
        ).place(relx=0.5, y=10, anchor=CENTER)

        # Section column headers
        Label(preview_host, text="Selected Record",
              bg=self.colors["field"], fg=self.colors["muted"],
              font=("Segoe UI", 8)).place(x=14, y=28)
        Label(preview_host, text="New Upload",
              bg=self.colors["field"], fg=self.colors["muted"],
              font=("Segoe UI", 8)).place(x=158, y=28)

        # Left photo — updates when a row is clicked
        photo_left_label = Label(preview_host, bg="#061124", width=114, height=114,
                                  text="Select\na row", fg="#3A5A8A",
                                  font=("Segoe UI", 8), compound=CENTER)
        photo_left_label.place(x=12, y=44)
        photo_left_label.img_ref = None

        # VS divider
        Label(preview_host, text="VS",
              bg=self.colors["field"], fg="#2A4A6A",
              font=("Segoe UI Semibold", 9)).place(x=136, y=100, anchor=CENTER)

        # Right photo — static (newly uploaded)
        self._dup_new_img_ref = self._load_modal_photo("temp/1.png", (114, 114))
        Label(preview_host, image=self._dup_new_img_ref, bg="#061124",
              width=114, height=114).place(x=158, y=44)

        # Selected record name label
        selected_name_lbl = Label(
            preview_host, text="\u2190 Click any row to compare",
            bg=self.colors["field"], fg=self.colors["muted"],
            font=("Segoe UI", 8), anchor=W,
        )
        selected_name_lbl.place(x=12, y=163)

        # Divider
        Canvas(preview_host, bg=self.colors["panel_border"],
               height=1, bd=0, highlightthickness=0).place(x=8, y=175, width=268)

        Label(preview_host, text="SIMILARITY ANALYSIS",
              bg=self.colors["field"], fg=self.colors["accent"],
              font=("Segoe UI Semibold", 9)).place(relx=0.5, y=185, anchor=CENTER)

        # ── Arc gauge canvas ─────────────────────────────────────────────────
        import math as _math
        _GCW, _GCH = 264, 110
        # Arc bounding box: semicircle with endpoints at y≈104 (cy), top at y≈4
        _ABX1, _ABY1, _ABX2, _ABY2 = 12, 4, 252, 204
        _ACX  = (_ABX1 + _ABX2) / 2   # 132 – horizontal centre
        _ACY  = (_ABY1 + _ABY2) / 2   # 104 – vertical   centre (= arc endpoints)
        _ARX  = (_ABX2 - _ABX1) / 2   # 120 – x-radius
        _ARY  = (_ABY2 - _ABY1) / 2   # 100 – y-radius
        _ALW  = 18                     # line width of arc strokes

        gauge_canvas = Canvas(preview_host, width=_GCW, height=_GCH,
                              bg=self.colors["field"], highlightthickness=0, bd=0)
        gauge_canvas.place(x=10, y=196)

        # ── Large % label ────────────────────────────────────────────────────
        pct_label = Label(preview_host, text="\u2014",
                          bg=self.colors["field"], fg=self.colors["muted"],
                          font=("Segoe UI Semibold", 24))
        pct_label.place(relx=0.5, y=312, anchor=CENTER)

        # ── Verdict label ────────────────────────────────────────────────────
        verdict_label = Label(
            preview_host, text="Click a row to see analysis",
            bg=self.colors["field"], fg=self.colors["muted"],
            font=("Segoe UI", 8), wraplength=258, justify=CENTER,
        )
        verdict_label.place(relx=0.5, y=342, anchor=CENTER)

        # ── Threat-level segment bar ─────────────────────────────────────────
        _SEG_DEFS = [
            ("POSSIBLE",   85, 88,  "#1A3550", "#2D7DCA"),
            ("PROBABLE",   89, 91,  "#1A3520", "#4CAF50"),
            ("LIKELY",     92, 95,  "#3A2A08", "#E58C1A"),
            ("HIGH MATCH", 96, 100, "#3A0808", "#E03030"),
        ]
        _SW, _SGAP = 54, 8
        _S_TOTAL = len(_SEG_DEFS) * _SW + (len(_SEG_DEFS) - 1) * _SGAP
        _SX0 = (_GCW - _S_TOTAL) // 2

        seg_canvas = Canvas(preview_host, width=_GCW, height=36,
                            bg=self.colors["field"], highlightthickness=0, bd=0)
        seg_canvas.place(x=10, y=364)

        seg_rect_ids, seg_txt_ids = [], []
        for i, (lbl, *_, base_c, _lit_c) in enumerate(_SEG_DEFS):
            sx = _SX0 + i * (_SW + _SGAP)
            seg_rect_ids.append(
                seg_canvas.create_rectangle(sx, 2, sx + _SW, 16, fill=base_c, outline="")
            )
            seg_txt_ids.append(
                seg_canvas.create_text(sx + _SW // 2, 26, text=lbl,
                                       fill="#2D4A6A", font=("Segoe UI", 6), anchor=CENTER)
            )

        # ── Helper colour/verdict functions ──────────────────────────────────
        def _threat_color(pct):
            if pct >= 96:   return "#D42B2B"
            elif pct >= 92: return "#E05A1E"
            elif pct >= 89: return "#EB8A1E"
            else:           return "#F5C842"

        def _verdict_text(pct):
            if pct >= 96:
                return "HIGH MATCH\nSame person strongly indicated"
            elif pct >= 92:
                return "HIGHLY SUSPECTED SAME PERSON\nStrong facial similarity detected"
            elif pct >= 89:
                return "LIKELY SAME PERSON\nSignificant facial match found"
            else:
                return "POSSIBLE MATCH\nVerify manually to confirm identity"

        def _seg_index(pct):
            if pct >= 96:   return 3
            elif pct >= 92: return 2
            elif pct >= 89: return 1
            else:           return 0

        def _draw_gauge(sim_pct):
            gauge_canvas.delete("all")

            # Background arc — full top semicircle, dark
            gauge_canvas.create_arc(
                _ABX1, _ABY1, _ABX2, _ABY2,
                start=0, extent=180,
                style=ARC, outline="#1A2D4A", width=_ALW,
            )
            if sim_pct <= 0:
                return

            tc = _threat_color(sim_pct)
            # Fill arc — clockwise from west (180°) proportional to similarity
            # extent is negative (clockwise); at 100% it sweeps full 180°.
            fill_ext = (sim_pct / 100) * 180
            gauge_canvas.create_arc(
                _ABX1, _ABY1, _ABX2, _ABY2,
                start=180, extent=-fill_ext,
                style=ARC, outline=tc, width=_ALW,
            )

            # Needle-tip dot at the arc endpoint
            tip_rad = _math.radians(180 - fill_ext)
            tip_x = _ACX + _ARX * _math.cos(tip_rad)
            tip_y = _ACY - _ARY * _math.sin(tip_rad)
            r = 7
            gauge_canvas.create_oval(
                tip_x - r, tip_y - r, tip_x + r, tip_y + r,
                fill=tc, outline="#FFFFFF", width=1,
            )

            # 85 % threshold tick mark
            thresh_rad = _math.radians(180 - 0.85 * 180)  # = radians(27°)
            tix = _ACX + _ARX * _math.cos(thresh_rad)
            tiy = _ACY - _ARY * _math.sin(thresh_rad)
            ti_inner_x = _ACX + (_ARX - 9) * _math.cos(thresh_rad)
            ti_inner_y = _ACY - (_ARY - 9) * _math.sin(thresh_rad)
            gauge_canvas.create_line(ti_inner_x, ti_inner_y, tix, tiy,
                                     fill="#F5C842", width=1)
            gauge_canvas.create_text(tix + 2, tiy - 6, text="85%",
                                     fill="#F5C842", font=("Segoe UI", 6), anchor=SW)

            # Centre text: the similarity value
            gauge_canvas.create_text(
                _ACX, _ACY - 6,
                text=f"{sim_pct}%",
                fill=tc, font=("Segoe UI Semibold", 14),
            )

        def _update_seg_bar(pct):
            active = _seg_index(pct)
            for i, (r_id, t_id, seg_def) in enumerate(
                    zip(seg_rect_ids, seg_txt_ids, _SEG_DEFS)):
                _, _, _, _, base_c, lit_c = seg_def
                seg_canvas.itemconfig(r_id, fill=lit_c if i == active else base_c)
                seg_canvas.itemconfig(t_id, fill="#FFFFFF" if i == active else "#2D4A6A")

        # ── Row-click handler ─────────────────────────────────────────────────
        def _on_row_select(event):
            sel = table.selection()
            if not sel:
                return
            rec = item_record_map.get(sel[0])
            if not rec:
                return

            img_path = os.path.join("images", f"user.{rec['id']}.png")
            new_img = self._load_modal_photo(img_path, (114, 114))
            photo_left_label.img_ref = new_img
            photo_left_label.configure(image=new_img, text="")

            crim_id_str = self._format_criminal_id(rec["id"])
            selected_name_lbl.configure(
                text=f"{rec.get('name', '-')}  |  {crim_id_str}"
            )

            sim = int(rec.get("similarity", 0))
            tc  = _threat_color(sim)
            pct_label.configure(text=f"{sim}%", fg=tc)
            verdict_label.configure(text=_verdict_text(sim), fg=tc)
            _draw_gauge(sim)
            _update_seg_bar(sim)

        table.bind("<<TreeviewSelect>>", _on_row_select)

        # Auto-preview the highest-similarity record on open
        if records:
            best = max(records, key=lambda r: r.get("similarity", 0))
            _bimg = self._load_modal_photo(
                os.path.join("images", f"user.{best['id']}.png"), (114, 114))
            photo_left_label.img_ref = _bimg
            photo_left_label.configure(image=_bimg, text="")
            selected_name_lbl.configure(
                text=f"{best.get('name', '-')}  |  {self._format_criminal_id(best['id'])}"
            )
            _bs = int(best.get("similarity", 85))
            _bc = _threat_color(_bs)
            pct_label.configure(text=f"{_bs}%", fg=_bc)
            verdict_label.configure(text=_verdict_text(_bs), fg=_bc)
            _draw_gauge(_bs)
            _update_seg_bar(_bs)

        Label(
            frame,
            text="Choose action:",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).place(x=18, y=530)

        action = {"value": "cancel"}

        def close_with(value):
            action["value"] = value
            modal.destroy()

        alias_btn = Button(
            frame,
            text="Mark Name as Alias",
            command=lambda: close_with("alias"),
            bg="#24364F",
            fg=self.colors["text"],
            activebackground="#2F486A",
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            width=17,
        )
        alias_btn.place(x=190, y=558)

        violation_btn = Button(
            frame,
            text="Add Violation Entry",
            command=lambda: close_with("violation"),
            bg=self.colors["btn"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            width=19,
        )
        violation_btn.place(x=360, y=558)

        continue_btn = Button(
            frame,
            text="Continue as New Person",
            command=lambda: close_with("continue"),
            bg="#1B4D38",
            fg=self.colors["text"],
            activebackground="#276A4E",
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            width=21,
        )
        continue_btn.place(x=562, y=558)

        cancel_btn = Button(
            frame,
            text="Cancel",
            command=lambda: close_with("cancel"),
            bg="#3B2A2A",
            fg=self.colors["text"],
            activebackground="#583838",
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            width=12,
        )
        cancel_btn.place(x=786, y=558)

        modal.protocol("WM_DELETE_WINDOW", lambda: close_with("cancel"))
        self.root.wait_window(modal)

        if action["value"] == "violation":
            self._add_violation(existing_id, new_violation)
            history_text = self._get_violation_history_text(existing_id)
            self._show_notification(
                title="Violation Added",
                message=(
                    f"Existing record kept for {existing_name} ({self._format_criminal_id(existing_id)}).\n"
                    f"New violation added: {new_violation}\n\n"
                    f"Violation history:\n{history_text}"
                ),
                kind="info",
            )
        elif action["value"] == "continue":
            success, payload = self.database_enter(allow_duplicate_insert=True)
            if success == 1:
                self._show_notification(
                    title="Success",
                    message="New profile created as a different person.",
                    kind="info",
                )
                self.go_back()
            else:
                self._show_notification(
                    title="Validation Warning",
                    message=payload,
                    kind="warning",
                )
        elif action["value"] == "alias":
            alias_added = self._add_alias(existing_id, admin_entered_name)
            if alias_added:
                self._show_notification(
                    title="Alias Saved",
                    message=(
                        f"New name '{admin_entered_name}' has been marked as alias for "
                        f"{existing_name} ({self._format_criminal_id(existing_id)})."
                    ),
                    kind="info",
                )
            else:
                self._show_notification(
                    title="Alias Not Saved",
                    message="Alias is empty, already exists, or matches the registered name.",
                    kind="warning",
                )

    def _load_modal_photo(self, image_path, size):
        fallback = Image.new("RGB", size, color="#061124")
        try:
            if os.path.exists(image_path):
                image = Image.open(image_path)
                image = ImageOps.contain(image, size, RESAMPLE)
                canvas = Image.new("RGB", size, color="#061124")
                x = (size[0] - image.size[0]) // 2
                y = (size[1] - image.size[1]) // 2
                canvas.paste(image, (x, y))
                return ImageTk.PhotoImage(canvas)
        except Exception:
            pass
        return ImageTk.PhotoImage(fallback)

    def _format_criminal_id(self, criminal_id):
        try:
            return f"CR-{int(criminal_id):04d}"
        except Exception:
            return str(criminal_id)

    def _collect_duplicate_records(self, primary_id, matches):
        match_lookup = {item.get("id"): item for item in (matches or []) if item.get("id")}
        if primary_id not in match_lookup:
            match_lookup[primary_id] = {"id": primary_id, "similarity": 85}

        criminal_ids = sorted(match_lookup.keys(), key=lambda cid: match_lookup[cid].get("distance", 9.9))

        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        records = []

        for criminal_id in criminal_ids:
            cursor.execute("SELECT Name, Nationality FROM People WHERE ID=?", (criminal_id,))
            person = cursor.fetchone() or ("Unknown", "-")
            aliases = self._get_aliases_for_criminal(criminal_id)
            alias_text = ", ".join(aliases[:2]) if aliases else "-"
            similarity = int(match_lookup[criminal_id].get("similarity", 85))
            photo_name = f"user.{criminal_id}.png"

            cursor.execute(
                """
                SELECT ViolationText, CreatedAt
                FROM Violations
                WHERE CriminalID=?
                ORDER BY ViolationID ASC
                """,
                (criminal_id,),
            )
            violations = cursor.fetchall()

            if violations:
                for violation_text, created_at in violations:
                    created_text = str(created_at) if created_at else ""
                    date_value = created_text.split(" ")[0] if created_text else "-"
                    records.append(
                        {
                            "id": criminal_id,
                            "name": person[0] or "-",
                            "alias": alias_text,
                            "crime": violation_text or "-",
                            "date": date_value,
                            "location": person[1] if person[1] else "-",
                            "photo": photo_name,
                            "similarity": similarity,
                            "sort_key": created_text,
                        }
                    )
            else:
                records.append(
                    {
                        "id": criminal_id,
                        "name": person[0] or "-",
                        "alias": alias_text,
                        "crime": "-",
                        "date": "-",
                        "location": person[1] if person[1] else "-",
                        "photo": photo_name,
                        "similarity": similarity,
                        "sort_key": "",
                    }
                )

        conn.close()
        records.sort(key=lambda row: (row.get("sort_key", ""), row.get("similarity", 0)))
        return records

    def _show_notification(self, title, message, kind="info"):
        modal = Toplevel(self.root)
        modal.transient(self.root)
        modal.grab_set()
        modal.resizable(False, False)
        modal.title(title)
        modal.configure(bg=self.colors["panel"])

        width = 460
        height = 230 if kind == "confirm" else 210
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        modal.geometry(f"{width}x{height}+{x}+{y}")

        frame = Frame(
            modal,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        frame.place(x=12, y=12, width=width - 24, height=height - 24)

        tone = self.colors["accent"] if kind != "warning" else "#FFAD42"

        Label(
            frame,
            text=title,
            bg=self.colors["panel"],
            fg=tone,
            font=("Segoe UI Semibold", 14),
        ).place(x=18, y=14)

        Label(
            frame,
            text=message,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Segoe UI", 10),
            justify=LEFT,
            wraplength=width - 70,
            anchor="w",
        ).place(x=18, y=52)

        result = {"value": False}

        def close_with(value):
            result["value"] = value
            modal.destroy()

        if kind == "confirm":
            yes_btn = Button(
                frame,
                text="Proceed",
                command=lambda: close_with(True),
                bg=self.colors["btn"],
                fg=self.colors["text"],
                activebackground=self.colors["btn_hover"],
                activeforeground=self.colors["text"],
                bd=0,
                relief=FLAT,
                cursor="hand2",
                font=("Segoe UI Semibold", 10),
                width=14,
            )
            yes_btn.place(x=165, y=155)

            no_btn = Button(
                frame,
                text="Cancel",
                command=lambda: close_with(False),
                bg="#24364F",
                fg=self.colors["text"],
                activebackground="#2F486A",
                activeforeground=self.colors["text"],
                bd=0,
                relief=FLAT,
                cursor="hand2",
                font=("Segoe UI Semibold", 10),
                width=14,
            )
            no_btn.place(x=292, y=155)
        else:
            ok_btn = Button(
                frame,
                text="OK",
                command=lambda: close_with(True),
                bg=self.colors["btn"],
                fg=self.colors["text"],
                activebackground=self.colors["btn_hover"],
                activeforeground=self.colors["text"],
                bd=0,
                relief=FLAT,
                cursor="hand2",
                font=("Segoe UI Semibold", 10),
                width=12,
            )
            ok_btn.place(x=312, y=145)

        modal.protocol("WM_DELETE_WINDOW", lambda: close_with(False))
        self.root.wait_window(modal)
        return result["value"]

    def go_back(self):
        subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "start.py")])
        self.root.destroy()

    def get_id(self):
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ID) FROM People")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] is not None else 0

    def _ensure_violations_table(self):
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Violations (
                ViolationID INTEGER PRIMARY KEY AUTOINCREMENT,
                CriminalID INTEGER NOT NULL,
                ViolationText TEXT NOT NULL,
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (CriminalID) REFERENCES People(ID)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_criminal_id ON Violations(CriminalID)")
        conn.commit()
        conn.close()

    def _ensure_aliases_table(self):
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Aliases (
                AliasID INTEGER PRIMARY KEY AUTOINCREMENT,
                CriminalID INTEGER NOT NULL,
                AliasName TEXT NOT NULL,
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(CriminalID, AliasName),
                FOREIGN KEY (CriminalID) REFERENCES People(ID)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_aliases_criminal_id ON Aliases(CriminalID)")
        conn.commit()
        conn.close()

    def _normalize_alias(self, value):
        return " ".join(str(value).strip().split())

    def _add_alias(self, criminal_id, alias_name):
        alias_clean = self._normalize_alias(alias_name)
        if not alias_clean:
            return False

        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM People WHERE ID=?", (criminal_id,))
        row = cursor.fetchone()
        registered_name = self._normalize_alias(row[0]) if row and row[0] else ""
        if registered_name.lower() == alias_clean.lower():
            conn.close()
            return False

        cursor.execute(
            "INSERT OR IGNORE INTO Aliases (CriminalID, AliasName) VALUES (?, ?)",
            (criminal_id, alias_clean),
        )
        inserted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return inserted

    def _get_aliases_for_criminal(self, criminal_id):
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT AliasName FROM Aliases WHERE CriminalID=? ORDER BY AliasID ASC",
            (criminal_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [str(row[0]) for row in rows if row and row[0]]

    def _seed_violations_from_people(self):
        # Backfill one initial violation for existing people when migration runs first time.
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO Violations (CriminalID, ViolationText)
            SELECT p.ID, p.Crime
            FROM People p
            WHERE p.Crime IS NOT NULL
              AND TRIM(p.Crime) <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM Violations v WHERE v.CriminalID = p.ID
              )
            """
        )
        conn.commit()
        conn.close()

    def _add_violation(self, criminal_id, violation_text):
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Violations (CriminalID, ViolationText) VALUES (?, ?)",
            (criminal_id, violation_text),
        )
        # Keep latest violation mirrored in People.Crime for existing screens.
        cursor.execute("UPDATE People SET Crime=? WHERE ID=?", (violation_text, criminal_id))
        conn.commit()
        conn.close()

    def _get_violation_history_text(self, criminal_id, limit=5):
        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ViolationText
            FROM Violations
            WHERE CriminalID=?
            ORDER BY ViolationID DESC
            LIMIT ?
            """,
            (criminal_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "No previous violations found."
        return "\n".join([f"- {str(row[0])}" for row in rows])

    def _is_valid_name(self, value):
        # Accept letters with common name separators, reject numeric-only/invalid names.
        return re.fullmatch(r"[A-Za-z][A-Za-z\s'.-]{1,49}", value) is not None

    def _is_valid_text_label(self, value):
        # Accept descriptive text fields while disallowing numbers-only input.
        if not value:
            return False
        if re.fullmatch(r"\d+", value):
            return False
        return re.fullmatch(r"[A-Za-z0-9\s,.'()/-]{2,80}", value) is not None

    def _load_known_faces(self):
        """Load all known face encodings from the images folder."""
        self.known_encodings = []
        self.known_face_ids = []
        
        if not os.path.isdir("images"):
            return
        
        for filename in os.listdir("images"):
            if not filename.startswith("user.") or not filename.endswith(".png"):
                continue
            
            try:
                # Extract ID from filename like "user.1.png"
                parts = filename.split(".")
                if len(parts) >= 3:
                    criminal_id = int(parts[1])
                    image_path = os.path.join("images", filename)
                    img = fr.load_image_file(image_path)
                    vectors = fr.face_encodings(img)
                    if vectors:
                        self.known_encodings.append(vectors[0])
                        self.known_face_ids.append(criminal_id)
            except (ValueError, IndexError, Exception):
                continue

    def _check_duplicate_face(self):
        """
        Check if the face in temp/1.png already exists in the database.
        Returns: (exists: bool, criminal_id: int or None, matches: list[dict])
        """
        if not os.path.exists("temp/1.png"):
            return False, None, None
        
        try:
            # Reload all known faces to catch any recent registrations
            self._load_known_faces()
            
            # Load the new face
            new_img = fr.load_image_file("temp/1.png")
            new_encodings = fr.face_encodings(new_img)
            
            if not new_encodings:
                return False, None, None
            
            new_encoding = new_encodings[0]
            
            if not self.known_encodings:
                return False, None, None
            
            face_distances = fr.face_distance(self.known_encodings, new_encoding)

            if len(face_distances) > 0:
                # Keep high-confidence matches and map them to a user-friendly similarity score.
                # dist <= 0.45 is considered a match. We present this range as 85%-100% similarity.
                matched_indices = [i for i, dist in enumerate(face_distances) if dist <= 0.45]
                if matched_indices:
                    best_for_id = {}
                    for idx in sorted(matched_indices, key=lambda i: face_distances[i]):
                        cid = self.known_face_ids[idx]
                        distance = float(face_distances[idx])
                        similarity = int(round(85 + ((0.45 - distance) / 0.45) * 15))
                        similarity = max(85, min(100, similarity))

                        if cid not in best_for_id or distance < best_for_id[cid]["distance"]:
                            best_for_id[cid] = {
                                "distance": distance,
                                "similarity": similarity,
                            }

                    ordered_ids = sorted(best_for_id.keys(), key=lambda criminal_id: best_for_id[criminal_id]["distance"])

                    conn = sqlite3.connect("criminal.db")
                    cursor = conn.cursor()
                    matched_rows = []
                    for cid in ordered_ids:
                        cursor.execute("SELECT ID, Name, Crime FROM people WHERE ID=?", (cid,))
                        row = cursor.fetchone()
                        if row:
                            matched_rows.append(
                                {
                                    "id": row[0],
                                    "name": row[1],
                                    "crime": row[2],
                                    "similarity": best_for_id[cid]["similarity"],
                                    "distance": best_for_id[cid]["distance"],
                                }
                            )
                    conn.close()

                    if matched_rows:
                        return True, matched_rows[0]["id"], matched_rows
            
            return False, None, None
        
        except Exception as e:
            print(f"[DEBUG] Duplicate face check error: {e}")
            return False, None, None

    def database_enter(self, allow_duplicate_insert=False):
        name = self.fullname.get().strip()
        father = self.fathername.get().strip()
        mother = self.mothername.get().strip()
        body = self.bodymark.get().strip()
        nat = self.nationality.get().strip()
        crime = self.crime.get().strip()

        gender = ""
        if self.gen.get() == 1:
            gender = "Male"
        elif self.gen.get() == 2:
            gender = "Female"

        religion = self.rel.get().strip()
        blood_group = self.blood.get().strip()

        if religion == "Select Religion":
            religion = None
        if blood_group == "Select Blood Group":
            blood_group = None

        if not name:
            return 0, "Name is required."
        if not self._is_valid_name(name):
            return 0, "Name must contain letters only (no numeric-only names)."

        if father and not self._is_valid_name(father):
            return 0, "Father Name is invalid. Use letters and spaces only."
        if mother and not self._is_valid_name(mother):
            return 0, "Mother Name is invalid. Use letters and spaces only."

        if not gender:
            return 0, "Gender is required."
        if religion is None:
            return 0, "Religion is required."

        if nat and not self._is_valid_name(nat):
            return 0, "Nationality is invalid. Use letters and spaces only."

        if not crime:
            return 0, "Crime convicted is required."
        canonical_crime = self._canonical_crime(crime)
        if not canonical_crime:
            return 0, "Crime convicted must be selected from the crime list."
        crime = canonical_crime

        if not self.selected_file or not os.path.exists("temp/1.png"):
            return 0, "Face image is required. Please upload an image before registering."

        if body and not self._is_valid_text_label(body):
            return 0, "Body Mark format is invalid."

        # Check for duplicate face unless admin explicitly chose to continue as a new person.
        if not allow_duplicate_insert:
            is_duplicate, existing_id, existing_info = self._check_duplicate_face()
            if is_duplicate and existing_info:
                primary = existing_info[0]
                return 2, {
                    "id": existing_id,
                    "name": primary["name"],
                    "crime": primary["crime"],
                    "similarity": primary["similarity"],
                    "new_violation": crime,
                    "matches": existing_info,
                }

        conn = sqlite3.connect("criminal.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO People (Name,Gender,Father,Mother,Religion,Blood,Bodymark,Nationality,Crime) VALUES(?,?,?,?,?,?,?,?,?)",
            (name, gender, father, mother, religion, blood_group, body, nat, crime),
        )
        new_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Violations (CriminalID, ViolationText) VALUES (?, ?)",
            (new_id, crime),
        )
        conn.commit()
        conn.close()

        target = "images/user." + str(new_id) + ".png"
        shutil.copy("temp/1.png", target)
        return 1, "ok"

    def _fade_in_window(self):
        alpha = self.root.attributes("-alpha")
        if alpha < 1.0:
            self.root.attributes("-alpha", min(alpha + 0.05, 1.0))
            self.root.after(20, self._fade_in_window)

    def _slide_in_panel(self):
        updated = False
        if self.form_x < self.form_target_x:
            self.form_x += 0.01
            updated = True
        if self.preview_x > self.preview_target_x:
            self.preview_x -= 0.01
            updated = True

        self.form_panel.place_configure(relx=self.form_x)
        self.preview_panel.place_configure(relx=self.preview_x)

        if updated:
            self.root.after(16, self._slide_in_panel)

    def _draw_background(self, event):
        self.bg_canvas.delete("all")
        width = max(event.width, 1)
        height = max(event.height, 1)

        top = self._hex_to_rgb("#030814")
        bottom = self._hex_to_rgb("#0A1B39")

        for y in range(height):
            ratio = y / height
            r = int(top[0] + (bottom[0] - top[0]) * ratio)
            g = int(top[1] + (bottom[1] - top[1]) * ratio)
            b = int(top[2] + (bottom[2] - top[2]) * ratio)
            self.bg_canvas.create_line(0, y, width, y, fill=f"#{r:02x}{g:02x}{b:02x}")

        for x in range(0, width, 44):
            self.bg_canvas.create_line(x, 64, x, height, fill="#0F2B55")
        for y in range(64, height, 34):
            self.bg_canvas.create_line(0, y, width, y, fill="#0A2242")

        self.bg_canvas.create_rectangle(0, 63, width, 64, fill="#245AA3", outline="")

    @staticmethod
    def _hex_to_rgb(value):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RegisterDashboard()
    app.run()
