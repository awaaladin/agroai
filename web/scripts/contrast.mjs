// Prints WCAG contrast ratios for the palette pairs the UI uses. Run: npm run contrast
// Rule from the brief: text needs at least 7:1 (AAA). Large decorative fills may be lower but never carry text alone.
const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const P = { cream: '#F7F1E1', forest: '#0F3D2E', leaf: '#3BB273', gold: '#F2B532', terracotta: '#C8553D',
  terracottaInk: '#8F2F1B', leafInk: '#14603F', creamDark: '#EADFC3', night: '#0B1F18', nightText: '#F7F1E1' };
const pairs = [
  ['forest on cream (body text)', P.forest, P.cream], ['forest on cream-dark (cards)', P.forest, P.creamDark],
  ['cream on forest (primary button)', P.cream, P.forest], ['forest on leaf (accent fill)', P.forest, P.leaf],
  ['forest on gold (mic, highlights)', P.forest, P.gold], ['leaf-ink on cream (healthy text)', P.leafInk, P.cream],
  ['terracotta-ink on cream (warning text)', P.terracottaInk, P.cream], ['cream on terracotta-ink (warning button)', P.cream, P.terracottaInk],
  ['terracotta on cream (NOT for text)', P.terracotta, P.cream], ['leaf on cream (NOT for text)', P.leaf, P.cream],
  ['dark theme: cream on night', P.nightText, P.night], ['dark theme: leaf on night (icons/fills)', P.leaf, P.night],
  ['dark theme: gold on night', P.gold, P.night],
];
for (const [name, fg, bg] of pairs) {
  const r = ratio(fg, bg);
  console.log(`${r.toFixed(2).padStart(6)}:1  ${r >= 7 ? 'AAA ' : r >= 4.5 ? 'AA  ' : 'FAIL'}  ${name}`);
}
