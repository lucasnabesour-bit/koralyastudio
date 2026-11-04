import React from 'react';
import {createRoot} from 'react-dom/client';
import ResidentApp from './app/riverains/resident-app';
import type {Tab} from './app/riverains/resident-app';
import {demoMember} from './app/riverains/demo-data';
import './app/globals.css';
const q=new URLSearchParams(location.search),embedded=q.get('integre')==='1',tab=q.get('onglet')||'accueil';
const initialTab=(['accueil','fil','logement','espaces','decisions','activites'].includes(tab)?tab:'accueil') as Tab;
createRoot(document.getElementById('root')!).render(<>{!embedded&&<header className="private-header"><a href="/index.html">☯ <b>Domaine</b><small>YIN & YANG</small></a><div><span>L’APPLICATION DU DOMAINE</span><a href="/index.html">Retour au Domaine ↗</a></div></header>}<ResidentApp member={demoMember} demo initialTab={initialTab} embedded={embedded}/></>);
