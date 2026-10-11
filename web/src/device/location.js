// Coarse farm location. Two sources: the browser's geolocation (rounded to 2 decimals, about 1 km, before it is
// stored or sent anywhere) or a town picked by hand. Every failure falls back to the town picker.
import { settings } from '../state/store.js';

// Approximate town-centre coordinates for Akwa Ibom (good enough for a 5-day weather forecast).
export const TOWNS = [
  { name: 'Uyo', lat: 5.04, lon: 7.93 }, { name: 'Eket', lat: 4.64, lon: 7.92 }, { name: 'Ikot Ekpene', lat: 5.18, lon: 7.71 },
  { name: 'Oron', lat: 4.81, lon: 8.24 }, { name: 'Etinan', lat: 4.85, lon: 7.86 }, { name: 'Abak', lat: 4.99, lon: 7.78 },
  { name: 'Itu', lat: 5.17, lon: 7.98 }, { name: 'Ikot Abasi', lat: 4.57, lon: 7.57 }, { name: 'Mkpat Enin', lat: 4.78, lon: 7.72 },
  { name: 'Ikono', lat: 5.2, lon: 7.82 },
];

const round2 = (n) => Math.round(n * 100) / 100;

/** Ask the browser for a coarse position. Resolves {lat, lon} or rejects with 'denied' | 'unavailable' | 'timeout'. */
export function detect({ timeout = 10_000 } = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('unavailable'));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: round2(p.coords.latitude), lon: round2(p.coords.longitude) }),
      (e) => reject(new Error(e.code === 1 ? 'denied' : e.code === 3 ? 'timeout' : 'unavailable')),
      { enableHighAccuracy: false, timeout, maximumAge: 10 * 60_000 },
    );
  });
}

export function saveGps({ lat, lon }) { settings.set({ lat, lon, locationSource: 'gps', town: '' }); }
export function saveTown(town) { settings.set({ lat: town.lat, lon: town.lon, locationSource: 'town', town: town.name }); }

/** The saved location, or null when the farmer has not given one. */
export function getLocation() {
  const { lat, lon, town, locationSource } = settings.get();
  return lat == null || lon == null ? null : { lat, lon, town, source: locationSource };
}
