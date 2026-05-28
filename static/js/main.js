/**
 * SpiceBite Honeypot v2 — Main JavaScript
 * Includes: DevTools detection, user dropdown, flash auto-dismiss, nav scroll
 *
 * WARNING: DevTools detection is intentional honeypot behaviour.
 */

// ══════════════════════════════════════════════════════════════════════════════
// DEVTOOLS HONEYPOT DETECTION
// ══════════════════════════════════════════════════════════════════════════════
(function devToolsHoneypot() {
  'use strict';
  let dtOpen = false;
  const THRESHOLD = 160;

  function ping(data) {
    fetch('/api/devtools-ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).catch(function() {});
  }

  // Method 1: Window size differential
  function checkSize() {
    const wDiff = window.outerWidth  - window.innerWidth;
    const hDiff = window.outerHeight - window.innerHeight;
    const open  = wDiff > THRESHOLD || hDiff > THRESHOLD;
    if (open && !dtOpen) {
      dtOpen = true;
      ping({ event: 'devtools_opened', method: 'size_diff', w: wDiff, h: hDiff, ts: Date.now() });
    } else if (!open) {
      dtOpen = false;
    }
  }
  setInterval(checkSize, 2000);

  // Method 2: console.log profiling trick
  var devtoolsObj = { opened: false };
  Object.defineProperty(devtoolsObj, 'isOpened', {
    get: function() {
      if (!this.opened) {
        this.opened = true;
        ping({ event: 'devtools_opened', method: 'object_profiling', ts: Date.now() });
      }
    }
  });

  // Method 3: Intercept console usage (attacker probing)
  var _origConsole = {};
  ['log','warn','error','info','debug','table','dir'].forEach(function(m) {
    _origConsole[m] = console[m];
    console[m] = function() {
      var args = Array.prototype.slice.call(arguments).map(function(a) {
        try { return String(a).substring(0, 100); } catch(e) { return '[object]'; }
      });
      ping({ event: 'console_used', method: m, args: args, ts: Date.now() });
      return _origConsole[m].apply(console, arguments);
    };
  });
})();

// ══════════════════════════════════════════════════════════════════════════════
// USER DROPDOWN MENU
// ══════════════════════════════════════════════════════════════════════════════
(function userDropdown() {
  var btn = document.getElementById('userMenuBtn');
  var dd  = document.getElementById('userDropdown');
  if (!btn || !dd) return;

  btn.addEventListener('click', function(e) {
    e.stopPropagation();
    dd.classList.toggle('open');
  });

  document.addEventListener('click', function() {
    dd.classList.remove('open');
  });

  dd.addEventListener('click', function(e) {
    e.stopPropagation();
  });
})();

// ══════════════════════════════════════════════════════════════════════════════
// FLASH MESSAGE AUTO-DISMISS
// ══════════════════════════════════════════════════════════════════════════════
(function autoFlash() {
  var toasts = document.querySelectorAll('.flash-toast');
  toasts.forEach(function(el, i) {
    setTimeout(function() {
      el.style.transition = 'opacity .4s, transform .4s';
      el.style.opacity    = '0';
      el.style.transform  = 'translateX(20px)';
      setTimeout(function() { if (el.parentNode) el.parentNode.removeChild(el); }, 420);
    }, 3500 + i * 200);
  });
})();

// ══════════════════════════════════════════════════════════════════════════════
// NAVBAR SCROLL SHADOW
// ══════════════════════════════════════════════════════════════════════════════
(function navScroll() {
  var nav = document.getElementById('mainNav');
  if (!nav) return;
  window.addEventListener('scroll', function() {
    nav.style.boxShadow = window.scrollY > 40 ? '0 4px 40px rgba(0,0,0,.6)' : '';
  }, { passive: true });
})();

// ══════════════════════════════════════════════════════════════════════════════
// ITEM CARD 3D TILT
// ══════════════════════════════════════════════════════════════════════════════
(function cardTilt() {
  var cards = document.querySelectorAll('.item-card');
  cards.forEach(function(card) {
    card.addEventListener('mousemove', function(e) {
      var rect = card.getBoundingClientRect();
      var x = ((e.clientX - rect.left) / rect.width  - 0.5) * 10;
      var y = ((e.clientY - rect.top)  / rect.height - 0.5) * 10;
      card.style.transform  = 'translateY(-4px) rotateX(' + (-y) + 'deg) rotateY(' + x + 'deg)';
      card.style.transition = 'transform 0.05s';
    });
    card.addEventListener('mouseleave', function() {
      card.style.transform  = '';
      card.style.transition = 'all 0.3s';
    });
  });
})();

// ══════════════════════════════════════════════════════════════════════════════
// SMOOTH ANCHOR SCROLL
// ══════════════════════════════════════════════════════════════════════════════
document.querySelectorAll('a[href^="#"]').forEach(function(a) {
  a.addEventListener('click', function(e) {
    var target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ── Auth-gated button feedback ────────────────────────────────────────────────
document.querySelectorAll('form[action*="cart/add"]').forEach(form => {
  form.addEventListener('submit', function(e) {
    const btn = this.querySelector('button[type="submit"]');
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = '✓ Added!';
      btn.style.background = 'var(--green, #2ecc71)';
      setTimeout(() => { btn.innerHTML = orig; btn.style.background = ''; }, 1200);
    }
  });
});

// ── Checkout form validation ──────────────────────────────────────────────────
const co = document.getElementById('checkoutForm');
if (co) {
  co.addEventListener('submit', function(e) {
    const card = document.getElementById('cardNum');
    if (card && card.value.replace(/\s/g,'').length < 16) {
      e.preventDefault();
      card.style.borderColor = 'var(--accent)';
      card.focus();
      return;
    }
  });
}
