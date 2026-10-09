# Camera flythrough: street → over the wall → pool → west bed → round the corner → path behind the house → yard.
# Runs after build_scene.py in the same Blender process:
#
#   blender -b --factory-startup --python build_scene.py --python flythrough.py -- --no-render \
#           [--engine eevee|cycles] [--seconds 24] [--fps 25] [--res 1280x720] [--samples 32] [--frames 1-50] [--png]
#
# Writes out/flythrough-<engine>-NNNN-NNNN.mp4 (H.264), or with --png single frames to out/fly_frames/ that survive an
# interrupted run (existing frames are skipped on restart) and are joined by encode_video.py.
# Route points are in Three.js coordinates like VIEWS in index.html; the third value is the relative speed there.
import bpy, math, os, sys
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
ENGINE = arg('--engine', 'eevee'); SECONDS = float(arg('--seconds', 24)); FPS = int(arg('--fps', 25))
RES = [int(v) for v in arg('--res', '1280x720').split('x')]; SAMPLES = int(arg('--samples', 32))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')

# (eye position, look-at point), eye height ~1,7 m above the lawn
ROUTE = [
    ([8.0, 1.7, 39.5],   [9.0, 2.4, 10.0], 0.8),   # on the street, like the "Z ulice" view
    ([8.0, 3.4, 30.0],   [6.0, 0.6, 14.0], 1.4),   # rising over the wall
    ([8.5, 2.2, 21.0],   [4.4, 0.3, 14.7], 1.0),   # towards the pool and the enclosure
    ([-1.2, 1.8, 19.0],  [-3.5, 0.5, 8.0], 0.8),   # turning to the new west bed
    ([-1.6, 1.7, 6.0],   [-3.3, 0.4, -2.0], 0.6),  # slowly along the bed
    ([-2.0, 1.7, -0.6],  [4.0, 0.4, -1.8], 0.6),   # round the north-west corner
    ([4.0, 1.65, -1.85], [12.0, 0.3, -1.9], 0.8),  # on the stepping stones behind the house
    ([12.5, 1.65, -1.85], [18.5, 0.3, 0.2], 0.7),  # round the corner into the yard behind the garage
    ([16.2, 1.65, -0.4], [20.6, 0.3, 1.6], 0.35),  # coming to rest by the fire bowl
]
def b3(p): return np.array([p[0], -p[2], p[1]], float)
P = np.array([b3(p) for p, _, _ in ROUTE]); T = np.array([b3(t) for _, t, _ in ROUTE])
V = np.array([v for _, _, v in ROUTE])

def catmull(pts, u):
    """Centripetal-ish Catmull-Rom through pts, u in [0, len-1]."""
    i = min(int(u), len(pts) - 2); t = u - i
    p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)

# Time along the route: distance divided by the local speed (interpolated between route points), eased at both ends
dense = np.linspace(0, len(P) - 1, 6000)
pos = np.array([catmull(P, u) for u in dense])
step = np.r_[0, np.linalg.norm(np.diff(pos, axis=0), axis=1)]
speed = np.interp(dense, np.arange(len(V)), V)
arc = np.cumsum(step); tim = np.cumsum(step / speed)
n = int(SECONDS * FPS)
s = np.linspace(0, 1, n); s = s * s * (3 - 2 * s) * 0.2 + s * 0.8
us = np.interp(s * tim[-1], tim, dense)

scene = bpy.context.scene
cd = bpy.data.cameras.new('fly'); cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(44); cd.clip_start = 0.05; cd.clip_end = 600
cam = bpy.data.objects.new('cam_fly', cd); scene.collection.objects.link(cam); scene.camera = cam
for f, u in enumerate(us, start=1):
    p = Vector(catmull(P, u)); t = Vector(catmull(T, u))
    cam.location = p; cam.rotation_euler = (t - p).to_track_quat('-Z', 'Y').to_euler()
    if f > 1: cam.rotation_euler.make_compatible(prev)
    prev = cam.rotation_euler.copy()
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
print(f'route {arc[-1]:.0f} m, {n} frames, {arc[-1] / SECONDS:.1f} m/s')

scene.frame_start, scene.frame_end = 1, n
if arg('--frames'): scene.frame_start, scene.frame_end = [int(v) for v in arg('--frames').split('-')]
scene.render.fps = FPS
scene.render.resolution_x, scene.render.resolution_y = RES
if ENGINE == 'eevee':
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee; ee.taa_render_samples = SAMPLES
    for attr, val in (('use_raytracing', True), ('use_shadows', True), ('use_volumetric_shadows', True)):
        if hasattr(ee, attr): setattr(ee, attr, val)
    scene.world.sun_threshold = 5.0 if hasattr(scene.world, 'sun_threshold') else None
else:
    scene.cycles.samples = SAMPLES
    if "--blur" in argv: scene.render.use_motion_blur = True; scene.render.motion_blur_shutter = 0.4   # optional camera motion blur (about twice as slow)

im = scene.render.image_settings
if '--png' in argv:
    im.media_type = 'IMAGE'; im.file_format = 'PNG'; im.color_depth = '8'
    scene.render.use_overwrite = False; scene.render.use_placeholder = True    # resumable, several runs can share the work
    scene.render.filepath = os.path.join(OUT, 'fly_frames', 'f')
else:
    im.media_type = 'VIDEO'; im.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'; scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'; scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.filepath = os.path.join(OUT, f'flythrough-{ENGINE}-')
bpy.ops.render.render(animation=True)
print('video', scene.render.frame_path(frame=scene.frame_start))
