// Présentation autonome : tous les modules fonctionnent en démonstration locale.
views.riverains=views.resident=function(){integratedAppTab='accueil';return views.application()};
const standaloneRender=render;render=function(){standaloneRender();document.querySelectorAll('a[href="/cercle-demo/"]').forEach(a=>{if(a.classList.contains('private-header-link')){a.href='#application';a.textContent='L’application'}else if(a.closest('#nav')){a.textContent='◎ Application riverains · démo'}})};render();
