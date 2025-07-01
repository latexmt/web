from io import StringIO
from flask import current_app
from itertools import chain
import logging
import subprocess

from latexmt_core.document_processor import DocumentTranslator
from latexmt_core.glossary import load_glossary

from . import db
from .configure import ConfigKey
from .dirs import input_base, output_base
from .format import texfmt_cmdline, texfmt_files
from .job import Job
from .translator import get_translator_aligner


def translate_single(input_text: str, params: Job) -> str:
    config = current_app.config

    job_logger = logging.getLogger('translate_single')
    logger = job_logger.getChild(__name__)

    lock, translator, aligner = get_translator_aligner('FIXME', 'FIXME',
                                                       parent_logger=job_logger,
                                                       opus_model_base=params.model,
                                                       opus_input_prefix=params.input_prefix)

    glossary = load_glossary(lines=params.glossary.splitlines())

    processor = DocumentTranslator(translator, aligner,
                                   glossary=glossary,
                                   parent_logger=logger,
                                   recurse_input=False)

    processor_in = StringIO(input_text)
    processor_in.name = str(processor_in)
    processor_out = StringIO()
    processor_out.name = str(processor_out)

    logger.info('Start processing input')

    try:
        with lock:
            processor._DocumentTranslator__process_file(  # type: ignore
                processor_in, processor_out)
            processor_out.flush()
            processor_out.seek(0)
    except Exception as err:
        logger.warning('Error processing input', extra={'err': err})

    output_text = processor_out.read()
    logger.info('Finished processing input')

    if config[ConfigKey.TEXFMT_BIN] is not None and config[ConfigKey.TEXFMT_BIN] != '':
        texfmt_result = subprocess.run(texfmt_cmdline() + ['--stdin'],
                                       input=output_text.encode('utf-8'),
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)

        if texfmt_result.returncode != 0:
            logger.warning('Error formatting output')

        output_text = texfmt_result.stdout.decode('utf-8')
        logger.info('Formatted output')

    return output_text


def job_worker(job_id: int):
    config = current_app.config

    job = db.get_job(job_id)
    assert job is not None

    job_logger = logging.getLogger(f'Job {job.id}')
    logger = job_logger.getChild(__name__)

    logger.info('Starting worker')
    job.status = 'initialising'
    job = db.update_job(job_id, job)

    glossary = load_glossary(
        lines=job.glossary.splitlines(), parent_logger=job_logger)

    input_dir = input_base().joinpath(str(job.id))
    output_dir = output_base().joinpath(str(job.id))

    lock, translator, aligner = get_translator_aligner('FIXME', 'FIXME',
                                                       parent_logger=job_logger,
                                                       opus_model_base=job.model,
                                                       opus_input_prefix=job.input_prefix)

    processor = DocumentTranslator(translator, aligner,
                                   glossary=glossary,
                                   parent_logger=job_logger)

    logger.info(f'Job {job.id}: Start processing documents')
    job.status = 'processing'
    job = db.update_job(job_id, job)

    for input_file in chain(input_dir.rglob('*.tex'), input_dir.rglob('*.Rnw')):
        try:
            with lock:
                processor.process_document(input_file, output_dir.joinpath(
                    input_file.relative_to(input_dir).parent))

        except Exception as err:
            logger.warning('Error processing file',
                           extra={'err': err, 'input_file': input_file})
            job.status = 'error'
            job.download_url = f'/api/jobs/{job.id}/download'
            job = db.update_job(job_id, job)
            break

    logger.info('Finished translating input files')

    if config[ConfigKey.TEXFMT_BIN] is not None and config[ConfigKey.TEXFMT_BIN] != '':
        output_files = list(chain(output_dir.rglob('*.tex'),
                                  output_dir.rglob('*.Rnw')))
        texfmt_result = texfmt_files(output_files)
        if texfmt_result.returncode != 0:
            logger.warning('Error formatting output files')
        logger.info('Formatted output files')

    if job.status != 'error':
        logger.info('Finished')
        job.status = 'done'
        job.download_url = f'/api/jobs/{job.id}/download'
        job = db.update_job(job_id, job)

    processor.clear_processed()
    for handler in job_logger.handlers:
        job_logger.removeHandler(handler)
        handler.close()
