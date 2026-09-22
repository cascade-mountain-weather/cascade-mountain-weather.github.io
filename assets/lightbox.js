// Lightweight, dependency-free lightbox for data figures (forecast plots,
// model-tools images). Opt-in via class so new images have to ask for it
// explicitly: add "PlotFormat" (posts + ski-area tool pages), "SynopticPlot"
// (synoptic tools page), or a generic "lightbox-img" class to any new <img>
// that should be click-to-enlarge.
//
// Images are bound at DOMContentLoaded even though several of them get their
// `src` filled in later by other scripts (live model plots) - that's fine,
// we only read `.src`/`.naturalWidth` at click/open time, not bind time.
(function () {
    const SELECTOR = 'img.PlotFormat, img.SynopticPlot, img.lightbox-img';

    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    ready(function () {
        const images = Array.from(document.querySelectorAll(SELECTOR));
        if (images.length === 0) return;

        images.forEach((img) => {
            img.classList.add('cmw-lightbox-trigger');
            img.setAttribute('tabindex', '0');
            img.setAttribute('role', 'button');
        });

        const overlay = document.createElement('div');
        overlay.id = 'cmw-lightbox';
        overlay.setAttribute('aria-hidden', 'true');
        overlay.innerHTML = `
            <button type="button" class="cmw-lightbox-close" aria-label="Close">&times;</button>
            <button type="button" class="cmw-lightbox-prev" aria-label="Previous image">&#8249;</button>
            <img class="cmw-lightbox-img" alt="" />
            <button type="button" class="cmw-lightbox-next" aria-label="Next image">&#8250;</button>
            <p class="cmw-lightbox-caption"></p>
        `;
        document.body.appendChild(overlay);

        const lbImg = overlay.querySelector('.cmw-lightbox-img');
        const caption = overlay.querySelector('.cmw-lightbox-caption');
        const btnPrev = overlay.querySelector('.cmw-lightbox-prev');
        const btnNext = overlay.querySelector('.cmw-lightbox-next');
        const btnClose = overlay.querySelector('.cmw-lightbox-close');

        let gallery = [];
        let index = -1;

        function usable(img) {
            return !!(img.currentSrc || img.src) && img.naturalWidth > 0;
        }

        function show(i) {
            if (gallery.length === 0) return;
            index = (i + gallery.length) % gallery.length;
            const img = gallery[index];
            lbImg.src = img.currentSrc || img.src;
            lbImg.alt = img.alt || '';
            caption.textContent = img.alt || '';
            const multi = gallery.length > 1;
            btnPrev.hidden = !multi;
            btnNext.hidden = !multi;
        }

        function open(clicked) {
            // Build the gallery from every currently-loaded match on the page,
            // so "next/prev" steps through whatever plots are actually on
            // this page (posts and tool pages both have 1-N of these).
            gallery = images.filter(usable);
            const startIndex = gallery.indexOf(clicked);
            if (startIndex === -1) return; // clicked image itself isn't loaded/usable
            document.body.classList.add('cmw-lightbox-open');
            overlay.classList.add('open');
            overlay.setAttribute('aria-hidden', 'false');
            show(startIndex);
        }

        function close() {
            overlay.classList.remove('open');
            overlay.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('cmw-lightbox-open');
            lbImg.src = '';
        }

        images.forEach((img) => {
            img.addEventListener('click', () => {
                if (usable(img)) open(img);
            });
            img.addEventListener('keydown', (e) => {
                if ((e.key === 'Enter' || e.key === ' ') && usable(img)) {
                    e.preventDefault();
                    open(img);
                }
            });
        });

        btnClose.addEventListener('click', close);
        btnPrev.addEventListener('click', () => show(index - 1));
        btnNext.addEventListener('click', () => show(index + 1));

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) close();
        });

        document.addEventListener('keydown', (e) => {
            if (!overlay.classList.contains('open')) return;
            if (e.key === 'Escape') close();
            if (e.key === 'ArrowLeft') show(index - 1);
            if (e.key === 'ArrowRight') show(index + 1);
        });

        // Swipe left/right to step through the gallery on touch devices.
        let touchStartX = null;
        overlay.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].clientX;
        }, { passive: true });
        overlay.addEventListener('touchend', (e) => {
            if (touchStartX === null) return;
            const dx = e.changedTouches[0].clientX - touchStartX;
            touchStartX = null;
            if (Math.abs(dx) < 50) return;
            show(index + (dx < 0 ? 1 : -1));
        }, { passive: true });
    });
})();
