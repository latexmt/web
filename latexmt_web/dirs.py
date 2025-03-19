from flask import current_app
import logging
from pathlib import Path
import shutil

from .configure import ConfigKey


def basedir(): return Path(current_app.config[ConfigKey.WORK_DIR])
def upload_base(): return basedir().joinpath('upload')
def input_base(): return basedir().joinpath('input')
def output_base(): return basedir().joinpath('output')
def log_base(): return basedir().joinpath('log')


__basepaths = {
    'upload': upload_base,
    'input': input_base,
    'output': output_base,
}


def __clear(job_id: int, name: str):
    logger = logging.getLogger(f'Job {job_id}').getChild(__name__)
    logger.info(f'Clearing {name}')
    _dir = __basepaths[name]().joinpath(str(job_id))
    shutil.rmtree(_dir)


def clear_upload(job_id: int):
    __clear(job_id, 'upload')


def clear_input(job_id: int):
    __clear(job_id, 'input')


def clear_output(job_id: int):
    __clear(job_id, 'output')
