# SPDX-License-Identifier: GPL-3.0-or-later
"""Selection, pivot and orientation helpers. Coordinates here are world space."""
import bpy
import bmesh
from mathutils import Matrix, Vector

AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))

class Selection(list):
	"""Keep wrapped edit BMeshes alive as long as their vertex wrappers are used."""
	def __init__(self):
		super().__init__()
		self.bmeshes = []

def selection(context):
	if context.mode == 'EDIT_MESH':
		result = Selection()
		for ob in context.objects_in_mode_unique_data:
			if ob.type != 'MESH':
				continue
			bm = bmesh.from_edit_mesh(ob.data)
			result.bmeshes.append(bm)
			result.extend((ob, v) for v in bm.verts if v.select and not v.hide)
		return result
	return [(ob, None) for ob in context.selected_editable_objects]

def world_point(ob, vertex):
	return ob.matrix_world @ vertex.co if vertex is not None else ob.matrix_world.translation.copy()

def active_point(context):
	ob = context.active_object
	if ob is None:
		return None
	if context.mode == 'EDIT_MESH':
		bm = bmesh.from_edit_mesh(ob.data)
		elem = bm.faces.active if context.tool_settings.mesh_select_mode[2] else bm.select_history.active
		if elem is not None and elem.select:
			if isinstance(elem, bmesh.types.BMVert):
				co = elem.co
			elif isinstance(elem, bmesh.types.BMEdge):
				co = (elem.verts[0].co + elem.verts[1].co) / 2
			else:
				co = elem.calc_center_median()
			return ob.matrix_world @ co
		return None
	return ob.matrix_world.translation.copy()

def pivot(context, items=None):
	items = selection(context) if items is None else items
	if not items:
		return None
	mode = context.scene.tool_settings.transform_pivot_point
	if mode == 'CURSOR':
		return context.scene.cursor.location.copy()
	if mode == 'ACTIVE_ELEMENT':
		active = active_point(context)
		if active is not None:
			return active
	points = [world_point(ob, v) for ob, v in items]
	if mode == 'BOUNDING_BOX_CENTER':
		return Vector(tuple((min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)))
	return sum(points, Vector()) / len(points)

def orientation(context, requested='FOLLOW'):
	slot = context.scene.transform_orientation_slots[0]
	name = slot.type if requested == 'FOLLOW' else requested
	ob = context.active_object
	if name == 'GLOBAL' or ob is None:
		return 'GLOBAL', Matrix.Identity(3)
	if name == 'VIEW':
		return name, view_basis(context)
	if name == 'CURSOR':
		return name, context.scene.cursor.matrix.to_quaternion().to_matrix()
	if slot.custom_orientation and requested == 'FOLLOW':
		return name, slot.custom_orientation.matrix.copy()
	local = ob.matrix_world.to_quaternion().to_matrix()
	if name == 'NORMAL' and context.mode == 'EDIT_MESH':
		bm = bmesh.from_edit_mesh(ob.data)
		faces = [f for f in bm.faces if f.select and not f.hide]
		elem = bm.select_history.active
		face = bm.faces.active
		normal = Vector()
		tangent = Vector()
		if face is not None and face.select:
			normal = face.normal.copy()
			tangent = face.verts[1].co - face.verts[0].co
		elif faces:
			normal = sum((f.normal for f in faces), Vector())
			tangent = faces[0].verts[1].co - faces[0].verts[0].co
		elif isinstance(elem, bmesh.types.BMEdge):
			normal = sum((v.normal for v in elem.verts), Vector())
			tangent = elem.verts[1].co - elem.verts[0].co
		else:
			normal = sum((v.normal for v in bm.verts if v.select and not v.hide), Vector())
		if normal.length_squared > 1e-12:
			z = (ob.matrix_world.to_3x3().inverted_safe().transposed() @ normal).normalized()
			x = ob.matrix_world.to_3x3() @ tangent
			x -= z * x.dot(z)
			if x.length_squared < 1e-12:
				x = z.orthogonal()
			x.normalize()
			return name, Matrix((x, z.cross(x), z)).transposed()
	if name == 'GIMBAL' and ob.rotation_mode not in {'QUATERNION', 'AXIS_ANGLE'}:
		# Gimbal axes are non-orthogonal; native orientation resolves their constraints.
		return name, local
	return name, local

def view_basis(context):
	# Use the rendered view matrix rather than a separately updated view quaternion.
	return context.region_data.view_matrix.inverted_safe().to_quaternion().to_matrix()

def world_per_pixel(context, center):
	# Derive pixel size from projection depth. Subtracting two unprojected
	# points one pixel apart loses precision (especially in orthographic
	# views), making the handle size oscillate as its world position changes.
	view = context.region_data
	clip = view.window_matrix @ view.view_matrix @ center.to_4d()
	projection_x = abs(view.window_matrix[0][0])
	if clip.w <= 1e-8 or projection_x <= 1e-8 or context.region.width <= 0:
		return None
	return 2.0 * clip.w / (context.region.width * projection_x)
