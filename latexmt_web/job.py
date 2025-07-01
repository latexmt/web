from dataclasses import dataclass

# type imports
from typing import Optional


@dataclass
class Job:
    id: int
    status: str
    model: str
    input_prefix: str
    download_url: Optional[str]
    glossary: str = ''
