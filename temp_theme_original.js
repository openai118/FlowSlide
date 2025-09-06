/* FlowSlide unified theme handling */
(function(){
  if(window.FlowSlideTheme) return; // idempotent
  var mql = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
  function effective(){
    var saved=null; try{ saved=localStorage.getItem('fs-theme'); }catch(e){}
    if(saved==='github'|| saved==='dark') return saved;
    return (mql && mql.matches)?'dark':'github';
  }
  function apply(theme){
    try {
      document.documentElement.classList.remove('theme-github','theme-dark');
      if(theme==='dark') document.documentElement.classList.add('theme-dark');
      else document.documentElement.classList.add('theme-github');
      var ico=document.getElementById('site-favicon');
      if(ico){ ico.href = (theme==='dark')? '/static/images/flowslide-logo-dark.svg':'/static/images/flowslide-logo-light.svg'; }
      var bl=document.getElementById('brand-logo');
      if(bl){ bl.src = (theme==='dark')? '/static/images/flowslide-logo-dark.svg':'/static/images/flowslide-logo-light.svg'; }
      var toggle=document.getElementById('theme-toggle');
      if(toggle){
         var i=toggle.querySelector('i');
         if(i){ i.className = (theme==='dark')? 'fas fa-moon':'fas fa-sun'; }
      }
    } catch(e){}
  }
  function refresh(){ apply(effective()); }
  function toggle(){
    var cur=effective();
    var next=(cur==='dark')? 'github':'dark';
    try{ localStorage.setItem('fs-theme', next); }catch(e){}
    refresh();
  }
  if(mql && mql.addEventListener){
    mql.addEventListener('change', function(){
      var saved=null; try{ saved=localStorage.getItem('fs-theme'); }catch(e){}
      if(!saved) refresh();
    });
  } else if(mql && mql.addListener){
    mql.addListener(function(){
      var saved=null; try{ saved=localStorage.getItem('fs-theme'); }catch(e){}
      if(!saved) refresh();
    });
  }
  document.addEventListener('DOMContentLoaded', function(){
    var btn=document.getElementById('theme-toggle');
    if(btn && !btn.__FS_BOUND){ btn.__FS_BOUND=true; btn.addEventListener('click', toggle); }
    refresh();
    // Front-end wording normalization: replace visible 'PPT' with 'Slide' (but keep PPTX)
    try {
      var walker=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
      var nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(function(n){
        var t=n.nodeValue;
        if(!t) return;
        if(t.indexOf('PPT')===-1) return;
        // Skip if parent is SCRIPT/STYLE or inside an attribute-like template
        var p=n.parentElement; if(p && (/SCRIPT|STYLE/.test(p.tagName))) return;
        // Replace PPT not followed by X
        var replaced=t.replace(/PPT(?!X)/g,'Slide');
        if(replaced!==t) n.nodeValue=replaced;
      });
    } catch(e){}
  });
  // Early apply (may run before DOMContentLoaded)
  apply(effective());
  window.FlowSlideTheme={apply:apply, refresh:refresh, toggle:toggle, effective:effective};
})();
