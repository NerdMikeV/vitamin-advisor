// Build-time API base. Set VITE_API_BASE_URL in the Vercel project (and in a
// local .env) to the Railway backend URL; defaults to the dev backend.
const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

async function req(path, opts) {
  const res = await fetch(`${API}${path}`, opts)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const getEntities = () => req('/entities')
export const getDisclaimer = () => req('/disclaimer')
export const getResearch = (entityId) => req(`/research/${entityId}`)
export const postPlan = (survey) =>
  req('/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(survey) })
export const postCheck = (agents, profile) =>
  req('/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agents, profile }) })
