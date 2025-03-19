from flask import current_app
from threading import Lock

from latexmt_core.context_logger import logger_from_kwargs

from .configure import ConfigKey
from latexmt_core.get_translator import get_translator_aligner as get_translator_aligner_base

# type imports
from latexmt_core.alignment import Aligner
from latexmt_core.translation import Translator

__translator_aligners_mutex = Lock()
__translator_aligners: dict[tuple[str, str],
                            tuple[Lock, Translator, Aligner]] = {}


def get_translator_aligner(src_lang: str, tgt_lang: str, **kwargs) -> tuple[Lock, Translator, Aligner]:
    global __translator_aligners
    config = current_app.config

    logger = logger_from_kwargs(**kwargs)

    with __translator_aligners_mutex:
        if (src_lang, tgt_lang) not in __translator_aligners:
            logger.info(f'Initialising translator for {src_lang}-{tgt_lang}...')  # nopep8

            translator, aligner = get_translator_aligner_base(
                src_lang=src_lang, tgt_lang=tgt_lang,
                trans_type=config[ConfigKey.TRANSLATOR],
                align_type=config[ConfigKey.ALIGNER],
                opus_model_base=config[ConfigKey.OPUS_MODEL],
                logger=logger
            )

            __translator_aligners[(src_lang, tgt_lang)] = \
                (Lock(), translator, aligner)

    return __translator_aligners[(src_lang, tgt_lang)]
