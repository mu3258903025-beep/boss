@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

set "PATH=D:\Git\cmd;%PATH%"
where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] git not found. Please confirm D:\Git\cmd\git.exe exists or install Git.
  pause
  exit /b 1
)

cd /d D:\BossJob
echo ==========================================
echo     Publish BossJob project to GitHub
echo ==========================================
echo.

rem ---- 1. LICENSE author ----
set /p AUTHOR=Type your GitHub username (written into LICENSE copyright line): 
set "AUTHOR=!AUTHOR:"=!"
if not "!AUTHOR!"=="" (
  powershell -NoProfile -Command "(Get-Content LICENSE -Raw -Encoding UTF8) -replace 'YOUR_NAME_HERE','!AUTHOR!' | Set-Content LICENSE -Encoding UTF8"
  echo    Updated LICENSE author to: !AUTHOR!
) else (
  echo    No username entered; LICENSE keeps placeholder, edit line 3 later.
)
echo.

rem ---- 2. open create-repo page ----
echo Opening GitHub new-repository page...
echo    Create an EMPTY repo: do NOT check Add README / Add .gitignore / Choose a license.
echo    After creating, copy the repo URL (like https://github.com/you/repo.git).
start "" "https://github.com/new"
echo.

rem ---- 3. init ----
if not exist ".git" (
  echo [1/5] git init ...
  git init
) else (
  echo [1/5] Already a git repo, skip init.
)

rem ---- 4. add + preview ----
echo [2/5] git add ...
git add -A
echo       Files to be committed:
git diff --cached --name-only

rem ---- 5. commit ----
echo [3/5] git commit ...
git commit -m "BOSS job tool: clean / filter / AI skill extraction / CDP collector"
if errorlevel 1 echo       (nothing new to commit, that is fine.)

rem ---- 6. remote ----
set /p REPO=Paste the repo URL here: 
set "REPO=!REPO:"=!"
if "!REPO!"=="" (
  echo No URL given, aborted.
  pause
  exit /b 1
)
set "R=!REPO!"
echo !R! | findstr /i "http" >nul && goto :skipnorm
echo !R! | findstr ":" >nul && goto :skipnorm
set "R=https://github.com/!REPO!.git"
:skipnorm
echo [4/5] Setting remote: !R!
git remote remove origin >nul 2>&1
git remote add origin "!R!"

rem ---- 7. push (force: overwrites GitHub's auto-generated empty README on first publish) ----
echo [5/5] Pushing (if a browser opens, log into GitHub and authorize)...
git branch -M main
git push -u origin main --force

echo.
if errorlevel 1 (
  echo Push FAILED. Common causes:
  echo   - Browser login/authorization not completed: finish it, then re-run this script.
  echo   - Old git without browser login: use a Personal Access Token (I can guide you).
) else (
  echo Done! Project published to: !R!
)
echo.
pause
