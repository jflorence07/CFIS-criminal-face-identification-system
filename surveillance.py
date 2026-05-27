import cv2
import numpy as np
import sqlite3
from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps
import os
import math
import winsound
import sys
import subprocess
import time
import threading


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


class App:
    """Live surveillance dashboard with modern UI and personnel match results."""

    def __init__(self, video_source=0):
        self.appname = "Face Detection System - Surveillance"
        self.window = Tk()
        self.window.title(self.appname)
        self.window.geometry("1360x760")
        self.window.state("zoomed")
        self.window.configure(bg="#040B1A")
        self.window.attributes("-alpha", 0.0)

        self.colors = {
            "bg": "#040B1A",
            "header": "#081224",
            "panel": "#0B152A",
            "panel_border": "#1C3D76",
            "text": "#E6F1FF",
            "muted": "#89A8D8",
            "accent": "#2DB3FF",
            "grid1": "#0F2B55",
            "grid2": "#0A2242",
            "danger": "#FF5252",
            "nav_btn": "#0D1C35",
            "nav_btn_hover": "#16335E",
            "nav_btn_pressed": "#102746",
            "nav_btn_border": "#2E7EDC",
        }

        self.video_source = video_source
        self.vid = myvideocapture(self.video_source)
        self._frame_fail_count = 0

        self.detected_people = []
        self.warned_conflicts = set()
        self.face_locations = []
        self.face_encodings = []
        self.face_names = []
        self.process_this_frame = True
        self.frame_detections = []  # batch detections in current frame
        self.frame_conflicts = []  # batch conflicts in current frame
        self.notification_scheduled = False  # prevent duplicate notifications

        self.images = self.load_images_from_folder("images")
        self.encodings = []
        self.known_face_names = []
        self._load_known_faces()

        self.faceDetect = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        self.recognizer = None
        if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()

        self.bg_canvas = Canvas(self.window, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_background)

        self._build_header()
        self._build_layout()
        self._build_details()

        self._fade_in_window()
        self._slide_in_panels()

        notify_launcher_ready(self.window)
        self.update()
        self.window.mainloop()

    def _load_known_faces(self):
        for filename in self.images:
            image_path = os.path.join("images", filename)
            try:
                img = fr.load_image_file(image_path)
                face_vectors = fr.face_encodings(img)
                if not face_vectors:
                    continue
                self.encodings.append(face_vectors[0])
                self.known_face_names.append((os.path.splitext(filename)[0]).split(".")[1])
            except Exception:
                continue

    def _build_header(self):
        self.header = Frame(self.window, bg=self.colors["header"], height=64)
        self.header.place(x=0, y=0, relwidth=1)

        self._create_nav_button(self.header, "<  Back to Menu", self.go_back).pack(side=LEFT, padx=(18, 10), pady=14)

        Label(
            self.header,
            text="FACE DETECTION SYSTEM",
            bg=self.colors["header"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 13),
        ).pack(side=LEFT, padx=8, pady=18)

        Label(
            self.header,
            text="Live camera feed and real-time suspect matching",
            bg=self.colors["header"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(side=RIGHT, padx=20, pady=22)

    def _build_layout(self):
        self.video_panel = Frame(
            self.window,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        self.result_panel = Frame(
            self.window,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )

        self.video_x = 0.27
        self.video_target_x = 0.29
        self.result_x = 0.67
        self.result_target_x = 0.65

        self.video_panel.place(relx=self.video_x, rely=0.56, anchor=CENTER, width=760, height=620)
        self.result_panel.place(relx=self.result_x, rely=0.56, anchor=CENTER, width=560, height=620)

        Label(
            self.video_panel,
            text="Live Video Feed",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 18),
        ).place(x=16, y=12)

        self.canvas = Canvas(self.video_panel, width=724, height=540, bg="#061124", highlightthickness=0)
        self.canvas.place(x=16, y=48)

        self.status_label = Label(
            self.video_panel,
            text="Status: Monitoring",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        )
        self.status_label.place(x=16, y=592)

        Label(
            self.video_panel,
            text="Camera Source:",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        ).place(x=492, y=592)

        self.camera_source_var = StringVar()
        self.camera_source_combo = ttk.Combobox(
            self.video_panel,
            textvariable=self.camera_source_var,
            values=["0", "1", "2", "3"],
            state="readonly",
            width=4,
        )
        current_source = self.vid.active_source if isinstance(self.vid.active_source, int) else 0
        self.camera_source_var.set(str(current_source))
        self.camera_source_combo.place(x=584, y=591)

        Button(
            self.video_panel,
            text="Switch",
            command=self.switch_camera_source,
            bg="#10325E",
            fg=self.colors["text"],
            activebackground="#1A4D8F",
            activeforeground=self.colors["text"],
            bd=0,
            relief=FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=2,
        ).place(x=636, y=589)

        self._update_camera_status("Monitoring", self.colors["muted"])

        Label(
            self.result_panel,
            text="Detection Log",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 18),
        ).place(x=16, y=12)

        self._setup_tree_style()
        self.tree = ttk.Treeview(
            self.result_panel,
            columns=("id", "name", "crime", "nationality", "match"),
            show="headings",
            height=10,
        )

        self.tree.heading("id", text="Cr-ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("crime", text="Crime")
        self.tree.heading("nationality", text="Nationality")
        self.tree.heading("match", text="Matching %")

        self.tree.column("id", width=70, anchor=CENTER)
        self.tree.column("name", width=150, anchor=W)
        self.tree.column("crime", width=120, anchor=W)
        self.tree.column("nationality", width=110, anchor=W)
        self.tree.column("match", width=90, anchor=CENTER)

        self.tree.place(x=16, y=50, width=528, height=320)
        self.tree.bind("<Double-1>", self.doubleclick)

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

    def _nav_hover_in(self, button):
        button.configure(bg=self.colors["nav_btn_hover"], padx=16)

    def _nav_hover_out(self, button):
        button.configure(bg=self.colors["nav_btn"], padx=14)

    def _nav_press(self, button):
        button.configure(bg=self.colors["nav_btn_pressed"], padx=13)

    def _build_details(self):
        self.details_panel = Frame(
            self.result_panel,
            bg="#08182F",
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )
        self.details_panel.place(x=16, y=388, width=528, height=214)

        Label(
            self.details_panel,
            text="Selected Profile",
            bg="#08182F",
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 12),
        ).place(x=12, y=10)

        self.detail_image_label = Label(self.details_panel, bg="#061124", anchor=CENTER)
        self.detail_image_label.place(x=12, y=30, width=180, height=180)

        self.detail_labels = {}
        fields = [
            ("Name", 205, 34),
            ("Gender", 205, 58),
            ("Father", 205, 82),
            ("Mother", 205, 106),
            ("Religion", 205, 130),
            ("Blood", 205, 154),
            ("Nationality", 205, 178),
        ]

        for key, x, y in fields:
            Label(
                self.details_panel,
                text=key + ":",
                bg="#08182F",
                fg=self.colors["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).place(x=x, y=y)

            value_label = Label(
                self.details_panel,
                text="-",
                bg="#08182F",
                fg=self.colors["text"],
                font=("Segoe UI", 9),
                anchor="w",
            )
            value_label.place(x=x + 80, y=y)
            self.detail_labels[key.lower()] = value_label

        self.crime_label = Label(
            self.details_panel,
            text="",
            bg="#08182F",
            fg=self.colors["danger"],
            font=("Segoe UI Semibold", 11),
            anchor="w",
            justify=LEFT,
            wraplength=300,
        )
        self.crime_label.place(x=205, y=198)

    def _active_backend_name(self):
        if self.vid.active_backend == cv2.CAP_DSHOW:
            return "DSHOW"
        if self.vid.active_backend == cv2.CAP_MSMF:
            return "MSMF"
        return "default"

    def _update_camera_status(self, prefix, color):
        source = self.vid.active_source if self.vid.active_source is not None else "?"
        backend = self._active_backend_name()
        self.status_label.configure(
            text=f"Status: {prefix} (camera {source}, {backend})",
            fg=color,
        )

    def switch_camera_source(self):
        selected = self.camera_source_var.get().strip()
        if not selected.isdigit():
            self._update_camera_status("Invalid camera source", self.colors["danger"])
            return

        new_source = int(selected)
        try:
            self.vid.video_source = new_source
            self.vid.reopen()
            self._frame_fail_count = 0
            self._update_camera_status("Monitoring", self.colors["muted"])
        except Exception:
            self._update_camera_status(f"Camera {new_source} not available", self.colors["danger"])

    def _setup_tree_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#0A1D3A",
            foreground="#E6F1FF",
            fieldbackground="#0A1D3A",
            rowheight=28,
            bordercolor="#1C3D76",
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
        style.map(
            "Treeview",
            background=[("selected", "#1A58A8")],
            foreground=[("selected", "#E6F1FF")],
        )

    def load_images_from_folder(self, folder):
        if not os.path.isdir(folder):
            return []
        return [name for name in os.listdir(folder) if os.path.isfile(os.path.join(folder, name))]

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

        self.viewdetail(criminal_id)

    def viewdetail(self, criminal_id):
        conn = sqlite3.connect("criminal.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM people WHERE Id=?", (criminal_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return

        self.detail_labels["name"].configure(text=str(row[1]))
        self.detail_labels["gender"].configure(text=str(row[2]))
        self.detail_labels["father"].configure(text=str(row[3]))
        self.detail_labels["mother"].configure(text=str(row[4]))
        self.detail_labels["religion"].configure(text=str(row[5]))
        self.detail_labels["blood"].configure(text=str(row[6]))
        self.detail_labels["nationality"].configure(text=str(row[8]))
        self.crime_label.configure(text=self._get_crime_history_text(criminal_id, fallback_crime=row[9]))

        face_path = "images/user." + str(criminal_id) + ".png"
        if os.path.exists(face_path):
            image = Image.open(face_path)
            image = ImageOps.contain(image, (180, 180), RESAMPLE)
            self.detail_photo = ImageTk.PhotoImage(image)
            self.detail_image_label.configure(image=self.detail_photo, text="")
        else:
            self.detail_image_label.configure(image="", text="No image", fg=self.colors["muted"]) 

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

    def getProfile(self, identity):
        if not identity:
            return None

        conn = sqlite3.connect("criminal.db")
        cmd = "SELECT ID,name,crime,nationality FROM people WHERE ID=?"
        cursor = conn.execute(cmd, (identity,))
        profile = cursor.fetchone()
        conn.close()
        return profile

    def showPercentageMatch(self, face_distance, face_match_threshold=0.6):
        if face_distance > face_match_threshold:
            match_range = 1.0 - face_match_threshold
            linear_val = (1.0 - face_distance) / (match_range * 2.0)
            return linear_val
        match_range = face_match_threshold
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

    def _play_notification_sound_async(self):
        """Play sound in background thread to avoid blocking video loop."""
        def play_sound():
            try:
                winsound.PlaySound("SystemExit", winsound.SND_ALIAS)
            except Exception:
                pass
        thread = threading.Thread(target=play_sound, daemon=True)
        thread.start()

    def _show_conflict_warning_async(self, matched_ids):
        """Show conflict warning non-blocking using after()."""
        key = tuple(sorted([str(item) for item in matched_ids]))
        if key in self.warned_conflicts:
            return
        self.warned_conflicts.add(key)

        def show_modal():
            modal = Toplevel(self.window)
            modal.transient(self.window)
            modal.resizable(False, False)
            modal.title("Danger Warning")
            modal.configure(bg="#2A0606")
            modal.attributes("-topmost", True)

            width = 560
            height = 250
            screen_w = self.window.winfo_screenwidth()
            screen_h = self.window.winfo_screenheight()
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

        # Show modal after 250ms to not block video
        self.window.after(250, show_modal)

    def _process_frame_detections(self):
        """Process all detections batched in current frame and notify once."""
        if not self.frame_detections:
            return

        # Only ring/notify once per frame batch
        self._play_notification_sound_async()

        # Add all new profiles to tree
        for profile, confidence in self.frame_detections:
            profile_data = tuple(list(profile) + [confidence])
            self.tree.insert("", "end", values=profile_data)

        # Show conflict warnings
        for matched_ids in self.frame_conflicts:
            self._show_conflict_warning_async(matched_ids)

        # Update status with summary
        num_new = len(self.frame_detections)
        if self.frame_conflicts:
            self._update_camera_status(
                f"Alert - {num_new} match(es) detected with duplicate records",
                self.colors["danger"],
            )
        else:
            self._update_camera_status(f"Match detected - {num_new} personnel", self.colors["accent"])

        # Clear batch
        self.frame_detections = []
        self.frame_conflicts = []
        self.notification_scheduled = False

    def update(self):
        is_true, frame = self.vid.getframe()
        if is_true:
            self._frame_fail_count = 0
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
            self.canvas.create_image(0, 0, image=self.photo, anchor=NW)

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = np.ascontiguousarray(small_frame)

            if self.process_this_frame and self.encodings:
                self.frame_detections = []  # reset batch for this frame
                self.frame_conflicts = []   # reset batch for this frame
                self.face_locations = fr.face_locations(rgb_small_frame)
                try:
                    self.face_encodings = fr.face_encodings(rgb_small_frame, self.face_locations)
                except TypeError:
                    self.face_encodings = []

                self.face_names = []
                for face_encoding in self.face_encodings:
                    face_distances = fr.face_distance(self.encodings, face_encoding)
                    if len(face_distances) == 0:
                        continue

                    best_match_index = int(np.argmin(face_distances))

                    identity = 0
                    percent = self.showPercentageMatch(face_distances[best_match_index])

                    matched_indices = [i for i, dist in enumerate(face_distances) if dist < 0.45]
                    matched_ids = []
                    for idx in sorted(matched_indices, key=lambda i: face_distances[i]):
                        cid = self.known_face_names[idx]
                        if cid not in matched_ids:
                            matched_ids.append(cid)

                    if matched_ids:
                        identity = matched_ids[0]

                    self.face_names.append(identity)

                    confidence = str(round(percent * 100, 2)) + "%"
                    candidate_profiles = []
                    for candidate_id in matched_ids:
                        profile = self.getProfile(candidate_id)
                        if profile:
                            candidate_profiles.append(profile)

                    candidate_profiles.sort(key=lambda row: self._crime_severity_score(row[2]), reverse=True)
                    for profile in candidate_profiles:
                        if profile not in self.detected_people:
                            self.detected_people.append(profile)
                            # Batch this detection
                            self.frame_detections.append((profile, confidence))

                    if len(matched_ids) > 1:
                        # Batch the conflict
                        self.frame_conflicts.append(matched_ids)

                # Process all batched detections at end of frame
                if self.frame_detections and not self.notification_scheduled:
                    self.notification_scheduled = True
                    self._process_frame_detections()

            self.process_this_frame = not self.process_this_frame

        else:
            self._frame_fail_count += 1
            if self._frame_fail_count == 15:
                self._update_camera_status("Camera connected but no frames. Retrying...", self.colors["danger"])
            if self._frame_fail_count >= 45:
                self.vid.reopen()
                self._frame_fail_count = 0
                self._update_camera_status("Monitoring", self.colors["muted"])

        self.window.after(15, self.update)

    def _fade_in_window(self):
        alpha = self.window.attributes("-alpha")
        if alpha < 1.0:
            self.window.attributes("-alpha", min(alpha + 0.05, 1.0))
            self.window.after(20, self._fade_in_window)

    def _slide_in_panels(self):
        updated = False
        if self.video_x < self.video_target_x:
            self.video_x += 0.005
            updated = True
        if self.result_x > self.result_target_x:
            self.result_x -= 0.005
            updated = True

        self.video_panel.place_configure(relx=self.video_x)
        self.result_panel.place_configure(relx=self.result_x)

        if updated:
            self.window.after(16, self._slide_in_panels)

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
            self.bg_canvas.create_line(x, 64, x, height, fill=self.colors["grid1"])
        for y in range(64, height, 34):
            self.bg_canvas.create_line(0, y, width, y, fill=self.colors["grid2"])

        self.bg_canvas.create_rectangle(0, 63, width, 64, fill="#245AA3", outline="")

    @staticmethod
    def _hex_to_rgb(value):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def go_back(self):
        if getattr(sys, 'frozen', False):
            subprocess.Popen([os.path.join(os.path.dirname(sys.executable), 'CFIS.exe')])
        else:
            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "start.py")])
        self.window.destroy()


class myvideocapture:
    def __init__(self, video_source=0):
        self.video_source = video_source
        self.vid = None
        self.width = 0
        self.height = 0
        self.active_source = None
        self.active_backend = None
        self.reopen()

    def _open_capture_with_backend(self, source, backend=None):
        if backend is None:
            cap = cv2.VideoCapture(source)
        else:
            cap = cv2.VideoCapture(source, backend)

        if not cap or not cap.isOpened():
            if cap:
                cap.release()
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        if not self._capture_produces_frames(cap):
            cap.release()
            return None

        return cap

    @staticmethod
    def _capture_produces_frames(cap, attempts=12):
        for _ in range(attempts):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                return True
            time.sleep(0.05)
        return False

    def reopen(self):
        if self.vid is not None and self.vid.isOpened():
            self.vid.release()

        candidates = []
        if isinstance(self.video_source, int):
            if os.name == "nt":
                candidates.append((self.video_source, cv2.CAP_DSHOW))
            candidates.append((self.video_source, None))
        else:
            if os.name == "nt":
                candidates.append((self.video_source, cv2.CAP_DSHOW))
            candidates.append((self.video_source, None))

        unique_candidates = []
        seen = set()
        for source, backend in candidates:
            key = (str(source), backend if backend is not None else "default")
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append((source, backend))

        selected = None
        selected_source = None
        selected_backend = None
        for source, backend in unique_candidates:
            selected = self._open_capture_with_backend(source, backend)
            if selected is not None:
                selected_source = source
                selected_backend = backend
                break

        if selected is None:
            raise ValueError("Unable to open any video source", self.video_source)

        self.vid = selected
        self.active_source = selected_source
        self.active_backend = selected_backend
        self.width = self.vid.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def getframe(self):
        if self.vid and self.vid.isOpened():
            ret, frame = self.vid.read()
            if not ret:
                return ret, None
            height = frame.shape[0]
            width = frame.shape[1]
            if height > 0:
                scale = 540 / float(height)
                target_width = max(1, int(width * scale))
                frame = cv2.resize(frame, (target_width, 540), interpolation=cv2.INTER_AREA)
            return ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return False, None

    def __del__(self):
        if self.vid and self.vid.isOpened():
            self.vid.release()


if __name__ == "__main__":
    App()
