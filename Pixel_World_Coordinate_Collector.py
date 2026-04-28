# Pixel-World Coordinate Collector
# A tool to collect Ground Control Points (GCPs) by clicking on images and entering their real-world coordinates. Supports multiple images, zoom/pan, and CSV export.
# Author: Sabuj Biswas (with assistance from ChatGPT)
# Usage:
# 1. Run the script to open the GUI.
# 2. Use "Load Image" or "Load Multiple Images" to select your images.
# 3. Click on the image to add GCPs. A dialog will prompt for world coordinates (X, Y in meters).
# 4. Right-click near a point to delete it.
# 5. Use the table on the right to view all points from all images, select points, or delete the selected point.
# 6. Use the "Save Points to CSV" button to export all collected points to a CSV file. The CSV will include the image path, pixel coordinates, and world coordinates for each point.

import csv
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np


class PixelWorldCoordinateCollector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pixel-World Coordinate Collector")
        self.geometry("1400x860")
        self.minsize(1100, 700)

        self.image_paths = []
        self.image_path = ""
        self.image_bgr_original = None
        self.image_h = 0
        self.image_w = 0

        self.gcps_by_image = {}
        self.gcps = []
        self.selected_gcp_index = None
        self.last_saved_path = ""
        self.tree_row_map = {}

        # Display / interaction state.
        self.display_scale = 1.0
        self.display_offset_x = 0
        self.display_offset_y = 0
        self.display_w = 0
        self.display_h = 0
        self.tk_image = None
        self.zoom_level = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 20.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._pan_last = None
        self._cached_disp_base = None
        self._cached_disp_key = None

        self._build_ui()
        self._update_view()

    def _build_ui(self):
        self.configure(bg="#f3f6fb")
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # Left preview panel.
        left_frame = ttk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(left_frame, bg="#1f1f1f", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        self.canvas.bind("<Configure>", lambda _e: self._update_view())

        # Right scroll panel.
        right_outer = ttk.Frame(self)
        right_outer.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right_outer.grid_rowconfigure(0, weight=1)
        right_outer.grid_columnconfigure(0, weight=1)

        self.right_canvas = tk.Canvas(right_outer, bg="#f3f6fb", highlightthickness=0)
        self.right_canvas.grid(row=0, column=0, sticky="nsew")
        right_scroll = ttk.Scrollbar(right_outer, orient="vertical", command=self.right_canvas.yview)
        right_scroll.grid(row=0, column=1, sticky="ns")
        self.right_canvas.configure(yscrollcommand=right_scroll.set)
        self.right_content = ttk.Frame(self.right_canvas)
        self.right_window = self.right_canvas.create_window((0, 0), window=self.right_content, anchor="nw")
        self.right_content.bind("<Configure>", self._on_right_content_configure)
        self.right_canvas.bind("<Configure>", self._on_right_canvas_configure)

        # Section 1.
        sec1 = ttk.LabelFrame(self.right_content, text="Section 1 - File controls")
        sec1.pack(fill="x", padx=6, pady=6)
        ttk.Button(sec1, text="Load Image", command=self._load_image).pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(sec1, text="Load Multiple Images", command=self._load_multiple_images).pack(fill="x", padx=8, pady=(0, 4))
        self.lbl_image_file = ttk.Label(sec1, text="Image: not loaded")
        self.lbl_image_file.pack(fill="x", padx=8, pady=(0, 4))
        self.lbl_image_count = ttk.Label(sec1, text="Images loaded: 0")
        self.lbl_image_count.pack(fill="x", padx=8, pady=(0, 4))

        list_wrap = ttk.Frame(sec1)
        list_wrap.pack(fill="x", padx=8, pady=(0, 8))
        self.image_listbox = tk.Listbox(list_wrap, height=5, exportselection=False)
        self.image_listbox.pack(side="left", fill="x", expand=True)
        list_scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.image_listbox.yview)
        list_scroll.pack(side="right", fill="y")
        self.image_listbox.configure(yscrollcommand=list_scroll.set)
        self.image_listbox.bind("<<ListboxSelect>>", self._on_image_list_select)

        zoom_row = ttk.Frame(sec1)
        zoom_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(zoom_row, text="Zoom +", command=lambda: self._zoom_with_factor(1.2)).pack(side="left", padx=(0, 4))
        ttk.Button(zoom_row, text="Zoom -", command=lambda: self._zoom_with_factor(1 / 1.2)).pack(side="left", padx=4)
        ttk.Button(zoom_row, text="Reset View", command=self._reset_zoom_pan).pack(side="left", padx=4)
        self.lbl_zoom = ttk.Label(sec1, text="Zoom: 1.00x")
        self.lbl_zoom.pack(fill="x", padx=8, pady=(0, 8))

        # Section 2.
        sec2 = ttk.LabelFrame(self.right_content, text="Section 2 - GCP table")
        sec2.pack(fill="both", expand=True, padx=6, pady=6)
        cols = ("idx", "u", "v", "wx", "wy", "img")
        self.tree = ttk.Treeview(sec2, columns=cols, show="headings", height=10)
        headers = [
            ("idx", "Index", 55),
            ("u", "Pixel u", 80),
            ("v", "Pixel v", 80),
            ("wx", "World X", 80),
            ("wy", "World Y", 80),
            ("img", "Image", 130),
        ]
        for c, t, w in headers:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        tree_scroll = ttk.Scrollbar(sec2, orient="vertical", command=self.tree.yview)
        tree_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Section 3.
        sec3 = ttk.LabelFrame(self.right_content, text="Section 3 - Point controls")
        sec3.pack(fill="x", padx=6, pady=6)
        ttk.Button(sec3, text="Delete Selected Point", command=self._delete_selected_point).pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(sec3, text="Clear Points (Current Image)", command=self._clear_current_points).pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(sec3, text="Clear Points (All Images)", command=self._clear_all_points).pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(sec3, text="Save Points to CSV", command=self._save_csv).pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(sec3, text="Tip: Left-click add point, Right-click delete nearest point").pack(anchor="w", padx=8, pady=(0, 8))

        # Section 4.
        sec4 = ttk.LabelFrame(self.right_content, text="Section 4 - Results panel")
        sec4.pack(fill="x", padx=6, pady=6)
        self.lbl_current_points = ttk.Label(sec4, text="Current image points: 0")
        self.lbl_current_points.pack(anchor="w", padx=8, pady=(8, 2))
        self.lbl_total_points = ttk.Label(sec4, text="Total points (all images): 0")
        self.lbl_total_points.pack(anchor="w", padx=8, pady=(0, 8))

        # Section 5.
        sec5 = ttk.LabelFrame(self.right_content, text="Section 5 - View controls")
        sec5.pack(fill="x", padx=6, pady=6)
        self.var_show_labels = tk.BooleanVar(value=True)
        self.var_show_only_selected = tk.BooleanVar(value=False)
        ttk.Checkbutton(sec5, text="Show Point Labels", variable=self.var_show_labels, command=self._update_view).pack(fill="x", padx=8, pady=(8, 4))
        ttk.Checkbutton(sec5, text="Highlight Selected Point", variable=self.var_show_only_selected, command=self._update_view).pack(fill="x", padx=8, pady=(4, 8))
        ttk.Label(sec5, text="Table/CSV include points from all loaded images").pack(anchor="w", padx=8, pady=(0, 8))

        # Section 6.
        sec6 = ttk.LabelFrame(self.right_content, text="Section 6 - Save button")
        sec6.pack(fill="x", padx=6, pady=6)
        ttk.Button(sec6, text="Save Points to CSV", command=self._save_csv).pack(fill="x", padx=8, pady=(8, 4))
        self.lbl_save_path = ttk.Label(sec6, text="Last saved: -")
        self.lbl_save_path.pack(fill="x", padx=8, pady=(0, 8))

    def _on_right_content_configure(self, _event):
        self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

    def _on_right_canvas_configure(self, event):
        self.right_canvas.itemconfig(self.right_window, width=event.width)

    def _short_file(self, path):
        if not path:
            return "not loaded"
        base = os.path.basename(path)
        return base if len(base) <= 42 else base[:39] + "..."

    def _reset_zoom_pan(self):
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.lbl_zoom.configure(text=f"Zoom: {self.zoom_level:.2f}x")
        self._update_view()

    def _set_current_image(self, path):
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            messagebox.showerror("Error", f"Failed to load image: {path}")
            return False
        self.image_path = path
        self.image_bgr_original = img
        self.image_h, self.image_w = img.shape[:2]
        if path not in self.gcps_by_image:
            self.gcps_by_image[path] = []
        self.gcps = self.gcps_by_image[path]
        self.selected_gcp_index = None
        self._cached_disp_base = None
        self._cached_disp_key = None
        self.lbl_image_file.configure(text=f"Image: {self._short_file(path)}")
        self._reset_zoom_pan()
        self._refresh_table()
        self._refresh_stats()
        self._update_view()
        return True

    def _load_image(self):
        path = filedialog.askopenfilename(
            title="Load Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("All files", "*.*")],
        )
        if not path:
            return
        self.image_paths = [path]
        self.gcps_by_image = {}
        self._cached_disp_base = None
        self._cached_disp_key = None
        self.image_listbox.delete(0, tk.END)
        self.image_listbox.insert(tk.END, os.path.basename(path))
        self.image_listbox.selection_clear(0, tk.END)
        self.image_listbox.selection_set(0)
        self.lbl_image_count.configure(text=f"Images loaded: {len(self.image_paths)}")
        self._set_current_image(path)

    def _load_multiple_images(self):
        paths = filedialog.askopenfilenames(
            title="Load Multiple Images",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("All files", "*.*")],
        )
        if not paths:
            return
        self.image_paths = list(paths)
        self.gcps_by_image = {}
        self._cached_disp_base = None
        self._cached_disp_key = None
        self.image_listbox.delete(0, tk.END)
        for p in self.image_paths:
            self.image_listbox.insert(tk.END, os.path.basename(p))
        self.image_listbox.selection_clear(0, tk.END)
        self.image_listbox.selection_set(0)
        self.lbl_image_count.configure(text=f"Images loaded: {len(self.image_paths)}")
        self._set_current_image(self.image_paths[0])

    def _on_image_list_select(self, _event):
        sel = self.image_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.image_paths):
            self._set_current_image(self.image_paths[idx])

    def _canvas_to_original_uv(self, x, y):
        if self.image_bgr_original is None:
            return None
        if not (
            self.display_offset_x <= x < self.display_offset_x + self.display_w
            and self.display_offset_y <= y < self.display_offset_y + self.display_h
        ):
            return None
        u = (x - self.display_offset_x) / self.display_scale
        v = (y - self.display_offset_y) / self.display_scale
        u = float(np.clip(u, 0, self.image_w - 1))
        v = float(np.clip(v, 0, self.image_h - 1))
        return u, v

    def _on_mouse_wheel(self, event):
        if self.image_bgr_original is None:
            return
        factor = 1.1 if event.delta > 0 else (1 / 1.1)
        self._zoom_with_factor(factor, event.x, event.y)

    def _zoom_with_factor(self, factor, anchor_x=None, anchor_y=None):
        if self.image_bgr_original is None:
            return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        if anchor_x is None:
            anchor_x = cw / 2.0
        if anchor_y is None:
            anchor_y = ch / 2.0
        uv = self._canvas_to_original_uv(anchor_x, anchor_y)
        if uv is None:
            uv = (self.image_w / 2.0, self.image_h / 2.0)
        u, v = uv
        new_zoom = float(np.clip(self.zoom_level * factor, self.min_zoom, self.max_zoom))
        if abs(new_zoom - self.zoom_level) < 1e-9:
            return
        self.zoom_level = new_zoom
        fit_scale = min(cw / self.image_w, ch / self.image_h)
        new_scale = fit_scale * self.zoom_level
        new_w = self.image_w * new_scale
        new_h = self.image_h * new_scale
        self.pan_x = anchor_x - (u * new_scale) - ((cw - new_w) / 2.0)
        self.pan_y = anchor_y - (v * new_scale) - ((ch - new_h) / 2.0)
        self.lbl_zoom.configure(text=f"Zoom: {self.zoom_level:.2f}x")
        self._update_view()

    def _on_pan_start(self, event):
        self._pan_last = (event.x, event.y)

    def _on_pan_move(self, event):
        if self._pan_last is None:
            return
        dx = event.x - self._pan_last[0]
        dy = event.y - self._pan_last[1]
        self._pan_last = (event.x, event.y)
        self.pan_x += dx
        self.pan_y += dy
        self._update_view()

    def _on_pan_end(self, _event):
        self._pan_last = None

    def _ask_world_xy_dialog(self, gcp_number):
        dlg = tk.Toplevel(self)
        dlg.title(f"Add GCP #{gcp_number} World Coordinates")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        ttk.Label(dlg, text="World X (m)").grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
        ent_x = ttk.Entry(dlg, width=18)
        ent_x.grid(row=0, column=1, padx=10, pady=(10, 4))
        ttk.Label(dlg, text="World Y (m)").grid(row=1, column=0, padx=10, pady=4, sticky="w")
        ent_y = ttk.Entry(dlg, width=18)
        ent_y.grid(row=1, column=1, padx=10, pady=4)
        ent_x.focus_set()
        out = {"v": None}

        def on_ok():
            try:
                out["v"] = (float(ent_x.get().strip()), float(ent_y.get().strip()))
                dlg.destroy()
            except Exception:
                messagebox.showerror("Error", "World X and World Y must be float values.")

        ttk.Button(dlg, text="OK", command=on_ok).grid(row=2, column=0, padx=8, pady=(6, 10))
        ttk.Button(dlg, text="Cancel", command=dlg.destroy).grid(row=2, column=1, padx=8, pady=(6, 10))
        dlg.wait_window()
        return out["v"]

    def _on_left_click(self, event):
        if self.image_bgr_original is None:
            messagebox.showerror("Error", "Load an image first.")
            return
        uv = self._canvas_to_original_uv(event.x, event.y)
        if uv is None:
            return
        vals = self._ask_world_xy_dialog(len(self.gcps) + 1)
        if vals is None:
            return
        world_x, world_y = vals
        u, v = uv
        self.gcps.append(
            {
                "index": len(self.gcps) + 1,
                "u": float(u),
                "v": float(v),
                "world_x": float(world_x),
                "world_y": float(world_y),
            }
        )
        self._refresh_table()
        self._refresh_stats()
        self._update_view()

    def _on_right_click(self, event):
        if not self.gcps:
            return
        uv = self._canvas_to_original_uv(event.x, event.y)
        if uv is None:
            return
        u_click, v_click = uv
        radius_px = max(10.0, 6.0 / max(self.display_scale, 1e-9))
        best_idx = None
        best_d = 1e18
        for i, g in enumerate(self.gcps):
            d = ((g["u"] - u_click) ** 2 + (g["v"] - v_click) ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best_idx = i
        if best_idx is None or best_d > radius_px:
            return
        del self.gcps[best_idx]
        for i, g in enumerate(self.gcps):
            g["index"] = i + 1
        self.selected_gcp_index = None
        self._refresh_table()
        self._refresh_stats()
        self._update_view()

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            self.selected_gcp_index = None
        else:
            item_id = sel[0]
            if item_id in self.tree_row_map:
                row_path, row_local_index = self.tree_row_map[item_id]
                if row_path != self.image_path:
                    self._set_current_image(row_path)
                self.selected_gcp_index = int(row_local_index)
            else:
                self.selected_gcp_index = None
        self._update_view()

    def _delete_selected_point(self):
        if self.selected_gcp_index is None or not self.gcps:
            return
        idx0 = self.selected_gcp_index - 1
        if idx0 < 0 or idx0 >= len(self.gcps):
            return
        del self.gcps[idx0]
        for i, g in enumerate(self.gcps):
            g["index"] = i + 1
        self.selected_gcp_index = None
        self._refresh_table()
        self._refresh_stats()
        self._update_view()

    def _clear_current_points(self):
        if not self.image_path:
            return
        self.gcps_by_image[self.image_path] = []
        self.gcps = self.gcps_by_image[self.image_path]
        self.selected_gcp_index = None
        self._cached_disp_base = None
        self._cached_disp_key = None
        self._refresh_table()
        self._refresh_stats()
        self._update_view()

    def _clear_all_points(self):
        for p in list(self.gcps_by_image.keys()):
            self.gcps_by_image[p] = []
        if self.image_path:
            self.gcps = self.gcps_by_image.get(self.image_path, [])
        self.selected_gcp_index = None
        self._cached_disp_base = None
        self._cached_disp_key = None
        self._refresh_table()
        self._refresh_stats()
        self._update_view()

    def _refresh_stats(self):
        current_n = len(self.gcps)
        total_n = sum(len(v) for v in self.gcps_by_image.values())
        self.lbl_current_points.configure(text=f"Current image points: {current_n}")
        self.lbl_total_points.configure(text=f"Total points (all images): {total_n}")

    def _refresh_table(self):
        self.tree_row_map = {}
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Show all points from all loaded images in one table.
        global_idx = 1
        for path in self.image_paths:
            img_name = os.path.basename(path)
            for g in self.gcps_by_image.get(path, []):
                item_id = self.tree.insert(
                    "",
                    "end",
                    values=(
                        global_idx,
                        f"{g['u']:.2f}",
                        f"{g['v']:.2f}",
                        f"{g['world_x']:.4f}",
                        f"{g['world_y']:.4f}",
                        img_name,
                    ),
                )
                # Keep mapping to exact source point for selection/deletion routing.
                self.tree_row_map[item_id] = (path, int(g["index"]))
                global_idx += 1

    def _draw_points(self, img):
        for g in self.gcps:
            # Draw in display space for speed.
            u = int(round(g["u"] * self.display_scale))
            v = int(round(g["v"] * self.display_scale))
            cv2.circle(img, (u, v), 6, (255, 255, 255), 2, lineType=cv2.LINE_AA)
            cv2.circle(img, (u, v), 5, (0, 0, 255), -1, lineType=cv2.LINE_AA)
            if self.var_show_labels.get():
                txt = f"{g['index']} ({g['world_x']:.2f}, {g['world_y']:.2f})"
                cv2.putText(img, txt, (u + 10, v - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(img, txt, (u + 10, v - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
            if self.var_show_only_selected.get() and self.selected_gcp_index == g["index"]:
                cv2.circle(img, (u, v), 11, (0, 255, 255), 2, lineType=cv2.LINE_AA)

    def _update_view(self):
        self.canvas.delete("all")
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        if self.image_bgr_original is None:
            self.canvas.create_text(cw // 2, ch // 2, text="Load an image to begin", fill="#bbbbbb", font=("Segoe UI", 14, "bold"))
            return

        fit_scale = min(cw / self.image_w, ch / self.image_h)
        self.display_scale = fit_scale * self.zoom_level
        self.display_w = max(1, int(round(self.image_w * self.display_scale)))
        self.display_h = max(1, int(round(self.image_h * self.display_scale)))
        max_pan_x = max((self.display_w - cw) / 2.0, 0.0)
        max_pan_y = max((self.display_h - ch) / 2.0, 0.0)
        self.pan_x = float(np.clip(self.pan_x, -max_pan_x, max_pan_x))
        self.pan_y = float(np.clip(self.pan_y, -max_pan_y, max_pan_y))
        self.display_offset_x = int(round((cw - self.display_w) / 2.0 + self.pan_x))
        self.display_offset_y = int(round((ch - self.display_h) / 2.0 + self.pan_y))

        # Cache resized base image to avoid expensive full-resolution redraw every frame.
        cache_key = (id(self.image_bgr_original), self.display_w, self.display_h)
        if self._cached_disp_key != cache_key or self._cached_disp_base is None:
            interp = cv2.INTER_CUBIC if self.zoom_level > 1.0 else cv2.INTER_AREA
            self._cached_disp_base = cv2.resize(
                self.image_bgr_original, (self.display_w, self.display_h), interpolation=interp
            )
            self._cached_disp_key = cache_key

        disp = self._cached_disp_base.copy()
        self._draw_points(disp)
        ok, enc = cv2.imencode(".ppm", disp)
        if not ok:
            return
        self.tk_image = tk.PhotoImage(data=enc.tobytes(), format="PPM")
        self.canvas.create_image(self.display_offset_x, self.display_offset_y, image=self.tk_image, anchor="nw")

    def _save_csv(self):
        total_n = sum(len(v) for v in self.gcps_by_image.values())
        if total_n == 0:
            messagebox.showerror("Error", "No points to save.")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save points to CSV",
            defaultextension=".csv",
            initialfile="pixel_world_points.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not out_path:
            return
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["image_path", "index", "pixel_u", "pixel_v", "world_x_m", "world_y_m"])
                global_idx = 1
                for path in self.image_paths:
                    pts = self.gcps_by_image.get(path, [])
                    for g in pts:
                        writer.writerow(
                            [
                                path,
                                int(global_idx),
                                float(g["u"]),
                                float(g["v"]),
                                float(g["world_x"]),
                                float(g["world_y"]),
                            ]
                        )
                        global_idx += 1
            self.last_saved_path = out_path
            self.lbl_save_path.configure(text=f"Last saved: {out_path}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save CSV.\n{exc}")


if __name__ == "__main__":
    app = PixelWorldCoordinateCollector()
    app.mainloop()
