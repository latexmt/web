import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).parent.parent))

# autopep8: off - the stuff at the top needs to STAY at the top
from flask import Flask, render_template, request, send_file
from flask_executor import Executor
from flask_sock import Sock, Server as WS

import subprocess
import time
import json
from io import BytesIO
import logging
import shutil
from zipfile import ZipFile, ZIP_STORED

from latexmt_core.context_logger import ContextLogger
from .configure import ConfigKey, latexmt_configure
from . import db
from .dirs import (
    basedir,
    upload_base,
    input_base,
    output_base,
    log_base,
    clear_upload,
)
from .helpers import ensure_dir
from .job import Job
from .worker import job_worker, translate_single
# autopep8: on


logging.setLoggerClass(ContextLogger)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(levelname)s:%(name)s:%(message)s\tcontext=%(context)s', defaults={'context': {}}))
logging.basicConfig(level=logging.INFO, handlers=[handler])

logger = logging.getLogger(__name__)


app = Flask(__name__,
            static_folder='static',
            template_folder='templates'
            )
app.config['TEMPLATES_AUTO_RELOAD'] = True

app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True
executor = Executor(app)

app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)

# translation parameters
latexmt_configure(app)

with app.app_context():
    for dir_ in (basedir, upload_base, input_base, output_base, log_base):
        ensure_dir(dir_())

logging.getLogger().setLevel(app.config[ConfigKey.LOG_LEVEL])

# templates and their defaults
templates = {
    'index': ('index.html',
              {'languages': ['de', 'en'],
               'src_default': 'de',
               'tgt_default': 'en'}),
    'direct': ('direct.html',
               {'languages': ['de', 'en'],
                'src_default': 'de',
                'tgt_default': 'en'})
}


def render_template_with_defaults(template_name: str, **context):
    template, defaults = templates[template_name]
    return render_template(template, **defaults, **context)


@app.route('/jobs')
def index():
    return render_template_with_defaults('index', jobs=get_jobs())


@app.route('/')
def direct():
    return render_template_with_defaults('direct', jobs=get_jobs())


@app.route('/api/jobs')
def get_jobs():
    return [{'id': id, 'status': job.status, 'download_url': job.download_url}
            for (id, job) in db.get_jobs().items() if job.status != 'archived']


@app.route('/submit', methods=['POST'])
def submit_job():
    document = request.files['document']
    src_lang = request.form['src_lang']
    tgt_lang = request.form['tgt_lang']
    glossary = request.form['glossary']

    job = Job(0,
              status='new',
              src_lang=src_lang,
              tgt_lang=tgt_lang,
              download_url=None,
              glossary=glossary)
    job = db.create_job(job)

    upload_dir = upload_base().joinpath(str(job.id))
    ensure_dir(upload_dir)
    input_dir = input_base().joinpath(str(job.id))
    ensure_dir(input_dir)

    assert document.filename is not None
    upload_path = upload_dir.joinpath(document.filename)
    document.save(upload_path)

    log_file = log_base().joinpath(str(job.id) + '.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.getLogger().handlers[0].formatter)

    job_logger = logging.getLogger(f'Job {job.id}')
    job_logger.addHandler(file_handler)

    if upload_path.name.endswith('.zip'):
        with ZipFile(upload_path, mode='r') as upload_zip:
            upload_zip.extractall(path=input_dir)
    else:
        shutil.copy2(src=str(upload_path), dst=str(input_dir))

    executor.submit(job_worker, job.id)
    logger.info('Submitted', extra={'job': job})

    clear_upload(job.id)

    return render_template_with_defaults('index', jobs=db.get_jobs(), submitted_id=job.id)


@app.route('/status/<job_id>')
def status(job_id: str):
    job = db.get_job(int(job_id))
    if job is None:
        return 'nonexistent', 404

    return job.status


@app.route('/download/<job_id>')
def download(job_id: str):
    job = db.get_job(int(job_id))
    if job is None:
        return 'nonexistent', 404

    output_dir = output_base().joinpath(str(job.id))
    output_files = list(output_dir.rglob('*'))

    if len(output_files) > 1:
        download_file = BytesIO()
        with ZipFile(download_file, mode='w', compression=ZIP_STORED) as zf:
            for output_file in output_files:
                zf.write(output_file, arcname=output_file.relative_to(output_dir))

        download_file.seek(0)
        response = send_file(download_file, download_name=f'{job.id}.zip',
                             mimetype='application/zip', as_attachment=True)

    else:
        with open(output_files[0], mode='rb') as download_bytes:
            download_file = BytesIO(download_bytes.read())
        response = send_file(download_file, download_name=str(output_files[0].name),
                             mimetype='text/x-tex', as_attachment=True)

    job.status = 'archived'
    db.update_job(job.id, job)
    logger.info('Archived', extra={'job': job})

    return response


@app.route('/translate', methods=['POST'])
def single():
    input_text = request.form['input_text']
    src_lang = request.form['src_lang']
    tgt_lang = request.form['tgt_lang']
    glossary = request.form['glossary'] if 'glossary' in request.form else ''

    params = Job(0,
                 status='new',
                 src_lang=src_lang,
                 tgt_lang=tgt_lang,
                 download_url=None,
                 glossary=glossary)
    params = db.create_job(params)

    # log_file = log_base().joinpath(str(params.id) + '.log')
    # file_handler = logging.FileHandler(log_file)
    # file_handler.setFormatter(logging.getLogger().handlers[0].formatter)

    # job_logger = logging.getLogger(f'Job {params.id}')
    # job_logger.addHandler(file_handler)

    return translate_single(input_text, params)


def ws_monitor(ws: WS, job_id: str, reader: subprocess.Popen):
    while ws.connected and ws.pong_received:
        time.sleep(1)

    reader.terminate()
    logger.info(f'Closed log reader for job {job_id}')

    if ws.connected:
        ws.close()


@sock.route('/logs/<job_id>')
def get_logs(ws: WS, job_id: str):
    job = db.get_job(int(job_id))
    if job is None:
        ws.send(json.dumps({'error': f'Job {job_id} does not exist'}))
        return

    log_file = log_base().joinpath(str(job.id) + '.log')
    if not log_file.exists():
        ws.send(json.dumps({'error': f'No log file for job {job_id}'}))
        return

    f: subprocess.Popen | None = None
    try:
        f = subprocess.Popen(
            ['tail', '-f', '-n+1', str(log_file)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f'Opened log reader for job {job_id}')
        assert f.stdout is not None

        executor.submit(ws_monitor, ws, job_id, f)
        for line in f.stdout:
            ws.send(json.dumps({'log_line': line.decode()}))
    except Exception as e:
        ws.send(json.dumps({'error': str(e)}))
        if f is not None and f.returncode is None:
            f.terminate()
