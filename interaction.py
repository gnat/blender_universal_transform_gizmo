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

	def _start_direction(self, context, mouse):
		origin = view3d_utils.region_2d_to_origin_3d(self.region, context.region_data, mouse)
		direction = view3d_utils.region_2d_to_vector_3d(self.region, context.region_data, mouse)
		denom = direction.dot(self.rot_axis)
		vec = Vector()
		if abs(denom) > 1e-6:
			hit = origin + direction * ((self.center - origin).dot(self.rot_axis) / denom)
			vec = hit - self.center
			vec -= self.rot_axis * vec.dot(self.rot_axis)
		if vec.length_squared < 1e-12:
			vec = self.rot_axis.orthogonal()
		return vec.normalized()

	@property
	def display_center(self):
		return self.center + self.delta if self.kind == 'MOVE' else self.center

	def record_event(self, event):
		if event.value != 'PRESS' or event.ctrl or event.alt:
			return
		if event.type == 'BACK_SPACE':
			self.numeric = self.numeric[:-1]
		elif event.type in {'DEL', 'DELETE'}:
			self.numeric = ''
		elif event.unicode and event.unicode in '0123456789.+-*/()':
			# Only used to distinguish whole turns, never to drive a transform.
			self.numeric += event.unicode

	def sample(self):
		points = [ctx.world_point(ob, v) for ob, v in self.sample_items]
		mean = sum(points, Vector()) / len(points)
		self.delta = mean - self.mean
		if self.kind == 'SCALE':
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
		if self.kind == 'ROTATE':
			name = 'XYZ'[self.axis] if self.axis >= 0 else 'Screen'
			return f'{name}  {math.degrees(self.angle):+.2f}°   {self.angle:+.4f} rad'
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
		text = s.text(context)
		width, height = blf.dimensions(0, text)
		x = max(12, min(anchor.x + 32 * scale, s.region.width - width - 12))
		y = max(20, min(anchor.y - 40 * scale, s.region.height - height - 12))
		blf.enable(0, blf.SHADOW)
		blf.shadow(0, 5, 0, 0, 0, 0.9)
		blf.shadow_offset(0, 1, -1)
		blf.color(0, 1, 1, 1, 1)
		blf.position(0, x, y, 0)
		blf.draw(0, text)
		blf.disable(0, blf.SHADOW)
	except (ReferenceError, RuntimeError):
		pass

def _draw_pie():
	context = bpy.context
	s = current(context)
	if s is None or s.kind != 'ROTATE':
		return
	blend,depth = gpu.state.blend_get(),gpu.state.depth_test_get()
	try:
		p = settings.preferences(context)
		angle = math.copysign(min(abs(s.angle), math.tau), s.angle)
		steps = max(2, int(abs(angle) / math.tau * 128))
		u = s.pie_start * s.radius
		v = s.rot_axis.cross(u)
		arc = [s.center + u * math.cos(angle * i / steps) + v * math.sin(angle * i / steps) for i in range(steps + 1)]
		verts = [co for i in range(steps) for co in (s.center, arc[i], arc[i+1])]
		gpu.state.blend_set('ALPHA')
		gpu.state.depth_test_set('NONE')
		lines = [co for a, b in zip(arc, arc[1:]) for co in (a, b)]
		lines += [s.center, arc[0], s.center, arc[-1]]
		with gpu.matrix.push_pop(),gpu.matrix.push_pop_projection():
			gpu.matrix.load_matrix(context.region_data.view_matrix)
			gpu.matrix.load_projection_matrix(context.region_data.window_matrix)
			_draw_batch('TRIS', verts, (*p.color_hover, 0.8))
			_draw_batch('LINES', lines, (*p.color_hover, 0.95), p.line_width)
	finally:
		gpu.state.blend_set(blend)
		gpu.state.depth_test_set(depth)

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
	props.constraint_axis = s.constraint
	props.orient_type = s.orient
	props.orient_matrix = s.basis
	props.orient_matrix_type = s.orient
	if s.kind == 'ROTATE':
		props.orient_axis = 'XYZ'[s.axis] if s.axis >= 0 else 'Z'
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
