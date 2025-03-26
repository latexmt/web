import os
from dataclasses import dataclass, fields
from dacite import from_dict
from enum import StrEnum
from flask import Flask
import json

# type imports
from pathlib import Path
from typing import Optional


@dataclass
class LatexMtConfig():
    work_dir: str
    log_level: Optional[str]
    translator: str
    aligner: str
    opus_model: str
    texfmt_bin: Optional[str]
    texfmt_conf: Optional[str]
    enable_jobs: Optional[bool]


class ConfigKey(StrEnum):
    WORK_DIR = 'LATEXMT_WORK_DIR'
    LOG_LEVEL = 'LATEXMT_LOG_LEVEL'
    TRANSLATOR = 'LATEXMT_TRANSLATOR'
    ALIGNER = 'LATEXMT_ALIGNER'
    OPUS_MODEL = 'LATEXMT_OPUS_MODEL'
    TEXFMT_BIN = 'LATEXMT_TEXFMT_BIN'
    TEXFMT_CONF = 'LATEXMT_TEXFMT_CONF'
    ENABLE_JOBS = 'LATEXMT_ENABLE_JOBS'


def get_config_path() -> Path:
    try:
        return Path(os.environ['LATEXMT_CONFIG_PATH'])
    except Exception:
        return Path('config.json')


def latexmt_configure(app: Flask, path: Path = get_config_path()):
    """
    populates `app.config` with LaTeXMT configuration values found in JSON
    file at `path`
    """

    config = from_dict(data_class=LatexMtConfig,
                       data=json.load(open(path, 'r')))

    if config.enable_jobs is None:
        config.enable_jobs = False

    if config.log_level is None:
        config.log_level = 'INFO'

    if config.opus_model.startswith('./') or config.opus_model.startswith('../'):
        config.opus_model = str(Path(config.opus_model).resolve())

    for field in fields(config):
        app.config['LATEXMT_' + field.name.upper()] = \
            getattr(config, field.name)
