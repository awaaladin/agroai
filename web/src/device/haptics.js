// Short vibration patterns where supported (Android Chrome). Silent no-op elsewhere and when muted in Settings.
import { settings } from '../state/store.js';

const PATTERNS = { tap: 12, capture: [18, 40, 18], success: [20, 60, 20, 60, 40], error: [60, 80, 60] };

/** @param {'tap'|'capture'|'success'|'error'} kind */
export function haptic(kind) {
  if (!settings.get().haptics || !('vibrate' in navigator)) return;
  try { navigator.vibrate(PATTERNS[kind]); } catch { /* ignore */ }
}
