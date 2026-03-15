@echo off
REM Download the LLM model for Mira
REM Qwen 2.5 1.5B Instruct (Q4_K_M quantization, ~1.1GB)

set MODEL_DIR=models
set MODEL_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf
set MODEL_URL=https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/%MODEL_FILE%

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

if exist "%MODEL_DIR%\%MODEL_FILE%" (
    echo Model already exists: %MODEL_DIR%\%MODEL_FILE%
    echo Delete it first if you want to re-download.
    exit /b 0
)

echo Downloading %MODEL_FILE% (~1.1 GB)...
echo From: %MODEL_URL%
echo.

curl -L --progress-bar -o "%MODEL_DIR%\%MODEL_FILE%" "%MODEL_URL%"

if exist "%MODEL_DIR%\%MODEL_FILE%" (
    echo.
    echo Download complete: %MODEL_DIR%\%MODEL_FILE%
) else (
    echo Download failed!
    exit /b 1
)
