import time
import re
from pathlib import Path
import os
import shutil
import tempfile
import win32com.client
import pythoncom

from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, VideoFileClip
from moviepy.editor import CompositeAudioClip
from PIL import Image

# Compatibility fix for Pillow 10.0.0+ (moviepy uses deprecated ANTIALIAS)
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
# =========================
# PPTX to Images via PowerPoint COM
# =========================


def natural_sort_key(path: Path):
    """
    Extract numbers from filename for natural sorting.
    Example: Slide10.png -> ["slide", 10, ".png"]
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", path.stem)
    ]

def pptx_to_images_via_powerpoint(pptx_path, output_folder):
    """
    Convert PPTX/POTX to PNG images using PowerPoint COM automation (Windows only).
    If opening a .potx directly fails, make a temporary .pptx copy and open that.
    """
    pptx_path = Path(str(pptx_path).strip('"\'"')).resolve()
    output_folder = Path(str(output_folder)).resolve()
    output_folder.mkdir(exist_ok=True)

    temp_copy_dir = None
    powerpoint = None
    presentation = None
    pythoncom.CoInitialize()

    try:
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        try:
            presentation = powerpoint.Presentations.Open(str(pptx_path), WithWindow=False)
        except Exception as first_exc:
            if pptx_path.suffix.lower() == ".potx":
                temp_copy_dir = tempfile.TemporaryDirectory()
                temp_pptx = Path(temp_copy_dir.name) / f"{pptx_path.stem}.pptx"
                shutil.copy(str(pptx_path), str(temp_pptx))
                print(f"⚠️  .potx open failed, trying temporary copy: {temp_pptx}")
                presentation = powerpoint.Presentations.Open(str(temp_pptx), WithWindow=False)
            else:
                raise

        # 17 = PNG export
        presentation.SaveAs(str(output_folder), 17)
        presentation.Close()
        powerpoint.Quit()

        # Small delay to ensure files are written
        time.sleep(1)

        slide_images = (
            list(output_folder.glob("*.png")) +
            list(output_folder.glob("*.jpg"))
        )

        slide_images.sort(key=natural_sort_key)
        print(f"Slides exported as images to {output_folder}")
        return slide_images

    except Exception as e:
        print(f"Error converting PPTX to images: {str(e)}")
        raise
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if powerpoint is not None:
            try:
                powerpoint.Quit()
            except Exception:
                pass
        if temp_copy_dir is not None:
            temp_copy_dir.cleanup()
        pythoncom.CoUninitialize()


# =========================
# Video Creation from Images + Audio
# =========================
def create_video_from_images_and_audio(slide_images, audio_folder, output_video, fps=30):
    """
    Create a video where each slide duration matches its corresponding audio duration.
    If an audio file is missing, a default image duration of 2 seconds is used.
    """
    image_clips = []
    audio_clips = []
    current_start = 0.0

    for idx, img_path in enumerate(slide_images, start=1):
        audio_path = os.path.join(audio_folder, f"slide_{idx}.mp3")

        # Ensure even dimensions (required by libx264)
        img = Image.open(str(img_path))
        w, h = img.size
        if w % 2 or h % 2:
            img = img.resize((w + w % 2, h + h % 2), Image.Resampling.LANCZOS)
            img.save(str(img_path))

        # Get audio duration to set image duration
        slide_duration = 2.0  # fallback if audio missing
        if os.path.exists(audio_path):
            aud = AudioFileClip(audio_path)
            slide_duration = aud.duration
            aud = aud.set_start(current_start)
            audio_clips.append(aud)

        # Create image clip with duration matching audio
        img_clip = (
            ImageClip(str(img_path))
            .resize(height=1080)  # scale proportionally
            .on_color(size=(1920, 1080), color=(0, 0, 0), pos=("center", "center"))
            .set_duration(slide_duration)
        )
        image_clips.append(img_clip)

        current_start += slide_duration

    # Concatenate all image clips
    video = concatenate_videoclips(image_clips)

    # Attach composite audio if any
    if audio_clips:
        video = video.set_audio(CompositeAudioClip(audio_clips))

    video.write_videofile(
        output_video,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",
            "-b:a", "192k"
        ]
    )
    
    # Extract and return video duration
    try:
        video_clip = VideoFileClip(output_video)
        duration = video_clip.duration
        video_clip.close()
        return duration
    except Exception as e:
        print(f"Warning: Could not extract video duration: {e}")
        return None