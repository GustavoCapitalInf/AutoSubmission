const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const docSelect = document.getElementById("docSelect");
const statusPill = document.getElementById("statusPill");
const dlMd = document.getElementById("dlMd");
const dlHtml = document.getElementById("dlHtml");
const docEl = document.getElementById("doc");
const sourceEl = document.getElementById("source");
const renderedEl = document.getElementById("rendered");
const body = document.body;

// jobId -> {filename, status, page_count}
const jobs = {};

uploadBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  uploadFiles(fileInput.files);
  fileInput.value = "";
});

// Drag-and-drop anywhere on the page.
["dragover", "dragenter"].forEach((ev) =>
  window.addEventListener(ev, (e) => { e.preventDefault(); body.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  window.addEventListener(ev, (e) => {
    e.preventDefault();
    if (ev === "drop" && e.dataTransfer) uploadFiles(e.dataTransfer.files);
    if (e.relatedTarget === null || ev === "drop") body.classList.remove("drag");
  })
);

docSelect.addEventListener("change", () => selectDoc(docSelect.value));

function uploadFiles(fileList) {
  if (!fileList || !fileList.length) return;
  const form = new FormData();
  for (const f of fileList) form.append("files", f);
  fetch("/upload", { method: "POST", body: form })
    .then((r) => r.json())
    .then((data) => {
      let firstNew = null;
      for (const job of data.jobs) {
        jobs[job.id] = { filename: job.filename, status: "queued", page_count: job.page_count };
        addOption(job.id, job.filename);
        pollJob(job.id);
        if (firstNew === null) firstNew = job.id;
      }
      if (firstNew && !docSelect.value) { docSelect.value = firstNew; selectDoc(firstNew); }
    });
}

function addOption(jobId, filename) {
  // Remove the "No documents" placeholder option.
  const ph = docSelect.querySelector('option[value=""]');
  if (ph) ph.remove();
  const opt = document.createElement("option");
  opt.value = jobId;
  opt.textContent = `${filename}  (queued)`;
  docSelect.appendChild(opt);
}

function pollJob(jobId) {
  const interval = setInterval(() => {
    fetch(`/status/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        jobs[jobId].status = data.status;
        jobs[jobId].error = data.error;
        if (data.page_count) jobs[jobId].page_count = data.page_count;
        const opt = docSelect.querySelector(`option[value="${jobId}"]`);
        if (opt) opt.textContent = `${jobs[jobId].filename}  (${data.status})`;
        if (docSelect.value === jobId) refreshStatusUI(jobId);
        if (data.status === "done" || data.status === "error") clearInterval(interval);
      });
  }, 2000);
}

function refreshStatusUI(jobId) {
  const job = jobs[jobId];
  if (!job) return;
  statusPill.textContent = job.status;
  statusPill.className = `pill ${job.status}`;
  const done = job.status === "done";
  dlMd.disabled = !done;
  dlHtml.disabled = !done;
  dlMd.onclick = done ? () => (window.location = `/download/${jobId}/md`) : null;
  dlHtml.onclick = done ? () => (window.location = `/download/${jobId}/html`) : null;
}

function selectDoc(jobId) {
  if (!jobId || !jobs[jobId]) return;
  refreshStatusUI(jobId);
  const job = jobs[jobId];

  // Left: page images.
  docEl.innerHTML = "";
  if (job.page_count > 0) {
    for (let n = 0; n < job.page_count; n++) {
      const img = document.createElement("img");
      img.src = `/page/${jobId}/${n}`;
      img.alt = `Page ${n + 1}`;
      docEl.appendChild(img);
    }
  } else {
    docEl.innerHTML = '<div class="placeholder">No pages.</div>';
  }

  if (job.status === "done") {
    fetch(`/markdown/${jobId}`)
      .then((r) => r.text())
      .then((md) => { sourceEl.textContent = md; });
    renderedEl.src = `/result/${jobId}`;
  } else if (job.status === "error") {
    sourceEl.textContent = "Error: " + (job.error || "unknown");
    renderedEl.removeAttribute("src");
  } else {
    sourceEl.textContent = "Processing…";
    renderedEl.removeAttribute("src");
  }
}
