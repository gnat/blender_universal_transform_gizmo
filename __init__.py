# SPDX-License-Identifier: GPL-3.0-or-later
"""Universal Transform Gizmo"""

import bpy
from . import settings, interaction, gizmos, controls, keymaps

# Blender picks groups in registration order and draws them in reverse.
_CLASSES = (*settings.CLASSES, *interaction.CLASSES, *gizmos.CLASSES, *controls.CLASSES,
			gizmos.UTG_GGT_trackball, *keymaps.CLASSES)

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
