const policies = ["static", "least_loaded", "threshold", "stability_aware", "uncertainty_aware"];
const colors = { static: "#8493a9", least_loaded: "#6c96ff", threshold: "#ffd17a", stability_aware: "#86e0ac", uncertainty_aware: "#4dd9d0" };
const labels = { static: "Static", least_loaded: "Least loaded", threshold: "Threshold", stability_aware: "Stability aware", uncertainty_aware: "Uncertainty aware" };
const metricInfo = {
  tcp_app_rtt_p99_ms: { title: "TCP application RTT p99", unit: "ms", direction: "lower is better", format: v => `${v.toFixed(2)} ms` },
  aggregate_goodput_mbps: { title: "Aggregate goodput", unit: "Mbps", direction: "higher is better", format: v => `${v.toFixed(2)} Mbps` },
  udp_loss_pct: { title: "UDP packet loss", unit: "%", direction: "lower is better", format: v => `${v.toFixed(3)}%` },
  jain_fairness: { title: "Jain fairness", unit: "0–1", direction: "higher is better", format: v => v.toFixed(3) },
  path_changes_per_minute: { title: "Path changes per minute", unit: "changes/min", direction: "lower is better", format: v => v.toFixed(2) },
  controller_cpu_seconds: { title: "Ryu controller CPU time", unit: "s", direction: "lower is better", format: v => `${v.toFixed(3)} s` },
  controller_rss_peak_mb: { title: "Ryu controller peak RSS", unit: "MB", direction: "lower is better", format: v => `${v.toFixed(1)} MB` }
};
const $ = id => document.getElementById(id);
function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const parseLine = line => { const out=[]; let field="", quoted=false; for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'&&line[i+1]==='"'&&quoted){field+='"';i++;}else if(c==='"')quoted=!quoted;else if(c===','&&!quoted){out.push(field);field="";}else field+=c;}out.push(field);return out; };
  const header=parseLine(lines.shift()); return lines.filter(Boolean).map(line=>Object.fromEntries(parseLine(line).map((v,i)=>[header[i],v])));
}
function fillSelect(select, values, pretty = x => x) { select.replaceChildren(...values.map(v => { const o=document.createElement('option');o.value=v;o.textContent=pretty(v);return o; })); }
function numeric(row, key) { const n=Number(row[key]); return Number.isFinite(n) ? n : null; }
function policySamples() {
  const scenario=$('scenario').value,condition=$('condition').value,path=$('path').value;
  return data.summary.filter(r=>r.scenario===scenario&&r.condition===condition&&r.initial_path===path);
}
function draw() {
  const metric=$('metric').value, info=metricInfo[metric], rows=policySamples();
  const plot=`${$('scenario').value}__${$('condition').value}__${$('path').value}__${metric}.svg`;
  $('chart-export').href=`data/plots/${plot}`;
  $('chart-export').download=plot;
  const svg=$('chart'); svg.replaceChildren(); svg.setAttribute('viewBox','0 0 900 360');
  $('chart-title').textContent=`${info.title} by policy`;
  $('chart-description').textContent=`${$('scenario').selectedOptions[0]?.textContent} · ${$('condition').value} telemetry · ${$('path').value} bottleneck · ${info.direction}`;
  $('chart-unit').textContent=info.unit;
  const values=rows.flatMap(r=>[numeric(r,`${metric}_ci95_low`),numeric(r,`${metric}_ci95_high`)]).filter(v=>v!==null);
  if(!values.length){svg.innerHTML='<text x="450" y="180" text-anchor="middle" fill="#a6b5c9">No measured values for this slice</text>'; $('results-table').innerHTML='<tr><td colspan="4">No measured values for this selection.</td></tr>';return;}
  let min=Math.min(0,...values),max=Math.max(...values);if(min===max)max=min+1;const pad=(max-min)*.12;min=Math.max(0,min-pad);max+=pad;
  const left=220,right=850,top=30,bottom=300,x=v=>left+(v-min)/(max-min)*(right-left);
  for(let tick=0;tick<=4;tick++){const v=min+(max-min)*tick/4,xx=x(v);const line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('x1',xx);line.setAttribute('x2',xx);line.setAttribute('y1',top);line.setAttribute('y2',bottom);line.setAttribute('stroke','#263750');svg.append(line);const t=document.createElementNS(svg.namespaceURI,'text');t.setAttribute('x',xx);t.setAttribute('y',326);t.setAttribute('text-anchor','middle');t.setAttribute('fill','#8495ab');t.setAttribute('font-size','11');t.textContent=v.toFixed(2);svg.append(t);}
  const table=[];for(let i=0;i<policies.length;i++){const p=policies[i],row=rows.find(r=>r.policy===p),y=58+i*51;if(!row){continue;}const mean=numeric(row,`${metric}_mean`),lo=numeric(row,`${metric}_ci95_low`),hi=numeric(row,`${metric}_ci95_high`),n=numeric(row,`${metric}_n`)??0;if(mean===null){continue;}
    const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x',8);text.setAttribute('y',y+4);text.setAttribute('fill','#d6e2f0');text.setAttribute('font-size','12');text.textContent=labels[p];svg.append(text);
    const range=document.createElementNS(svg.namespaceURI,'line');range.setAttribute('x1',x(lo??mean));range.setAttribute('x2',x(hi??mean));range.setAttribute('y1',y);range.setAttribute('y2',y);range.setAttribute('stroke',colors[p]);range.setAttribute('stroke-width','4');range.setAttribute('stroke-linecap','round');svg.append(range);
    const dot=document.createElementNS(svg.namespaceURI,'circle');dot.setAttribute('cx',x(mean));dot.setAttribute('cy',y);dot.setAttribute('r',6);dot.setAttribute('fill',colors[p]);svg.append(dot);
    table.push(`<tr><td><i class="policy-dot" style="background:${colors[p]}"></i>${labels[p]}</td><td>${n}</td><td>${info.format(mean)}</td><td>${lo===null||hi===null?'—':`${info.format(lo)} – ${info.format(hi)}`}</td></tr>`);
  }
  const axis=document.createElementNS(svg.namespaceURI,'text');axis.setAttribute('x',(left+right)/2);axis.setAttribute('y',354);axis.setAttribute('text-anchor','middle');axis.setAttribute('fill','#71829a');axis.setAttribute('font-size','10');axis.textContent=`Mean ${info.title} (${info.unit}) with trial-level bootstrap 95% interval`;svg.append(axis);
  $('results-table').innerHTML=table.join('')||'<tr><td colspan="4">No measured values for this selection.</td></tr>';
  $('legend').innerHTML=policies.map(p=>`<span><i style="background:${colors[p]}"></i>${labels[p]}</span>`).join('');
}
let data;
async function init(){
  try{
    const [summaryText,trialsText,manifest]=await Promise.all([fetch('data/FINAL_CAMPAIGN_SUMMARY.csv').then(r=>{if(!r.ok)throw Error('summary unavailable');return r.text();}),fetch('data/trials.csv').then(r=>{if(!r.ok)throw Error('trial metrics unavailable');return r.text();}),fetch('data/manifest.json').then(r=>r.json())]);
    data={summary:parseCsv(summaryText),trials:parseCsv(trialsText)};
    $('included-count').textContent=manifest.trial_count;
    const available=new Set(data.summary.map(r=>r.scenario));
    const scenarioNames=['sudden_burst','alternating_bursts',...new Set(data.summary.map(r=>r.scenario))].filter((v,i,a)=>available.has(v)&&a.indexOf(v)===i);
    fillSelect($('scenario'),scenarioNames,x=>x.replaceAll('_',' '));
    fillSelect($('condition'),['baseline','delayed','noisy','combined']);
    fillSelect($('path'),[...new Set(data.summary.map(r=>r.initial_path))]);
    $('scenario').value='sudden_burst';$('condition').value='combined';$('path').value='s1-s2-s4';
    ['scenario','condition','path','metric'].forEach(id=>$(id).addEventListener('change',draw));draw();
  }catch(error){$('results-table').innerHTML=`<tr><td colspan="4">Could not load campaign data: ${error.message}</td></tr>`;}
}
init();
