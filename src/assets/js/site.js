/* Magitronic — comportamento do site (sem dependências) */
(function () {
  'use strict';

  var BASE = document.body.getAttribute('data-base') || '';  // '/v2' na segunda versão
  var dl = (window.dataLayer = window.dataLayer || []);
  function track(event, data) {
    var payload = { event: event };
    for (var k in data) payload[k] = data[k];
    dl.push(payload);
  }

  // ---------- menu ----------
  var toggle = document.querySelector('.menu-toggle');
  var nav = document.getElementById('menu');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('open', open);
    });
  }
  document.querySelectorAll('.sub-toggle').forEach(function (btn) {
    var sub = document.getElementById(btn.getAttribute('aria-controls'));
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') !== 'true';
      btn.setAttribute('aria-expanded', String(open));
      sub.classList.toggle('open', open);
    });
    document.addEventListener('click', function (e) {
      if (window.innerWidth >= 1100 && !btn.parentElement.contains(e.target)) {
        btn.setAttribute('aria-expanded', 'false');
        sub.classList.remove('open');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && btn.getAttribute('aria-expanded') === 'true') {
        btn.setAttribute('aria-expanded', 'false');
        sub.classList.remove('open');
        btn.focus();
      }
    });
  });

  // ---------- medição de cliques (WhatsApp e telefone) ----------
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-track]');
    if (a) track(a.getAttribute('data-track') + '_click', { link_url: a.href, page_path: location.pathname });
  });

  // ---------- formulários de orçamento ----------
  function onlyDigits(s) { return (s || '').replace(/\D/g, ''); }

  function maskPhone(input) {
    input.addEventListener('input', function () {
      var d = onlyDigits(input.value).slice(0, 11);
      var out = d;
      if (d.length > 2) out = '(' + d.slice(0, 2) + ') ' + d.slice(2);
      if (d.length > 7) out = '(' + d.slice(0, 2) + ') ' + d.slice(2, d.length - 4) + '-' + d.slice(-4);
      input.value = out;
    });
  }

  function collect(form) {
    var lines = [];
    var data = {};
    form.querySelectorAll('[name]').forEach(function (el) {
      var name = el.name;
      if (name === 'botcheck' || name === 'consentimento') return;
      if ((el.type === 'radio' || el.type === 'checkbox') && !el.checked) return;
      var v = (el.value || '').trim();
      if (!v) return;
      data[name] = v;
      var label = el.getAttribute('data-label') || name;
      lines.push('*' + label + ':* ' + v);
    });
    return { data: data, lines: lines };
  }

  function validate(form) {
    var firstBad = null;
    form.querySelectorAll('[required]').forEach(function (el) {
      var bad = el.type === 'checkbox' ? !el.checked : !el.value.trim();
      if (el.type === 'tel' && !bad) bad = onlyDigits(el.value).length < 10;
      if (el.type === 'email' && !bad) bad = !/^\S+@\S+\.\S+$/.test(el.value);
      el.setAttribute('aria-invalid', bad ? 'true' : 'false');
      if (bad && !firstBad) firstBad = el;
    });
    var emailEl = form.querySelector('input[type="email"]');
    if (emailEl && emailEl.value && !/^\S+@\S+\.\S+$/.test(emailEl.value)) {
      emailEl.setAttribute('aria-invalid', 'true');
      firstBad = firstBad || emailEl;
    }
    return firstBad;
  }

  function sendEmail(form, collected, keepalive) {
    var key = form.getAttribute('data-key');
    if (!key) return Promise.resolve(false);
    var body = {
      access_key: key,
      subject: form.getAttribute('data-subject') || 'Pedido pelo site',
      from_name: 'Site Magitronic',
      pagina: location.href
    };
    for (var k in collected.data) body[k] = collected.data[k];
    body.botcheck = form.querySelector('[name="botcheck"]').checked;
    return fetch('https://api.web3forms.com/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      keepalive: !!keepalive
    }).then(function (r) { return r.json(); }).then(function (j) { return !!j.success; });
  }

  function remember(collected, channel) {
    try {
      sessionStorage.setItem('mg-lead', JSON.stringify({ lines: collected.lines, channel: channel }));
    } catch (e) {}
  }

  document.querySelectorAll('[data-lead-form]').forEach(function (form) {
    form.querySelectorAll('input[type="tel"]').forEach(maskPhone);
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var status = form.querySelector('.form-status');
      status.className = 'form-status';
      status.textContent = '';
      if (form.querySelector('[name="botcheck"]').checked) return;

      var bad = validate(form);
      if (bad) {
        status.className = 'form-status error';
        status.textContent = 'Confira os campos destacados antes de enviar.';
        bad.focus();
        return;
      }

      var collected = collect(form);
      var intro = form.getAttribute('data-intro') || 'Olá!';
      var text = intro + '\n\n' + collected.lines.join('\n') + '\n\n(enviado pelo site)';
      var waUrl = 'https://wa.me/' + form.getAttribute('data-wa') + '?text=' + encodeURIComponent(text);

      var channel = form.getAttribute('data-channel');
      var pref = collected.data.preferencia || 'WhatsApp';
      var hasKey = !!form.getAttribute('data-key');
      var viaWhatsApp = channel === 'whatsapp' || pref === 'WhatsApp' || !hasKey;

      track('generate_lead', { form_id: form.id, lead_channel: viaWhatsApp ? 'whatsapp' : 'email', page_path: location.pathname });
      remember(collected, viaWhatsApp ? 'whatsapp' : 'email');

      if (viaWhatsApp) {
        // abre o WhatsApp no mesmo gesto do clique (evita bloqueio de pop-up) e manda uma cópia por e-mail
        // (sem 'noopener' no terceiro argumento: com ele o window.open sempre retorna null)
        var win = window.open(waUrl, '_blank');
        if (win) win.opener = null;
        sendEmail(form, collected, true).catch(function () {});
        try { sessionStorage.setItem('mg-wa', waUrl); } catch (err) {}
        if (!win) { location.href = waUrl; return; }
        location.href = BASE + '/obrigado';
        return;
      }

      var btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      status.textContent = 'Enviando…';
      sendEmail(form, collected, false).then(function (ok) {
        if (!ok) throw new Error('falha');
        try { sessionStorage.setItem('mg-wa', waUrl); } catch (err) {}
        location.href = BASE + '/obrigado';
      }).catch(function () {
        btn.disabled = false;
        status.className = 'form-status error';
        status.innerHTML = 'Não conseguimos enviar agora. <a href="' + waUrl + '" target="_blank" rel="noopener">Envie o mesmo pedido pelo WhatsApp</a> ou ligue para (11) 5052-5228.';
      });
    });
  });

  // pré-seleção pela URL: /orcamento?tipo=Peça&defeito=...
  var params = new URLSearchParams(location.search);
  ['tipo', 'defeito', 'peca', 'marca'].forEach(function (name) {
    var v = params.get(name);
    if (!v) return;
    document.querySelectorAll('select[name="' + name + '"]').forEach(function (sel) {
      for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].text === v) sel.selectedIndex = i;
      }
    });
  });

  // página de obrigado: resumo do pedido
  var summary = document.getElementById('lead-summary');
  if (summary) {
    try {
      var lead = JSON.parse(sessionStorage.getItem('mg-lead') || 'null');
      var wa = sessionStorage.getItem('mg-wa');
      if (lead && lead.lines && lead.lines.length) {
        var ul = document.createElement('ul');
        lead.lines.forEach(function (l) {
          var li = document.createElement('li');
          li.textContent = l.replace(/\*/g, '');
          ul.appendChild(li);
        });
        summary.appendChild(ul);
        summary.hidden = false;
      }
      var waBtn = document.getElementById('lead-wa');
      if (waBtn && wa) waBtn.href = wa;
    } catch (e) {}
  }

  // ---------- carrossel do topo ----------
  document.querySelectorAll('[data-carousel]').forEach(function (car) {
    var slides = [].slice.call(car.querySelectorAll('.slide'));
    if (slides.length < 2) return;
    var dotsBox = car.querySelector('.car-dots');
    var interval = parseInt(car.getAttribute('data-interval'), 10) || 10000;
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var index = 0;
    var timer = null;
    var dots = slides.map(function (_, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', 'Ir para o quadro ' + (i + 1));
      b.addEventListener('click', function () { go(i); restart(); });
      if (dotsBox) dotsBox.appendChild(b);
      return b;
    });

    function go(i) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (s, n) {
        var on = n === index;
        s.classList.toggle('is-active', on);
        if (on) s.removeAttribute('aria-hidden'); else s.setAttribute('aria-hidden', 'true');
        s.querySelectorAll('a, button').forEach(function (el) {
          if (on) el.removeAttribute('tabindex'); else el.setAttribute('tabindex', '-1');
        });
      });
      dots.forEach(function (d, n) {
        if (n === index) d.setAttribute('aria-current', 'true'); else d.removeAttribute('aria-current');
      });
    }
    function next() { go(index + 1); }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function start() {
      if (reduce || document.hidden) return;
      stop();
      timer = setInterval(next, interval);
    }
    function restart() { stop(); start(); }

    car.querySelector('.car-next').addEventListener('click', function () { next(); restart(); });
    car.querySelector('.car-prev').addEventListener('click', function () { go(index - 1); restart(); });

    // clique no quadro (fora de links e botões) avança
    car.addEventListener('click', function (e) {
      if (e.target.closest('a, button')) return;
      next();
      restart();
    });

    // pausa enquanto a pessoa interage ou a aba está em segundo plano
    car.addEventListener('mouseenter', stop);
    car.addEventListener('mouseleave', start);
    car.addEventListener('focusin', stop);
    car.addEventListener('focusout', start);
    document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); else start(); });

    // arrastar no celular
    var x0 = null;
    car.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; stop(); }, { passive: true });
    car.addEventListener('touchend', function (e) {
      if (x0 !== null) {
        var dx = e.changedTouches[0].clientX - x0;
        if (Math.abs(dx) > 40) { go(index + (dx < 0 ? 1 : -1)); }
      }
      x0 = null;
      start();
    });

    car.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { next(); restart(); }
      if (e.key === 'ArrowLeft') { go(index - 1); restart(); }
    });

    go(0);
    start();
  });

  // ---------- mapa sob demanda ----------
  document.querySelectorAll('.map-load').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var iframe = document.createElement('iframe');
      iframe.src = btn.getAttribute('data-map-src');
      iframe.title = btn.getAttribute('data-map-title');
      iframe.referrerPolicy = 'no-referrer-when-downgrade';
      btn.parentElement.classList.remove('map-facade');
      btn.replaceWith(iframe);
    });
  });

  // ---------- consentimento de cookies (LGPD) ----------
  var consent = document.getElementById('consent');
  if (consent) {
    var saved = null;
    try { saved = localStorage.getItem('mg-consent'); } catch (e) {}
    if (!saved) consent.hidden = false;
    consent.addEventListener('click', function (e) {
      var b = e.target.closest('[data-consent]');
      if (!b) return;
      var v = b.getAttribute('data-consent');
      try { localStorage.setItem('mg-consent', v); } catch (err) {}
      if (typeof window.gtag === 'function') {
        var s = v === 'granted' ? 'granted' : 'denied';
        window.gtag('consent', 'update', { ad_storage: s, ad_user_data: s, ad_personalization: s, analytics_storage: s });
      }
      consent.hidden = true;
    });
  }
})();
