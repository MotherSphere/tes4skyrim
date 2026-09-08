@echo off
REM Build TESRuntime.dll (SKSE plugin, x64) and compose_test.exe.
REM
REM Standalone build, same as game_bridge: no SKSE source tree, no CMake.
REM Everything the plugin needs from the game is resolved at runtime through
REM the Address Library or a signature scan, so the only inputs are MSVC and
REM the Windows SDK.

setlocal

set VS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (
    echo [build] ERROR: could not initialise MSVC x64 environment
    exit /b 1
)

cd /d "%~dp0plugin"
if not exist obj mkdir obj
if not exist objt mkdir objt

echo [build] compiling plugin...
cl /nologo /c /EHa /std:c++17 /O2 /MD /W3 /DNDEBUG ^
   plugin.cpp addresses.cpp hook.cpp stream.cpp compose.cpp json.cpp log.cpp ^
   /Fo:obj\
if errorlevel 1 (
    echo [build] ERROR: compilation failed
    exit /b 1
)

echo [build] linking plugin...
link /nologo /DLL /OUT:..\TESRuntime.dll obj\*.obj kernel32.lib shell32.lib ole32.lib
if errorlevel 1 (
    echo [build] ERROR: link failed
    exit /b 1
)
echo [build] OK -^> %~dp0TESRuntime.dll

echo [build] compiling compose_test...
cl /nologo /EHa /std:c++17 /O2 /MD /W3 /DNDEBUG ^
   compose_test.cpp compose.cpp json.cpp /Fo:objt\ /Fe:..\compose_test.exe
if errorlevel 1 (
    echo [build] ERROR: compose_test failed
    exit /b 1
)
echo [build] OK -^> %~dp0compose_test.exe

endlocal
