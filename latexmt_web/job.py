from dataclasses import dataclass

# type imports
from typing import Optional


@dataclass
class Job:
    id: int
    status: str
    model: str
    input_prefix: str
    src_lang: str
    tgt_lang: str
    download_url: Optional[str]
    deepl_api_token: Optional[str] = None
    glossary: str = ''
    mask_placeholder: Optional[str] = None
