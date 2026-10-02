(() => {
  'use strict';

  const year = document.getElementById('yearInput');
  const disaster = document.getElementById('disasterInput');
  const location = document.getElementById('locationInput');
  const button = document.getElementById('analyzeBtn');
  const status = document.getElementById('status');
  const progress = document.getElementById('progress');
  const risk = document.getElementById('riskBadge');
  const preview = document.getElementById('baselinePreview');
  const baselineName = document.getElementById('baselineName');
  const baselineYear = document.getElementById('baselineYear');
  let busy = false;
  let options = {};

  function setRisk(value) {
    risk.className = 'risk neutral';
    risk.textContent = 'Awaiting analysis';
    document.getElementById('riskMetric').textContent = value || '—';
    if (value === 'LOW') { risk.className = 'risk low'; risk.textContent = 'LOW RISK'; }
    else if (value === 'MODERATE') { risk.className = 'risk moderate'; risk.textContent = 'MODERATE RISK'; }
    else if (value === 'HIGH') { risk.className = 'risk high'; risk.textContent = 'HIGH RISK'; }
    else if (value) risk.textContent = value;
  }

  function populateLocations() {
    location.innerHTML = '<option value="">Select location</option>';
    const list = Array.isArray(options[disaster.value]) ? options[disaster.value] : [];
    list.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      location.appendChild(opt);
    });
    location.disabled = list.length === 0;
    if (!list.length) location.innerHTML = '<option value="">No locations available</option>';
    updatePreview();
  }

  async function loadOptions() {
    try {
      const response = await fetch('/api/options?_=' + Date.now(), { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not load server locations.');
      options = data.options || {};
      if (options.GLACIER) disaster.value = 'GLACIER';
      populateLocations();
      status.textContent = options.GLACIER?.length
        ? 'GLACIER is selected by default. Select a location and enter a future year.'
        : 'No satellite locations found on the server.';
    } catch (error) {
      status.textContent = 'Could not load server locations: ' + error.message;
    }
  }

  async function updatePreview() {
    const loc = location.value;
    if (!loc) {
      preview.style.display = 'none';
      baselineName.textContent = 'Select a location';
      baselineYear.textContent = 'No image selected';
      return;
    }
    try {
      const r = await fetch('/api/preview?disaster=' + encodeURIComponent(disaster.value) + '&location=' + encodeURIComponent(loc) + '&_=' + Date.now(), { cache: 'no-store' });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Preview unavailable');
      preview.onload = () => { preview.style.display = 'block'; };
      preview.src = d.url;
      baselineName.textContent = d.name;
      baselineYear.textContent = 'Latest stored image · ' + d.year;
    } catch (error) {
      preview.style.display = 'none';
      baselineName.textContent = 'Preview unavailable';
      baselineYear.textContent = error.message;
    }
  }

  function render(data) {
    const item = (data.results || [])[0] || {};
    const prediction = item.prediction || {};
    document.getElementById('futureYear').textContent = data.future_year ?? '—';
    const topWindow = prediction.disaster_window || {};
    document.getElementById('predictedYearTop').textContent = topWindow.high_risk_year || topWindow.estimated_disaster_year || '—';
    document.getElementById('predictedChange').textContent = prediction.predicted_change != null ? prediction.predicted_change + '%' : '—';
    setRisk(prediction.risk || '');
    document.getElementById('equation').textContent = prediction.equation || 'No mathematical prediction equation returned.';

    const body = document.getElementById('historyBody');
    body.innerHTML = '';
    const changes = Array.isArray(item.changes) ? item.changes : [];
    if (!changes.length) {
      body.innerHTML = '<tr><td colspan="2">No historical comparison data.</td></tr>';
    } else {
      changes.forEach(row => {
        const tr = document.createElement('tr');
        const y = document.createElement('td');
        const c = document.createElement('td');
        y.textContent = row?.[0] ?? '—';
        c.textContent = row?.[1] != null ? row[1] + '%' : '—';
        tr.append(y, c);
        body.appendChild(tr);
      });
    }

    const window = prediction.disaster_window || {};
    document.getElementById('windowYears').textContent = window.window || 'Not reliably predictable';
    document.getElementById('windowMessage').textContent = window.message || 'No risk-window estimate returned.';
    document.getElementById('annualRate').textContent = prediction.annual_change_rate != null ? prediction.annual_change_rate + '% / year' : '—';
    document.getElementById('highRiskYear').textContent = window.high_risk_year || '—';
  }

  disaster.addEventListener('change', populateLocations);
  location.addEventListener('change', updatePreview);

  button.addEventListener('click', async () => {
    if (busy) return;
    const value = year.value.trim();
    const y = Number(value);
    if (!Number.isInteger(y) || y < 1900 || y > 2100) {
      status.textContent = 'Please enter a valid future year.';
      year.focus();
      return;
    }
    if (!location.value) {
      status.textContent = 'Please select a location.';
      location.focus();
      return;
    }

    busy = true;
    button.disabled = true;
    button.querySelector('span').textContent = 'Analyzing...';
    progress.style.display = 'block';
    status.textContent = 'Analyzing ' + location.value + ' using the stored satellite images...';
    setRisk('');

    try {
      const form = new URLSearchParams();
      form.set('future_year', String(y));
      form.set('disaster', disaster.value || 'GLACIER');
      form.set('location', location.value);
      const response = await fetch('/api/analyze', { method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'}, body: form.toString(), cache: 'no-store' });
      let data;
      try { data = await response.json(); }
      catch (_) { throw new Error('The server returned an unreadable response.'); }
      if (!response.ok || data.error) throw new Error(data.error || 'Analysis failed.');
      render(data);
      status.textContent = 'Analysis completed successfully for ' + location.value + '.';
    } catch (error) {
      status.textContent = 'Analysis failed: ' + error.message;
    } finally {
      busy = false;
      button.disabled = false;
      button.querySelector('span').textContent = 'Run analysis';
      progress.style.display = 'none';
    }
  });

  year.addEventListener('keydown', event => {
    if (event.key === 'Enter') button.click();
  });

  loadOptions();

  // Self-contained interactive Earth. No CDN/network dependency is required.
  const canvas = document.getElementById('globe');
  if (canvas && canvas.getContext) {
    const ctx = canvas.getContext('2d', { alpha: true });
    const map = new Image();
    map.src = '/static/earth/earth_map.jpg';
    let sourceCanvas = null;
    let sourceCtx = null;
    let yaw = -0.45, pitch = 0.08, zoom = 0.82;
    let dragging = false, lastX = 0, lastY = 0, vx = 0.002, vy = 0;
    let raf = 0;

    map.onload = () => {
      sourceCanvas = document.createElement('canvas');
      sourceCanvas.width = map.naturalWidth;
      sourceCanvas.height = map.naturalHeight;
      sourceCtx = sourceCanvas.getContext('2d', { willReadFrequently: true });
      sourceCtx.drawImage(map, 0, 0);
      drawEarth();
    };

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(180, Math.floor(canvas.clientWidth * dpr));
      const h = Math.max(160, Math.floor(canvas.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      drawEarth();
    }

    function drawEarth() {
      if (!ctx) return;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      const cx = w * 0.5, cy = h * 0.5;
      const radius = Math.min(w, h) * 0.34 * zoom;
      if (radius < 20) return;

      // Soft atmosphere/shadow layers first.
      const glow = ctx.createRadialGradient(cx-radius*.25, cy-radius*.35, radius*.55, cx, cy, radius*1.15);
      glow.addColorStop(0, 'rgba(104,160,181,.16)');
      glow.addColorStop(1, 'rgba(104,160,181,0)');
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(cx, cy, radius*1.18, 0, Math.PI*2); ctx.fill();

      if (!sourceCtx) {
        ctx.fillStyle = '#9fb9c7'; ctx.beginPath(); ctx.arc(cx,cy,radius,0,Math.PI*2); ctx.fill(); return;
      }
      const src = sourceCtx.getImageData(0,0,sourceCanvas.width,sourceCanvas.height).data;
      const image = ctx.createImageData(Math.ceil(radius*2), Math.ceil(radius*2));
      const iw = Math.ceil(radius*2), ih = Math.ceil(radius*2);
      const lightX = -0.45, lightY = -0.35, lightZ = 0.82;
      const cp = Math.cos(pitch), sp = Math.sin(pitch), cyaw = Math.cos(yaw), syaw = Math.sin(yaw);

      for (let py=0; py<ih; py++) {
        const ny=(py+0.5-ih/2)/radius;
        if (Math.abs(ny)>1) continue;
        for (let px=0; px<iw; px++) {
          const nx=(px+0.5-iw/2)/radius;
          const rr=nx*nx+ny*ny;
          if (rr>1) continue;
          const nz=Math.sqrt(1-rr);
          // Camera-space point -> yaw then pitch.
          let x=nx*cyaw+nz*syaw;
          let z=-nx*syaw+nz*cyaw;
          let y=ny;
          const yy=y*cp-z*sp;
          const zz=y*sp+z*cp;
          y=yy; z=zz;
          let lon=Math.atan2(x,z);
          let lat=Math.asin(Math.max(-1,Math.min(1,y)));
          let u=(lon/(Math.PI*2)+0.5); u-=Math.floor(u);
          let v=0.5-lat/Math.PI;
          const sx=Math.min(sourceCanvas.width-1,Math.max(0,Math.floor(u*sourceCanvas.width)));
          const sy=Math.min(sourceCanvas.height-1,Math.max(0,Math.floor(v*sourceCanvas.height)));
          const si=(sy*sourceCanvas.width+sx)*4;
          const normalX=x, normalY=y, normalZ=z;
          const diffuse=Math.max(0.30, normalX*lightX+normalY*lightY+normalZ*lightZ);
          const di=(py*iw+px)*4;
          image.data[di]=Math.min(255,src[si]*diffuse+8);
          image.data[di+1]=Math.min(255,src[si+1]*diffuse+10);
          image.data[di+2]=Math.min(255,src[si+2]*diffuse+12);
          image.data[di+3]=255;
        }
      }
      const off=document.createElement('canvas'); off.width=iw; off.height=ih;
      off.getContext('2d').putImageData(image,0,0);
      ctx.save(); ctx.translate(cx-iw/2,cy-ih/2); ctx.drawImage(off,0,0); ctx.restore();
      ctx.strokeStyle='rgba(47,113,142,.22)'; ctx.lineWidth=Math.max(1,w/600); ctx.beginPath(); ctx.arc(cx,cy,radius,0,Math.PI*2); ctx.stroke();
    }

    function animate() {
      if (!dragging) { yaw += vx; pitch += vy; vx *= .992; vy *= .992; if (Math.abs(vx)<0.00035) vx=0.00065; if (Math.abs(vy)<0.00003) vy=0; }
      drawEarth();
      raf=requestAnimationFrame(animate);
    }
    canvas.addEventListener('pointerdown', e => { dragging=true; lastX=e.clientX; lastY=e.clientY; canvas.setPointerCapture?.(e.pointerId); });
    canvas.addEventListener('pointermove', e => { if(!dragging)return; const dx=e.clientX-lastX,dy=e.clientY-lastY; yaw -= dx*.006; pitch=Math.max(-1.0,Math.min(1.0,pitch-dy*.0045)); vx=-dx*.00055; vy=-dy*.00035; lastX=e.clientX; lastY=e.clientY; });
    const stop=()=>{dragging=false}; canvas.addEventListener('pointerup',stop); canvas.addEventListener('pointercancel',stop); canvas.addEventListener('pointerleave',()=>{ if(dragging) dragging=false; });
    canvas.addEventListener('wheel', e=>{e.preventDefault(); zoom=Math.max(.68,Math.min(1.0,zoom+(-e.deltaY)*.00035)); drawEarth();},{passive:false});
    window.addEventListener('resize',resize);
    resize(); animate();
  }
})();
