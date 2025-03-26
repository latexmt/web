const jobTableId = 'job-list'

function getJobTable() {
  return document.querySelector(`#${jobTableId} > tbody`)
}

function clearJobTable() {
  for (const e of getJobTable().children) {
    e.remove()
  }
}

/**
 * @returns {Promise<{
 *    id: number
 *    status: string
 *    download_url: string | null
 * }[]>}
 */
async function getJobs() {
  const response = await fetch('/api/jobs')
  if (!response.ok) {
    console.error('fetching jobs failed')
    return {}
  }

  return response.json()
}

/**
 * @param { {
 *    id: number
 *    status: string
 *    download_url: string | null
 * } } job
 */
function formatJobRow(job) {
  return `<tr data-id="${job.id}">
      <td scope="row" class="align-middle">${job.id}</td>
      <td scope="row" class="align-middle">
        ${job.status}
        ${
          job.download_url
            ? '(<a href="' + job.download_url + '">download</a>)'
            : ''
        }
      </td>
      <td scope="row" class="align-middle">
        <button
          data-id="${job.id}"
          type="button"
          class="btn btn-link"
          onclick="showLogs(${job.id})"
        >
          Logs
        </button>
      </td>
    </tr>`
}

async function updateJobTable() {
  const jobs = await getJobs()

  let existingJobs = []

  const jobTable = getJobTable()
  for (const job of jobs) {
    existingJobs.push(job.id)

    const rowElem = jobTable.querySelector(`tr[data-id="${job.id}"]`)
    if (!rowElem) {
      jobTable.innerHTML += formatJobRow(job)
    } else {
      rowElem.outerHTML = formatJobRow(job)
    }
  }

  for (const elem of document.querySelectorAll('tr[data-id]')) {
    const jobId = parseInt(elem.attributes['data-id'].value)
    if (!existingJobs.includes(jobId)) {
      closeLogs(jobId)
      elem.remove()
    }
  }
}

/**
 * @type {Record<number, {socket: WebSocket; elem: HTMLElement}>}
 */
const logRows = {}

/**
 * @param {number} jobId
 */
function showLogs(jobId) {
  if (jobId in logRows) {
    closeLogs(jobId)
    return
  }

  const socket = new WebSocket(`/api/jobs/${jobId}/log`)

  button_node = document.querySelector(`button[data-id="${jobId}"]`)
  const elem = document.createElement('tr')
  elem.innerHTML =
    '<td class="table-active" colspan=3><code class="job-log"></code></td>'
  button_node.parentElement.parentElement.parentElement.insertBefore(
    elem,
    button_node.parentElement.parentElement.nextSibling
  )

  const code_elem = elem.childNodes[0].childNodes[0]

  logRows[jobId] = { socket, elem: code_elem }

  socket.addEventListener('message', event => {
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

function closeLogs(jobId) {
  if (jobId in logRows) {
    if (logRows[jobId].socket.readyState !== WebSocket.CLOSED)
      logRows[jobId].socket.close()

    logRows[jobId].elem.parentElement.parentElement.remove()

    delete logRows[jobId]
  }
}

/**
 * @param {DragEvent} event
 */
async function handleFileDrop(event) {
  const dropTarget = event.target

  if (event.dataTransfer.files.length > 0) {
    const file = event.dataTransfer.files[0]

    if ('value' in dropTarget) dropTarget.value = await file.text()
    else dropTarget.innerHTML = await file.text()
  }
}

/**
 * @param {string} query
 */
function addFileDrop(query) {
  document.querySelectorAll(query).forEach(elem => {
    elem.addEventListener('dragover', e => e.preventDefault())
    elem.addEventListener('drop', handleFileDrop)
  })
}

/**
 * @param {SubmitEvent} event
 */
async function translateText(event) {
  event.preventDefault()

  const formData = new FormData(event.submitter.form)
  setFormState('disabled', event.submitter.form.id)
  document.querySelector('#output_text').innerHTML = ''
  const result = await fetch('/api/translate', {
    method: 'POST',
    body: formData,
  }).finally(() => setFormState('enabled', event.submitter.form.id))

  document.querySelector('#output_text').innerHTML = await result.text()
}

/**
 * @param {SubmitEvent} event
 */
async function translateDocument(event) {
  event.preventDefault()

  const formData = new FormData(event.submitter.form)
  const response = await fetch('/api/jobs', {
    method: 'POST',
    body: formData,
  })

  await updateJobTable()
}

/**
 * @param {('enabled' | 'disabled')} state
 * @param {string} formName
 */
function setFormState(state, formName) {
  for (const elem of document.forms.namedItem(formName)) {
    if (state === 'enabled') {
      elem.removeAttribute('disabled')
    } else {
      elem.setAttribute('disabled', true)
    }
  }
}

/**
 * @param {Event} event
 */
function syncValue(event) {
  /**
   * @type {string}
   */
  const syncId = event.target.attributes['data-sync-id'].value
  const syncValue = event.target.value

  document
    .querySelectorAll(`[data-sync-id='${syncId}']`)
    .forEach(elem => elem !== event.target && (elem.value = syncValue))
}

/**
 * @param {string} query
 */
function addValueSync(query) {
  const syncObserver = new MutationObserver((mutationList, observer) => {
    for (const mutation of mutationList) {
      if (mutation.type === 'childList') {
        syncValue(mutation.target)
      }
    }
  })
  document.querySelectorAll(query).forEach(elem => {
    // watch .value
    elem.addEventListener('change', syncValue)
    // watch .innerHTML
    syncObserver.observe(elem, {
      characterData: true,
      subtree: true,
    })
  })
}
