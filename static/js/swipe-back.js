/**
 * SWIPE-BACK GESTURE (Instagram/iOS style)
 * Left edge se right slide -> glass Back bubble follow karta hai ->
 * release par pichla page (browsing history wala hi order: trip detail
 * -> statement -> customers -> ...) smooth view-transition ke saath.
 */
(function () {
    var EDGE = 28;            // kitne px andar se start ho gesture
    var TRIGGER = 0.32;       // 32% slide par back navigate hoga
    var MAXSHIFT = 26;        // page ka max visual shift (px)

    var startX = 0, startY = 0;
    var tracking = false, dragging = false, navigated = false;
    var ui = null, dimEl = null, pillEl = null;

    function allowedTarget(t) {
        if (!t || !t.closest) return false;
        // Inputs, links, buttons aur horizontally-scrollable areas me gesture off
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

    function progress(dx) {
        var span = window.innerWidth * 0.35;
        var p = Math.min(Math.max(dx / span, 0), 1);
        return p;
    }

    function paint(p) {
        ui.classList.add('on');
        dimEl.style.opacity = (p * 0.9).toFixed(2);
        // Pill left edge se finger ke saath slide
        var x = -34 + p * 120;
        pillEl.style.transform = 'translate(' + x.toFixed(1) + 'px, -50%) scale(' +
            (0.85 + p * 0.3).toFixed(2) + ')';
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

    function goBack() {
        navigated = true;
        if (history.length > 1) history.back();
        else window.location.href = '/';
        // Naye page par fresh gesture ke liye flag reset (bfcache safe)
        window.addEventListener('pageshow', function () { navigated = false; }, { once: true });
    }

    document.addEventListener('touchstart', function (e) {
        if (navigated) return;
        var t = e.target;
        if (!allowedTarget(t)) return;
        var touch = e.touches[0];
        if (touch.clientX > EDGE) return;
        startX = touch.clientX;
        startY = touch.clientY;
        tracking = true;
        dragging = false;
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (!tracking || navigated) return;
        var touch = e.touches[0];
        var dx = touch.clientX - startX;
        var dy = touch.clientY - startY;

        if (!dragging) {
            if (dx <= 6) return;
            // Zyada vertical ho toh cancel (scroll priority)
            if (Math.abs(dy) > Math.abs(dx) * 1.2) { tracking = false; return; }
            if (history.length <= 1) { tracking = false; return; }
            dragging = true;
            ensureUI();
        }
        paint(progress(dx));
        if (e.cancelable) e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchend', function (e) {
        if (!tracking) return;
        tracking = false;
        if (!dragging || navigated) { dragging = false; return; }
        dragging = false;
        var dx = e.changedTouches[0].clientX - startX;
        var p = progress(dx);
        if (p >= TRIGGER) {
            reset(true);
            goBack();
        } else {
            reset(false);
            ui.classList.remove('on');
        }
    });

    document.addEventListener('touchcancel', function () {
        tracking = false; dragging = false;
        reset(false);
        if (ui) ui.classList.remove('on');
    });
})();
