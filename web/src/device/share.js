// Share the officer message: Web Share API (opens WhatsApp/SMS from the share sheet) first, then a wa.me link,
// then plain copy. The text never includes the photo.

/** @returns {'shared'|'whatsapp'|'copied'|'cancelled'} */
export async function shareText(text, title = 'AgroAI Advisor') {
  if (navigator.share) {
    try { await navigator.share({ title, text }); return 'shared'; }
    catch (e) { if (e?.name === 'AbortError') return 'cancelled'; /* otherwise fall through */ }
  }
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  const win = window.open(url, '_blank', 'noopener');
  if (win) return 'whatsapp';
  try { await navigator.clipboard.writeText(text); return 'copied'; } catch { return 'cancelled'; }
}

export const whatsappLink = (text) => `https://wa.me/?text=${encodeURIComponent(text)}`;

const FALLBACK_CONF = (c) => (c >= 0.8 ? 'sure' : c >= 0.6 ? 'fairly sure' : 'not sure');

/** Officer message built on the device from a stored answer (used for saved checks and expired sessions). */
export function officerText(r, savedAt) {
  const a = r.assessment;
  const lines = ['AgroAI Advisor: crop check', `Crop: ${r.crop?.name || 'unknown'}`];
  if (savedAt) lines.push(`Date: ${new Date(savedAt).toISOString().slice(0, 10)}`);
  lines.push(`Likely problem: ${a.likely_problem} (${FALLBACK_CONF(a.confidence)}, ${Math.round(a.confidence * 100)}%)`);
  if (a.alternatives?.length) lines.push(`Other possibilities: ${a.alternatives.map((x) => x.name).join(', ')}`);
  lines.push(`What the app saw: ${a.what_i_see}`);
  if (r.escalate?.recommended && r.escalate.reason) lines.push(`Why I am sending this: ${r.escalate.reason}`);
  if (r.farmer_questions?.length) { lines.push('Questions for the officer / to check on the farm:'); r.farmer_questions.forEach((q, i) => lines.push(`${i + 1}. ${q}`)); }
  lines.push('This is an AI suggestion, not a final diagnosis. Please confirm.');
  return lines.join('\n');
}
