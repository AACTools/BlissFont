/* resolver.js — shared engine for the Bliss resolver pages (hub.html,
 * index.html's Symbol Hub tab, ruby.html). Loaded via <script src="resolver.js">
 * before use. One implementation of: asset loading, float16 decode, cosine,
 * staged label search (exact -> plural retry -> prefix), and the semantic
 * fallback (word vectors -> de-compound -> cosine over symbol vectors).
 *
 * Exposes window.Resolver. All queries run against a sql.js database handle.
 */
(function () {
  const DIM = 50;

  // float16 blob -> Float32Array (vectors are stored half-precision)
  function blobVec(blob) {
    const u16 = new Uint16Array(new Uint8Array(blob).buffer);
    const out = new Float32Array(u16.length);
    for (let i = 0; i < u16.length; i++) {
      const h = u16[i];
      const s = (h & 0x8000) ? -1 : 1, e = (h & 0x7c00) >> 10, f = h & 0x03ff;
      out[i] = e === 0 ? s * f * Math.pow(2, -24)
             : e === 0x1f ? (f ? NaN : s * Infinity)
             : s * (1 + f / 1024) * Math.pow(2, e - 15);
    }
    return out;
  }

  function cos(a, b) {
    let d = 0, na = 0, nb = 0;
    for (let k = 0; k < a.length; k++) { d += a[k] * b[k]; na += a[k] ** 2; nb += b[k] ** 2; }
    return d / (Math.sqrt(na) * Math.sqrt(nb) || 1);
  }

  const norm = (s) => s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();

  /* Staged label lookup: exact -> plural retry -> strip-plural -> shortest prefix.
   * Returns sql.js rows [key, gloss_en, pos, pua_stable, blissary_code, lang, text]. */
  function labelQuery(db, term) {
    const q = norm(term);
    if (!q) return [];
    const run = (args) => {
      const r = db.exec(
        `SELECT s.key, s.gloss_en, s.pos, s.pua_stable, s.blissary_code, l.lang, l.text
         FROM labels l JOIN symbols s ON s.key = l.symbol_key
         WHERE l.norm = ? OR l.norm LIKE ? OR l.norm LIKE ?
         ORDER BY CASE WHEN l.norm = ? THEN 0 ELSE 1 END, s.gloss_en
         LIMIT 12`, args);
      return r.length ? r[0].values : [];
    };
    let rows = run([q, q + ' %', q + '%', q]);
    if (!rows.length && /s$/.test(q) && q.length > 3) rows = run([q.replace(/e?s$/, ''), q.replace(/e?s$/, '') + ' %', q.replace(/e?s$/, '') + '%', q.replace(/e?s$/, '')]);
    return rows;
  }

  /* Semantic fallback: mean of word vectors for the query (de-compounding an
   * unknown single word as a last resort), cosine against every symbol vector.
   * Returns [key, gloss_en, pos, pua_stable, blissary_code, '', score][]. */
  function semantic(db, query) {
    const q = norm(query);
    if (!q) return null;
    const acc = new Float32Array(DIM); let n = 0;
    const addWord = (w) => {
      const r = db.exec("SELECT vec FROM word_vecs WHERE word = ?", [w]);
      if (!r.length) return false;
      const v = blobVec(r[0].values[0][0]);
      for (let d = 0; d < DIM; d++) acc[d] += v[d];
      return true;
    };
    const words = q.split(' ');
    for (const w of words) { if (addWord(w)) n++; }
    if (!n && words.length === 1 && words[0].length > 5) {
      const w = words[0];
      for (let i = 3; i <= w.length - 3; i++) {
        if (addWord(w.slice(0, i)) && addWord(w.slice(i))) { n = 2; break; }
      }
    }
    if (!n) return null;
    for (let d = 0; d < DIM; d++) acc[d] /= n;
    const rows = db.exec(
      `SELECT v.symbol_key, s.gloss_en, s.pos, s.pua_stable, s.blissary_code, v.vec
       FROM symbol_vecs v JOIN symbols s ON s.key = v.symbol_key`);
    if (!rows.length) return null;
    const scored = [];
    for (const [key, gloss, pos, pua, bcode, vec] of rows[0].values) {
      scored.push([cos(acc, blobVec(vec)), key, gloss, pos, pua, bcode]);
    }
    scored.sort((a, b) => b[0] - a[0]);
    return scored.slice(0, 12).map(([s, key, gloss, pos, pua, bcode]) =>
      [key, gloss, pos, pua, bcode, '', s]);
  }

  /* Load sql.js (CDN) + the resolver asset -> sql.js database handle. */
  async function load(assetUrl) {
    if (typeof initSqlJs === 'undefined') {
      await new Promise((res, rej) => {
        const s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.2/sql-wasm.js';
        s.onload = res; s.onerror = rej;
        document.head.appendChild(s);
      });
    }
    const SQL = await initSqlJs({ locateFile: f => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.2/${f}` });
    const res = await fetch(assetUrl);
    if (!res.ok) throw new Error(`resolver db ${res.status}`);
    return new SQL.Database(new Uint8Array(await res.arrayBuffer()));
  }

  window.Resolver = { DIM, blobVec, cos, norm, labelQuery, semantic, load };
})();
