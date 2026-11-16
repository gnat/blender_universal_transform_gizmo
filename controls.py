# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import bpy
from bpy.props import BoolProperty, EnumProperty
from mathutils import Matrix, Vector
from . import settings, interaction, gizmos
from . import context as ctx

KINDS = (
	('VISIBILITY', 'Gizmo Visibility', 'Show or hide the gizmo while keeping its visibility button'),
	('ORIENTATION', 'Transform Orientation', 'Cycle Blender transform orientations'),
	('PIVOT', 'Transform Pivot Point', 'Cycle Blender transform pivot points'),
	('SNAP', 'Snapping', 'Toggle Blender snapping'),
	('PROPORTIONAL', 'Proportional Editing', 'Toggle proportional editing in the current mode'),
)
VISIBILITY = {
	'VISIBILITY': 'show_visibility_toggle',
	'ORIENTATION': 'show_orientation_toggle',
	'PIVOT': 'show_pivot_toggle',
	'SNAP': 'show_snap_toggle',
	'PROPORTIONAL': 'show_proportional_toggle',
}

def orientation_values(context):
	slot = context.scene.transform_orientation_slots[0]
	values = list(slot.bl_rna.properties['type'].enum_items.keys())
	# RNA's static enum list omits custom orientations. A rejected empty value
	# exposes the context's valid identifiers without changing the setting.
	try:
		slot.type = ''
	except TypeError as error:
		try:
			available = ast.literal_eval(str(error).partition(' not found in ')[2])
		except (ValueError, SyntaxError):
			available = ()
		if isinstance(available, (tuple, list)) and available and all(isinstance(value, str) for value in available):
			values = list(available)
	if slot.type not in values:
		values.append(slot.type)
	enabled = settings.preferences(context).orientation_modes
	builtins = set(slot.bl_rna.properties['type'].enum_items.keys())
	return [value for value in values if value in enabled or (value not in builtins and 'CUSTOM' in enabled)]

def proportional_property(context):
	return 'use_proportional_edit_objects' if context.mode == 'OBJECT' else 'use_proportional_edit'

def state(context, kind):
	tool_settings = context.scene.tool_settings
	if kind == 'VISIBILITY':
		visible = settings.handles_visible(context)
		return ('Visible' if visible else 'Hidden'), ('HIDE_OFF' if visible else 'HIDE_OFF'), False
	if kind == 'ORIENTATION':
		slot = context.scene.transform_orientation_slots[0]
		item = slot.bl_rna.properties['type'].enum_items.get(slot.type)
		return (item.name, item.icon, False) if item else (slot.type, 'ORIENTATION_LOCAL', False)
	if kind == 'PIVOT':
		item = tool_settings.bl_rna.properties['transform_pivot_point'].enum_items[tool_settings.transform_pivot_point]
		return item.name, item.icon, False
	if kind == 'SNAP':
		enabled = tool_settings.use_snap
		return ('On' if enabled else 'Off'), ('SNAP_ON' if enabled else 'SNAP_OFF'), enabled
	enabled = getattr(tool_settings, proportional_property(context))
	icon = 'PROP_OFF'
	if enabled:
		icon = 'PROP_ON'
		if context.mode != 'OBJECT':
			if tool_settings.use_proportional_connected:
				icon = 'PROP_CON'
			elif tool_settings.use_proportional_projected:
				icon = 'PROP_PROJECTED'
	return ('On' if enabled else 'Off'), icon, enabled

def cycle(context, kind, reverse=False):
	tool_settings = context.scene.tool_settings
	if kind == 'VISIBILITY':
		context.window_manager.universal_gizmo_visible = not context.window_manager.universal_gizmo_visible
	elif kind == 'SNAP':
		tool_settings.use_snap = not tool_settings.use_snap
	elif kind == 'PROPORTIONAL':
		prop = proportional_property(context)
		setattr(tool_settings, prop, not getattr(tool_settings, prop))
	else:
		if kind == 'ORIENTATION':
			owner = context.scene.transform_orientation_slots[0]
			prop = 'type'
			values = orientation_values(context)
		else:
			owner, prop = tool_settings, 'transform_pivot_point'
			enabled = settings.preferences(context).pivot_modes
			values = [item[0] for item in settings.PIVOT_ITEMS if item[0] in enabled]
		if not values:
			return
		current = getattr(owner, prop)
		index = values.index(current) if current in values else (0 if reverse else -1)
		setattr(owner, prop, values[(index + (-1 if reverse else 1)) % len(values)])
	settings.redraw()

class UTG_OT_toggle_visibility(bpy.types.Operator):
	bl_idname = 'view3d.universal_gizmo_toggle'
	bl_label = 'Show / Hide the Universal Transform Gizmo'
	bl_description = 'Show / Hide the Universal Transform Gizmo'

	keep_button: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def description(cls, context, properties):
		if properties.keep_button:
			return 'Hide the gizmo and keep this button visible' if settings.handles_visible(context) else 'Show the gizmo'
		return cls.bl_description

	def execute(self, context):
		wm = context.window_manager
		prop = 'universal_gizmo_visible' if self.keep_button else 'universal_gizmo_enabled'
		setattr(wm, prop, not getattr(wm, prop))
		return {'FINISHED'}

class UTG_OT_cycle_setting(bpy.types.Operator):
	bl_idname = 'view3d.universal_gizmo_cycle_setting'
	bl_label = 'Universal Gizmo Setting'
	bl_options = {'UNDO', 'INTERNAL'}

	setting: EnumProperty(items=KINDS)
	reverse: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def description(cls, context, properties):
		label = next(item[1] for item in KINDS if item[0] == properties.setting)
		value = state(context, properties.setting)[0]
		return f'{label}: {value}\nLeft-click: next; Right-click: previous'

	def invoke(self, context, event):
		self.reverse = event.type == 'RIGHTMOUSE'
		return self.execute(context)

	def execute(self, context):
		cycle(context, self.setting, self.reverse)
		return {'FINISHED'}

class UTG_GGT_controls(bpy.types.GizmoGroup):
	bl_idname = 'UTG_GGT_controls'
	bl_label = 'Universal Transform Mode Buttons'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'WINDOW'
	bl_options = {'3D', 'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'}

	@classmethod
	def poll(cls, context):
		p = settings.preferences(context)
		return gizmos.UTG_GGT_universal.available(context) and any(getattr(p, prop) for prop in VISIBILITY.values())

	@classmethod
	def setup_keymap(cls, keyconfig):
		keymap = keyconfig.keymaps.get('Universal Transform Mode Buttons')
		if keymap is None:
			keymap = keyconfig.keymaps.new(name='Universal Transform Mode Buttons', space_type='VIEW_3D')
			for button in ('LEFTMOUSE', 'RIGHTMOUSE'):
				keymap.keymap_items.new('gizmogroup.gizmo_tweak', button, 'PRESS', any=True)
		return keymap

	def setup(self, context):
		self.buttons = {}
		self.variants = {}
		self.side = 1
		for kind, label, description in KINDS:
			self.buttons[kind] = self.button_for_icon(kind, state(context, kind)[1])

	def button_for_icon(self, kind, icon):
		key = kind, icon
		if key not in self.variants:
			# Blender caches the initial icon, so each icon keeps its own button.
			button = self.gizmos.new('GIZMO_GT_button_2d')
			button.icon = icon
			button.draw_options = set()
			button.use_draw_scale = True
			button.use_draw_offset_scale = False
			button.use_event_handle_all = False
			button.use_tooltip = True
			button.show_drag = False
			button.line_width = 1.0
			if kind == 'VISIBILITY':
				properties = button.target_set_operator(UTG_OT_toggle_visibility.bl_idname)
				properties.keep_button = True
			else:
				properties = button.target_set_operator(UTG_OT_cycle_setting.bl_idname)
				properties.setting = kind
			self.variants[key] = button
		return self.variants[key]

	def draw_prepare(self, context):
		p = settings.preferences(context)
		active = interaction.current(context)
		center = active.display_center if active else ctx.pivot(context)
		if center is None or context.region_data is None:
			for button in self.buttons.values():
				button.hide = True
			return
		clip = context.region_data.window_matrix @ context.region_data.view_matrix @ center.to_4d()
		visible = [kind for kind in self.buttons if getattr(p, VISIBILITY[kind])]
		handles_visible = settings.handles_visible(context)
		pixel = ctx.world_per_pixel(context, center)
		if clip.w <= 1e-8 or not visible or pixel is None:
			for button in self.buttons.values():
				button.hide = True
			return
		point = Vector(((clip.x / clip.w + 1) * context.region.width / 2,
						(clip.y / clip.w + 1) * context.region.height / 2))
		ui_scale = context.preferences.system.ui_scale
		radius = (p.toggle_size / 2 + 4) * ui_scale
		spacing = (p.toggle_size + 12) * ui_scale
		left, right = radius + 6, context.region.width - radius - 6
		for region in context.area.regions:
			if region.type == 'UI' and not context.space_data.show_region_ui:
				continue
			if region.type == 'TOOLS' and not context.space_data.show_region_toolbar:
				continue
			if region.type in {'UI', 'TOOLS'} and region.width > 1:
				if region.x > context.region.x:
					right = min(right, region.x - context.region.x - radius - 6)
				else:
					left = max(left, region.x + region.width - context.region.x + radius + 6)
		size = context.preferences.view.gizmo_size * p.size
		distance = size * p.toggle_distance
		width = spacing * (len(visible) - 1)
		if self.side > 0 and point.x + distance + width > right:
			self.side = -1
		elif self.side < 0 and point.x + distance + width < right - radius * 2:
			self.side = 1
		x = point.x + self.side * distance
		if self.side < 0:
			x -= width
		x = min(max(x, left), max(left, right - width))
		y = min(max(point.y + size * p.toggle_vertical_offset, radius + 6), context.region.height - radius - 6)
		basis = ctx.view_basis(context)
		theme = context.preferences.themes[0].user_interface
		for kind, button in self.buttons.items():
			button.hide = kind not in visible or (not handles_visible and kind != 'VISIBILITY')
			if button.hide:
				continue
			value, icon, enabled = state(context, kind)
			if button.icon != icon:
				button.hide = True
				button = self.button_for_icon(kind, icon)
				self.buttons[kind] = button
			button.hide = False
			button.color = (0.08, 0.08, 0.08) if kind == 'VISIBILITY' and not handles_visible else (tuple(theme.wcol_radio.inner_sel[:3]) if enabled else (0.18, 0.18, 0.18))
			button.color_highlight = p.color_hover
			button.alpha = p.toggle_opacity * (0.22 if active and p.fade_inactive else 1)
			button.alpha_highlight = p.toggle_opacity
			button.hide_select = active is not None
			button.scale_basis = pixel * p.toggle_size / 2
			position = center + basis.col[0] * ((x + visible.index(kind) * spacing - point.x) * pixel)
			position += basis.col[1] * ((y - point.y) * pixel)
			button.matrix_basis = Matrix.Translation(position)

CLASSES = (UTG_OT_toggle_visibility, UTG_OT_cycle_setting, UTG_GGT_controls)
