// Finds sentences the CMS assembles — template literals, and strings joined
// with `+` to each other or to a variable — and turns each into the regex its
// output must match.
const CJK = /[一-鿿]/;
// Removes comments without mistaking the inside of a string for one.
//
// The first version was three regexes, and `accept="image/*"` opened a comment
// that ran to the next `*/` — sometimes two hundred lines later. Everything in
// between was invisible to both coverage tests, which then passed on screens
// that were half Chinese (the Settings page, found by clicking through it).
// So: walk the text, step over strings and templates, and only then look for
// `/*` and `//`. Newlines are kept so line numbers still mean something.
function stripComments(source) {
  let out = ''; const n = source.length;
  const blank = text => text.replace(/[^\n]/g, ' ');
  for (let i = 0; i < n; i++) {
    const c = source[i], d = source[i + 1];
    if (c === '\'' || c === '"') {
      // A quote with no partner on its own line is an apostrophe in JSX text.
      let j = i + 1;
      while (j < n && source[j] !== c && source[j] !== '\n') j += source[j] === '\\' ? 2 : 1;
      if (source[j] === c) { out += source.slice(i, j + 1); i = j; } else out += c;
      continue;
    }
    if (c === '`') {
      let j = i + 1, depth = 0;
      for (; j < n; j++) {
        if (source[j] === '\\') { j++; continue; }
        if (source[j] === '$' && source[j + 1] === '{') { depth++; j++; continue; }
        if (depth && source[j] === '}') { depth--; continue; }
        if (!depth && source[j] === '`') break;
      }
      out += source.slice(i, j + 1); i = j; continue;
    }
    if (c === '/' && d === '*') {
      const end = source.indexOf('*/', i + 2); const stop = end < 0 ? n : end + 2;
      out += blank(source.slice(i, stop)); i = stop - 1; continue;
    }
    if (c === '/' && d === '/' && /(^|[\s;{}(),])$/.test(source.slice(Math.max(0, i - 1), i))) {
      let j = source.indexOf('\n', i); if (j < 0) j = n;
      out += blank(source.slice(i, j)); i = j - 1; continue;
    }
    out += c;
  }
  return out.replace(/\{\s*\}/g, m => m.replace(/[{}]/g, ' '));   // what `{/* … */}` leaves behind
}
// Every quoted string literal, including the ones inside a template's `${…}`.
//
// Pairing quotes with a regex goes out of step after `lines.join('\n')`: the
// escaped newline is not a string to the regex, so the next quote it meets is
// taken as an opening one and every string after it on the line is read
// inside-out. `'日报已复制到剪贴板'` was missed that way.
function quotedStrings(source) {
  const src = stripComments(source); const found = []; const n = src.length;
  const code = (i, untilBrace) => {              // returns the index it stopped at
    let depth = 0;
    for (; i < n; i++) {
      const c = src[i];
      if (c === '\'' || c === '"') {
        let j = i + 1, text = '';
        while (j < n && src[j] !== c && src[j] !== '\n') { if (src[j] === '\\') { text += src[j] + (src[j + 1] || ''); j += 2; } else text += src[j++]; }
        if (src[j] === c) { found.push(text); i = j; }
        continue;
      }
      if (c === '`') { i = template(i); continue; }
      if (untilBrace) { if (c === '{') depth++; else if (c === '}') { if (!depth) return i; depth--; } }
    }
    return i;
  };
  const template = (i) => {                      // src[i] is `; returns the index of the closing one
    for (i++; i < n; i++) {
      if (src[i] === '\\') { i++; continue; }
      if (src[i] === '`') return i;
      if (src[i] === '$' && src[i + 1] === '{') i = code(i + 2, true);
    }
    return i;
  };
  code(0, false);
  return found;
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
// A non-string operand in a `+` chain: `(a || b)`, `s.name`, `fmt(x)`.
// Returns the index just past it, or -1 when what follows is not one.
function readOperand(src, i) {
  let j = i;
  const skipGroup = (open, close) => {
    let depth = 0;
    for (; j < src.length; j++) {
      const c = src[j];
      if (c === '\'' || c === '"') { const q = readQuoted(src, j); if (q) j = q.end - 1; continue; }
      if (c === '`') { j = readTemplate(src, j).end - 1; continue; }
      if (c === open) depth++;
      else if (c === close) { depth--; if (!depth) { j++; return true; } }
    }
    return false;
  };
  if (src[j] === '(') { if (!skipGroup('(', ')')) return -1; }
  else { const m = /^[\w$][\w$.?]*/.exec(src.slice(j, j + 120)); if (!m) return -1; j += m[0].length; }
  for (;;) {
    if (src[j] === '(') { if (!skipGroup('(', ')')) return -1; }
    else if (src[j] === '[') { if (!skipGroup('[', ']')) return -1; }
    else if (src[j] === '.' || (src[j] === '?' && src[j + 1] === '.')) { const m = /^\??\.[\w$]+/.exec(src.slice(j, j + 80)); if (!m) break; j += m[0].length; }
    else break;
  }
  return j;
}

function extract(source) {
  const src = stripComments(source); const sentences = []; const seen = new Set();
  const lineOf = i => src.slice(0, i).split('\n').length;
  // Every template, nested ones included, and every quoted string outside one.
  const templates = [];
  const tokens = new Map();                 // start index -> { end, parts }
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === '`') { const t = readTemplate(src, i, templates); i = t.end - 1; }
  }
  for (const t of templates) tokens.set(t.start, t);
  const insideTemplate = i => templates.some(t => t.start < i && i < t.end);
  for (const m of src.matchAll(/(['"])((?:(?!\1)[^\\\n]|\\.){1,300})\1/g)) {
    if (!CJK.test(m[2]) || insideTemplate(m.index)) continue;
    tokens.set(m.index, { start: m.index, end: m.index + m[0].length, parts: [{ lit: m[2] }], quoted: true });
  }
  const plus = (end) => { const m = /^\s*\+\s*/.exec(src.slice(end, end + 200)); return m ? end + m[0].length : -1; };
  const consumed = new Set();
  for (const t of [...tokens.values()].sort((a, b) => a.start - b.start)) {
    if (consumed.has(t.start)) continue;
    let parts = t.parts.slice(), end = t.end;
    // `name + ' 已签到'`: the operand in front of the first string is a hole too.
    const before = src.slice(Math.max(0, t.start - 160), t.start);
    if (/[\w$\])]\s*\+\s*$/.test(before) && !/['"`]\s*\+\s*$/.test(before)) parts.unshift({ expr: 'operand before' });
    for (;;) {
      const next = plus(end); if (next < 0) break;
      const token = tokens.get(next);
      if (token) { consumed.add(token.start); parts = parts.concat(token.parts); end = token.end; continue; }
      if (src[next] === '\'' || src[next] === '"') { const q = readQuoted(src, next); if (!q) break; parts = parts.concat(q.parts); end = q.end; continue; }
      const stop = readOperand(src, next); if (stop < 0) break;
      parts.push({ expr: src.slice(next, stop).trim() }); end = stop;
    }
    const merged = [];
    for (const p of parts) { if (p.lit !== undefined && merged.length && merged[merged.length - 1].lit !== undefined) merged[merged.length - 1].lit += p.lit; else merged.push({ ...p }); }
    const literal = merged.filter(p => p.lit !== undefined).map(p => p.lit).join('');
    if (!CJK.test(literal)) continue;
    if (/^\s*<!doctype/i.test(literal)) continue;                 // the family report, written as a whole document
    if (!merged.some(p => p.expr !== undefined)) continue;      // no hole: a static string, covered elsewhere
    const rx = toRegex(merged);
    if (seen.has(rx.source)) continue; seen.add(rx.source);
    sentences.push({ line: lineOf(t.start), source: src.slice(Math.max(0, t.start - (merged[0].expr !== undefined ? 40 : 0)), end).slice(0, 600), parts: merged, regex: rx.source, exprs: rx.exprs });
  }
  return sentences;
}
module.exports = { extract, sample, stripComments, quotedStrings, CJK };
