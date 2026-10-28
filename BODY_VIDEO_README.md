# Body timelapse videos

Run `Generate_Body_Videos.cmd`, or from PowerShell:

```powershell
python E:\Timelapse\Script\make_body_videos.py --extras --overwrite
```

The tool reads monthly numbered collages in `Output/Body/JPG` and writes to
`Output/Video/Body_Stabilized`. Source images and the face video tool are unchanged.
Dependencies are the same as `requirements-video.txt`; processing is local.

The default creates four 720 x 960 MP4s plus a 1440 x 1920 synchronized grid.
The grid preserves front / facing-right above back / facing-left. Side labels
describe image direction, since these are mirror photographs.
All source photos appear in numeric chronological order at six photos per second,
encoded at 24 FPS. With 559 photos the duration is 93.17 seconds.
Labels show the source folder's month/year; no exact capture day is inferred.
Missing filename numbers are not invented or repeated.

`--extras` adds a 42-second monthly grid (for 21 months), holding each month's
middle available photo for two seconds, and four beginning/end comparison JPGs.
The monthly choices are recorded in `alignment_report.json`.

## Alignment

Head templates are manually calibrated from eight dates across this person's
archive in `body_video_config.json`. The tool matches head appearance within a
view-specific search region and aligns head center and apparent head height.
Only translation and uniform scaling are used. No independent width/height
scaling, body reshaping, background generation, morphing, or synthetic frames
are applied. Waist/chest/hip/shoulder widths are never alignment inputs.

Head pose, camera roll, mirror perspective, breathing, stance, clothing, lighting,
and motion blur remain visible. Head size normalization is an approximation to
camera distance, not a physical measurement. Short hair/head tilt can affect it.
The front and back retain full-body framing where source coverage permits; side
views focus on head to thighs because lower legs are often missing in the source.
Dark borders indicate missing source coverage. No body-fat or size measurements
are inferred. The videos are visual comparisons.

`alignment_report.json` records anchors, template similarity, methods, settings,
sources, and output paths. Similarity is not a calibrated probability of accuracy.
The reusable cache is `Script/body_alignment_cache.json`; source metadata,
configuration, and algorithm version invalidate entries when changed.

For manual corrections add entries to `overrides`, keyed by source-relative file
and view, containing `[center_x, center_y, head_height_divided_by_tile_width, 0]`.
Coordinates are normalized to the original tile. Template boxes use normalized
`[x, y, width, height]`. New camera setups may require recalibration.

## Options and verification

Use `--analyze-only` to generate the alignment report without videos;
`--sample-step 20 --output E:\Timelapse\Output\Video\Body_Preview` for a quick
preview; `--views front --layout separate` for one view; and `--speed 12` for a
faster sequence. Run `--help` for all options. FPS must be divisible by speed.
`--output-names side_right all_views --overwrite` regenerates only those outputs
while keeping the other existing video paths in the report.

The encoder is MPEG-4 Part 2 (`mp4v`), as used by the face renderer. A desktop
player may be needed. No audio is added. Each output's frame count, FPS, and
decoding at its start, middle, and end are checked before its temporary file
replaces the final filename. Existing outputs require `--overwrite` in the CLI;
the launcher supplies this flag.

Run `python Script\inspect_body_alignment.py` to generate sheets showing the
weakest matches and timeline samples. These review sheets are distinct from the
date-labelled `Body_preview_*.jpg` sheets written during rendering.

Run `python -m unittest discover -s Script -p test_body_videos.py -v` to verify
torso width does not influence the head anchor and uniform scaling preserves
body aspect ratio. The face renderer's existing tests cover shared image loading,
chronology, affine transformation, and video support logic.
