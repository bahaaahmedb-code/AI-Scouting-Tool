import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 45000 })

// ── Players ──────────────────────────────────────────────────────────────────
export const getPlayers = (params = {}) =>
  api.get('/players', { params }).then(r => r.data)

export const getPlayer = (pid) =>
  api.get(`/players/${pid}`).then(r => r.data)

export const getShap = (pid, params = {}) =>
  api.get(`/players/${pid}/shap`, { params }).then(r => r.data)

// ── Explain ───────────────────────────────────────────────────────────────────
export const getGlobalImportance = (position) =>
  api.get('/explain/global', { params: position ? { position } : {} }).then(r => r.data)

export const getDependence = (feature) =>
  api.get(`/explain/dependence/${feature}`).then(r => r.data)

// ── Scout ─────────────────────────────────────────────────────────────────────
export const postScout = (params) =>
  api.get('/scout', { params }).then(r => r.data)

export const getScout = postScout

// ── Compare & Radar ───────────────────────────────────────────────────────────
export const getCompare = (ids) =>
  api.get('/compare', { params: { ids: ids.join(',') } }).then(r => r.data)

export const getRadar = (ids) =>
  api.get('/radar', { params: { ids: ids.join(',') } }).then(r => r.data)

// ── Rankings ──────────────────────────────────────────────────────────────────
export const getRankings = (params = {}) =>
  api.get('/rankings', { params }).then(r => r.data)

// ── What-if ───────────────────────────────────────────────────────────────────
export const postWhatIf = (body) =>
  api.post('/whatif', body).then(r => r.data)

// ── Chat ──────────────────────────────────────────────────────────────────────
export const postChat = (body) =>
  api.post('/chat', body).then(r => r.data)

export const getGeminiStatus = () =>
  api.get('/chat/gemini-status').then(r => r.data)

export const postGeminiKey = (body) =>
  api.post('/chat/gemini-key', body).then(r => r.data)

// ── Meta / health ─────────────────────────────────────────────────────────────
export const getMeta = () =>
  api.get('/meta').then(r => r.data)

export const getHealth = () =>
  api.get('/health').then(r => r.data)

export const getGlossary = () =>
  api.get('/glossary').then(r => r.data)

// ── Eval ──────────────────────────────────────────────────────────────────────
export const evalLogin = (code) =>
  api.post('/eval/login', {}, { headers: { 'x-access-code': code } }).then(r => r.data)

export const postRatings = (body, code) =>
  api.post('/eval/ratings', body, { headers: { 'x-access-code': code } }).then(r => r.data)

export const postTask = (body, code) =>
  api.post('/eval/tasks', body, { headers: { 'x-access-code': code } }).then(r => r.data)

export const postSus = (body, code) =>
  api.post('/eval/sus', body, { headers: { 'x-access-code': code } }).then(r => r.data)

export const getEvalSummary = (code) =>
  api.get('/eval/summary', { headers: { 'x-access-code': code } }).then(r => r.data)

export default api
