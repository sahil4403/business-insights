/**
 * SWIPE GESTURES — Instagram/iOS style, DONO sides se:
 *   • Left edge se RIGHT slide  -> BACK  (pichla page)
 *   • Right edge se LEFT slide  -> FORWARD (agle page, agar history me ho)
 * Glass bubble finger follow karta hai; release par snap + navigate.
 */
(function () {
    var EDGE = 56;        // dono taraf ka touch zone (pehle 28 tha)
    var TRIGGER = 0.30;   // 30% slide par navigate

    var startX = 0, startY = 0;
    var tracking = false, dragging = false, navigated = false;
    var side = null;      // 'left' | 'right'
    var ui = null, dimEl = null, pillEl = null;

    function allowedTarget(t) {
        if (!t || !t.closest) return false;
        if (t.closest('input, textarea, select, button, a, [contenteditable="true"]')) return false;
        if (t.closest('.overflow-x-auto, .app-tabs, .lq-bar, .lq-action, [data-noswipe]')) return false;
        return true;
    }

    function ensureUI() {
        if (ui) return;
        ui = document.createElement('div');
        ui.id = 'swipeback-ui';
        ui.innerHTML =
            '<div class="sb-dim"></div>' +
            '<div class="sb-pill">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M15 19l-7-7 7-7"/></svg></div>';
        dimEl = ui.querySelector('.sb-dim');
        pillEl = ui.querySelector('.sb-pill');
        document.body.appendChild(ui);
    }

    function rawProgress(dx) {
        var span = window.innerWidth * 0.35;
        return Math.min(Math.max(dx / span, 0), 1);
    }

    function paint(dx) {
        ui.classList.add('on');
        var p = Math.abs(rawProgress(dx));
        dimEl.style.opacity = (p * 0.9).toFixed(2);

        var shift = -34 + p * 120;
        var scale = (0.85 + p * 0.3).toFixed(2);
        if (side === 'left') {
            pillEl.style.transform =
                'translate(' + shift.toFixed(1) + 'px, -50%) scale(' + scale + ')';
        } else {
            // Right side: mirror (bubble right edge se slide-in, arrow flip)
            pillEl.style.transform =
                'translate(' + (-shift.toFixed(1)) + 'px, -50%) scale(' + scale + ') scaleX(-1)';
        }
        pillEl.style.opacity = Math.min(p * 2.2, 1).toFixed(2);
    }

    function reset(animated) {
        if (!ui) return;
        if (!animated) { ui.classList.remove('on'); return; }
        ui.style.transition = 'opacity .18s ease';
        ui.style.opacity = '0';
        setTimeout(function () {
            ui.classList.remove('on');
            ui.style.opacity = '';
        }, 190);
    }

    function navigate() {
        navigated = true;
        if (side === 'right' && history.length > 0) {
            history.forward();
        } else if (history.length > 1) {
            history.back();
        } else {
            window.location.href = '/';
        }
        window.addEventListener('pageshow', function () { navigated = false; }, { once: true });
    }

    document.addEventListener('touchstart', function (e) {
        if (navigated) return;
        var t = e.target;
        if (!allowedTarget(t)) return;
        var touch = e.touches[0];
        var w = window.innerWidth;
        side = null;
        if (touch.clientX <= EDGE) side = 'left';
        else if (touch.clientX >= w - EDGE) side = 'right';
        if (!side) return;
        startX = touch.clientX;
        startY = touch.clientY;
        tracking = true;
        dragging = false;
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (!tracking || navigated || !side) return;
        var touch = e.touches[0];
        var dx = touch.clientX - startX;
        var dy = touch.clientY - startY;

        // Har side ke liye "aage" ki direction alag hai
        var forwardDx = side === 'left' ? dx : -dx;
        if (!dragging) {
            if (forwardDx <= 6) return;
            if (Math.abs(dy) > Math.abs(dx) * 1.2) { tracking = false; return; }
            dragging = true;
            ensureUI();
            pillEl.classList.toggle('from-right', side === 'right');
        }
        paint(forwardDx);
        if (e.cancelable) e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchend', function (e) {
        if (!tracking) return;
        tracking = false;
        if (!dragging || navigated) { dragging = false; return; }
        dragging = false;
        var dx = e.changedTouches[0].clientX - startX;
        var forwardDx = side === 'left' ? dx : -dx;
        if (rawProgress(forwardDx) >= TRIGGER) {
            reset(true);
            navigate();
        } else {
            reset(false);
            if (ui) ui.classList.remove('on');
        }
    });

    document.addEventListener('touchcancel', function () {
        tracking = false; dragging = false;
        reset(false);
        if (ui) ui.classList.remove('on');
    });
})();
