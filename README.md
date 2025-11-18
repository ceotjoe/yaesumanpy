# Yaesu SD Card Manager (Python)

This folder contains a multi-platform rewrite of the original Win32 Yaesu SD card manager.  It mirrors the legacy functionality:

- load every DAT file set inside the `QSOLOG` folder and keep the message/picture lists in memory
- edit message subjects and text, insert new blank messages, delete or deduplicate entries
- insert resized pictures (160×120 for `LOW`, 320×240 for `MID`) and write them into the radio’s `PHOTO` folder with the expected naming pattern
- edit each new picture in a small overlay editor that lets you place the configured callsign as a text overlay (with draggable position, color, and size) plus an optional QR code generated from the configured URL before saving
- inspect pictures, edit their subjects, delete or deduplicate them
- open the stored GPS coordinates in a browser via Google Maps
- persist changes back to `QSOMNG.DAT`, `QSOMSG*.DAT`, and `QSOPCT*.DAT` when saving
- keep call sign / GPS / quality settings in a config dialog (now stored under `~/.yaesuman/config.json` instead of the Windows registry)

## Requirements

- Python 3.9+
- Tkinter (ships with the standard CPython builds)
- Pillow (`pip install -r requirements.txt`)
- qrcode (`pip install -r requirements.txt`)

## Running

```bash
cd python
python app.py
```

On startup the program asks for any `.DAT` file inside the SD card’s `QSOLOG` directory.  After editing, click **Save and Exit** or use **File → Save** to write the updated binary files back to the card.  The picture insert action prompts for a JPEG, takes you through the overlay editor (configure text color/size/position and optionally a QR code generated from the URL configured in the **Configuration** dialog), and finally stores the merged JPEG into the SD card’s `PHOTO` directory.

## Notes

- The Windows-only registry settings have been replaced with a JSON config file inside the user’s home directory to keep the application platform-independent.  This dialog now also stores the optional overlay URL that powers the QR code in the picture editor.
- The built-in image viewer uses Pillow; no extra OS-specific codecs are required.
