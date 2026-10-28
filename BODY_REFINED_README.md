# Refined body timelapse

Run `Generate_Refined_Body_Videos.cmd` to analyze the archive and regenerate the
refined version in `Output/Video/Body_Refined`. The original body videos remain
in `Body_Stabilized`. Source photos and face videos are unchanged.

The front view tracks features inside the chest tattoo, using SIFT matching and
RANSAC to estimate translation, rotation, and uniform scaling. The tracking mask
excludes body contours and the phone. Alternate tattoo references, registered to
the first photo's coordinate system, handle appearance changes across the archive.
The crop emphasizes head, torso, and upper legs. The four-view video uses this
refined front alongside the original back and side alignments.

This removes dependence on head tilt and hair size. It does not independently
resize width/height, reshape the body, or generate intermediate images. Breathing,
skin stretch, pose, perspective, and lighting still affect visual comparisons;
tattoo size normalization is approximate and is not a physical measurement.

Playback is eight photos per second at 24 FPS: all 559 photos in 69.875 seconds.
The monthly comparison holds each month's middle available photo for 1.5 seconds,
giving 31.5 seconds for 21 months. Date labels are month/year from source folders.

`alignment_report.json` records every anchor, inlier count, match count, and
registration error. `torso_tracking.json` stores the tracking results. The initial
archive matched all 559 photos; seven needed alternate references. Review sheets
include weak matches and timeline samples. MP4s use the same `mp4v` codec as the
original face/body videos; use a desktop player if needed.

To render the already analyzed archive again:

```powershell
python E:\Timelapse\Script\render_refined_body.py --extras
```

To render only the front:

```powershell
python E:\Timelapse\Script\render_refined_body.py --views front --layout separate
```

The central-face experiment is retained as `refine_body_front.py`; the final
recommended pipeline uses `refine_body_torso.py`. Running the face experiment
replaces refined alignment data, so rerun the refined launcher afterward to
restore torso tracking.

Tests in `test_body_videos.py` verify that a known camera transform can be
recovered even when the synthetic torso width changes, and that output scaling
preserves proportions. Each rendered video is checked for expected frame count,
FPS, and decoding at the beginning, middle, and end before replacing its file.
