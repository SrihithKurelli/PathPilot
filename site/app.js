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
const conditionOrder = ["baseline", "delayed", "noisy", "combined"];
const $ = id => document.getElementById(id);

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const parseLine = line => {
    const out=[]; let field="", quoted=false;
    for(let i=0;i<line.length;i++) {
      const c=line[i];
      if(c==='"'&&line[i+1]==='"'&&quoted){field+='"';i++;}
      else if(c==='"') quoted=!quoted;
      else if(c===','&&!quoted){out.push(field);field="";}
      else field+=c;
    }
    out.push(field); return out;
  };
  const header=parseLine(lines.shift());
  return lines.filter(Boolean).map(line=>Object.fromEntries(parseLine(line).map((v,i)=>[header[i],v])));
}
function fillSelect(select, values, pretty=x=>x, preferred=null) {
  select.replaceChildren(...values.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=pretty(v);return o;}));
  if(preferred && values.includes(preferred)) select.value=preferred;
}
function numeric(row,key) {
  const value=row?.[key];
  if(value===null||value===undefined||String(value).trim()==="") return null;
  const n=Number(value); return Number.isFinite(n)?n:null;
}
function scenarioRows() { return data.summary.filter(r=>r.scenario===$('scenario').value); }
function conditionRows() { return scenarioRows().filter(r=>r.condition===$('condition').value); }
function policySamples() { return conditionRows().filter(r=>r.initial_path===$('path').value); }
function metricRows(rows,key) {
  return rows.filter(r=>(numeric(r,`${key}_n`)??0)>0 && numeric(r,`${key}_mean`)!==null
    && numeric(r,`${key}_ci95_low`)!==null && numeric(r,`${key}_ci95_high`)!==null);
}
function hasPolicyVariation(rows,key) {
  const observed=metricRows(rows,key);
  if(observed.length<2) return false;
  const means=observed.map(r=>numeric(r,`${key}_mean`));
  const low=Math.min(...means),high=Math.max(...means);
  return high-low>Math.max(1e-9,Math.abs(high)*1e-9);
}
function refreshConditions(preferred="combined") {
  const values=[...new Set(scenarioRows().map(r=>r.condition))].sort((a,b)=>conditionOrder.indexOf(a)-conditionOrder.indexOf(b));
  fillSelect($('condition'),values,x=>x,preferred);
}
function refreshPaths(preferred=null) {
  const values=[...new Set(conditionRows().map(r=>r.initial_path))].sort();
  fillSelect($('path'),values,x=>x,preferred);
}
function refreshMetrics(preferred=$('metric').value) {
  const rows=policySamples();
  const available=Object.keys(metricInfo).filter(key=>hasPolicyVariation(rows,key));
  fillSelect($('metric'),available,key=>`${metricInfo[key].title} (${metricInfo[key].unit}) · ${metricInfo[key].direction}`,preferred);
  $('metric').disabled=available.length<=1;
  return available;
}
function showNoComparableData() {
  const svg=$('chart'); svg.replaceChildren(); svg.setAttribute('viewBox','0 0 900 360');
  const msg=document.createElementNS(svg.namespaceURI,'text');
  msg.setAttribute('x','450');msg.setAttribute('y','170');msg.setAttribute('text-anchor','middle');msg.setAttribute('fill','#a6b5c9');msg.setAttribute('font-size','14');
  msg.textContent='No comparable metric varies across policies in this slice.';svg.append(msg);
  const hint=document.createElementNS(svg.namespaceURI,'text');
  hint.setAttribute('x','450');hint.setAttribute('y','198');hint.setAttribute('text-anchor','middle');hint.setAttribute('fill','#71829a');hint.setAttribute('font-size','11');
  hint.textContent='Choose another scenario, telemetry condition, or bottleneck path.';svg.append(hint);
  $('chart-title').textContent='No chartable metric for this slice';
  $('chart-description').textContent='Metrics with missing samples or identical policy means are hidden.';
  $('chart-unit').textContent='—';$('results-table').innerHTML='<tr><td colspan="4">No comparable observations for this selection.</td></tr>';
  $('legend').replaceChildren();$('chart-export').style.display='none';
}
function draw() {
  const rows=policySamples(),metric=$('metric').value;
  if(!metric || !hasPolicyVariation(rows,metric)){showNoComparableData();return;}
  const info=metricInfo[metric],observed=metricRows(rows,metric);
  const plot=`${$('scenario').value}__${$('condition').value}__${$('path').value}__${metric}.svg`;
  $('chart-export').href=`data/plots/${plot}`;$('chart-export').download=plot;$('chart-export').style.display='';
  const svg=$('chart');svg.replaceChildren();svg.setAttribute('viewBox','0 0 900 360');
  $('chart-title').textContent=`${info.title} by policy`;
  $('chart-description').textContent=`${$('scenario').selectedOptions[0]?.textContent.replaceAll('_',' ')} · ${$('condition').value} telemetry · ${$('path').value} bottleneck · ${info.direction}`;
  $('chart-unit').textContent=info.unit;
  const values=observed.flatMap(r=>[numeric(r,`${metric}_ci95_low`),numeric(r,`${metric}_ci95_high`)]).filter(v=>v!==null);
  let min=Math.min(...values),max=Math.max(...values);
  if(max-min<1e-12){const pad=Math.max(Math.abs(max)*.05,.5);min=max-pad;max+=pad;}
  else {const pad=(max-min)*.12;min=Math.max(0,min-pad);max+=pad;}
  const left=220,right=850,top=30,bottom=300,x=v=>left+(v-min)/(max-min)*(right-left);
  for(let tick=0;tick<=4;tick++) {
    const v=min+(max-min)*tick/4,xx=x(v),line=document.createElementNS(svg.namespaceURI,'line');
    line.setAttribute('x1',xx);line.setAttribute('x2',xx);line.setAttribute('y1',top);line.setAttribute('y2',bottom);line.setAttribute('stroke','#263750');svg.append(line);
    const t=document.createElementNS(svg.namespaceURI,'text');t.setAttribute('x',xx);t.setAttribute('y',326);t.setAttribute('text-anchor','middle');t.setAttribute('fill','#8495ab');t.setAttribute('font-size','11');t.textContent=v.toFixed(2);svg.append(t);
  }
  const table=[],shownPolicies=[];
  for(let i=0;i<policies.length;i++) {
    const p=policies[i],row=observed.find(r=>r.policy===p),y=58+i*51;if(!row) continue;
    const mean=numeric(row,`${metric}_mean`),lo=numeric(row,`${metric}_ci95_low`),hi=numeric(row,`${metric}_ci95_high`),n=numeric(row,`${metric}_n`)??0;
    const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x',8);text.setAttribute('y',y+4);text.setAttribute('fill','#d6e2f0');text.setAttribute('font-size','12');text.textContent=labels[p];svg.append(text);
    const range=document.createElementNS(svg.namespaceURI,'line');range.setAttribute('x1',x(lo));range.setAttribute('x2',x(hi));range.setAttribute('y1',y);range.setAttribute('y2',y);range.setAttribute('stroke',colors[p]);range.setAttribute('stroke-width','4');range.setAttribute('stroke-linecap','round');svg.append(range);
    const dot=document.createElementNS(svg.namespaceURI,'circle');dot.setAttribute('cx',x(mean));dot.setAttribute('cy',y);dot.setAttribute('r',6);dot.setAttribute('fill',colors[p]);svg.append(dot);
    table.push(`<tr><td><i class="policy-dot" style="background:${colors[p]}"></i>${labels[p]}</td><td>${n}</td><td>${info.format(mean)}</td><td>${info.format(lo)} – ${info.format(hi)}</td></tr>`);
    shownPolicies.push(p);
  }
  const axis=document.createElementNS(svg.namespaceURI,'text');axis.setAttribute('x',(left+right)/2);axis.setAttribute('y',354);axis.setAttribute('text-anchor','middle');axis.setAttribute('fill','#71829a');axis.setAttribute('font-size','10');axis.textContent=`Mean ${info.title} (${info.unit}) with trial-level bootstrap 95% interval`;svg.append(axis);
  $('results-table').innerHTML=table.join()||'<tr><td colspan="4">No measured values for this selection.</td></tr>';
  $('legend').innerHTML=shownPolicies.map(p=>`<span><i style="background:${colors[p]}"></i>${labels[p]}</span>`).join('');
}

let data;
async function init() {
  try {
    const [summaryText,manifest]=await Promise.all([
      fetch('data/FINAL_CAMPAIGN_SUMMARY.csv').then(r=>{if(!r.ok)throw Error('summary unavailable');return r.text();}),
      fetch('data/manifest.json').then(r=>r.json())
    ]);
    data={summary:parseCsv(summaryText)};$('included-count').textContent=manifest.trial_count;
    const available=new Set(data.summary.map(r=>r.scenario));
    const scenarios=['sudden_burst','alternating_bursts',...available].filter((v,i,a)=>available.has(v)&&a.indexOf(v)===i);
    fillSelect($('scenario'),scenarios,x=>x.replaceAll('_',' '),'sudden_burst');
    refreshConditions('combined');refreshPaths('s1-s2-s4');
    refreshMetrics('tcp_app_rtt_p99_ms');draw();
    $('scenario').addEventListener('change',()=>{refreshConditions();refreshPaths();refreshMetrics();draw();});
    $('condition').addEventListener('change',()=>{refreshPaths();refreshMetrics();draw();});
    $('path').addEventListener('change',()=>{refreshMetrics();draw();});
    $('metric').addEventListener('change',draw);
  } catch(error) {
    $('results-table').innerHTML=`<tr><td colspan="4">Could not load campaign data: ${error.message}</td></tr>`;
  }
}
init();
