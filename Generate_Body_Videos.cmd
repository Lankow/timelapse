@echo off
cd /d "%~dp0"
python "%~dp0make_body_videos.py" --extras --overwrite
if errorlevel 1 (
  echo Body video generation failed. See the message above.
) else (
  echo Videos and comparisons are ready in Output\Video\Body_Stabilized.
)
pause
