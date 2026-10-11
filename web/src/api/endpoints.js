// One function per backend endpoint (docs/api.md). No endpoints beyond that contract.
import { request, TIMEOUTS } from './client.js';

/**
 * @typedef {{recommended:boolean, reason:string|null}} Escalate
 * @typedef {{usable:boolean, issue:string|null, advice:string|null}} ImageQuality
 * @typedef {{name:string, confidence:number}} Guess
 * @typedef {{likely_problem:string, confidence:number, alternatives:Guess[], what_i_see:string,
 *   why_i_think_so:string, what_could_change_my_mind:string}} Assessment
 * @typedef {{step:number, what:string, when:'today'|'this_week'|'next_season', why:string}} Action
 * @typedef {{session_id:string|null, image_quality:ImageQuality, crop:Guess|null, assessment:Assessment|null,
 *   actions:Action[], prevention:string[], farmer_questions:string[], weather_note:string|null,
 *   escalate:Escalate, spoken_text:string}} Diagnosis
 * @typedef {{session_id:string, answer_text:string, spoken_text:string, follow_up_suggestions:string[],
 *   escalate:Escalate, confidence:number}} ChatReply
 * @typedef {{code:string, severity:'good'|'info'|'warning', message:string, message_pcm:string, dates:string[]}} Advice
 * @typedef {{date:string, condition_code:number, high_c:number, low_c:number, rain_chance_pct:number,
 *   rain_mm:number, wind_kph:number}} Day
 * @typedef {{lat:number, lon:number, current:{temp_c:number, condition_code:number, wind_kph:number},
 *   days:Day[], advice:Advice[]}} WeatherAdvice
 */

export const health = () => request('/v1/health', { auth: false, timeout: 8000 });

/** @param {Blob} image @param {{crop?:string, symptoms?:string, lat?:number, lon?:number, language:'en'|'pcm'}} o
 *  @returns {Promise<Diagnosis>} */
export function diagnose(image, o, signal) {
  const form = new FormData();
  form.append('image', image, 'leaf.jpg');
  form.append('language', o.language);
  if (o.crop) form.append('crop', o.crop);
  if (o.symptoms) form.append('symptoms_text', o.symptoms);
  if (o.lat != null && o.lon != null) { form.append('lat', String(o.lat)); form.append('lon', String(o.lon)); }
  return request('/v1/diagnose', { method: 'POST', form, timeout: TIMEOUTS.diagnose, signal });
}

/** @param {{message:string, language:'en'|'pcm', session_id?:string, lat?:number, lon?:number, crop?:string}} body
 *  @returns {Promise<ChatReply>} */
export const chat = (body, signal) => request('/v1/chat', { method: 'POST', json: body, timeout: TIMEOUTS.chat, signal });

/** @returns {Promise<WeatherAdvice>} */
export const weatherAdvice = (lat, lon, crop, signal) => {
  const q = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  if (crop) q.set('crop', crop);
  return request(`/v1/weather/advice?${q}`, { signal });
};

/** @returns {Promise<{session_id:string, text:string}>} */
export const shareCard = (sessionId) => request('/v1/share-card', { method: 'POST', json: { session_id: sessionId } });

export const deleteSession = (sessionId) => request(`/v1/session/${sessionId}`, { method: 'DELETE' });

/** @param {Blob} audio @returns {Promise<{text:string}>} */
export function transcribe(audio, language, signal) {
  const form = new FormData();
  form.append('audio', audio, 'voice.webm');
  form.append('language', language);
  return request('/v1/transcribe', { method: 'POST', form, signal });
}

// ---- accounts (phone number + PIN) ----
/** @typedef {{id:string, phone:string, name:string, language:'en'|'pcm', town:string, lat:number|null, lon:number|null,
 *   crops:string[], notes:string, created_at:string, checks_count:number, last_check_at:string|null}} Profile
 * @typedef {{id:string, created_at:string, crop:string, problem:string, confidence:number, escalate:boolean}} CheckSummary */

/** @returns {Promise<{access_token:string, expires_in:number, user:Profile}>} */
export const register = (body) => request('/v1/auth/register', { method: 'POST', json: body, auth: false });
export const login = (phone, pin) => request('/v1/auth/login', { method: 'POST', json: { phone, pin }, auth: false });

/** @returns {Promise<Profile>} */
export const me = () => request('/v1/me');
export const updateMe = (patch) => request('/v1/me', { method: 'PATCH', json: patch });
/** @returns {Promise<CheckSummary[]>} */
export const myChecks = (limit = 20, offset = 0) => request(`/v1/me/checks?limit=${limit}&offset=${offset}`);
/** @returns {Promise<{id:string, created_at:string, result:Diagnosis}>} */
export const myCheck = (id) => request(`/v1/me/checks/${id}`);
export const deleteMyCheck = (id) => request(`/v1/me/checks/${id}`, { method: 'DELETE' });
/** @typedef {{id:number, started_at:string, last_at:string, title:string, messages:number}} ConversationSummary */
/** @returns {Promise<ConversationSummary[]>} past conversations, newest first (accounts only) */
export const myChats = (limit = 20) => request(`/v1/me/chats?limit=${limit}`);
/** @returns {Promise<{role:'farmer'|'advisor', text:string, created_at:string}[]>} */
export const myChat = (id) => request(`/v1/me/chats/${id}`);
export const clearMyHistory =() => request('/v1/me/history', { method: 'DELETE' });
export const deleteMyAccount = () => request('/v1/me', { method: 'DELETE' });
