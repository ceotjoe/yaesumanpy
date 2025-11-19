# Repository Guidelines

## Project Structure & Module Organization
- `app.py` hosts the Tkinter UI, location picker, and event handlers.
- `data_model.py` carries the binary parsing/writing logic for Yaesu SD card files.
- `picture_editor.py`, `image_utils.py`, and `config_store.py` provide editing helpers, imaging utilities, and config persistence (`~/.yaesuman/config.json`).
- `requirements.txt` lists runtime deps (`Pillow`, `qrcode`, `geopy`). Assets (pictures, DAT files) live outside the repo; point the app to an SD-card dump when prompted.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` – create/enter a virtualenv to isolate dependencies.
- `pip install -r requirements.txt` – install GUI, imaging, QR, and geocoding packages.
- `python app.py` – launch the GUI; it prompts for a `QSOMNG.DAT` path and opens message/picture editors.
- `python -m compileall app.py data_model.py` – quick syntax smoke test for core modules.

## Coding Style & Naming Conventions
- Follow PEP8/black-style conventions: 4-space indent, descriptive snake_case for variables/functions, PascalCase for Tkinter classes.
- Keep UI text strings short; reuse ttk widgets and helper methods where possible.
- Comments should explain tricky binary offsets or conversions (e.g., GPS fixed-point minutes). Avoid restating obvious assignments.

## Testing Guidelines
- No automated suite today; rely on targeted scripts (`python -m compileall …`) plus manual UI checks (load DAT, edit records, Google Maps buttons, location picker).
- When adding utility functions, consider lightweight doctests or `if __name__ == "__main__"` snippets for validation.

## Commit & Pull Request Guidelines
- Use concise, imperative commit messages (e.g., “Add geocoding picker”) mirroring the existing history.
- Each PR should describe user-facing changes, testing performed, and any config impacts (e.g., new deps, files written under `~/.yaesuman`).
- Add screenshots/GIFs for UI changes when practical, especially for new dialogs or workflows.
