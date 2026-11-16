# SPDX-License-Identifier: GPL-3.0-or-later
import bpy

_KEYMAPS = []
_OPERATOR = 'view3d.universal_gizmo_toggle'

def user_item(context):
	config = context.window_manager.keyconfigs.user
	keymap = config.keymaps.get('3D View') if config else None
	if keymap:
		items = [item for item in keymap.keymap_items if item.idname == _OPERATOR and not item.properties.keep_button]
		return next((item for item in items if item.type != 'NONE'), items[0] if items else None)
	return None

def draw(layout, context):
	item = user_item(context)
	if item is None:
		return
	layout.label(text='Show / Hide Shortcut')
	row = layout.row(align=True)
	row.prop(item, 'type', text='', full_event=True)
	if item.type != 'NONE':
		row.operator('view3d.universal_gizmo_clear_shortcut', text='', icon='X')

def register():
	config = bpy.context.window_manager.keyconfigs.addon
	if config:
		keymap = config.keymaps.new(name='3D View', space_type='VIEW_3D')
		item = keymap.keymap_items.new(_OPERATOR, 'NONE', 'PRESS')
		_KEYMAPS.append((keymap, item))

def unregister():
	for keymap, item in _KEYMAPS:
		keymap.keymap_items.remove(item)
	_KEYMAPS.clear()

class UTG_OT_clear_shortcut(bpy.types.Operator):
	bl_idname = 'view3d.universal_gizmo_clear_shortcut'
	bl_label = 'Clear Show / Hide Shortcut'
	bl_description = 'Leave the global show / hide shortcut unassigned'
	bl_options = {'INTERNAL'}

	def execute(self, context):
		item = user_item(context)
		if item is None:
			return {'CANCELLED'}
		item.type = 'NONE'
		item.any = False
		item.shift = item.ctrl = item.alt = item.oskey = False
		item.key_modifier = 'NONE'
		return {'FINISHED'}

CLASSES = (UTG_OT_clear_shortcut,)
