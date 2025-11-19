from __future__ import annotations

import math
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import webbrowser

from PIL import Image, ImageTk

from config_store import load_config, save_config
from data_model import DataManager, MainConfig
from image_utils import prepare_picture
from picture_editor import PictureEditor


class YaesuManagerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Yaesu SD Card Manager (Python)")
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit_without_save)

        self.config = load_config()
        self.manager = DataManager(self.config)

        self.current_message_index: int | None = None
        self.current_picture_index: int | None = None
        self.display_image: ImageTk.PhotoImage | None = None

        self._build_ui()
        self._create_menu()

        self.root.after(200, self.open_dat_file)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.list_frame = ttk.Frame(self.main_frame)
        self.list_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        msg_frame, self.message_list = self._create_listbox(
            self.list_frame, "Message List", self.on_message_select
        )
        msg_frame.grid(row=0, column=0, sticky="nsew")

        pic_frame, self.picture_list = self._create_listbox(
            self.list_frame, "Picture List", self.on_picture_select
        )
        pic_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.list_frame.rowconfigure(0, weight=1)
        self.list_frame.rowconfigure(1, weight=1)

        self.detail_frame = ttk.Frame(self.main_frame)
        self.detail_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        self._build_message_details()
        self._build_picture_details()

        action_frame = ttk.Frame(self.main_frame)
        action_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        action_frame.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(
            action_frame, text="Remove Duplicates", command=self.remove_duplicates
        ).grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Button(
            action_frame, text="Configuration", command=self.open_config_dialog
        ).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(
            action_frame, text="Save and Exit", command=self.on_save_and_exit
        ).grid(row=0, column=2, sticky="ew", padx=5)
        ttk.Button(
            action_frame, text="Exit without saving", command=self.on_exit_without_save
        ).grid(row=0, column=3, sticky="ew", padx=5)

    def _create_listbox(self, parent: ttk.Frame, title: str, callback):
        frame = ttk.LabelFrame(parent, text=title, padding=5)
        listbox = tk.Listbox(frame, height=10)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        listbox.bind("<<ListboxSelect>>", callback)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(button_frame, text="Insert", command=lambda lb=listbox: self._insert_from_list(lb)).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )
        ttk.Button(button_frame, text="Delete", command=lambda lb=listbox: self._delete_from_list(lb)).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )

        if "Picture" in title:
            ttk.Button(button_frame, text="GoogleMaps", command=self.open_picture_google_maps).pack(
                side=tk.RIGHT, padx=2
            )
        else:
            ttk.Button(button_frame, text="GoogleMaps", command=self.open_message_google_maps).pack(
                side=tk.RIGHT, padx=2
            )

        return frame, listbox

    def _build_message_details(self) -> None:
        self.message_frame = ttk.LabelFrame(self.detail_frame, text="Message Details", padding=10)
        self.message_frame.grid(row=0, column=0, sticky="nsew")
        self.detail_frame.rowconfigure(0, weight=1)

        labels = ["Date", "From", "Repeater", "To", "Position", "Subject"]
        self.msg_vars = {name: tk.StringVar() for name in labels}

        for idx, label in enumerate(labels):
            ttk.Label(self.message_frame, text=f"{label}:").grid(row=idx, column=0, sticky="e", pady=2)
            entry_state = "normal" if label == "Subject" else "readonly"
            entry = ttk.Entry(
                self.message_frame, textvariable=self.msg_vars[label], width=40, state=entry_state
            )
            entry.grid(row=idx, column=1, sticky="ew", pady=2)
            if label == "Subject":
                self.msg_subject_entry = entry

        self.message_frame.columnconfigure(1, weight=1)

        ttk.Label(self.message_frame, text="Text Data:").grid(row=6, column=0, sticky="ne", pady=(5, 0))
        self.msg_text = tk.Text(self.message_frame, height=5, width=50, wrap="word")
        self.msg_text.grid(row=6, column=1, sticky="nsew", pady=(5, 0))
        self.message_frame.rowconfigure(6, weight=1)

    def _build_picture_details(self) -> None:
        self.picture_frame = ttk.LabelFrame(self.detail_frame, text="Picture Details", padding=10)
        self.picture_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.detail_frame.rowconfigure(1, weight=1)

        labels = ["Date", "From", "Repeater", "To", "Position", "Subject"]
        self.pic_vars = {name: tk.StringVar() for name in labels}
        for idx, label in enumerate(labels):
            ttk.Label(self.picture_frame, text=f"{label}:").grid(row=idx, column=0, sticky="e", pady=2)
            entry_state = "normal" if label == "Subject" else "readonly"
            entry = ttk.Entry(
                self.picture_frame, textvariable=self.pic_vars[label], width=40, state=entry_state
            )
            entry.grid(row=idx, column=1, sticky="ew", pady=2)
            if label == "Subject":
                self.pic_subject_entry = entry

        self.picture_frame.columnconfigure(1, weight=1)

        self.image_frame = ttk.LabelFrame(self.picture_frame, text="Preview", padding=5)
        self.image_frame.grid(row=0, column=2, rowspan=len(labels), sticky="nsew", padx=(10, 0))
        self.picture_frame.columnconfigure(2, weight=1)
        self.picture_frame.rowconfigure(len(labels), weight=1)

        self.image_label = ttk.Label(self.image_frame, text="No image loaded", anchor="center")
        self.image_label.pack(fill=tk.BOTH, expand=True)

    def _create_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open DAT...", command=lambda: self.open_dat_file(initial=False))
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_only)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_exit_without_save)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    # List operations
    # ------------------------------------------------------------------
    def _insert_from_list(self, listbox: tk.Listbox) -> None:
        if listbox is self.message_list:
            self.add_message()
        else:
            self.add_picture()

    def _delete_from_list(self, listbox: tk.Listbox) -> None:
        if listbox is self.message_list:
            self.delete_message()
        else:
            self.delete_picture()

    def refresh_message_list(self) -> None:
        self.message_list.delete(0, tk.END)
        for record in self.manager.messages:
            self.message_list.insert(tk.END, record.get_date())

    def refresh_picture_list(self) -> None:
        self.picture_list.delete(0, tk.END)
        for record in self.manager.pictures:
            self.picture_list.insert(tk.END, record.get_date())

    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------
    def on_message_select(self, event=None) -> None:
        if not self.manager.messages:
            return
        selection = self.message_list.curselection()
        if not selection:
            return
        self.commit_message_edits()
        index = selection[0]
        self.current_message_index = index
        record = self.manager.messages[index]
        self.msg_vars["Date"].set(record.get_date())
        self.msg_vars["From"].set(record.get_from())
        self.msg_vars["Repeater"].set(record.get_repeater())
        self.msg_vars["To"].set(record.get_to())
        self.msg_vars["Position"].set(record.get_position())
        self.msg_vars["Subject"].set(record.get_subject())
        self.msg_text.delete("1.0", tk.END)
        self.msg_text.insert("1.0", record.get_text())

    def on_picture_select(self, event=None) -> None:
        if not self.manager.pictures:
            return
        selection = self.picture_list.curselection()
        if not selection:
            return
        self.commit_picture_edits()
        index = selection[0]
        self.current_picture_index = index
        record = self.manager.pictures[index]
        self.pic_vars["Date"].set(record.get_date())
        self.pic_vars["From"].set(record.get_from())
        self.pic_vars["Repeater"].set(record.get_repeater())
        self.pic_vars["To"].set(record.get_to())
        self.pic_vars["Position"].set(record.get_position())
        self.pic_vars["Subject"].set(record.get_subject())
        self._display_picture(record)

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------
    def add_message(self) -> None:
        if not self._ensure_loaded():
            return
        self.commit_message_edits()
        record = self.manager.add_message()
        self.refresh_message_list()
        self.message_list.selection_clear(0, tk.END)
        index = len(self.manager.messages) - 1
        self.message_list.selection_set(index)
        self.message_list.see(index)
        self.on_message_select()

    def delete_message(self) -> None:
        if self.current_message_index is None:
            return
        self.commit_message_edits()
        self.manager.remove_message(self.current_message_index)
        self.refresh_message_list()
        if self.manager.messages:
            new_index = min(self.current_message_index, len(self.manager.messages) - 1)
            self.message_list.selection_set(new_index)
            self.on_message_select()
        else:
            self.current_message_index = None
            self._clear_message_fields()

    def add_picture(self) -> None:
        if not self._ensure_loaded():
            return
        file_path = filedialog.askopenfilename(
            title="Select picture",
            filetypes=[("JPEG files", ("*.jpg", "*.jpeg")), ("All Files", "*.*")],
        )
        if not file_path:
            return
        source = Path(file_path)
        dest = None
        try:
            prepared = prepare_picture(source, self.config.quality)
            editor = PictureEditor(self.root, prepared, self.config)
            edited = editor.show()
            if edited is None:
                return
            dest = self.manager.allocate_picture_filename()
            dest.parent.mkdir(parents=True, exist_ok=True)
            edited.convert("RGB").save(dest, format="JPEG")
        except Exception as exc:
            if dest is not None:
                self.manager.picture_counter -= 1
            messagebox.showerror("Error", f"Unable to insert picture:\n{exc}")
            return
        record = self.manager.add_picture()
        record.set_filename(dest.name)
        record.set_size(dest.stat().st_size)
        self.manager.mark_changed()
        self.refresh_picture_list()
        index = len(self.manager.pictures) - 1
        self.picture_list.selection_clear(0, tk.END)
        self.picture_list.selection_set(index)
        self.on_picture_select()

    def delete_picture(self) -> None:
        if self.current_picture_index is None:
            return
        self.commit_picture_edits()
        self.manager.remove_picture(self.current_picture_index)
        self.refresh_picture_list()
        if self.manager.pictures:
            new_index = min(self.current_picture_index, len(self.manager.pictures) - 1)
            self.picture_list.selection_set(new_index)
            self.on_picture_select()
        else:
            self.current_picture_index = None
            self._clear_picture_fields()
            self._clear_image()

    # ------------------------------------------------------------------
    def commit_message_edits(self) -> None:
        if self.current_message_index is None:
            return
        record = self.manager.messages[self.current_message_index]
        subject = self.msg_subject_entry.get()[:16]
        if subject != record.get_subject():
            record.set_subject(subject)
            self.manager.mark_changed()
        text = self.msg_text.get("1.0", "end").replace("\n", " ").strip()
        if text != record.get_text():
            record.set_text(text[:80])
            self.manager.mark_changed()

    def commit_picture_edits(self) -> None:
        if self.current_picture_index is None:
            return
        record = self.manager.pictures[self.current_picture_index]
        subject = self.pic_subject_entry.get()[:16]
        if subject != record.get_subject():
            record.set_subject(subject)
            self.manager.mark_changed()

    # ------------------------------------------------------------------
    def open_dat_file(self, initial: bool = True) -> None:
        path = filedialog.askopenfilename(
            title="Select any DAT file",
            filetypes=[("DAT files", "*.DAT"), ("All Files", "*.*")],
        )
        if not path:
            if initial and not self.manager.messages:
                messagebox.showinfo(
                    "Information", "No DAT file selected. The application will stay idle."
                )
            return
        self.current_message_index = None
        self.current_picture_index = None
        try:
            self.manager.load(Path(path))
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to load data:\n{exc}")
            return
        self.refresh_message_list()
        self.refresh_picture_list()
        if self.manager.messages:
            self.message_list.selection_set(0)
            self.on_message_select()
        else:
            self._clear_message_fields()
        if self.manager.pictures:
            self.picture_list.selection_set(0)
            self.on_picture_select()
        else:
            self._clear_picture_fields()
            self._clear_image()
        self.root.title(f"Yaesu SD Card Manager (Python) - {path}")

    def save_only(self) -> None:
        if not self._ensure_loaded():
            return
        try:
            self.commit_message_edits()
            self.commit_picture_edits()
            self.manager.save()
            messagebox.showinfo("Saved", "Files saved to SD card.")
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to save files:\n{exc}")

    def on_save_and_exit(self) -> None:
        self.save_only()
        self.root.destroy()

    def on_exit_without_save(self) -> None:
        if self.manager.changed:
            if not messagebox.askyesno("Confirm", "Data will be lost. Exit anyway?"):
                return
        self.root.destroy()

    def remove_duplicates(self) -> None:
        removed_msg = self.manager.remove_message_duplicates()
        removed_pic = self.manager.remove_picture_duplicates()
        if removed_msg or removed_pic:
            self.refresh_message_list()
            self.refresh_picture_list()
            messagebox.showinfo(
                "Duplicates removed",
                f"Messages removed: {removed_msg}\nPictures removed: {removed_pic}",
            )

    def open_message_google_maps(self) -> None:
        if self.current_message_index is None:
            return
        record = self.manager.messages[self.current_message_index]
        self._open_google_maps(record.get_position())

    def open_picture_google_maps(self) -> None:
        if self.current_picture_index is None:
            return
        record = self.manager.pictures[self.current_picture_index]
        self._open_google_maps(record.get_position())

    # ------------------------------------------------------------------
    def open_config_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Configuration")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        ttk.Label(dialog, text="Call Sign:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        call_var = tk.StringVar(value=self.config.callsign)
        ttk.Entry(dialog, textvariable=call_var).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="GPS (20 chars):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        gps_var = tk.StringVar(value=self.config.gps)
        ttk.Entry(dialog, textvariable=gps_var).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(
            dialog,
            text="Pick location...",
            command=lambda: self._open_location_picker(dialog, gps_var),
        ).grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(dialog, text="Picture Quality:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        quality_var = tk.StringVar(value=self.config.quality)
        ttk.Combobox(dialog, textvariable=quality_var, values=["LOW", "MID"], state="readonly").grid(
            row=2, column=1, padx=5, pady=5
        )

        ttk.Label(dialog, text="QR/Overlay URL:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        overlay_var = tk.StringVar(value=self.config.overlay_url)
        ttk.Entry(dialog, textvariable=overlay_var).grid(row=3, column=1, padx=5, pady=5)

        def _apply():
            self.config = MainConfig(
                callsign=call_var.get(),
                gps=gps_var.get(),
                quality=quality_var.get(),
                overlay_url=overlay_var.get(),
            ).normalized()
            save_config(self.config)
            self.manager.update_config(self.config)
            dialog.destroy()

        ttk.Button(dialog, text="OK", command=_apply).grid(row=4, column=0, padx=5, pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=4, column=1, padx=5, pady=10)

    def _open_location_picker(self, parent: tk.Toplevel, gps_var: tk.StringVar) -> None:
        try:
            from geopy.geocoders import Nominatim
        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "The geopy package is required for location search.\n"
                "Install it with `pip install geopy` and try again.",
            )
            return

        picker = tk.Toplevel(parent)
        picker.title("Search location")
        picker.transient(parent)
        picker.grab_set()
        picker.columnconfigure(1, weight=1)
        picker.rowconfigure(1, weight=1)

        query_var = tk.StringVar()
        status_var = tk.StringVar(value="Enter a city or address and press Search.")
        results: list = []
        geolocator = Nominatim(user_agent="yaesumanpy")

        ttk.Label(picker, text="Query:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        search_entry = ttk.Entry(picker, textvariable=query_var)
        search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        search_button = ttk.Button(picker, text="Search")
        search_button.grid(row=0, column=2, padx=5, pady=5)

        result_list = tk.Listbox(picker, height=8)
        result_list.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        result_scroll = ttk.Scrollbar(picker, orient=tk.VERTICAL, command=result_list.yview)
        result_scroll.grid(row=1, column=3, sticky="ns", pady=5)
        result_list.configure(yscrollcommand=result_scroll.set)

        ttk.Label(picker, textvariable=status_var, foreground="gray").grid(
            row=2, column=0, columnspan=3, padx=5, pady=(0, 5), sticky="w"
        )

        action_frame = ttk.Frame(picker)
        action_frame.grid(row=3, column=0, columnspan=3, pady=5)
        ttk.Button(action_frame, text="Use location", command=lambda: _apply_selection()).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(action_frame, text="Cancel", command=picker.destroy).pack(side=tk.LEFT, padx=5)

        def _finish_search(locations, error=None):
            nonlocal results
            search_button.config(state="normal")
            result_list.delete(0, tk.END)
            if error:
                status_var.set(f"Lookup failed: {error}")
                return
            if not locations:
                status_var.set("No matches found.")
                results = []
                return
            results = locations
            for loc in results:
                description = f"{loc.address} ({loc.latitude:.4f}, {loc.longitude:.4f})"
                result_list.insert(tk.END, description)
            status_var.set("Select a result and click Use location.")

        def _search_location(event=None):
            query = query_var.get().strip()
            if not query:
                status_var.set("Please enter a city, address, or landmark.")
                return
            status_var.set("Searching...")
            search_button.config(state="disabled")
            result_list.delete(0, tk.END)

            def _worker():
                try:
                    locations = geolocator.geocode(query, exactly_one=False, limit=10, addressdetails=False)
                except Exception as exc:
                    picker.after(0, lambda: _finish_search(None, error=exc))
                else:
                    picker.after(0, lambda: _finish_search(locations))

            threading.Thread(target=_worker, daemon=True).start()

        def _apply_selection(event=None):
            if not results:
                status_var.set("Search for a location first.")
                return
            selection = result_list.curselection()
            if not selection:
                status_var.set("Select a result to use.")
                return
            loc = results[selection[0]]
            try:
                gps_text = self._decimal_to_gps(float(loc.latitude), float(loc.longitude))
            except (TypeError, ValueError):
                status_var.set("Unable to convert the selected coordinates.")
                return
            gps_var.set(gps_text)
            picker.destroy()

        search_button.configure(command=_search_location)
        search_entry.bind("<Return>", _search_location)
        result_list.bind("<Double-Button-1>", _apply_selection)
        picker.protocol("WM_DELETE_WINDOW", picker.destroy)
        search_entry.focus_set()

    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> bool:
        if not self.manager.qso_dir:
            messagebox.showinfo("Load data", "Please open a DAT file first.")
            return False
        return True

    def _clear_message_fields(self) -> None:
        for var in self.msg_vars.values():
            var.set("")
        self.msg_text.delete("1.0", tk.END)

    def _clear_picture_fields(self) -> None:
        for var in self.pic_vars.values():
            var.set("")

    def _display_picture(self, record: PictureRecord) -> None:
        path = self.manager.picture_path(record)
        if not path or not path.exists():
            self._clear_image()
            return
        try:
            with Image.open(path) as img:
                img_copy = img.copy()
            img_copy.thumbnail((320, 240), Image.LANCZOS)
            self.display_image = ImageTk.PhotoImage(img_copy)
            self.image_label.configure(image=self.display_image, text="")
        except Exception as exc:
            self._clear_image()
            messagebox.showerror("Error", f"Cannot load picture:\n{exc}")

    def _clear_image(self) -> None:
        self.display_image = None
        self.image_label.configure(image="", text="No image loaded")

    @staticmethod
    def _decimal_to_gps(lat: float, lon: float) -> str:
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise ValueError("Invalid coordinates")

        def _encode(value: float, pos: str, neg: str, max_deg: int) -> tuple[str, int, int]:
            hemi = pos if value >= 0 else neg
            value = abs(value)
            deg = int(value)
            minutes = (value - deg) * 60.0
            minute_scaled = int(round(minutes * 10000))
            if minute_scaled >= 600000:
                minute_scaled = 0
                deg = min(deg + 1, max_deg)
            return hemi, deg, minute_scaled

        lat_part = _encode(lat, "N", "S", 90)
        lon_part = _encode(lon, "E", "W", 180)
        return f"{lat_part[0]}{lat_part[1]:03d}{lat_part[2]:06d}{lon_part[0]}{lon_part[1]:03d}{lon_part[2]:06d}"

    def _open_google_maps(self, position: str) -> None:
        if not position or position.startswith("-"):
            return
        try:
            parts = position.replace("\"", "").replace("'", "").split("/")
            lat_part = parts[0].strip()
            lon_part = parts[1].strip()
            lat_dir, lat_rest = lat_part.split(":")
            lon_dir, lon_rest = lon_part.split(":")
            lat_deg, lat_min, lat_sec = map(float, lat_rest.split())
            lon_deg, lon_min, lon_sec = map(float, lon_rest.split())
            lat = lat_deg + lat_min / 60.0 + lat_sec / 3600.0
            lon = lon_deg + lon_min / 60.0 + lon_sec / 3600.0
            if lat_dir == "S":
                lat *= -1
            if lon_dir == "W":
                lon *= -1
            url = f"https://www.google.com/maps/place/{lat:.4f},{lon:.4f}"
            webbrowser.open(url)
        except Exception:
            messagebox.showerror("Error", "Unable to parse GPS position for Google Maps.")

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = YaesuManagerApp()
    app.run()


if __name__ == "__main__":
    main()
