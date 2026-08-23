/**
 * LIQUID TABBAR — touch/hold/slide ke liye iPhone-jaisa fluid blob.
 * Blob finger ko follow karta hai, velocity se stretch hota hai,
 * chhodne par nearest tab par spring-snap hota hai (aur navigate bhi).
 */
(function () {
    function init() {
        var bars = document.querySelectorAll('.lq-bar');
        bars.forEach(initBar);
    }

    function initBar(bar) {
        var links = Array.prototype.slice.call(bar.querySelectorAll('.lq-link'));
        if (!links.length || bar.dataset.liquidReady === '1') return;
        bar.dataset.liquidReady = '1';

        var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Blob element
        var blob = document.createElement('div');
        blob.className = 'lq-blob';
        bar.insertBefore(blob, bar.firstChild);

        var reducedPad = 3;

        function slotRect(el) {
            return { x: el.offsetLeft, w: el.offsetWidth };
        }

        function activeIndex() {
            for (var i = 0; i < links.length; i++) {
                if (links[i].classList.contains('active')) return i;
            }
            return -1;
        }

        var cur = activeIndex();
        var pos = { x: 0, w: 0 };
        var target = { x: 0, w: 0 };
        var vel = 0;
        var prevTargetX = null;
        var ready = false;

        function setImmediate(i) {
            var r = slotRect(links[i]);
            pos = { x: r.x + reducedPad, w: r.w - reducedPad * 2 };
            target = { x: pos.x, w: pos.w };
            paint();
            blob.style.opacity = '1';
            bar.classList.add('lq-ready');
            ready = true;
        }

        function goToSlot(i) {
            var r = slotRect(links[i]);
            target.x = r.x + reducedPad;
            target.w = r.w - reducedPad * 2;
        }

        // Initial placement (after fonts/layout settle)
        requestAnimationFrame(function () {
            if (cur >= 0) setImmediate(cur); else blob.style.opacity = '0';
        });
        window.addEventListener('resize', function () {
            cur = activeIndex();
            if (cur >= 0) setImmediate(cur);
        });

        // ---- Render loop ----
        function paint() {
            var sx = 1 + Math.min(Math.abs(vel) / 26, 0.45);
            var sy = 1 - Math.min(Math.abs(vel) / 90, 0.28);
            blob.style.width = pos.w + 'px';
            blob.style.transform =
                'translateX(' + pos.x + 'px)' +
                (reduceMotion ? '' : ' scaleX(' + sx.toFixed(3) + ') scaleY(' + sy.toFixed(3) + ')');
        }

        function tick() {
            if (!ready) { requestAnimationFrame(tick); return; }
            var dx = target.x - pos.x;
            var dw = target.w - pos.w;
            vel = prevTargetX === null ? 0 : (target.x - prevTargetX);
            prevTargetX = target.x;
            pos.x += dx * 0.24;
            pos.w += dw * 0.24;
            paint();
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);

        // ---- Pointer interactions ----
        var dragging = false;
        var moved = 0;
        var startClientX = 0;

        function localX(e) {
            var r = bar.getBoundingClientRect();
            return e.clientX - r.left;
        }
        function nearestIndex(x) {
            var best = 0, bestDist = Infinity;
            links.forEach(function (l, i) {
                var c = l.offsetLeft + l.offsetWidth / 2;
                var d = Math.abs(c - x);
                if (d < bestDist) { bestDist = d; best = i; }
            });
            return best;
        }
        function clearHovers() {
            links.forEach(function (l) { l.classList.remove('lq-hover'); });
        }

        // NOTE: setPointerCapture use NAHI karte — wo click ko bar par
        // re-target kar deta hai aur andar ke <a> links mar jaate hain.
        var activePid = null;

        function onWindowMove(e) {
            if (e.pointerId !== activePid) return;
            var lx = localX(e);
            moved = Math.max(moved, Math.abs(e.clientX - startClientX));
            var half = pos.w / 2;
            target.x = Math.max(reducedPad, Math.min(lx - half, bar.offsetWidth - pos.w - reducedPad));
            links.forEach(function (l, idx) {
                var cx = l.offsetLeft + l.offsetWidth / 2;
                l.classList.toggle('lq-hover', Math.abs(cx - lx) < l.offsetWidth / 2);
            });
        }
        function onWindowUp(e) {
            if (e.pointerId !== activePid) return;
            window.removeEventListener('pointermove', onWindowMove);
            activePid = null;

            var i = nearestIndex(localX(e));
            endDragVisualsOnly(i);

            // SIRF real slide par JS navigation — chhota tap = native click
            // handle karega. Pehle dono fire ho rahe the (double-nav = gitter).
            if (moved > 10) goToTab(i);
        }

        function endDragVisualsOnly(i) {
            clearHovers();
            var changed = i !== cur;
            cur = i;
            goToSlot(i);
            links.forEach(function (l, idx) { l.classList.toggle('active', idx === cur); });
        }

        function endDrag(e) {
            if (!dragging) return;
            dragging = false;
            clearHovers();
            var i = nearestIndex(localX(e));
            var changed = i !== cur;
            cur = i;
            goToSlot(i);

            links.forEach(function (l, idx) { l.classList.toggle('active', idx === cur); });
        }

        function goToTab(i) {
            var href = links[i].getAttribute('href');
            setTimeout(function () { window.location.href = href; }, moved > 10 ? 120 : 25);
        }

        bar.addEventListener('pointerdown', function (e) {
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            dragging = true;
            moved = 0;
            startClientX = e.clientX;
            prevTargetX = null;
            activePid = e.pointerId;
            window.addEventListener('pointermove', onWindowMove);
        });

        window.addEventListener('pointerup', onWindowUp);
        window.addEventListener('pointercancel', function (e) {
            if (e.pointerId !== activePid) { return; }
            window.removeEventListener('pointermove', onWindowMove);
            activePid = null;
            dragging = false;
            clearHovers();
            cur = activeIndex();
        });

        bar.addEventListener('pointermove', function (e) {
            if (activePid !== null) return; // drag chal raha hai — window handler dekh raha hai
            if (e.pointerType !== 'mouse') return;
            // Hover preview (desktop)
            var i = nearestIndex(localX(e));
            links.forEach(function (l, idx) { l.classList.toggle('lq-hover', idx === i); });
            goToSlot(i);
        });
        // Native clicks ko bilkul free chhone do — tap par <a> khud navigate
        // karta hai. Slide-release par upar wala pointerup handler navigate
        // karega (us case me click fire hi nahi hota).
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
