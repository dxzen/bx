// Reveal.js manages the current slide. The same HTML remains readable without JavaScript.
(() => {
  const root = document.querySelector('main.reveal');
  if (!root || typeof Reveal !== 'function') return;
  const pages = Array.from(root.querySelectorAll('.slides > .slide'));
  if (!pages.length) return;

  if (window.self !== window.top && new URLSearchParams(location.search).get('poster') === '1') {
    document.documentElement.classList.add('poster');
  }
  const byId = id => document.getElementById(id);
  const position = byId('position');
  const previous = byId('previous');
  const next = byId('next');
  const fullscreen = byId('fullscreen');
  const progress = document.querySelector('.progress-line > span');
  const engine = new Reveal(root, {
    // Keep ordinary CSS reflow, browser zoom and vertical scrolling within a long page.
    embedded: true, disableLayout: true, center: false, scrollActivationWidth: 0,
    display: 'flex', transition: 'none', backgroundTransition: 'none',
    controls: false, progress: false, slideNumber: false, overview: false, help: false,
    jumpToSlide: false, keyboard: false, touch: false, hideInactiveCursor: false,
    // Reveal reads named anchors and browser history; our controls keep the legacy #id URL.
    hash: false, history: false, respondToHashChanges: true,
    postMessage: false, focusBodyOnPageVisibilityChange: false
  });

  const pad = value => String(value).padStart(2, '0');
  function updateControls() {
    const current = engine.getIndices().h;
    position.textContent = `${pad(current + 1)} / ${pad(pages.length)}`;
    previous.disabled = current === 0;
    next.disabled = current === pages.length - 1;
    if (progress) progress.style.transform = `scaleX(${(current + 1) / pages.length})`;
  }

  function go(index) {
    if (!pages[index]) return;
    engine.slide(index);
    history.replaceState(null, '', '#' + pages[index].id);
    pages[index].focus({ preventScroll: true });
  }

  const fullscreenElement = () => document.fullscreenElement || document.webkitFullscreenElement;
  function updateFullscreen() {
    const active = Boolean(fullscreenElement());
    fullscreen.setAttribute('aria-pressed', String(active));
    fullscreen.setAttribute('aria-label', active ? '退出全屏' : '进入全屏');
    fullscreen.title = active ? '退出全屏（F）' : '进入全屏（F）';
  }
  async function toggleFullscreen() {
    if (fullscreen.disabled) return;
    try {
      if (fullscreenElement()) {
        const exit = document.exitFullscreen || document.webkitExitFullscreen;
        await exit.call(document);
      } else {
        const element = document.documentElement;
        const enter = element.requestFullscreen || element.webkitRequestFullscreen;
        await enter.call(element);
      }
    } catch {
      fullscreen.title = '当前窗口不允许系统全屏，可在单独窗口打开报告';
    }
  }

  // The nine modules form a business model. Mark typical reading paths, never hide text.
  const relations = {
    partners: ['activities', 'resources'], activities: ['resources', 'value', 'costs'],
    resources: ['activities', 'costs'], value: ['segments', 'channels', 'revenue'],
    relations: ['segments', 'channels'], channels: ['partners', 'segments', 'revenue'],
    segments: ['value', 'relations', 'revenue'], costs: ['activities', 'resources'],
    revenue: ['segments', 'value', 'costs']
  };
  const canvas = root.querySelector('.canvas');
  const cells = canvas ? Array.from(canvas.querySelectorAll('.cell[data-cell]')) : [];
  function selectCell(key) {
    if (!canvas) return;
    canvas.classList.toggle('has-selection', Boolean(key));
    for (const cell of cells) {
      const selected = cell.dataset.cell === key;
      cell.classList.toggle('is-selected', selected);
      cell.classList.toggle('is-related', Boolean(relations[key]?.includes(cell.dataset.cell)));
      cell.querySelector('.cell-trigger').setAttribute('aria-pressed', String(selected));
    }
  }

  engine.initialize().then(() => {
    document.documentElement.classList.add('enhanced');
    updateControls();
    engine.on('slidechanged', ({currentSlide}) => {
      updateControls();
      currentSlide.scrollTop = 0;
      if (canvas?.classList.contains('has-selection')) selectCell(null);
    });

    // Keep existing #evidence-N links shareable. Back returns to the citing slide.
    root.addEventListener('click', event => {
      const link = event.target.closest('a[href^="#"]');
      if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      const target = byId(link.getAttribute('href').slice(1));
      const page = target?.closest('.slide');
      if (!page) return;
      event.preventDefault();
      event.stopPropagation();
      history.pushState(null, '', link.getAttribute('href'));
      engine.slide(pages.indexOf(page));
      page.focus({ preventScroll: true });
      if (target !== page) target.scrollIntoView({ block: 'nearest' });
    }, true);

    canvas?.addEventListener('click', event => {
      if (event.target.closest('a')) return;
      const cell = event.target.closest('.cell[data-cell]');
      if (cell) selectCell(cell.classList.contains('is-selected') ? null : cell.dataset.cell);
    });
    previous.onclick = () => go(engine.getIndices().h - 1);
    next.onclick = () => go(engine.getIndices().h + 1);
    byId('print').onclick = () => window.print();
    fullscreen.disabled = !(document.fullscreenEnabled || document.webkitFullscreenEnabled);
    fullscreen.onclick = toggleFullscreen;
    updateFullscreen();
    document.addEventListener('fullscreenchange', updateFullscreen);
    document.addEventListener('webkitfullscreenchange', updateFullscreen);
    window.addEventListener('keydown', event => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
          event.target.isContentEditable || event.target.closest('input, textarea, select')) return;
      const index = engine.getIndices().h;
      const keys = {ArrowRight: index + 1, ArrowDown: index + 1, PageDown: index + 1,
                    ArrowLeft: index - 1, ArrowUp: index - 1, PageUp: index - 1, Home: 0, End: pages.length - 1};
      if (Object.hasOwn(keys, event.key)) {
        event.preventDefault();
        go(keys[event.key]);
      } else if (event.key.toLowerCase() === 'f') {
        event.preventDefault();
        if (!event.repeat) toggleFullscreen();
      } else if (event.key === 'Escape') selectCell(null);
    });
  });
})();
