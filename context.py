# SPDX-License-Identifier: GPL-3.0-or-later
"""Selection, pivot and orientation helpers. Coordinates here are world space."""
import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
SUPPORTED_MODES = {'OBJECT', 'EDIT_MESH', 'POSE'}

class Selection(list):
	"""Keep wrapped edit BMeshes alive as long as their vertex wrappers are used."""
	def __init__(self):
		super().__init__()
		self.bmeshes = []

def has_selection(context):
	if context.mode == 'EDIT_MESH':
		return any(ob.type == 'MESH' and ob.data.total_vert_sel > 0
					for ob in context.objects_in_mode_unique_data)
	return bool(selection(context))

def selection(context):
	if context.mode == 'POSE':
		bones = [bone for bone in context.selected_pose_bones or ()
					if bone.id_data.is_editable and bone.id_data.data.pose_position == 'POSE']
		selected = set(bones)
		# Selected descendants follow their selected ancestors in the group pivot.
		return [(bone.id_data, bone) for bone in bones
				if not any(parent in selected for parent in bone.parent_recursive)]
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

def world_matrix(ob, bone):
	return ob.matrix_world @ bone.matrix if bone is not None else ob.matrix_world

def world_point(ob, element):
	if isinstance(element, bpy.types.PoseBone):
		return ob.matrix_world @ element.head
	return ob.matrix_world @ element.co if element is not None else ob.matrix_world.translation.copy()

def pose_reference(context, items):
	active = context.active_pose_bone
	return next((item for item in items if item[1] == active), items[0])

def pose_handle_bone(ob, bone):
	if (ob.data.show_bone_custom_shapes and bone.custom_shape and bone.custom_shape_transform
			and bone.use_transform_at_custom_shape):
		return bone.custom_shape_transform
	return bone

def active_point(context):
	ob = context.active_object
	if ob is None:
		return None
	if context.mode == 'POSE':
		bone = context.active_pose_bone
		return world_point(ob, pose_handle_bone(ob, bone)) if bone and not bone.hide else None
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

def _bounds_center(points):
	return Vector(tuple((min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)))

def pivot(context, items=None):
	mode = context.scene.tool_settings.transform_pivot_point
	if items is None and mode in {'CURSOR', 'ACTIVE_ELEMENT'}:
		if not has_selection(context):
			return None
	else:
		items = selection(context) if items is None else items
	if items is not None and not items:
		return None
	if mode == 'CURSOR':
		return context.scene.cursor.location.copy()
	if mode == 'ACTIVE_ELEMENT':
		active = active_point(context)
		if active is not None:
			return active
	if items is None:
		items = selection(context)
		if not items:
			return None
	if context.mode == 'POSE':
		points = [world_point(ob, pose_handle_bone(ob, bone)) for ob, bone in items]
		if mode in {'BOUNDING_BOX_CENTER', 'ACTIVE_ELEMENT'}:
			matrix = context.active_object.matrix_world
			inverse = matrix.inverted_safe()
			return matrix @ _bounds_center([inverse @ point for point in points])
	else:
		points = [world_point(ob, v) for ob, v in items]
	if mode == 'BOUNDING_BOX_CENTER':
		return _bounds_center(points)
	return sum(points, Vector()) / len(points)

def orientation(context):
	slot = context.scene.transform_orientation_slots[0]
	name = slot.type
	ob = context.active_object
	if name == 'GLOBAL' or ob is None:
		return 'GLOBAL', Matrix.Identity(3)
	if name == 'VIEW':
		return name, view_basis(context)
	if name == 'CURSOR':
		return name, context.scene.cursor.matrix.to_quaternion().to_matrix()
	if slot.custom_orientation:
		return name, slot.custom_orientation.matrix.copy()
	if context.mode == 'POSE':
		active = context.active_pose_bone
		if name == 'PARENT':
			armature = ob.matrix_world.to_quaternion()
			if active and active.parent:
				armature = armature @ active.parent.matrix.to_quaternion()
			return name, armature.to_matrix()
		if name == 'GIMBAL':
			gimbal = _pose_gimbal_basis(ob, active)
			if gimbal is not None:
				return name, gimbal
		if active and not active.hide and context.scene.tool_settings.transform_pivot_point == 'ACTIVE_ELEMENT':
			bones = [active]
		else:
			bones = [bone for owner, bone in selection(context) if owner == ob]
		if not bones:
			return name, Matrix.Identity(3)
		frames = [pose_handle_bone(ob, bone).matrix.to_3x3() for bone in bones]
		normal_matrix = ob.matrix_world.to_3x3().inverted_safe().transposed()
		z = (normal_matrix @ sum((frame.col[2] for frame in frames), Vector())).normalized()
		y = normal_matrix @ sum((frame.col[1] for frame in frames), Vector())
		x = y.cross(z)
		if z.length_squared < 1e-12 or x.length_squared < 1e-12:
			return name, Matrix.Identity(3)
		x.normalize()
		return name, Matrix((x, z.cross(x), z)).transposed()
	local = ob.matrix_world.to_quaternion().to_matrix()
	if name == 'NORMAL' and context.mode == 'EDIT_MESH':
		bm = bmesh.from_edit_mesh(ob.data)
		elem = bm.select_history.active
		face = bm.faces.active
		normal = Vector()
		tangent = Vector()
		if face is not None and face.select:
			normal = face.normal.copy()
			tangent = face.verts[1].co - face.verts[0].co
		else:
			faces = [f for f in bm.faces if f.select and not f.hide]
			if faces:
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

def _pose_gimbal_basis(ob, bone):
	if bone is None or bone.rotation_mode == 'QUATERNION':
		return None
	basis = ob.matrix_world.to_3x3()
	if bone.parent:
		parent = bone.parent.matrix if bone.bone.use_inherit_rotation else bone.parent.bone.matrix_local
		basis = basis @ parent.to_3x3()
	basis = basis @ bone.bone.matrix
	if bone.rotation_mode == 'AXIS_ANGLE':
		angle, *direction = bone.rotation_axis_angle
		axis = Vector(direction).normalized()
		if axis.length_squared <= 1e-12:
			return None
		x = Vector((axis.y, axis.z, axis.x)).cross(axis)
		x = x.normalized() if x.length_squared > 1e-12 else axis.orthogonal().normalized()
		x = Quaternion(axis, angle) @ x
		axes = (x, axis.cross(x), axis)
	else:
		outer = Quaternion()
		axes = list(AXES)
		for axis in reversed(bone.rotation_mode):
			i = 'XYZ'.index(axis)
			axes[i] = outer @ AXES[i]
			outer = outer @ Quaternion(AXES[i], bone.rotation_euler[i])
	return Matrix(tuple((basis @ axis).normalized() for axis in axes)).transposed()

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
