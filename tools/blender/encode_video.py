# Joins the PNG frames from `flythrough.py --png` (out/fly_frames/fNNNN.png) into out/flythrough.mp4 with Blender's
# video sequencer, so no separate ffmpeg is needed:
#
#   blender -b --factory-startup --python encode_video.py -- [--fps 25]
import bpy, glob, os, sys

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FPS = int(argv[argv.index('--fps') + 1]) if '--fps' in argv else 25
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
frames = sorted(f for f in glob.glob(os.path.join(OUT, 'fly_frames', 'f*.png')) if os.path.getsize(f) > 0)
if not frames: sys.exit('no frames in out/fly_frames')

scene = bpy.context.scene
w, h = bpy.data.images.load(frames[0]).size
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = w, h, 100
scene.render.fps = FPS
seq = scene.sequence_editor_create()
strips = seq.strips if hasattr(seq, 'strips') else seq.sequences   # renamed in Blender 5
strip = strips.new_image('frames', frames[0], 1, 1)
for f in frames[1:]: strip.elements.append(os.path.basename(f))
scene.frame_start, scene.frame_end = 1, len(frames)
im = scene.render.image_settings
im.media_type = 'VIDEO'; im.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'; scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'; scene.render.ffmpeg.ffmpeg_preset = 'BEST'
scene.render.filepath = os.path.join(OUT, 'flythrough.mp4')
scene.render.use_file_extension = False
bpy.ops.render.render(animation=True)
print('video', scene.render.filepath, len(frames), 'frames')
