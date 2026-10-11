// The farm's location. Two sources: the browser's real GPS position (rounded to 2 decimals, about 1 km, before it is
// stored or sent to the weather service) or a town picked by hand. Every failure falls back to the town picker.
// Asking is always an explicit tap ("Use my location"): nothing reads the position in the background.
import { settings } from '../state/store.js';

// Approximate town-centre coordinates for Akwa Ibom (good enough for a 5-day weather forecast).
export const TOWNS = [
  { name: 'Uyo', lat: 5.04, lon: 7.93 }, { name: 'Eket', lat: 4.64, lon: 7.92 }, { name: 'Ikot Ekpene', lat: 5.18, lon: 7.71 },
  { name: 'Oron', lat: 4.81, lon: 8.24 }, { name: 'Etinan', lat: 4.85, lon: 7.86 }, { name: 'Abak', lat: 4.99, lon: 7.78 },
  { name: 'Itu', lat: 5.17, lon: 7.98 }, { name: 'Ikot Abasi', lat: 4.57, lon: 7.57 }, { name: 'Mkpat Enin', lat: 4.78, lon: 7.72 },
  { name: 'Ikono', lat: 5.2, lon: 7.82 },
];

const round2 = (n) => Math.round(n * 100) / 100;
const km = (a, b) => {
  const R = 6371; const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat); const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};

/**
 * Ask the browser for the device's real position (GPS where the phone has it). Resolves {lat, lon, accuracy} with
 * the coordinates already rounded, or rejects with 'denied' | 'unavailable' | 'timeout'.
 */
export function detect({ timeout = 15_000 } = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('unavailable'));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: round2(p.coords.latitude), lon: round2(p.coords.longitude), accuracy: Math.round(p.coords.accuracy || 0) }),
      (e) => reject(new Error(e.code === 1 ? 'denied' : e.code === 3 ? 'timeout' : 'unavailable')),
      // GPS, not a cached or network-guessed position: a stale fix can be a different town.
      { enableHighAccuracy: true, timeout, maximumAge: 60_000 },
    );
  });
}

/** The nearest known town within ~40 km, or null. */
export function nearestTown({ lat, lon }) {
  const best = TOWNS.map((t) => ({ t, d: km({ lat, lon }, t) })).sort((a, b) => a.d - b.d)[0];
  return best && best.d <= 40 ? best.t.name : null;
}

/**
 * A readable place name for a position ("Uyo, Akwa Ibom"). Uses a free reverse-geocoding service with the already
 * rounded coordinates; falls back to the nearest known town, then to ''. Never throws.
 */
export async function placeName({ lat, lon }) {
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 6000);
    const r = await fetch(
      `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`,
      { signal: ctl.signal },
    );
    clearTimeout(timer);
    if (r.ok) {
      const j = await r.json();
      const name = j.city || j.locality || '';
      const region = (j.principalSubdivision || '').replace(/ State$/i, '');
      const label = [name, region].filter((x, i, a) => x && a.indexOf(x) === i).join(', ');
      if (label) return label.slice(0, 60);
    }
  } catch { /* offline or blocked: use the nearest town instead */ }
  return nearestTown({ lat, lon }) || '';
}

/** Detect the real position, name the place, and save it. Resolves {lat, lon, place, accuracy}. */
export async function useMyLocation() {
  const c = await detect();
  const place = await placeName(c);
  saveGps({ lat: c.lat, lon: c.lon, place });
  return { ...c, place };
}

export function saveGps({ lat, lon, place = '' }) { settings.set({ lat, lon, locationSource: 'gps', town: place }); }
export function saveTown(town) { settings.set({ lat: town.lat, lon: town.lon, locationSource: 'town', town: town.name }); }

/** The saved location, or null when the farmer has not given one. */
export function getLocation() {
  const { lat, lon, town, locationSource } = settings.get();
  return lat == null || lon == null ? null : { lat, lon, town, source: locationSource };
}
