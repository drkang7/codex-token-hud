"use strict";
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.hash.slice(1));
const token = params.get("token") || "";
const requestedThreads=params.getAll("thread");
let current = requestedThreads[requestedThreads.length-1] || "", threads = [], mode = "time", first = null, last = null;
let activeRange = null, loading = false, metadata = null, lastLive = null;
let nativeAvailable = false, pinnedThread = "";
const fmt = (n, digits=1) => Number.isFinite(n) ? n.toLocaleString(undefined, {maximumFractionDigits:digits, minimumFractionDigits:digits}) : "—";
const date = n => Number.isFinite(n) ? new Date(n).toLocaleString() : "—";
const localInput = n => { const d=new Date(n); return new Date(n-d.getTimezoneOffset()*60000).toISOString().slice(0,19); };
function notice(text, error=false){$("notice").textContent=text;$("notice").classList.toggle("error",error);}
async function api(path, body){
  const response=await fetch("/api/"+path,{method:body?"POST":"GET",cache:"no-store",headers:{"X-Hud-Token":token,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
  const value=await response.json();if(!response.ok)throw new Error(value.error||"读取失败");return value;
}
function threadQuery(force=false){return "thread="+encodeURIComponent(current)+(force?"&force=1":"");}
function renderThreads(){
  const query=$("threadSearch").value.trim().toLowerCase(), select=$("thread");select.replaceChildren();
  const matches=threads.filter(t=>!query||t.title.toLowerCase().includes(query)||t.id.toLowerCase().includes(query));
  const selected=threads.find(t=>t.id===current);
  const visible=selected&&!matches.includes(selected)?[selected,...matches]:matches;
  for(const t of visible){
    const option=document.createElement("option");option.value=t.id;option.textContent=t.title+" · "+t.id.slice(-8);option.title=t.title+" · "+t.id;select.append(option);
  }
  select.value=current;
  $("threadMatchCount").textContent=matches.length+" 个对话";$("searchEmpty").hidden=matches.length>0||!query;
}
function syncHudControls(){
  $("hudControls").hidden=!nativeAvailable;
  $("pinHud").hidden=!nativeAvailable||!current||pinnedThread===current;
  $("unpinHud").hidden=!nativeAvailable||!pinnedThread;
  $("hudState").textContent=!pinnedThread?"自动跟随桌面对话":pinnedThread===current?"已固定当前对话":"已固定其他对话";
  $("hudBinding").hidden=pinnedThread===current;
  const pinned=threads.find(t=>t.id===pinnedThread);
  $("hudBinding").textContent=!pinnedThread?"固定对话后，切换到其他应用仍会显示状态栏。":pinnedThread===current?
    "正在固定显示此对话。解除后将自动跟随桌面当前对话。":"当前固定："+(pinned?.title||pinnedThread);
}
function syncActions(){
  document.querySelectorAll("[data-api]").forEach(button=>{button.disabled=loading||!current;});
  syncHudControls();
}
async function loadThreads(force=false){
  const value=await api("threads"+(force?"?force=1":""));threads=value.threads;
  nativeAvailable=!!value.native_available;pinnedThread=value.pinned_thread_id||"";
  if(!current||!threads.some(t=>t.id===current))current=value.bound_thread_id||threads[0]?.id||"";
  renderThreads();syncActions();
  if(!current){$("selectedThread").textContent="暂无可读的本地对话";notice("未找到本地日志。请检查日志目录，然后点击立即刷新。",true);$("refresh").disabled=false;return;}
  await selectThread();
}
async function selectThread(){
  const id=current;first=null;last=null;metadata=null;lastLive=null;showRange(null);
  clearRangeError();
  for(const prefix of ["first","last"]){$(prefix+"Chosen").textContent="尚未选定"+(prefix==="first"?"首条":"末条")+"消息";$(prefix+"Chosen").dataset.chosen="false";$(prefix+"Query").value="";$(prefix+"Candidates").replaceChildren();}
  const t=threads.find(t=>t.id===id);$("threadMeta").textContent=t?`${t.segment_count} 段日志 · 更新 ${date(t.updated_at_ms)}`:"";$("threadMeta").title=id;
  $("selectedThread").textContent=t?.title||id;syncHudControls();
  notice("正在读取所选对话…");
  await updateLive();if(id!==current)return;
  preset(60);notice(params.get("compact")==="1"?"":"最近响应每秒读取");
  if(mode==="messages")await searchMessages("first");
}
function markPreset(minutes){document.querySelectorAll("[data-minutes], #allTime").forEach(button=>button.setAttribute("aria-pressed",button.id==="allTime"?minutes==="all":Number(button.dataset.minutes)===minutes));}
function preset(minutes){$("end").value=localInput(Date.now());$("start").value=localInput(Date.now()-minutes*60000);markPreset(minutes);clearRangeError();}
function clearRangeError(){ $("rangeError").hidden=true;for(const id of ["start","end","firstQuery","lastQuery"])$(id).removeAttribute("aria-invalid"); }
function rangeError(text,field){$("rangeError").textContent=text;$("rangeError").hidden=false;if(field){$(field).setAttribute("aria-invalid","true");$(field).focus();}throw new Error(text);}
async function historyInfo(query="",force=false){return api("messages?"+threadQuery(force)+"&q="+encodeURIComponent(query));}
async function searchMessages(prefix){
  const id=current;notice("正在索引此对话的用户消息…");
  const value=await historyInfo($(prefix+"Query").value);if(current!==id)return;
  metadata=value;const list=$(prefix+"Candidates");list.replaceChildren();
  for(const message of value.messages){
    const button=document.createElement("button"), stamp=document.createElement("time"), preview=document.createElement("span");
    stamp.textContent=date(message.at_ms);preview.textContent=message.preview;button.append(stamp,preview);
    button.addEventListener("click",()=>{if(prefix==="first")first=message;else last=message;$(prefix+"Query").value=message.preview;$(prefix+"Chosen").textContent="已选 · "+date(message.at_ms)+" · "+message.preview;$(prefix+"Chosen").dataset.chosen="true";list.replaceChildren();clearRangeError();});list.append(button);
  }
  notice(`共有 ${value.message_count} 条用户消息、${value.sample_count} 个响应。${value.messages.length?"请点击一条搜索结果确定边界。":"没有匹配的消息，请调整文字片段。"}`);
}
function showRange(result){
  const changed=result&&result.confirmed_at_ms!==activeRange?.confirmed_at_ms;
  activeRange=result;$("clearRange").hidden=!result;
  document.querySelector(".range-panel").dataset.hasRange=String(!!result);
  $("rangeState").textContent=result?"已确认 · 固定快照":"尚未确认范围";
  $("rangeCacheMeter").hidden=!Number.isFinite(result?.cache_percent);
  if(result&&Number.isFinite(result.cache_percent))$("rangeCacheMeter").value=result.cache_percent;
  for(const id of ["rangeRate","rangeCache","count","output","duration","coverage"])$(id).textContent="—";
  if(!result){$("rangeLabel").textContent="选择统计范围，然后点击确认。";$("coverage").textContent="确认后显示有效样本数";$("rangeNote").textContent="确认后保留统计快照，再次确认可更新。";return;}
  $("rangeRate").textContent=fmt(result.rate);$("rangeCache").textContent=fmt(result.cache_percent);
  $("count").textContent=fmt(result.sample_count,0);$("output").textContent=fmt(result.output_tokens,0);$("duration").textContent=fmt(result.duration_seconds)+" 秒";
  $("coverage").textContent=`计时 ${result.timed_samples}/${result.sample_count} · 缓存 ${result.cache_samples}/${result.sample_count}`;
  const b=result.bounds;$("rangeLabel").textContent=result.mode==="time"?date(b.start_ms)+" → "+date(b.end_ms):date(b.first.at_ms)+" → "+date(b.last.at_ms)+"（含末条回答）";
  const basis=result.timing_basis;
  $("rangeNote").textContent=(result.sample_count?`模型：${result.models.join(" / ")||"未知"}。流式计时 ${basis.stream||0} 次，请求计时 ${basis.request||0} 次。` : "此范围没有已记录的完成响应，请调整范围。")+
    (result.timed_samples<result.sample_count?` 其中用于速率计算的输出为 ${fmt(result.timed_output_tokens,0)} token。`:"")+
    ` 快照确认于 ${date(result.confirmed_at_ms)}。`+(result.warnings.length?" "+result.warnings.join("；"):"");
  if(changed&&!matchMedia("(prefers-reduced-motion: reduce)").matches)document.querySelector(".range-metrics").animate([{opacity:.5,transform:"translateY(3px)"},{opacity:1,transform:"translateY(0)"}],{duration:260,easing:"cubic-bezier(.2,.8,.2,1)"});
}
async function updateLive(force=false){
  if(!current)return;const id=current,value=await api("live?"+threadQuery(force));if(current!==id)return;
  lastLive=value;const m=value.metrics,s=m.last,age=s?Date.now()-s.measured_at_ms:Infinity;
  if("native_available" in value){nativeAvailable=!!value.native_available;pinnedThread=value.pinned_thread_id||"";syncHudControls();}
  const currentSample=s&&s.model===m.model&&!(m.turn_started_at_ms>s.measured_at_ms&&m.stage!=="idle");
  const valid=currentSample&&age<15*60*1000&&value.source.state==="ok";
  $("model").textContent=m.model||"模型尚无记录";$("liveRate").textContent=valid?fmt(s.rate):"—";$("liveCache").textContent=valid?fmt(s.cache_percent):"—";
  $("liveState").textContent=value.source.state!=="ok"?"日志暂不可读":m.stage==="generating"?"生成中":m.stage==="tools"?"工具运行中":!s?"等待计数":age>=15*60*1000?"历史响应":"已更新";
  $("liveState").dataset.state=value.source.state!=="ok"?"unreadable":!s?"waiting":age>=15*60*1000?"history":"current";
  $("liveTime").textContent=s?`统计时间 ${date(s.measured_at_ms)} · ${s.basis==="stream"?"模型流式计时":"请求计时，含首 token 等待"}`:"响应完成后才有计数，暂无完成响应";
  if(value.range&&(!activeRange||value.range.confirmed_at_ms!==activeRange.confirmed_at_ms))showRange(value.range);
  if(!value.range&&activeRange)showRange(null);
}
async function busy(button, operation){
  if(loading)return;loading=true;syncActions();button.setAttribute("aria-busy","true");
  const label=button.querySelector(".button-label"), original=label?.textContent;
  if(label&&button.dataset.busyLabel)label.textContent=button.dataset.busyLabel;
  try{await operation();}catch(e){if(button.id==="confirm"){$("rangeError").textContent=e.message;$("rangeError").hidden=false;}else notice(e.message,true);}finally{if(label)label.textContent=original;button.removeAttribute("aria-busy");loading=false;syncActions();if(!current)$("refresh").disabled=false;}
}
$("threadSearch").addEventListener("input",renderThreads);
$("thread").addEventListener("change",()=>{current=$("thread").value;selectThread().catch(e=>notice(e.message,true));});
for(const [id,newMode] of [["timeTab","time"],["messageTab","messages"]])$(id).addEventListener("click",()=>{
  mode=newMode;$("timeTab").setAttribute("aria-selected",mode==="time");$("messageTab").setAttribute("aria-selected",mode==="messages");
  $("timeTab").tabIndex=mode==="time"?0:-1;$("messageTab").tabIndex=mode==="messages"?0:-1;document.querySelector(".tabs").dataset.mode=mode;clearRangeError();
  $("timePane").hidden=mode!=="time";$("messagePane").hidden=mode!=="messages";
  if(mode==="messages"&&!first)busy($("firstFind"),()=>searchMessages("first"));
});
document.querySelector(".tabs").addEventListener("keydown",event=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;event.preventDefault();const id=event.key==="Home"?"timeTab":event.key==="End"?"messageTab":mode==="time"?"messageTab":"timeTab";$(id).click();$(id).focus();});
for(const id of ["start","end"])$(id).addEventListener("input",()=>{markPreset(null);clearRangeError();});
for(const prefix of ["first","last"])$(prefix+"Query").addEventListener("input",()=>{if(prefix==="first")first=null;else last=null;$(prefix+"Chosen").textContent="内容已修改，请查找并重新选择消息";$(prefix+"Chosen").dataset.chosen="false";clearRangeError();});
document.querySelectorAll("[data-minutes]").forEach(button=>button.addEventListener("click",()=>preset(Number(button.dataset.minutes))));
$("allTime").addEventListener("click",()=>busy($("allTime"),async()=>{metadata=await historyInfo();if(!metadata.start_ms)throw new Error("此对话没有用户消息记录");$("start").value=localInput(metadata.start_ms);$("end").value=localInput(Math.max((metadata.end_ms||0)+1000,Date.now()));markPreset("all");clearRangeError();notice("已选择全部记录，点击确认开始统计。");}));
for(const prefix of ["first","last"])$(prefix+"Find").addEventListener("click",()=>busy($(prefix+"Find"),()=>searchMessages(prefix)));
$("confirm").addEventListener("click",()=>busy($("confirm"),async()=>{
  const id=current;let selection;
  clearRangeError();
  if(mode==="messages"){if(!first||!last)rangeError("请从搜索结果中选定首尾两条消息。",!first?"firstQuery":"lastQuery");if(first.at_ms>last.at_ms)rangeError("末条消息必须晚于首条消息，请重新选择。","lastQuery");selection={mode,first_id:first.id,last_id:last.id};}
  else {const start=new Date($("start").value),end=new Date($("end").value);if(!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime()))rangeError("请填写有效的开始和结束时间。",!Number.isFinite(start.getTime())?"start":"end");if(start>end)rangeError("结束时间不能早于开始时间。","end");selection={mode,start:start.toISOString(),end:end.toISOString()};}
  notice("正在读取完整历史并计算…");const result=await api("range",{thread_id:id,selection});if(id!==current)return;showRange(result);notice("");
  if(innerWidth<=730)document.querySelector(".range-panel").scrollIntoView({block:"start",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});
}));
$("clearRange").addEventListener("click",()=>busy($("clearRange"),async()=>{await api("clear",{thread_id:current});showRange(null);notice("已返回最近响应统计。");}));
$("refresh").addEventListener("click",()=>busy($("refresh"),async()=>{
  const old=lastLive?.metrics.last?.measured_at_ms, listing=await api("threads?force=1");threads=listing.threads;nativeAvailable=!!listing.native_available;pinnedThread=listing.pinned_thread_id||"";
  if(!current||!threads.some(t=>t.id===current)){current=listing.bound_thread_id||threads[0]?.id||"";renderThreads();if(current)await selectThread();else notice("未找到本地日志，请检查日志目录。",true);return;}
  renderThreads();syncHudControls();await updateLive(true);
  if(mode==="messages")await searchMessages("first");
  notice("已重新扫描并读取最新日志 · "+new Date().toLocaleTimeString()+(old===lastLive?.metrics.last?.measured_at_ms?"；日志尚未记录新的完成响应。":"；发现新的响应统计。"));
}));
$("mini").addEventListener("click",()=>{const hash=new URLSearchParams({token,thread:current,compact:"1"});window.open("/#"+hash,"codex-token-hud-mini","width=500,height=590,resizable=yes,scrollbars=yes");});
$("pinHud").addEventListener("click",()=>busy($("pinHud"),async()=>{const id=current;await api("pin",{thread_id:id});pinnedThread=id;syncHudControls();notice("状态栏已固定此对话，切换应用后仍会显示。");}));
$("unpinHud").addEventListener("click",()=>busy($("unpinHud"),async()=>{await api("unpin",{thread_id:current});pinnedThread="";syncHudControls();notice("已解除固定，状态栏自动跟随当前桌面对话。");}));
if(params.get("compact")==="1")document.body.classList.add("compact");
loadThreads().catch(e=>notice(e.message,true));
setInterval(async()=>{if(loading||!current)return;try{await updateLive();}catch(e){notice(e.message,true);}},1000);
