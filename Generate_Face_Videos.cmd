@echo off
setlocal
echo Face timelapse video generator
echo.
echo 1 - All four separate videos
echo 2 - Front
echo 3 - Profile from lower-left tile
echo 4 - Profile from lower-right tile
echo 5 - Top
echo 6 - Four-view comparison grid
echo 7 - All separate videos plus comparison grid
echo.
echo Selected output videos will be regenerated. Original photos stay untouched.
choice /c 1234567 /n /m "Choose 1-7: "
set "selection=%errorlevel%"
set "views=all"
set "layout=separate"
if "%selection%"=="2" set "views=front"
if "%selection%"=="3" set "views=left"
if "%selection%"=="4" set "views=right"
if "%selection%"=="5" set "views=top"
if "%selection%"=="6" set "layout=grid"
if "%selection%"=="7" set "layout=both"
python "%~dp0make_face_videos.py" --views %views% --layout %layout% --overwrite
if errorlevel 1 (
  echo.
  echo Generation failed. Read the error above and VIDEO_README.md.
) else (
  echo.
  echo Done. Videos are in Output\Video\Stabilized.
)
pause
