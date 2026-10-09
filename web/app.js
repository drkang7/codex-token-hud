"use strict";
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.hash.slice(1));
const token = params.get("token") || "";
const requestedThreads=params.getAll("thread");
let current = requestedThreads[requestedThreads.length-1] || "", threads = [], mode = "time", first = null, last = null;
let activeRange = null, loading = false, metadata = null, lastLive = null;
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
  for(const t of threads){
    if(query&&!t.title.toLowerCase().includes(query)&&!t.id.toLowerCase().includes(query))continue;
    const option=document.createElement("option");option.value=t.id;option.textContent=t.title+" · "+t.id.slice(-8);option.title=t.title+" · "+t.id;select.append(option);
  }
  select.value=current;
}
async function loadThreads(force=false){
  const value=await api("threads"+(force?"?force=1":""));threads=value.threads;
  $("pinHud").hidden=!value.native_available;$("unpinHud").hidden=!value.native_available||!value.pinned_thread_id;
  if(!current||!threads.some(t=>t.id===current))current=value.bound_thread_id||threads[0]?.id||"";
  renderThreads();
  if(!current){notice("未找到可读的本地日志。可用 --codex-home 指定目录，或 --log 打开单个日志文件。",true);return;}
  await selectThread();
}
async function selectThread(){
  const id=current;first=null;last=null;metadata=null;lastLive=null;showRange(null);
  for(const prefix of ["first","last"]){$(prefix+"Chosen").textContent="尚未选定";$(prefix+"Candidates").replaceChildren();}
  const t=threads.find(t=>t.id===id);$("threadMeta").textContent=(t?`${t.segment_count} 个日志片段 · 最近活动 ${date(t.updated_at_ms)}`:"")+" · "+id;
  notice("正在读取所选对话…");
  await updateLive();if(id!==current)return;
  preset(60);notice("已连接，实时数据每秒更新。区间结果在点击确认后计算。");
  if(mode==="messages")await searchMessages("first");
}
function preset(minutes){$("end").value=localInput(Date.now());$("start").value=localInput(Date.now()-minutes*60000);}
async function historyInfo(query="",force=false){return api("messages?"+threadQuery(force)+"&q="+encodeURIComponent(query));}
async function searchMessages(prefix){
  const id=current;notice("正在索引此对话的用户消息…");
  const value=await historyInfo($(prefix+"Query").value);if(current!==id)return;
  metadata=value;const list=$(prefix+"Candidates");list.replaceChildren();
  for(const message of value.messages){
    const button=document.createElement("button"), stamp=document.createElement("time"), preview=document.createElement("span");
    stamp.textContent=date(message.at_ms);preview.textContent=message.preview;button.append(stamp,preview);
    button.addEventListener("click",()=>{if(prefix==="first")first=message;else last=message;$(prefix+"Query").value=message.preview;$(prefix+"Chosen").textContent=date(message.at_ms)+" · "+message.preview;list.replaceChildren();});list.append(button);
  }
  notice(`共有 ${value.message_count} 条用户消息、${value.sample_count} 个响应。${value.messages.length?"请点击一条搜索结果确定边界。":"没有匹配的消息，请调整文字片段。"}`);
}
function showRange(result){
  activeRange=result;$("clearRange").hidden=!result;
  for(const id of ["rangeRate","rangeCache","count","output","duration","coverage"])$(id).textContent="—";
  if(!result){$("rangeLabel").textContent="选择左侧范围，然后点击确认";$("rangeNote").textContent="确认后的结果为固定快照，不会随新消息改变。可随时返回最近响应。";return;}
  $("rangeRate").textContent=fmt(result.rate);$("rangeCache").textContent=fmt(result.cache_percent);
  $("count").textContent=fmt(result.sample_count,0);$("output").textContent=fmt(result.output_tokens,0);$("duration").textContent=fmt(result.duration_seconds)+" 秒";
  $("coverage").textContent=`计时 ${result.timed_samples}/${result.sample_count} · 缓存 ${result.cache_samples}/${result.sample_count}`;
  const b=result.bounds;$("rangeLabel").textContent=result.mode==="time"?date(b.start_ms)+" → "+date(b.end_ms):date(b.first.at_ms)+" → "+date(b.last.at_ms)+"（含末条回答）";
  const basis=result.timing_basis;
  $("rangeNote").textContent=(result.sample_count?`模型：${result.models.join(" / ")||"未知"}。流式计时 ${basis.stream||0} 次，请求计时 ${basis.request||0} 次。` : "此范围没有已记录的完成响应，请调整范围。")+
    (result.timed_samples<result.sample_count?` 其中用于速率计算的输出为 ${fmt(result.timed_output_tokens,0)} token。`:"")+
    ` 快照确认于 ${date(result.confirmed_at_ms)}。`+(result.warnings.length?" "+result.warnings.join("；"):"");
}
async function updateLive(force=false){
  if(!current)return;const id=current,value=await api("live?"+threadQuery(force));if(current!==id)return;
  lastLive=value;const m=value.metrics,s=m.last,age=s?Date.now()-s.measured_at_ms:Infinity;
  const currentSample=s&&s.model===m.model&&!(m.turn_started_at_ms>s.measured_at_ms&&m.stage!=="idle");
  const valid=currentSample&&age<15*60*1000&&value.source.state==="ok";
  $("model").textContent=m.model||"模型尚无记录";$("liveRate").textContent=valid?fmt(s.rate):"—";$("liveCache").textContent=valid?fmt(s.cache_percent):"—";
  $("liveState").textContent=value.source.state!=="ok"?"日志暂不可读":m.stage==="generating"?"生成中":m.stage==="tools"?"工具运行中":!s?"等待计数":age>=15*60*1000?"历史响应":"已更新";
  $("liveTime").textContent=s?`统计时间 ${date(s.measured_at_ms)} · ${s.basis==="stream"?"模型流式计时":"请求计时，含首 token 等待"}`:"响应完成后才有计数，暂无完成响应";
  if(value.range&&(!activeRange||value.range.confirmed_at_ms!==activeRange.confirmed_at_ms))showRange(value.range);
  if(!value.range&&activeRange)showRange(null);
}
async function busy(button, operation){if(loading)return;loading=true;button.disabled=true;try{await operation();}catch(e){notice(e.message,true);}finally{button.disabled=false;loading=false;}}
$("threadSearch").addEventListener("input",renderThreads);
$("thread").addEventListener("change",()=>{current=$("thread").value;selectThread().catch(e=>notice(e.message,true));});
for(const [id,newMode] of [["timeTab","time"],["messageTab","messages"]])$(id).addEventListener("click",()=>{
  mode=newMode;$("timeTab").setAttribute("aria-selected",mode==="time");$("messageTab").setAttribute("aria-selected",mode==="messages");
  $("timePane").hidden=mode!=="time";$("messagePane").hidden=mode!=="messages";
  if(mode==="messages"&&!first)busy($("firstFind"),()=>searchMessages("first"));
});
document.querySelectorAll("[data-minutes]").forEach(button=>button.addEventListener("click",()=>preset(Number(button.dataset.minutes))));
$("allTime").addEventListener("click",()=>busy($("allTime"),async()=>{metadata=await historyInfo();if(!metadata.start_ms)throw new Error("此对话没有用户消息记录");$("start").value=localInput(metadata.start_ms);$("end").value=localInput(Math.max((metadata.end_ms||0)+1000,Date.now()));notice("已选择此对话全部记录，点击确认开始统计。");}));
for(const prefix of ["first","last"])$(prefix+"Find").addEventListener("click",()=>busy($(prefix+"Find"),()=>searchMessages(prefix)));
$("confirm").addEventListener("click",()=>busy($("confirm"),async()=>{
  const id=current;let selection;
  if(mode==="messages"){if(!first||!last)throw new Error("请先从搜索结果中选定首尾两条用户消息");selection={mode,first_id:first.id,last_id:last.id};}
  else {const start=new Date($("start").value),end=new Date($("end").value);if(!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime()))throw new Error("请填写有效的起止时间");selection={mode,start:start.toISOString(),end:end.toISOString()};}
  notice("正在读取完整历史并计算…");const result=await api("range",{thread_id:id,selection});if(id!==current)return;showRange(result);notice("区间统计已确认，结果已保存。");
}));
$("clearRange").addEventListener("click",()=>busy($("clearRange"),async()=>{await api("clear",{thread_id:current});showRange(null);notice("已返回最近响应统计。");}));
$("refresh").addEventListener("click",()=>busy($("refresh"),async()=>{
  const old=lastLive?.metrics.last?.measured_at_ms, listing=await api("threads?force=1");threads=listing.threads;renderThreads();await updateLive(true);
  if(mode==="messages")await searchMessages("first");
  notice("已重新扫描并读取最新日志 · "+new Date().toLocaleTimeString()+(old===lastLive?.metrics.last?.measured_at_ms?"；日志尚未记录新的完成响应。":"；发现新的响应统计。"));
}));
$("mini").addEventListener("click",()=>{const hash=new URLSearchParams({token,thread:current,compact:"1"});window.open("/#"+hash,"codex-token-hud-mini","width=500,height=590,resizable=yes,scrollbars=yes");});
$("pinHud").addEventListener("click",()=>busy($("pinHud"),async()=>{await api("pin",{thread_id:current});$("unpinHud").hidden=false;notice("状态栏已固定此对话，可在其他应用前方显示；右键可解除固定。");}));
$("unpinHud").addEventListener("click",()=>busy($("unpinHud"),async()=>{await api("unpin",{thread_id:current});$("unpinHud").hidden=true;notice("已解除固定，状态栏自动跟随当前桌面对话。");}));
if(params.get("compact")==="1")document.body.classList.add("compact");
loadThreads().catch(e=>notice(e.message,true));
setInterval(async()=>{if(loading||!current)return;try{await updateLive();}catch(e){notice(e.message,true);}},1000);
