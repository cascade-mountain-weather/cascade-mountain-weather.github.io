// Shared header behavior: click/tap toggle for dropdown, hover keep-open, outside click and Escape to close
(function(){
  try{
    // Support any number of nav dropdowns (Home, Forecast, Current Weather &
    // Observations, Model Tools, ...), not just the first one on the page.
    const dropdowns = Array.from(document.querySelectorAll('.nav-item.dropdown')).map(function(dropdown){
      return { dropdown: dropdown, toggle: dropdown.querySelector(':scope > .dropdown-toggle') };
    }).filter(function(pair){ return !!pair.toggle; });

    if(!dropdowns.length) return;

    function closeAll(except){
      dropdowns.forEach(function(pair){
        if(pair.dropdown === except) return;
        pair.dropdown.classList.remove('open');
        pair.toggle.setAttribute('aria-expanded', 'false');
      });
    }

    dropdowns.forEach(function(pair){
      const dropdown = pair.dropdown;
      const dropdownToggle = pair.toggle;

      // Toggle on click/tap: one press to open, one press to close. Opening
      // one dropdown closes any other that's currently open.
      dropdownToggle.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        const isOpen = dropdown.classList.toggle('open');
        dropdownToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        if(isOpen) closeAll(dropdown);
      });
    });

    // Close when clicking outside any dropdown (ignore clicks on a toggle itself)
    document.addEventListener('click', function(e){
      dropdowns.forEach(function(pair){
        if(pair.toggle.contains(e.target)) return;
        if(!pair.dropdown.contains(e.target)){
          pair.dropdown.classList.remove('open');
          pair.toggle.setAttribute('aria-expanded','false');
        }
      });
    });

    // Close on Escape
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape') closeAll(null);
    });
  }catch(err){ console.warn('header behavior error', err); }

  // Replace the header title text with the CMW logo across pages.
  try{
    const headerTitle = document.querySelector('header h1');
    if(headerTitle && !headerTitle.querySelector('.cmw-header-main-logo')){
      const logo = document.createElement('img');
      logo.className = 'cmw-header-main-logo';
      logo.alt = 'Cascade Mountain Weather logo';
      logo.decoding = 'async';
      logo.loading = 'eager';

      const logoCandidates = [
        'assets/images/cmw_logo.png',
        '../assets/images/cmw_logo.png',
        '../../assets/images/cmw_logo.png'
      ];
      let logoIndex = 0;
      logo.src = logoCandidates[logoIndex];
      logo.addEventListener('error', function(){
        logoIndex += 1;
        if(logoIndex < logoCandidates.length){
          logo.src = logoCandidates[logoIndex];
        }
      });

      headerTitle.textContent = '';
      headerTitle.classList.add('cmw-header-logo-wrap');
      headerTitle.appendChild(logo);
    }
  }catch(err){ console.warn('header title logo injection error', err); }

  // Once the header has scrolled out of view, show the small logo in the nav bar
  try{
    const bar = document.querySelector('nav');
    const top = document.querySelector('body > header');
    if(bar && top){
      const mark = function(){ bar.classList.toggle('scrolled', window.pageYOffset > top.offsetHeight); };
      window.addEventListener('scroll', mark, { passive: true });
      mark();
    }
  }catch(err){ console.warn('nav logo error', err); }

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

  // Add a simple UTC -> Pacific time conversion axis below Utah meteogram PNGs.
  (function injectPacificTimeAxis(){
    try{
      const targets = document.querySelectorAll('img#utah-weather-url, img#utah-rrfsqsf-url');
      if(!targets.length) return;

      targets.forEach((img) => {
        if(img.dataset.ptAxisInjected === 'true') return;

        const wrapper = document.createElement('div');
        wrapper.className = 'utah-image-wrap';
        img.parentNode.insertBefore(wrapper, img);
        wrapper.appendChild(img);
        img.dataset.ptAxisInjected = 'true';
      });
    }catch(err){
      console.warn('utc to pacific axis injection error', err);
    }
  })();
})();