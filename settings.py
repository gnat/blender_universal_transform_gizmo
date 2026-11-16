# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty
from . import keymaps

PACKAGE = __package__

def redraw(self=None, context=None):
	for win in bpy.context.window_manager.windows:
		for area in win.screen.areas:
			if area.type == 'VIEW_3D':
				area.tag_redraw()

def update_visibility(self, context):
	if self.universal_gizmo_enabled:
		self.universal_gizmo_visible = True
	redraw()

def handles_visible(context):
	return not preferences(context).show_visibility_toggle or context.window_manager.universal_gizmo_visible

def preferences(context):
	addon = context.preferences.addons.get(PACKAGE)
	return addon.preferences if addon else _Defaults()

class _Defaults:
	size = 1.2
	opacity = 0.9
	color_center = (0.96, 0.96, 0.96)
	color_hover = (1.0, 0.52, 0.12)
	line_width = 2.5
	arrow_length = 2.0
	arrow_head_width = 0.15
	arrow_head_length = 0.60
	arrows_both_directions = False
	cube_size = 0.085
	plane_size = 0.34
	plane_offset = 0.44
	arc_radius = 0.96
	screen_radius = 1.15
	center_radius = 0.18
	center_line_width = 3.75
	center_dot_radius = 0.06
	font_size = 15.0
	fade_inactive = True
	toggle_size = 24.0
	toggle_distance = 1.0
	toggle_vertical_offset = 1.0
	toggle_opacity = 0.9
	show_visibility_toggle = True
	show_orientation_toggle = True
	show_pivot_toggle = False
	show_snap_toggle = False
	show_proportional_toggle = False
	orientation_global_local_only = True

def colors(context):
	theme = context.preferences.themes[0].user_interface
	return (tuple(theme.axis_x), tuple(theme.axis_y), tuple(theme.axis_z))

def draw_appearance(layout, p):
	col = layout.column(align=True)
	col.use_property_split = False
	col.prop(p, 'arrows_both_directions')
	col.prop(p, 'fade_inactive')
	layout.use_property_split = True
	layout.prop(p, 'size')
	layout.prop(p, 'opacity')
	layout.prop(p, 'line_width')
	layout.prop(p, 'color_center')
	layout.prop(p, 'color_hover')
	col = layout.column(align=True)
	for key in ('arrow_length', 'arrow_head_width', 'arrow_head_length',
				'cube_size', 'plane_size', 'plane_offset', 'center_dot_radius', 'arc_radius'):
		col.prop(p, key)
	col.prop(p, 'screen_radius')
	col.prop(p, 'center_radius')
	col.prop(p, 'center_line_width')
	col.prop(p, 'font_size')

def draw_toggles(layout, p):
	layout.label(text='Transform Mode Buttons')
	col = layout.column(align=True)
	col.use_property_split = False
	col.prop(p, 'show_visibility_toggle')
	col.prop(p, 'show_orientation_toggle')
	row = col.row()
	row.enabled = p.show_orientation_toggle
	row.prop(p, 'orientation_global_local_only')
	col.prop(p, 'show_pivot_toggle')
	col.prop(p, 'show_snap_toggle')
	col.prop(p, 'show_proportional_toggle')
	col = layout.column(align=True)
	col.use_property_split = True
	col.prop(p, 'toggle_size', text='Icon Size')
	col.prop(p, 'toggle_distance', text='Distance')
	col.prop(p, 'toggle_vertical_offset', text='Vertical Offset')
	col.prop(p, 'toggle_opacity', text='Opacity')

class UTG_Preferences(bpy.types.AddonPreferences):
	bl_idname = PACKAGE

	size: FloatProperty(name='Size Multiplier', default=1.2, min=0.4, max=4.0,
						description="Multiplies Blender's global gizmo size", update=redraw)
	opacity: FloatProperty(name='Opacity', default=0.9, min=0.05, max=1, update=redraw)
	color_center: FloatVectorProperty(name='Screen Controls', subtype='COLOR', size=3, default=_Defaults.color_center, min=0, max=1, update=redraw)
	color_hover: FloatVectorProperty(name='Hover Color', subtype='COLOR', size=3, default=_Defaults.color_hover, min=0, max=1, update=redraw)
	line_width: FloatProperty(name='Line Width', default=2.5, min=1, max=6, update=redraw)
	arrow_length: FloatProperty(name='Arrow Length', default=2.0, min=0.8, max=3.5, update=redraw)
	arrow_head_width: FloatProperty(name='Arrowhead Width', default=0.15, min=0.04, max=0.5, update=redraw)
	arrow_head_length: FloatProperty(name='Arrowhead Length', default=0.60, min=0.1, max=1.5,
									description='Length of the tapered head, limited by the total arrow length', update=redraw)
	arrows_both_directions: BoolProperty(name='Arrows in Both Directions', default=False, update=redraw)
	cube_size: FloatProperty(name='Scale Cube Size', default=0.085, min=0.04, max=0.18, update=redraw)
	plane_size: FloatProperty(name='Location Square Size', default=0.34, min=0.08, max=0.65, update=redraw)
	plane_offset: FloatProperty(name='Location Square Offset', default=0.44, min=0.15, max=1.0, update=redraw)
	arc_radius: FloatProperty(name='Rotation Radius', default=0.96, min=0.5, max=1.6, update=redraw)
	screen_radius: FloatProperty(name='Screen Rotation Radius', default=1.15, min=0.6, max=2, update=redraw)
	center_radius: FloatProperty(name='Uniform Scale Ring Radius', default=0.16, min=0.1, max=0.3, update=redraw)
	center_line_width: FloatProperty(name='Scale Ring Width', default=3.75, min=1, max=12,
									description='Line width of the uniform scale ring in pixels', update=redraw)
	center_dot_radius: FloatProperty(name='Location Dot Size', default=0.06, min=0.01, max=0.15,
									description='Radius of the center screen-space move dot in gizmo units', update=redraw)
	font_size: FloatProperty(name='Readout Font Size', default=15, min=10, max=30, update=redraw)
	fade_inactive: BoolProperty(name='Fade Other Handles During Drag', default=True, update=redraw)
	toggle_size: FloatProperty(name='Toggle Icon Size', default=24, min=8, max=96, precision=0,
								description='Icon size in screen pixels before Blender UI scaling', update=redraw)
	toggle_distance: FloatProperty(name='Toggle Distance', default=1.0, min=0.5, max=8,
								description='Distance of the toggle strip from the gizmo center in gizmo units', update=redraw)
	toggle_vertical_offset: FloatProperty(name='Toggle Vertical Offset', default=1.0, min=-8, max=8,
											description='Vertical offset of the first toggle button from the gizmo center in gizmo units', update=redraw)
	toggle_opacity: FloatProperty(name='Toggle Opacity', default=0.9, min=0.05, max=1, update=redraw)
	show_visibility_toggle: BoolProperty(name='Gizmo Visibility', default=True,
									description='Keep a visibility button available when the gizmo is hidden', update=redraw)
	show_orientation_toggle: BoolProperty(name='Transform Orientation', default=True, update=redraw)
	show_pivot_toggle: BoolProperty(name='Transform Pivot Point', default=False, update=redraw)
	show_snap_toggle: BoolProperty(name='Snapping', default=False, update=redraw)
	show_proportional_toggle: BoolProperty(name='Proportional Editing', default=False, update=redraw)
	orientation_global_local_only: BoolProperty(name='Limit to Global/Local/Normal', default=True,
											description='Limit orientation cycling to the big 3 instead of all available orientations', update=redraw)

	def draw(self, context):
		keymaps.draw(self.layout, context)
		self.layout.separator()
		self.layout.operator('view3d.universal_gizmo_reset', icon='LOOP_BACK')
		draw_appearance(self.layout, self)
		self.layout.separator()
		draw_toggles(self.layout, self)

class UTG_OT_reset(bpy.types.Operator):
	bl_idname = 'view3d.universal_gizmo_reset'
	bl_label = 'Reset Appearance'
	bl_description = 'Restore default gizmo appearance and inherit the current Blender axis colors'

	def execute(self, context):
		p = preferences(context)
		for key in _Defaults.__dict__:
			if not key.startswith('_'):
				p.property_unset(key)
		redraw()
		return {'FINISHED'}

class UTG_PT_main(bpy.types.Panel):
	bl_label = 'Universal Transform Gizmo'
	bl_idname = 'UTG_PT_main'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Universal'

	def draw(self, context):
		layout = self.layout
		p = preferences(context)
		layout.operator('view3d.universal_gizmo_toggle', text='Show Universal Gizmo', icon='GIZMO',
						depress=context.window_manager.universal_gizmo_enabled).keep_button = False
		keymaps.draw(layout, context)
		if not context.space_data.show_gizmo:
			layout.prop(context.space_data, 'show_gizmo', text='Enable Viewport Gizmos', icon='ERROR')
		layout.separator()
		layout.label(text='Appearance')
		layout.operator('view3d.universal_gizmo_reset', icon='LOOP_BACK')
		draw_appearance(layout.column(), p)
		layout.separator()
		draw_toggles(layout.column(), p)

def draw_header(self, context):
	if context.mode in {'OBJECT', 'EDIT_MESH'}:
		self.layout.prop(context.window_manager, 'universal_gizmo_enabled', text='', icon='GIZMO', toggle=True)

CLASSES = (UTG_Preferences, UTG_OT_reset, UTG_PT_main)
