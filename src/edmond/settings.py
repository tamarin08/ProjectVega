"""Independent Edmond preferences. Repeat permission is never persisted."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile

DEFAULT_NOTES = tuple(range(36, 52))


def valid_notes(value):
    return (isinstance(value, (tuple, list)) and len(value) == 16
            and all(type(n) is int and 0 <= n <= 127 for n in value)
            and len(set(value)) == 16)


@dataclass
class Settings:
    notes: tuple[int, ...] = DEFAULT_NOTES
    channel: int = 10
    velocity: int = 100
    bpm: int = 100
    division: int = 16
    midi_port: str = ""
    bank: int = 0
    extra: dict = field(default_factory=dict, repr=False)


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ProjectEdmond" / "settings.json"
        self.status = ""

    def load(self) -> Settings:
        settings = Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Expected a settings object")
        except FileNotFoundError:
            return settings
        except (OSError, ValueError) as exc:
            self.status = f"Preferences could not be loaded: {exc}"
            return settings
        if valid_notes(data.get("notes")):
            settings.notes = tuple(data["notes"])
        for key, low, high in (("channel", 1, 16), ("velocity", 1, 127), ("bpm", 30, 300), ("bank", 0, 1)):
            value = data.get(key)
            if type(value) is int and low <= value <= high:
                setattr(settings, key, value)
        if type(data.get("division")) is int and data["division"] in (8, 16, 32):
            settings.division = data["division"]
        if isinstance(data.get("midi_port"), str):
            settings.midi_port = data["midi_port"]
        settings.extra = {key: value for key, value in data.items() if key not in settings.__dataclass_fields__}
        return settings

    def save(self, settings: Settings) -> bool:
        data = dict(settings.extra)
        data.update({key: value for key, value in vars(settings).items() if key != "extra"})
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix="settings-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, indent=2)
                stream.write("\n")
            os.replace(temporary, self.path)
            self.status = ""
            return True
        except OSError as exc:
            self.status = f"Preferences could not be saved: {exc}"
            return False
        finally:
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
