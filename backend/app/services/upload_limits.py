"""Resource bounds for decoded uploads. ffprobe is preferred; OpenCV is fallback."""
import subprocess, json, os

def validate_image_limits(width, height, size, settings):
    pixels = int(width or 0) * int(height or 0)
    if settings.MAX_IMAGE_PIXELS and pixels > settings.MAX_IMAGE_PIXELS:
        raise ValueError(f"Image pixel limit exceeded: {pixels} > {settings.MAX_IMAGE_PIXELS}.")
    ratio = pixels / max(int(size or 1), 1)
    # A flat screenshot legitimately compresses to a few KB, so the ratio only matters for very large images.
    min_pixels = int(getattr(settings, "DECOMPRESSION_RATIO_MIN_PIXELS", 0) or 0)
    if settings.MAX_DECOMPRESSION_RATIO and pixels >= min_pixels and ratio > settings.MAX_DECOMPRESSION_RATIO:
        raise ValueError(f"Image decompression ratio limit exceeded: {ratio:.1f} > {settings.MAX_DECOMPRESSION_RATIO}.")

class VideoProbeUnavailable(ValueError):
    """The video could not be read by ffprobe or OpenCV, so frame and duration limits could not be checked."""

def validate_video_limits(path, size, settings):
    try:
        proc = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries", "stream=nb_read_frames,duration", "-of", "json", str(path)], capture_output=True, text=True, timeout=settings.UPLOAD_PROBE_TIMEOUT_SECONDS)
        if proc.returncode == 0:
            streams=json.loads(proc.stdout).get("streams", [])
            frames=sum(int(x.get("nb_read_frames") or 0) for x in streams)
            duration=max([float(x.get("duration") or 0) for x in streams] or [0])
        else: frames=duration=0
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError): frames=duration=0
    if not frames:
        try:
            import cv2
            cap=cv2.VideoCapture(str(path)); frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0); fps=float(cap.get(cv2.CAP_PROP_FPS) or 0); duration=frames/fps if fps else 0; cap.release()
        except Exception: frames=duration=0
    frames = max(int(frames or 0), 0)  # OpenCV reports -1 for a file it cannot open; never treat that as 'ok'
    duration = max(float(duration or 0), 0.0)
    if frames and settings.MAX_VIDEO_FRAMES and frames > settings.MAX_VIDEO_FRAMES: raise ValueError(f"Video frame-count limit exceeded: {frames} > {settings.MAX_VIDEO_FRAMES}.")
    if duration and settings.MAX_VIDEO_DURATION_SECONDS and duration > settings.MAX_VIDEO_DURATION_SECONDS: raise ValueError(f"Video duration limit exceeded: {duration:.1f}s > {settings.MAX_VIDEO_DURATION_SECONDS}s.")
    if not frames: raise VideoProbeUnavailable("Video could not be safely probed; upload refused.")
