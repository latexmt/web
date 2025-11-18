const jobTableId = 'job-list'

function getJobTable() {
  return document.querySelector(`#${jobTableId} > tbody`)
}

// Initialize draggable vertical divider for resizable panels
function initResizer() {
  const container = document.querySelector('.resizable-container')
  if (!container) return

  const divider = container.querySelector('.divider')
  const left = container.querySelector('.resizable-panel.left')
  const right = container.querySelector('.resizable-panel.right')
  if (!divider || !left || !right) return

  let dragging = false

  const clamp = (v, a, b) => Math.min(b, Math.max(a, v))

  function startDrag(e) {
    e.preventDefault()
    dragging = true
    document.body.classList.add('resizing')
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', stopDrag)
  }

  function onDrag(e) {
    if (!dragging) return
    const rect = container.getBoundingClientRect()
    const x = e.clientX - rect.left
    const pct = clamp((x / rect.width) * 95, 5, 95)
    left.style.flex = `0 0 ${pct}%`
    right.style.flex = `0 0 ${100 - pct}%`
  }

  function stopDrag() {
    dragging = false
    document.body.classList.remove('resizing')
    window.removeEventListener('mousemove', onDrag)
    window.removeEventListener('mouseup', stopDrag)
  }

  // keyboard support
  divider.addEventListener('keydown', (e) => {
    const rect = container.getBoundingClientRect()
    const leftWidth = left.getBoundingClientRect().width
    let pct = (leftWidth / rect.width) * 100
    if (e.key === 'ArrowLeft') pct = clamp(pct - 2, 5, 95)
    if (e.key === 'ArrowRight') pct = clamp(pct + 2, 5, 95)
    left.style.flex = `0 0 ${pct}%`
    right.style.flex = `0 0 ${100 - pct}%`
  })

  divider.addEventListener('mousedown', startDrag)
  divider.addEventListener('dblclick', () => {
    left.style.flex = '0 0 50%'
    right.style.flex = '0 0 50%'
  })
}

document.addEventListener('DOMContentLoaded', () => {
  try { initResizer() } catch (e) { console.debug('initResizer failed', e) }
})

// Enable inserting a tab character when pressing Tab inside contenteditable code blocks
function enableTabInCode() {
  const selector = 'pre.filedrop-target code[contenteditable], code[contenteditable]'

  function attach(elem) {
    if (elem.__tab_handler_attached) return
    const handler = function (e) {
      if (e.key !== 'Tab') return
      e.preventDefault()
      const sel = window.getSelection()
      if (!sel || sel.rangeCount === 0) return
      const range = sel.getRangeAt(0)
      // insert tab character
      const tabNode = document.createTextNode('\t')
      range.deleteContents()
      range.insertNode(tabNode)
      // place caret after the inserted node
      range.setStartAfter(tabNode)
      range.collapse(true)
      sel.removeAllRanges()
      sel.addRange(range)
    }
    elem.addEventListener('keydown', handler)
    elem.__tab_handler_attached = true
  }

  // attach to existing nodes
  document.querySelectorAll(selector).forEach(attach)

  // observe DOM for future code elements
  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (!(node instanceof HTMLElement)) continue
        if (node.matches && node.matches(selector)) attach(node)
        node.querySelectorAll && node.querySelectorAll(selector).forEach(attach)
      }
    }
  })
  mo.observe(document.body, { childList: true, subtree: true })
}

document.addEventListener('DOMContentLoaded', () => {
  try { enableTabInCode() } catch (e) { console.debug('enableTabInCode failed', e) }
})

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
 * @param {FormData} formData
 * @param {Record<string, string>} validateSet
 * @returns {{ valid: string[], invalid: string[] }}
 */
function validateParams(formData, validateSet) {
  let valid = []
  let invalid = []

  for (key in validateSet) {
    const expected = validateSet[key]
    const actual = formData.has(key) ? formData.get(key) : ''

    if (actual.length > 0 && !actual.includes(expected)) {
      invalid.push(key)
    } else {
      valid.push(key)
    }
  }

  return { valid, invalid }
}

/**
 * @param {SubmitEvent} event
 */
async function translateText(event) {
  event.preventDefault()

  /**
   * @type {HTMLFormElement}
   */
  const form = event.submitter.form
  const formData = new FormData(form)

  // get content of code elements
  for (const elem of form.querySelectorAll('code[name]')) {
    formData.set(elem.getAttribute('name'), elem.innerText)
  }

  // TODO: proper form validation
  const validateSet = { 'mask_placeholder': '%INDEX%' }
  const { valid, invalid } = validateParams(formData, validateSet)
  for (const id of invalid) {
    document.querySelector(`[data-sync-id="${id}"]`).classList.add('is-invalid')
  }
  for (const id of valid) {
    document.querySelector(`[data-sync-id="${id}"]`).classList.remove('is-invalid')
  }
  if (invalid.length > 0) {
    return
  }

  setFormState('disabled', event.submitter.form.id)
  document.querySelector('#output_text').innerHTML = ''
  const result = await fetch('/api/translate', {
    method: 'POST',
    body: formData,
  }).finally(() => setFormState('enabled', event.submitter.form.id))

  document.querySelector('#output_text').innerHTML = await result.text()
  // If Prism is available, re-run highlighting on the updated code element
  try {
    const outElem = document.querySelector('#output_text')
    if (window.Prism && outElem) {
      Prism.highlightElement(outElem)
    }
  } catch (err) {
    // non-fatal: highlighting is optional
    console.debug('Prism highlight error:', err)
  }

  // also re-render input text
  try {
    const inElem = document.querySelector('#input_text')
    if (window.Prism && inElem) {
      Prism.highlightElement(inElem)
    }
  } catch (err) {
    // non-fatal: highlighting is optional
    console.debug('Prism highlight error:', err)
  }
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
