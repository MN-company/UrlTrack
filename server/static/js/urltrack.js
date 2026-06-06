function setActiveNav() {
  document.querySelectorAll('[data-nav]').forEach((link) => {
    const href = new URL(link.href, location.origin).pathname.replace(/\/$/, '');
    const current = location.pathname.replace(/\/$/, '');
    if (href === current || (href && href !== '/dashboard' && current.startsWith(href + '/'))) {
      link.classList.add('active');
    }
  });
}

function bindAppShell() {
  const moreWrap = document.querySelector('#moreWrap');
  const moreButton = document.querySelector('#moreBtn');
  const moreDropdown = document.querySelector('#moreDropdown');
  const avatarButton = document.querySelector('#avatarBtn');
  const avatarDropdown = document.querySelector('#avatarDropdown');
  const navLinks = [...document.querySelectorAll('#topNav > .topbar-item')];

  function rebuildOverflow() {
    if (!moreDropdown || !moreWrap) return;
    moreDropdown.innerHTML = '';
    navLinks.forEach((link) => {
      if (getComputedStyle(link).display === 'none') {
        const clone = link.cloneNode(true);
        clone.className = '';
        moreDropdown.appendChild(clone);
      }
    });
    moreWrap.style.display = moreDropdown.children.length ? 'block' : '';
  }

  function applyTheme(choice, persist = true) {
    const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.themeChoice = choice;
    document.documentElement.dataset.theme = choice === 'system' ? (dark ? 'dark' : 'light') : choice;
    if (persist) localStorage.setItem('urltrack-theme', choice);
    document.querySelectorAll('[data-theme-option]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.themeOption === choice);
    });
  }

  document.querySelectorAll('[data-theme-option]').forEach((button) => {
    button.addEventListener('click', () => applyTheme(button.dataset.themeOption));
  });
  applyTheme(document.documentElement.dataset.themeChoice || 'system', false);

  moreButton?.addEventListener('click', (event) => {
    event.stopPropagation();
    moreDropdown.classList.toggle('open');
    avatarDropdown?.classList.remove('open');
  });
  avatarButton?.addEventListener('click', (event) => {
    event.stopPropagation();
    avatarDropdown.classList.toggle('open');
    moreDropdown?.classList.remove('open');
  });
  document.addEventListener('click', () => {
    moreDropdown?.classList.remove('open');
    avatarDropdown?.classList.remove('open');
  });
  window.addEventListener('resize', rebuildOverflow);
  rebuildOverflow();
}

function bindToggles() {
  document.querySelectorAll('.toggle').forEach((toggle) => {
    toggle.addEventListener('click', () => toggle.classList.toggle('enabled'));
  });
}

function bindModeChips() {
  document.querySelectorAll('.mode-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const group = chip.closest('.mode-strip');
      if (!group) return;
      group.querySelectorAll('.mode-chip').forEach((item) => item.classList.remove('active'));
      chip.classList.add('active');
    });
  });
}

function bindTabs() {
  document.querySelectorAll('[data-tab-target]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = button.dataset.tabTarget;
      const scope = button.closest('[data-tabs]') || document;
      scope.querySelectorAll('[data-tab-target]').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      scope.querySelectorAll('.tab-panel').forEach((panel) => {
        panel.hidden = panel.id !== target;
      });
    });
  });
}

function bindTechnicalToggle() {
  document.querySelectorAll('[data-toggle-technical]').forEach((button) => {
    button.addEventListener('click', () => {
      const panel = document.querySelector(button.dataset.toggleTechnical);
      if (!panel) return;
      panel.hidden = !panel.hidden;
      button.textContent = panel.hidden ? 'Show technical fingerprint' : 'Hide technical fingerprint';
    });
  });
}

function bindGraph() {
  const nodes = document.querySelectorAll('.node');
  const title = document.querySelector('[data-node-title]');
  const body = document.querySelector('[data-node-body]');
  nodes.forEach((node) => {
    node.addEventListener('click', () => {
      nodes.forEach((item) => item.classList.remove('active'));
      node.classList.add('active');
      if (title) title.textContent = node.dataset.title || node.textContent.trim();
      if (body) body.textContent = node.dataset.body || 'Supporting visits loaded from shared identifiers and campaign overlap.';
    });
  });
}

const nodeCopy = {
  entry: {
    title: 'Short link entry',
    body: 'Owns the public URL, domain, slug, UTM tags, and first-touch event. It should stay readable because this is what the operator shares.',
    rules: ['Domain: go.urltrack.io', 'Slug: investor-pack', 'Campaign: Investor access']
  },
  gate: {
    title: 'Access gate',
    body: 'Decides who can continue. Combine email capture, password, captcha, consent, max clicks, expiration, and country rules without hiding the visitor path.',
    rules: ['Email required for unknown visitors', 'Captcha only when risk > 65', 'Consent shown before fingerprinting']
  },
  risk: {
    title: 'Risk decision',
    body: 'Scores traffic using VPN, hosting ASN, missing JS, repeated fingerprint, impossible travel, and failed gate attempts.',
    rules: ['Block VPN + failed captcha', 'Safe-route hosting ASN', 'Watch repeated canvas hash']
  },
  route: {
    title: 'Smart routing',
    body: 'Sends visitors to the right destination by device, country, campaign family, or risk. Safe URLs keep suspicious traffic away from protected assets.',
    rules: ['iOS -> TestFlight landing', 'Desktop -> secure demo room', 'Risk > 80 -> safe URL']
  },
  capture: {
    title: 'Lead capture',
    body: 'Turns repeated visits into people or entities. Captured fields feed Lead Intelligence and AI evidence citations.',
    rules: ['Fields: email, name, company', 'Score +18 after second visit', 'Webhook to CRM enrichment']
  },
  qr: {
    title: 'Dynamic QR',
    body: 'Shares the same link rules while separating scan analytics from regular clicks. Useful for events, print, and field sales.',
    rules: ['Scan source: booth-qr', 'Export SVG', 'Event segment retained']
  },
  alert: {
    title: 'Alert and evidence',
    body: 'Creates the audit trail: notifications, database events, journey graph edges, and AI Analyst citations.',
    rules: ['Telegram for hot leads', 'Webhook for blocked traffic', 'Evidence saved to visit file']
  }
};

function bindCreatorCanvas() {
  const nodes = document.querySelectorAll('[data-flow-node]');
  const title = document.querySelector('[data-inspector-title]');
  const body = document.querySelector('[data-inspector-body]');
  const rules = document.querySelector('[data-inspector-rules]');
  if (!nodes.length || !title || !body || !rules) return;

  const selectNode = (node) => {
    const id = node.dataset.flowNode;
    const copy = nodeCopy[id] || nodeCopy.entry;
    nodes.forEach((item) => item.classList.remove('selected'));
    node.classList.add('selected');
    title.textContent = copy.title;
    body.textContent = copy.body;
    rules.innerHTML = copy.rules.map((rule) => '<div class="rule-row"><span>' + rule + '</span><span class="badge info">Live</span></div>').join('');
  };

  nodes.forEach((node) => {
    node.addEventListener('click', () => selectNode(node));
  });
  selectNode(document.querySelector('[data-flow-node].selected') || nodes[0]);
}

function bindRunPreview() {
  const button = document.querySelector('[data-run-flow]');
  const output = document.querySelector('[data-run-output]');
  if (!button || !output) return;
  button.addEventListener('click', () => {
    const rows = [
      ['1', 'Visitor opens go.urltrack.io/investor-pack', 'Tracked'],
      ['2', 'Email gate appears because identity is unknown', 'Gate'],
      ['3', 'Captcha skipped after low-risk browser signal', 'Clean'],
      ['4', 'Desktop route sends visitor to secure demo room', 'Routed'],
      ['5', 'Lead score increases and Telegram alert fires', 'Alert']
    ];
    output.innerHTML = rows.map((row) => '<div class="run-step"><span class="run-index">' + row[0] + '</span><span>' + row[1] + '</span><span class="badge success">' + row[2] + '</span></div>').join('');
  });
}

function bindAiConsole() {
  const input = document.querySelector('[data-ai-input]');
  const output = document.querySelector('[data-ai-output]');
  const button = document.querySelector('[data-ai-run]');
  if (!input || !output || !button) return;
  button.addEventListener('click', () => {
    const query = input.value.trim() || '@hash:cv-9a81 explain related visits';
    output.innerHTML = '<strong>Analyst result</strong><p>' +
      'Query "' + query.replace(/[<>&]/g, '') + '" matches 4 visits across 2 campaigns. Highest confidence link is repeated canvas hash plus a shared MacBook browser profile. Review VT-1049 before releasing the gate block.</p>';
  });
}

function bindSmartEntry() {
  document.querySelectorAll('[data-smart-entry]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const value = form.querySelector('input[name="command"]')?.value.trim();
      if (!value) return;
      if (value.startsWith('@')) {
        location.href = form.dataset.aiUrl + '?message=' + encodeURIComponent(value);
      } else {
        const destination = /^https?:\/\//i.test(value) ? value : 'https://' + value;
        location.href = form.dataset.createUrl + '?destination=' + encodeURIComponent(destination);
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setActiveNav();
  bindAppShell();
  bindToggles();
  bindModeChips();
  bindTabs();
  bindTechnicalToggle();
  bindGraph();
  bindCreatorCanvas();
  bindRunPreview();
  bindAiConsole();
  bindSmartEntry();
});
