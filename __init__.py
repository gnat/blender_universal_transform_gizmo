# SPDX-License-Identifier: GPL-3.0-or-later
"""Universal Transform Gizmo"""

bl_info = {
	"name": "Universal Transform Gizmo",
	"author": "Nathaniel Sabanski",
	"version": (1, 0, 0),
	"blender": (5, 3, 0),
	"location": "3D View > Sidebar > Universal",
	"description": "Design improvments inspired by SDF Modeler, MagicaCSG, Unreal Engine!",
	"doc_url": "https://github.com/gnat/blender_universal_transform_gizmo",
	"tracker_url": "https://github.com/gnat/blender_universal_transform_gizmo",
	"category": "3D View",
}

import bpy
from . import settings, interaction, gizmos

_CLASSES = (*settings.CLASSES, *interaction.CLASSES, *gizmos.CLASSES)

def register():
	for cls in _CLASSES:
		bpy.utils.register_class(cls)
	bpy.types.WindowManager.universal_gizmo_enabled = bpy.props.BoolProperty(
		name="Universal Transform Gizmo", default=True,
		description="Show the universal gizmo for objects and mesh selections",
		update=settings.redraw,
	)
	bpy.types.VIEW3D_HT_header.append(settings.draw_header)
	gizmos.register_draw_handlers()

def unregister():
	interaction.shutdown()
	gizmos.unregister_draw_handlers()
	bpy.types.VIEW3D_HT_header.remove(settings.draw_header)
	del bpy.types.WindowManager.universal_gizmo_enabled
	for cls in reversed(_CLASSES):
		bpy.utils.unregister_class(cls)
