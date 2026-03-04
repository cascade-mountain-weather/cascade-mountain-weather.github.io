// Shared header behavior: click/tap toggle for dropdown, hover keep-open, outside click and Escape to close
(function(){
  try{
    const dropdownToggle = document.querySelector('.nav-item.dropdown > .dropdown-toggle');
    if(!dropdownToggle) return;
    const dropdown = dropdownToggle.closest('.nav-item.dropdown');
    let leaveTimer = null;

    // Toggle on click/tap: one press to open, one press to close
    dropdownToggle.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();           // ADD THIS LINE
      const isOpen = dropdown.classList.toggle('open');
      dropdownToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    // Close when clicking outside (ignore clicks on the toggle itself)
    document.addEventListener('click', function(e){
      if(dropdownToggle.contains(e.target)) return;
      if(!dropdown.contains(e.target)){
        dropdown.classList.remove('open');
        dropdownToggle.setAttribute('aria-expanded','false');
      }
    });

    // Close on Escape
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape'){
        dropdown.classList.remove('open');
        dropdownToggle.setAttribute('aria-expanded','false');
      }
    });
  }catch(err){ console.warn('header behavior error', err); }

  // Mobile nav hamburger toggle
  try{
    const nav = document.querySelector('nav');
    const toggle = document.querySelector('.nav-toggle');
    if(nav && toggle){
      const primaryNav = document.getElementById('primary-nav');
      toggle.addEventListener('click', function(){
        const isOpen = nav.classList.toggle('open');
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });

      // Close menu when clicking outside on small screens
      document.addEventListener('click', function(e){
        if(!nav.contains(e.target) && nav.classList.contains('open')){
          nav.classList.remove('open');
          toggle.setAttribute('aria-expanded','false');
        }
      });

      // Close on Escape
      document.addEventListener('keydown', function(e){
        if(e.key === 'Escape' && nav.classList.contains('open')){
          nav.classList.remove('open');
          toggle.setAttribute('aria-expanded','false');
        }
      });

      // Hide hamburger when scrolling past header
      let lastScroll = 0;
      window.addEventListener('scroll', function(){
        const header = document.querySelector('header');
        if(!header) return;
        const headerHeight = header.offsetHeight;
        const currentScroll = window.pageYOffset || document.documentElement.scrollTop;
        
        if(currentScroll > headerHeight) {
          toggle.classList.add('scrolled');
          // Close menu if it's open when hiding hamburger
          if(nav.classList.contains('open')){
            nav.classList.remove('open');
            toggle.setAttribute('aria-expanded','false');
          }
        } else {
          toggle.classList.remove('scrolled');
        }
        lastScroll = currentScroll;
      });
    }
  }catch(err){ console.warn('nav toggle error', err); }

  // Also attempt to resolve the latest forecast link and update any nav links
  (async function updateLatestNav(){
    // Candidate relative paths to latest-post-summary.html from different page depths
    const candidates = ['posts/latest-post-summary.html','../posts/latest-post-summary.html','../../posts/latest-post-summary.html'];
    let summaryText = null;
    for(const p of candidates){
      try{
        const res = await fetch(p);
        if(!res || !res.ok) continue;
        summaryText = await res.text();
        break;
      }catch(e){ /* try next */ }
    }
    let latestHref = '';
    if(summaryText){
      try{
        const scriptMatch = summaryText.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
        if(scriptMatch){ try{ (new Function(scriptMatch[1]))(); }catch(e){} }
        const temp = document.createElement('div'); temp.innerHTML = summaryText;
        latestHref = (typeof post_href !== 'undefined' && post_href) ? post_href : (temp.querySelector('#post-href')?.getAttribute('href')|| '');
      }catch(e){}
    }

    // If we didn't get a summary href, try probing recent dates (simple fallback)
    if(!latestHref){
      try{
        const today = new Date();
        for(let i=0;i<90;i++){
          const d = new Date(); d.setDate(today.getDate()-i);
          const yyyy = d.getFullYear();
          const mm = String(d.getMonth()+1).padStart(2,'0');
          const dd = String(d.getDate()).padStart(2,'0');
          const candidate = `posts/${yyyy}-${mm}-${dd}-weekend-forecast.html`;
          try{ const r = await fetch(candidate,{method:'HEAD'}); if(r && r.ok){ latestHref = candidate; break; } }
          catch(e){}
        }
      }catch(e){}
    }

    if(!latestHref) return; // nothing to update

    // Compute an absolute URL for the site repo so links work from any page.
    // Adjust the repository base if you host under a different path.
    const repoBase = '/' + 'cascade-mountain-weather.github.io' + '/';
    const absolute = window.location.origin + repoBase + latestHref.replace(/^\/+/, '');

    // Update nav anchors that point to the index anchor for latest-post
    const anchors = Array.from(document.querySelectorAll('a')).filter(a => {
      const h = a.getAttribute('href') || '';
      return h.endsWith('#latest-post') || h === '#latest-post' || /latest-post/i.test(a.textContent);
    });
    for(const a of anchors){
      a.href = absolute;
    }
  })();

  // Infinite-scroll older forecasts on dated post pages
  (function initInfiniteForecastScroll(){
    try{
      const path = window.location.pathname;
      const match = path.match(/\/(\d{4})-(\d{2})-(\d{2})-weekend-forecast\.html$/);
      if(!match) return;

      const main = document.querySelector('main');
      const firstPost = main ? main.querySelector('article.post') : null;
      if(!main || !firstPost) return;

      const startDate = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
      const loaded = new Set();
      loaded.add(`${match[1]}-${match[2]}-${match[3]}-weekend-forecast.html`);

      let cursorDate = new Date(startDate);
      let isLoading = false;
      let isExhausted = false;

      const feed = document.createElement('div');
      feed.id = 'infinite-forecast-feed';
      main.appendChild(feed);

      const sentinel = document.createElement('div');
      sentinel.id = 'infinite-forecast-sentinel';
      sentinel.textContent = 'Scroll for older forecasts';
      main.appendChild(sentinel);

      function formatDateForPath(dateObj){
        const yyyy = dateObj.getFullYear();
        const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
        const dd = String(dateObj.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}-weekend-forecast.html`;
      }

      async function postExists(href){
        try{
          const headRes = await fetch(href, { method: 'HEAD' });
          if(headRes && headRes.ok) return true;
        }catch(e){}

        try{
          const getRes = await fetch(href);
          return !!(getRes && getRes.ok);
        }catch(e){
          return false;
        }
      }

      async function findNextOlder(maxLookbackDays = 730){
        const probeDate = new Date(cursorDate);

        for(let i = 0; i < maxLookbackDays; i++){
          probeDate.setDate(probeDate.getDate() - 1);
          const fileName = formatDateForPath(probeDate);
          if(loaded.has(fileName)) continue;

          const href = `../posts/${fileName}`;
          if(await postExists(href)){
            return { href, fileName, dateObj: new Date(probeDate) };
          }
        }

        return null;
      }

      async function loadNextOlderPost(){
        if(isLoading || isExhausted) return;
        isLoading = true;
        sentinel.textContent = 'Loading older forecast…';

        try{
          const found = await findNextOlder();
          if(!found){
            isExhausted = true;
            sentinel.textContent = 'No older forecasts found';
            return;
          }

          const res = await fetch(found.href);
          if(!res.ok){
            cursorDate = found.dateObj;
            sentinel.textContent = 'Could not load older forecast';
            return;
          }

          const html = await res.text();
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const article = doc.querySelector('main article.post') || doc.querySelector('article.post');

          if(!article){
            cursorDate = found.dateObj;
            loaded.add(found.fileName);
            sentinel.textContent = 'Scroll for older forecasts';
            return;
          }

          const imported = document.importNode(article, true);
          imported.classList.add('loaded-post');

          feed.appendChild(imported);
          loaded.add(found.fileName);
          cursorDate = found.dateObj;
          sentinel.textContent = 'Scroll for older forecasts';
        }catch(err){
          sentinel.textContent = 'Error loading older forecast';
          console.warn('infinite forecast scroll error', err);
        }finally{
          isLoading = false;
        }
      }

      const observer = new IntersectionObserver((entries) => {
        for(const entry of entries){
          if(entry.isIntersecting) loadNextOlderPost();
        }
      }, {
        root: null,
        rootMargin: '0px 0px 900px 0px',
        threshold: 0
      });

      observer.observe(sentinel);
    }catch(err){
      console.warn('init infinite forecast scroll error', err);
    }
  })();
})();