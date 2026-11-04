export const housingTabs=[['vue','Vue d’ensemble'],['ressources','Eau & énergie'],['equipements','Équipements'],['entretien','Entretien & demandes'],['documents','Documents']] as const;
export const equipmentCategories=['Eau','Solaire','Électricité','Wi-Fi','Cuisine','Confort','Autre'];
export const equipmentStatuses=['À vérifier','Opérationnel','À entretenir','Hors service'];
export const requestStages=['ouvert','en_cours','resolu','annule'];
export const requestLabels:Record<string,string>={ouvert:'Ouverte',en_cours:'En cours',resolu:'Résolue',annule:'Annulée'};
export const homeConcepts=[{id:'M01',containers:'C01 · C02',name:'Maison riveraine 01',use:'Résidence · non proposée à la location'},{id:'M02',containers:'C03 · C04',name:'Maison riveraine 02',use:'Résidence · non proposée à la location'},{id:'M03',containers:'C05 · C06',name:'Maison riveraine 03',use:'Résidence · non proposée à la location'},{id:'M04',containers:'C07 · C08',name:'Les deux suites containers',use:'Deux suites indépendantes · scénario locatif'},{id:'M05',containers:'C09 · C10',name:'Maison en L du Domaine',use:'Maison en L · scénario locatif'}];
