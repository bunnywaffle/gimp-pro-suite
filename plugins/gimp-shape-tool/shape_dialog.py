#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
==============================================================================
Streamlined, Modern GTK3 Dialog for GIMP 3.2 Vector Shape Tool
==============================================================================
Features:
- Dynamic context-sensitive parameters: ONLY shows controls for the active shape.
- 100% reliable color picker with FG / BG 1-click presets and exact float RGBA.
- Exact Vector Selection Tracing (turns ANY selection marquee/lasso into a vector shape).
- Authentic Comic Speech Bubbles, Natural Clouds, Heart, and Organic Blobs.
- Interactive continuous size scaling slider + quick multiplier buttons.
- Real-time live canvas preview for fill, stroke, size, and shapes.
"""

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gegl', '0.4')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gimp, GimpUi, Gegl, Gtk, Gdk, GLib, GObject
import xml.etree.ElementTree as ET
import math
import sys
import os

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import shape_engine as se

def _(msg):
    return GLib.dgettext(None, msg)

def rgba_to_gegl(gdk_rgba):
    return Gegl.Color.new(f"rgba({gdk_rgba.red:.6f}, {gdk_rgba.green:.6f}, {gdk_rgba.blue:.6f}, {gdk_rgba.alpha:.6f})")


class ShapeToolDialog(Gtk.Dialog):
    def __init__(self, image):
        super().__init__(
            title=_("Vector Shape Generator"),
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(490, 600)
        self.set_resizable(True)

        self.image = image
        self.preview_layer = None
        self.preview_path = None
        self.last_path_d = None
        self.cached_selection_d = None
        self.update_timeout_id = None
        self.updating_ui = False

        # Image dimensions & Initial placement
        self.img_w = image.get_width() if image else 800
        self.img_h = image.get_height() if image else 800
        self.max_dim = max(self.img_w, self.img_h, 1000)

        self.init_cx = self.img_w / 2.0
        self.init_cy = self.img_h / 2.0
        default_side = min(self.img_w * 0.5, self.img_h * 0.5, 360.0)
        self.init_w = default_side
        self.init_h = default_side

        has_selection = False
        if self.image:
            try:
                selection = self.image.get_selection()
                ret = selection.bounds(self.image)
                non_empty = ret[1] if len(ret) == 6 else (ret[0] if len(ret) == 5 else False)
                x1 = ret[2] if len(ret) == 6 else (ret[1] if len(ret) == 5 else 0)
                y1 = ret[3] if len(ret) == 6 else (ret[2] if len(ret) == 5 else 0)
                x2 = ret[4] if len(ret) == 6 else (ret[3] if len(ret) == 5 else 0)
                y2 = ret[5] if len(ret) == 6 else (ret[4] if len(ret) == 5 else 0)
                if non_empty and (x2 > x1) and (y2 > y1):
                    has_selection = True
                    self.init_cx = (x1 + x2) / 2.0
                    self.init_cy = (y1 + y2) / 2.0
                    sw = float(x2 - x1)
                    sh = float(y2 - y1)
                    self.init_w = sw
                    self.init_h = sh
            except Exception:
                pass

        # Initial RGBA colors
        self.cur_fill_rgba = Gdk.RGBA()
        self.cur_fill_rgba.red = 0.12
        self.cur_fill_rgba.green = 0.53
        self.cur_fill_rgba.blue = 0.90
        self.cur_fill_rgba.alpha = 1.0

        self.cur_stroke_rgba = Gdk.RGBA()
        self.cur_stroke_rgba.red = 0.15
        self.cur_stroke_rgba.green = 0.15
        self.cur_stroke_rgba.blue = 0.15
        self.cur_stroke_rgba.alpha = 1.0

        try:
            fg = Gimp.context_get_foreground()
            if fg and hasattr(fg, 'get_rgba'):
                r, g, b, a = fg.get_rgba()
                self.cur_fill_rgba.red = r
                self.cur_fill_rgba.green = g
                self.cur_fill_rgba.blue = b
                self.cur_fill_rgba.alpha = a
        except Exception:
            pass

        self._build_ui()
        if has_selection:
            self.shape_combo.set_active_id("from_selection")
            self.aspect_lock_check.set_active(False)
            self._extract_selection_svg_d()
        else:
            self.shape_combo.set_active_id("rect")

        self._on_shape_selected(self.shape_combo)
        self._schedule_preview()

    def _build_ui(self):
        # Action buttons
        self.add_button(_("Reset"), Gtk.ResponseType.APPLY)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        create_btn = self.add_button(_("Create Shape"), Gtk.ResponseType.OK)
        create_btn.get_style_context().add_class("suggested-action")

        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(8)
        content.set_margin_bottom(8)

        # -------------------------------------------------------------
        # 1. Shape Selector Dropdown
        # -------------------------------------------------------------
        shape_select_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        shape_label = Gtk.Label(label=_("Shape:"))
        shape_label.set_markup("<b>Shape:</b>")
        shape_label.set_xalign(0)
        shape_select_box.pack_start(shape_label, False, False, 0)

        self.shape_combo = Gtk.ComboBoxText()
        self.shape_combo.append("from_selection", "✨  From Active Selection (Vectorize)")
        self.shape_combo.append("rect", "⬛  Rectangle / Square")
        self.shape_combo.append("ellipse", "⭕  Circle / Ellipse / Pie / Donut")
        self.shape_combo.append("triangle", "🔺  Triangle")
        self.shape_combo.append("ngon", "⬡  Polygon (N-Gon 3–64 sides)")
        self.shape_combo.append("star", "⭐  Star & Starburst")
        self.shape_combo.append("complex_poly", "▱  Parallelogram / Trapezoid / Rhombus")
        self.shape_combo.append("arrow", "➡️  Arrow (Linear, Double, Chevron, Curved)")
        self.shape_combo.append("bubble", "💬  Speech Bubble (Comic / Callout)")
        self.shape_combo.append("cloud", "☁️  Cloud (Fluffy, Cumulus, Rain)")
        self.shape_combo.append("blob", "🫧  Organic Blob (Liquid, Splatter, Droplet)")
        self.shape_combo.append("badge", "🏵️  Badge & Ribbon")
        self.shape_combo.append("spiral", "🌀  Spiral (Archimedean / Golden)")
        self.shape_combo.append("gear", "⚙️  Gear / Cogwheel")
        self.shape_combo.append("symbol", "❤️  Symbols (Heart, Cross, Map Pin)")
        self.shape_combo.set_active(1)
        self.shape_combo.connect("changed", self._on_shape_selected)
        shape_select_box.pack_start(self.shape_combo, True, True, 0)
        content.pack_start(shape_select_box, False, False, 0)

        # -------------------------------------------------------------
        # 2. Dynamic Context-Sensitive Shape Options Stack
        # -------------------------------------------------------------
        self.props_frame = Gtk.Frame(label=_(" Shape Parameters "))
        self.props_stack = Gtk.Stack()
        self.props_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.props_stack.set_margin_start(8)
        self.props_stack.set_margin_end(8)
        self.props_stack.set_margin_top(6)
        self.props_stack.set_margin_bottom(6)
        self.props_frame.add(self.props_stack)
        content.pack_start(self.props_frame, False, False, 0)

        # Build each compact sub-panel
        self._build_from_selection_panel()
        self._build_rect_panel()
        self._build_ellipse_panel()
        self._build_triangle_panel()
        self._build_ngon_panel()
        self._build_star_panel()
        self._build_complex_poly_panel()
        self._build_arrow_panel()
        self._build_bubble_panel()
        self._build_cloud_panel()
        self._build_blob_panel()
        self._build_badge_panel()
        self._build_spiral_panel()
        self._build_gear_panel()
        self._build_symbol_panel()

        # -------------------------------------------------------------
        # 3. Interactive Sizing & Placement Panel
        # -------------------------------------------------------------
        trans_frame = Gtk.Frame(label=_(" Interactive Size & Position "))
        trans_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        trans_box.set_margin_start(8)
        trans_box.set_margin_end(8)
        trans_box.set_margin_top(6)
        trans_box.set_margin_bottom(6)
        trans_frame.add(trans_box)
        content.pack_start(trans_frame, False, False, 0)

        # Continuous Interactive Scale / Size Slider
        size_slider_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        size_slider_box.pack_start(Gtk.Label(label=_("Scale / Size:"), xalign=0), False, False, 0)
        self.size_scale_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, self.max_dim * 1.5, 5)
        self.size_scale_slider.set_value(max(self.init_w, self.init_h))
        self.size_scale_slider.connect("value-changed", self._on_size_slider_changed)
        size_slider_box.pack_start(self.size_scale_slider, True, True, 0)
        trans_box.pack_start(size_slider_box, False, False, 0)

        # Quick Scale Multiplier buttons
        quick_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        m25_btn = Gtk.Button(label="-25%")
        m25_btn.connect("clicked", lambda b: self._scale_shape(0.75))
        quick_btn_box.pack_start(m25_btn, True, True, 0)

        p25_btn = Gtk.Button(label="+25%")
        p25_btn.connect("clicked", lambda b: self._scale_shape(1.25))
        quick_btn_box.pack_start(p25_btn, True, True, 0)

        half_btn = Gtk.Button(label="0.5x")
        half_btn.connect("clicked", lambda b: self._scale_shape(0.5))
        quick_btn_box.pack_start(half_btn, True, True, 0)

        double_btn = Gtk.Button(label="2x")
        double_btn.connect("clicked", lambda b: self._scale_shape(2.0))
        quick_btn_box.pack_start(double_btn, True, True, 0)

        half_canvas_btn = Gtk.Button(label="50% Canvas")
        half_canvas_btn.connect("clicked", self._on_fit_half_canvas)
        quick_btn_box.pack_start(half_canvas_btn, True, True, 0)

        fit_sel_btn = Gtk.Button(label="Fit Selection")
        fit_sel_btn.connect("clicked", self._on_fit_selection)
        quick_btn_box.pack_start(fit_sel_btn, True, True, 0)
        trans_box.pack_start(quick_btn_box, False, False, 0)

        grid1 = Gtk.Grid(column_spacing=8, row_spacing=6)
        trans_box.pack_start(grid1, False, False, 0)

        # Precise Width / Height Spin Buttons + Lock
        grid1.attach(Gtk.Label(label=_("Dimensions:"), xalign=0), 0, 0, 1, 1)
        dim_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dim_box.pack_start(Gtk.Label(label="W:"), False, False, 0)
        self.w_spin = Gtk.SpinButton.new_with_range(2, 50000, 1)
        self.w_spin.set_value(self.init_w)
        self.w_spin.connect("value-changed", self._on_dim_changed)
        dim_box.pack_start(self.w_spin, True, True, 0)

        dim_box.pack_start(Gtk.Label(label="H:"), False, False, 0)
        self.h_spin = Gtk.SpinButton.new_with_range(2, 50000, 1)
        self.h_spin.set_value(self.init_h)
        self.h_spin.connect("value-changed", self._on_dim_changed)
        dim_box.pack_start(self.h_spin, True, True, 0)

        self.aspect_lock_check = Gtk.CheckButton(label=_("🔗 Link 1:1"))
        self.aspect_lock_check.set_active(True)
        self.aspect_lock_check.connect("toggled", self._on_aspect_toggled)
        dim_box.pack_start(self.aspect_lock_check, False, False, 0)
        grid1.attach(dim_box, 1, 0, 1, 1)

        # Position X, Y & Center Button
        grid1.attach(Gtk.Label(label=_("Position:"), xalign=0), 0, 1, 1, 1)
        pos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        pos_box.pack_start(Gtk.Label(label="X:"), False, False, 0)
        self.cx_spin = Gtk.SpinButton.new_with_range(-10000, 50000, 1)
        self.cx_spin.set_value(self.init_cx)
        self.cx_spin.connect("value-changed", self._on_param_changed)
        pos_box.pack_start(self.cx_spin, True, True, 0)

        pos_box.pack_start(Gtk.Label(label="Y:"), False, False, 0)
        self.cy_spin = Gtk.SpinButton.new_with_range(-10000, 50000, 1)
        self.cy_spin.set_value(self.init_cy)
        self.cy_spin.connect("value-changed", self._on_param_changed)
        pos_box.pack_start(self.cy_spin, True, True, 0)

        center_btn = Gtk.Button(label=_("Center in Canvas"))
        center_btn.connect("clicked", self._on_fit_canvas)
        pos_box.pack_start(center_btn, False, False, 0)
        grid1.attach(pos_box, 1, 1, 1, 1)

        # Rotation Slider
        grid1.attach(Gtk.Label(label=_("Rotation:"), xalign=0), 0, 2, 1, 1)
        self.rotation_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -180, 180, 1)
        self.rotation_scale.set_value(0)
        self.rotation_scale.connect("value-changed", self._on_param_changed)
        grid1.attach(self.rotation_scale, 1, 2, 1, 1)

        # -------------------------------------------------------------
        # 4. Style & Output Mode Section
        # -------------------------------------------------------------
        style_frame = Gtk.Frame(label=_(" Appearance & Output Mode "))
        style_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        style_box.set_margin_start(8)
        style_box.set_margin_end(8)
        style_box.set_margin_top(6)
        style_box.set_margin_bottom(6)
        style_frame.add(style_box)
        content.pack_start(style_frame, False, False, 0)

        grid2 = Gtk.Grid(column_spacing=8, row_spacing=6)
        style_box.pack_start(grid2, False, False, 0)

        # Fill & Stroke controls with Gtk.ColorButton
        grid2.attach(Gtk.Label(label=_("Appearance:"), xalign=0), 0, 0, 1, 1)
        app_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.enable_fill_check = Gtk.CheckButton(label=_("Fill"))
        self.enable_fill_check.set_active(True)
        self.enable_fill_check.connect("toggled", self._on_param_changed)
        app_box.pack_start(self.enable_fill_check, False, False, 0)

        self.fill_color_btn = Gtk.ColorButton()
        self.fill_color_btn.set_rgba(self.cur_fill_rgba)
        self.fill_color_btn.connect("color-set", self._on_param_changed)
        app_box.pack_start(self.fill_color_btn, False, False, 0)

        # Quick FG / BG color buttons
        fg_btn = Gtk.Button(label="FG")
        fg_btn.set_tooltip_text(_("Set Fill Color to GIMP Foreground Color"))
        fg_btn.connect("clicked", self._on_set_fg_color)
        app_box.pack_start(fg_btn, False, False, 0)

        self.enable_stroke_check = Gtk.CheckButton(label=_("Stroke"))
        self.enable_stroke_check.set_active(False)
        self.enable_stroke_check.connect("toggled", self._on_param_changed)
        app_box.pack_start(self.enable_stroke_check, False, False, 0)

        self.stroke_color_btn = Gtk.ColorButton()
        self.stroke_color_btn.set_rgba(self.cur_stroke_rgba)
        self.stroke_color_btn.connect("color-set", self._on_param_changed)
        app_box.pack_start(self.stroke_color_btn, False, False, 0)

        app_box.pack_start(Gtk.Label(label="Width:"), False, False, 0)
        self.stroke_width_spin = Gtk.SpinButton.new_with_range(0.5, 100.0, 0.5)
        self.stroke_width_spin.set_value(3.0)
        self.stroke_width_spin.connect("value-changed", self._on_param_changed)
        app_box.pack_start(self.stroke_width_spin, False, False, 0)
        grid2.attach(app_box, 1, 0, 1, 1)

        # Output Target
        grid2.attach(Gtk.Label(label=_("Output To:"), xalign=0), 0, 1, 1, 1)
        out_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.append("vector_layer", "✨ Vector Layer (Native GIMP 3.2)")
        self.output_combo.append("vector_path", "📐 Vector Path (Paths Dock)")
        self.output_combo.append("raster_layer", "🎨 Raster Layer")
        self.output_combo.append("selection", "✨ Selection Marquee")
        self.output_combo.set_active(0)
        self.output_combo.connect("changed", self._on_output_changed)
        out_box.pack_start(self.output_combo, True, True, 0)

        self.sel_op_combo = Gtk.ComboBoxText()
        self.sel_op_combo.append("replace", "Replace")
        self.sel_op_combo.append("add", "Add (+)")
        self.sel_op_combo.append("subtract", "Subtract (-)")
        self.sel_op_combo.append("intersect", "Intersect (∩)")
        self.sel_op_combo.set_active(0)
        self.sel_op_combo.connect("changed", self._on_param_changed)
        self.sel_op_combo.set_visible(False)
        out_box.pack_start(self.sel_op_combo, False, False, 0)
        grid2.attach(out_box, 1, 1, 1, 1)

        self.connect("response", self._on_response)
        self.show_all()

    def _on_set_fg_color(self, btn):
        try:
            fg = Gimp.context_get_foreground()
            if fg and hasattr(fg, 'get_rgba'):
                r, g, b, a = fg.get_rgba()
                rgba = Gdk.RGBA()
                rgba.red, rgba.green, rgba.blue, rgba.alpha = r, g, b, a
                self.fill_color_btn.set_rgba(rgba)
                self._on_param_changed()
        except Exception:
            pass

    # ------------------------------------------------------------------------
    # Compact Shape Panels
    # ------------------------------------------------------------------------
    def _extract_selection_svg_d(self):
        if not self.image:
            return None
        try:
            selection = self.image.get_selection()
            ret = selection.bounds(self.image)
            non_empty = ret[1] if len(ret) == 6 else (ret[0] if len(ret) == 5 else False)
            x1 = ret[2] if len(ret) == 6 else (ret[1] if len(ret) == 5 else 0)
            y1 = ret[3] if len(ret) == 6 else (ret[2] if len(ret) == 5 else 0)
            x2 = ret[4] if len(ret) == 6 else (ret[3] if len(ret) == 5 else 0)
            y2 = ret[5] if len(ret) == 6 else (ret[4] if len(ret) == 5 else 0)
            if not non_empty or x2 <= x1 or y2 <= y1:
                return None

            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure('plug-in-sel2path')
            if not proc:
                return None

            existing_paths = list(self.image.get_paths() or [])
            config = proc.create_config()
            config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
            config.set_property('image', self.image)
            proc.run(config)

            new_paths = [p for p in (self.image.get_paths() or []) if p not in existing_paths]
            if not new_paths:
                return None

            sel_path = new_paths[0]
            svg_str = self.image.export_path_to_string(sel_path)
            try:
                self.image.remove_path(sel_path)
            except Exception:
                pass

            root = ET.fromstring(svg_str)
            d_list = []
            for elem in root.iter():
                if elem.tag.endswith('path') and 'd' in elem.attrib:
                    d_list.append(elem.attrib['d'])
            
            if d_list:
                self.cached_selection_d = ' '.join(d_list)
                return self.cached_selection_d
            return None
        except Exception:
            return None

    def _build_from_selection_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        
        self.sel_status_label = Gtk.Label(label=_("Selection: Scanning..."), xalign=0)
        self.sel_status_label.set_markup("<b>Selection:</b> Checking canvas selection...")
        grid.attach(self.sel_status_label, 0, 0, 2, 1)

        grid.attach(Gtk.Label(label=_("Mode / Geometry:"), xalign=0), 0, 1, 1, 1)
        self.sel_shape_type = Gtk.ComboBoxText()
        self.sel_shape_type.append("exact", "✍️ Exact Selection Outline (Vectorize)")
        self.sel_shape_type.append("rounded_rect", "🔲 Rounded Box (Fitted)")
        self.sel_shape_type.append("rect", "⬛ Rectangle / Box (Fitted)")
        self.sel_shape_type.append("ellipse", "⭕ Ellipse / Circle (Fitted)")
        self.sel_shape_type.append("heart", "❤️ Heart (Fitted)")
        self.sel_shape_type.append("triangle", "🔺 Triangle (Fitted)")
        self.sel_shape_type.append("star", "⭐ Star (Fitted)")
        self.sel_shape_type.append("cloud", "☁️ Cloud (Fitted)")
        self.sel_shape_type.append("blob", "🫧 Organic Blob (Fitted)")
        self.sel_shape_type.set_active(0)
        self.sel_shape_type.connect("changed", self._on_param_changed)
        grid.attach(self.sel_shape_type, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Corner Radius:"), xalign=0), 0, 2, 1, 1)
        self.sel_corner_radius = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 200, 1)
        self.sel_corner_radius.set_value(24.0)
        self.sel_corner_radius.connect("value-changed", self._on_param_changed)
        grid.attach(self.sel_corner_radius, 1, 2, 1, 1)

        refresh_btn = Gtk.Button(label=_("🔄 Re-Scan Canvas Selection"))
        refresh_btn.connect("clicked", self._on_refresh_selection)
        grid.attach(refresh_btn, 0, 3, 2, 1)

        self.props_stack.add_named(grid, "from_selection")

    def _on_refresh_selection(self, btn=None):
        if not self.image:
            self.sel_status_label.set_markup("<i>No active image</i>")
            return
        try:
            selection = self.image.get_selection()
            ret = selection.bounds(self.image)
            non_empty = ret[1] if len(ret) == 6 else (ret[0] if len(ret) == 5 else False)
            x1 = ret[2] if len(ret) == 6 else (ret[1] if len(ret) == 5 else 0)
            y1 = ret[3] if len(ret) == 6 else (ret[2] if len(ret) == 5 else 0)
            x2 = ret[4] if len(ret) == 6 else (ret[3] if len(ret) == 5 else 0)
            y2 = ret[5] if len(ret) == 6 else (ret[4] if len(ret) == 5 else 0)
            if non_empty and (x2 > x1) and (y2 > y1):
                sw = float(x2 - x1)
                sh = float(y2 - y1)
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                self.updating_ui = True
                self.cx_spin.set_value(cx)
                self.cy_spin.set_value(cy)
                self.w_spin.set_value(sw)
                self.h_spin.set_value(sh)
                self.size_scale_slider.set_value(max(sw, sh))
                self.aspect_lock_check.set_active(False)
                self.updating_ui = False
                self._extract_selection_svg_d()
                self.sel_status_label.set_markup(f"<b>Selection:</b> {int(sw)} × {int(sh)} px at ({int(x1)}, {int(y1)})")
                self._schedule_preview()
            else:
                self.cached_selection_d = None
                self.sel_status_label.set_markup("<i>ℹ️ No active selection on canvas.</i>")
        except Exception:
            self.sel_status_label.set_markup("<i>Selection read error</i>")

    def _build_rect_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Corner Fillet:"), xalign=0), 0, 0, 1, 1)
        self.rect_corner_style = Gtk.ComboBoxText()
        self.rect_corner_style.append("round", "Rounded (Smooth)")
        self.rect_corner_style.append("chamfer", "Chamfered / Beveled")
        self.rect_corner_style.append("inverted", "Inverted / Concave")
        self.rect_corner_style.set_active(0)
        self.rect_corner_style.connect("changed", self._on_param_changed)
        grid.attach(self.rect_corner_style, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Corner Radius:"), xalign=0), 0, 1, 1, 1)
        self.rect_radius_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 200, 1)
        self.rect_radius_scale.set_value(20.0)
        self.rect_radius_scale.connect("value-changed", self._on_param_changed)
        grid.attach(self.rect_radius_scale, 1, 1, 1, 1)
        self.props_stack.add_named(grid, "rect")

    def _build_ellipse_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Subtype:"), xalign=0), 0, 0, 1, 1)
        self.ellipse_mode = Gtk.ComboBoxText()
        self.ellipse_mode.append("full", "Full Ellipse / Circle")
        self.ellipse_mode.append("arc", "Open Arc")
        self.ellipse_mode.append("pie", "Pie Slice (Sector)")
        self.ellipse_mode.append("annular", "Donut Wedge (Annular)")
        self.ellipse_mode.set_active(0)
        self.ellipse_mode.connect("changed", self._on_ellipse_mode_changed)
        grid.attach(self.ellipse_mode, 1, 0, 1, 1)

        self.ellipse_angle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.ellipse_angle_row.pack_start(Gtk.Label(label="Start (°):"), False, False, 0)
        self.ellipse_start_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 360, 5)
        self.ellipse_start_scale.set_value(0)
        self.ellipse_start_scale.connect("value-changed", self._on_param_changed)
        self.ellipse_angle_row.pack_start(self.ellipse_start_scale, True, True, 0)

        self.ellipse_angle_row.pack_start(Gtk.Label(label="Sweep (°):"), False, False, 0)
        self.ellipse_sweep_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 360, 5)
        self.ellipse_sweep_scale.set_value(360)
        self.ellipse_sweep_scale.connect("value-changed", self._on_param_changed)
        self.ellipse_angle_row.pack_start(self.ellipse_sweep_scale, True, True, 0)
        grid.attach(self.ellipse_angle_row, 0, 1, 2, 1)
        self.props_stack.add_named(grid, "ellipse")

    def _build_triangle_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Type:"), xalign=0), 0, 0, 1, 1)
        self.triangle_preset = Gtk.ComboBoxText()
        self.triangle_preset.append("equilateral", "Equilateral")
        self.triangle_preset.append("isosceles", "Isosceles")
        self.triangle_preset.append("right_bl", "Right-Angled (Corner Bottom-Left)")
        self.triangle_preset.append("right_br", "Right-Angled (Corner Bottom-Right)")
        self.triangle_preset.append("right_tl", "Right-Angled (Corner Top-Left)")
        self.triangle_preset.append("right_tr", "Right-Angled (Corner Top-Right)")
        self.triangle_preset.set_active(0)
        self.triangle_preset.connect("changed", self._on_param_changed)
        grid.attach(self.triangle_preset, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Corner Fillet:"), xalign=0), 0, 1, 1, 1)
        self.triangle_fillet_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.triangle_fillet_scale.set_value(0)
        self.triangle_fillet_scale.connect("value-changed", self._on_param_changed)
        grid.attach(self.triangle_fillet_scale, 1, 1, 1, 1)
        self.props_stack.add_named(grid, "triangle")

    def _build_ngon_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Sides Count:"), xalign=0), 0, 0, 1, 1)
        self.ngon_sides_spin = Gtk.SpinButton.new_with_range(3, 64, 1)
        self.ngon_sides_spin.set_value(6)
        self.ngon_sides_spin.connect("value-changed", self._on_param_changed)
        grid.attach(self.ngon_sides_spin, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Corner Fillet:"), xalign=0), 0, 1, 1, 1)
        self.ngon_fillet_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.ngon_fillet_scale.set_value(0)
        self.ngon_fillet_scale.connect("value-changed", self._on_param_changed)
        grid.attach(self.ngon_fillet_scale, 1, 1, 1, 1)
        self.props_stack.add_named(grid, "ngon")

    def _build_star_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Points:"), xalign=0), 0, 0, 1, 1)
        self.star_points_spin = Gtk.SpinButton.new_with_range(3, 32, 1)
        self.star_points_spin.set_value(5)
        self.star_points_spin.connect("value-changed", self._on_param_changed)
        grid.attach(self.star_points_spin, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Inner Radius (%):"), xalign=0), 0, 1, 1, 1)
        self.star_inner_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 95, 1)
        self.star_inner_scale.set_value(45)
        self.star_inner_scale.connect("value-changed", self._on_param_changed)
        grid.attach(self.star_inner_scale, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Style:"), xalign=0), 0, 2, 1, 1)
        self.starburst_mode = Gtk.ComboBoxText()
        self.starburst_mode.append("standard", "Standard Star")
        self.starburst_mode.append("burst_multi", "Starburst (Alternating Rays)")
        self.starburst_mode.set_active(0)
        self.starburst_mode.connect("changed", self._on_param_changed)
        grid.attach(self.starburst_mode, 1, 2, 1, 1)
        self.props_stack.add_named(grid, "star")

    def _build_complex_poly_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Type:"), xalign=0), 0, 0, 1, 1)
        self.complex_poly_type = Gtk.ComboBoxText()
        self.complex_poly_type.append("parallelogram", "Parallelogram (Skewed)")
        self.complex_poly_type.append("trapezoid", "Trapezoid / Trapezium")
        self.complex_poly_type.append("rhombus", "Rhombus / Diamond")
        self.complex_poly_type.append("hexagon", "Regular Hexagon (6)")
        self.complex_poly_type.append("octagon", "Regular Octagon (8)")
        self.complex_poly_type.set_active(0)
        self.complex_poly_type.connect("changed", self._on_param_changed)
        grid.attach(self.complex_poly_type, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Skew / Width Ratio:"), xalign=0), 0, 1, 1, 1)
        self.complex_poly_skew = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -60, 60, 1)
        self.complex_poly_skew.set_value(20)
        self.complex_poly_skew.connect("value-changed", self._on_param_changed)
        grid.attach(self.complex_poly_skew, 1, 1, 1, 1)
        self.props_stack.add_named(grid, "complex_poly")

    def _build_arrow_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Arrow Type:"), xalign=0), 0, 0, 1, 1)
        self.arrow_type = Gtk.ComboBoxText()
        self.arrow_type.append("arrow_linear", "Linear Arrow (Single Head)")
        self.arrow_type.append("arrow_double", "Double-Headed Arrow")
        self.arrow_type.append("arrow_chevron", "Chevron / Block Arrow")
        self.arrow_type.append("arrow_curved", "Curved / Arc Arrow")
        self.arrow_type.set_active(0)
        self.arrow_type.connect("changed", self._on_param_changed)
        grid.attach(self.arrow_type, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Shaft Width (%):"), xalign=0), 0, 1, 1, 1)
        self.arrow_shaft_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 80, 1)
        self.arrow_shaft_scale.set_value(40)
        self.arrow_shaft_scale.connect("value-changed", self._on_param_changed)
        grid.attach(self.arrow_shaft_scale, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Head Size (%):"), xalign=0), 0, 2, 1, 1)
        self.arrow_head_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 80, 1)
        self.arrow_head_scale.set_value(40)
        self.arrow_head_scale.connect("value-changed", self._on_param_changed)
        grid.attach(self.arrow_head_scale, 1, 2, 1, 1)
        self.props_stack.add_named(grid, "arrow")

    def _build_bubble_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Bubble Style:"), xalign=0), 0, 0, 1, 1)
        self.bubble_style = Gtk.ComboBoxText()
        self.bubble_style.append("rounded", "Rounded Callout")
        self.bubble_style.append("rect", "Rectangular Callout")
        self.bubble_style.append("oval", "Oval Callout")
        self.bubble_style.append("thought_cloud", "Thought Cloud")
        self.bubble_style.set_active(0)
        self.bubble_style.connect("changed", self._on_param_changed)
        grid.attach(self.bubble_style, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Tail Position:"), xalign=0), 0, 1, 1, 1)
        self.bubble_tail_pos = Gtk.ComboBoxText()
        self.bubble_tail_pos.append("bottom_left", "Bottom-Left")
        self.bubble_tail_pos.append("bottom_center", "Bottom-Center")
        self.bubble_tail_pos.append("bottom_right", "Bottom-Right")
        self.bubble_tail_pos.append("top_left", "Top-Left")
        self.bubble_tail_pos.append("top_right", "Top-Right")
        self.bubble_tail_pos.append("left", "Left")
        self.bubble_tail_pos.append("right", "Right")
        self.bubble_tail_pos.set_active(0)
        self.bubble_tail_pos.connect("changed", self._on_param_changed)
        grid.attach(self.bubble_tail_pos, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Tail Length (%):"), xalign=0), 0, 2, 1, 1)
        self.bubble_tail_len = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 15, 70, 1)
        self.bubble_tail_len.set_value(35)
        self.bubble_tail_len.connect("value-changed", self._on_param_changed)
        grid.attach(self.bubble_tail_len, 1, 2, 1, 1)
        self.props_stack.add_named(grid, "bubble")

    def _build_cloud_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Cloud Style:"), xalign=0), 0, 0, 1, 1)
        self.cloud_type = Gtk.ComboBoxText()
        self.cloud_type.append("cumulus", "Cumulus Cloud (Classic Flat Base)")
        self.cloud_type.append("fluffy_round", "Fluffy Round Cloud (360° Puffs)")
        self.cloud_type.append("rain_cloud", "Rain Cloud (with Drops)")
        self.cloud_type.set_active(0)
        self.cloud_type.connect("changed", self._on_param_changed)
        grid.attach(self.cloud_type, 1, 0, 1, 1)
        self.props_stack.add_named(grid, "cloud")

    def _build_blob_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Blob Lobes:"), xalign=0), 0, 0, 1, 1)
        self.blob_nodes = Gtk.SpinButton.new_with_range(3, 12, 1)
        self.blob_nodes.set_value(6)
        self.blob_nodes.connect("value-changed", self._on_param_changed)
        grid.attach(self.blob_nodes, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Random Seed:"), xalign=0), 0, 1, 1, 1)
        seed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.blob_seed_spin = Gtk.SpinButton.new_with_range(1, 999, 1)
        self.blob_seed_spin.set_value(1)
        self.blob_seed_spin.connect("value-changed", self._on_param_changed)
        seed_box.pack_start(self.blob_seed_spin, True, True, 0)
        
        rand_btn = Gtk.Button(label="🎲 Shuffle")
        rand_btn.connect("clicked", lambda b: self.blob_seed_spin.set_value(self.blob_seed_spin.get_value() + 1))
        seed_box.pack_start(rand_btn, False, False, 0)
        grid.attach(seed_box, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Deformation (%):"), xalign=0), 0, 2, 1, 1)
        self.blob_contrast = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 60, 1)
        self.blob_contrast.set_value(28)
        self.blob_contrast.connect("value-changed", self._on_param_changed)
        grid.attach(self.blob_contrast, 1, 2, 1, 1)
        self.props_stack.add_named(grid, "blob")

    def _build_badge_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Badge Style:"), xalign=0), 0, 0, 1, 1)
        self.badge_style = Gtk.ComboBoxText()
        self.badge_style.append("badge_scallop", "Scalloped Rosette / Seal")
        self.badge_style.append("badge_banner", "Banner Ribbon (Notched Ends)")
        self.badge_style.append("badge_award", "Award Ribbon (Rosette with Tails)")
        self.badge_style.set_active(0)
        self.badge_style.connect("changed", self._on_param_changed)
        grid.attach(self.badge_style, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Scallops / Waves:"), xalign=0), 0, 1, 1, 1)
        self.badge_scallop_spin = Gtk.SpinButton.new_with_range(6, 64, 1)
        self.badge_scallop_spin.set_value(16)
        self.badge_scallop_spin.connect("value-changed", self._on_param_changed)
        grid.attach(self.badge_scallop_spin, 1, 1, 1, 1)
        self.props_stack.add_named(grid, "badge")

    def _build_spiral_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Spiral Type:"), xalign=0), 0, 0, 1, 1)
        self.spiral_type = Gtk.ComboBoxText()
        self.spiral_type.append("spiral_arch", "Archimedean Spiral")
        self.spiral_type.append("spiral_log", "Logarithmic (Golden Ratio)")
        self.spiral_type.set_active(0)
        self.spiral_type.connect("changed", self._on_param_changed)
        grid.attach(self.spiral_type, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Turns Count:"), xalign=0), 0, 1, 1, 1)
        self.spiral_turns = Gtk.SpinButton.new_with_range(1, 20, 0.5)
        self.spiral_turns.set_value(4)
        self.spiral_turns.connect("value-changed", self._on_param_changed)
        grid.attach(self.spiral_turns, 1, 1, 1, 1)
        self.props_stack.add_named(grid, "spiral")

    def _build_gear_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Teeth Count:"), xalign=0), 0, 0, 1, 1)
        self.gear_teeth = Gtk.SpinButton.new_with_range(4, 48, 1)
        self.gear_teeth.set_value(12)
        self.gear_teeth.connect("value-changed", self._on_param_changed)
        grid.attach(self.gear_teeth, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Tooth Depth (%):"), xalign=0), 0, 1, 1, 1)
        self.gear_depth = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 80, 1)
        self.gear_depth.set_value(30)
        self.gear_depth.connect("value-changed", self._on_param_changed)
        grid.attach(self.gear_depth, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Center Bore (%):"), xalign=0), 0, 2, 1, 1)
        self.gear_hole = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 80, 1)
        self.gear_hole.set_value(30)
        self.gear_hole.connect("value-changed", self._on_param_changed)
        grid.attach(self.gear_hole, 1, 2, 1, 1)
        self.props_stack.add_named(grid, "gear")

    def _build_symbol_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, border_width=4)
        grid.attach(Gtk.Label(label=_("Symbol:"), xalign=0), 0, 0, 1, 1)
        self.symbol_type = Gtk.ComboBoxText()
        self.symbol_type.append("heart", "Heart (Classic Vector)")
        self.symbol_type.append("cross", "Cross / Plus Symbol")
        self.symbol_type.append("map_pin", "Map Marker / Location Pin")
        self.symbol_type.set_active(0)
        self.symbol_type.connect("changed", self._on_param_changed)
        grid.attach(self.symbol_type, 1, 0, 1, 1)
        self.props_stack.add_named(grid, "symbol")

    # ------------------------------------------------------------------------
    # Dynamic Visibility & Sizing Callbacks
    # ------------------------------------------------------------------------
    def _on_shape_selected(self, combo):
        active_id = combo.get_active_id() or "rect"
        self.props_stack.set_visible_child_name(active_id)
        if active_id == "from_selection":
            self._on_refresh_selection()
        self._schedule_preview()

    def _on_ellipse_mode_changed(self, combo):
        mode = combo.get_active_id()
        self.ellipse_angle_row.set_visible(mode != "full")
        self._on_param_changed()

    def _on_output_changed(self, combo):
        is_sel = combo.get_active_id() == "selection"
        self.sel_op_combo.set_visible(is_sel)
        self._on_param_changed()

    def _on_aspect_toggled(self, check):
        if check.get_active():
            val = min(self.w_spin.get_value(), self.h_spin.get_value())
            self.updating_ui = True
            self.w_spin.set_value(val)
            self.h_spin.set_value(val)
            self.size_scale_slider.set_value(val)
            self.updating_ui = False
            self._schedule_preview()

    def _on_size_slider_changed(self, slider):
        if self.updating_ui:
            return
        new_size = slider.get_value()
        self.updating_ui = True
        cur_w = self.w_spin.get_value()
        cur_h = self.h_spin.get_value()
        if self.aspect_lock_check.get_active():
            self.w_spin.set_value(new_size)
            self.h_spin.set_value(new_size)
        else:
            ratio = cur_h / cur_w if cur_w > 0 else 1.0
            self.w_spin.set_value(new_size)
            self.h_spin.set_value(new_size * ratio)
        self.updating_ui = False
        self._schedule_preview()

    def _scale_shape(self, factor):
        self.updating_ui = True
        cur_w = self.w_spin.get_value() * factor
        cur_h = self.h_spin.get_value() * factor
        self.w_spin.set_value(cur_w)
        self.h_spin.set_value(cur_h)
        self.size_scale_slider.set_value(max(cur_w, cur_h))
        self.updating_ui = False
        self._schedule_preview()

    def _on_dim_changed(self, spin):
        if not self.updating_ui and self.aspect_lock_check.get_active():
            self.updating_ui = True
            val = spin.get_value()
            self.w_spin.set_value(val)
            self.h_spin.set_value(val)
            self.size_scale_slider.set_value(val)
            self.updating_ui = False
        self._on_param_changed()

    def _on_fit_selection(self, btn):
        if not self.image:
            return
        try:
            selection = self.image.get_selection()
            ret = selection.bounds(self.image)
            non_empty = ret[1] if len(ret) == 6 else (ret[0] if len(ret) == 5 else False)
            x1 = ret[2] if len(ret) == 6 else (ret[1] if len(ret) == 5 else 0)
            y1 = ret[3] if len(ret) == 6 else (ret[2] if len(ret) == 5 else 0)
            x2 = ret[4] if len(ret) == 6 else (ret[3] if len(ret) == 5 else 0)
            y2 = ret[5] if len(ret) == 6 else (ret[4] if len(ret) == 5 else 0)
            if non_empty and (x2 > x1) and (y2 > y1):
                self.updating_ui = True
                self.cx_spin.set_value((x1 + x2) / 2.0)
                self.cy_spin.set_value((y1 + y2) / 2.0)
                sw = float(x2 - x1)
                sh = float(y2 - y1)
                if self.aspect_lock_check.get_active():
                    side = min(sw, sh)
                    self.w_spin.set_value(side)
                    self.h_spin.set_value(side)
                    self.size_scale_slider.set_value(side)
                else:
                    self.w_spin.set_value(sw)
                    self.h_spin.set_value(sh)
                    self.size_scale_slider.set_value(max(sw, sh))
                self.updating_ui = False
                self._schedule_preview()
        except Exception:
            pass

    def _on_fit_half_canvas(self, btn):
        self.updating_ui = True
        side = min(self.img_w, self.img_h) * 0.5
        self.w_spin.set_value(side)
        self.h_spin.set_value(side)
        self.size_scale_slider.set_value(side)
        self.updating_ui = False
        self._schedule_preview()

    def _on_fit_canvas(self, btn):
        self.updating_ui = True
        self.cx_spin.set_value(self.img_w / 2.0)
        self.cy_spin.set_value(self.img_h / 2.0)
        self.updating_ui = False
        self._schedule_preview()

    def _on_param_changed(self, *args):
        if self.updating_ui:
            return
        self._schedule_preview()

    def _schedule_preview(self, delay_ms=25):
        if self.update_timeout_id is not None:
            GLib.source_remove(self.update_timeout_id)
        self.update_timeout_id = GLib.timeout_add(delay_ms, self._update_preview)

    # ------------------------------------------------------------------------
    # Generate SVG Path from Active Shape
    # ------------------------------------------------------------------------
    def generate_current_path_d(self):
        shape = self.shape_combo.get_active_id() or "rect"
        cx = self.cx_spin.get_value()
        cy = self.cy_spin.get_value()
        w = self.w_spin.get_value()
        h = self.h_spin.get_value()
        rot = self.rotation_scale.get_value()

        if shape == "from_selection":
            stype = self.sel_shape_type.get_active_id() or "exact"
            rad = self.sel_corner_radius.get_value()
            if stype == "exact":
                if not self.cached_selection_d:
                    self._extract_selection_svg_d()
                if self.cached_selection_d:
                    return self.cached_selection_d
                return se.generate_rectangle(cx - w / 2.0, cy - h / 2.0, w, h, 0, 0, 0, 0)
            elif stype == "rect":
                return se.generate_rectangle(cx - w / 2.0, cy - h / 2.0, w, h, 0, 0, 0, 0)
            elif stype == "rounded_rect":
                return se.generate_rectangle(cx - w / 2.0, cy - h / 2.0, w, h, rad, rad, rad, rad, "round")
            elif stype == "ellipse":
                return se.generate_ellipse(cx, cy, w / 2.0, h / 2.0, mode="full")
            elif stype == "heart":
                return se.generate_heart(cx, cy, w, h)
            elif stype == "triangle":
                return se.generate_triangle(cx, cy, w, h, "equilateral", corner_radius=rad)
            elif stype == "star":
                return se.generate_star(cx, cy, w / 2.0, h / 2.0, inner_ratio=0.5, points=5, corner_radius=rad * 0.2)
            elif stype == "cloud":
                return se.generate_cloud(cx, cy, w, h, "cumulus")
            elif stype == "blob":
                return se.generate_organic_blob(cx, cy, w, h, complexity=6, seed=1, contrast=0.28)

        elif shape == "rect":
            style = self.rect_corner_style.get_active_id()
            r_val = self.rect_radius_scale.get_value()
            return se.generate_rectangle(cx - w / 2.0, cy - h / 2.0, w, h, r_val, r_val, r_val, r_val, corner_style=style)

        elif shape == "ellipse":
            mode = self.ellipse_mode.get_active_id()
            start_ang = self.ellipse_start_scale.get_value() + rot
            sweep_ang = self.ellipse_sweep_scale.get_value()
            end_ang = start_ang + sweep_ang
            inner_r = 0.5 if mode == "annular" else 0.0
            return se.generate_ellipse(cx, cy, w / 2.0, h / 2.0, start_angle_deg=start_ang, end_angle_deg=end_ang, mode=mode, inner_ratio=inner_r)

        elif shape == "triangle":
            preset = self.triangle_preset.get_active_id()
            r_fillet = self.triangle_fillet_scale.get_value()
            return se.generate_triangle(cx, cy, w, h, preset=preset, corner_radius=r_fillet)

        elif shape == "ngon":
            sides = int(self.ngon_sides_spin.get_value())
            c_rad = self.ngon_fillet_scale.get_value()
            return se.generate_regular_polygon(cx, cy, w / 2.0, h / 2.0, sides=sides, rotation_deg=rot, corner_radius=c_rad)

        elif shape == "star":
            points = int(self.star_points_spin.get_value())
            in_ratio = self.star_inner_scale.get_value() / 100.0
            burst = self.starburst_mode.get_active_id()
            return se.generate_star(cx, cy, w / 2.0, h / 2.0, inner_ratio=in_ratio, points=points, rotation_deg=rot, starburst_mode=burst)

        elif shape == "complex_poly":
            ptype = self.complex_poly_type.get_active_id()
            skew = self.complex_poly_skew.get_value()
            if ptype == "parallelogram":
                return se.generate_parallelogram(cx, cy, w, h, skew_deg=skew)
            elif ptype == "trapezoid":
                top_ratio = max(0.1, (skew + 60.0) / 120.0)
                return se.generate_trapezoid(cx, cy, w, h, top_ratio=top_ratio)
            elif ptype == "rhombus":
                return se.generate_rhombus(cx, cy, w, h)
            elif ptype == "hexagon":
                return se.generate_hexagon_octagon(cx, cy, w / 2.0, h / 2.0, sides=6)
            elif ptype == "octagon":
                return se.generate_hexagon_octagon(cx, cy, w / 2.0, h / 2.0, sides=8)

        elif shape == "arrow":
            atype = self.arrow_type.get_active_id()
            shaft_r = self.arrow_shaft_scale.get_value() / 100.0
            head_len = self.arrow_head_scale.get_value() / 100.0
            if atype == "arrow_linear":
                return se.generate_arrow(cx, cy, w, h, arrow_type="linear", shaft_ratio=shaft_r, head_len_ratio=head_len, rotation_deg=rot)
            elif atype == "arrow_double":
                return se.generate_arrow(cx, cy, w, h, arrow_type="linear", shaft_ratio=shaft_r, head_len_ratio=head_len, double_headed=True, rotation_deg=rot)
            elif atype == "arrow_chevron":
                return se.generate_arrow(cx, cy, w, h, arrow_type="chevron", shaft_ratio=shaft_r, head_len_ratio=head_len, rotation_deg=rot)
            elif atype == "arrow_curved":
                return se.generate_arrow(cx, cy, w, h, arrow_type="curved", shaft_ratio=shaft_r, head_len_ratio=head_len)

        elif shape == "bubble":
            btype = self.bubble_style.get_active_id()
            tpos = self.bubble_tail_pos.get_active_id() or "bottom_left"
            tlen = self.bubble_tail_len.get_value() / 100.0
            return se.generate_speech_bubble(cx, cy, w, h, bubble_type=btype, corner_radius=18.0, tail_pos=tpos, tail_length=tlen, tail_width=0.25)

        elif shape == "cloud":
            ctype = self.cloud_type.get_active_id() or "cumulus"
            return se.generate_cloud(cx, cy, w, h, cloud_type=ctype)

        elif shape == "blob":
            nodes = int(self.blob_nodes.get_value())
            seed = int(self.blob_seed_spin.get_value())
            contrast = self.blob_contrast.get_value() / 100.0
            return se.generate_organic_blob(cx, cy, w, h, complexity=nodes, seed=seed, contrast=contrast)

        elif shape == "badge":
            bstyle = self.badge_style.get_active_id()
            scallops = int(self.badge_scallop_spin.get_value())
            if bstyle == "badge_scallop":
                return se.generate_scalloped_badge(cx, cy, w / 2.0, h / 2.0, scallops=scallops)
            elif bstyle == "badge_banner":
                return se.generate_banner_ribbon(cx, cy, w, h)
            elif bstyle == "badge_award":
                return se.generate_award_ribbon(cx, cy, radius=min(w, h) * 0.35, scallops=scallops)

        elif shape == "spiral":
            stype = self.spiral_type.get_active_id()
            turns = self.spiral_turns.get_value()
            if stype == "spiral_arch":
                return se.generate_spiral(cx, cy, max_radius=min(w, h) / 2.0, turns=turns, spiral_type="archimedean")
            else:
                return se.generate_spiral(cx, cy, max_radius=min(w, h) / 2.0, turns=turns, spiral_type="logarithmic")

        elif shape == "gear":
            teeth = int(self.gear_teeth.get_value())
            depth_r = self.gear_depth.get_value() / 100.0
            hole_r = self.gear_hole.get_value() / 100.0
            return se.generate_gear(cx, cy, outer_r=min(w, h) / 2.0, teeth=teeth, tooth_depth_ratio=depth_r, hole_ratio=hole_r)

        elif shape == "symbol":
            sym = self.symbol_type.get_active_id()
            if sym == "heart":
                return se.generate_heart(cx, cy, w, h)
            elif sym == "cross":
                return se.generate_cross(cx, cy, w, h, arm_thickness_ratio=0.35, corner_radius=4.0)
            elif sym == "map_pin":
                return se.generate_map_pin(cx, cy, w, h, hole_ratio=0.35)

        return se.generate_rectangle(cx - w / 2.0, cy - h / 2.0, w, h)

    def get_settings(self):
        f_rgba = self.fill_color_btn.get_rgba()
        s_rgba = self.stroke_color_btn.get_rgba()
        return {
            "path_d": self.generate_current_path_d(),
            "target_mode": self.output_combo.get_active_id(),
            "sel_op": self.sel_op_combo.get_active_id(),
            "enable_fill": self.enable_fill_check.get_active(),
            "enable_stroke": self.enable_stroke_check.get_active(),
            "fill_gegl": rgba_to_gegl(f_rgba),
            "stroke_gegl": rgba_to_gegl(s_rgba),
            "stroke_width": float(self.stroke_width_spin.get_value()),
        }

    # ------------------------------------------------------------------------
    # Live Preview (Fast-Path In-Place Color Updates + Throttled Geometry)
    # ------------------------------------------------------------------------
    def _cleanup_preview(self):
        if not self.image:
            return
        if self.preview_layer is not None:
            try:
                if self.preview_layer in self.image.get_layers():
                    self.image.remove_layer(self.preview_layer)
            except Exception:
                pass
            self.preview_layer = None

        if self.preview_path is not None:
            try:
                if self.preview_path in self.image.get_paths():
                    self.image.remove_path(self.preview_path)
            except Exception:
                pass
            self.preview_path = None
        self.last_path_d = None

    def _update_preview(self):
        self.update_timeout_id = None
        if not self.image:
            return False

        path_d = self.generate_current_path_d()
        if not path_d:
            self._cleanup_preview()
            Gimp.displays_flush()
            return False

        enable_fill = self.enable_fill_check.get_active()
        enable_stroke = self.enable_stroke_check.get_active()
        f_rgba = self.fill_color_btn.get_rgba()
        s_rgba = self.stroke_color_btn.get_rgba()
        fill_gegl = rgba_to_gegl(f_rgba)
        stroke_gegl = rgba_to_gegl(s_rgba)
        stroke_w = float(self.stroke_width_spin.get_value())
        target_mode = self.output_combo.get_active_id()

        # FAST-PATH: If geometry is unchanged and preview_layer is active, update colors in-place (<1ms)
        if (target_mode != "vector_path" and
            self.preview_layer is not None and
            self.preview_layer in self.image.get_layers() and
            path_d == self.last_path_d):
            
            try:
                if enable_fill:
                    self.preview_layer.set_fill_color(fill_gegl)
                    self.preview_layer.set_enable_fill(True)
                else:
                    self.preview_layer.set_enable_fill(False)

                if enable_stroke and stroke_w > 0:
                    self.preview_layer.set_stroke_color(stroke_gegl)
                    self.preview_layer.set_stroke_width(stroke_w)
                    self.preview_layer.set_enable_stroke(True)
                else:
                    self.preview_layer.set_enable_stroke(False)
                    self.preview_layer.set_stroke_width(0.0)

                Gimp.displays_flush()
                return False
            except Exception:
                pass

        # FULL-PATH: Geometry changed or layer newly created
        svg_doc = se.build_svg_document(path_d, self.img_w, self.img_h)

        try:
            self._cleanup_preview()
            success, paths = self.image.import_paths_from_string(svg_doc, len(svg_doc), False, False)
            if success and paths:
                self.preview_path = paths[0]
                self.preview_path.set_name("[Preview Path]")
                self.last_path_d = path_d

                if target_mode != "vector_path":
                    vec = Gimp.VectorLayer.new(self.image, self.preview_path)
                    vec.set_name("[Preview Shape]")
                    if enable_fill:
                        vec.set_fill_color(fill_gegl)
                        vec.set_enable_fill(True)
                    else:
                        vec.set_enable_fill(False)

                    if enable_stroke and stroke_w > 0:
                        vec.set_stroke_color(stroke_gegl)
                        vec.set_stroke_width(stroke_w)
                        vec.set_enable_stroke(True)
                    else:
                        vec.set_enable_stroke(False)
                        vec.set_stroke_width(0.0)

                    self.image.insert_layer(vec, None, 0)
                    self.preview_layer = vec
                    self.preview_path.set_visible(False)
                else:
                    self.preview_path.set_visible(True)

                Gimp.displays_flush()
        except Exception:
            pass

        return False

    def _on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.APPLY:
            self.updating_ui = True
            self.cx_spin.set_value(self.init_cx)
            self.cy_spin.set_value(self.init_cy)
            self.w_spin.set_value(self.init_w)
            self.h_spin.set_value(self.init_h)
            self.size_scale_slider.set_value(max(self.init_w, self.init_h))
            self.aspect_lock_check.set_active(True)
            self.rotation_scale.set_value(0)
            self.enable_fill_check.set_active(True)
            self.enable_stroke_check.set_active(False)
            self.updating_ui = False
            self._schedule_preview()
