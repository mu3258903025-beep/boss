@echo off
setlocal
chcp 65001 >nul
set PATH=D:\Git\cmd;%PATH%
cd /d D:\BossJob

echo ==========================================
echo   Publish BossJob project to GitHub
echo ==========================================
echo.

rem 1) init
if not exist ".git" (
  echo [1/5] git init ...
  git init
) else (
  echo [1/5] git repository already exists.
)

rem 2) add (respects .gitignore)
echo [2/5] git add ...
git add -A

rem 3) commit
echo [3/5] git commit ...
git commit -m "BOSS job tool: clean / filter / AI skill extraction / CDP collector"
if errorlevel 1 echo      (nothing new to commit - that is fine)

rem 4) remote
echo.
echo Create an EMPTY repo first:  https://github.com/new
echo    - do NOT add README / .gitignore / license there
echo    - copy the repo URL it gives you
echo.
set /p REPO=Paste your GitHub repo URL here: 
if "%REPO%"=="" (
  echo No URL given. Aborted.
  pause
  exit /b 1
)

echo [4/5] setting remote ...
git remote remove origin >nul 2>&1
git remote add origin "%REPO%"

rem 5) push
echo [5/5] pushing (a browser window may open for GitHub login) ...
git branch -M main
git push -u origin main

echo.
if errorlevel 1 (
  echo Push FAILED.
  echo - If it asked you to sign in, finish that in the browser and run this again.
  echo - Make sure the repo on GitHub is EMPTY (no README/license/gitignore).
) else (
  echo Done! Your project is now on GitHub:
  echo   %REPO%
)
echo.
pause
