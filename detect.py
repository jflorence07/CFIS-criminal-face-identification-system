from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from PIL import ImageTk, Image, ImageOps
import sqlite3
import shutil
import cv2
import os
import numpy as np
import math
import winsound
import sys
import subprocess


def ensure_project_venv():
    """Relaunch with .venv interpreter when launched from a different Python."""
    if getattr(sys, 'frozen', False):
        return
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

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
import face_recognition as fr

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


class PhotoMatchDashboard:
    """Modern photo-matching screen for CFIS with animated dashboard UI."""

    def __init__(self):
        self.root = Tk()
        self.root.title("Criminal Registration System - Photo Match")
        self.root.geometry("1360x760")
        self.root.state("zoomed")
        self.root.configure(bg="#040B1A")
        self.root.attributes("-alpha", 0.0)

        self.colors = {
            "header": "#081224",
            "panel": "#0B152A",
            "panel_border": "#1C3D76",
            "text": "#E6F1FF",
            "muted": "#89A8D8",
            "accent": "#2DB3FF",
            "btn": "#103A76",
            "btn_hover": "#1A58A8",
            "btn_pressed": "#0D2C58",
            "danger": "#FF5252",
            "nav_btn": "#0D1C35",
            "nav_btn_hover": "#16335E",
            "nav_btn_pressed": "#102746",
            "nav_btn_border": "#2E7EDC",
        }

        self.preview_photo = None
        self.detail_photo = None
        self.match_label = None
        self.photo_selected = False
        self.warned_conflicts = set()

        self.images = self.load_images_from_folder("images")
        self.encodings = []
        self.known_face_names = []
        self._load_known_faces()

        self.bg_canvas = Canvas(self.root, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_background)

        self._build_header()
        self._build_layout()
        self._fade_in_window()
        self._slide_in_panels()
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
            text="Upload an image and identify known suspects",
            bg=self.colors["header"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(side=RIGHT, padx=20, pady=22)

    def _build_layout(self):
        self.left_panel = Frame(
            self.root,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        self.right_panel = Frame(
            self.root,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )

        self.left_x = 0.24
        self.left_target_x = 0.26
        self.right_x = 0.72
        self.right_target_x = 0.70

        self.left_panel.place(relx=self.left_x, rely=0.56, anchor=CENTER, width=620, height=620)
        self.right_panel.place(relx=self.right_x, rely=0.56, anchor=CENTER, width=660, height=620)

        Label(
            self.left_panel,
            text="Select Photo to Detect Faces",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 18),
        ).place(x=18, y=14)

        self.preview_box = Label(
            self.left_panel,
            bg="#061124",
            fg=self.colors["muted"],
            text="No photo selected",
            font=("Segoe UI", 12),
            anchor=CENTER,
        )
        self.preview_box.place(x=18, y=52, width=580, height=480)

        self.status_label = Label(
            self.left_panel,
            text="Status: Waiting for input",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        )
        self.status_label.place(x=18, y=548)

        self.button_row = Frame(self.left_panel, bg=self.colors["panel"])
        self.button_row.place(x=18, y=572, width=584, height=40)

        self.select_btn = self._action_button("Select Photo", self.open_photo)
        self.select_btn.pack(in_=self.button_row, side=LEFT, padx=(0, 14))

        self.match_btn = self._action_button("View Matching Records", self.view_matches)
        self.match_btn.pack(in_=self.button_row, side=LEFT)

        Label(
            self.right_panel,
            text="Matches (Double click for profile details)",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 16),
        ).place(x=16, y=14)

        self._setup_tree_style()
        self.tree = ttk.Treeview(
            self.right_panel,
            columns=("id", "name", "crime", "nationality"),
            show="headings",
            height=9,
        )
        self.tree.heading("id", text="Criminal-ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("crime", text="Crime")
        self.tree.heading("nationality", text="Nationality")

        self.tree.column("id", width=110, anchor=CENTER)
        self.tree.column("name", width=180, anchor=W)
        self.tree.column("crime", width=160, anchor=W)
        self.tree.column("nationality", width=130, anchor=W)

        self.tree.place(x=16, y=48, width=628, height=250)
        self.tree.bind("<Double-1>", self.doubleclick)

        self.detail_panel = Frame(
            self.right_panel,
            bg="#08182F",
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        self.detail_panel.place(x=16, y=316, width=628, height=286)

        self.detail_image = Label(self.detail_panel, bg="#061124", anchor=CENTER)
        self.detail_image.place(x=12, y=16, width=250, height=250)

        self.profile_fields = {}
        fields = [
            ("Name", 278, 22),
            ("Father", 278, 48),
            ("Mother", 278, 74),
            ("Gender", 278, 100),
            ("Religion", 278, 126),
            ("Blood", 278, 152),
            ("BodyMark", 278, 178),
            ("Nationality", 278, 204),
        ]

        for key, x, y in fields:
            Label(
                self.detail_panel,
                text=key + ":",
                bg="#08182F",
                fg=self.colors["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).place(x=x, y=y)

            value = Label(
                self.detail_panel,
                text="-",
                bg="#08182F",
                fg=self.colors["text"],
                font=("Segoe UI", 9),
                anchor="w",
            )
            value.place(x=x + 85, y=y)
            self.profile_fields[key.lower()] = value

        self.crime_label = Label(
            self.detail_panel,
            text="",
            bg="#08182F",
            fg=self.colors["danger"],
            font=("Segoe UI Semibold", 11),
            anchor="w",
            justify=LEFT,
            wraplength=320,
        )
        self.crime_label.place(x=278, y=236)

    def _setup_tree_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#0A1D3A",
            foreground="#E6F1FF",
            fieldbackground="#0A1D3A",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#0F2E5E",
            foreground="#A8D8FF",
            font=("Segoe UI Semibold", 10),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#1A58A8")], foreground=[("selected", "#E6F1FF")])

    def _action_button(self, text, command):
        btn = Button(
            self.left_panel,
            text=text,
            command=command,
            width=22,
            bg=self.colors["btn"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 11),
            padx=12,
            pady=8,
        )
        btn.bind("<Enter>", lambda event, b=btn: self._button_hover_in(b))
        btn.bind("<Leave>", lambda event, b=btn: self._button_hover_out(b))
        btn.bind("<ButtonPress-1>", lambda event, b=btn: self._button_press(b))
        btn.bind("<ButtonRelease-1>", lambda event, b=btn: self._button_release(b))
        return btn

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

    def open_photo(self):
        path = filedialog.askopenfilename(
            title="Select photo",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")],
        )
        if not path:
            return

        os.makedirs("temp", exist_ok=True)
        shutil.copy(path, "temp/1.png")

        image = Image.open("temp/1.png")
        image = ImageOps.contain(image, (580, 480), RESAMPLE)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_box.configure(image=self.preview_photo, text="")
        self.status_label.configure(text="Status: Photo selected", fg=self.colors["accent"])
        
        # Set a flag to indicate a photo was just selected
        self.photo_selected = True

    def clear_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

    def load_images_from_folder(self, folder):
        if not os.path.isdir(folder):
            return []
        return [name for name in os.listdir(folder) if os.path.isfile(os.path.join(folder, name))]

    def _load_known_faces(self):
        for filename in self.images:
            image_path = os.path.join("images", filename)
            try:
                img = fr.load_image_file(image_path)
                vectors = fr.face_encodings(img)
                if not vectors:
                    continue
                self.encodings.append(vectors[0])
                self.known_face_names.append((os.path.splitext(filename)[0]).split(".")[1])
            except Exception:
                continue

    def show_percentage_match(self, face_distance, threshold=0.6):
        if face_distance > threshold:
            match_range = 1.0 - threshold
            linear_val = (1.0 - face_distance) / (match_range * 2.0)
            return linear_val
        match_range = threshold
        linear_val = 1.0 - (face_distance / (match_range * 2.0))
        return linear_val + ((1.0 - linear_val) * math.pow((linear_val - 0.5) * 2, 0.2))

    def _crime_severity_score(self, crime_text):
        text = str(crime_text).lower()
        score = 0
        rules = [
            (100, ["terror", "terrorism", "mass murder"]),
            (95, ["murder", "homicide", "rape"]),
            (90, ["kidnap", "abduction", "human trafficking"]),
            (80, ["armed robbery", "robbery", "attempt to murder"]),
            (70, ["assault", "weapon", "shoot", "stab"]),
            (60, ["drug", "narcotic", "smuggling"]),
            (45, ["fraud", "cyber", "forgery", "extortion"]),
            (30, ["theft", "burglary", "snatching"]),
            (15, ["vandal", "trespass", "public nuisance", "traffic"]),
        ]
        for value, keywords in rules:
            if any(keyword in text for keyword in keywords):
                score = max(score, value)
        return score

    def _show_conflict_warning(self, matched_ids):
        key = tuple(sorted([str(item) for item in matched_ids]))
        if key in self.warned_conflicts:
            return
        self.warned_conflicts.add(key)

        modal = Toplevel(self.root)
        modal.transient(self.root)
        modal.grab_set()
        modal.resizable(False, False)
        modal.title("Danger Warning")
        modal.configure(bg="#2A0606")
        modal.attributes("-topmost", True)

        width = 560
        height = 250
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        modal.geometry(f"{width}x{height}+{x}+{y}")

        frame = Frame(modal, bg="#2A0606", highlightthickness=2, highlightbackground="#FF3B3B")
        frame.place(x=12, y=12, width=width - 24, height=height - 24)

        Label(
            frame,
            text="CRITICAL ALERT",
            bg="#2A0606",
            fg="#FFC9C9",
            font=("Segoe UI Semibold", 10),
        ).place(x=16, y=10)

        Label(
            frame,
            text="[DANGER] SAME FACE ALREADY EXISTS",
            bg="#2A0606",
            fg="#FF3B3B",
            font=("Segoe UI Black", 14),
        ).place(x=16, y=32)

        Label(
            frame,
            text="This user already exists under multiple records: " + ", ".join([str(i) for i in matched_ids]),
            bg="#2A0606",
            fg=self.colors["text"],
            font=("Segoe UI", 10),
            wraplength=510,
            justify=LEFT,
            anchor="w",
        ).place(x=16, y=82)

        Label(
            frame,
            text="Block duplicate registration and review all linked records immediately.",
            bg="#2A0606",
            fg="#FF9C9C",
            font=("Segoe UI", 9),
            anchor="w",
        ).place(x=16, y=142)

        Button(
            frame,
            text="OK",
            command=modal.destroy,
            bg="#8D1616",
            fg=self.colors["text"],
            activebackground="#B02121",
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            width=12,
        ).place(x=406, y=184)

        self.root.wait_window(modal)

    def view_matches(self):
        self.clear_tree()

        # Check if a photo was actually selected in this session
        if not self.photo_selected or not os.path.exists("temp/1.png"):
            self.status_label.configure(text="Status: Select a photo first", fg=self.colors["danger"])
            return

        frame = cv2.imread("temp/1.png")
        if frame is None:
            self.status_label.configure(text="Status: Unable to read selected image", fg=self.colors["danger"])
            return

        if not self.encodings:
            self.status_label.configure(text="Status: No known face encodings available", fg=self.colors["danger"])
            return

        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])

        face_locations = fr.face_locations(rgb_small_frame)
        try:
            face_encodings = fr.face_encodings(rgb_small_frame, face_locations)
        except TypeError:
            face_encodings = []

        if not face_encodings:
            self.status_label.configure(text="Status: No faces found", fg=self.colors["danger"])
            return

        match_found = False
        inserted_ids = set()
        for face_encoding in face_encodings:
            face_distances = fr.face_distance(self.encodings, face_encoding)
            if len(face_distances) == 0:
                continue

            matched_indices = [i for i, dist in enumerate(face_distances) if dist < 0.45]
            if not matched_indices:
                continue

            matched_ids = []
            for idx in sorted(matched_indices, key=lambda i: face_distances[i]):
                cid = self.known_face_names[idx]
                if cid not in matched_ids:
                    matched_ids.append(cid)

            conn = sqlite3.connect("criminal.db")
            cur = conn.cursor()
            matched_rows = []
            for identity in matched_ids:
                cur.execute("SELECT ID,name,crime,nationality FROM people WHERE ID=?", (identity,))
                row = cur.fetchone()
                if row:
                    matched_rows.append(row)
            conn.close()

            matched_rows.sort(key=lambda row: self._crime_severity_score(row[2]), reverse=True)
            for row in matched_rows:
                if row[0] not in inserted_ids:
                    self.tree.insert("", "end", values=row)
                    inserted_ids.add(row[0])
                    match_found = True

            winsound.PlaySound("SystemExit", winsound.SND_ALIAS)
            best_match_index = int(np.argmin(face_distances))
            percent = self.show_percentage_match(face_distances[best_match_index])

            if len(matched_ids) > 1:
                self._show_conflict_warning(matched_ids)
                self.status_label.configure(
                    text="Status: Warning - same face linked to multiple records: " + ", ".join([str(i) for i in matched_ids]),
                    fg=self.colors["danger"],
                )
            else:
                self.status_label.configure(
                    text="Status: Matching " + str(round(percent * 100, 2)) + "%",
                    fg=self.colors["accent"],
                )

        if not match_found:
            self.status_label.configure(text="Status: No match found", fg=self.colors["danger"])

    def doubleclick(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0], "values")
        if not item:
            return

        try:
            criminal_id = int(item[0])
        except (ValueError, IndexError):
            return

        self.view_detail(criminal_id)

    def view_detail(self, criminal_id):
        conn = sqlite3.connect("criminal.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM people WHERE Id=?", (criminal_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return

        self.profile_fields["name"].configure(text=str(row[1]))
        self.profile_fields["father"].configure(text=str(row[3]))
        self.profile_fields["mother"].configure(text=str(row[4]))
        self.profile_fields["gender"].configure(text=str(row[2]))
        self.profile_fields["religion"].configure(text=str(row[5]))
        self.profile_fields["blood"].configure(text=str(row[6]))
        self.profile_fields["bodymark"].configure(text=str(row[7]))
        self.profile_fields["nationality"].configure(text=str(row[8]))
        self.crime_label.configure(text=self._get_crime_history_text(criminal_id, fallback_crime=row[9]))

        face_path = "images/user." + str(criminal_id) + ".png"
        if os.path.exists(face_path):
            image = Image.open(face_path)
            image = ImageOps.contain(image, (250, 250), RESAMPLE)
            self.detail_photo = ImageTk.PhotoImage(image)
            self.detail_image.configure(image=self.detail_photo, text="")

    def _get_crime_history_text(self, criminal_id, fallback_crime):
        conn = sqlite3.connect("criminal.db")
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT ViolationText FROM Violations WHERE CriminalID=? ORDER BY ViolationID DESC LIMIT 4",
                (criminal_id,),
            )
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()

        if not rows:
            return "Crime: " + str(fallback_crime)

        history = "\n".join(["- " + str(item[0]) for item in rows])
        return "Violations (latest first):\n" + history

    def go_back(self):
        if getattr(sys, 'frozen', False):
            subprocess.Popen([os.path.join(os.path.dirname(sys.executable), 'CFIS.exe')])
        else:
            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "start.py")])
        self.root.destroy()

    def _fade_in_window(self):
        alpha = self.root.attributes("-alpha")
        if alpha < 1.0:
            self.root.attributes("-alpha", min(alpha + 0.05, 1.0))
            self.root.after(20, self._fade_in_window)

    def _slide_in_panels(self):
        updated = False
        if self.left_x < self.left_target_x:
            self.left_x += 0.006
            updated = True
        if self.right_x > self.right_target_x:
            self.right_x -= 0.006
            updated = True

        self.left_panel.place_configure(relx=self.left_x)
        self.right_panel.place_configure(relx=self.right_x)

        if updated:
            self.root.after(16, self._slide_in_panels)

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
    app = PhotoMatchDashboard()
    app.run()
