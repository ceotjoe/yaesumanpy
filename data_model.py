from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import datetime as dt
import os


TXT_HEADER_SIZE = 128
TXT_TEXT_SIZE = 80
PICTURE_RECORD_SIZE = 128
MNG_RECORD_SIZE = 32

DATE_FIELD_SIZE = 6

MESSAGE_POINTER_OFFSET = 0x50  # 80
MESSAGE_SUBJECT_OFFSET = 0x40  # 64
MESSAGE_DATE_CREATE_OFFSET = 46
MESSAGE_DATE_SEND_OFFSET = 52
MESSAGE_DATE_RECEIVE_OFFSET = 58
MESSAGE_FROM_OFFSET = 30
MESSAGE_TO_OFFSET = 9
MESSAGE_REPEATER_OFFSET = 4
MESSAGE_GPS_OFFSET = 100

PICTURE_SUBJECT_OFFSET = 0x40
PICTURE_FILENAME_OFFSET = 0x54
PICTURE_SIGNATURE_OFFSET = 25
PICTURE_GPS_OFFSET = 100


def _pad_ascii(text: str, length: int, pad: int = 0x20) -> bytes:
    encoded = text.encode("ascii", errors="ignore")[:length]
    return encoded + bytes([pad]) * (length - len(encoded))


def _strip_ascii(data: Sequence[int]) -> str:
    return bytes(data).rstrip(b"\x00 ").decode("ascii", errors="ignore")


def _bcd_to_int(value: int) -> int:
    return ((value >> 4) * 10) + (value & 0xF)


def _int_to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def _decode_date(raw: Sequence[int]) -> str:
    if not raw or raw[0] == 0:
        return "----/--/-- --:--:--"
    year = 2000 + _bcd_to_int(raw[0])
    month = _bcd_to_int(raw[1])
    day = _bcd_to_int(raw[2])
    hour = _bcd_to_int(raw[3])
    minute = _bcd_to_int(raw[4])
    second = _bcd_to_int(raw[5])
    return f"{day:02d}/{month:02d}/{year:04d} {hour:02d}:{minute:02d}:{second:02d}"


def _encode_date(target: bytearray, offset: int, text: str) -> str:
    day, month, year, hour, minute, second = 0, 0, 0, 0, 0, 0
    try:
        parts = text.strip().split()
        if len(parts) == 2:
            dpart, tpart = parts
            day, month, year = map(int, dpart.split("/"))
            hour, minute, second = map(int, tpart.split(":"))
    except ValueError:
        now = dt.datetime.now()
        day, month, year = now.day, now.month, now.year
        hour, minute, second = now.hour, now.minute, now.second

    values = [
        _int_to_bcd(year - 2000),
        _int_to_bcd(month),
        _int_to_bcd(day),
        _int_to_bcd(hour),
        _int_to_bcd(minute),
        _int_to_bcd(second),
    ]
    target[offset : offset + DATE_FIELD_SIZE] = bytes(values)
    return f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}"


def _format_position(raw: Sequence[int]) -> str:
    data = bytes(raw)
    if not data or data[0] not in (ord("N"), ord("S")):
        return "-:-- --' --\" / -:-- --' --\""

    lat_hem = chr(data[0])
    lon_hem = chr(data[10])
    try:
        lat_deg = int(data[1:4].decode("ascii"))
        lon_deg = int(data[11:14].decode("ascii"))
        # The radio stores minutes as a fixed-point value with four decimals.
        lat_min = int(data[4:10].decode("ascii")) / 10000.0
        lon_min = int(data[14:20].decode("ascii")) / 10000.0
    except (ValueError, UnicodeDecodeError):
        return "-:-- --' --\" / -:-- --' --\""

    def _split(value: float) -> tuple[int, int]:
        minutes = int(value)
        seconds = int((value - minutes) * 60)
        return minutes, seconds

    lat_m, lat_s = _split(lat_min)
    lon_m, lon_s = _split(lon_min)
    return (
        f"{lat_hem}:{lat_deg:3d} {lat_m:2d}' {lat_s:2d}\" / "
        f"{lon_hem}:{lon_deg:3d} {lon_m:2d}' {lon_s:2d}\""
    )


def _write_u16_be(buf: bytearray, offset: int, value: int) -> None:
    buf[offset] = (value >> 8) & 0xFF
    buf[offset + 1] = value & 0xFF


def _read_u16_be(buf: Sequence[int], offset: int) -> int:
    return (buf[offset] << 8) | buf[offset + 1]


def _write_u32_be(buf: bytearray, offset: int, value: int) -> None:
    buf[offset] = (value >> 24) & 0xFF
    buf[offset + 1] = (value >> 16) & 0xFF
    buf[offset + 2] = (value >> 8) & 0xFF
    buf[offset + 3] = value & 0xFF


def _read_u32_be(buf: Sequence[int], offset: int) -> int:
    return (
        (buf[offset] << 24)
        | (buf[offset + 1] << 16)
        | (buf[offset + 2] << 8)
        | buf[offset + 3]
    )


@dataclass
class MainConfig:
    callsign: str = "EA7EE"
    gps: str = "N037126800W007038500"
    quality: str = "LOW"
    overlay_url: str = ""

    def normalized(self) -> "MainConfig":
        self.callsign = self.callsign[:16]
        self.gps = self.gps[:20]
        if self.quality not in {"LOW", "MID"}:
            self.quality = "LOW"
        self.overlay_url = self.overlay_url.strip()
        return self


class MessageRecord:
    def __init__(self, header: Optional[bytes] = None, text: Optional[bytes] = None):
        self.header = bytearray(header or (b"\x20" * TXT_HEADER_SIZE))
        self.text = bytearray(text or (b"\x20" * TXT_TEXT_SIZE))

    def copy(self) -> "MessageRecord":
        return MessageRecord(bytes(self.header), bytes(self.text))

    def message_pointer(self) -> int:
        return _read_u32_be(self.header, MESSAGE_POINTER_OFFSET)

    def set_message_pointer(self, value: int) -> None:
        _write_u32_be(self.header, MESSAGE_POINTER_OFFSET, value)

    def set_default_payload(self, config: MainConfig, pointer: int, index: int) -> None:
        self.header[:] = b"\x20" * TXT_HEADER_SIZE
        self.text[:] = b"\x20" * TXT_TEXT_SIZE
        self.header[0] = 0x63
        self.header[1] = 0x00
        _write_u16_be(self.header, 2, index)
        self.header[MESSAGE_REPEATER_OFFSET : MESSAGE_REPEATER_OFFSET + 5] = b"\x00" * 5
        self.set_message_pointer(pointer)
        self.set_from(config.callsign)
        if config.gps and len(config.gps) == 20:
            self.header[MESSAGE_GPS_OFFSET : MESSAGE_GPS_OFFSET + 20] = config.gps.encode(
                "ascii", errors="ignore"
            )
        else:
            self.header[MESSAGE_GPS_OFFSET : MESSAGE_GPS_OFFSET + 20] = b"\xFF" * 20
        self.set_to("ALL")
        self.set_subject("")
        self.set_text("")

    def get_date(self) -> str:
        return _decode_date(
            self.header[
                MESSAGE_DATE_SEND_OFFSET : MESSAGE_DATE_SEND_OFFSET + DATE_FIELD_SIZE
            ]
        )

    def set_date(self, text: str) -> None:
        formatted = _encode_date(self.header, MESSAGE_DATE_CREATE_OFFSET, text)
        _encode_date(self.header, MESSAGE_DATE_SEND_OFFSET, text)
        _encode_date(self.header, MESSAGE_DATE_RECEIVE_OFFSET, text)
        self.set_subject(formatted)

    def set_from(self, value: str) -> None:
        self.header[MESSAGE_FROM_OFFSET : MESSAGE_FROM_OFFSET + 16] = _pad_ascii(value, 16)

    def get_from(self) -> str:
        return _strip_ascii(self.header[MESSAGE_FROM_OFFSET : MESSAGE_FROM_OFFSET + 16])

    def set_to(self, value: str) -> None:
        self.header[MESSAGE_TO_OFFSET : MESSAGE_TO_OFFSET + 16] = _pad_ascii(value, 16)

    def get_to(self) -> str:
        return _strip_ascii(self.header[MESSAGE_TO_OFFSET : MESSAGE_TO_OFFSET + 16])

    def get_repeater(self) -> str:
        field = self.header[MESSAGE_REPEATER_OFFSET : MESSAGE_REPEATER_OFFSET + 5]
        if field[0] == 0:
            return ""
        return _strip_ascii(field)

    def get_position(self) -> str:
        return _format_position(self.header[MESSAGE_GPS_OFFSET : MESSAGE_GPS_OFFSET + 20])

    def get_subject(self) -> str:
        return _strip_ascii(self.header[MESSAGE_SUBJECT_OFFSET : MESSAGE_SUBJECT_OFFSET + 16])

    def set_subject(self, text: str) -> None:
        self.header[MESSAGE_SUBJECT_OFFSET : MESSAGE_SUBJECT_OFFSET + 16] = _pad_ascii(text, 16)

    def get_text(self) -> str:
        return _strip_ascii(self.text)

    def set_text(self, text: str) -> None:
        self.text[:] = _pad_ascii(text, TXT_TEXT_SIZE)


class PictureRecord:
    def __init__(self, header: Optional[bytes] = None):
        self.header = bytearray(header or (b"\x20" * PICTURE_RECORD_SIZE))

    def copy(self) -> "PictureRecord":
        return PictureRecord(bytes(self.header))

    def set_default_payload(self, config: MainConfig, index: int, signature_tail: bytes) -> None:
        self.header[:] = b"\x20" * PICTURE_RECORD_SIZE
        self.header[0] = 0x70
        self.header[1] = 0x00
        _write_u16_be(self.header, 2, index)
        self.set_from(config.callsign)
        if config.gps and len(config.gps) == 20:
            self.header[PICTURE_GPS_OFFSET : PICTURE_GPS_OFFSET + 20] = config.gps.encode(
                "ascii", errors="ignore"
            )
        else:
            self.header[PICTURE_GPS_OFFSET : PICTURE_GPS_OFFSET + 20] = b"\xFF" * 20
        tail = (signature_tail + b"     ")[:5]
        self.header[PICTURE_SIGNATURE_OFFSET : PICTURE_SIGNATURE_OFFSET + 5] = tail

    def get_date(self) -> str:
        return _decode_date(self.header[46:52])

    def set_date(self, text: str) -> None:
        formatted = _encode_date(self.header, 46, text)
        _encode_date(self.header, 52, text)
        _encode_date(self.header, 58, text)
        self.set_subject(formatted)

    def get_from(self) -> str:
        return _strip_ascii(self.header[MESSAGE_FROM_OFFSET : MESSAGE_FROM_OFFSET + 16])

    def set_from(self, value: str) -> None:
        self.header[MESSAGE_FROM_OFFSET : MESSAGE_FROM_OFFSET + 16] = _pad_ascii(value, 16)

    def get_to(self) -> str:
        return _strip_ascii(self.header[MESSAGE_TO_OFFSET : MESSAGE_TO_OFFSET + 16])

    def get_repeater(self) -> str:
        field = self.header[MESSAGE_REPEATER_OFFSET : MESSAGE_REPEATER_OFFSET + 5]
        if field[0] == 0:
            return ""
        return _strip_ascii(field)

    def get_position(self) -> str:
        return _format_position(self.header[PICTURE_GPS_OFFSET : PICTURE_GPS_OFFSET + 20])

    def get_subject(self) -> str:
        return _strip_ascii(self.header[PICTURE_SUBJECT_OFFSET : PICTURE_SUBJECT_OFFSET + 16])

    def set_subject(self, text: str) -> None:
        self.header[PICTURE_SUBJECT_OFFSET : PICTURE_SUBJECT_OFFSET + 16] = _pad_ascii(text, 16)

    def get_filename(self) -> str:
        return _strip_ascii(
            self.header[PICTURE_FILENAME_OFFSET : PICTURE_FILENAME_OFFSET + 16]
        )

    def set_filename(self, name: str) -> None:
        self.header[PICTURE_FILENAME_OFFSET : PICTURE_FILENAME_OFFSET + 16] = _pad_ascii(
            name, 16
        )

    def get_size(self) -> int:
        return _read_u32_be(self.header, 80)

    def set_size(self, value: int) -> None:
        _write_u32_be(self.header, 80, value)


class DataManager:
    """Python port of the legacy CData class."""

    def __init__(self, config: MainConfig):
        self.config = config.normalized()
        self.messages: List[MessageRecord] = []
        self.pictures: List[PictureRecord] = []
        self.main_file: Optional[Path] = None
        self.qso_dir: Optional[Path] = None
        self.photo_dir: Optional[Path] = None
        self.signature_seed = b"HE5Gbv"
        self.signature_tail = self.signature_seed[1:6]
        self.picture_counter = 0
        self.next_message_offset = 0
        self.changed = False

    # ------------------------------------------------------------------
    # Loading / saving
    # ------------------------------------------------------------------
    def load(self, any_dat_path: Path) -> None:
        dat_path = Path(any_dat_path).expanduser().resolve()
        if not dat_path.exists():
            raise FileNotFoundError(dat_path)
        self.main_file = dat_path
        self.qso_dir = dat_path.parent
        self.photo_dir = self.qso_dir.parent / "PHOTO"

        mng_data = (self.qso_dir / "QSOMNG.DAT").read_bytes()
        if len(mng_data) < MNG_RECORD_SIZE:
            raise ValueError("QSOMNG.DAT is corrupted")
        msg_count = (
            0
            if mng_data[0] == 0xFF and mng_data[1] == 0xFF
            else _read_u16_be(mng_data, 0)
        )
        pct_count = (
            0
            if mng_data[16] == 0xFF and mng_data[17] == 0xFF
            else _read_u16_be(mng_data, 16)
        )
        self.picture_counter = _read_u16_be(mng_data, 18)

        self.messages.clear()
        self.pictures.clear()

        msg_path = self.qso_dir / "QSOMSG.DAT"
        msg_dir_path = self.qso_dir / "QSOMSGDIR.DAT"
        msg_fat_path = self.qso_dir / "QSOMSGFAT.DAT"
        if msg_count > 0:
            self._load_messages(msg_path, msg_dir_path, msg_fat_path, msg_count)
        else:
            self.next_message_offset = 0

        pct_dir_path = self.qso_dir / "QSOPCTDIR.DAT"
        pct_fat_path = self.qso_dir / "QSOPCTFAT.DAT"
        if pct_count > 0:
            self._load_pictures(pct_dir_path, pct_fat_path, pct_count)
        else:
            self.signature_seed = b"HE5Gbv"
            self.signature_tail = self.signature_seed[1:6]

        self.changed = False

    def _load_messages(
        self, msg_path: Path, dir_path: Path, fat_path: Path, expected: int
    ) -> None:
        self.next_message_offset = os.path.getsize(msg_path)
        with open(dir_path, "rb") as dir_file, open(fat_path, "rb") as fat_file, open(
            msg_path, "rb"
        ) as msg_file:
            while True:
                dir_bytes = dir_file.read(TXT_HEADER_SIZE)
                if len(dir_bytes) == 0:
                    break
                if len(dir_bytes) != TXT_HEADER_SIZE:
                    raise ValueError("QSOMSGDIR.DAT is corrupted")
                fat_bytes = fat_file.read(4)
                if len(fat_bytes) != 4:
                    raise ValueError("QSOMSGFAT.DAT is corrupted")
                if fat_bytes[0] != 0x40:
                    continue
                pointer = (dir_bytes[0x52] << 8) | dir_bytes[0x53]
                msg_file.seek(pointer)
                text = msg_file.read(TXT_TEXT_SIZE)
                if len(text) != TXT_TEXT_SIZE:
                    raise ValueError("QSOMSG.DAT is corrupted")
                self.messages.append(MessageRecord(dir_bytes, text))

    def _load_pictures(self, dir_path: Path, fat_path: Path, expected: int) -> None:
        capture_signature = True
        with open(dir_path, "rb") as dir_file, open(fat_path, "rb") as fat_file:
            while True:
                dir_bytes = dir_file.read(PICTURE_RECORD_SIZE)
                if len(dir_bytes) == 0:
                    break
                if len(dir_bytes) != PICTURE_RECORD_SIZE:
                    raise ValueError("QSOPCTDIR.DAT is corrupted")
                fat_bytes = fat_file.read(4)
                if len(fat_bytes) != 4:
                    raise ValueError("QSOPCTFAT.DAT is corrupted")
                if fat_bytes[0] != 0x40:
                    continue
                self.pictures.append(PictureRecord(dir_bytes))
                if capture_signature:
                    capture_signature = False
                    seed = dir_bytes[
                        PICTURE_FILENAME_OFFSET : PICTURE_FILENAME_OFFSET + 6
                    ]
                    if len(seed) < 6:
                        seed = seed.ljust(6, b"0")
                    self.signature_seed = bytes(seed)
                    self.signature_tail = self.signature_seed[1:6]

    def save(self) -> None:
        if not self.qso_dir:
            raise RuntimeError("Data set was not loaded")
        self._write_management()
        self._write_messages()
        self._write_pictures()
        self.changed = False

    def _write_management(self) -> None:
        buf = bytearray([0xFF] * MNG_RECORD_SIZE)
        if self.messages:
            _write_u16_be(buf, 0, len(self.messages))
        if self.pictures:
            _write_u16_be(buf, 16, len(self.pictures))
        _write_u16_be(buf, 18, self.picture_counter)
        (self.qso_dir / "QSOMNG.DAT").write_bytes(buf)

    def _write_messages(self) -> None:
        msg_fat_path = self.qso_dir / "QSOMSGFAT.DAT"
        msg_dir_path = self.qso_dir / "QSOMSGDIR.DAT"
        msg_path = self.qso_dir / "QSOMSG.DAT"
        with open(msg_fat_path, "wb") as fat_file, open(
            msg_dir_path, "wb"
        ) as dir_file, open(msg_path, "wb") as msg_file:
            pos1 = 0
            for idx, record in enumerate(self.messages):
                fat_file.write(bytes([0x40, 0x00, (pos1 >> 8) & 0xFF, pos1 & 0xFF]))
                pos1 += 0x80
                _write_u16_be(record.header, 2, idx)
                dir_file.write(record.header)
                pointer = record.message_pointer()
                msg_file.seek(pointer)
                msg_file.write(record.text)

    def _write_pictures(self) -> None:
        pct_fat_path = self.qso_dir / "QSOPCTFAT.DAT"
        pct_dir_path = self.qso_dir / "QSOPCTDIR.DAT"
        with open(pct_fat_path, "wb") as fat_file, open(pct_dir_path, "wb") as dir_file:
            pos1 = 0
            for idx, record in enumerate(self.pictures):
                fat_file.write(bytes([0x40, 0x00, (pos1 >> 8) & 0xFF, pos1 & 0xFF]))
                pos1 += 0x80
                _write_u16_be(record.header, 2, idx * 2)
                dir_file.write(record.header)

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------
    def add_message(self) -> MessageRecord:
        pointer = self.next_message_offset
        self.next_message_offset += TXT_TEXT_SIZE
        record = MessageRecord()
        record.set_default_payload(self.config, pointer, len(self.messages))
        record.set_date(dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self.messages.append(record)
        self.changed = True
        return record

    def remove_message(self, index: int) -> None:
        if 0 <= index < len(self.messages):
            del self.messages[index]
            self.changed = True

    def remove_message_duplicates(self) -> int:
        seen = {}
        removed = 0
        i = 0
        while i < len(self.messages):
            payload = bytes(self.messages[i].text)
            if payload in seen:
                del self.messages[i]
                removed += 1
            else:
                seen[payload] = True
                i += 1
        if removed:
            self.changed = True
        return removed

    # ------------------------------------------------------------------
    # Picture helpers
    # ------------------------------------------------------------------
    def add_picture(self) -> PictureRecord:
        record = PictureRecord()
        record.set_default_payload(self.config, len(self.pictures) * 2, self.signature_tail)
        record.set_date(dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self.pictures.append(record)
        self.changed = True
        return record

    def remove_picture(self, index: int) -> None:
        if 0 <= index < len(self.pictures):
            del self.pictures[index]
            self.changed = True

    def remove_picture_duplicates(self) -> int:
        seen = {}
        removed = 0
        i = 0
        while i < len(self.pictures):
            size = self.pictures[i].get_size()
            if size in seen:
                del self.pictures[i]
                removed += 1
            else:
                seen[size] = True
                i += 1
        if removed:
            self.changed = True
        return removed

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------
    def ensure_photo_dir(self) -> Path:
        if not self.photo_dir:
            raise RuntimeError("Photo directory is unknown")
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        return self.photo_dir

    def allocate_picture_filename(self) -> Path:
        self.ensure_photo_dir()
        prefix = self.signature_seed.decode("ascii", errors="ignore")
        name = f"{prefix}{self.picture_counter:06d}.jpg"
        self.picture_counter += 1
        return self.photo_dir / name

    def mark_changed(self) -> None:
        self.changed = True

    def update_config(self, config: MainConfig) -> None:
        self.config = config.normalized()

    def picture_path(self, record: PictureRecord) -> Optional[Path]:
        if not self.photo_dir:
            return None
        name = record.get_filename()
        if not name:
            return None
        return self.photo_dir / name
