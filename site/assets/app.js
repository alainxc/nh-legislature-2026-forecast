/* Shared front-end: maps, seat-distribution charts, sortable tables, ladder, swing slider. */
(function () {
  const tip = document.getElementById('tip');
  function showTip(html, ev) {
    if (!tip) return;
    tip.innerHTML = html; tip.style.display = 'block';
    const x = (ev.clientX || 0) + 14, y = (ev.clientY || 0) + 14;
    tip.style.left = Math.min(x, window.innerWidth - 280) + 'px';
    tip.style.top = Math.min(y, window.innerHeight - 90) + 'px';
  }
  function hideTip() { if (tip) tip.style.display = 'none'; }
  window.showTip = showTip; window.hideTip = hideTip;

  const colour = d3.scaleLinear().domain([0, 0.2, 0.35, 0.5, 0.65, 0.8, 1])
    .range(['#b1261a', '#d9402b', '#f0a99c', '#d8d0e8', '#9cc0f0', '#2a6fdb', '#1b4ea3']).clamp(true);
  window.probColour = colour;
  const fmtM = m => (m == null || isNaN(m)) ? '—' : (Math.abs(m) < 0.05 ? 'even' : (m > 0 ? 'D+' : 'R+') + Math.abs(m).toFixed(1));
  const pct = p => (p == null || isNaN(p)) ? '—' : Math.round(p * 100) + '%';
  window.fmtM = fmtM; window.pct = pct;

  // ---------- chamber seat distribution charts ----------
  window.drawSeatDistributions = function (F) {
    document.querySelectorAll('svg.dist').forEach(svg => {
      const ch = svg.dataset.chamber, c = F.chambers[ch]; if (!c) return;
      const W = svg.clientWidth || 480, H = 160, m = { l: 8, r: 8, t: 10, b: 24 };
      const dist = Object.entries(c.distribution).map(([k, v]) => ({ k: +k, v: v / F.n_sims }));
      const ks = dist.map(d => d.k);
      const lo = Math.max(0, d3.min(ks) - 1), hi = Math.min(c.total_seats, d3.max(ks) + 1);
      const x = d3.scaleBand().domain(d3.range(lo, hi + 1)).range([m.l, W - m.r]).padding(0.1);
      const y = d3.scaleLinear().domain([0, d3.max(dist, d => d.v)]).range([H - m.b, m.t]);
      const s = d3.select(svg).attr('viewBox', `0 0 ${W} ${H}`);
      s.selectAll('*').remove();
      s.selectAll('rect').data(dist).join('rect')
        .attr('x', d => x(d.k)).attr('width', x.bandwidth())
        .attr('y', d => y(d.v)).attr('height', d => y(0) - y(d.v))
        .attr('fill', d => d.k >= c.majority ? 'var(--dem)' : (c.total_seats - d.k >= c.majority ? 'var(--rep)' : 'var(--tie)'))
        .on('mousemove', (ev, d) => showTip(`<b>${d.k} Democratic seats</b><br>${(d.v * 100).toFixed(1)}% of simulations`, ev))
        .on('mouseleave', hideTip);
      const mx = x(c.majority) != null ? x(c.majority) - x.step() * 0.05 : null;
      if (mx != null) {
        s.append('line').attr('x1', mx).attr('x2', mx).attr('y1', m.t).attr('y2', H - m.b).attr('stroke', 'var(--fg)').attr('stroke-dasharray', '3,3');
        s.append('text').attr('x', mx + 4).attr('y', m.t + 10).attr('font-size', 11).text(`majority (${c.majority})`);
      }
      const step = hi - lo > 60 ? 20 : hi - lo > 30 ? 10 : hi - lo > 12 ? 5 : 1;
      const ticks = d3.range(lo, hi + 1).filter(k => k % step === 0);
      s.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`)
        .call(d3.axisBottom(x).tickValues(ticks).tickSize(3)).selectAll('text').attr('font-size', 11);
      s.append('text').attr('x', W / 2).attr('y', H - 2).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', 'var(--muted)').text('Democratic seats after the election');
    });
  };

  // ---------- map ----------
  window.initMap = function (id, F, rel) {
    const svg = d3.select('#' + id); if (svg.empty()) return;
    const bySen = {}; F.seats.forEach(s => bySen[s.key] = s);
    const byHouse = {}; (F.house || []).forEach(d => byHouse[d.key] = d);
    // town -> expected D share of all House seats covering it
    const townShare = {};
    (F.house || []).forEach(d => (d.town_list || []).forEach(t => {
      const acc = townShare[t] || (townShare[t] = { d: 0, n: 0, keys: [] });
      acc.d += d.d_seats_mean; acc.n += d.seats; acc.keys.push(d.key);
    }));
    const geo = {}; const projection = d3.geoMercator(); const path = d3.geoPath(projection);
    function draw(layer) {
      const g = geo[layer]; if (!g) return;
      projection.fitSize([700, 760], geo.counties || g);
      svg.selectAll('path').remove();
      const feats = layer === 'house' ? g.features.filter(f => !f.properties.floterial) : g.features;
      svg.selectAll('path.d').data(feats).join('path').attr('class', 'd').attr('d', path)
        .attr('fill', f => {
          const p = f.properties;
          if (layer === 'senate') { const s = bySen[p.key]; return s ? colour(s.p_dem) : '#bbb'; }
          if (layer === 'house') { const d = byHouse[p.key]; return d ? colour(d.p_dem) : '#bbb'; }
          const t = townShare[p.town]; return t ? colour(t.d / t.n) : '#bbb';
        })
        .on('mousemove', (ev, f) => {
          const p = f.properties;
          if (layer === 'senate') { const s = bySen[p.key]; if (!s) return; showTip(`<b>${s.label}</b><br>${s.dem_cand || '—'} (D) v. ${s.rep_cand || '—'} (R)<br>P(Dem) ${pct(s.p_dem)} · ${fmtM(s.margin_mean)}${s.uncontested ? '<br><i>uncontested</i>' : ''}`, ev); return; }
          if (layer === 'house') { const d = byHouse[p.key]; if (!d) return; showTip(`<b>House ${d.district_id}</b> · ${d.seats} seat${d.seats > 1 ? 's' : ''}<br>expected D seats ${d.d_seats_mean.toFixed(1)} · party margin ${fmtM(d.margin_mean)}<br>${d.n_d} D v. ${d.n_r} R on the ballot`, ev); return; }
          const t = townShare[p.town];
          showTip(`<b>${p.town}</b>${t ? `<br>House districts: ${t.keys.map(k => k.replace('-', ' ')).join(', ')}<br>expected D share of ${t.n} seat${t.n > 1 ? 's' : ''}: ${pct(t.d / t.n)}` : ''}`, ev);
        })
        .on('mouseleave', hideTip)
        .on('click', (ev, f) => {
          const p = f.properties;
          if (layer === 'senate' && bySen[p.key]) location.href = rel + 'districts/' + p.key + '.html';
          else if (layer === 'house' && byHouse[p.key]) location.href = rel + 'districts/' + p.key + '.html';
          else if (layer === 'towns') { const t = townShare[p.town]; if (t && t.keys.length) location.href = rel + 'districts/' + t.keys[0] + '.html'; }
        });
      if (geo.counties) {
        svg.selectAll('path.county').data(geo.counties.features).join('path').attr('class', 'county').attr('d', path)
          .attr('fill', 'none').attr('stroke', 'var(--fg)').attr('stroke-opacity', 0.35).attr('stroke-width', 0.8).attr('pointer-events', 'none');
      }
    }
    Promise.all([
      d3.json(rel + 'assets/geo/senate.geojson'), d3.json(rel + 'assets/geo/house.geojson').catch(() => null),
      d3.json(rel + 'assets/geo/towns.geojson').catch(() => null), d3.json(rel + 'assets/geo/counties.geojson').catch(() => null)
    ]).then(([s, h, t, c]) => { geo.senate = s; geo.house = h; geo.towns = t; geo.counties = c; draw('senate'); });
    document.querySelectorAll('button.tab[data-map]').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('button.tab[data-map]').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); draw(b.dataset.map);
    }));
  };

  // ---------- Senate seats table ----------
  window.initSeatsTable = function (F) {
    const tbody = document.querySelector('#seats tbody'); if (!tbody) return;
    const q = document.getElementById('q'), rS = document.getElementById('rating'), cOnly = document.getElementById('contested');
    let sortK = 'p_flip', asc = false;
    function render() {
      let rows = F.seats.slice();
      const qq = (q.value || '').toLowerCase();
      if (qq) rows = rows.filter(s => [s.label, s.dem_cand, s.rep_cand, s.incumbent_name, s.region_label, s.rating].join(' ').toLowerCase().includes(qq));
      if (rS.value) rows = rows.filter(s => s.rating === rS.value);
      if (cOnly.checked) rows = rows.filter(s => !s.uncontested);
      rows.sort((a, b) => {
        let va = a[sortK], vb = b[sortK];
        if (sortK === 'seat') { va = +a.key.slice(1); vb = +b.key.slice(1); }
        if (sortK === 'region') { va = a.region_label; vb = b.region_label; }
        if (va == null) return 1; if (vb == null) return -1;
        if (typeof va === 'string') return asc ? va.localeCompare(vb) : vb.localeCompare(va);
        return asc ? va - vb : vb - va;
      });
      tbody.innerHTML = rows.map(s => `<tr>
        <td><a href="districts/${s.key}.html">${s.label}</a>${s.uncontested ? ' <span class="note">(unc.)</span>' : ''}${s.open_seat ? ' <span class="note">(open)</span>' : ''}</td>
        <td>${s.region_label}</td>
        <td><span class="pill" style="background:var(--${s.holder_party === 'D' ? 'dem' : s.holder_party === 'R' ? 'rep' : 'tie'})">${s.holder_party}</span></td>
        <td>${s.dem_cand || '—'}</td><td>${s.rep_cand || '—'}</td>
        <td class="num">${fmtM(s.lean)}</td><td class="num">${fmtM(s.margin_mean)}</td>
        <td class="num" style="color:${colour(s.p_dem)};font-weight:600">${pct(s.p_dem)}</td><td class="num">${pct(s.p_flip)}</td>
        <td>${s.rating}</td><td class="num">${s.tipping ? (s.tipping * 100).toFixed(1) + '%' : '—'}</td></tr>`).join('');
      document.querySelectorAll('#seats th').forEach(th => { th.classList.toggle('sorted', th.dataset.k === sortK); th.classList.toggle('asc', th.dataset.k === sortK && asc); });
    }
    document.querySelectorAll('#seats th').forEach(th => th.addEventListener('click', () => {
      if (sortK === th.dataset.k) asc = !asc; else { sortK = th.dataset.k; asc = ['seat', 'dem_cand', 'rep_cand', 'region'].includes(sortK); }
      render();
    }));
    [q, rS, cOnly].forEach(el => el.addEventListener('input', render));
    render();
  };

  // ---------- House districts table ----------
  window.initHouseTable = function (F) {
    const tbody = document.querySelector('#house tbody'); if (!tbody || !F.house) return;
    const q = document.getElementById('hq'), cS = document.getElementById('hcounty'), tS = document.getElementById('htype'), cOnly = document.getElementById('hcontested');
    let sortK = 'p_change', asc = false;
    const order = ['Belknap', 'Carroll', 'Cheshire', 'Coos', 'Grafton', 'Hillsborough', 'Merrimack', 'Rockingham', 'Strafford', 'Sullivan'];
    function render() {
      let rows = F.house.slice();
      const qq = (q.value || '').toLowerCase();
      if (qq) rows = rows.filter(d => [d.label, d.region_label, d.rating, (d.town_list || []).join(' ')].join(' ').toLowerCase().includes(qq));
      if (cS.value) rows = rows.filter(d => d.county === cS.value);
      if (tS.value === 'base') rows = rows.filter(d => !d.floterial); if (tS.value === 'floterial') rows = rows.filter(d => d.floterial);
      if (cOnly.checked) rows = rows.filter(d => d.contested);
      rows.sort((a, b) => {
        let va = a[sortK], vb = b[sortK];
        if (sortK === 'district_id') { va = order.indexOf(a.county) * 100 + +a.key.split('-')[1]; vb = order.indexOf(b.county) * 100 + +b.key.split('-')[1]; }
        if (sortK === 'held') { va = a.held_d - a.held_r; vb = b.held_d - b.held_r; }
        if (sortK === 'cands') { va = a.n_d - a.n_r; vb = b.n_d - b.n_r; }
        if (sortK === 'region') { va = a.region_label; vb = b.region_label; }
        if (va == null) return 1; if (vb == null) return -1;
        if (typeof va === 'string') return asc ? va.localeCompare(vb) : vb.localeCompare(va);
        return asc ? va - vb : vb - va;
      });
      tbody.innerHTML = rows.map(d => `<tr>
        <td><a href="districts/${d.key}.html">${d.district_id}</a>${d.floterial ? ' <span class="note">(flot.)</span>' : ''}${d.contested ? '' : ' <span class="note">(unc.)</span>'}</td>
        <td>${d.region_label}</td><td class="num">${d.seats}</td>
        <td>${d.held_d}–${d.held_r}${d.vacant ? ` <span class="note">(${d.vacant} vac.)</span>` : ''}</td>
        <td>${d.n_d}–${d.n_r}${d.n_other ? ` <span class="note">+${d.n_other}</span>` : ''}</td>
        <td class="num">${fmtM(d.lean)}</td><td class="num">${fmtM(d.margin_mean)}</td>
        <td class="num">${d.d_seats_mean.toFixed(1)}</td>
        <td class="num" style="color:${colour(d.p_dem)};font-weight:600">${pct(d.p_dem)}</td><td class="num">${pct(d.p_change)}</td><td>${d.rating}</td></tr>`).join('');
      document.querySelectorAll('#house th').forEach(th => { th.classList.toggle('sorted', th.dataset.k === sortK); th.classList.toggle('asc', th.dataset.k === sortK && asc); });
    }
    document.querySelectorAll('#house th').forEach(th => th.addEventListener('click', () => {
      if (sortK === th.dataset.k) asc = !asc; else { sortK = th.dataset.k; asc = ['district_id', 'region'].includes(sortK); }
      render();
    }));
    [q, cS, tS, cOnly].forEach(el => el.addEventListener('input', render));
    render();
  };

  // ---------- ladder ----------
  window.drawLadder = function (id, F) {
    const svg = d3.select('#' + id); if (svg.empty()) return;
    const W = svg.node().clientWidth || 900;
    const panels = [{ ch: 'senate', items: F.seats.slice().sort((a, b) => b.margin_mean - a.margin_mean), label: 'State Senate (24 seats): bars show the expected margin; the dashed line is the 13th seat' }];
    if (F.house && F.chambers.house) panels.push({ ch: 'house', items: F.house.slice().sort((a, b) => b.margin_mean - a.margin_mean), label: 'State House districts (203, sized by seats): bars show the expected party margin' });
    const H = panels.length * 180; svg.attr('viewBox', `0 0 ${W} ${H}`);
    panels.forEach((p, i) => {
      const y0 = i * 180 + 24, h = 130;
      const g = svg.append('g');
      g.append('text').attr('x', 10).attr('y', y0 - 8).attr('font-size', 13).attr('font-weight', 600).text(p.label);
      const maxAbs = Math.min(60, d3.max(p.items, s => Math.abs(s.margin_mean)) || 30);
      const y = d3.scaleLinear().domain([-maxAbs, maxAbs]).range([y0 + h, y0]);
      if (p.ch === 'senate') {
        const x = d3.scaleBand().domain(p.items.map(s => s.key)).range([10, W - 10]).padding(0.08);
        g.selectAll('rect').data(p.items).join('rect').attr('x', s => x(s.key)).attr('width', x.bandwidth())
          .attr('y', s => Math.min(y(0), y(Math.max(-maxAbs, Math.min(maxAbs, s.margin_mean))))).attr('height', s => Math.abs(y(0) - y(Math.max(-maxAbs, Math.min(maxAbs, s.margin_mean)))))
          .attr('fill', s => colour(s.p_dem))
          .on('mousemove', (ev, s) => showTip(`<b>${s.label}</b><br>${fmtM(s.margin_mean)} · P(Dem) ${pct(s.p_dem)}${s.tipping ? `<br>tipping-point ${(s.tipping * 100).toFixed(1)}%` : ''}`, ev)).on('mouseleave', hideTip)
          .on('click', (ev, s) => location.href = 'districts/' + s.key + '.html');
        const maj = F.chambers.senate.majority; const mx = x(p.items[maj - 1].key) + x.bandwidth();
        g.append('line').attr('x1', mx).attr('x2', mx).attr('y1', y0).attr('y2', y0 + h).attr('stroke', 'var(--fg)').attr('stroke-dasharray', '4,3');
        g.append('text').attr('x', mx + 4).attr('y', y0 + 12).attr('font-size', 11).text(`13th seat: ${p.items[maj - 1].label}`);
      } else {
        const total = d3.sum(p.items, d => d.seats); const x = d3.scaleLinear().domain([0, total]).range([10, W - 10]);
        let acc = 0;
        p.items.forEach(d => { d._x0 = acc; acc += d.seats; });
        g.selectAll('rect').data(p.items).join('rect').attr('x', d => x(d._x0)).attr('width', d => Math.max(0.5, x(d._x0 + d.seats) - x(d._x0) - 0.5))
          .attr('y', d => Math.min(y(0), y(Math.max(-maxAbs, Math.min(maxAbs, d.margin_mean))))).attr('height', d => Math.abs(y(0) - y(Math.max(-maxAbs, Math.min(maxAbs, d.margin_mean)))))
          .attr('fill', d => colour(d.p_dem))
          .on('mousemove', (ev, d) => showTip(`<b>House ${d.district_id}</b> · ${d.seats} seats<br>party margin ${fmtM(d.margin_mean)} · expected D seats ${d.d_seats_mean.toFixed(1)}`, ev)).on('mouseleave', hideTip)
          .on('click', (ev, d) => location.href = 'districts/' + d.key + '.html');
        const mx = x(F.chambers.house.majority);
        g.append('line').attr('x1', mx).attr('x2', mx).attr('y1', y0).attr('y2', y0 + h).attr('stroke', 'var(--fg)').attr('stroke-dasharray', '4,3');
        g.append('text').attr('x', mx + 4).attr('y', y0 + 12).attr('font-size', 11).text('201 seats, counting from the most Democratic district');
      }
      g.append('line').attr('x1', 10).attr('x2', W - 10).attr('y1', y(0)).attr('y2', y(0)).attr('stroke', 'var(--fg)').attr('stroke-opacity', 0.5);
    });
  };

  // ---------- "what if the polls are off" slider (interpolates the precomputed swing curve) ----------
  window.initSwing = function (F) {
    const range = document.getElementById('swing-range'); if (!range || !F.swing_curve) return;
    const curve = F.swing_curve.slice().sort((a, b) => a.env - b.env);
    const el = id => document.getElementById(id);
    function at(env, ch, k) {
      let i = 0; while (i < curve.length - 1 && curve[i + 1].env <= env) i++;
      const a = curve[i], b = curve[Math.min(i + 1, curve.length - 1)];
      if (!a[ch]) return null;
      const t = b.env === a.env ? 0 : Math.min(1, Math.max(0, (env - a.env) / (b.env - a.env)));
      return a[ch][k] + t * (b[ch][k] - a[ch][k]);
    }
    function render(env) {
      range.value = env;
      el('swing-value').textContent = fmtM(env);
      for (const ch of ['senate', 'house']) {
        if (!el(`swing-${ch}-big`) || !F.chambers[ch]) continue;
        const c = F.chambers[ch];
        const pD = at(env, ch, 'p_dem_control'), pR = at(env, ch, 'p_rep_control'), mean = at(env, ch, 'dem_seats_mean');
        const lo = at(env, ch, 'dem_seats_p05'), hi = at(env, ch, 'dem_seats_p95'), pT = Math.max(0, 1 - pD - pR);
        const lead = pD >= pR;
        el(`swing-${ch}-big`).className = 'big ' + (lead ? 'dem' : 'rep');
        el(`swing-${ch}-big`).textContent = Math.round((lead ? pD : pR) * 100) + '%';
        el(`swing-${ch}-text`).innerHTML = `chance <b>${lead ? 'Democrats' : 'Republicans'}</b> control · expected <b>${mean.toFixed(1)}</b> D seats of ${c.total_seats} (90% range ${Math.round(lo)}–${Math.round(hi)})` +
          `<div class="note">D ${(pD * 100).toFixed(1)}% · R ${(pR * 100).toFixed(1)}%${pT > 0.001 ? ` · no majority ${(pT * 100).toFixed(1)}%` : ''}</div>`;
        el(`swing-${ch}-bar`).innerHTML = `<span style="width:${pD * 100}%;background:var(--dem)"></span>` + (pT > 0.001 ? `<span style="width:${pT * 100}%;background:var(--tie)"></span>` : '');
      }
      const diff = env - F.env.margin;
      el('swing-note').textContent = `Statewide generic legislative vote fixed at ${fmtM(env)}` + (Math.abs(diff) < 0.05 ? ' (the model\'s current estimate).' : `, ${Math.abs(diff).toFixed(1)} points ${diff > 0 ? 'more Democratic' : 'more Republican'} than the model's current estimate of ${fmtM(F.env.margin)}.`) +
        ' Regional and district error still apply at each setting; only the statewide error is switched off.';
      document.querySelectorAll('[data-swing]').forEach(b => b.classList.toggle('active', Math.abs(presetValue(b.dataset.swing) - env) < 0.3));
    }
    const presetValue = k => k === 'model' ? F.env.margin : F.env.margin + (F.env.backtest_misses[k] || 0);
    const snap = v => Math.round(v * 2) / 2;
    range.addEventListener('input', () => render(+range.value));
    document.querySelectorAll('[data-swing]').forEach(b => b.addEventListener('click', () => render(snap(presetValue(b.dataset.swing)))));
    render(snap(F.env.margin));
  };

  window.drawEnvDist = function (id, D) {
    const svg = d3.select('#' + id); if (svg.empty()) return;
    const W = svg.node().clientWidth || 800, H = 140, m = { l: 8, r: 8, t: 8, b: 22 };
    svg.attr('viewBox', `0 0 ${W} ${H}`);
    const bins = D.hist_bins.slice(0, -1).map((b, i) => ({ lo: b, hi: D.hist_bins[i + 1], v: D.hist[i] }));
    const total = d3.sum(bins, b => b.v);
    const x = d3.scaleLinear().domain([-20, 20]).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, d3.max(bins, b => b.v)]).range([H - m.b, m.t]);
    svg.selectAll('rect').data(bins).join('rect').attr('x', b => x(b.lo) + 1).attr('width', x(1) - x(0) - 2)
      .attr('y', b => y(b.v)).attr('height', b => y(0) - y(b.v)).attr('fill', b => (b.lo + b.hi) / 2 > 0 ? 'var(--dem)' : 'var(--rep)')
      .on('mousemove', (ev, b) => showTip(`${fmtM(b.lo)} to ${fmtM(b.hi)}: ${(100 * b.v / total).toFixed(1)}%`, ev)).on('mouseleave', hideTip);
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(9).tickFormat(v => v === 0 ? 'even' : (v > 0 ? 'D+' : 'R+') + Math.abs(v)));
  };

  // normal margin density for a Senate seat
  window.drawMarginDist = function (id, mu, sd) {
    const svg = d3.select('#' + id); if (svg.empty() || sd == null) return;
    const W = svg.node().clientWidth || 480, H = 120, m = { l: 8, r: 8, t: 8, b: 22 };
    svg.attr('viewBox', `0 0 ${W} ${H}`);
    const lo = Math.min(-5, mu - 3.2 * sd), hi = Math.max(5, mu + 3.2 * sd);
    const x = d3.scaleLinear().domain([lo, hi]).range([m.l, W - m.r]);
    const pts = d3.range(lo, hi, (hi - lo) / 160).map(v => ({ v, d: Math.exp(-0.5 * ((v - mu) / sd) ** 2) }));
    const y = d3.scaleLinear().domain([0, 1]).range([H - m.b, m.t]);
    const area = d3.area().x(p => x(p.v)).y0(y(0)).y1(p => y(p.d));
    svg.append('path').datum(pts.filter(p => p.v <= 0)).attr('d', area).attr('fill', 'var(--rep)').attr('opacity', 0.7);
    svg.append('path').datum(pts.filter(p => p.v >= -0.01)).attr('d', area).attr('fill', 'var(--dem)').attr('opacity', 0.7);
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(7).tickFormat(v => v === 0 ? 'even' : (v > 0 ? 'D+' : 'R+') + Math.abs(v)));
    svg.append('text').attr('x', W / 2).attr('y', H - 1).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', 'var(--muted)').text('simulated margin');
  };

  // bar chart of the D-seat split distribution for a House district
  window.drawSeatSplit = function (id, dist, seats) {
    const svg = d3.select('#' + id); if (svg.empty()) return;
    const W = svg.node().clientWidth || 480, H = 120, m = { l: 8, r: 8, t: 8, b: 24 };
    svg.attr('viewBox', `0 0 ${W} ${H}`);
    const data = d3.range(0, seats + 1).map(k => ({ k, v: dist[k] || 0 }));
    const x = d3.scaleBand().domain(data.map(d => d.k)).range([m.l, W - m.r]).padding(0.15);
    const y = d3.scaleLinear().domain([0, Math.max(0.05, d3.max(data, d => d.v))]).range([H - m.b, m.t]);
    svg.selectAll('rect').data(data).join('rect').attr('x', d => x(d.k)).attr('width', x.bandwidth()).attr('y', d => y(d.v)).attr('height', d => y(0) - y(d.v))
      .attr('fill', d => colour(seats ? d.k / seats : 0.5))
      .on('mousemove', (ev, d) => showTip(`<b>${d.k} Democrat${d.k === 1 ? '' : 's'}, ${seats - d.k} Republican${seats - d.k === 1 ? '' : 's'}</b><br>${(d.v * 100).toFixed(1)}% of simulations`, ev)).on('mouseleave', hideTip);
    svg.selectAll('text.v').data(data).join('text').attr('class', 'v').attr('x', d => x(d.k) + x.bandwidth() / 2).attr('y', d => y(d.v) - 3).attr('text-anchor', 'middle').attr('font-size', 11).text(d => d.v >= 0.005 ? Math.round(d.v * 100) + '%' : '');
    svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).tickFormat(k => `${k} D`));
  };
})();
