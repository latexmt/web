const job_table_id = 'job-list'

function get_job_table() {
  return document.getElementById(job_table_id).children[0]
}

function clear_job_table() {
  const rows = document.querySelectorAll(`#${job_table_id} tr:not(:first-child)`)
  // const rows = get_job_table().querySelectorAll('tr:not(:first-child))')
  rows.forEach(e => e.remove())
}

/**
 * @returns {Promise<{
 *    id: number
 *    status: string
 *    download_url: string | null
 * }[]>}
 */
async function get_jobs() {
  const response = await fetch('/api/jobs')
  if (!response.ok) {
    console.error('fetching jobs failed')
    return {}
  }

  return response.json()
}

/**
 * @param job { {
 *    id: number
 *    status: string
 *    download_url: string | null
 * } }
 */
function format_job_row(job) {
  return `<td>${job.id}</td>
    <td>
      ${job.status} ${job.download_url ? '(<a href="' + job.download_url + '">download</a>)' : ''}
    </td>
    <td>
      <button data-id="${job.id}" onclick="show_logs(${job.id})">Logs</button>
    </td>`
}

async function update_job_table() {
  const jobs = await get_jobs()

  let existing_jobs = []

  const job_table = get_job_table()
  for (const job of jobs) {
    existing_jobs.push(job.id)

    const row_elem = document.querySelector(`tr[data-id="${job.id}"]`)
    if (!row_elem) {
      job_table.innerHTML += `<tr data-id="${job.id}">${format_job_row(job)}</tr>`
    } else {
      row_elem.innerHTML = format_job_row(job)
    }
  }

  for (const elem of document.querySelectorAll('tr[data-id]')) {
    const job_id = parseInt(elem.attributes['data-id'].value)
    if (!existing_jobs.includes(job_id)) {
      close_logs(job_id)
      elem.remove()
    }
  }
}

/**
 * @param event {SubmitEvent}
 */
async function submit_form(event) {
  event.preventDefault()

  console.log(event.submitter)
  const response = await fetch('/submit', {
    method: 'POST',
    body: new FormData(event.submitter.parentElement)
  })

  await update_job_table()
}

/**
 * @type {Record<number, {socket: WebSocket; elem: HTMLElement}>}
 */
const log_rows = {}

/**
 * @param job_id {number}
 */
function show_logs(job_id) {
  if (job_id in log_rows) {
    close_logs(job_id)
    return
  }

  const socket = new WebSocket(`/logs/${job_id}`)

  button_node = document.querySelector(`button[data-id="${job_id}"]`)
  const elem = document.createElement('tr')
  elem.innerHTML = '<td colspan=3><code></code></td>'
  button_node.parentElement.parentElement.parentElement.insertBefore(elem, button_node.parentElement.parentElement.nextSibling)

  const code_elem = elem.childNodes[0].childNodes[0]

  log_rows[job_id] = { socket, elem: code_elem }

  socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data)
    if ('error' in data) {
      console.error(data.error)
      code_elem.innerHTML += 'Error: ' + data.error
    } else {
      code_elem.innerHTML += data.log_line
    }

    code_elem.scrollTo(0, code_elem.scrollHeight)
  })
}

function close_logs(job_id) {
  if (job_id in log_rows) {
    if (log_rows[job_id].socket.readyState !== WebSocket.CLOSED)
      log_rows[job_id].socket.close()

    log_rows[job_id].elem.parentElement.parentElement.remove()

    delete log_rows[job_id]
  }
}

const update_loop_interval = 3000
function update_loop() {
  update_job_table().finally(() => setTimeout(update_loop, update_loop_interval))
}

/**
 * @param event {DragEvent}
 */
async function handleFileDrop(event) {
  const dropTarget = event.target

  if (event.dataTransfer.files.length > 0) {
    const file = event.dataTransfer.files[0]

    if( 'value' in dropTarget)
      dropTarget.value = await file.text()
    else
      dropTarget.innerHTML = await file.text()
  }
}
