# Stabilized face timelapse videos

The reusable tool is `make_face_videos.py`. It reads the monthly four-photo
collages in `../Output/Face/JPG` and writes MP4 videos to
`../Output/Video/Stabilized`. It never changes, deletes, or uploads source images.
It works locally without downloading AI models. The existing Photoshop script
and its configuration are separate and are not modified by this tool.

## Quick start on this computer

Double-click `Generate_Face_Videos.cmd` and select the view(s). The launcher
regenerates the selected movies, replacing their previous versions only after
new files pass verification. All four individual videos and a comparison grid
are available. The original unstabilized movie remains in `Output/Video`.

Python and the dependencies are already installed on this computer. To install
on another computer, run `python -m pip install -r requirements-video.txt` from
this directory. Tested with Python 3.14, OpenCV 4.13, NumPy 2.4.1, and Pillow 12.1.

## Command-line examples

These examples run in PowerShell from any directory:

```powershell
# All four separate views plus a synchronized comparison grid
python E:\Timelapse\Script\make_face_videos.py --views all --layout both

# Only the front view
python E:\Timelapse\Script\make_face_videos.py --views front

# Both profiles and top, at a slower six photos per second
python E:\Timelapse\Script\make_face_videos.py --views left right top --speed 6

# Replace previously generated versions (explicit in CLI, automatic in launcher)
python E:\Timelapse\Script\make_face_videos.py --views all --layout both --overwrite

# Fast preview: every twentieth source image, separate output directory
python E:\Timelapse\Script\make_face_videos.py --sample-step 20 --output E:\Timelapse\Output\Video\QuickPreview

# Analyze and write the alignment report without creating videos
python E:\Timelapse\Script\make_face_videos.py --analyze-only
```

Run `--help` for all options. `--speed` means source photos per second, while
`--fps` means encoded video frames per second. FPS must be a multiple of speed.
The defaults are 12 photos/second and 24 FPS, giving 107 seconds for 1,284 images.
Every photo is retained in the default full render, with no crossfades or
synthetic intermediate faces. Default single-view resolution is 720 x 960,
including the date header. The four-view grid is 1440 x 1920. No audio is added.
The MP4 codec is MPEG-4 Part 2 (`mp4v`); use a desktop player if a browser does
not support it.

## View names and source layout

| CLI name | Source tile | Description |
| --- | --- | --- |
| `front` | upper-left | Face looking at the camera |
| `top` | upper-right | Head tilted forward |
| `left` | lower-left | Profile usually looking toward the right of the image |
| `right` | lower-right | Profile usually looking toward the left of the image |

**Left/right refer to positions in the source collage, not anatomical sides.**
This avoids reversing anatomical labels when photographs have been mirrored.
The grid preserves the original layout: front/top above left/right.

## Stabilization and its limits

For the front view, the tool finds both eyes and aligns their midpoint,
distance, and tilt. Profile and top views match calibrated head templates
drawn from 16 representative images across the archive. Their position and
scale are aligned; actual head pose and tilt in these views are retained.
Template matching combines head contours with grayscale appearance, with position and size checked against the front view from the same collage. This accommodates views where a frontal face detector cannot work.

Only translation, uniform scaling, and (front view) rotation are applied.
There is no face reshaping, hair replacement, beautification, background
generation, or image morphing. Some residual movement is expected from changes
in expression, head pose, hair shape, lighting, and automatic tracking.
Dark borders are shown when a shifted frame extends beyond the original image;
missing image content is not invented. Apparent absolute head size is normalized,
so the videos are for visual comparison, not physical size measurement.

The tool sorts by year, month, and the numeric filename suffix, so `face_1000`
does not appear before `face_999`. JPG and PNG are supported together. The date
label comes from the monthly folder, not an inferred day or EXIF timestamp.
Duplicate frame numbers within a month are rejected. Unexpected collage shapes
are rejected rather than silently cropped with the wrong layout.

## Reuse with new months

1. Export new collages into another monthly folder under `Output/Face/JPG`,
   using the same four-view layout and numbered filenames.
2. Run the launcher again or add `--overwrite` to a command.
3. Review the generated `preview_*.jpg` sheets and `alignment_report.json`.

Unchanged image alignments are reused from `video_alignment_cache.json` beside
the script. Changed source size/timestamp, configuration, or algorithm version
invalidates affected cache entries. Use `--rebuild-cache` to force analysis.
Keep the calibration source photographs: `video_config.json` references them.
For a different person, layout, or camera setup, recalibrate the templates and
crop layout in that config rather than assuming these personal references work.

## Configuration and correcting a frame

Paths in `video_config.json` are relative to that configuration file. View
`quadrant` is `[column, row]` in the 2 x 2 collage. Each view's `target` is
`[x, y, span]`, normalized to the output image below the header. For front,
the span is eye separation; for other views it is the reference head-box width.
Lowering target span zooms out; raising it zooms in. Target x/y controls position.

Each template has a source-relative filename and `box: [x, y, width, height]`,
normalized to its individual source tile. These are real reference crops from
your photos, not generated faces. You can add templates for a substantially
different pose or camera setup.

For a difficult frame, add a manual entry under `overrides`, for example:

```json
"overrides": {
  "49_August_2026/face_1288.jpg": {
    "front": [0.50, 0.60, 0.14, 0.0],
    "top": [0.50, 0.76, 0.43, 0.0]
  }
}
```

These numbers are an **illustration, not measured corrections**. The format is
`[anchor_x, anchor_y, span, angle_degrees]`, normalized to the original tile.
For front, use the midpoint of the eyes and inter-eye distance. For other views,
use the head-box center and width. Positive angle follows OpenCV's rotation
convention. The report records each frame's measured anchor, confidence,
reference template, and whether it was manually corrected or interpolated.

Missing detections are interpolated from neighboring successful detections;
at either end the nearest successful measurement is used. Confidence below 0.52
is counted for review. Valid positions are not smoothed across independent
photographs, since doing so would reintroduce camera movement.

The renderer verifies frame count, FPS, and decoding at the beginning, middle,
and end before moving a `.partial.mp4` into its final filename. An interrupted
run may leave partial files; rerunning replaces those temporary outputs.

Implementation references: [OpenCV cascade detection](https://docs.opencv.org/4.12.0/d1/de5/classcv_1_1CascadeClassifier.html).

## Development checks

Run `python -m unittest discover -s E:\Timelapse\Script -p test_face_videos.py -v` to check numeric ordering, mixed file formats, collage quadrant mapping, eye alignment, and template translation.
