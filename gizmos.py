# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import gpu
from mathutils import Matrix, Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from . import settings, geometry, interaction
from . import context as ctx

_SCREEN_DRAW_HANDLE = None
_SCREEN_CONTROLS = {}

def _capture_screen_control(gizmo, context, color, alpha, width):
	view = context.region_data
	clip = view.window_matrix @ view.view_matrix @ gizmo.matrix_basis.translation.to_4d()
	if clip.w <= 1e-8:
		return
	center = Vector(((clip.x/clip.w+1)*context.region.width/2,
						(clip.y/clip.w+1)*context.region.height/2))
	size = context.preferences.view.gizmo_size * settings.preferences(context).size

	def pixel(co):
		return (center.x+co[0]*size, center.y+co[1]*size, 0)

	key = (context.window.as_pointer(), context.region.as_pointer())
	_SCREEN_CONTROLS.setdefault(key, {})[gizmo.kind] = {
		'lines': [pixel(v) for v in gizmo.lines],
		'tris': [pixel(v) for v in gizmo.tris],
		'color': (*color,alpha), 'width': width,
	}

def _draw_screen_controls():
	context = bpy.context
	if context.window is None or context.region is None:
		return
	key = (context.window.as_pointer(), context.region.as_pointer())
	# Consume only this frame's records; hidden/unselected gizmos leave no ghosts.
	controls = _SCREEN_CONTROLS.pop(key, None)
	if not controls:
		return
	width,height = context.region.width,context.region.height
	projection = Matrix(((2/width,0,0,-1),(0,2/height,0,-1),(0,0,-1,0),(0,0,0,1)))
	blend,depth = gpu.state.blend_get(),gpu.state.depth_test_get()
	try:
		with gpu.matrix.push_pop(),gpu.matrix.push_pop_projection():
			gpu.matrix.load_matrix(Matrix.Identity(4))
			gpu.matrix.load_projection_matrix(projection)
			gpu.state.blend_set('ALPHA')
			gpu.state.depth_test_set('NONE')
			for kind in ('ROTATE','SCALE','MOVE'):
				control = controls.get(kind)
				if control:
					interaction._draw_batch('TRIS',control['tris'],control['color'])
					interaction._draw_batch('LINES',control['lines'],control['color'],control['width'])
	finally:
		gpu.state.blend_set(blend)
		gpu.state.depth_test_set(depth)

def register_draw_handlers():
	global _SCREEN_DRAW_HANDLE
	if _SCREEN_DRAW_HANDLE is None:
		_SCREEN_DRAW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(_draw_screen_controls,(),'WINDOW','POST_PIXEL')

def unregister_draw_handlers():
	global _SCREEN_DRAW_HANDLE
	if _SCREEN_DRAW_HANDLE is not None:
		bpy.types.SpaceView3D.draw_handler_remove(_SCREEN_DRAW_HANDLE,'WINDOW')
		_SCREEN_DRAW_HANDLE = None
	_SCREEN_CONTROLS.clear()

class UTG_GT_handle(bpy.types.Gizmo):
	bl_idname = 'UTG_GT_handle'

	def setup(self):
		self.kind = 'MOVE'
		self.axis = -1
		self.direction = 1
		self.plane_signs = None
		self.lines, self.tris = [], []
		self.rear_lines = []
		self.rear_alpha = 0.0
		self.fill_alpha = 1.0
		self.base_alpha = 1.0
		self.mouse = (0, 0)
		self.use_draw_modal = True
		self.use_draw_scale = False
		self.use_draw_offset_scale = False
		self.use_event_handle_all = False
		self.use_tooltip = True

	def draw(self, context):
		p = settings.preferences(context)
		active = interaction.current(context)
		selected = self.is_highlight or (active and active.kind == self.kind and active.axis == self.axis
											and active.direction == self.direction)
		color = tuple(p.color_hover) if selected else tuple(self.color)
		alpha = self.base_alpha
		if active and p.fade_inactive and not selected:
			alpha *= 0.22
		width = p.line_width + (0.7 if selected else 0)
		if self.axis < 0:
			if self.kind == 'SCALE':
				width = p.center_line_width + (0.7 if selected else 0)
			_capture_screen_control(self,context,color,alpha,width)
			return
		matrix = self.matrix_basis
		lines = [matrix @ Vector(v) for v in self.lines]
		tris = [matrix @ Vector(v) for v in self.tris]
		rear = [matrix @ Vector(v) for v in self.rear_lines]
		blend,depth = gpu.state.blend_get(),gpu.state.depth_test_get()
		gpu.state.blend_set('ALPHA')
		gpu.state.depth_test_set('NONE')
		try:
			# Other viewport draw passes may leave jittered or interpolated matrices.
			# Isolate ours and use one unjittered view/projection pair for this frame.
			with gpu.matrix.push_pop(),gpu.matrix.push_pop_projection():
				gpu.matrix.load_matrix(context.region_data.view_matrix)
				gpu.matrix.load_projection_matrix(context.region_data.window_matrix)
				if self.kind == 'SCALE':
					toward = ctx.view_basis(context).col[2]
					for i in range(0, len(tris), 6):
						face = tris[i:i+6]
						normal = (face[1]-face[0]).cross(face[2]-face[0]).normalized()
						light = normal.dot(toward)
						if light > 0:
							shade = 0.55 + 0.45 * light
							interaction._draw_batch('TRIS', face, (*(c*shade for c in color), alpha))
				else:
					interaction._draw_batch('TRIS', tris, (*color, alpha * (1 if selected else self.fill_alpha)))
				if self.rear_alpha > 0:
					interaction._draw_batch('LINES',rear,(*color,alpha*self.rear_alpha),width)
				interaction._draw_batch('LINES', lines, (*color, alpha), width)
		finally:
			gpu.state.blend_set(blend)
			gpu.state.depth_test_set(depth)

	def test_select(self, context, location):
		self.mouse = tuple(location)
		if self.hide or interaction.current(context):
			return -1
		mouse = Vector(location)
		matrix = self.matrix_basis

		def project(co):
			return location_3d_to_region_2d(context.region, context.region_data, matrix @ Vector(co))

		threshold = 7 * context.preferences.system.ui_scale
		if self.kind == 'MOVE' and self.axis >= 3:
			# Wide line tolerances make neighboring small plane squares overlap.
			threshold = 2.5 * context.preferences.system.ui_scale
		pick_lines = self.lines + (self.rear_lines if self.rear_alpha > 0.25 else [])
		lines = [project(v) for v in pick_lines]
		for a, b in zip(lines[::2], lines[1::2]):
			if a is not None and b is not None and geometry.distance_segment(mouse, a, b) <= threshold:
				return 0
		tris = [project(v) for v in self.tris]
		for i in range(0, len(tris), 3):
			a,b,c = tris[i:i+3]
			if a is not None and b is not None and c is not None:
				if geometry.in_triangle(mouse, a, b, c):
					return 0
				if self.kind != 'MOVE' or self.axis < 0:
					if min(geometry.distance_segment(mouse,a,b),geometry.distance_segment(mouse,b,c),geometry.distance_segment(mouse,c,a)) < threshold * 0.55:
						return 0
		return -1

	def modal(self, context, event, tweak):
		active = interaction.current(context)
		if active:
			active.record_event(event)
		return {'RUNNING_MODAL'}

	def exit(self, context, cancel):
		interaction.shutdown()

def _matrix(center, basis, scale):
	matrix = basis.to_4x4()
	matrix.translation = center
	return matrix @ Matrix.Diagonal((scale, scale, scale, 1))

def _axis_basis(basis, axis):
	# Local Z points along the selected axis; the XY plane is its rotation plane.
	return Matrix((basis.col[(axis+1)%3], basis.col[(axis+2)%3], basis.col[axis])).transposed()

class UTG_GGT_universal(bpy.types.GizmoGroup):
	bl_idname = 'UTG_GGT_universal'
	bl_label = 'Universal Transform Gizmo'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'WINDOW'
	bl_options = {'3D', 'PERSISTENT', 'SHOW_MODAL_ALL'}

	@classmethod
	def setup_keymap(cls, keyconfig):
		# Begin on press so the complete drag reaches the native transform,
		# including short drags that consist of only one mouse-move event.
		km = keyconfig.keymaps.get('Universal Transform Gizmo')
		if km is None:
			km = keyconfig.keymaps.new(name='Universal Transform Gizmo', space_type='VIEW_3D')
			km.keymap_items.new('gizmogroup.gizmo_tweak', 'LEFTMOUSE', 'PRESS', any=True)
		return km

	@classmethod
	def poll(cls, context):
		return cls.available(context) and settings.handles_visible(context)

	@classmethod
	def available(cls, context):
		if not getattr(context.window_manager, 'universal_gizmo_enabled', False):
			return False
		if context.mode not in {'OBJECT', 'EDIT_MESH'} or not context.active_object:
			return False
		tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
		if tool and tool.idname in {'builtin.move', 'builtin.rotate', 'builtin.scale', 'builtin.scale_cage', 'builtin.transform'}:
			return False
		if not context.space_data.show_gizmo:
			return False
		# Hide during unrelated keyboard transforms, but retain our active handles.
		if interaction.current(context) is None and any(op.bl_idname.startswith('TRANSFORM_OT_') for op in context.window.modal_operators):
			return False
		return bool(ctx.selection(context))

	def setup(self, context):
		self.handles = []
		self.facing_directions = {'MOVE': None, 'SCALE': None}
		# Picking follows the visible layering: screen controls are on top.
		specifications = [('MOVE', -1, 1), ('SCALE', -1, 1), ('ROTATE', -1, 1)]
		specifications += [('MOVE', a+3, 1) for a in range(3)]
		specifications += [('SCALE', a, direction) for direction in (1,-1) for a in range(3)]
		specifications += [('MOVE', a, direction) for direction in (1,-1) for a in range(3)]
		specifications += [('ROTATE', a, 1) for a in range(3)]
		# Blender evaluates later-created gizmos first when picking this group.
		for kind, axis, direction in reversed(specifications):
			gz = self.gizmos.new(UTG_GT_handle.bl_idname)
			gz.kind, gz.axis = kind, axis
			gz.direction = direction
			native = {'MOVE': 'transform.translate', 'ROTATE': 'transform.rotate', 'SCALE': 'transform.resize'}[kind]
			gz.operator_properties = gz.target_set_operator(native)
			self.handles.append(gz)

	def invoke_prepare(self, context, gizmo):
		interaction.prepare(context, gizmo)

	def draw_prepare(self, context):
		p = settings.preferences(context)
		active = interaction.current(context)
		if active:
			# Capture one current pose before drawing any handles or overlays.
			# A timer/post-pixel sample leaves the handles on the previous frame.
			active.sample()
		center = active.display_center if active else ctx.pivot(context)
		if center is None:
			return
		pixel = ctx.world_per_pixel(context, center)
		if pixel is None:
			for gz in self.handles:
				gz.hide = True
			return
		scale = pixel * context.preferences.view.gizmo_size * p.size
		_, move_basis = ctx.orientation(context)
		scale_basis = move_basis
		view_basis = ctx.view_basis(context)
		if active:
			move_basis = active.draw_move_basis
			scale_basis = active.draw_scale_basis
		axis_colors = settings.colors(context)
		view_normal = view_basis.col[2]
		if context.region_data.is_perspective:
			toward_camera = context.region_data.view_matrix.inverted_safe().translation-center
			if toward_camera.length_squared > 1e-12:
				toward_camera.normalize()
			else:
				toward_camera = view_normal
		else:
			toward_camera = view_normal
		for kind,basis in (('MOVE',move_basis),('SCALE',scale_basis)):
			previous = self.facing_directions[kind]
			if not active or previous is None:
				self.facing_directions[kind] = tuple(
					geometry.closest_side(basis.col[a].dot(toward_camera),
											previous[a] if previous else None)
					for a in range(3))
		for gz in self.handles:
			kind, axis = gz.kind, gz.axis
			# Keep one camera-facing arrow and its scale cube on each axis.
			# During a native transform the chosen sides remain unchanged.
			gz.hide = (not p.arrows_both_directions and kind in {'MOVE','SCALE'}
						and 0 <= axis < 3
						and gz.direction != self.facing_directions[kind][axis])
			if gz.hide:
				continue
			gz.fill_alpha = 1.0
			gz.rear_lines, gz.rear_alpha = [],0.0
			if axis < 0:
				basis = view_basis
				gz.color = p.color_center
				gz.base_alpha = p.opacity
				gz.matrix_basis = _matrix(center, basis, scale)
				if kind == 'MOVE':
					gz.lines, gz.tris = geometry.dot(p.center_dot_radius)
				elif kind == 'SCALE':
					gz.lines, gz.tris = geometry.segments(geometry.circle(p.center_radius)), []
				else:
					gz.lines, gz.tris = geometry.segments(geometry.circle(p.screen_radius)), []
				continue
			a = axis % 3
			source_basis = scale_basis if kind == 'SCALE' else move_basis
			basis = _axis_basis(source_basis, a)
			if gz.direction < 0:
				basis = basis @ Matrix.Diagonal((1,-1,-1))
			gz.matrix_basis = _matrix(center, basis, scale)
			gz.color = axis_colors[a]
			gz.base_alpha = p.opacity
			if kind == 'MOVE' and axis >= 3:
				# Choose the nearest corner without changing the constraint axes.
				# Freeze it for the entire drag so the picked square cannot jump.
				if not active or gz.plane_signs is None:
					toward = basis.transposed() @ toward_camera
					gz.plane_signs = geometry.closest_quadrant(toward, gz.plane_signs)
				gz.lines, gz.tris = geometry.plane(p.plane_offset, p.plane_size, gz.plane_signs)
				gz.fill_alpha = 0.28
			elif kind == 'MOVE':
				gz.lines, gz.tris = geometry.arrow(p.arrow_length,p.arrow_head_width/2,p.arrow_head_length)
			elif kind == 'SCALE':
				gz.lines, gz.tris = geometry.cube((0,0,p.arrow_length+0.19), p.cube_size)
				gz.fill_alpha = 0.85
			else:
				toward = basis.transposed() @ toward_camera
				gz.lines,gz.rear_lines,gz.rear_alpha = geometry.front_half(p.arc_radius,toward)
				gz.tris = []

CLASSES = (UTG_GT_handle, UTG_GGT_universal)
