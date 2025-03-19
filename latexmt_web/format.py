from flask import current_app
from pathlib import Path
import subprocess

from .configure import ConfigKey


def texfmt_cmdline() -> list[str]:
    config = current_app.config

    texfmt_bin = config[ConfigKey.TEXFMT_BIN]
    texfmt_conf = config[ConfigKey.TEXFMT_CONF]

    command_line = [texfmt_bin]

    if texfmt_conf is not None and texfmt_conf != '':
        command_line += ['--config', texfmt_conf]

    return command_line


def texfmt_files(files: list[Path]) -> subprocess.CompletedProcess[bytes]:
    command_line = texfmt_cmdline()

    for file in files:
        command_line += [str(file.resolve())]

    return subprocess.run(command_line)
