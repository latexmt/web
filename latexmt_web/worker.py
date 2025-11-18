from io import StringIO
from flask import current_app
from itertools import chain
import logging
import subprocess
import traceback
import os

from latexmt_core.document_processor import DocumentTranslator
from latexmt_core.glossary import load_glossary
from latexmt_core.parsing.to_text import mask_str_default

from . import db
from .configure import ConfigKey
from .dirs import input_base, output_base
from .format import texfmt_cmdline, texfmt_files
from .job import Job
from .translator import get_translator_aligner


def translate_single(input_text: str, src_lang: str, tgt_lang: str, params: Job) -> str:
    config = current_app.config

    job_logger = logging.getLogger("translate_single")
    logger = job_logger.getChild(__name__)

    trans_type = config[ConfigKey.TRANSLATOR]
    align_type = config[ConfigKey.ALIGNER]

    # if deepl_api_token is set, load deepl translator
    if params.deepl_api_token is not None and len(params.deepl_api_token.strip()) > 0:
        trans_type = "api_deepl"
        os.environ["DEEPL_API_TOKEN"] = params.deepl_api_token.strip()

    lock, translator, aligner = get_translator_aligner(
        src_lang,
        tgt_lang,
        trans_type=trans_type,
        align_type=align_type,
        parent_logger=job_logger,
    )

    glossary = load_glossary(lines=params.glossary.splitlines())

    mask_str = mask_str_default
    if params.mask_placeholder is not None and len(params.mask_placeholder.strip()) > 0:
        mask_str = params.mask_placeholder.strip()

    processor = DocumentTranslator(
        translator,
        aligner,
        glossary=glossary,
        parent_logger=logger,
        recurse_input=False,
        mask_str=mask_str,
    )

    processor_in = StringIO(input_text)
    processor_in.name = str(processor_in)
    processor_out = StringIO()
    processor_out.name = str(processor_out)

    logger.info("Start processing input")

    try:
        with lock:
            processor._DocumentTranslator__process_file(  # type: ignore
                processor_in, processor_out
            )
            processor_out.flush()
            processor_out.seek(0)
    except Exception as err:
        logger.warning(f"Error processing input\n{err}\n{traceback.format_exc()}")

    output_text = processor_out.read()
    logger.info("Finished processing input")

    if config[ConfigKey.TEXFMT_BIN] is not None and config[ConfigKey.TEXFMT_BIN] != "":
        texfmt_result = subprocess.run(
            texfmt_cmdline() + ["--stdin"],
            input=output_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        if texfmt_result.returncode != 0:
            logger.warning("Error formatting output")
        else:
            output_text = texfmt_result.stdout.decode("utf-8")
            logger.info("Formatted output")

    return output_text


def job_worker(job_id: int):
    config = current_app.config

    job = db.get_job(job_id)
    assert job is not None

    job_logger = logging.getLogger(f"Job {job.id}")
    logger = job_logger.getChild(__name__)

    logger.info("Starting worker")
    job.status = "initialising"
    job = db.update_job(job_id, job)

    glossary = load_glossary(lines=job.glossary.splitlines(), parent_logger=job_logger)

    input_dir = input_base().joinpath(str(job.id))
    output_dir = output_base().joinpath(str(job.id))

    # job.model contains src_lang, job.input_prefix contains tgt_lang
    lock, translator, aligner = get_translator_aligner(
        job.src_lang, job.tgt_lang, parent_logger=job_logger
    )

    processor = DocumentTranslator(
        translator, aligner, glossary=glossary, parent_logger=job_logger
    )

    logger.info(f"Job {job.id}: Start processing documents")
    job.status = "processing"
    job = db.update_job(job_id, job)

    for input_file in chain(input_dir.rglob("*.tex"), input_dir.rglob("*.Rnw")):
        try:
            with lock:
                processor.process_document(
                    input_file,
                    output_dir.joinpath(input_file.relative_to(input_dir).parent),
                )

        except Exception as err:
            logger.warning(
                f"Error processing input\n{err}\n{traceback.format_exc()}",
                extra={"input_file": input_file},
            )
            job.status = "error"
            job.download_url = f"/api/jobs/{job.id}/download"
            job = db.update_job(job_id, job)
            break

    logger.info("Finished translating input files")

    if config[ConfigKey.TEXFMT_BIN] is not None and config[ConfigKey.TEXFMT_BIN] != "":
        output_files = list(chain(output_dir.rglob("*.tex"), output_dir.rglob("*.Rnw")))
        texfmt_result = texfmt_files(output_files)
        if texfmt_result.returncode != 0:
            logger.warning("Error formatting output files")
        logger.info("Formatted output files")

    if job.status != "error":
        logger.info("Finished")
        job.status = "done"
        job.download_url = f"/api/jobs/{job.id}/download"
        job = db.update_job(job_id, job)

    processor.clear_processed()
    for handler in job_logger.handlers:
        job_logger.removeHandler(handler)
        handler.close()
