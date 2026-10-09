// Finds sentences the CMS assembles — template literals and strings joined
// with `+` — and turns each into the regex its output must match.
const CJK = /[一-鿿]/;
function stripComments(source) {
  return source.replace(/\{\/\*[\s\S]*?\*\/\}/g, '').replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '))
    .replace(/^\s*\/\/.*$/gm, '');
}
function readQuoted(src, i) {            // src[i] is ' or "
  const q = src[i]; let j = i + 1, text = '';
  for (; j < src.length; j++) {
    if (src[j] === '\\') { text += src[j] + src[j + 1]; j++; continue; }
    if (src[j] === q) return { end: j + 1, parts: [{ lit: text }] };
    if (src[j] === '\n') return null;
    text += src[j];
  }
  return null;
}
function readExpr(src, i, found) {       // i is just past `${`; returns index past the closing }
  let depth = 1, j = i;
  for (; j < src.length; j++) {
    const c = src[j];
    if (c === '\'' || c === '"') { const q = readQuoted(src, j); if (q) { j = q.end - 1; } continue; }
    if (c === '`') { const t = readTemplate(src, j, found); j = t.end - 1; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (!depth) return j + 1; }
  }
  return j;
}
function readTemplate(src, i, found) {   // src[i] is `
  let j = i + 1, lit = ''; const parts = [];
  for (; j < src.length; j++) {
    const c = src[j];
    if (c === '\\') { lit += c + src[j + 1]; j++; continue; }
    if (c === '`') break;
    if (c === '$' && src[j + 1] === '{') {
      const end = readExpr(src, j + 2, found);
      parts.push({ lit }); lit = '';
      parts.push({ expr: src.slice(j + 2, end - 1).trim() });
      j = end - 1; continue;
    }
    lit += c;
  }
  parts.push({ lit });
  const node = { start: i, end: j + 1, parts };
  if (found) found.push(node);
  return node;
}
function unescapeLit(lit) { return lit.replace(/\\n/g, '\n').replace(/\\(['"`$\\])/g, '$1'); }
function toRegex(parts) {
  const esc = s => s.replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&');
  let body = '', holes = 0; const exprs = [];
  parts.forEach((p, k) => {
    if (p.expr !== undefined) { holes++; exprs.push(p.expr); body += k === parts.length - 1 ? '([\\s\\S]*)' : '([\\s\\S]*?)'; }
    else body += unescapeLit(p.lit).split(/(\s+)/).map(t => /^\s+$/.test(t) ? '\\s*' : esc(t)).join('');
  });
  body = body.replace(/^(\\s\*)+/, '').replace(/(\\s\*)+$/, '');
  return { source: `^${body}$`, holes, exprs };
}
function sample(parts, fill) {
  let n = 0;
  return parts.map(p => p.expr !== undefined ? fill(n++) : unescapeLit(p.lit)).join('').trim();
}
function extract(source) {
  const src = stripComments(source); const sentences = []; const seen = new Set();
  const lineOf = i => src.slice(0, i).split('\n').length;
  // templates, nested ones included
  const all = [];
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === '`') { const t = readTemplate(src, i, all); i = t.end - 1; }
  }
  // chains joined with +
  const starts = new Map(all.map(t => [t.start, t]));
  const chainNext = (end) => { const m = /^\s*\+\s*/.exec(src.slice(end, end + 200)); return m ? end + m[0].length : -1; };
  const consumed = new Set();
  for (const t of all.slice().sort((a, b) => a.start - b.start)) {
    if (consumed.has(t.start)) continue;
    let parts = t.parts.slice(), end = t.end, chained = false;
    for (;;) {
      const next = chainNext(end); if (next < 0) break;
      if (src[next] === '`' && starts.has(next)) { const u = starts.get(next); consumed.add(u.start); parts = parts.concat(u.parts); end = u.end; chained = true; continue; }
      if (src[next] === '\'' || src[next] === '"') { const q = readQuoted(src, next); if (!q) break; parts = parts.concat(q.parts); end = q.end; chained = true; continue; }
      break;
    }
    // merge adjacent literals
    const merged = [];
    for (const p of parts) { if (p.lit !== undefined && merged.length && merged[merged.length - 1].lit !== undefined) merged[merged.length - 1].lit += p.lit; else merged.push({ ...p }); }
    const literal = merged.filter(p => p.lit !== undefined).map(p => p.lit).join('');
    if (!CJK.test(literal)) continue;
    if (!merged.some(p => p.expr !== undefined)) continue;      // no hole: a static string, covered elsewhere
    const rx = toRegex(merged);
    if (seen.has(rx.source)) continue; seen.add(rx.source);
    sentences.push({ line: lineOf(t.start), source: src.slice(t.start, end).slice(0, 600), parts: merged, regex: rx.source, exprs: rx.exprs });
  }
  return sentences;
}
module.exports = { extract, sample, CJK };
