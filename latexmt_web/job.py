from dataclasses import dataclass

# type imports
from typing import Optional


@dataclass
class Job:
    id: int
    status: str
    src_lang: str
    tgt_lang: str
    download_url: Optional[str]
    glossary: str = ''
