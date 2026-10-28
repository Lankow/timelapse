@echo off
cd /d "%~dp0"
python "%~dp0make_body_videos.py" --analyze-only --output "%~dp0..\Output\Video\Body_Tracking"
if errorlevel 1 goto failed
python "%~dp0refine_body_torso.py" --source-report "%~dp0..\Output\Video\Body_Tracking\alignment_report.json"
if errorlevel 1 goto failed
python "%~dp0render_refined_body.py" --extras
if errorlevel 1 goto failed
echo Refined videos are ready in Output\Video\Body_Refined.
pause
exit /b 0
:failed
echo Generation failed. Review the message above.
pause
exit /b 1
