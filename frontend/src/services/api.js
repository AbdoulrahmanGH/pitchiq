import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8001' });

export const getTeamReadiness    = () => api.get('/api/team/readiness').then(r => r.data);
export const getPlayerPerformance = () => api.get('/api/players/performance').then(r => r.data);
export const getFatigueRisk      = () => api.get('/api/players/fatigue-risk').then(r => r.data);
export const getSquadDepth       = () => api.get('/api/players/depth').then(r => r.data);
export const getMatchesSummary   = () => api.get('/api/matches/summary').then(r => r.data);
