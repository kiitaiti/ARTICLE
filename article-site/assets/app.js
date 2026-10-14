/* ============================================================
   ARTICLE — shared behaviour
   タッチ端末（スマホ/タブレット）は軽量モードで動作します。
   ============================================================ */
(function () {
  'use strict';

  var IS_TOUCH = matchMedia('(hover: none) and (pointer: coarse)').matches;
  var REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var USE_IFRAMES = !IS_TOUCH;
  window.ARTICLE_USE_IFRAMES = USE_IFRAMES;

  /* ---------- LOADER ---------- */
  (function () {
    var loader = document.getElementById('loader');
    if (!loader) return;
    var hide = function () {
      loader.classList.add('done');
      setTimeout(function () { if (loader.parentNode) loader.remove(); }, 1000);
    };
    window.addEventListener('load', function () { setTimeout(hide, 620); });
    setTimeout(hide, 2600); // 保険
  })();

  /* ---------- 背景の明暗に応じてヘッダー配色を切り替え ---------- */
  (function () {
    var hd = document.querySelector('header');
    if (!hd) return;
    var ticking = false;
    var update = function () {
      ticking = false;
      var zones = document.querySelectorAll('[data-bg]');
      if (!zones.length) return;
      var y = hd.offsetHeight * 0.6, light = false;
      for (var i = 0; i < zones.length; i++) {
        var r = zones[i].getBoundingClientRect();
        if (r.top <= y && r.bottom > y) { light = zones[i].dataset.bg === 'light'; break; }
      }
      hd.classList.toggle('on-light', light);
    };
    var onScroll = function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    document.addEventListener('article:contentupdated', onScroll);
    update();
  })();

  /* ---------- モバイルメニュー ---------- */
  (function () {
    var btn = document.getElementById('menuBtn');
    var ov = document.getElementById('navOverlay');
    if (!btn || !ov) return;
    var close = ov.querySelector('.close');
    var open = function () {
      ov.classList.add('open');
      document.body.style.overflow = 'hidden';
      btn.setAttribute('aria-expanded', 'true');
      btn.setAttribute('aria-label', 'メニューを閉じる');
    };
    var shut = function () {
      ov.classList.remove('open');
      document.body.style.overflow = '';
      btn.setAttribute('aria-expanded', 'false');
      btn.setAttribute('aria-label', 'メニューを開く');
    };
    btn.addEventListener('click', function () {
      if (ov.classList.contains('open')) { shut(); } else { open(); }
    });
    if (close) close.addEventListener('click', shut);
    ov.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', shut); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') shut(); });
  })();

  /* ---------- スクロールで表示 ---------- */
  var revealIO = null;
  function initReveal(scope) {
    var els = (scope || document).querySelectorAll('.rv:not(.on)');
    if (!els.length) return;
    if (REDUCED) { els.forEach(function (el) { el.classList.add('on'); }); return; }
    if (!revealIO) {
      revealIO = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('on'); revealIO.unobserve(e.target); }
        });
      }, { threshold: 0.12 });
    }
    els.forEach(function (el) { revealIO.observe(el); });
  }
  window.ARTICLE_initReveal = initReveal;
  initReveal(document);

  /* ============================================================
     WORKS ページ
     - WEB / FILM のタブ切り替え
     - 1ページ9件のページ送り（URLの ?type= &page= と同期）
     - PCのみ実サイトのライブプレビュー（iframe）を重ねる
     - スマホ・タブレットは microCMS のサムネイル画像を表示（iframeは作らない）
     - 映像はモーダルで大きく再生
     ============================================================ */
  (function () {
    var PER_PAGE = 9;
    var section = document.querySelector('.wk-sec');
    if (!section) return;

    /* ---------- 1. Webサイトのライブプレビュー ----------
       スマホ・タブレットでは iframe を一切つくりません。
       HTMLに出力済みのサムネイル画像（img）がそのまま表示されます。       */
    var frameIO = null;
    function initPreviews(scope) {
      if (!USE_IFRAMES) return;              // スマホ・タブレットは何もしない
      var shots = (scope || document).querySelectorAll('.wk-shot[data-preview]:not([data-ready])');
      if (!shots.length) return;
      if (!frameIO) {
        frameIO = new IntersectionObserver(function (entries) {
          entries.forEach(function (e) {
            if (!e.isIntersecting) return;
            mountFrame(e.target);
            frameIO.unobserve(e.target);
          });
        }, { rootMargin: '300px 0px' });
      }
      shots.forEach(function (s) { s.setAttribute('data-ready', '1'); frameIO.observe(s); });
    }

    function mountFrame(shot) {
      var url = shot.getAttribute('data-preview');
      var frame = shot.querySelector('.wk-frame');
      if (!url || !frame || frame.querySelector('iframe')) return;
      var ifr = document.createElement('iframe');
      ifr.src = url;
      ifr.title = '';
      ifr.setAttribute('aria-hidden', 'true');
      ifr.setAttribute('tabindex', '-1');
      ifr.setAttribute('loading', 'lazy');
      ifr.setAttribute('scrolling', 'no');
      ifr.addEventListener('load', function () { shot.classList.add('is-live'); });
      frame.appendChild(ifr);
      fitFrame(shot);
    }

    function fitFrame(shot) {
      var ifr = shot.querySelector('iframe');
      var frame = shot.querySelector('.wk-frame');
      if (!ifr || !frame) return;
      var scale = frame.clientWidth / 1440;
      ifr.style.width = '1440px';
      ifr.style.height = (frame.clientHeight / scale) + 'px';
      ifr.style.transform = 'scale(' + scale + ')';
    }
    function fitAll() {
      section.querySelectorAll('.wk-shot.is-live').forEach(fitFrame);
    }
    var fitTimer;
    window.addEventListener('resize', function () {
      clearTimeout(fitTimer); fitTimer = setTimeout(fitAll, 150);
    });

    /* ---------- 2. 動画モーダル ---------- */
    var modal = document.getElementById('videoModal');
    var mVideo = document.getElementById('vmodalVideo');
    var mTitle = document.getElementById('vmodalTitle');
    var lastFocus = null;

    function openModal(src, title, vertical) {
      if (!modal || !mVideo) return;
      lastFocus = document.activeElement;
      mTitle.textContent = title || '';
      modal.classList.toggle('is-vertical', !!vertical);
      mVideo.src = src;
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      // 表示直後にフォーカスを閉じるボタンへ
      requestAnimationFrame(function () {
        modal.classList.add('is-open');
        var close = modal.querySelector('.vmodal-close');
        if (close) close.focus();
        var pr = mVideo.play();
        if (pr && pr.catch) pr.catch(function () {});
      });
    }

    function closeModal() {
      if (!modal || modal.hidden) return;
      mVideo.pause();
      mVideo.removeAttribute('src');
      mVideo.load();                       // 読み込みを完全に止める
      modal.classList.remove('is-open');
      modal.hidden = true;
      document.body.style.overflow = '';
      if (lastFocus && lastFocus.focus) lastFocus.focus();
      lastFocus = null;
    }

    if (modal) {
      modal.querySelectorAll('[data-vmodal-close]').forEach(function (el) {
        el.addEventListener('click', closeModal);
      });
      document.addEventListener('keydown', function (e) {
        if (modal.hidden) return;
        if (e.key === 'Escape') { closeModal(); return; }
        if (e.key !== 'Tab') return;
        // フォーカスをモーダル内に閉じ込める
        var f = modal.querySelectorAll('button, video, [href], [tabindex]:not([tabindex="-1"])');
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      });
    }

    section.addEventListener('click', function (e) {
      var btn = e.target.closest('.wk-link[data-video]');
      if (!btn) return;
      e.preventDefault();
      openModal(btn.getAttribute('data-video'),
                btn.getAttribute('data-title'),
                btn.hasAttribute('data-vertical'));
    });

    /* ---------- 3. タブ + ページ送り ---------- */
    var tabbar = section.querySelector('.wk-tabbar');
    var tabs = Array.prototype.slice.call(section.querySelectorAll('[role="tab"]'));
    var panels = {};
    var counters = section.querySelector('[data-count]');
    section.querySelectorAll('.wk-panel').forEach(function (p) {
      panels[p.dataset.tab] = {
        el: p,
        cards: Array.prototype.slice.call(p.querySelectorAll('.wk-card')),
        pager: p.querySelector('.wk-pager'),
        page: 1
      };
    });
    if (!tabs.length || !Object.keys(panels).length) { initPreviews(document); return; }

    var current = 'web';

    function pageCount(kind) {
      return Math.max(1, Math.ceil(panels[kind].cards.length / PER_PAGE));
    }

    function buildNums(kind) {
      var d = panels[kind];
      if (!d.pager) return;
      var ol = d.pager.querySelector('.wk-pg-nums');
      if (!ol) return;
      ol.innerHTML = '';
      for (var n = 1; n <= pageCount(kind); n++) {
        var li = document.createElement('li');
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = ('0' + n).slice(-2);
        b.dataset.page = n;
        b.setAttribute('aria-label', n + 'ページ目へ');
        li.appendChild(b);
        ol.appendChild(li);
      }
    }

    function renderPage(kind, scroll) {
      var d = panels[kind];
      var total = pageCount(kind);
      if (d.page > total) d.page = total;
      if (d.page < 1) d.page = 1;

      d.cards.forEach(function (c) {
        c.hidden = (parseInt(c.dataset.page, 10) || 1) !== d.page;
      });

      if (d.pager) {
        d.pager.hidden = total <= 1;
        d.pager.querySelectorAll('.wk-pg-nums button').forEach(function (b) {
          var on = parseInt(b.dataset.page, 10) === d.page;
          b.setAttribute('aria-current', on ? 'page' : 'false');
        });
        var prev = d.pager.querySelector('[data-nav="prev"]');
        var next = d.pager.querySelector('[data-nav="next"]');
        if (prev) prev.disabled = d.page <= 1;
        if (next) next.disabled = d.page >= total;
      }

      if (counters) {
        var from = (d.page - 1) * PER_PAGE + 1;
        var to = Math.min(d.page * PER_PAGE, d.cards.length);
        counters.textContent = d.cards.length
          ? d.cards.length + '件中 ' + from + '\u2013' + to + '件を表示'
          : '';
      }

      initPreviews(d.el);
      if (window.ARTICLE_initReveal) window.ARTICLE_initReveal(d.el);
      fitAll();

      if (scroll) {
        var top = section.getBoundingClientRect().top + window.pageYOffset - 72;
        window.scrollTo({ top: top, behavior: REDUCED ? 'auto' : 'smooth' });
      }
    }

    function showTab(kind, scroll) {
      if (!panels[kind]) kind = 'web';
      current = kind;
      tabs.forEach(function (t) {
        var on = t.dataset.tab === kind;
        t.setAttribute('aria-selected', String(on));
        t.tabIndex = on ? 0 : -1;
      });
      Object.keys(panels).forEach(function (k) {
        panels[k].el.hidden = k !== kind;
      });
      renderPage(kind, scroll);
    }

    function syncUrl(replace) {
      var q = '?type=' + current + '&page=' + panels[current].page;
      var url = location.pathname + q;
      if (replace) history.replaceState(null, '', url);
      else history.pushState(null, '', url);
    }

    function readUrl() {
      var q = new URLSearchParams(location.search);
      var kind = (q.get('type') || '').toLowerCase();
      if (location.hash === '#film') kind = 'film';
      if (!panels[kind]) kind = 'web';
      var pg = parseInt(q.get('page'), 10);
      panels[kind].page = (pg && pg > 0) ? pg : 1;
      showTab(kind, false);
    }

    /* --- イベント --- */
    tabs.forEach(function (t) {
      t.addEventListener('click', function () {
        if (current === t.dataset.tab) return;
        panels[t.dataset.tab].page = 1;   // タブを切り替えたら1ページ目へ
        showTab(t.dataset.tab, false);
        syncUrl(false);
      });
      t.addEventListener('keydown', function (e) {
        var i = tabs.indexOf(t);
        var to = null;
        if (e.key === 'ArrowRight') to = tabs[(i + 1) % tabs.length];
        if (e.key === 'ArrowLeft') to = tabs[(i - 1 + tabs.length) % tabs.length];
        if (e.key === 'Home') to = tabs[0];
        if (e.key === 'End') to = tabs[tabs.length - 1];
        if (!to) return;
        e.preventDefault();
        to.focus();
        to.click();
      });
    });

    section.addEventListener('click', function (e) {
      var pgr = e.target.closest('.wk-pager');
      if (!pgr) return;
      var kind = pgr.dataset.pager;
      var d = panels[kind];
      if (!d) return;
      var num = e.target.closest('.wk-pg-nums button');
      var nav = e.target.closest('[data-nav]');
      if (num) d.page = parseInt(num.dataset.page, 10);
      else if (nav) d.page += (nav.dataset.nav === 'next' ? 1 : -1);
      else return;
      renderPage(kind, true);
      syncUrl(false);
    });

    window.addEventListener('popstate', readUrl);

    /* --- 初期化 --- */
    Object.keys(panels).forEach(buildNums);
    if (tabbar) tabbar.hidden = false;
    readUrl();
    syncUrl(true);
  })();

  /* ---------- 追加描画されたコンテンツを初期化 ---------- */
  document.addEventListener('article:contentupdated', function (e) {
    var scope = (e && e.detail && e.detail.scope) || document;
    initReveal(scope);
  });

  /* ---------- COLUMN：カテゴリー絞り込み ----------
     記事本文はビルド時に静的HTMLとして出力済みです。
     ここでは表示済みのカードを出し分けているだけで、通信は発生しません。      */
  (function () {
    var bar = document.querySelector('.col-filter');
    var grid = document.getElementById('columnGrid');
    if (!bar || !grid) return;

    var buttons = Array.prototype.slice.call(bar.querySelectorAll('button[data-filter]'));
    var cards = Array.prototype.slice.call(grid.querySelectorAll('.col-card'));
    var empty = document.getElementById('columnEmpty');

    function apply(cat, push) {
      cat = (cat || 'ALL').toUpperCase();
      if (!buttons.some(function (b) { return b.dataset.filter === cat; })) cat = 'ALL';

      var shown = 0;
      cards.forEach(function (card) {
        var hit = cat === 'ALL' || card.dataset.category === cat;
        card.hidden = !hit;
        if (hit) shown++;
      });
      buttons.forEach(function (b) {
        b.setAttribute('aria-pressed', String(b.dataset.filter === cat));
      });
      if (empty) empty.hidden = shown !== 0;
      grid.hidden = shown === 0;

      if (push) {
        var url = cat === 'ALL'
          ? location.pathname
          : location.pathname + '?cat=' + cat.toLowerCase();
        history.replaceState(null, '', url);
      }
      if (window.ARTICLE_initReveal) window.ARTICLE_initReveal(grid);
      document.dispatchEvent(new CustomEvent('article:contentupdated', { detail: { scope: grid } }));
    }

    buttons.forEach(function (b) {
      b.addEventListener('click', function () { apply(b.dataset.filter, true); });
    });

    var initial = new URLSearchParams(location.search).get('cat');
    if (initial) apply(initial, false);
  })();

  /* ---------- お問い合わせフォーム（Netlify Forms） ---------- */
  (function () {
    var form = document.getElementById('contactForm');
    var buttons = document.querySelectorAll('.pj-select button');
    var hidden = document.getElementById('pjType');

    /* ご相談の種類（ボタン選択） */
    if (buttons.length) {
      var select = function (type) {
        buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.pj === type)); });
        if (hidden) hidden.value = type || '';
      };
      buttons.forEach(function (b) {
        b.addEventListener('click', function () { select(b.dataset.pj); });
      });
      var t = new URLSearchParams(location.search).get('type');
      if (t) select(t);
    }

    if (!form) return;
    var msg = document.getElementById('formMsg');
    var btn = document.getElementById('contactSubmit');
    var label = btn ? btn.innerHTML : '';

    function setMsg(text, isError) {
      if (!msg) return;
      msg.textContent = text || '';
      msg.classList.toggle('is-error', !!isError);
    }

    function unlock() {
      form.removeAttribute('data-sending');
      if (btn) { btn.disabled = false; btn.innerHTML = label; }
    }

    /* 必須項目が空のとき、ブラウザ標準の検証は submit イベントを発生させずに
       止めてしまうため、invalid イベント（キャプチャ）でメッセージを出す。
       JavaScriptが動かない環境でも標準の検証は効くので、この形にしています。 */
    form.addEventListener('invalid', function () {
      setMsg('未入力、または形式が正しくない項目があります。ご確認ください。', true);
    }, true);

    form.addEventListener('submit', function (e) {
      /* 二重送信の防止 */
      if (form.getAttribute('data-sending') === '1') { e.preventDefault(); return; }

      /* 必須項目の確認（念のためJS側でも確認する） */
      if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
        e.preventDefault();
        setMsg('未入力、または形式が正しくない項目があります。ご確認ください。', true);
        var bad = form.querySelector(':invalid');
        if (bad) {
          if (typeof form.reportValidity === 'function') form.reportValidity();
          bad.focus();
        }
        return;
      }

      /* ハニーポットに入力がある＝ボット。送信せずに終わらせる */
      var honey = form.querySelector('[name="bot-field"]');
      if (honey && honey.value) { e.preventDefault(); location.href = '/thanks/'; return; }

      form.setAttribute('data-sending', '1');
      if (btn) { btn.disabled = true; btn.innerHTML = '送信中&hellip;'; }
      setMsg('送信しています。少々お待ちください。', false);
    });

    /* ブラウザの「戻る」で戻ったとき、ボタンが押せないままにならないように */
    window.addEventListener('pageshow', function () { unlock(); setMsg(''); });
  })();
})();
