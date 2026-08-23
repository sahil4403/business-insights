/**
 * LIVE SLIDE GESTURES — Instagram/iOS jaisa:
 * Drag karte waqt CURRENT PAGE khud slide hota hai, neeche previous-layer
 * dikhti hai. Release: threshold cross -> page bahar slide + navigate;
 * warna spring-back. Right side se ulta slide = FORWARD.
 */
(function () {
    var EDGE = 64;          // dono taraf touch zone
    var TRIGGER = 0.30;     // 30% ya flick velocity par commit
    var FLICK_V = 0.55;     // px/ms — tez flick bhi commit

    var startX = 0, startY = 0, lastX = 0, lastT = 0;
    var tracking = false, dragging = false, animating = false, navigated = false;
    var side = null;        // 'left' | 'right'
    var under = null;

    function shell() { return document.getElementById('app-shell'); }

    function allowedTarget(t) {
        if (!t || !t.closest) return false;
        if (t.closest('input, textarea, select, button, a, [contenteditable="true"]')) return false;
        if (t.closest('.overflow-x-auto, .app-tabs, .lq-bar, .lq-action, [data-noswipe]')) return false;
        return true;
    }

    function ensureUnder() {
        if (under) return;
        under = document.createElement('div');
        under.id = 'swipe-under';
        under.innerHTML =
            '<div class="su-brand">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
            '<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg>' +
            '<span>Business Insights</span></div>';
        document.body.appendChild(under);
    }

    function rawP(dx) {
        return Math.min(Math.max(dx / (window.innerWidth * 0.42), 0), 1);
    }

    function paint(dx) {
        var sh = shell(); if (!sh || !under) return;
        var p = rawP(dx);
        var maxShift = window.innerWidth * 0.86;
        var shift = Math.max(0, Math.min(Math.abs(dx), maxShift));
        if (side === 'right') shift = -shift;
        sh.style.transform = 'translateX(' + shift.toFixed(1) + 'px)';
        under.style.opacity = Math.min(p * 1.5, 1).toFixed(2);
    }

    function setTransition(on) {
        var sh = shell(); if (!sh) return;
        sh.style.transition = on ? 'transform .26s cubic-bezier(.22,.9,.3,1)' : 'none';
    }

    function clearDrag() {
        var sh = shell();
        if (sh) {
            sh.style.transition = '';
            sh.style.transform = '';
            sh.style.willChange = '';
        }
        if (under) under.style.opacity = '0';
    }

    function commit(dx) {
        var sh = shell(); if (!sh) { navigate(); return; }
        animating = true;
        var full = window.innerWidth * 0.92;
        if (side === 'right') full = -full;
        sh.style.transform = 'translateX(' + full + 'px)';
        setTimeout(function () {
            navigated = true;
            if (side === 'right' && history.length > 0) history.forward();
            else if (history.length > 1) history.back();
            else window.location.href = '/';
            window.addEventListener('pageshow', function () {
                animating = false; navigated = false;
                clearDrag();
                if (under) under.style.opacity = '0';
            }, { once: true });
        }, 210);
    }

    document.addEventListener('touchstart', function (e) {
        if (animating || navigated) return;
        var t = e.target;
        if (!allowedTarget(t)) return;
        var touch = e.touches[0];
        var w = window.innerWidth;
        side = null;
        if (touch.clientX <= EDGE) side = 'left';
        else if (touch.clientX >= w - EDGE) side = 'right';
        if (!side) return;
        startX = lastX = touch.clientX;
        startY = lastT = touch.clientY;
        lastT = performance.now();
        tracking = true; dragging = false;
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (!tracking || navigated || animating || !side) return;
        var touch = e.touches[0];
        var dx = touch.clientX - startX;
        var dy = touch.clientY - startY;
        var forwardDx = side === 'left' ? dx : -dx;

        if (!dragging) {
            if (forwardDx <= 8) return;
            if (Math.abs(dy) > Math.abs(dx) * 1.15) { tracking = false; return; }
            dragging = true;
            ensureUnder();
            var sh = shell();
            if (sh) sh.style.willChange = 'transform';
        }
        paint(forwardDx);
        // flick velocity sample
        var now = performance.now();
        var dt = now - lastT;
        if (dt > 0) {
            window.__swipeV = ((side === 'left' ? dx : -dx) - 0) / (now - (window.__swipeT0 || now)) || 0;
            window.__swipeT0 = window.__swipeT0 || now;
        }
        lastX = touch.clientX;
        if (e.cancelable) e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchend', function (e) {
        if (!tracking) return;
        tracking = false;
        if (!dragging || navigated || animating) { dragging = false; return; }
        dragging = false;

        var dx = e.changedTouches[0].clientX - startX;
        var forwardDx = side === 'left' ? dx : -dx;
        var p = rawP(forwardDx);
        var vel = window.__swipeV || 0;

        if (p >= TRIGGER || (vel > FLICK_V && forwardDx > 40)) {
            ensureUnder();
            under.style.opacity = '1';
            commit(forwardDx);
        } else {
            setTransition(true);
            paint(0);
            setTimeout(function () { clearDrag(); }, 280);
        }
        window.__swipeV = 0; window.__swipeT0 = null;
    });

    document.addEventListener('touchcancel', function () {
        tracking = false; dragging = false;
        clearDrag();
    });

    // bfcache wapas aane par reset
    window.addEventListener('pageshow', function () {
        animating = false; navigated = false;
        clearDrag();
        if (under) under.style.opacity = '0';
    });
})();
