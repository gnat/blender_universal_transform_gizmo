# SPDX-License-Identifier: GPL-3.0-or-later
"""
Native transform dispatch, lifecycle, and readouts of applied geometry changes.
The observer passes input to Blender's modal transform. It never writes selection
data, changes the snap configuration, or adds an extra undo step.
"""
import math
import bpy
import blf
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from . import context as ctx, settings

_SESSION = None
_DRAW = []
TRACKBALL_MIN_ANGLE = 0.00005

def current(context=None):
	s = _SESSION
	if s is None or s.stopped:
		return None
	if context and (context.area != s.area or context.region != s.region):
		return None
	return s

def _draw_batch(primitive, verts, color, width=2.0):
	if not verts:
		return
	if primitive == 'LINES':
		shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
		shader.bind()
		viewport = gpu.state.viewport_get()
		shader.uniform_float('viewportSize', (viewport[2], viewport[3]))
		shader.uniform_float('lineWidth', width)
	else:
		shader = gpu.shader.from_builtin('UNIFORM_COLOR')
		shader.bind()
	shader.uniform_float('color', color)
	batch_for_shader(shader, primitive, {'pos': verts}).draw(shader)

class Session:
	def __init__(self, context, mouse, kind, axis):
		self.kind, self.axis = kind, axis
		self.direction = 1
		self.area, self.region, self.window = context.area, context.region, context.window
		self.items = ctx.selection(context)
		self.center = ctx.pivot(context, self.items)
		p = settings.preferences(context)
		self.orient, self.basis = ctx.orientation(context)
		self.draw_move_basis = self.basis.copy()
		self.draw_scale_basis = self.basis.copy()
		self.view_basis = ctx.view_basis(context)
		if axis < 0:
			self.orient, self.basis = 'VIEW', self.view_basis.copy()
		self.constraint = tuple(i == axis for i in range(3)) if axis >= 0 else (False,)*3
		if kind == 'MOVE' and axis >= 3:
			self.constraint = tuple(i != axis - 3 for i in range(3))
		self.rot_axis = self.basis.col[axis if axis >= 0 else 2].normalized() if kind == 'ROTATE' else None
		# A representative sample limits per-frame work; selection itself is never changed.
		stride = max(1, len(self.items) // 256)
		self.sample_items = self.items[::stride][:256]
		self.points = [ctx.world_point(ob, v) for ob, v in self.sample_items]
		self.mean = sum(self.points, Vector()) / len(self.points)
		self.object = context.active_object if context.mode == 'OBJECT' else None
		self.linear = self.object.matrix_world.to_3x3().copy() if self.object else None
		self.delta = Vector()
		self.factors = Vector((1, 1, 1))
		self.angle = 0.0
		self.previous_angle = 0.0
		self.numeric = ''
		self.stopped = False
		self.scale = ctx.world_per_pixel(context, self.center) * context.preferences.view.gizmo_size * p.size
		self.radius = self.scale * (p.arc_radius if axis >= 0 and kind == 'ROTATE' else p.screen_radius)
		self.pie_start = self._start_direction(context, mouse) if kind == 'ROTATE' else None
		if kind == 'TRACKBALL':
			self.radius = self.scale * p.arc_radius * p.trackball_scale
			self.trackball_angles = (0.0, 0.0)
			self.trackball_mouse = Vector(mouse)
			toward = self.view_basis.col[2]
			# Tilt each plane toward the viewer so its slice remains readable.
			self.trackball_pie_normals = tuple((self.view_basis.col[i] + toward * 0.4).normalized()
												for i in range(2))
			x_normal, y_normal = self.trackball_pie_normals
			# The planes intersect along a shared, viewer-facing starting edge.
			self.trackball_pie_start = x_normal.cross(y_normal).normalized()
			self.trackball_input = Vector((0, 0))
			self.trackball_ctrl = self.trackball_shift = False
			self.trackball_snap = False
			self.trackball_numbers = ['', '']
			self.trackball_field = 0
			self.trackball_unit = context.scene.unit_settings.system_rotation
			self.trackball_edges = None
			if not self.object and context.tool_settings.transform_pivot_point == 'INDIVIDUAL_ORIGINS':
				self.trackball_edges = []
				for ob, v in self.sample_items:
					edge = next((e for e in v.link_edges if e.select and not e.hide), None)
					if edge:
						self.trackball_edges.append((ob, v, edge.other_vert(v)))
			if not self.object:
				self.trackball_vectors = self._trackball_vectors(self.points, self.mean)

	def _start_direction(self, context, mouse):
		axis = self.rot_axis
		origin = view3d_utils.region_2d_to_origin_3d(self.region, context.region_data, mouse)
		direction = view3d_utils.region_2d_to_vector_3d(self.region, context.region_data, mouse)
		denom = direction.dot(axis)
		vec = Vector()
		if abs(denom) > 1e-6:
			hit = origin + direction * ((self.center - origin).dot(axis) / denom)
			vec = hit - self.center
			vec -= axis * vec.dot(axis)
		if vec.length_squared < 1e-12:
			vec = axis.orthogonal()
		return vec.normalized()

	def _trackball_vectors(self, points, mean):
		if self.trackball_edges is not None:
			return [ctx.world_point(ob, b) - ctx.world_point(ob, a) for ob, a, b in self.trackball_edges]
		center = mean if len(points) > 1 else self.center
		return [p - center for p in points]

	def _sample_trackball(self, points, mean):
		# The mouse input disambiguates turns and selections with no observable rotation.
		x, y = self.trackball_input
		if self.trackball_snap != self.trackball_ctrl:
			step = math.radians(1 if self.trackball_shift else 5)
			x, y = round(x / step) * step, round(y / step) * step
		components = [-y, x]
		for i, number in enumerate(self.trackball_numbers):
			try:
				value = float(number)
			except ValueError:
				continue
			if math.isfinite(value):
				components[i] = value if self.trackball_unit == 'RADIANS' else math.radians(value)
		hint = self.view_basis @ Vector((*components, 0))
		axis, angle = hint.normalized(), hint.length
		if self.object:
			change = self.object.matrix_world.to_3x3() @ self.linear.inverted_safe()
			axis, angle = change.to_quaternion().to_axis_angle()
		else:
			pairs = list(zip(self.trackball_vectors, self._trackball_vectors(points, mean)))
			if pairs:
				# A point's displacement is perpendicular to the rotation axis.
				# Trackball's axis lies in the view plane, so one projected chord identifies it.
				view_normal = self.view_basis.col[2]
				normals = [view_normal.cross(b - a) for a, b in pairs]
				normal = max(normals, key=lambda n: n.length_squared)
				if normal.length_squared > 1e-12:
					axis = normal.normalized()
				sine = sum(axis.dot(a.cross(b)) for a, b in pairs)
				cosine = sum(a.dot(b) - a.dot(axis)*b.dot(axis) for a, b in pairs)
				if abs(sine) + abs(cosine) > 1e-12:
					angle = math.atan2(sine, cosine)
		if abs(angle) < 1e-6 and hint.length > math.pi:
			axis = hint.normalized()
		angle += round((hint.dot(axis) - angle) / math.tau) * math.tau
		self.trackball_angles = tuple(angle * axis.dot(self.view_basis.col[i]) for i in range(2))

	@property
	def display_center(self):
		return self.center + self.delta if self.kind == 'MOVE' else self.center

	def record_event(self, event):
		if self.kind == 'TRACKBALL':
			self.trackball_ctrl, self.trackball_shift = event.ctrl, event.shift
			if event.type == 'MOUSEMOVE':
				mouse = Vector((event.mouse_region_x, event.mouse_region_y))
				self.trackball_input += (mouse - self.trackball_mouse) * (0.01 / 30 if event.shift else 0.01)
				self.trackball_mouse = mouse
		if event.value != 'PRESS' or event.ctrl or event.alt:
			return
		number = self.trackball_numbers[self.trackball_field] if self.kind == 'TRACKBALL' else self.numeric
		if event.type == 'BACK_SPACE':
			number = number[:-1]
		elif event.type in {'DEL', 'DELETE'}:
			number = ''
		elif event.unicode and event.unicode in '0123456789.+-*/()':
			# Only used to distinguish whole turns, never to drive a transform.
			number += event.unicode
		if self.kind == 'TRACKBALL':
			self.trackball_numbers[self.trackball_field] = number
			if event.type == 'TAB':
				if event.shift:
					self.trackball_snap = not self.trackball_snap
				elif any(self.trackball_numbers):
					self.trackball_field = 1 - self.trackball_field
		else:
			self.numeric = number

	def sample(self):
		points = [ctx.world_point(ob, v) for ob, v in self.sample_items]
		mean = sum(points, Vector()) / len(points)
		self.delta = mean - self.mean
		if self.kind == 'TRACKBALL':
			self._sample_trackball(points, mean)
		elif self.kind == 'SCALE':
			if self.object:
				change = self.object.matrix_world.to_3x3() @ self.linear.inverted_safe()
				self.factors = Vector(tuple(u.dot(change @ u) for u in self.basis.col))
			else:
				before = [self.basis.transposed() @ (p - self.center) for p in self.points]
				after = [self.basis.transposed() @ (p - self.center) for p in points]
				self.factors = Vector(tuple(
					sum(a[i] * b[i] for a, b in zip(before, after)) / d if (d := sum(a[i]**2 for a in before)) > 1e-12 else 1.0
					for i in range(3)))
		elif self.kind == 'ROTATE':
			normal = self.rot_axis
			if self.object:
				before = list(self.linear.col)
				after = list(self.object.matrix_world.to_3x3().col)
			else:
				before = [p - self.center for p in self.points]
				after = [p - self.center for p in points]
			dot, cross = 0.0, 0.0
			for a, b in zip(before, after):
				a = a - normal * a.dot(normal)
				b = b - normal * b.dot(normal)
				dot += a.dot(b)
				cross += normal.dot(a.cross(b))
			raw = math.atan2(cross, dot)
			self.angle += (raw - self.previous_angle + math.pi) % math.tau - math.pi
			self.previous_angle = raw
			# Native RNA values are only saved when a modal transform ends.
			# Geometry gives the applied angle; numeric input supplies turn count.
			try:
				number = math.radians(float(self.numeric))
			except ValueError:
				pass
			else:
				self.angle = (raw + round((number - raw) / math.tau) * math.tau
								if abs(dot) + abs(cross) > 1e-12 else number)

	def text(self, context):
		if self.kind in {'ROTATE', 'TRACKBALL'}:
			if self.kind == 'TRACKBALL':
				angles = [(axis, angle) for axis, angle in zip('XY', self.trackball_angles)
							if abs(angle) >= TRACKBALL_MIN_ANGLE]
			else:
				name = 'XYZ'[self.axis] if self.axis >= 0 else 'Screen'
				angles = [(name, self.angle)]
			show_radians = settings.preferences(context).show_radians
			lines = []
			for name, angle in angles:
				line = f'{name}  {math.degrees(angle):+.2f}°'
				if show_radians:
					line += f'   {angle:+.3f} r'
				lines.append(line)
			return '\n'.join(lines)
		if self.kind == 'SCALE':
			if self.axis < 0:
				factor = sum(self.factors) / 3
				return f'XYZ  {factor:.4f}×   ({(factor - 1)*100:+.2f}%)'
			return f'{"XYZ"[self.axis]}  {self.factors[self.axis]:.4f}×   ({(self.factors[self.axis]-1)*100:+.2f}%)'
		values = self.basis.transposed() @ self.delta
		axes = [i for i, enabled in enumerate(self.constraint) if enabled] if self.axis >= 0 else [i for i, v in enumerate(self.delta) if abs(v) > 1e-7]
		if self.axis < 0:
			values = self.delta
		if not axes:
			return 'Screen  0'

		def fmt(value):
			units = context.scene.unit_settings
			if units.system != 'NONE':
				return ('+' if value >= 0 else '') + bpy.utils.units.to_string(units.system, 'LENGTH', value * units.scale_length, precision=4)
			return f'{value:+.4f}'

		return '   '.join(f'{"XYZ"[i]}  {fmt(values[i])}' for i in axes)

def _draw_text():
	context = bpy.context
	s = current(context)
	if s is None:
		return
	try:
		anchor = view3d_utils.location_3d_to_region_2d(s.region, context.region_data, s.display_center)
		if anchor is None:
			return
		p = settings.preferences(context)
		scale = context.preferences.system.ui_scale
		blf.size(0, p.font_size * scale)
		lines = s.text(context).splitlines()
		if not lines:
			return
		width, height = map(max, zip(*(blf.dimensions(0, line) for line in lines)))
		spacing = p.font_size * scale * 1.2
		height += (len(lines)-1) * spacing
		x = max(12, min(anchor.x + 32 * scale, s.region.width - width - 12))
		y = max(20, min(anchor.y - 40 * scale, s.region.height - height - 12))
		blf.enable(0, blf.SHADOW)
		blf.shadow(0, 5, 0, 0, 0, 0.9)
		blf.shadow_offset(0, 1, -1)
		blf.color(0, 1, 1, 1, 1)
		for i, line in enumerate(reversed(lines)):
			blf.position(0, x, y + i*spacing, 0)
			blf.draw(0, line)
		blf.disable(0, blf.SHADOW)
	except (ReferenceError, RuntimeError):
		pass

def _draw_sector(s, start, normal, angle, color, width):
	u = start * s.radius
	lines = [s.center, s.center + u]
	if abs(angle) >= 1e-6:
		steps = max(2, int(abs(angle) / math.tau * 128))
		v = normal.cross(u)
		arc = [s.center + u * math.cos(angle * i / steps) + v * math.sin(angle * i / steps) for i in range(steps + 1)]
		verts = [co for i in range(steps) for co in (s.center, arc[i], arc[i+1])]
		lines += [co for a, b in zip(arc, arc[1:]) for co in (a, b)]
		lines += [s.center, arc[-1]]
		_draw_batch('TRIS', verts, (*color, 0.8))
	_draw_batch('LINES', lines, (*color, 0.95), width)

def _draw_pie():
	context = bpy.context
	s = current(context)
	if s is None or s.kind not in {'ROTATE', 'TRACKBALL'}:
		return
	blend,depth = gpu.state.blend_get(),gpu.state.depth_test_get()
	try:
		p = settings.preferences(context)
		if s.kind == 'TRACKBALL':
			# Sample in this draw pass so the pies and readouts update together.
			s.sample()
		gpu.state.blend_set('ALPHA')
		gpu.state.depth_test_set('NONE')
		with gpu.matrix.push_pop(),gpu.matrix.push_pop_projection():
			gpu.matrix.load_matrix(context.region_data.view_matrix)
			gpu.matrix.load_projection_matrix(context.region_data.window_matrix)
			if s.kind == 'TRACKBALL':
				_draw_trackball_pies(s, p)
			else:
				angle = math.copysign(min(abs(s.angle), math.tau), s.angle)
				_draw_sector(s, s.pie_start, s.rot_axis, angle, p.color_hover, p.line_width)
	finally:
		gpu.state.blend_set(blend)
		gpu.state.depth_test_set(depth)

def _draw_trackball_pies(s, p):
	brightness = p.trackball_pie_brightness
	colors = (tuple(channel * brightness for channel in p.color_hover), p.color_hover)
	for axis in (1, 0):
		angle = s.trackball_angles[axis]
		if abs(angle) < TRACKBALL_MIN_ANGLE:
			continue
		sweep = math.fmod(angle, math.tau)
		if math.tau - abs(sweep) < 1e-6:
			sweep = 0.0
		normal = s.trackball_pie_normals[axis]
		_draw_sector(s, s.trackball_pie_start, normal, sweep, colors[axis], p.line_width)

def _start_draw():
	if not _DRAW:
		_DRAW.append(bpy.types.SpaceView3D.draw_handler_add(_draw_text, (), 'WINDOW', 'POST_PIXEL'))
		_DRAW.append(bpy.types.SpaceView3D.draw_handler_add(_draw_pie, (), 'WINDOW', 'POST_VIEW'))

def shutdown():
	global _SESSION
	if _SESSION:
		_SESSION.stopped = True
	_SESSION = None
	while _DRAW:
		bpy.types.SpaceView3D.draw_handler_remove(_DRAW.pop(), 'WINDOW')
	settings.redraw()

def prepare(context, gizmo):
	"""
	Configure the directly bound native operator, then attach a read-only observer.
.
	A nested bpy.ops.transform invocation uses the window's latest event state,
	which may be ahead of the press currently being handled. Direct gizmo binding
	preserves Blender's original press coordinates even for very fast drags.
	"""
	global _SESSION
	if current():
		shutdown()
	s = Session(context, gizmo.mouse, gizmo.kind, gizmo.axis)
	s.direction = gizmo.direction
	_SESSION = s
	props = gizmo.operator_properties
	props.release_confirm = True
	if s.kind != 'TRACKBALL':
		props.constraint_axis = s.constraint
		props.orient_type = s.orient
		props.orient_matrix = s.basis
		props.orient_matrix_type = s.orient
		if s.kind == 'ROTATE':
			props.orient_axis = 'XYZ'[s.axis] if s.axis >= 0 else 'Z'
	else:
		context.area.tag_redraw()
	_start_draw()

	def check_start():
		if current() is not s or s.stopped:
			return None
		try:
			running = gizmo.is_modal
		except ReferenceError:
			running = False
		if not running:
			shutdown()
		return None

	bpy.app.timers.register(check_start, first_interval=0.001)

CLASSES = ()
