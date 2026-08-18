const ICONS = {
  chevronRight:
    '<svg class="icon-sm chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>',
  image:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="width:22px;height:22px;"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
  inbox:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="width:40px;height:40px;"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path></svg>',
  refresh:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>',
  check:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
  alert:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
  clock:
    '<svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
};

const libraryList = document.getElementById('library-list');
const jobDetail = document.getElementById('job-detail');
const jobDetailContent = document.getElementById('job-detail-content');
const backBtn = document.getElementById('back-to-list');

const STATUS_LABEL = { done: 'concluído', error: 'erro', pending: 'na fila', running: 'gerando...' };
const STATUS_ICON = { done: ICONS.check, error: ICONS.alert, pending: ICONS.clock, running: ICONS.clock };

async function loadLibrary() {
  libraryList.innerHTML = '<p class="hint">Carregando...</p>';
  const resp = await fetch('/jobs');
  const jobs = await resp.json();

  if (jobs.length === 0) {
    libraryList.innerHTML = `
      <div class="card empty-state">
        ${ICONS.inbox}
        <p><strong>Nenhuma geração ainda</strong></p>
        <p>Vá em "Criar" pra começar seu primeiro carrossel.</p>
      </div>`;
    return;
  }

  libraryList.innerHTML = '';
  jobs.forEach((job) => {
    const row = document.createElement('div');
    row.className = 'job-row';

    const modeLabel = job.mode === 'carousel' ? `Carrossel · ${job.num_images} imagens` : 'Imagem única';
    const statusIcon = STATUS_ICON[job.status] || '';

    row.innerHTML = `
      ${job.thumbnail_url ? `<img class="job-thumb" src="${job.thumbnail_url}" />` : `<div class="job-thumb empty">${ICONS.image}</div>`}
      <div class="job-row-info">
        <div class="job-row-title">
          ${modeLabel}
          <span class="status-badge ${job.status}">${statusIcon} ${STATUS_LABEL[job.status] || job.status}</span>
        </div>
        <div class="job-row-excerpt">${(job.content_excerpt || '(sem conteúdo)').replace(/</g, '&lt;')}</div>
      </div>
      <div class="job-row-date">${new Date(job.created_at).toLocaleString('pt-BR')}</div>
      ${ICONS.chevronRight}
    `;
    row.addEventListener('click', () => openJobDetail(job.id));
    libraryList.appendChild(row);
  });
}

async function openJobDetail(jobId) {
  const resp = await fetch(`/jobs/${jobId}`);
  const job = await resp.json();

  libraryList.classList.add('hidden');
  jobDetail.classList.remove('hidden');

  const refsHtml = (job.references || [])
    .map((r) => `<img src="${r.url}" title="${r.kind}" />`)
    .join('');

  const slidesHtml = job.slides
    .map(
      (s) => `
      <div class="slide-card${s.status === 'error' ? ' error' : ''}">
        ${s.image_url ? `<img src="${s.image_url}" />` : ''}
        <div class="slide-body">
          <div class="slide-meta">${STATUS_ICON[s.status] || ''} Slide ${s.idx}${s.role ? ' · ' + s.role : ''}${s.provider_used ? ' · ' + s.provider_used : ''}</div>
          ${s.status === 'error' ? `<div class="error-msg">${s.error_message || 'falhou'}</div>` : ''}
          <div class="prompt-block">${(s.final_prompt || '').replace(/</g, '&lt;')}</div>
        </div>
      </div>`
    )
    .join('');

  const modeLabel = job.mode === 'carousel' ? `Carrossel · ${job.num_images} imagens` : 'Imagem única';

  jobDetailContent.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">
        <h2>${modeLabel}</h2>
        <span class="status-badge ${job.status}">${STATUS_ICON[job.status] || ''} ${STATUS_LABEL[job.status] || job.status}</span>
      </div>
      <button id="repeat-call-btn" class="primary">${ICONS.refresh} Realizar chamada novamente</button>
    </div>
    <p class="hint">${new Date(job.created_at).toLocaleString('pt-BR')} · IA escolhida: ${job.preferred_provider || 'automática (melhor disponível)'}</p>

    <div class="field-block">
      <div class="field-block-label">Conteúdo</div>
      <div class="prompt-block">${(job.content_text || '').replace(/</g, '&lt;')}</div>
    </div>

    <div class="field-block">
      <div class="field-block-label">Design</div>
      <div class="prompt-block">${(job.design_text || '(não informado)').replace(/</g, '&lt;')}</div>
    </div>

    ${refsHtml ? `<div class="field-block"><div class="field-block-label">Referências usadas</div><div class="ref-strip">${refsHtml}</div></div>` : ''}

    <div class="field-block">
      <div class="field-block-label">Imagens geradas</div>
      <div class="gallery">${slidesHtml}</div>
    </div>
  `;

  document.getElementById('repeat-call-btn').addEventListener('click', () => {
    window.location.href = `/?repeat_job_id=${job.id}`;
  });
}

backBtn.addEventListener('click', () => {
  jobDetail.classList.add('hidden');
  libraryList.classList.remove('hidden');
});

loadLibrary();
