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

      // The hamburger stays on screen at any scroll position and the open menu is fixed to the screen,
      // so scrolling no longer closes it (that left the button and menu out of step).
    }
  }catch(err){ console.warn('nav toggle error', err); }

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