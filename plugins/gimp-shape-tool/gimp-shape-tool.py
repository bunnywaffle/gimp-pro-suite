#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
==============================================================================
Vector Shape Tool Plug-in for GIMP 3.0 / 3.2+
==============================================================================
A complete shape generator suite supporting native GIMP 3.2 Vector Layers,
Paths, Rasterized Layers, and Dynamic Selection Marquees.
"""

import sys
import os
import traceback
import gi

gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gegl', '0.4')
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')

from gi.repository import Gimp, GimpUi, Gegl, Gtk, GLib, GObject

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import shape_engine as se
from shape_dialog import ShapeToolDialog

def _(msg):
    return GLib.dgettext(None, msg)

PROC_NAME = "plug-in-vector-shape-tool"


class VectorShapeToolPlugin(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_set_i18n(self, procname):
        return True, 'gimp30-python', None

    def do_query_procedures(self):
        return [PROC_NAME]

    def do_create_procedure(self, name):
        if name == PROC_NAME:
            procedure = Gimp.ImageProcedure.new(
                self, name,
                Gimp.PDBProcType.PLUGIN,
                self.run_shape_tool, None
            )
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.ALWAYS |
                Gimp.ProcedureSensitivityMask.DRAWABLE |
                Gimp.ProcedureSensitivityMask.DRAWABLES |
                Gimp.ProcedureSensitivityMask.NO_DRAWABLES
            )
            procedure.set_attribution(
                "GIMP Community",
                "GIMP Vector Shape Extension",
                "2026"
            )
            procedure.set_documentation(
                _("Vector Shape Tool for GIMP 3.2"),
                _("Generates basic primitives, polygons, stars, arrows, callout bubbles, spirals, and symbols as native Vector Layers, Paths, Raster Layers, or Selections."),
                name
            )
            procedure.set_menu_label(_("Vector _Shape Generator..."))
            procedure.add_menu_path("<Image>/Layer/")
            procedure.add_menu_path("<Image>/Tools/")
            procedure.add_menu_path("<Image>/Filters/Render/")

            return procedure

        return None

    def run_shape_tool(self, procedure, run_mode, image, drawables, config, data):
        try:
            Gegl.init(None)

            # If no active image, automatically create a new canvas
            if image is None:
                image = Gimp.Image.new(1000, 1000, Gimp.ImageBaseType.RGB)
                bg = Gimp.Layer.new(image, "Background", 1000, 1000, Gimp.ImageType.RGBA_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
                bg.fill(Gimp.FillType.WHITE)
                image.insert_layer(bg, None, 0)
                Gimp.Display.new(image)
                Gimp.displays_flush()

            img_w = image.get_width()
            img_h = image.get_height()

            if run_mode == Gimp.RunMode.INTERACTIVE:
                GimpUi.init("gimp-shape-tool")
                dialog = ShapeToolDialog(image)
                response = dialog.run()

                # Clean up any live preview
                dialog._cleanup_preview()

                if response != Gtk.ResponseType.OK:
                    dialog.destroy()
                    Gimp.displays_flush()
                    return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)

                settings = dialog.get_settings()
                dialog.destroy()
            else:
                # Non-interactive default rectangle
                cx, cy = img_w / 2.0, img_h / 2.0
                w, h = min(img_w * 0.5, 400.0), min(img_h * 0.5, 400.0)
                settings = {
                    "path_d": se.generate_rectangle(cx - w / 2.0, cy - h / 2.0, w, h, 20.0, 20.0, 20.0, 20.0, "round"),
                    "target_mode": "vector_layer",
                    "sel_op": "replace",
                    "enable_fill": True,
                    "enable_stroke": False,
                    "fill_gegl": Gimp.context_get_foreground() or Gegl.Color.new("#1976d2"),
                    "stroke_gegl": Gimp.context_get_background() or Gegl.Color.new("#212121"),
                    "stroke_width": 3.0
                }

            path_d = settings["path_d"]
            if not path_d:
                return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

            svg_doc = se.build_svg_document(path_d, img_w, img_h)

            image.undo_group_start()
            try:
                success, paths = image.import_paths_from_string(svg_doc, len(svg_doc), False, False)
                if not success or not paths:
                    image.undo_group_end()
                    Gimp.message(_("Failed to generate vector shape path."))
                    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, None)

                shape_path = paths[0]
                target_mode = settings["target_mode"]
                enable_fill = settings["enable_fill"]
                enable_stroke = settings["enable_stroke"]
                fill_gegl = settings["fill_gegl"]
                stroke_gegl = settings["stroke_gegl"]
                stroke_width = settings["stroke_width"]

                if target_mode == "vector_layer":
                    shape_path.set_name("Vector Shape Path")
                    shape_path.set_visible(False)
                    vec_layer = Gimp.VectorLayer.new(image, shape_path)
                    vec_layer.set_name("Vector Shape Layer")
                    if enable_fill:
                        vec_layer.set_fill_color(fill_gegl)
                        vec_layer.set_enable_fill(True)
                    else:
                        vec_layer.set_enable_fill(False)

                    if enable_stroke and stroke_width > 0:
                        vec_layer.set_stroke_color(stroke_gegl)
                        vec_layer.set_stroke_width(stroke_width)
                        vec_layer.set_enable_stroke(True)
                    else:
                        vec_layer.set_enable_stroke(False)
                        vec_layer.set_stroke_width(0.0)

                    image.insert_layer(vec_layer, None, 0)

                elif target_mode == "vector_path":
                    shape_path.set_name("Vector Shape Path")
                    shape_path.set_visible(True)

                elif target_mode == "raster_layer":
                    shape_path.set_name("Shape Path (Rasterized)")
                    raster_layer = Gimp.Layer.new(
                        image, "Shape Layer",
                        img_w, img_h,
                        Gimp.ImageType.RGBA_IMAGE,
                        100.0, Gimp.LayerMode.NORMAL
                    )
                    raster_layer.fill(Gimp.FillType.TRANSPARENT)
                    image.insert_layer(raster_layer, None, 0)

                    if enable_fill:
                        image.select_item(Gimp.ChannelOps.REPLACE, shape_path)
                        Gimp.context_set_foreground(fill_gegl)
                        raster_layer.edit_fill(Gimp.FillType.FOREGROUND)
                        Gimp.Selection.none(image)

                    if enable_stroke and stroke_width > 0:
                        Gimp.context_set_foreground(stroke_gegl)
                        Gimp.context_set_line_width(stroke_width)
                        shape_path.stroke(raster_layer)

                    image.remove_path(shape_path)

                elif target_mode == "selection":
                    sel_op_str = settings["sel_op"]
                    op_map = {
                        "replace": Gimp.ChannelOps.REPLACE,
                        "add": Gimp.ChannelOps.ADD,
                        "subtract": Gimp.ChannelOps.SUBTRACT,
                        "intersect": Gimp.ChannelOps.INTERSECT
                    }
                    op = op_map.get(sel_op_str, Gimp.ChannelOps.REPLACE)
                    image.select_item(op, shape_path)
                    image.remove_path(shape_path)

                Gimp.displays_flush()
            finally:
                image.undo_group_end()

            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

        except Exception as exc:
            traceback.print_exc()
            Gimp.message(f"Vector Shape Tool Error:\n{str(exc)}")
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error(message=str(exc))
            )


if __name__ == "__main__":
    Gimp.main(VectorShapeToolPlugin.__gtype__, sys.argv)
