// Soft ripple on every big button: one delegated listener, so it works for buttons added later too.
export function installRipple(root = document) {
  root.addEventListener('pointerdown', (e) => {
    const b = e.target.closest?.('.btn, .seed-card');
    if (!b || b.disabled) return;
    const r = b.getBoundingClientRect();
    const size = Math.max(r.width, r.height) * 2;
    const s = document.createElement('span');
    s.className = 'ripple';
    s.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
    if (getComputedStyle(b).position === 'static') b.style.position = 'relative';
    b.style.overflow = 'hidden';
    b.append(s);
    s.addEventListener('animationend', () => s.remove(), { once: true });
  }, { passive: true });
}
