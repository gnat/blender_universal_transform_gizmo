# SPDX-License-Identifier: GPL-3.0-or-later

import math
from mathutils import Vector

ARROW_HEAD_RADIUS = 0.075
ARROW_HEAD_LENGTH = 0.60

def segments(points, closed=False):
	return [v for i in range(len(points) if closed else len(points)-1)
			for v in (points[i], points[(i+1) % len(points)])]

def circle(radius, start=0, sweep=math.tau, count=96):
	return [(radius * math.cos(start + sweep*i/count), radius * math.sin(start + sweep*i/count), 0) for i in range(count+1)]

def arrow(length, head_radius=ARROW_HEAD_RADIUS, head_length=ARROW_HEAD_LENGTH):
	base = length - min(head_length, length-0.22)
	lines = [(0, 0, 0.20), (0, 0, base + 0.03)]
	ring = [(head_radius*math.cos(math.tau*i/12), head_radius*math.sin(math.tau*i/12), base) for i in range(12)]
	tris = [v for i in range(12) for v in (ring[i], ring[(i+1)%12], (0, 0, length))]
	tris += [v for i in range(1, 11) for v in (ring[0], ring[i], ring[i+1])]
	return lines, tris

def front_half(radius, toward, count=144):
	direction = Vector((toward.x, toward.y, 0))
	amount = direction.length
	points = [Vector(v) for v in circle(radius, count=count)]
	if amount < 1e-8:
		return segments(points), [], 0.0
	front, back = [], []
	for a,b in zip(points,points[1:]):
		da,db = a.dot(direction),b.dot(direction)
		if da >= 0 and db >= 0:
			front.extend((a,b))
		elif da <= 0 and db <= 0:
			back.extend((a,b))
		else:
			cut = a.lerp(b,da/(da-db))
			if da > 0:
				front.extend((a,cut))
				back.extend((cut,b))
			else:
				back.extend((a,cut))
				front.extend((cut,b))
	t = max(0.0,min(1.0,(amount-0.025)/0.125))
	rear_alpha = 1.0-t*t*(3.0-2.0*t)
	return front,back,rear_alpha

def cube(center, size):
	verts = [Vector(center)+Vector((x*size,y*size,z*size)) for x,y,z in
				((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
	faces = ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
	tris = [verts[i] for face in faces for i in (face[0],face[1],face[2],face[0],face[2],face[3])]
	edges = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
	return [verts[i] for edge in edges for i in edge], tris

def closest_side(value, previous=None):
	"""Keep the previous side when the camera is almost perpendicular."""
	if previous is None:
		return 1 if value >= 0 else -1
	return 1 if value > 0.04 else -1 if value < -0.04 else previous

def closest_quadrant(toward, previous=None):
	"""Pick the nearest in-plane quadrant; keep its side near an edge-on view."""
	return tuple(closest_side(value, previous[i] if previous else None)
					for i,value in enumerate(toward[:2]))

def plane(offset, size, signs=(1,1)):
	corners = [(signs[0]*offset+x*size/2,signs[1]*offset+y*size/2,0)
				for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
	return segments(corners, True), [corners[i] for i in (0,1,2,0,2,3)]

def dot(radius=0.045):
	points = circle(radius, count=32)
	return [], [v for a,b in zip(points, points[1:]) for v in ((0,0,0),a,b)]

def distance_segment(p, a, b):
	ab = b - a
	t = max(0, min(1, (p-a).dot(ab)/ab.length_squared)) if ab.length_squared > 1e-9 else 0
	return (p - a - ab*t).length

def in_triangle(p, a, b, c):
	def cross(v, w):
		return v.x*w.y-v.y*w.x

	area = cross(b-a, c-a)
	if abs(area) < 0.5:
		return False
	s, t = cross(p-a, c-a)/area, cross(b-a, p-a)/area
	return s >= 0 and t >= 0 and s+t <= 1
