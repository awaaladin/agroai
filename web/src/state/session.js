// What the current visit is working on, shared between screens (photo -> analyzing -> result -> chat).
// Memory only, plus the session id in sessionStorage so "Ask about this" and a reload keep the conversation.
const KEY = 'agroai.sessionId';

export const work = {
  photoUrl: '',      // object URL of the compressed photo (memory only, revoked when replaced)
  photoBlob: null,
  crop: '',          // crop key chosen by the farmer, or ''
  symptoms: '',
  result: null,      // Diagnosis from /v1/diagnose
  savedId: '',       // set when the result is an account's saved check
  savedAt: '',
};

export function setPhoto(blob) {
  if (work.photoUrl) URL.revokeObjectURL(work.photoUrl);
  work.photoBlob = blob;
  work.photoUrl = blob ? URL.createObjectURL(blob) : '';
}

export function clearWork() {
  setPhoto(null);
  work.crop = ''; work.symptoms = ''; work.result = null; work.savedId = ''; work.savedAt = '';
}

// The visible chat thread. Kept in sessionStorage so switching language (which re-draws the page), a reload, or
// coming back from another screen shows the same conversation instead of an empty one.
const CHAT_KEY = 'agroai.chatLog';
const CHAT_MAX = 60;
/** @returns {{who:'you'|'advisor', text:string}[]} */
export const getChatLog = () => { try { return JSON.parse(sessionStorage.getItem(CHAT_KEY) || '[]'); } catch { return []; } };
export const setChatLog = (log) => {
  try { sessionStorage.setItem(CHAT_KEY, JSON.stringify(log.slice(-CHAT_MAX))); } catch { /* ignore */ }
};
export const pushChat = (who, text) => setChatLog([...getChatLog(), { who, text }]);
export const clearChat = () => { try { sessionStorage.removeItem(CHAT_KEY); } catch { /* ignore */ } };

export const getSessionId =() => { try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; } };
export const setSessionId = (id) => { try { id ? sessionStorage.setItem(KEY, id) : sessionStorage.removeItem(KEY); } catch { /* ignore */ } };
