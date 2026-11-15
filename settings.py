# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty

PACKAGE = __package__

def redraw(self=None, context=None):
	for win in bpy.context.window_manager.windows:
		for area in win.screen.areas:
			if area.type == 'VIEW_3D':
				area.tag_redraw()

def preferences(context):
	addon = context.preferences.addons.get(PACKAGE)
	return addon.preferences if addon else _Defaults()

class _Defaults:
	size = 1.2
	opacity = 0.9
	color_center = (0.96, 0.96, 0.96)
	color_hover = (1.0, 0.52, 0.12)
	line_width = 2.5
	arrow_length = 1.9
	arrow_head_width = 0.15
	arrow_head_length = 0.60
	arrows_both_directions = False
	cube_size = 0.085
	plane_size = 0.32
	plane_offset = 0.44
	arc_radius = 0.96
	screen_radius = 1.15
	center_radius = 0.18
	scale_orientation = 'FOLLOW'
	orientation = 'FOLLOW'
	readout = True
	pie_preview = True
	font_size = 15.0
	pie_alpha = 0.24
	fade_inactive = True

def colors(context):
	theme = context.preferences.themes[0].user_interface
	return (tuple(theme.axis_x), tuple(theme.axis_y), tuple(theme.axis_z))

def draw_appearance(layout, p):
	layout.use_property_split = True
	layout.prop(p, 'size')
	layout.prop(p, 'opacity')
	layout.prop(p, 'line_width')
	layout.prop(p, 'color_center')
	layout.prop(p, 'color_hover')
	col = layout.column(align=True)
	for key in ('arrow_length', 'arrow_head_width', 'arrow_head_length',
				'cube_size', 'plane_size', 'plane_offset', 'arc_radius'):
		col.prop(p, key)
	col.prop(p, 'screen_radius')
	col.prop(p, 'center_radius')
	layout.operator('view3d.universal_gizmo_reset', icon='LOOP_BACK')

class UTG_Preferences(bpy.types.AddonPreferences):
	bl_idname = PACKAGE

	size: FloatProperty(name='Size Multiplier', default=1.2, min=0.4, max=4.0,
						description="Multiplies Blender's global gizmo size", update=redraw)
	opacity: FloatProperty(name='Opacity', default=0.9, min=0.05, max=1, update=redraw)
	color_center: FloatVectorProperty(name='Screen Controls', subtype='COLOR', size=3, default=_Defaults.color_center, min=0, max=1, update=redraw)
	color_hover: FloatVectorProperty(name='Hover Color', subtype='COLOR', size=3, default=_Defaults.color_hover, min=0, max=1, update=redraw)
	line_width: FloatProperty(name='Line Width', default=2.5, min=1, max=6, update=redraw)
	arrow_length: FloatProperty(name='Location Arrow Length', default=1.9, min=0.8, max=3.5, update=redraw)
	arrow_head_width: FloatProperty(name='Arrowhead Width', default=0.15, min=0.04, max=0.5, update=redraw)
	arrow_head_length: FloatProperty(name='Arrowhead Length', default=0.60, min=0.1, max=1.5,
									description='Length of the tapered head, limited by the total arrow length', update=redraw)
	arrows_both_directions: BoolProperty(name='Arrows in Both Directions', default=False, update=redraw)
	cube_size: FloatProperty(name='Scale Cube Size', default=0.085, min=0.04, max=0.18, update=redraw)
	plane_size: FloatProperty(name='Plane Square Size', default=0.32, min=0.08, max=0.65, update=redraw)
	plane_offset: FloatProperty(name='Plane Square Offset', default=0.44, min=0.15, max=1.0, update=redraw)
	arc_radius: FloatProperty(name='Axis Rotation Radius', default=0.96, min=0.5, max=1.6, update=redraw)
	screen_radius: FloatProperty(name='Screen Rotation Radius', default=1.15, min=0.6, max=2, update=redraw)
	center_radius: FloatProperty(name='Uniform Scale Ring Radius', default=0.16, min=0.1, max=0.3, update=redraw)
	orientation: EnumProperty(name='Move / Rotate Orientation', items=[
		('FOLLOW', 'Blender', 'Follow the viewport transform orientation'),
		('GLOBAL', 'Global', 'World axes'), ('LOCAL', 'Local', 'Active object axes'),
		('VIEW', 'View', 'Screen axes')], default='FOLLOW', update=redraw)
	scale_orientation: EnumProperty(name='Scale Orientation', items=[
		('FOLLOW', 'Blender', 'Follow the viewport transform orientation'),
		('LOCAL', 'Local', 'Scale on active object axes'),
		('GLOBAL', 'Global', 'Scale on world axes'),
		('VIEW', 'View', 'Scale on screen axes')], default='FOLLOW', update=redraw)
	readout: BoolProperty(name='Live Transform Readout', default=True, update=redraw)
	pie_preview: BoolProperty(name='Rotation Pie Preview', default=True, update=redraw)
	pie_alpha: FloatProperty(name='Pie Opacity', default=0.24, min=0.05, max=0.8, update=redraw)
	font_size: FloatProperty(name='Readout Font Size', default=15, min=10, max=30, update=redraw)
	fade_inactive: BoolProperty(name='Fade Other Handles During Drag', default=True, update=redraw)

	def draw(self, context):
		draw_appearance(self.layout, self)

class UTG_OT_reset(bpy.types.Operator):
	bl_idname = 'view3d.universal_gizmo_reset'
	bl_label = 'Reset Appearance'
	bl_description = 'Restore default gizmo appearance and inherit the current Blender axis colors'

	def execute(self, context):
		p = preferences(context)
		for key in _Defaults.__dict__:
			if not key.startswith('_') and key not in {'orientation', 'scale_orientation'}:
				p.property_unset(key)
		redraw()
		return {'FINISHED'}

class UTG_PT_main(bpy.types.Panel):
	bl_label = 'Universal Transform'
	bl_idname = 'UTG_PT_main'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Universal'

	def draw(self, context):
		layout = self.layout
		p = preferences(context)
		layout.prop(context.window_manager, 'universal_gizmo_enabled', text='Show Universal Gizmo')
		col = layout.column(align=True)
		col.label(text='Move / Rotate Axes')
		col.prop(p, 'orientation', text='')
		col = layout.column(align=True)
		col.label(text='Scale Axes')
		col.prop(p, 'scale_orientation', text='')
		layout.separator()
		layout.prop(p, 'arrows_both_directions')
		layout.separator()
		layout.prop(p, 'readout')
		layout.prop(p, 'pie_preview')
		layout.prop(p, 'fade_inactive')
		layout.prop(p, 'font_size')
		layout.prop(p, 'pie_alpha')
		if not context.space_data.show_gizmo:
			layout.prop(context.space_data, 'show_gizmo', text='Enable Viewport Gizmos', icon='ERROR')
		layout.separator()
		layout.label(text='Appearance')
		draw_appearance(layout.column(), p)

def draw_header(self, context):
	if context.mode in {'OBJECT', 'EDIT_MESH'}:
		self.layout.prop(context.window_manager, 'universal_gizmo_enabled', text='', icon='GIZMO', toggle=True)

CLASSES = (UTG_Preferences, UTG_OT_reset, UTG_PT_main)

