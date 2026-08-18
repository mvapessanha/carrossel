const ICONS = {
  x: '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
  download:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
  edit: '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>',
  check:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
  alert:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
  clock:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
};

const preferredProviderSelect = document.getElementById('preferred_provider');
const modeRadios = document.querySelectorAll('input[name="mode"]');
const modeLabelSingle = document.getElementById('mode-label-single');
const modeLabelCarousel = document.getElementById('mode-label-carousel');
const numImagesWrap = document.getElementById('num_images_wrap');
const contentFilesInput = document.getElementById('content_files');
const designRefsInput = document.getElementById('design_refs');
const contentFilesPreview = document.getElementById('content_files_preview');
const designRefsPreview = document.getElementById('design_refs_preview');
const form = document.getElementById('create-form');
const submitBtn = document.getElementById('submit-btn');
const modal = document.getElementById('confirm-modal');
const modalEditBtn = document.getElementById('modal-edit-btn');
const modalConfirmBtn = document.getElementById('modal-confirm-btn');
const resultsSection = document.getElementById('results');
const resultsStatus = document.getElementById('results-status');
const resultsGallery = document.getElementById('results-gallery');
const downloadZipBtn = document.getElementById('download-zip-btn');
const cancelJobBtn = document.getElementById('cancel-job-btn');
const clearFormBtn = document.getElementById('clear-form-btn');
const editAllBox = document.getElementById('edit-all-box');
const editAllInstruction = document.getElementById('edit-all-instruction');
const editAllBtn = document.getElementById('edit-all-btn');
const quotaBar = document.getElementById('quota-bar');
const reusedRefsNote = document.getElementById('reused-refs-note');
const reuseContainer = document.getElementById('reuse_reference_ids_container');

let reusedRefs = []; // referencias de um job anterior sendo reaproveitadas ao "repetir chamada"
let currentJobId = null;

function updateModeUI() {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  numImagesWrap.classList.toggle('hidden', mode !== 'carousel');
  modeLabelSingle.classList.toggle('active', mode === 'single');
  modeLabelCarousel.classList.toggle('active', mode === 'carousel');
}
modeRadios.forEach((r) => r.addEventListener('change', updateModeUI));
updateModeUI();

function removeFileAt(input, idx) {
  const dt = new DataTransfer();
  Array.from(input.files).forEach((f, i) => {
    if (i !== idx) dt.items.add(f);
  });
  input.files = dt.files;
}

function renderFilePreview(input, container) {
  container.innerHTML = '';
  Array.from(input.files || []).forEach((file, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'thumb-wrap';

    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.className = 'thumb';
      img.src = URL.createObjectURL(file);
      wrap.appendChild(img);
    } else {
      const chip = document.createElement('span');
      chip.className = 'file-chip';
      chip.textContent = file.name;
      wrap.appendChild(chip);
    }

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'remove-x';
    removeBtn.innerHTML = ICONS.x;
    removeBtn.addEventListener('click', () => {
      removeFileAt(input, idx);
      renderFilePreview(input, container);
    });
    wrap.appendChild(removeBtn);

    container.appendChild(wrap);
  });
}
contentFilesInput.addEventListener('change', () => renderFilePreview(contentFilesInput, contentFilesPreview));
designRefsInput.addEventListener('change', () => renderFilePreview(designRefsInput, designRefsPreview));

function renderReusedRefs() {
  reuseContainer.innerHTML = '';
  if (reusedRefs.length === 0) {
    reusedRefsNote.classList.add('hidden');
    return;
  }
  reusedRefsNote.classList.remove('hidden');
  reusedRefsNote.textContent = 'Reaproveitando referências da chamada anterior (clique no x pra remover):';

  const wrap = document.createElement('div');
  wrap.className = 'file-preview';
  reusedRefs.forEach((ref) => {
    const box = document.createElement('div');
    box.className = 'thumb-wrap';

    const img = document.createElement('img');
    img.className = 'thumb';
    img.src = ref.url;
    box.appendChild(img);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'remove-x';
    removeBtn.innerHTML = ICONS.x;
    removeBtn.addEventListener('click', () => {
      reusedRefs = reusedRefs.filter((r) => r.id !== ref.id);
      renderReusedRefs();
    });
    box.appendChild(removeBtn);
    wrap.appendChild(box);

    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'reuse_reference_ids';
    hidden.value = ref.id;
    reuseContainer.appendChild(hidden);
  });
  reuseContainer.appendChild(wrap);
}

let pendingPreferredProvider = null;

function trySetPreferredProvider(value) {
  const exists = [...preferredProviderSelect.options].some((o) => o.value === value);
  if (exists) preferredProviderSelect.value = value;
  return exists;
}

async function prefillFromRepeat(jobId) {
  const resp = await fetch(`/jobs/${jobId}`);
  if (!resp.ok) return;
  const job = await resp.json();
  document.getElementById('content_text').value = job.content_text || '';
  document.getElementById('design_text').value = job.design_text || '';
  document.querySelector(`input[name="mode"][value="${job.mode}"]`).checked = true;
  document.getElementById('num_images').value = job.num_images;
  updateModeUI();
  pendingPreferredProvider = job.preferred_provider || '';
  if (trySetPreferredProvider(pendingPreferredProvider)) pendingPreferredProvider = null;
  reusedRefs = job.references || [];
  renderReusedRefs();
}

const params = new URLSearchParams(window.location.search);
const repeatJobId = params.get('repeat_job_id');
if (repeatJobId) prefillFromRepeat(repeatJobId);

form.addEventListener('submit', (e) => {
  e.preventDefault();
  modal.classList.remove('hidden');
});

modalEditBtn.addEventListener('click', () => modal.classList.add('hidden'));

modalConfirmBtn.addEventListener('click', async () => {
  modal.classList.add('hidden');
  await submitJob();
});

clearFormBtn.addEventListener('click', () => {
  form.reset(); // limpa textareas, radios (volta pra "Imagem unica"), numero de imagens e o select de IA
  contentFilesPreview.innerHTML = '';
  designRefsPreview.innerHTML = '';
  reusedRefs = [];
  renderReusedRefs();
  updateModeUI();
  resultsSection.classList.add('hidden');
  resultsGallery.innerHTML = '';
  resultsStatus.textContent = '';
  history.replaceState(null, '', window.location.pathname); // tira ?repeat_job_id= da URL
});

const POLL_INTERVAL_MS = 4000;

async function submitJob() {
  const formData = new FormData(form);
  let resp, data;
  try {
    resp = await fetch('/jobs', { method: 'POST', body: formData });
    data = await resp.json();
  } catch (err) {
    resultsSection.classList.remove('hidden');
    resultsStatus.textContent = 'Erro de rede: ' + err.message;
    return;
  }
  if (!resp.ok) {
    resultsSection.classList.remove('hidden');
    resultsStatus.textContent = 'Erro: ' + (data.detail || 'falha desconhecida');
    return;
  }
  await trackJob(data.id);
}

async function trackJob(jobId) {
  currentJobId = jobId;
  const originalBtnHtml = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Gerando...';
  cancelJobBtn.classList.remove('hidden');
  cancelJobBtn.disabled = false;
  cancelJobBtn.onclick = () => cancelJob(jobId);
  editAllBox.classList.add('hidden');

  resultsSection.classList.remove('hidden');
  downloadZipBtn.classList.add('hidden');
  resultsSection.scrollIntoView({ behavior: 'smooth' });

  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const resp = await fetch(`/jobs/${jobId}`);
      if (!resp.ok) break;
      const job = await resp.json();
      renderJobResult(job);
      if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') break;
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
  } finally {
    loadQuota();
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnHtml;
    cancelJobBtn.classList.add('hidden');
  }
}

async function cancelJob(jobId) {
  cancelJobBtn.disabled = true;
  cancelJobBtn.innerHTML = '<span class="spinner"></span> Cancelando...';
  try {
    await fetch(`/jobs/${jobId}/cancel`, { method: 'POST' });
  } catch (err) {
    // o proximo poll do trackJob vai refletir o estado real de qualquer forma
  }
}

async function resumeActiveJobIfAny() {
  try {
    const resp = await fetch('/jobs');
    const jobs = await resp.json();
    const active = jobs.find((j) => j.status === 'pending' || j.status === 'running');
    if (active) trackJob(active.id);
  } catch (err) {
    // silencioso -- so' uma tentativa de retomar, nao e' critico
  }
}
resumeActiveJobIfAny();

function renderJobResult(job) {
  const doneCount = job.slides.filter((s) => s.status === 'done').length;
  const totalExpected = job.num_images;

  if (job.status === 'pending' || job.status === 'running') {
    const startedCount = job.slides.length;
    resultsStatus.innerHTML = `<span class="spinner spinner-accent"></span> Gerando... ${startedCount} de ${totalExpected} imagens processadas. Pode navegar pra outra tela, continua rodando.`;
  } else if (job.status === 'done') {
    resultsStatus.textContent = `Pronto! ${doneCount} de ${job.slides.length} imagens geradas.`;
  } else if (job.status === 'cancelled') {
    resultsStatus.textContent = `Cancelado. ${doneCount} de ${job.slides.length} imagens tinham sido geradas ate a hora do cancelamento.`;
  } else {
    resultsStatus.textContent = `Falhou: ${job.error_message || ''}`;
  }

  resultsGallery.innerHTML = '';
  job.slides.forEach((slide) => resultsGallery.appendChild(renderSlideCard(slide)));

  const finished = job.status === 'done' || job.status === 'error' || job.status === 'cancelled';

  if (job.mode === 'carousel' && doneCount > 0 && finished) {
    downloadZipBtn.classList.remove('hidden');
    downloadZipBtn.onclick = () => {
      window.location.href = `/jobs/${job.id}/download.zip`;
    };
  }

  editAllBox.classList.toggle('hidden', !(doneCount > 0 && finished));
}

async function submitEditAll() {
  const instruction = editAllInstruction.value.trim();
  if (!instruction || !currentJobId) return;

  const originalHtml = editAllBtn.innerHTML;
  editAllBtn.disabled = true;
  editAllBtn.innerHTML = '<span class="spinner"></span> Aplicando...';

  try {
    const fd = new FormData();
    fd.append('instruction', instruction);
    const resp = await fetch(`/jobs/${currentJobId}/edit-all`, { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) {
      alert('Erro: ' + (data.detail || 'falha desconhecida'));
      return;
    }
    editAllInstruction.value = '';
    await trackJob(currentJobId);
  } catch (err) {
    alert('Erro de rede: ' + err.message);
  } finally {
    editAllBtn.disabled = false;
    editAllBtn.innerHTML = originalHtml;
  }
}
editAllBtn.addEventListener('click', submitEditAll);

function renderSlideCard(slide) {
  const card = document.createElement('div');
  card.className = 'slide-card' + (slide.status === 'error' ? ' error' : '');

  if (slide.image_url) {
    const img = document.createElement('img');
    img.src = slide.image_url;
    card.appendChild(img);
  }

  const body = document.createElement('div');
  body.className = 'slide-body';

  const statusIcon = slide.status === 'done' ? ICONS.check : slide.status === 'error' ? ICONS.alert : ICONS.clock;
  const meta = document.createElement('div');
  meta.className = 'slide-meta';
  meta.innerHTML = `${statusIcon} Slide ${slide.idx}${slide.role ? ' · ' + slide.role : ''}${slide.provider_used ? ' · ' + slide.provider_used : ''}`;
  body.appendChild(meta);

  if (slide.status === 'error') {
    const err = document.createElement('div');
    err.className = 'error-msg';
    err.textContent = slide.error_message || 'Falha ao gerar esta imagem.';
    body.appendChild(err);
  }

  if (slide.image_url) {
    const actions = document.createElement('div');
    actions.className = 'slide-actions';

    const downloadLink = document.createElement('a');
    downloadLink.href = slide.image_url;
    downloadLink.download = `slide_${slide.idx}.png`;
    downloadLink.innerHTML = ICONS.download + ' Baixar';
    downloadLink.className = 'secondary';
    actions.appendChild(downloadLink);

    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'secondary';
    editBtn.innerHTML = ICONS.edit + ' Editar';
    actions.appendChild(editBtn);

    body.appendChild(actions);

    const editBox = document.createElement('div');
    editBox.className = 'edit-box hidden';
    const editInput = document.createElement('input');
    editInput.type = 'text';
    editInput.placeholder = 'O que mudar nesta imagem?';
    const editSubmit = document.createElement('button');
    editSubmit.type = 'button';
    editSubmit.className = 'primary';
    editSubmit.textContent = 'OK';
    editBox.appendChild(editInput);
    editBox.appendChild(editSubmit);
    body.appendChild(editBox);

    editBtn.addEventListener('click', () => editBox.classList.toggle('hidden'));

    editSubmit.addEventListener('click', async () => {
      if (!editInput.value.trim()) return;
      editSubmit.disabled = true;
      editSubmit.textContent = '...';
      try {
        const fd = new FormData();
        fd.append('instruction', editInput.value.trim());
        const resp = await fetch(`/slides/${slide.id}/edit`, { method: 'POST', body: fd });
        const data = await resp.json();
        if (!resp.ok) {
          alert('Erro ao editar: ' + (data.detail || 'falha desconhecida'));
          return;
        }
        card.querySelector('img').src = data.image_url + '?t=' + Date.now();
        meta.innerHTML = `${ICONS.check} Slide ${slide.idx}${slide.role ? ' · ' + slide.role : ''} · ${data.provider_used}`;
        editBox.classList.add('hidden');
        editInput.value = '';
      } catch (err) {
        alert('Erro de rede: ' + err.message);
      } finally {
        editSubmit.disabled = false;
        editSubmit.textContent = 'OK';
        loadQuota();
      }
    });
  }

  card.appendChild(body);
  return card;
}

function populateProviderSelect(providers) {
  const current = preferredProviderSelect.value;
  const options = providers
    .map((q) => {
      const label = q.configured ? q.label : `${q.label} (sem chave)`;
      const disabled = q.configured ? '' : 'disabled';
      return `<option value="${q.provider_id}" ${disabled}>${label}</option>`;
    })
    .join('');
  preferredProviderSelect.innerHTML = `<option value="">Automático (melhor disponível)</option>${options}`;

  const target = pendingPreferredProvider !== null ? pendingPreferredProvider : current;
  if (trySetPreferredProvider(target)) pendingPreferredProvider = null;
}

async function loadQuota() {
  try {
    const resp = await fetch('/quota');
    const items = await resp.json();
    const cards = items
      .map((q) => {
        if (q.is_paid) {
          const pct = q.configured ? Math.min(Math.round((q.spent_usd / q.budget_usd) * 100), 100) : 0;
          const value = q.configured
            ? `US$${q.remaining_usd.toFixed(2)}<span style="font-size:0.7rem;color:var(--text-faint);font-weight:600;"> restantes</span>`
            : '—';
          const barColor = pct >= 90 ? 'var(--danger)' : 'var(--accent)';
          return `
            <div class="stat-card">
              <div class="stat-label">${q.label} 💳</div>
              <div class="stat-value ${q.configured ? '' : 'muted'}">${value}</div>
              ${q.configured ? `<div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>` : ''}
              <div class="stat-kind">${q.configured ? `US$${q.spent_usd.toFixed(2)} gastos de US$${q.budget_usd.toFixed(2)} · US$${q.cost_per_image_usd.toFixed(3)}/imagem` : 'sem chave configurada'}</div>
            </div>`;
        }
        const pct = q.configured && q.limit > 0 ? Math.round((q.used / q.limit) * 100) : 0;
        const value = q.configured ? `${q.remaining}<span style="font-size:0.7rem;color:var(--text-faint);font-weight:600;">/${q.limit}</span>` : '—';
        const kindNote = q.configured ? (q.kind === 'soft' ? 'estimativa própria' : 'limite oficial') : 'sem chave configurada';
        return `
          <div class="stat-card">
            <div class="stat-label">${q.label}</div>
            <div class="stat-value ${q.configured ? '' : 'muted'}">${value}</div>
            ${q.configured ? `<div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%"></div></div>` : ''}
            <div class="stat-kind">${kindNote}</div>
          </div>`;
      })
      .join('');
    quotaBar.innerHTML = `<h2>Cota das IAs (hoje)</h2><div class="quota-grid">${cards}</div>`;
    populateProviderSelect(items.filter((q) => q.provider_id !== 'planner_groq'));
  } catch (err) {
    quotaBar.innerHTML = '';
  }
}
loadQuota();
