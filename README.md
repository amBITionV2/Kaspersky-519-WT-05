# Kaspersky-519-WT-05

## Dependency Overview

This project currently depends on:

- **Web app stack**: `Flask`, `Flask-SQLAlchemy`, `SQLAlchemy`, `Werkzeug`, `Jinja2`, `itsdangerous`.
- **SCSS tooling**: `Flask-Scss`, `pyScss`.
- **Web3/Ethereum**: `web3`, `eth-account`, `eth-abi`, `eth-typing`, `eth-utils`, `rlp`, `hexbytes`, `ckzg`.
- **Async/http**: `aiohttp`, `websockets`, `requests` (+ `urllib3`, `charset-normalizer`, `idna`, `certifi`).
- **Utilities**: `pydantic`, `typing_extensions`, `regex`, `toolz`, `cytoolz`, `attrs`, `six`.
- **Crypto/Windows**: `pycryptodome`, `pywin32` (Windows only).

Most packages target Python 3.8–3.12. On Windows, Python 3.11 or 3.12 is recommended.

Note: A local environment folder `myenv/` exists in the repo. Prefer using a project-local `.venv/` and ensure environment folders are git-ignored.

## Quick Start (Windows, Command Prompt)

### 1) Prerequisites

- **Python**: Install Python 3.11 or 3.12 from https://www.python.org/downloads/ and ensure "Add Python to PATH" is checked.
- **Command Prompt**: Use cmd.exe (Start > Run > cmd).
- Optional (rarely needed): Visual C++ Build Tools (for native wheels) https://visualstudio.microsoft.com/visual-cpp-build-tools/

### 2) Create a virtual environment

Run these commands from the project root `Kaspersky-519-WT-05/`:

```bat
REM Create a project-local venv named .venv
py -3 -m venv .venv

REM Activate it
.\.venv\Scripts\activate.bat

REM Upgrade pip/setuptools/wheel (recommended)
python -m pip install --upgrade pip setuptools wheel
```

### 3) Install dependencies

```bat
pip install -r requirements.txt
```

### 4) Verify installation

```bat
python -c "import flask, web3, sqlalchemy; print('OK: ', flask.__version__, web3.__version__, sqlalchemy.__version__)"
```

### 5) Deactivate/reactivate later

```bat
REM Deactivate
deactivate

REM Reactivate when you return to the project
.\.venv\Scripts\activate.bat
```
## Notes

- `myenv/` is intentionally committed and required for deployment. Do not remove it or add it to `.gitignore`. Avoid renaming this folder unless you also update your deployment configuration.
- `pywin32` is Windows-specific; on non-Windows systems you may remove or replace it if not needed.
- If any package fails to build, ensure you are on Python 3.11/3.12 and have the latest `pip` and build tools.
