/* Isolated from the preserved Dash workbench: no external requests or model SDK. */
(function () {
'use strict';
if (!document.body.classList.contains('rules-app')) return;
const steps=[['투자자료 분석','자료를 읽고 검증할 주제와 근거를 찾습니다.'],['투자 가설 생성','규칙이 제안한 가설·반대 가설을 검토하고 확정합니다.'],['실사 질문 생성','확정 가설에 맞는 질문 세트를 구성합니다.'],['중요도 평가','지금 필요한 질문 3개와 선정 이유를 확인합니다.'],['새 증거 반영','원문·답변을 검토하고 다음 질문이 어떻게 바뀌는지 확인합니다.']];
let dealMode=false;
let project=null,step=1,qid=null,hid=null,detail=null,dirty=false,preview=null;
const $=id=>document.getElementById(id);
function el(tag,attrs,...children){const n=document.createElement(tag);for(const [k,v] of Object.entries(attrs||{})){if(k.startsWith('on')) n.addEventListener(k.slice(2),v);else if(k==='class')n.className=v;else if(k==='checked'||k==='disabled'||k==='hidden'||k==='required')n[k]=!!v;else if(k==='value')n.value=v??'';else if(v!==undefined&&v!==null)n.setAttribute(k,v);}for(const c of children.flat(Infinity)){if(c===null||c===undefined||c===false)continue;n.append(c instanceof Node?c:document.createTextNode(String(c)));}return n;}
const btn=(label,fn,primary=false,attrs={})=>el('button',{type:'button',class:primary?'r-primary':'',onclick:fn,...attrs},label);
const badge=(label,kind='')=>el('span',{class:'r-badge '+kind},label);
const card=(title,...body)=>el('section',{class:'r-card'},el('h3',{},title),...body);
const p=(value,cls='')=>el('p',{class:cls},value);
const fmt=(n,d=2)=>n===null||n===undefined?'미계산':Number(n).toLocaleString('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:d});
const prob=n=>n===null||n===undefined?'미설정':fmt(n*100,1)+'%';
const state=()=>project?.state;
const topicLabel=id=>state()?.hypotheses.find(h=>h.id===id)?.label||id;
const originLabel=id=>({company:'회사 제공',counterparty:'거래 상대방',independent:'독립 출처',analyst:'담당자 작성'})[id]||id;
const questions=()=>state()?.questions||[];
const currentQ=()=>questions().find(q=>q.id===qid);
const units=()=>state()?.documents.flatMap(d=>d.spans.map(s=>({...s,document:d})))||[];
function notify(message,error=false){$('r-notice').textContent=message;$('r-notice').className=error?'r-error':'';}
function guard(){if(!dirty)return true;if(!confirm('미저장 입력이 있습니다. 저장하지 않고 이동하시겠습니까? 취소하면 현재 화면에서 저장할 수 있습니다.'))return false;dirty=false;return true;}
async function api(path,body){const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});let data;try{data=await response.json();}catch{throw Error('요청을 처리하지 못했습니다. 서버 상태를 확인하세요.');}if(!response.ok)throw Error(data.error||'요청 처리 실패');return data;}
async function task(label,fn){$('r-busy-label').textContent=label;$('r-busy').hidden=false;try{return await fn();}catch(e){notify(e.message,true);return null;}finally{$('r-busy').hidden=true;}}
const hosted=document.body.dataset.hosted==='true';
const orionCaseId='orion-271560';
const isOrion=()=>state()?.case_study?.id===orionCaseId;
const isOrionOverview=()=>isOrion()&&step===1&&!dealMode;
let overviewGroup=null;
let catalog=[];
function addCaseOptions(){
  if(!hosted||!catalog.length)return;
  const labels={'logistics-alpha':'사례 A','spirits-beta':'사례 B'};
  const options=catalog.map(c=>el('option',{value:'case:'+c.id},[labels[c.id],c.title].filter(Boolean).join(' · ')));
  $('r-project').append(el('optgroup',{label:'공개 사례 열기·이어하기'},options));
}
async function projects(){
  const rows=await api('/api/projects');
  const options=rows.map(r=>el('option',{value:r.id},r.company+' · '+r.period));
  $('r-project').replaceChildren(el('option',{value:''},'프로젝트 선택'));
  addCaseOptions();
  if(rows.length)$('r-project').append(...(hosted?[el('optgroup',{label:'내 프로젝트'},options)]:options));
  if(project)$('r-project').value=project.id;
}
async function load(id){const value=await api('/api/projects/'+id);project=value;dirty=false;preview=null;localStorage.setItem('orion-rule-project',id);if(qid&&!questions().some(q=>q.id===qid))qid=null;if(hid&&!state().hypotheses.some(h=>h.id===hid))hid=null;render();}
async function action(name,data={}){if(!project)return;return task('검토 내용 저장 중…',async()=>{const value=await api('/api/projects/'+project.id+'/actions/'+name,{...data,version:project.version});project=value;dirty=false;preview=null;render();notify('저장했습니다. 새 버전과 변경 이력을 저장했습니다.');return value;});}
function field(name,label,value='',type='text',required=false){let input;if(type==='textarea')input=el('textarea',{name,required,rows:3,maxlength:6000},value||'');else input=el('input',{name,type,required,value,step:type==='number'?'any':undefined});if(type==='number'){input.removeAttribute('required');if(required)input.required=true;}return el('label',{},label,input);}
function check(name,label,value=false){return el('label',{class:'r-check'},el('input',{name,type:'checkbox',checked:value}),label);}
function select(name,label,options,value){const input=el('select',{name},...options.map(([key,title])=>el('option',{value:key},title)));input.value=value??options[0]?.[0]??'';return el('label',{},label,input);}
function formValues(form){const result=Object.fromEntries(new FormData(form));form.querySelectorAll('input[type=number]').forEach(n=>{result[n.name]=n.value===''?null:Number(n.value);});form.querySelectorAll('input[type=checkbox]').forEach(n=>{result[n.name]=n.checked;});if(result.practice!==undefined)result.practice=result.practice==='true';return result;}
async function caseCatalog(){catalog=await api('/api/cases');$('r-case-library').hidden=hosted||!catalog.length;$('r-case').replaceChildren(...catalog.map(c=>el('option',{value:c.id},c.title)));return catalog;}
async function openCase(key){if(!guard())return;$('r-case').value=key;await task('사례 불러오는 중…',async()=>{project=await api('/api/cases/'+encodeURIComponent(key)+'/open',{});dealMode=false;step=1;detail=null;qid=null;hid=null;preview=null;dirty=false;localStorage.setItem('orion-rule-project',project.id);await projects();render();notify(isOrion()?'오리온 공개자료와 검토 이력을 불러왔습니다.':'익명화 사례를 열었습니다. 4단계에서 실습 가정을 적용하고 5단계에서 증거를 반영할 수 있습니다.');});}
const downloadLabel=d=>d.masked?'마스킹 텍스트 다운로드':'원본 파일 다운로드';
const orionSourceURL=source=>'/case-sources/'+orionCaseId+'/'+encodeURIComponent(source.id);

async function showOrionSource(source,page){
  const dialog=$('r-source-dialog');
  const url=orionSourceURL(source);
  const viewerURL=url+(page?'#page='+page:'');
  const body=el('div',{class:'r-source-body'});
  const pdf=source.format==='.pdf';
  const originalTab=el('a',{href:viewerURL,target:'_blank',rel:'noopener'},'PDF 원본 새 탭에서 열기');
  dialog.replaceChildren(
    el('div',{class:'r-source-dialog-header'},
      el('div',{},el('small',{},source.folder),el('h2',{id:'r-source-title'},source.filename)),
      btn('닫기',()=>dialog.close())),
    el('div',{class:'r-source-toolbar'},
      pdf?originalTab:null,
      el('a',{href:url+'?download=1'},'원본 파일 다운로드')),
    body);
  if(!dialog.open)dialog.showModal();
  if(pdf){
    await showPDFPages(body,source,page||1,originalTab);
    return;
  }
  body.append(p('워크시트를 불러오는 중입니다.','r-muted'));
  try{
    const sheets=await api(url+'?view=worksheet');
    const tab=select('sheet','워크시트',sheets.map((sheet,index)=>[String(index),sheet.title]),'0');
    const output=el('div',{class:'r-sheet-preview'});
    function showSheet(){
      const sheet=sheets[Number(tab.querySelector('select').value)];
      const columns=Array.from({length:Math.max(...sheet.rows.map(row=>row.length))},(_,i)=>i)
        .filter(i=>sheet.rows.some(row=>row[i]));
      const alphabet=index=>index<26?String.fromCharCode(65+index):
        alphabet(Math.floor(index/26)-1)+String.fromCharCode(65+(index%26));
      output.replaceChildren(table(['행',...columns.map(alphabet)],sheet.rows
        .map((row,index)=>[index+1,...columns.map(col=>row[col]||'')])));
    }
    tab.onchange=showSheet;
    body.replaceChildren(tab,p('원본 셀의 값 또는 수식을 표시합니다. 빈 열은 접었습니다.','r-form-help'),output);
    showSheet();
  }catch(error){
    body.replaceChildren(p(error.message,'r-error'));
  }
}

async function showPDFPages(body,source,page,originalTab){
  const url=orionSourceURL(source);
  let pages=source.total_units;
  if(!pages){
    try{pages=(await api(url+'?view=details')).total_units;}
    catch{body.append(el('iframe',{class:'r-source-pdf',src:originalTab.href,title:source.filename}));return;}
  }
  const panel=el('div',{class:'r-pdf-page'});
  const number=el('input',{type:'number','aria-label':'PDF 페이지 번호',min:1,max:pages,value:page});
  const previous=btn('이전 쪽',()=>show(page-1));
  const next=btn('다음 쪽',()=>show(page+1));
  const controls=el('div',{class:'r-pdf-controls'},previous,number,el('span',{},'/ '+pages+'쪽'),next);
  function show(requested){
    page=Math.max(1,Math.min(pages,requested));
    number.value=page;
    previous.disabled=page===1;
    next.disabled=page===pages;
    originalTab.href=url+'#page='+page;
    const image=el('img',{src:url+'?view=page&page='+page,alt:source.filename+' '+page+'쪽'});
    image.onerror=()=>panel.replaceChildren(el('iframe',{class:'r-source-pdf',src:originalTab.href,title:source.filename}));
    panel.replaceChildren(image);
    panel.scrollTop=0;
  }
  number.onchange=()=>show(Number.parseInt(number.value,10)||page);
  number.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();show(Number.parseInt(number.value,10)||page);}};
  body.append(controls,panel);
  show(page);
}

async function openOrionReview(group){
  if(!guard())return;
  if(!state().case_study.active_groups.includes(group)){
    const changed=await action('case_documents',{group});
    if(!changed)return;
  }
  jump(5);
  const sample=state().case_study.evidence_samples.find(row=>row.packet===group);
  const applied=state().evidence.some(e=>e.span===sample.span&&e.status==='approved');
  if(applied){
    qid=sample.question;
    renderMain();
    detail={kind:'span',id:sample.span};
    renderRight();
  }else{
    fillCaseEvidence(sample);
  }
}

function renderOrionSources(root,reviewOnly=false){
  const c=state().case_study;
  const sources=c.source_catalog;
  const panels=[];
  for(const group of ['public','related-party','foreign-subsidiaries']){
    const label=c.groups[group];
    if(reviewOnly&&group==='public')continue;
    const documents=sources.filter(d=>d.group===group);
    const active=c.active_groups.includes(group);
    const sample=c.evidence_samples.find(row=>row.packet===group);
    const applied=sample&&state().evidence.some(e=>e.span===sample.span&&e.status==='approved');
    panels.push(el('section',{class:'r-source-group'},
      el('div',{class:'r-source-group-top'},el('h4',{},label),
        badge(applied?'검토 반영':active?'분석에 등록됨':'추가 증빙',applied?'r-green':'r-blue')),
      sample?btn(applied?'반영한 근거 보기':active?'근거 검토 열기':'폴더 등록·증거 검토',()=>openOrionReview(group),!applied):null,
      el('details',{class:'r-source-list'},el('summary',{},'원본 '+documents.length+'개'),
        el('ul',{},documents.map(source=>el('li',{},
          el('div',{},el('small',{},source.folder),el('strong',{},source.filename)),
          btn('원본 보기',()=>showOrionSource(source),false,{'aria-label':source.filename+' 원본 보기'})))))));
  }
  const annual=sources.find(d=>d.filename.includes('2026.03.18'));
  root.append(card(reviewOnly?'추가 자료를 증거로 검토':'데이터 소스 · 원본 '+sources.length+'개',
    p(reviewOnly?'폴더 자료를 등록한 뒤 원문과 판정 기준을 확인하고 미리보기를 적용하세요.':
      '공개 기초자료에서 시작합니다. 두 후속 폴더의 원본도 바로 열 수 있고, 등록한 자료는 5단계에서 검토합니다.','r-muted'),
    !reviewOnly&&annual?btn('2025 사업보고서 원본 보기',()=>showOrionSource(annual)):null,
    ...panels));
}

function overviewDelta(before,after,digits,unit,scale=1){
  if(!Number.isFinite(before)||!Number.isFinite(after))return null;
  const move=Number(((after-before)*scale).toFixed(digits));
  return move?el('span',{class:'r-overview-delta '+(move>0?'r-overview-up':'r-overview-down')},
    (move>0?'↑ +':'↓ −')+fmt(Math.abs(move),digits)+unit):null;
}

function overviewKpi(label,before,after,format,delta){
  return el('div',{class:'r-overview-kpi'+(delta?' r-overview-changed':'')},
    el('div',{class:'r-overview-kpi-top'},el('span',{},label),delta),
    el('strong',{},format(after)),
    el('small',{},delta?'이전 '+format(before):'현재'));
}

function overviewProbability(label,before,after){
  const change=overviewDelta(before,after,1,'%p',100);
  const shown=Number.isFinite(after);
  const start=Number.isFinite(before)?before:after;
  return el('div',{class:'r-overview-probability'},
    el('div',{},el('strong',{},label),el('span',{},change?prob(before)+' → '+prob(after):prob(after),change)),
    shown?el('div',{class:'r-overview-track','aria-hidden':'true'},
      el('i',{class:'r-overview-fill'+(change?' r-overview-moving '+(after>before?'r-overview-up':'r-overview-down'):''),
        style:`--probability-start:${start*100}%;width:${after*100}%`}),
      change?el('i',{class:'r-overview-previous',style:`left:${before*100}%`}):null):null);
}

async function changeOverviewEvidence(sample,approved){
  if(!guard())return;
  overviewGroup=sample.packet;
  const response=approved?await action('revoke',{id:approved.id}):await action('case_evidence',{group:sample.packet});
  if(response){
    notify(approved?'증빙 반영을 취소하고 지표를 다시 계산했습니다.':'증빙을 반영하고 지표와 실사 질문 순위를 다시 계산했습니다.');
    $('r-content').querySelector(`button[data-evidence="${sample.packet}"]`)?.focus({preventScroll:true});
  }
}

function overviewValueBars(name,before,after,digits,unit){
  const shown=[before,after].filter(Number.isFinite);
  const min=Math.min(0,...shown),max=Math.max(0,...shown);
  const span=max-min||1;
  const zero=-min/span*100;
  const changed=Boolean(overviewDelta(before,after,digits,''));
  const series=[['이전',before],['현재',after]].map(([label,value],index)=>{
    const position=(value-min)/span*100;
    const tone=index&&changed?(after>before?' r-overview-up':' r-overview-down'):'';
    return el('div',{class:'r-overview-value-row'},el('span',{},label),
      el('div',{class:'r-overview-value-track','aria-hidden':'true'},
        el('i',{class:'r-overview-zero',style:`left:${zero}%`}),
        Number.isFinite(value)?el('i',{class:'r-overview-value-fill '+(index?'r-overview-value-current':'')+tone,
          style:`left:${Math.min(zero,position)}%;width:${Math.abs(position-zero)}%;transform-origin:${value<0?'right':'left'}`}):null),
      el('strong',{},Number.isFinite(value)?fmt(value,digits)+unit:'미계산'));
  });
  return el('section',{class:'r-overview-value'},el('h4',{},name),series);
}

function renderOrionSummary(root,stage=1){
  const [after,before=after]=project.snapshots;
  const rows=state().case_study.evidence_samples.map(sample=>{
    const question=after.questions[sample.question];
    const topic=questions().find(q=>q.id===sample.question)?.topic;
    const approved=state().evidence.find(e=>e.span===sample.span&&e.question===sample.question&&e.status==='approved');
    return {sample,question,topic,approved,label:topicLabel(topic),source:state().review_sources?.[sample.packet]};
  });
  const previousStatus=new Map(before.evidence.map(e=>[e.id,e.status]));
  const changedEvidence=[...after.evidence].reverse().find(e=>previousStatus.get(e.id)!==e.status);
  const selected=rows.find(row=>row.sample.packet===overviewGroup)||
    rows.find(({sample})=>sample.span===changedEvidence?.span&&sample.question===changedEvidence?.question)||rows[0];
  const count=snapshot=>rows.filter(({sample})=>snapshot.evidence.some(e=>e.span===sample.span&&e.question===sample.question&&e.status==='approved')).length;
  const selector=select('overview_focus','정보가치 기준',rows.map(row=>[row.sample.packet,row.label]),selected.sample.packet);
  selector.onchange=event=>{overviewGroup=event.target.value;renderMain();$('r-content').querySelector('[name=overview_focus]')?.focus({preventScroll:true});};
  const oldQuestion=before.questions[selected.sample.question];
  const eq=selected.question;
  const evsiBefore=oldQuestion?.evsi?.unit===eq?.evsi?.unit?oldQuestion?.evsi?.net:null;
  const evsiUnit=eq?.evsi?' '+eq.evsi.unit:'';
  const metric=(name,a,b,digits,unit)=>overviewKpi(name,a,b,n=>Number.isFinite(n)?fmt(n,digits)+unit:'미계산',overviewDelta(a,b,digits,''));
  const changedRank=Object.keys(after.ranks).some(id=>before.ranks[id]!==after.ranks[id])||
    Object.keys(before.ranks).some(id=>before.ranks[id]!==after.ranks[id]);
  const evidencePanel=el('section',{class:'r-overview-panel'},el('h3',{},'증빙 반영'),
    rows.map(({sample,approved,label,source})=>el('div',{class:'r-overview-evidence-row','data-packet':sample.packet},
      el('div',{},el('h4',{},label),el('small',{},sample.label)),
      badge(approved?({support:'지지 반영',contradict:'반박 반영'}[approved.outcome]||'검토 반영'):'반영 대기',approved?'r-green':''),
      el('div',{class:'r-overview-source-actions'},
        source?btn('원문 보기',()=>showOrionSource(source,source.page),false,{'aria-label':label+' 원문 보기'}):null,
        btn(approved?'반영 취소':'증빙 반영',()=>changeOverviewEvidence(sample,approved),!approved,
          {'data-evidence':sample.packet,'aria-label':label+(approved?' 반영 취소':' 증빙 반영')})),
      el('details',{},el('summary',{},'판정 근거'),p(approved?.note||sample.note)))));
  const probabilityCards=rows.map(({topic,label})=>overviewKpi(label+' 가설',before.probabilities[topic],after.probabilities[topic],prob,
    overviewDelta(before.probabilities[topic],after.probabilities[topic],1,'%p',100)));
  const valueCards=[metric('EIG',oldQuestion?.eig,eq?.eig,3,' bit'),metric('EVSI · 비용 차감 후',evsiBefore,eq?.evsi?.net,1,evsiUnit)];
  const evidenceCount=metric('반영 증빙',count(before),count(after),0,' / '+rows.length);
  const questionCount=metric('남은 실사 질문',Object.keys(before.ranks).length,Object.keys(after.ranks).length,0,'개');
  const probabilityPanel=el('section',{class:'r-overview-panel'},el('div',{class:'r-overview-panel-head'},
    el('h3',{},'가설 확률'),stage===1?selector:null),
    rows.map(({topic,label})=>overviewProbability(label,before.probabilities[topic],after.probabilities[topic])),
    el('div',{class:'r-overview-ticks','aria-hidden':'true'},['0%','25%','50%','75%','100%'].map(mark=>el('span',{},mark))),
    p('확률과 효용은 수업용 가정입니다.','r-muted'));
  const priorityPanel=el('section',{class:'r-overview-panel r-overview-priority'},el('h3',{},'다음 실사 질문'),
    el('div',{class:'r-impact-rank-grid'},changedRank?impactPriority('반영 전',before):null,
      impactPriority(changedRank?'반영 후':'현재 우선순위',after,changedRank?before:null)));
  const valuesPanel=el('section',{class:'r-overview-panel'},el('div',{class:'r-overview-panel-head'},
    el('h3',{},'정보가치 변화'),stage===4?selector:null),
    overviewValueBars('EIG · 기대정보이득',oldQuestion?.eig,eq?.eig,3,' bit'),
    overviewValueBars('EVSI · 비용 차감 후',evsiBefore,eq?.evsi?.net,1,evsiUnit));
  const cards={
    1:[...probabilityCards,...valueCards,evidenceCount,questionCount],
    2:probabilityCards,
    3:[questionCount,evidenceCount],
    4:valueCards,
    5:[...probabilityCards,evidenceCount]
  };
  const primary={1:probabilityPanel,2:probabilityPanel,3:priorityPanel,4:valuesPanel,5:probabilityPanel};
  root.append(el('section',{class:'r-overview'+(stage===1?'':' r-overview-tab'),'aria-label':'증빙 반영과 지표 변화'},
    el('div',{class:'r-overview-kpis'},cards[stage]),
    el('div',{class:'r-overview-grid'},primary[stage],evidencePanel),
    stage===1?priorityPanel:null));
  if(stage===1)renderOrionSources(root);
}

function impactPriority(title,snapshot,previous){
  const list=el('ol',{class:'r-impact-ranks'});
  const ids=Object.keys(snapshot.ranks).sort((a,b)=>snapshot.ranks[a]-snapshot.ranks[b]).slice(0,3);
  for(const id of ids){
    const rank=snapshot.ranks[id];
    const oldRank=previous?.ranks[id];
    const isNew=previous&&!oldRank;
    const movement=isNew?'새로 추천':oldRank&&oldRank!==rank?`#${oldRank} → #${rank}`:'';
    list.append(el('li',{class:isNew?'r-impact-new':''},
      el('span',{class:'r-impact-rank'},'#'+rank),
      el('span',{},snapshot.questions[id].title,movement?el('small',{},movement):null)));
  }
  return el('section',{class:'r-impact-priority-list'},el('h5',{},title),ids.length?list:p('추천 질문 없음','r-muted'));
}

function evidenceImpact(value,{reveal=true,heading,showSource,animate=false}={}){
  const {before,after,evidence}=value;
  const prior=before.probabilities[evidence.hypothesis];
  const posterior=after.probabilities[evidence.hypothesis];
  const start=before.questions[evidence.question];
  const end=after.questions[evidence.question];
  const points=Number.isFinite(prior)&&Number.isFinite(posterior)?Math.round((posterior-prior)*1000)/10:null;
  const delta=points===null?'확률 미설정':points===0?'변동 없음':(points>0?'+':'−')+fmt(Math.abs(points),1)+'%p';
  const tone=reveal?{support:'support',contradict:'refute'}[evidence.outcome]||'neutral':'neutral';
  const verdict={support:'가설 지지',contradict:'가설 반박',insufficient:'증거 불충분',reopen:'질문 재개'}[evidence.outcome];
  const valueLabel=probability=>Number.isFinite(probability)?prob(probability):'미설정';
  const shownAfter=reveal?posterior:prior;
  const plot=Number.isFinite(prior)&&Number.isFinite(shownAfter)?el('div',{class:'r-impact-plot','aria-hidden':'true'},
    el('div',{class:'r-impact-rail',style:`--impact-start:${prior*100}%;--impact-end:${shownAfter*100}%;--impact-low:${Math.min(prior,shownAfter)*100}%;--impact-distance:${Math.abs(shownAfter-prior)*100}%;--impact-origin:${shownAfter>=prior?'left':'right'}`},
      el('i',{class:'r-impact-range'}),el('i',{class:'r-impact-origin'}),el('i',{class:'r-impact-marker'})),
    el('div',{class:'r-impact-ticks'},el('span',{},'0%'),el('span',{},'50%'),el('span',{},'100%'))):null;
  const beforeCard=el('div',{class:'r-impact-number'},el('span',{},'반영 전'),el('strong',{},valueLabel(prior)));
  const afterCard=el('div',{class:'r-impact-number r-impact-after'},el('span',{},'반영 후'),
    reveal?el('strong',{},valueLabel(posterior)):el('strong',{class:'r-impact-pending'},'반영 대기'));
  const qValue=(q,key)=>{
    if(key==='eig')return Number.isFinite(q?.eig)?fmt(q.eig,3)+' bit':'미계산';
    return Number.isFinite(q?.evsi?.net)?fmt(q.evsi.net,1)+' '+q.evsi.unit:'미계산';
  };
  const metric=(name,key)=>el('div',{class:'r-impact-metric'},el('span',{},name),
    el('strong',{},qValue(start,key),el('span',{'aria-hidden':'true'},' → '),qValue(end,key)));
  return el('section',{class:`r-impact-result r-impact-${tone}${animate?' r-impact-animate':''}`},
    heading?el('h3',{class:'r-impact-heading',tabindex:'-1'},heading):null,
    el('div',{class:'r-impact-hero'},
      el('div',{class:'r-impact-hero-top'},el('span',{},'가설 확률 · 시연용 가정'),
        reveal?el('strong',{class:'r-impact-verdict'},verdict):null),
      el('h4',{},value.hypothesis||topicLabel(evidence.hypothesis)),
      el('div',{class:'r-impact-numbers'},beforeCard,
        el('div',{class:'r-impact-shift'},el('span',{'aria-hidden':'true'},'→'),
          reveal?el('strong',{},delta):null),afterCard),
      plot),
    el('div',{class:'r-impact-evidence'},
      el('div',{},el('h4',{},reveal?'판정 근거':'확인할 실사 질문'),
        p(reveal?evidence.note:start?.title||end?.title||''),
        reveal&&end?el('small',{},'기존 질문 · '+end.status):null),
      showSource?btn('증빙 원문 보기',showSource):null),
    reveal?el('details',{class:'r-impact-evidence-note'},el('summary',{},'판정 상세와 원문 위치'),
      p((end?.title||''),'r-muted'),p(evidence.origin),p(evidence.application)):null,
    el('div',{class:'r-impact-priorities'},el('h4',{},'다음 실사 질문 순위'),
      el('div',{class:'r-impact-rank-grid'},
        impactPriority('반영 전',before),
        reveal?impactPriority('반영 후',after,before):
          el('section',{class:'r-impact-priority-list r-impact-standby'},el('h5',{},'반영 후'),p('증거 반영 후 공개')))),
    reveal&&start&&end?el('div',{class:'r-impact-metrics'},
      el('h4',{},'확인한 질문의 정보가치'),
      el('div',{},metric('EIG · 불확실성 감소','eig'),metric('EVSI · 비용 차감 후','evsi'))):null);
}

function orionSourceLink(source,page){
  return source.original?btn(page?'PDF '+page+'쪽 원본 보기':'문서 내 원본 보기',()=>showOrionSource(source,page)):null;
}
function fillCaseEvidence(sample){if(!guard())return;qid=sample.question;preview=null;detail=null;renderMain();renderRight();const form=$('r-evidence-form');for(const name of ['outcome','span','response','group','note']){const field=form.elements.namedItem(name);if(field)field.value=sample[name]||'';}form.elements.namedItem('practice').value=sample.simulated?'true':'false';dirty=true;if(sample.span){detail={kind:'span',id:sample.span};renderRight();}notify(sample.simulated?'가상 후속 증거를 입력했습니다. 실제 딜에서 받은 답변이 아닙니다. 검토 후 미리보기로 확인하세요.':'원문과 판정 초안을 불러왔습니다. 미리보기에서 변화를 확인한 뒤 적용하세요.');}
function documentSources(d){const root=el('div');let shown=0;const more=btn('원문 구간 더 보기',()=>append(50));function append(count){more.remove();const next=Math.min(shown+count,d.spans.length);root.append(...d.spans.slice(shown,next).map(s=>sourceButton(s.id)));shown=next;if(shown<d.spans.length){more.textContent='원문 구간 더 보기 · '+(d.spans.length-shown)+'개 남음';root.append(more);}}append(15);return root;}
function caseScenario(root){const c=state().case_study;if(!c)return;root.append(card('EIG·EVSI 계산 실습',p('확률·우도·효용·확보 비용은 실제 자료에서 추정한 값이 아닙니다. 실습 가정을 적용한 뒤 오른쪽 상세에서 수정할 수 있습니다.','r-muted'),c.scenario_enabled?badge('실습 가정 적용 중 · 실제 딜 확률 아님','r-warn'):btn('편집 가능한 실습 가정 적용',()=>action('case_scenario'),true)));}
function renderCaseOverview(root){const c=state().case_study;
root.append(metrics(c.metrics.map(m=>[m.label,m.value])));
root.append(card('거래안의 기준과 변화',p(c.description),table(['시점·자료','주요 구조','근거'],c.versions.map(v=>[v.label,v.detail,el('div',{},...v.refs.slice(0,2).map(sourceButton))])),p(c.note,'r-form-help')));
if(c.checks?.length)root.append(card('회사 제공 자료와 모델의 확인점',table(['확인 항목','수치·판단 범위','근거'],c.checks.map(x=>[x.label,x.detail,el('div',{},...x.refs.slice(0,3).map(sourceButton))]))));
const w=c.waterfall,peak=Math.max(...w.values.map(Math.abs));let running=0;
const wf=el('div',{class:'r-waterfall',role:'img','aria-label':w.labels.map((label,i)=>label+' '+fmt(w.values[i])+'억원').join(',')});
wf.style.gridTemplateColumns='repeat('+w.labels.length+',minmax(0,1fr))';
w.values.forEach((v,i)=>{const total=i===0||i===w.values.length-1,high=total?v:running,low=total?0:running+v;const bar=el('div',{class:'r-wf-column'},el('div',{class:'r-wf-plot'},el('span',{class:'r-wf-number',style:'bottom:'+((Math.max(high,low)/peak)*155+5)+'px'},fmt(v)),el('i',{class:total?'r-wf-total':'r-wf-outflow',style:'bottom:'+((Math.min(high,low)/peak)*155)+'px;height:'+(Math.abs(high-low)/peak*155)+'px'})),el('small',{},w.labels[i]));wf.append(bar);running=total?v:low;});
root.append(card(w.title,wf,p(w.note,'r-form-help'),...w.refs.slice(0,2).map(sourceButton)));
const d=c.comparison||c.dilution,scale=d.scaleMax||100,threshold=c.comparison?d.threshold:50;
root.append(card(d.title,...d.labels.map((label,i)=>el('div',{class:'r-dilution-row'},el('div',{},label,el('strong',{},fmt(d.values[i],2)+(d.unit||'%'))),el('div',{class:'r-dilution-track'+(threshold===undefined?' r-no-threshold':''),style:threshold===undefined?'':'--r-threshold:'+(threshold/scale*100)+'%'},el('i',{style:'width:'+Math.max(0,Math.min(100,d.values[i]/scale*100))+'%;background:'+(threshold!==undefined?(d.values[i]<threshold?'#d67965':'#6478db'):i%2?'#4aada2':'#6478db')})))),p(d.note,'r-form-help'),...d.refs.slice(0,3).map(sourceButton)));
root.append(card('우선 검증 쟁점',...c.issues.map(issue=>el('div',{class:'r-case-issue'},btn(issue.title,()=>{if(!guard())return;qid=issue.question;jump(3);detail={kind:'question',id:qid};renderRight();}),p(issue.detail,'r-muted'),...issue.refs.slice(0,1).map(sourceButton))),p('가설·질문은 사례 구성자가 채택한 검토 초안입니다. 확정 실적·실사 완료·투자 승인을 의미하지 않습니다.','r-form-help')));
root.append(el('details',{class:'r-card'},el('summary',{},'익명화·자료 처리 범위'),p(c.masking),...state().documents.map(d=>p(d.filename+' · '+d.parsed_units+'/'+d.total_units+'개 텍스트 단위 · '+d.warnings.join(' '),'r-form-help'))));}
function sourceButton(ref){const s=units().find(x=>x.id===ref);return s?btn(s.document.filename+' · '+s.location,()=>openSpan(s),false,{class:'r-source-button'}):p('연결 원문 없음','r-muted');}
function openSpan(s){if(step!==5&&!guard())return;detail={kind:'span',id:s.id};renderRight();}
function chooseQ(id){if(!guard())return;qid=id;detail={kind:'question',id};renderRight();}
function table(headers,rows){return el('div',{class:'r-table-wrap'},el('table',{},el('thead',{},el('tr',{},...headers.map(h=>el('th',{},h)))),el('tbody',{},...rows.map(row=>el('tr',{},...row.map(v=>el('td',{},v)))))));}
function metrics(items){return el('div',{class:'r-metrics'},...items.map(([label,value])=>el('div',{class:'r-metric'},el('span',{},label),el('strong',{},value))));}
function probabilityBar(value){return el('div',{class:'r-prob-track',role:'img','aria-label':'가정 기반 가설 확률 '+prob(value)},el('span',{style:'width:'+Math.max(0,Math.min(100,(value||0)*100))+'%'}));}
function scoreParts(q){const colors={importance:'#6e73d9',gap:'#e9a154',obtainability:'#4aada2',eig:'#71a5df'},names={importance:'중요도',gap:'증빙 공백',obtainability:'확보 가능성',eig:'EIG'};const divisor=q.eig===null?.75:1;return el('div',{},el('div',{class:'r-score-parts',role:'img','aria-label':'추천 점수 구성'},...Object.entries(q.parts).map(([key,value])=>el('span',{style:`width:${value/divisor*100}%;background:${colors[key]}`}))),el('div',{class:'r-legend'},...Object.keys(q.parts).map(k=>el('span',{},el('i',{style:'background:'+colors[k]}),names[k]))));}
function jump(next){if(!guard())return;dealMode=false;step=next;preview=null;detail=null;render();$('r-content').scrollTop=0;}
function render(){renderFrame();renderMain();renderRight();renderFiles();}
function renderFrame(){document.body.classList.toggle('r-orion-overview',isOrionOverview());document.body.classList.toggle('r-orion-workflow',isOrion()&&step>1&&!dealMode);for(const [i,node] of [...$('r-nav').children].entries())node.setAttribute('aria-current',i+1===step?'step':'false');$('r-step-kicker').textContent='STEP '+String(step).padStart(2,'0')+' / 05';$('r-title').textContent=dealMode?'거래 구조·FDD 시각화':isOrionOverview()?'오리온 실사 대시보드':steps[step-1][0];$('r-description').textContent=isOrionOverview()?'증빙을 반영하고 가설 확률과 다음 질문의 변화를 확인하세요.':steps[step-1][1];$('r-project-heading').textContent=project?state().company+' · '+state().period:'근거에서 다음 질문으로';$('r-version').textContent=project?'저장됨 · v'+project.version:'';$('r-actions').replaceChildren();if(project){$('r-actions').append(el('a',{href:`/api/projects/${project.id}/export/csv`},'질문표 CSV'),el('a',{href:`/api/projects/${project.id}/export/json`},'검토 기록 JSON'),el('a',{href:`/api/projects/${project.id}/export/html`},'검토 보고서 HTML'));if(state().case_study)$('r-case').value=state().case_study.id;} }
function renderMain(){const root=$('r-content');root.replaceChildren();if(!project){root.append(el('div',{class:'r-empty'},el('h2',{},'다음에 무엇을 물어야 할까요?'),p('프로젝트를 선택하거나 새 자료를 등록하세요.'),catalog.some(c=>c.id===orionCaseId)?btn('오리온(271560) 사례 열기',()=>openCase(orionCaseId),true):btn('합성 검증 사례 열기',example,true)));return;}
if(!isOrion()||dealMode)root.append(el('div',{class:'r-stage-summary'},badge('자료 '+state().documents.length+'개'),badge('가설 '+state().hypotheses.length+'개'),badge('미해결 '+questions().filter(q=>q.eligible).length+'개'),badge('추천 '+state().recommendations.length+'개')));
if(!isOrion()&&state().case_study)root.append(el('div',{class:'r-card r-demo'},badge('익명화 실제 딜','r-blue'),p('자료 기반 검토 초안 · 확률·효용은 별도 실습 가정입니다.','r-form-help')));
if(state().demo)root.append(el('div',{class:'r-card r-demo'},badge('합성 예시','r-blue'),el('span',{},' 실제 기업 자료·실증 확률이 아닙니다. 입력 가정으로 계산 과정을 검증하는 사례입니다.')));
if(dealMode){window.OrionDealVisuals.render({root,projectId:project.id,data:state().visual_workspace,hasBudget:!!state().case_study?.waterfall,questions:questions(),units,sourceButton,el,p,card,btn,badge,field,select,check,fmt,table,metrics,formValues,guard,onAction:action,chooseQuestion:id=>{jump(3);chooseQ(id);},openExample:async()=>{await example();dealMode=true;render();}});return;}
if(isOrion()&&step>1)renderOrionSummary(root,step);
if(step===1)renderAnalysis(root);if(step===2)renderHypotheses(root);if(step===3)renderQuestions(root);if(step===4)renderRanking(root);if(step===5)renderEvidence(root);}
function renderFinancial(root){
 const facts=state().financial_facts||[],recon=state().reconciliations||[];
 const panel=card('재무 관측치 · 기간·단위·범위 검토',p('원문 기재를 구조화한 검토 초안입니다. Excel은 항목·값·단위·기간·범위·구분 열을 사용합니다. 검토 확인된 동일 기준의 서로 다른 문서만 대사합니다. 일반 문장의 숫자는 아래 원문 표현으로 보존합니다.','r-form-help'),el('a',{href:'/api/templates/financial.xlsx'},'합성 Excel 입력 양식 다운로드'));
 if(facts.length)panel.append(table(['항목·출처','값·단위','기간·범위·구분','검토'],facts.map(f=>[el('div',{},btn(f.metric,()=>{if(!guard())return;detail={kind:'fact',id:f.id};renderRight();}),sourceButton(f.span)),f.value+' '+(f.unit||'단위 미확인'),[f.period,f.scope,f.basis].map(v=>v||'미확인').join(' · '),btn(f.reviewed?'검토 완료 · 수정':'기준 검토',()=>{if(!guard())return;detail={kind:'fact',id:f.id};renderRight();})])));
 else panel.append(p('구조화 관측치가 없습니다. 자료 분석을 실행하거나 입력 양식을 참고하세요. 추출되지 않은 표를 자동으로 완료 처리하지 않습니다.','r-muted'));
 if(recon.length)panel.append(el('h4',{},'검토한 자료 간 대사'),table(['항목·기간','원천 1','원천 2','차이','판정'],recon.map(r=>[r.metric+' · '+r.period,fmt(r.left)+' '+r.unit,fmt(r.right)+' '+r.unit,fmt(r.difference)+' '+r.unit,r.status])),p('0이 아닌 차이는 해당 주제의 질문으로 연결됩니다. 원인·회계 조정 여부는 미판정이며, 기준을 수정하면 이전 차이 질문은 후속 조건 대기로 전환합니다.','r-form-help'));
 root.append(panel);
}
function researchPanel(root){
 const output=el('div',{id:'r-research-output'}),picker=select('research_question','계산을 살펴볼 질문',questions().map(q=>[q.id,q.title]),currentQ()?.id||state().recommendations[0]);
 const panel=card('계산 과정 · 민감도 · 추천 정책 비교',p('저장된 가정으로 결과를 설명하고, 가정을 바꾼 경우를 별도로 비교합니다. 저장된 판단이나 실제 추천은 변경하지 않습니다.','r-form-help'),picker,
 btn('계산 과정과 민감도 보기',async()=>{await task('가정별 결과 비교 중…',async()=>{
  const d=await api(`/api/projects/${project.id}/analysis?question=${encodeURIComponent(picker.querySelector('select').value)}`);output.replaceChildren();
  if(d.tree.available){const t=d.tree;output.append(card('답변별 의사결정 경로',p('현재 가설 확률 '+prob(t.prior)+' · 현재 최선 행동 '+(t.current_action?.actions.join(' / ')||'효용 미설정')),
    table(['답변','발생 확률','사후확률','불확실성 bits','최선 행동·기대효용'],t.answers.map(a=>[a.answer,prob(a.mass),prob(a.posterior),fmt(a.entropy,4),a.action?a.action.actions.join(' / ')+' · '+fmt(a.action.utility)+' '+t.unit:'판단 불가'])),p('가정 출처: '+t.source,'r-form-help')));}else output.append(p(d.tree.reason,'r-muted'));
  output.append(card('가정 민감도',p(d.note,'r-form-help'),table(['변경 가정','값','갱신 후 확률','EIG bits','EVSI 순효용','질문 순위','Top-3 유지 개수'],d.scenarios.map(s=>s.error?[s.parameter,s.value,s.error,'—','—','—','—']:[s.parameter,s.value,prob(s.probability),fmt(s.eig,4),s.evsi?fmt(s.evsi.net)+' '+s.evsi.unit:'미계산',s.rank||'대상 외',s.overlap+'/3']))));
  const names=ids=>ids.map(id=>questions().find(q=>q.id===id)?.title||id).join(' / ');
  output.append(card('같은 후보의 추천 비교',table(['방식','다음 질문 3개'],[['고정 체크리스트',names(d.comparison.fixed)],['정성 중요도',names(d.comparison.qualitative)],['Bayesian·EIG',names(d.comparison.eig)],...d.comparison.evsi.map(g=>['EVSI·비용 · '+g.unit+' · '+g.source,names(g.top3)])]),p('현재 프로젝트의 추천 비교는 효과 검증 점수가 아닙니다. EVSI 비교는 동일 단위·출처의 공통 효용 기준을 전제로 합니다.','r-form-help')));
 });},false));
 panel.append(output);root.append(panel);
 const evalOutput=el('div',{id:'r-evaluation-output'});
 root.append(el('details',{class:'r-card'},el('summary',{},'과제 검증 · 공유 가능한 합성 비교 실험'),p('실제 회사 자료를 전송하지 않습니다. 합성 사례 3개에서 동일 질문 후보와 15분 가정으로 정책을 비교합니다. 실제 기업 성능·독립 검증 결과는 아닙니다.','r-form-help'),btn('합성 비교 실험 실행',async()=>{await task('합성 실험 계산 중…',async()=>{const d=await api('/api/evaluation');evalOutput.replaceChildren(p(d.scope),table(['합성 사례','방식','핵심 질문 포함률','nDCG@3','첫 질문 순효용','답변 후 확률'],d.rows.map(r=>[r.case,r.arm,fmt(r.critical_recall*100,1)+'%',fmt(r.ndcg,3),fmt(r.first_evsi),prob(r.posterior)])),...d.limitations.map(v=>p(v,'r-form-help')),p('입력 SHA-256: '+d.input_sha256,'r-rule'));});}),evalOutput));
}
function renderFactDetail(root){
 const f=(state().financial_facts||[]).find(x=>x.id===detail?.id);if(!f)return false;
 const form=el('form',{id:'r-fact-form'},el('h3',{},'재무 관측치 검토'),sourceButton(f.span),p('원문은 바꾸지 않고 검토한 해석을 별도로 저장합니다. 단위·기간·범위·실적/계획을 확인하세요.','r-form-help'),
 field('metric','항목',f.metric,'text',true),field('value','값',f.value,'number',true),select('unit','단위',['원','천원','백만원','억원','USD','천USD','%'].map(x=>[x,x]),f.unit),field('period','기간 · 동일 비교 기준',f.period),field('scope','법인·연결·거래 범위',f.scope),field('basis','실적·계획·회계 정의',f.basis),field('review_note','검토 근거',f.review_note||'','textarea'),check('reviewed','출처와 비교 기준을 검토했습니다.',f.reviewed),el('button',{class:'r-primary'},'재무 관측치 검토 저장'));
 form.onsubmit=async e=>{e.preventDefault();await action('fact',{id:f.id,...formValues(form)});};root.append(form);return true;
}

function renderAnalysis(root){const docs=state().documents;if(isOrion())renderOrionSummary(root);else if(state().case_study)renderCaseOverview(root);else root.append(metrics([['등록 자료',docs.length],['추출 원문 구간',units().length],['검토할 가설',state().hypotheses.length]]));
const form=el('form',{id:'r-upload'},field('file','분석할 파일','','file',true),select('origin','자료 출처',[['company','회사 제공'],['counterparty','거래 상대방'],['independent','독립 출처'],['analyst','담당자 작성']],'company'),field('group','자료 의존 그룹 (기본: 파일명)','','text'),p('PDF·DOCX·PPTX·XLSX·TXT·MD·CSV / 파일당 10MB. 수식은 실행하지 않으며 스캔·복잡한 표는 검토가 필요합니다.','r-form-help'),el('button',{class:'r-primary'},'자료 등록·텍스트 추출'));
form.querySelector('[name=file]').accept='.pdf,.docx,.pptx,.xlsx,.txt,.md,.csv';form.onsubmit=async e=>{e.preventDefault();const body=new FormData(form);body.set('version',project.version);await task('자료 추출 중…',async()=>{project=await api(`/api/projects/${project.id}/documents`,body);dirty=false;render();notify(project.notice||'자료를 등록했습니다. 아래에서 분석 규칙을 실행하세요.');});};root.append(card('투자자료 등록',form));
root.append(el('div',{class:'r-actions'},btn('자료 분석·가설 초안 구성',()=>action('analyze'),true),btn('가설 검토로 이동 →',()=>jump(2))));
const search=el('form',{class:'r-inline-search'},el('input',{name:'query',placeholder:'원문 키워드 검색 · 예: 반복매출, 고객, 수금'}),el('button',{},'검색'));const results=el('div');search.onsubmit=async e=>{e.preventDefault();await task('근거 검색 중…',async()=>{const data=await api(`/api/projects/${project.id}/search?q=${encodeURIComponent(new FormData(search).get('query'))}`);results.replaceChildren(...(data.length?data.map(s=>card(s.filename+' · '+s.location,p(s.text.slice(0,260)),btn('원문 확인',()=>openSpan({...s,document:docs.find(d=>d.id===s.document)})))):[p('규칙으로 찾은 구간이 없습니다. 표현을 바꾸어 검색하거나 직접 확인하세요.')]));});};root.append(card('원문 근거 검색 · 로컬 BM25',search,results));renderFinancial(root);
if(state().hypotheses.length)root.append(card('규칙이 찾은 검토 주제',table(['검증 주제','검출 근거','해석'],state().hypotheses.map(h=>[h.label,h.refs.length?sourceButton(h.refs[0]):'규칙으로 관련 구간을 찾지 못함',h.refs.length?'관련 표현 검출 · 주장 진실성/충족 여부는 미판정':'미검출 · 자료 부재 또는 위험의 증명 아님']))));
if(state().findings?.length)root.append(card('원문에서 찾은 숫자·기간 표현 (해석 전)',
    table(['검토 주제','숫자 표현','원문'],state().findings.map(f=>[
        state().hypotheses.find(h=>h.id===f.topic)?.label||f.topic,
        f.numbers.length?f.numbers.join(' / '):'규칙 미검출',sourceButton(f.span)])),
    p('숫자를 자동으로 매출·성장률로 확정하거나 서로 다른 단위·기간을 합산하지 않습니다.','r-form-help')));
if(docs.length)root.append(card('자료 처리 범위',table(['자료','처리 상태','범위'],docs.map(d=>[btn(d.filename,()=>{detail={kind:'document',id:d.id};renderRight();}),d.status,d.parsed_units+' / '+d.total_units+' 구간 · 원문 '+d.spans.length+'개']))));}
function renderHypotheses(root){if(!state().hypotheses.length){root.append(el('div',{class:'r-empty'},p('자료 분석을 먼저 실행하면 가설 템플릿을 제안합니다.'),btn('자료 분석으로',()=>jump(1),true)));return;}root.append(p('가설은 검증 과제입니다. 숫자나 문구를 찾았다는 이유로 사실로 확정하지 않습니다.','r-muted'));for(const h of state().hypotheses){const node=card(h.label,el('div',{class:'r-card-header'},badge(h.origin_kind||(h.refs.length?'사례 작성·자료 연결':'기본 점검 과제 · 근거 미검출')),badge(h.approved?'검토 확정':'검토 전',h.approved?'r-good':'r-warn'),el('strong',{},prob(h.probability))),p(h.title),p('반대 가설: '+h.counter,'r-muted'),probabilityBar(h.probability),p(h.prior===null?'확률 가정 미설정':h.prior_source,'r-rule'),...h.refs.slice(0,2).map(sourceButton),btn('가설·확률 가정 검토',()=>{if(!guard())return;hid=h.id;detail={kind:'hypothesis',id:h.id};renderRight();}));root.append(node);}root.append(btn('확정 가설로 질문 구성 →',async()=>{if(await action('generate'))jump(3);},true));}
function questionList(rows){return table(['질문','가설·상태','정보량'],rows.map(q=>[el('div',{},btn(q.title,()=>chooseQ(q.id)),el('div',{},badge(q.mandatory?'필수 확인':topicLabel(q.topic),'r-blue')),el('small',{},q.request)),el('div',{},badge(q.status,q.status.startsWith('해소')?'r-good':'r-warn'),el('small',{},q.id)),el('span',{class:'r-numeric'},q.eig===null?'EIG 미계산':fmt(q.eig,4)+' bits')]));}
function renderQuestions(root){const active=questions().filter(q=>q.active&&!q.excluded);root.append(el('div',{class:'r-actions'},btn('질문 세트 구성·새 규칙 반영',()=>action('generate'),true),btn('중요도 평가 →',()=>jump(4))));if(active.length)root.append(card('현재 검토 질문 · '+active.length+'개',questionList(active)));else root.append(el('div',{class:'r-empty'},p('가설을 확정한 뒤 질문 세트를 구성하세요.'),btn('가설 검토로',()=>jump(2))));const future=questions().filter(q=>!q.active||q.excluded);if(future.length)root.append(el('details',{class:'r-card'},el('summary',{},'후속 조건 대기·제외 질문 '+future.length+'개'),p('부모 질문의 판정 결과에 따라 후속 질문이 활성화됩니다. 기존 질문과 증거 이력은 지우지 않습니다.','r-muted'),questionList(future)));
const approved=state().hypotheses.filter(h=>h.approved);if(approved.length){const f=el('form',{},select('topic','연결 가설',approved.map(h=>[h.id,h.label]),approved[0].id),field('title','직접 추가할 질문','','textarea',true),field('request','요청 자료','','textarea',true),field('criterion','완료 판정 기준','','textarea',true),el('button',{},'질문 추가'));f.onsubmit=async e=>{e.preventDefault();await action('custom',formValues(f));};root.append(el('details',{class:'r-card'},el('summary',{},'라이브러리에 없는 질문 직접 추가'),f));}}
function metricGuide(){
 const eig=card('EIG · 기대정보이득',p('Expected Information Gain','r-metric-english'),
  p('정의: 질문에 대한 가능한 답변을 받았을 때, 가설의 불확실성(엔트로피)이 평균적으로 얼마나 줄어드는지 나타냅니다.'),
  p('EIG = 현재 엔트로피 − 답변 후 엔트로피의 기댓값','r-formula'),
  p('왜 유용한가요? 한정된 실사 시간에 가설을 잘 구별할 수 있는 자료·질문을 먼저 찾습니다. 값이 클수록 더 많은 불확실성을 해소할 것으로 기대합니다.'),
  p('단위: bits. 현재의 이진 가설 모형에서는 0~1 bits이며, 현재 엔트로피가 상한입니다. 기업의 위험도나 투자 수익률을 뜻하지 않습니다.','r-muted'));
 const evsi=card('EVSI · 표본정보의 기대가치',p('Expected Value of Sample Information','r-metric-english'),
  p('정의: 추가 답변·증거를 바탕으로 최선의 행동을 선택할 때의 기대효용에서, 현재 정보로 최선의 행동을 선택할 때의 기대효용을 뺀 값입니다.'),
  p('EVSI = 정보 획득 후 최적 행동의 기대효용 − 현재 최적 행동의 기대효용','r-formula'),
  p('왜 유용한가요? 정보를 얻어 검토 진행·보류 판단이 개선될 여지가 얼마나 큰지 살펴봅니다. 확보·지연 비용까지 차감하면 추가 실사에 자원을 쓸 가치가 있는지 비교할 수 있습니다.'),
  p('단위: 설정한 효용점수 또는 금액. 비용 차감 후 = EVSI − 확보 비용 − 지연 비용. 비용 차감 전 EVSI는 0 이상이며, 차감 후에는 음수가 될 수 있습니다.','r-muted'));
 const box=el('section',{id:'r-information-guide','aria-label':'EIG와 EVSI 개념 설명'},el('div',{class:'r-information-heading'},el('h2',{},'EIG·EVSI 이해하기'),p('정의와 실사 의사결정에서의 활용')),
  el('div',{class:'r-information-grid'},eig,evsi),
  p('읽는 순서: EIG로 정보의 유용성을 보고 → EVSI로 판단 개선의 기대가치를 보고 → 비용 차감 후 값을 확인합니다. EIG가 높아도 모든 답변에서 같은 행동이 최선이면 EVSI는 0일 수 있습니다. 두 지표는 합산하지 않습니다.','r-information-note'),
  p('FDD 예시: 매출 반복성 검증이 가설의 불확실성을 줄여도 검토 진행·보류 판단을 바꾸지 못하면 EVSI는 작을 수 있습니다. 반대로 판단 경계에 있는 핵심 계약 증거는 판단 개선에 기여할 수 있습니다.','r-muted'),
  el('details',{},el('summary',{},'정의 참고 문헌'),el('p',{},el('a',{href:'https://pmc.ncbi.nlm.nih.gov/articles/PMC13558085/',target:'_blank',rel:'noopener noreferrer'},'EIG: Bayesian experimental design'), ' · ',el('a',{href:'https://pmc.ncbi.nlm.nih.gov/articles/PMC7373630/',target:'_blank',rel:'noopener noreferrer'},'EVSI: ISPOR Value of Information Task Force'))));
 return box;
}
function valueBars(rows,key,unit,label){
 const sorted=[...rows].sort((a,b)=>key==='eig'?b.eig-a.eig:b.evsi.net-a.evsi.net).slice(0,6);
 const values=sorted.map(q=>key==='eig'?q.eig:q.evsi.net);
 const low=Math.min(0,...values),high=Math.max(0,...values),span=high-low||1,zero=-low/span*100;
 const plot=el('div',{class:'r-value-bars',role:'group','aria-label':label});
 sorted.forEach(q=>{const value=key==='eig'?q.eig:q.evsi.net;
  const start=(Math.min(0,value)-low)/span*100,width=Math.abs(value)/span*100;
  const track=el('div',{class:'r-value-track','aria-hidden':'true'},el('i',{class:'r-value-zero',style:`left:${zero}%`}),el('span',{class:'r-value-fill '+(key==='eig'?'r-eig-fill':value<0?'r-negative-fill':'r-evsi-fill'),style:`left:${start}%;width:${width}%`}));
  plot.append(el('div',{class:'r-value-row'},btn(q.title,()=>chooseQ(q.id),false,{title:q.title}),track,el('strong',{},(key==='eig'?'EIG ':'비용 차감 후 ')+fmt(value,key==='eig'?4:2)+' '+unit)));
 });
 plot.append(p('막대 축: '+fmt(low,key==='eig'?4:2)+' ~ '+fmt(high,key==='eig'?4:2)+' '+unit+' · 그룹별 독립 축','r-form-help'),p('0 기준 막대 · '+(key==='eig'?'EIG':'비용 차감 후 값')+' 내림차순 · 상위 '+sorted.length+'개 · 전체 값은 아래 비교표에서 확인','r-form-help'));
 return plot;
}
function informationDashboard(rows){
 const section=el('section',{id:'r-information-dashboard','aria-label':'정보가치 비교 대시보드'});
 section.append(el('div',{class:'r-information-heading'},el('h2',{},'정보가치 분석 · EIG & EVSI'),p('더 많이 알려 주는 질문과 더 나은 판단으로 이어지는 질문을 비교합니다.')),p('대상: 현재 추천 대상인 검토 대기·보완 질문 '+rows.length+'개. 검토 완료·제외·후속 조건 대기 질문은 제외합니다. 답변을 받기 전의 기대값이며, 새 증거 반영 후 다시 계산됩니다.','r-form-help'));
 const info=rows.filter(q=>Number.isFinite(q.eig)),valued=rows.filter(q=>q.evsi);
 section.append(metrics([['EIG 계산 가능',info.length+' / '+rows.length],['EVSI 계산 가능',valued.length+' / '+rows.length],['비용 차감 후 양수',valued.filter(q=>q.evsi.net>0).length+'개']]));
 const charts=el('div',{class:'r-information-grid'});
 charts.append(card('EIG · 기대 불확실성 감소 (bits)',p('답변이 가설의 불확실성을 얼마나 줄일까요?','r-form-help'),info.length?valueBars(info,'eig','bits','EIG 비교 그래프'):p('EIG 미계산 · 가설 사전확률과 질문별 답변 우도·출처를 설정하세요. 아래 비교표에서 평가 가정을 열 수 있습니다.','r-empty')));
 const money=card('EVSI · 비용 차감 후 기대가치',p('답변이 판단을 개선하는 가치에서 확보·지연 비용을 뺀 값입니다. 효용 단위와 가정 출처별로 분리합니다. 단위가 같아도 효용 기준이 다르면 직접 비교할 수 없습니다.','r-form-help'));
 const groups=new Map();for(const q of valued){const group=JSON.stringify([q.evsi.unit,q.evsi.source]);if(!groups.has(group))groups.set(group,[]);groups.get(group).push(q);}
 for(const group of groups.values())money.append(el('h4',{},group[0].evsi.unit),p('가정 출처: '+group[0].evsi.source,'r-form-help'),valueBars(group,'net',group[0].evsi.unit,'비용 차감 후 EVSI 비교 그래프'));
 if(!valued.length)money.append(p('EVSI 미계산 · 확률·우도 모형에 더해 행동별 효용과 확보·지연 비용, 단위, 가정 출처가 필요합니다. 아래 비교표에서 평가 가정을 열어 입력하세요.','r-empty'));
 charts.append(money);section.append(charts,metricGuide());
 const lookup=card('정보가치 비교표 · 전체 추천 대상',p('값이 없는 항목은 미계산으로 표시합니다. EIG·EVSI는 각각의 질문을 현재 정보에서 단독으로 확인할 때의 기대값으로, 합계는 전체 실사의 정보가치가 아닙니다.','r-form-help'));
 lookup.append(table(['질문·가정 설정','EIG (bits)','EVSI · 비용 차감 전','확보·지연 비용','비용 차감 후','효용 단위·출처'],rows.map(q=>{
  const d=state().decisions[q.id],v=q.evsi;
  return [el('div',{},btn(q.title,()=>chooseQ(q.id)),el('small',{},q.id),btn('평가 가정 열기',()=>chooseQ(q.id))),
   el('div',{},Number.isFinite(q.eig)?'EIG '+fmt(q.eig,4)+' bits':'EIG 미계산',el('small',{},state().models[q.id]?.source||'확률·우도 가정 미설정')),
   v?fmt(v.gross):'EVSI 미계산',v?fmt(d.cost+d.delay):'미계산',
   v?el('strong',{class:v.net<0?'r-negative-text':'r-positive-text'},'비용 차감 후 '+fmt(v.net)):'미계산',
   v?el('div',{},v.unit,el('small',{},v.source)):'효용 시나리오 미설정'];
 })));
 section.append(lookup,p('계산의 전제: 사전확률·답변 우도·행동별 효용·비용은 담당자가 설정한 가정입니다. 실제 기업 자료만으로 자동 추정한 확률이나 검증된 거래가치가 아닙니다. 현재 EVSI는 진행/보류의 두 행동 모형이며, 가격·조건 재협상 효과는 포함하지 않습니다.','r-information-note'));
 return section;
}
function renderRanking(root){
 const eligible=questions().filter(q=>q.eligible).sort((a,b)=>a.rank-b.rank);
 root.append(informationDashboard(eligible));researchPanel(root);caseScenario(root);
 root.append(card('질문 추천 · 정보가치와 함께 검토',p('필수 확인을 우선하고 중요도 35% · 증빙 공백 25% · EIG 25% · 확보 가능성 15%로 추천합니다. EIG 미설정 시 나머지를 재정규화합니다. EVSI는 현재 추천 점수에 포함되지 않으며 별도로 비교합니다.','r-form-help')));
 for(const id of state().recommendations){const q=questions().find(q=>q.id===id);root.append(card('다음 질문 '+q.rank,el('h3',{},q.title),badge(q.provisional?'잠정 추천':'평가 설정 확인',q.provisional?'r-warn':'r-good'),p(q.reason,'r-muted'),scoreParts(q),p('추천 점수 '+fmt(q.score,1)+' · 중요도 '+q.importance+'/5'),el('div',{class:'r-actions'},btn('평가 가정 확인',()=>chooseQ(id)),btn('이 질문의 증거 반영',()=>{if(!guard())return;qid=id;jump(5);},true))));}
 if(!eligible.length)root.append(p('추천할 질문이 없습니다. 가설 확정·질문 구성 또는 후속 조건을 확인하세요.','r-empty'));
 else root.append(card('전체 추천 순서',table(['순위','질문','추천 점수'],eligible.map(q=>[q.rank,btn(q.title,()=>chooseQ(q.id)),fmt(q.score,1)]))));
}
function compare(before,after){
 const ids=[...new Set([...Object.keys(before.questions),...Object.keys(after.questions)])];
 const changed=ids.filter(id=>before.ranks[id]!==after.ranks[id]||before.questions[id]?.status!==after.questions[id]?.status||before.questions[id]?.active!==after.questions[id]?.active);
 const panel=card('질문·순위 변경',changed.length?table(['질문','이전','이후'],changed.map(id=>[after.questions[id]?.title||before.questions[id]?.title,(before.ranks[id]?'#'+before.ranks[id]:'추천 제외')+' · '+(before.questions[id]?.status||'없음'),(after.ranks[id]?'#'+after.ranks[id]:'추천 제외')+' · '+(after.questions[id]?.status||'없음')])):p('질문 상태와 추천 순서가 유지됩니다. 변경을 만들기 위해 임의의 순위를 넣지 않습니다.','r-muted'));
 const delta=ids.filter(id=>before.questions[id]?.eig!==after.questions[id]?.eig||before.questions[id]?.evsi?.net!==after.questions[id]?.evsi?.net);
 if(delta.length)panel.append(table(['질문','EIG 이전 → 이후','EVSI 순효용 이전 → 이후'],delta.map(id=>{
   const a=before.questions[id],b=after.questions[id];
   const value=q=>q&&Object.prototype.hasOwnProperty.call(q,'evsi')?(q.evsi?fmt(q.evsi.net)+' '+q.evsi.unit:'미계산'):'이전 기록 미보관';
   return [b?.title||a.title,fmt(a?.eig,4)+' → '+fmt(b?.eig,4),value(a)+' → '+value(b)];
 })));
 return panel;
}
function renderEvidence(root){if(!questions().length){root.append(p('가설과 질문을 먼저 구성하세요.','r-empty'));return;}if(isOrion()){const sources=el('details',{class:'r-card'},el('summary',{},'증빙 폴더와 원문'));renderOrionSources(sources,true);root.append(sources);}else if(state().case_study){caseScenario(root);root.append(card('증거 반영 실습',p('현재 자료를 확인하는 예시와 가상 후속 증거를 구분합니다. 예시는 입력만 채우며, 미리보기와 검토 후 적용해야 합니다.','r-form-help'),...state().case_study.evidence_samples.map(sample=>btn(sample.label,()=>fillCaseEvidence(sample)))));}if(!currentQ())qid=state().recommendations[0]||questions()[0].id;const q=currentQ();
const picker=select('question','반영할 질문',questions().map(x=>[x.id,x.title]),qid);picker.querySelector('select').onchange=e=>{if(!guard()){e.target.value=qid;return;}qid=e.target.value;preview=null;renderMain();renderRight();};root.append(card('증거를 연결할 질문',picker,p(q.request,'r-muted'),p('판정 기준: '+q.criterion)));
const u=units();const form=el('form',{id:'r-evidence-form'},el('input',{type:'hidden',name:'practice',value:'false'}),select('outcome','검토 결과',[['support','지지 증거 확인'],['contradict','반박 증거 확인'],['insufficient','불충분 · 확률 유지'],['reopen','질문 재개 · 확률 유지']],'support'),select('span','연결 원문 (또는 답변 직접 입력)',[['','답변 직접 입력 · 외부 검증 전'],...u.map(s=>[s.id,s.document.filename+' · '+s.location+' · '+s.text.slice(0,65)])],''),field('response','답변 원문 (원문 구간을 선택하지 않을 때)','','textarea'),field('group','증거 의존 그룹 (동일 원천은 같은 이름)','','text'),field('note','원문·판정 기준에 따른 검토 이유','','textarea',true),check('independent','이미 반영한 증거와 별개의 정보이며 독립성을 검토했습니다.'),p('독립성 미확인·동일 그룹은 추가 확률 반영을 보류합니다. 계약·검수·수금을 무조건 독립으로 인정하지 않습니다.','r-form-help'),isOrion()?null:check('reviewed','원문과 판정 기준을 검토했고, 아래 미리보기 결과의 적용/반려를 확인합니다.'),el('div',{class:'r-actions'},el('button',{class:'r-primary'},'적용 전 미리보기')));
form.querySelector('[name=span]').onchange=e=>{const s=u.find(s=>s.id===e.target.value);if(s){detail={kind:'span',id:s.id};renderRight();}};
const output=el('div',{id:'r-preview'});form.onsubmit=async e=>{e.preventDefault();await task('적용 전 결과 계산 중…',async()=>{const data={...formValues(form),question:qid,version:project.version};const value=await api(`/api/projects/${project.id}/preview`,data);preview={data,value};renderPreview(output);notify('미리보기입니다. 아직 증거와 확률을 저장하지 않았습니다.');});};form.oninput=e=>{if(e.target.name!=='reviewed'){preview=null;output.replaceChildren();}};form.onchange=e=>{if(e.target.name!=='reviewed'){preview=null;output.replaceChildren();}};root.append(card('새 답변·증거 검토',form),output);
if(project.snapshots.length>=2)root.append(el('details',{class:'r-card'},el('summary',{},'직전 저장 버전과 비교 · v'+project.snapshots[1].version+' → v'+project.snapshots[0].version),compare(project.snapshots[1],project.snapshots[0])));
const historyOutput=el('div');root.append(el('details',{class:'r-card'},el('summary',{},'이전 저장 버전 선택·비교'),btn('저장 버전 불러오기',async()=>{await task('이전 버전 확인 중…',async()=>{const snapshots=await api(`/api/projects/${project.id}/history`);const picker=select('before','비교할 이전 버전',snapshots.map(s=>[String(s.version),'v'+s.version+' · '+s.at]),String(snapshots[0].version));const display=el('div');const show=()=>{const old=snapshots.find(s=>String(s.version)===picker.querySelector('select').value),latest=snapshots[snapshots.length-1];display.replaceChildren(table(['가설','이전 확률','현재 확률'],Object.keys(latest.probabilities).map(h=>[topicLabel(h),prob(old.probabilities[h]),prob(latest.probabilities[h])])),compare(old,latest));};picker.onchange=show;historyOutput.replaceChildren(picker,display);show();});}),historyOutput));
for(const e of [...state().evidence].reverse()){root.append(card(e.status==='approved'?'적용 증거':e.status==='rejected'?'반려 증거':'철회 증거',badge(e.question,'r-blue'),e.practice?badge('실습용 가상 증거','r-warn'):null,badge({support:'지지',contradict:'반박',insufficient:'불충분',reopen:'재개'}[e.outcome]),p(e.application),p(e.origin+' · '+e.group,'r-muted'),p(e.note),e.status==='approved'?btn('적용 철회·이력 재생',async()=>{if(confirm('이 증거 적용을 철회하고 나머지 승인 증거를 다시 계산할까요?'))await action('revoke',{id:e.id});}):null));}
root.append(el('details',{class:'r-card'},el('summary',{},'프로젝트 변경 이력'),...state().history.slice().reverse().map(h=>el('div',{class:'r-history'},el('strong',{},h.action),p(h.detail),el('small',{},h.at)))));}
function renderPreview(output){if(!preview)return;const value=preview.value;const h=value.evidence.hypothesis;
  if(isOrion()){
    const span=units().find(u=>u.id===value.evidence.span);
    const showSource=span?.document.original?()=>showOrionSource(span.document,span.page):null;
    const hypothesis=state().hypotheses.find(row=>row.id===h)?.title;
    const confirmation=check('reviewed','원문과 판정 기준을 확인했습니다.');
    confirmation.querySelector('input').setAttribute('form','r-evidence-form');
    output.replaceChildren(evidenceImpact({...value,hypothesis},{heading:'증거 적용 미리보기',showSource,animate:true}),
      el('div',{class:'r-impact-review-actions'},confirmation,btn('검토 결과 적용',()=>commitPreview(false),true),btn('반려',()=>commitPreview(true))));
    output.querySelector('.r-impact-heading').focus();
    return;
  }
output.replaceChildren(card('증거 적용 미리보기',value.evidence.practice?badge('실습용 가상 증거','r-warn'):null,p('가설: '+topicLabel(h)+' · '+prob(value.before.probabilities[h])+' → '+prob(value.after.probabilities[h])),p(value.evidence.application),table(['질문','EIG 이전 → 이후','EVSI 순효용 이전 → 이후'],Object.keys(value.after.questions).filter(id=>value.before.questions[id]?.eig!==value.after.questions[id].eig||value.before.questions[id]?.evsi?.net!==value.after.questions[id].evsi?.net).map(id=>[value.after.questions[id].title,fmt(value.before.questions[id]?.eig,4)+' → '+fmt(value.after.questions[id].eig,4),fmt(value.before.questions[id]?.evsi?.net)+' → '+fmt(value.after.questions[id].evsi?.net)])),value.trace?.length?p('적용 우도비: '+(value.trace[value.trace.length-1].likelihood_ratio??'미계산')+' · '+value.trace[value.trace.length-1].application,'r-form-help'):null,compare(value.before,value.after),el('div',{class:'r-actions'},btn('검토 결과 적용',()=>commitPreview(false),true),btn('반려하고 현재 추천 유지',()=>commitPreview(true)))));}
async function commitPreview(reject){
  if(!preview)return;
  const f=$('r-evidence-form');
  if(!f.elements.namedItem('reviewed')?.checked){
    notify('원문과 판정 기준을 검토했다는 확인을 선택하세요.',true);
    return;
  }
  const data={...preview.data,reviewed:true,reject};
  const response=await action('evidence',data);
  if(!response)return;
  notify(reject?'반려 기록을 남겼습니다. 확률과 추천은 유지됩니다.':'증거를 적용하고 질문 상태·후속 질문·추천을 다시 계산했습니다.');
  if(isOrion()&&!reject)$('r-content').querySelector('.r-overview')?.scrollIntoView({block:'start'});
}
function renderRight(){const root=$('r-detail');root.replaceChildren();if(detail?.kind==='fact'&&renderFactDetail(root))return;if(!project){root.append(p('프로젝트를 만들고 자료·가설·질문을 선택하세요.'));return;}
if(detail?.kind==='span'){const s=units().find(s=>s.id===detail.id);if(s){root.append(el('h3',{},s.document.filename),p(s.location,'r-muted'),badge(s.document.status),p(s.text,'r-quote'),orionSourceLink(s.document,s.page),s.cell?card('Excel 셀 메타데이터',p('원래 값: '+s.cell.raw),p('수식: '+(s.cell.formula||'없음')),p('저장된 계산값: '+(s.cell.cached??'없음')),p('표시 형식: '+s.cell.number_format),p('시트: '+s.cell.sheet_state),s.cell.cached!==null&&s.cell.cached!==''&&Number.isFinite(Number(s.cell.cached))?btn('이 셀을 재무 관측치로 등록',async()=>{const v=await action('fact_new',{span:s.id});if(v){detail={kind:'fact',id:'manual_'+''};const f=state().financial_facts.find(x=>x.span===s.id);detail.id=f.id;renderRight();}}):null):null,p((s.document.masked?'마스킹 텍스트 해시: ':'원본 해시: ')+s.document.sha256,'r-rule'),el('a',{href:`/api/projects/${project.id}/files/${s.document.id}`},downloadLabel(s.document)));return;}}
if(detail?.kind==='document'){const d=state().documents.find(d=>d.id===detail.id);if(d){root.append(el('h3',{},d.filename),badge(d.status),p('버전 '+d.version+' · 출처 '+originLabel(d.origin)+' · 의존 그룹 '+d.group),p('처리 구간 '+d.parsed_units+' / '+d.total_units+' · 원문 조각 '+d.spans.length),...d.warnings.map(w=>p(w,'r-muted')),el('a',{href:`/api/projects/${project.id}/files/${d.id}`},downloadLabel(d)),p(d.sha256,'r-rule'),orionSourceLink(d),documentSources(d));return;}}
if(step===2&&detail?.kind==='hypothesis'){const h=state().hypotheses.find(h=>h.id===detail.id);if(h){const f=el('form',{id:'r-hypothesis-form'},el('h3',{},h.label),field('title','검증할 가설',h.title,'textarea',true),field('counter','반대 가설',h.counter,'textarea',true),check('approved','가설의 범위·기간·검증 기준을 검토하고 확정합니다.',h.approved),field('prior','사전확률 (0~1, 선택)',h.prior,'number'),field('prior_source','사전확률의 근거·가정',h.prior_source,'textarea'),p('자동 추정 확률이 아닙니다. 미설정 시 정성 추천만 제공합니다. 변경하면 승인된 증거를 새 사전확률에서 재생합니다.','r-form-help'),el('button',{class:'r-primary'},'가설 검토 저장'));f.onsubmit=async e=>{e.preventDefault();await action('hypothesis',{id:h.id,...formValues(f)});};root.append(f,...h.refs.slice(0,5).map(sourceButton));return;}}
const q=currentQ();if(q&&(step===3||step===4||step===5)){root.append(badge(q.id,'r-blue'),badge(q.status),el('h3',{},q.title),p('가정 기반 가설 확률: '+prob(q.probability)),p(q.eig===null?'EIG 미계산':`EIG ${fmt(q.eig,4)} bits`),p(q.reason,'r-muted'));
root.append(el('details',{class:'r-advanced'},el('summary',{},'관측 사실 · 검증 공백 · 질문 근거'),p(q.grounding?.observation||'관련 원문 미검출 · 기본 점검 과제'),p('검증 공백: '+q.criterion),p('연결 방식: '+(q.grounding?.method||'기존 연결')+' · 검색 결과는 사실 검증 완료를 뜻하지 않습니다.','r-form-help'),...q.refs.slice(0,3).map(sourceButton)));
if(step===5){root.append(p('요청 자료: '+q.request),p('판정 기준: '+q.criterion),...q.refs.slice(0,3).map(sourceButton));return;}
const model=state().models[q.id]||{};const f=el('form',{id:'r-question-form'},field('title','질문',q.title,'textarea',true),field('request','요청 자료',q.request,'textarea',true),field('criterion','해소 판정 기준',q.criterion,'textarea',true),el('div',{class:'r-mini-grid'},field('importance','중요도 (1~5)',q.importance,'number',true),field('obtainability','확보 가능성 (1~5)',q.obtainability,'number',true)),check('mandatory','필수 확인 질문으로 상단에 둡니다.',q.mandatory),check('excluded','현재 추천에서 제외합니다.',q.excluded));
const advanced=el('details',{class:'r-advanced'},el('summary',{},'확률·EIG 가정 설정 (선택)'),p('P(지지|H)와 P(지지|반대 H)를 입력합니다. 부정 결과는 각각의 여집합이며, 실제 기업에서 관측해 보정한 값이 아니라면 가정으로 표시해야 합니다.','r-form-help'),el('div',{class:'r-mini-grid'},field('a','P(지지|H)',model.a,'number'),field('b','P(지지|반대 H)',model.b,'number')),field('model_source','우도 가정의 출처',model.source||'','textarea'));
f.append(el('details',{class:'r-advanced'},el('summary',{},'중요도 평가 기준·증빙 공백'),p('1: 참고 사항 / 2: 제한적 영향 / 3: 추가 검증 필요 / 4: 판단·조건에 중요 / 5: 거래 판단의 핵심 검증 과제','r-form-help'),...Object.entries({missing:'자료 미수령',period:'기간·범위 불일치',reconciliation:'대사 미완료',source:'출처 불충분',definition:'산정 정의 미확인'}).map(([code,label])=>check('gap_'+code,label,q.gap_codes?.includes(code)))));
f.append(advanced,el('button',{class:'r-primary'},'질문·평가 설정 저장'));f.onsubmit=async e=>{e.preventDefault();const v=formValues(f);v.gap_codes=['missing','period','reconciliation','source','definition'].filter(k=>v['gap_'+k]);await action('question',{id:q.id,...v});};root.append(f);
const decision=state().decisions[q.id];const utility=decision?.utilities||[[null,null],[null,null]];const df=el('form',{id:'r-decision-form'},p('두 행동(검토 진행/보류)과 두 상태(H/반대 H)의 효용을 같은 단위로 입력합니다. 실제 거래가치 추정이 아닙니다.','r-form-help'),el('div',{class:'r-mini-grid'},field('go_h','진행 · H',utility[0][0],'number',true),field('go_not','진행 · 반대 H',utility[0][1],'number',true),field('hold_h','보류 · H',utility[1][0],'number',true),field('hold_not','보류 · 반대 H',utility[1][1],'number',true)),field('cost','질문 확보 비용',decision?.cost??0,'number',true),field('delay','별도 지연 비용',decision?.delay??0,'number',true),field('unit','효용 단위 (점수/원 등)',decision?.unit||'효용점수','text',true),field('source','효용·비용 가정 출처',decision?.source||'','textarea',true),el('button',{},'EVSI 시나리오 저장'));
df.onsubmit=async e=>{e.preventDefault();await action('decision',{id:q.id,...formValues(df)});};root.append(el('details',{class:'r-advanced'},el('summary',{},'의사결정 가치 EVSI (선택)'),df));if(q.evsi)root.append(card('가정 기반 정보가치',p('EVSI '+fmt(q.evsi.gross)+' '+q.evsi.unit),p('비용 차감 후 '+fmt(q.evsi.net)+' '+q.evsi.unit),p('EVPI 상한 '+fmt(q.evsi.evpi)+' '+q.evsi.unit),p(q.evsi.source,'r-muted')));else root.append(p('EVSI 미계산 · 확률 모형과 효용 시나리오가 필요합니다.','r-form-help'));root.append(...q.refs.slice(0,4).map(sourceButton));return;}
root.append(p('자료·가설·질문을 선택하면 원문과 평가 근거를 확인할 수 있습니다.'),p('이 프로그램은 질문 라이브러리와 명시적인 계산 규칙을 사용합니다. 발견하지 못한 표현이나 새로운 위험은 직접 검토하고 질문으로 추가하세요.','r-muted'));}
function renderFiles(){const search=$('r-file-search').value.toLowerCase();const root=$('r-files');root.replaceChildren();if(!project)return;for(const d of state().documents.filter(d=>d.filename.toLowerCase().includes(search))){const ext=d.filename.split('.').pop().toLowerCase();const family=({docx:'word',xlsx:'excel',pptx:'powerpoint',pdf:'pdf',csv:'csv'})[ext]||'other';root.append(btn('',()=>{if(step!==5&&!guard())return;detail={kind:'document',id:d.id};renderRight();},false,{class:'r-file',title:d.filename}));root.lastChild.append(el('img',{src:'/assets/file-'+family+'.svg',alt:ext+' 파일'}),el('span',{},el('strong',{},d.filename),el('small',{},d.status+' · v'+d.version+' · '+d.parsed_units+'/'+d.total_units)));}if(!root.children.length)root.append(p('표시할 자료가 없습니다.','r-muted'));}
async function example(){if(!guard())return;await task('합성 검증 사례 준비 중…',async()=>{project=await api('/api/example',{});dirty=false;qid=null;hid=null;detail=null;step=1;localStorage.setItem('orion-rule-project',project.id);await projects();render();notify('합성 사례를 열었습니다. 4단계에서 정보가치를 보고 5단계에서 증거를 반영해 보세요.');});}
$('r-create').onsubmit=async e=>{e.preventDefault();if(!guard())return;await task('프로젝트 생성 중…',async()=>{project=await api('/api/projects',formValues(e.target));step=1;dirty=false;qid=null;hid=null;detail=null;localStorage.setItem('orion-rule-project',project.id);await projects();$('r-new-project').open=false;render();notify('프로젝트를 만들었습니다. 검토할 자료를 등록하세요.');});};
$('r-project').onchange=async e=>{
  if(!guard()){e.target.value=project?.id||'';return;}
  const id=e.target.value;
  dealMode=false;step=1;detail=null;qid=null;hid=null;preview=null;$('r-file-search').value='';
  if(!id){project=null;localStorage.removeItem('orion-rule-project');render();return;}
  if(id.startsWith('case:'))await openCase(id.slice(5));
  else await task('프로젝트 불러오는 중…',()=>load(id));
  $('r-project').value=project?.id||'';
};
$('r-deal-map').onclick=()=>{if(!guard())return;dealMode=!dealMode;detail=null;render();$('r-content').scrollTop=0;};
$('r-example').onclick=example;$('r-file-search').oninput=renderFiles;$('r-open-case').onclick=()=>openCase($('r-case').value);
steps.forEach((s,i)=>$('r-nav').append(btn('',()=>jump(i+1),false,{'data-step':i+1,'aria-current':i===0?'step':'false'})));[...$('r-nav').children].forEach((n,i)=>n.append(el('span',{},String(i+1).padStart(2,'0')),steps[i][0]));
document.addEventListener('input',e=>{if(e.target.closest('form')&&!e.target.closest('#r-create'))dirty=true;});
document.addEventListener('change',e=>{if(e.target.closest('form')&&!e.target.closest('#r-create'))dirty=true;});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
(async()=>{render();await task('저장된 프로젝트 확인 중…',async()=>{const cases=await caseCatalog();await projects();render();const query=new URLSearchParams(location.search);const requested=query.get('case');if(requested&&cases.some(c=>c.id===requested)){await openCase(requested);return;}const id=localStorage.getItem('orion-rule-project');if(id){try{await load(id);$('r-project').value=id;return;}catch{localStorage.removeItem('orion-rule-project');}}if(cases.some(c=>c.id===orionCaseId))await openCase(orionCaseId);});})();
})();
