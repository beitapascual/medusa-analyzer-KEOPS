# Build Windows

Este proyecto se distribuye como una carpeta autocontenida generada con PyInstaller.
El ordenador destino no necesita Python, PyCharm ni instalar dependencias.

## Crear el ejecutable

Desde la raiz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows.ps1
```

El script:

- Usa `.venv` si ya existe.
- Crea `.venv` con `py -3.13` si no existe.
- Verifica que el entorno usa Python 3.13.
- Instala `requirements.txt` y `requirements-build.txt`.
- Genera `dist\MedusaAnalyzer\MedusaAnalyzer.exe`.
- Genera `dist\MedusaAnalyzer-windows-x64.zip`.

## Que entregar

Entrega `dist\MedusaAnalyzer-windows-x64.zip`.

La otra persona solo tiene que:

1. Extraer el ZIP.
2. Abrir `MedusaAnalyzer.exe`.

No debe copiar solo `MedusaAnalyzer.exe` fuera de la carpeta, porque necesita las DLLs
y recursos incluidos junto al ejecutable.

## Build rapido

Si las dependencias ya estan instaladas en `.venv`:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows.ps1 -SkipInstall
```
