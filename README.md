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

Note: The `myenv/` environment folder is included in the repo and required for deployment. Use `myenv/` for local setup as shown below. Do not git-ignore or remove it.

## Quick Start (Windows, Command Prompt)

### Prerequisites

- **Python**: Install Python 3.11 or 3.12 from https://www.python.org/downloads/ and ensure "Add Python to PATH" is checked.
- **Command Prompt**: Use cmd.exe (Start > Run > cmd).
- Optional (rarely needed): Visual C++ Build Tools (for native wheels) https://visualstudio.microsoft.com/visual-cpp-build-tools/

### Setup (cmd)

Run these commands from the project root `Kaspersky-519-WT-05/`:

```bat
python -m venv myenv
myenv\Scripts\activate.bat
pip install -r requirements.txt
```
## Notes

- 'deactivate' for deactivating the virtual environment.
- `myenv/` is intentionally committed and required for deployment. Do not remove it or add it to `.gitignore`. Avoid renaming this folder unless you also update your deployment configuration.
- `pywin32` is Windows-specific; on non-Windows systems you may remove or replace it if not needed.
- If any package fails to build, ensure you are on Python 3.11/3.12 and have the latest `pip` and build tools.
