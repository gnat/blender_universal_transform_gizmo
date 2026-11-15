# SPDX-License-Identifier: GPL-3.0-or-later
"""Universal Transform Gizmo"""

bl_info = {
	"name": "Universal Transform Gizmo",
	"author": "Nathaniel Sabanski",
	"version": (1, 0, 0),
	"blender": (5, 2, 0),
	"location": "3D View > Sidebar > Universal",
	"description": "Improved universal transform gizmo",
	"doc_url": "https://extensions.blender.org/add-ons/universal-transform-gizmo",
	"tracker_url": "https://github.com/gnat/blender_universal_transform_gizmo",
	"category": "3D View",
}

import bpy
from . import settings, interaction, gizmos, controls, keymaps

_CLASSES = (*settings.CLASSES, *interaction.CLASSES, *gizmos.CLASSES, *controls.CLASSES, *keymaps.CLASSES)

def register():
	for cls in _CLASSES:
		bpy.utils.register_class(cls)
	bpy.types.WindowManager.universal_gizmo_enabled = bpy.props.BoolProperty(
		name="Universal Transform Gizmo", default=True,
		description="Show / Hide the Universal Transform Gizmo",
		update=settings.update_visibility,
	)
	bpy.types.WindowManager.universal_gizmo_visible = bpy.props.BoolProperty(
		name="Gizmo Visibility", default=True,
		description="Show the gizmo while keeping its visibility button available",
		update=settings.redraw,
	)
	bpy.types.VIEW3D_HT_header.append(settings.draw_header)
	gizmos.register_draw_handlers()
	keymaps.register()

def unregister():
	interaction.shutdown()
	keymaps.unregister()
	gizmos.unregister_draw_handlers()
	bpy.types.VIEW3D_HT_header.remove(settings.draw_header)
	del bpy.types.WindowManager.universal_gizmo_enabled
	del bpy.types.WindowManager.universal_gizmo_visible
	for cls in reversed(_CLASSES):
		bpy.utils.unregister_class(cls)
