import sqlite3
from copy import deepcopy

from .dirs import basedir
from .job import Job

# type imports
from typing import Optional


def db_filename(): return basedir().joinpath('latexmt.sqlite3')


def __connect() -> sqlite3.Connection:
    sql = '''
        create table if not exists jobs(
            id integer primary key not null,
            status text not null,
            src_lang text not null,
            tgt_lang text not null,
            download_url text,
            glossary text)
    '''

    con = sqlite3.connect(db_filename())
    con.cursor().execute(sql)

    return con


def get_jobs() -> dict[int, Job]:
    sql = 'select id, status, src_lang, tgt_lang, download_url, glossary from jobs'

    con = __connect()
    cur = con.cursor()

    jobs = dict[int, Job]()
    for job_id, status, src_lang, tgt_lang, download_url, glossary in cur.execute(sql):
        jobs[job_id] = Job(job_id, status, src_lang, tgt_lang,
                           download_url, glossary)

    con.close()
    return jobs


def get_job(job_id) -> Optional[Job]:
    sql = 'select id, status, src_lang, tgt_lang, download_url, glossary from jobs where id = ?'

    con = __connect()
    cur = con.cursor()
    res = cur.execute(sql, (job_id,))

    row = res.fetchone()
    if row is None:
        con.close()
        return None

    job_id, status, src_lang, tgt_lang, download_url, glossary = row

    con.close()
    return Job(job_id, status, src_lang, tgt_lang, download_url, glossary)


def create_job(job: Job) -> Job:
    '''
    returns the `job` object with the updated ID
    '''

    sql = '''
        insert into jobs (status, src_lang, tgt_lang, download_url, glossary)
            values (?, ?, ?, ?, ?)
    '''

    con = __connect()
    cur = con.cursor()
    cur.execute(sql, (job.status, job.src_lang, job.tgt_lang,
                      job.download_url, job.glossary))
    con.commit()

    job = deepcopy(job)
    assert cur.lastrowid is not None
    job.id = cur.lastrowid

    con.close()
    return job


def update_job(job_id: int, job: Job) -> Job:
    '''
    returns the updated job object (should be the same as the input)
    '''

    sql = '''
        update jobs
            set status = ?,
                src_lang = ?,
                tgt_lang = ?,
                download_url = ?,
                glossary = ?
            where id = ?
    '''

    con = __connect()
    cur = con.cursor()
    cur.execute(sql, (job.status, job.src_lang, job.tgt_lang,
                      job.download_url, job.glossary, job_id))
    con.commit()

    con.close()
    upd_job = get_job(job_id)
    assert upd_job is not None
    return upd_job


def delete_job(job_id: int) -> int:
    '''
    returns 1 if a job was deleted, 0 otherwise 
    '''

    sql = '''
        delete from jobs where id = ?
    '''

    con = __connect()
    cur = con.cursor()
    cur.execute(sql, (job_id,))
    rowcount = cur.rowcount
    con.commit()

    con.close()
    return rowcount
