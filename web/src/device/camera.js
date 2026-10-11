// Camera: rear-camera preview, capture, and on-device compression. Re-encoding through a canvas also strips
// EXIF and GPS data, so the location of a photo never leaves the phone. Wake Lock keeps the screen on while open.

let stream = null;
let wake = null;

export const cameraSupported = () => !!navigator.mediaDevices?.getUserMedia;

/** Start the rear camera in a <video>. Rejects with an Error whose name is NotAllowedError, NotFoundError... */
export async function startCamera(video) {
  stopCamera();
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    audio: false,
  });
  video.srcObject = stream;
  video.setAttribute('playsinline', '');
  video.muted = true;
  await video.play().catch(() => {});
  try { wake = await navigator.wakeLock?.request('screen'); } catch { /* not supported or refused: fine */ }
  return stream;
}

export function stopCamera() {
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  wake?.release?.().catch(() => {});
  wake = null;
}

/** Longest side 1280 px, JPEG quality 0.85. Honours EXIF orientation, then drops all metadata. */
export async function compress(source, { maxSide = 1280, quality = 0.85 } = {}) {
  let bitmap;
  if (source instanceof HTMLVideoElement) {
    bitmap = { width: source.videoWidth, height: source.videoHeight, draw: (ctx, w, h) => ctx.drawImage(source, 0, 0, w, h), close() {} };
  } else {
    let bmp;
    try { bmp = await createImageBitmap(source, { imageOrientation: 'from-image' }); }
    catch { bmp = await createImageBitmap(source); }
    bitmap = { width: bmp.width, height: bmp.height, draw: (ctx, w, h) => ctx.drawImage(bmp, 0, 0, w, h), close: () => bmp.close?.() };
  }
  if (!bitmap.width || !bitmap.height) throw new Error('empty image');
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  bitmap.draw(canvas.getContext('2d'), w, h);
  bitmap.close();
  const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', quality));
  if (!blob) throw new Error('could not encode image');
  return { blob, width: w, height: h };
}
