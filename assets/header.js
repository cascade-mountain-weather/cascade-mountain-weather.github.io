// Shared header behavior: click/tap toggle for dropdown, hover keep-open, outside click and Escape to close
(function(){
  try{
    const dropdownToggle = document.querySelector('.nav-item.dropdown > .dropdown-toggle');
    if(!dropdownToggle) return;
    const dropdown = dropdownToggle.closest('.nav-item.dropdown');
    let leaveTimer = null;

    // Toggle on click/tap
    dropdownToggle.addEventListener('click', function(e){
      e.preventDefault();
      dropdown.classList.toggle('open');
    });

    // Keep open while mouse is over; delay closing so small pointer gaps don't hide the menu
    dropdown.addEventListener('mouseenter', function(){
      clearTimeout(leaveTimer);
      dropdown.classList.add('open');
    });
    dropdown.addEventListener('mouseleave', function(){
      clearTimeout(leaveTimer);
      leaveTimer = setTimeout(function(){ dropdown.classList.remove('open'); }, 200);
    });

    // Close when clicking outside
    document.addEventListener('click', function(e){
      if(!dropdown.contains(e.target)) dropdown.classList.remove('open');
    });

    // Close on Escape
    document.addEventListener('keydown', function(e){ if(e.key === 'Escape') dropdown.classList.remove('open'); });
  }catch(err){ console.warn('header behavior error', err); }

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
    const repoBase = '/' + 'Cascski-Alpine-Insights' + '/';
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
})();