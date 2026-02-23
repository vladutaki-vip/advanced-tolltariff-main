import os
import platform
from pathlib import Path
from typing import Optional

class Settings:
    database_url: str
    base_url: Optional[str]
    data_dir: Path

    def __init__(self) -> None:
        # Determine data directory (overrideable via env)
        data_dir_env = os.getenv("TOLLTARIFF_DATA_DIR")
        if data_dir_env:
            self.data_dir = Path(data_dir_env)
        else:
            if platform.system() == "Windows":
                localapp = os.getenv("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
                self.data_dir = Path(localapp) / "AdvancedTolltariff"
            else:
                # Default relative to cwd
                self.data_dir = Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Default DB path under data_dir if not provided
        default_sqlite = f"sqlite:///{(self.data_dir / 'data.db').as_posix()}"
        self.database_url = os.getenv("DATABASE_URL", default_sqlite)
        self.base_url = os.getenv("TOLLTARIFF_BASE_URL")

settings = Settings()
