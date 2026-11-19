/* Local native charts for the existing Orion app; no external runtime or requests. */
(function(){
'use strict';
let activeTab='flows',preview=false,lastProject=null;
const colors={source:'#4f68ce',use:'#238579',liability:'#4f68ce',equity:'#238579',unknown:'#b47d31',positive:'#4f68ce',negative:'#ce8750',total:'#52647c'};
const labels={qoe:'QoE · 정상화 EBITDA',nwc:'NWC · 영업운전자본',net_debt:'Net Debt · 순차입금'};
const categories={qoe:['일회성 비용','일회성 수익','Run-rate','회계정책','기타'],nwc:['매출채권','재고','매입채무','미지급비용','기타 영업항목'],net_debt:['차입금','현금·현금성','리스','채무 유사항목','기타']};
function svg(tag,attrs,...children){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,String(v));for(const c of children.flat()){if(c!==null&&c!==undefined)e.append(c instanceof Node?c:document.createTextNode(String(c)));}return e;}
function chart(ctx,title,width,height){const wrap=ctx.el('div',{class:'dv-chart'}),plot=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':title}),tip=ctx.el('p',{class:'dv-chart-tip','aria-live':'polite'},'포인터를 올리거나 항목에 키보드로 이동하면 상세 값을 확인할 수 있습니다.');plot.style.minWidth=width+'px';plot.prepend(svg('style',{},'.dv-svg-heading{font:700 17px system-ui,sans-serif;fill:#263b59}.dv-svg-label{font:500 16px system-ui,sans-serif}.dv-svg-value{font:650 16px system-ui,sans-serif}.dv-svg-tick{font:13px system-ui,sans-serif;fill:#61718a}'));wrap.append(plot,tip);return {wrap,plot,tip};}
function bind(node,tip,text,select){node.setAttribute('tabindex','0');node.setAttribute('role',select?'button':'graphics-symbol');node.setAttribute('aria-label',text);node.addEventListener('pointerenter',()=>tip.textContent=text);node.addEventListener('focus',()=>tip.textContent=text);if(select){node.addEventListener('click',select);node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});}}
function referenceControl(ctx,initial=[]){
 const chosen=new Set(initial),box=ctx.el('div',{class:'dv-refs'}),search=ctx.el('input',{type:'search',placeholder:'문서명·원문 키워드로 근거 검색','aria-label':'시각화 원문 근거 검색'}),results=ctx.el('div'),selected=ctx.el('div');
 const all=ctx.units();
 function show(){const query=search.value.toLowerCase();results.replaceChildren();selected.replaceChildren(...[...chosen].map(id=>ctx.el('div',{},ctx.sourceButton(id),ctx.btn('연결 해제',()=>{chosen.delete(id);show();}))));
  const rows=all.filter(s=>(s.document.filename+' '+s.location+' '+s.text).toLowerCase().includes(query)).slice(0,8);
  for(const s of rows){const cb=ctx.check('',s.document.filename+' · '+s.location+' · '+s.text.slice(0,45),chosen.has(s.id));cb.querySelector('input').onchange=e=>{if(e.target.checked)chosen.add(s.id);else chosen.delete(s.id);show();};results.append(cb);}
 }
 search.oninput=show;box.append(ctx.el('strong',{},'원문 근거 (선택·최대 10구간)'),search,ctx.p('검색 결과 8개씩 표시합니다. 근거를 연결해도 검토·회계 분류가 자동 승인되지는 않습니다.','r-form-help'),selected,results);show();return {box,values:()=>[...chosen]};
}
function flowChart(ctx,data,model,edit){
 const n=Math.max(data.sources.length,data.uses.length,1),h=Math.max(390,n*66+50),c=chart(ctx,'Sources와 Uses 자금 흐름',920,h),total=Math.max(Number(data.total_sources),Number(data.total_uses),1),k=(h-50-n*50-(n-1)*8)/total;
 c.plot.append(svg('text',{x:12,y:21,class:'dv-svg-heading'},'SOURCES · 자금 조달'),svg('text',{x:670,y:21,class:'dv-svg-heading'},'USES · 자금 사용'));
 const poolHeight=total*k,cx=400,cy=45;
 c.plot.append(svg('rect',{x:cx,y:cy,width:120,height:Math.max(42,poolHeight),rx:8,fill:'#edf2fb',stroke:'#a9b8d3'}),svg('text',{x:460,y:cy+20,'text-anchor':'middle',class:'dv-svg-label'},model.entity.slice(0,12)));
 for(const [side,rows,x] of [['source',data.sources,10],['use',data.uses,670]]){let y=45,pool=cy;
  for(const row of rows){const v=Number(row.amount),band=Math.max(0,v*k),height=50+band,node=svg('g',{}),x0=side==='source'?x+240:520,x1=side==='source'?400:x;
   if(band>0){const sy=side==='source'?y+20:pool,ty=side==='source'?pool:y+20;node.append(svg('path',{d:`M ${x0} ${sy} C ${(x0+x1)/2} ${sy}, ${(x0+x1)/2} ${ty}, ${x1} ${ty} L ${x1} ${ty+band} C ${(x0+x1)/2} ${ty+band}, ${(x0+x1)/2} ${sy+band}, ${x0} ${sy+band} Z`,fill:colors[side],opacity:.3}));}
   node.append(svg('rect',{x,y,width:240,height,rx:6,fill:colors[side],opacity:.95}),svg('text',{x:x+12,y:y+20,fill:'white',class:'dv-svg-label'},row.label.slice(0,12)+(row.label.length>12?'…':'')),svg('text',{x:x+12,y:y+height-9,fill:'white',class:'dv-svg-value'},ctx.fmt(v)+' '+model.unit));
   bind(node,c.tip,row.label+' · '+ctx.fmt(v)+' '+model.unit+' · '+row.note,()=>edit(row));c.plot.append(node);y+=height+8;pool+=band;
  }
 }
 if(!data.sources.length||!data.uses.length)c.wrap.append(ctx.p('Source 또는 Use가 비어 있습니다. 입력된 흐름만 표시합니다. 차이를 맞추기 위한 항목을 자동으로 만들지 않습니다.','r-form-help'));
 c.wrap.append(ctx.p('선의 두께는 금액에 비례합니다. 가운데 계정에서 합쳐지는 예산 흐름이며, 특정 투자자 자금이 특정 용도에 배정됐다는 뜻은 아닙니다.','r-form-help'));
 return c.wrap;
}
function waterfall(ctx,bridge,title,unit){
 if(!bridge.available)return ctx.p(bridge.reason,'r-empty');
 const sorted=[...bridge.rows].sort((a,b)=>Math.abs(Number(b.amount))-Math.abs(Number(a.amount))),shown=sorted.slice(0,8);
 if(sorted.length>8)shown.push({label:'기타 '+(sorted.length-8)+'건',amount:String(sorted.slice(8).reduce((s,r)=>s+Number(r.amount),0)),note:'전체 항목은 아래 표에서 확인'});
 let running=Number(bridge.start);const bars=[{label:'조정 전',low:0,high:running,value:running,total:true}];
 for(const row of shown){const after=running+Number(row.amount);bars.push({...row,low:running,high:after,value:Number(row.amount)});running=after;}
 bars.push({label:'조정 후',low:0,high:Number(bridge.end),value:Number(bridge.end),total:true});
 const lo=Math.min(0,...bars.flatMap(b=>[b.low,b.high])),hi=Math.max(0,...bars.flatMap(b=>[b.low,b.high])),range=hi-lo||1,w=Math.max(720,bars.length*108),h=350,c=chart(ctx,title,w,h),y=v=>46+(hi-v)/range*220;
 c.plot.append(svg('line',{x1:45,x2:w-15,y1:y(0),y2:y(0),stroke:'#9cabc0'}));
 for(const value of [lo,hi])c.plot.append(svg('text',{x:3,y:y(value)+5,class:'dv-svg-tick'},ctx.fmt(value,1)));
 const step=(w-75)/bars.length;
 bars.forEach((b,i)=>{const x=55+i*step,top=y(Math.max(b.low,b.high)),height=Math.abs(y(b.low)-y(b.high)),g=svg('g',{}),color=b.total?colors.total:b.value>=0?colors.positive:colors.negative;
  if(i>0&&i<bars.length-1)c.plot.append(svg('line',{x1:x-step*.35,x2:x+step*.12,y1:y(b.low),y2:y(b.low),stroke:'#aeb8c8','stroke-dasharray':'3 3'}));
  g.append(svg('rect',{x:x+step*.12,y:top,width:step*.64,height,fill:color,rx:3}),svg('text',{x:x+step*.44,y:Math.max(20,top-9),'text-anchor':'middle',class:'dv-svg-value'},(!b.total&&b.value>0?'+':'')+ctx.fmt(b.value,1)));
  const displayLabel=({qoe:'QoE 영향',nwc:'NWC 영향',net_debt:'Net Debt 영향'})[b.id]||b.label,chars=Math.max(4,Math.floor(step/16)-1);const text=svg('text',{x:x+step*.44,y:295,'text-anchor':'middle',class:'dv-svg-label'});text.append(svg('tspan',{x:x+step*.44,dy:0},displayLabel.slice(0,chars)),svg('tspan',{x:x+step*.44,dy:19},displayLabel.slice(chars,chars*2))); g.append(text);bind(g,c.tip,b.label+' · '+ctx.fmt(b.value)+' '+unit+(b.note?' · '+b.note:''));c.plot.append(g);
 });
 c.wrap.append(ctx.p('단위 '+unit+' · 회색: 시작/종료 · 파랑: 증가 · 주황: 감소. 절대금액 상위 8개 조정과 나머지 합계를 표시하며 전체 합계는 모두 반영합니다.','r-form-help'));
 const download=ctx.btn('그래프 SVG 저장',()=>{const blob=new Blob([new XMLSerializer().serializeToString(c.plot)],{type:'image/svg+xml'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Orion_waterfall.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});c.wrap.append(download);
 return c.wrap;
}
function render(ctx){
 if(lastProject!==ctx.projectId){activeTab='flows';preview=false;lastProject=ctx.projectId;}
 const {el,p,card,btn,field,select,check,fmt,table}=ctx,m=ctx.data.model,c=preview?ctx.data.preview:ctx.data.accepted,root=ctx.root;
 const refresh=()=>{if(!ctx.guard())return;root.replaceChildren();render(ctx);};
 root.append(card('거래 구조를 이해하는 작업 공간',ctx.badge(m.origin==='synthetic'?'합성 학습 시나리오':m.origin==='case_budget'?'사례 기재 자금 예산':'담당자 입력 시나리오',m.origin==='synthetic'?'r-warn':'r-blue'),
  p('자금 흐름 → 조달·대변 구조 → FDD 조정 → 지분가치 영향으로 연결해 봅니다. 조정의 검토 반영은 이 시나리오 안의 상태이며 질문·증빙 승인을 바꾸지 않습니다.','r-form-help'),m.linked_preview?p('기존 사례 자금 예산을 읽기 전용으로 연결했습니다. 항목을 편집·저장하면 새 시나리오와 이력을 만듭니다.','r-form-help'):null,p((m.notes||'입력 근거와 검토 기준을 설정하세요.')+' · 단위: '+m.unit,'r-muted')));
 const nav=el('div',{class:'dv-tabs',role:'tablist','aria-label':'거래 시각화 보기'});
 for(const [id,label] of [['flows','자금 흐름'],['capital','조달·BS 대변'],['fdd','QoE·NWC·Net Debt'],['price','지분가치 연결']])nav.append(btn(label,()=>{if(!ctx.guard())return;activeTab=id;root.replaceChildren();render(ctx);},false,{role:'tab','aria-selected':activeTab===id,class:activeTab===id?'r-primary':''}));root.append(nav);
 root.append(settings());
 if(activeTab==='flows')flows();if(activeTab==='capital')capital();if(activeTab==='fdd')fdd();if(activeTab==='price')price();
 function save(form,section,refs){form.onsubmit=async e=>{e.preventDefault();const v=ctx.formValues(form);await ctx.onAction('visual',{...v,section,operation:'save',refs:refs.values()});};}
 function editBase(section,fields){const form=el('form',{class:'dv-editor','data-section':section}),refs=referenceControl(ctx),note=field('note','입력 근거·검토 이유','','textarea',true),id=el('input',{type:'hidden',name:'item_id',value:''});
  form.append(id,...fields,note,refs.box,el('button',{class:'r-primary'},'시각화 항목 저장'));save(form,section,refs);
  const wrap=el('details',{class:'r-card dv-edit-box'},el('summary',{},'항목 추가·수정'),form);
  function edit(row){if(!ctx.guard())return;wrap.open=true;for(const input of form.querySelectorAll('input,select,textarea')){const key=input.name;if(key&&key in row)input.value=row[key]??'';}id.value=row.id;const replacement=referenceControl(ctx,row.refs);refs.box.replaceWith(replacement.box);refs.box=replacement.box;refs.values=replacement.values;
   if(section==='adjustments'){updateCategories();form.querySelector('[name=category]').value=row.category;}wrap.scrollIntoView({block:'nearest',behavior:'smooth'});}
  function updateCategories(){const stream=form.querySelector('[name=stream]'),cat=form.querySelector('[name=category]');if(!stream)return;const value=cat.value;cat.replaceChildren(...categories[stream.value].map(x=>el('option',{value:x},x)));cat.value=categories[stream.value].includes(value)?value:categories[stream.value][0];}
  const stream=form.querySelector('[name=stream]');if(stream){stream.onchange=updateCategories;updateCategories();}
  return {wrap,edit};
 }
 function actions(section,row,edit){return el('div',{class:'r-actions'},btn('수정',()=>edit(row)),btn('삭제',async()=>{if(!ctx.guard())return;if(confirm('이 시나리오 항목을 삭제하시겠습니까? 이전 저장 버전은 이력에 남습니다.'))await ctx.onAction('visual',{operation:'delete',section,item_id:row.id});}));}
 function refs(row){return el('div',{},p(row.note,'r-form-help'),...row.refs.map(ctx.sourceButton));}
 function settings(){
  const f=el('form',{id:'dv-settings-form',class:'dv-editor'},el('div',{class:'r-mini-grid'},field('entity','자금 계정·BS 발행 주체',m.entity,'text',true),field('scope','FDD 대상·연결 범위',m.scope),field('earnings_period','QoE 손익 기간',m.earnings_period),field('balance_date','NWC·Net Debt 기준일',m.balance_date),select('unit','공통 금액 단위',['억원','백만원','원','USD'].map(x=>[x,x]),m.unit)),field('notes','시나리오 근거·정의·거래 조건',m.notes,'textarea',true),
   el('div',{class:'r-mini-grid'},field('qoe','조정 전 EBITDA',m.bases.qoe,'number'),field('nwc','조정 전 NWC',m.bases.nwc,'number'),field('net_debt','조정 전 Net Debt',m.bases.net_debt,'number'),field('assets','참고 자산 총액 · 선택',m.assets,'number')),
   check('balance_complete','선택한 발행 주체의 부채·자본을 모두 입력했으며 자산과 동일 기준입니다.',m.balance_complete),
   select('ev_mode','기업가치(EV) 가정',[['fixed','직접 입력한 EV 고정'],['multiple','조정 EBITDA × 배수']],m.ev_mode),el('div',{class:'r-mini-grid'},field('enterprise_value','고정 EV · 직접 입력 모드',m.enterprise_value,'number'),field('multiple','EV/EBITDA 배수 · 배수 모드',m.multiple,'number'),field('peg','NWC 목표값 (Peg)',m.peg,'number')),
   p('QoE는 손익 기간, NWC·Net Debt는 기준일과 계약상 정의를 확인합니다. 금액 입력 후에는 단위를 바꿀 수 없습니다. 공란은 미입력이며 0과 다릅니다.','r-form-help'));
  const ref=referenceControl(ctx,m.base_refs);f.append(ref.box,el('button',{class:'r-primary'},'기준·가정 저장'));f.onsubmit=async e=>{e.preventDefault();await ctx.onAction('visual',{...ctx.formValues(f),operation:'settings',base_refs:ref.values()});};
  return el('details',{class:'r-card'},el('summary',{},'기준·금액·거래가치 가정 설정'),f);
 }
 function flows(){
  root.append(ctx.metrics([['Sources · 조달 합계',fmt(c.flow.total_sources)+' '+m.unit],['Uses · 사용 합계',fmt(c.flow.total_uses)+' '+m.unit],['미배분 / 부족',fmt(c.flow.gap)+' '+m.unit]]));
  const editor=editBase('flows',[field('label','투자자·대주 또는 수령자·용도','','text',true),select('side','구분',[['source','Source · 조달'],['use','Use · 사용']],'source'),field('amount','금액',null,'number',true)]);
  root.append(card('Sources → 자금 계정 → Uses',flowChart(ctx,c.flow,m,editor.edit),p('차이가 양수면 미배분 자금, 음수면 사용 계획 대비 부족한 재원입니다. 금액 일치는 조달 확약이나 집행 완료를 뜻하지 않습니다.','r-form-help')));
  if(!m.flows.length)root.append(el('div',{class:'r-actions'},ctx.hasBudget?btn('기존 사례 자금표 연결',()=>ctx.onAction('visual_import')):null,btn('새 합성 사례로 시각화 체험',ctx.openExample)));
  if(Number(c.flow.gap)!==0)root.append(p('조달과 사용이 대사되지 않습니다. 잔여 현금·비용·추가 조달을 검토하세요.','r-information-note'));
  root.append(card('자금 항목과 근거',table(['구분','조달자 / 용도','금액','근거','편집'],m.flows.map(r=>[r.side==='source'?'Source':'Use',r.label,fmt(r.amount)+' '+m.unit,refs(r),actions('flows',r,editor.edit)]))),editor.wrap);
 }
 function capital(){
  const a=c.capital,editor=editBase('instruments',[field('label','조달 항목명','','text',true),select('kind','상품',['보통주','은행차입','CB','RCPS','리스','기타 부채','기타 자본'].map(x=>[x,x]),'CB'),field('issuer','발행 주체',m.entity,'text',true),select('classification','회계 분류',[['unknown','계약 검토 전 · 미확정'],['liability','부채'],['equity','자본'],['split','부채·자본 복합']],'unknown'),field('proceeds','조달 현금 · 선택',null,'number'),field('book','기준일 장부금액',null,'number',true),field('liability_part','복합 분류 시 부채 부분',null,'number'),field('terms','상환·전환·배당 등 계약 조건','','textarea')]);
  const board=el('div',{class:'dv-balance-board'},el('section',{},el('h4',{},'차변 · 참고 자산'),el('strong',{},m.assets===null?'미입력':fmt(m.assets)+' '+m.unit),p('같은 주체·기준일·범위의 자산 총액','r-form-help')),el('section',{},el('h4',{},'대변 · 입력한 조달 구조'),...['liability','equity','unknown'].map((k,i)=>el('div',{class:'dv-capital-row'},el('span',{},['부채','자본','분류 미확정'][i]),el('strong',{style:'color:'+colors[k]},fmt(a[k])+' '+m.unit),el('div',{class:'dv-capital-track',hidden:Number(a.equity)<0||Number(a.total)<=0},el('span',{style:`width:${Number(a.total)>0?Math.max(0,Number(a[k])/Number(a.total)*100):0}%;background:${colors[k]}`}))))));
  root.append(card('BS 대변에서 보는 조달 구조 · '+a.issuer,board,Number(a.equity)<0?p('음수 자본은 구성비 막대 대신 금액으로 표시합니다.','r-form-help'):null,p('기준일 '+(m.balance_date||'미설정')+' · 미확정은 별도 표시합니다. 조달 현금과 장부금액은 발행비용·할인·전환권 등에 따라 다를 수 있습니다.','r-form-help'),p(a.balance_gap===null?'전체 입력·동일 기준 확인 전이므로 BS 대사는 보류합니다.':'자산 − 부채 − 자본 = '+fmt(a.balance_gap)+' '+m.unit,a.balance_gap===null?'r-muted':'r-information-note'),a.excluded_issuers?p('다른 발행 주체 '+a.excluded_issuers+'개 항목은 이 대변 합계에서 제외했습니다.','r-form-help'):null,
   p('CB·RCPS의 이름이 회계 분류를 결정하지 않습니다. 상환 의무·전환 조건 등을 검토한 분류를 입력합니다. Net Debt의 거래상 정의도 별도로 확인하세요.','r-form-help'),el('a',{href:'https://www.ifrs.org/issued-standards/list-of-standards/ias-32-financial-instruments-presentation/',target:'_blank',rel:'noopener noreferrer'},'회계 분류 참고 · IAS 32')));
  root.append(card('조달 상품별 조건·분류',table(['상품·발행 주체','분류','장부 / 조달 현금','부채·자본 부분','조건·근거','편집'],m.instruments.map(r=>[r.label+' · '+r.kind+' · '+r.issuer,{unknown:'미확정',liability:'부채',equity:'자본',split:'복합'}[r.classification],fmt(r.book)+' / '+fmt(r.proceeds)+' '+m.unit,r.classification==='split'?fmt(r.liability_part)+' / '+fmt(Number(r.book)-Number(r.liability_part)):'—',el('div',{},p(r.terms),refs(r)),actions('instruments',r,editor.edit)]))),editor.wrap);
 }
 function previewControl(){return btn(preview?'제안 포함 미리보기 · 검토 반영만 보기':'검토 반영 기준 · 제안도 미리보기',()=>{if(!ctx.guard())return;preview=!preview;root.replaceChildren();render(ctx);},preview,{id:'dv-preview-toggle'});}
 function fdd(){
  root.append(previewControl(),p(preview?'제안과 검토 반영 항목을 함께 계산한 미리보기입니다.':'검토 반영 항목만 계산합니다. 제안·제외 항목은 합계에 포함하지 않습니다.','r-information-note'));
  root.append(ctx.metrics(Object.entries(labels).map(([k,label])=>[label,c.bridges[k].available?fmt(c.bridges[k].start,1)+' → '+fmt(c.bridges[k].end,1)+' '+m.unit:'기준값 미입력'])));
  const editor=editBase('adjustments',[field('label','조정 항목명','','text',true),select('stream','FDD 구분',Object.entries(labels),'qoe'),select('category','하위 항목',categories.qoe.map(x=>[x,x]),categories.qoe[0]),field('amount','부호 있는 조정 금액 · 증가 + / 감소 −',null,'number',true),select('status','조정 검토 상태',[['proposed','제안'],['accepted','검토 반영'],['rejected','제외']],'proposed'),field('economic_key','같은 경제 항목의 중복 검토 키','','text'),select('question_id','관련 실사 질문',[['','연결 없음'],...ctx.questions.map(q=>[q.id,q.title])],'')]);
  for(const [key,title] of Object.entries(labels)){const b=c.bridges[key];root.append(card(title,ctx.badge(key==='qoe'?'손익 기간 '+(m.earnings_period||'미설정'):'기준일 '+(m.balance_date||'미설정'),'r-blue'),p({qoe:'반복 가능한 이익을 보기 위한 EBITDA 조정입니다. 비용 가산은 +, 이익 차감은 −로 입력합니다.',nwc:'영업성 자산에서 영업성 부채를 차감하는 거래상 NWC 정의를 따릅니다. 현금·차입금과 구분합니다.',net_debt:'차입·채무 유사항목에서 현금·현금 유사항목을 차감하는 거래상 정의를 따릅니다. 증가하면 지분가치는 감소합니다.'}[key],'r-form-help'),waterfall(ctx,b,title,m.unit)));}
  root.append(card('전체 조정 명세 · 부호와 상태 확인',table(['FDD·하위 항목','조정·금액','상태','근거·질문','편집'],m.adjustments.map(r=>[labels[r.stream]+' / '+r.category,r.label+' · '+(Number(r.amount)>0?'+':'')+fmt(r.amount)+' '+m.unit,{proposed:'제안',accepted:'검토 반영',rejected:'제외'}[r.status],el('div',{},refs(r),r.question_id?ctx.btn('연결 질문 확인',()=>ctx.chooseQuestion(r.question_id)):null),actions('adjustments',r,editor.edit)]))),editor.wrap);
 }
 function price(){
  root.append(previewControl(),...c.warnings.map(w=>p(w,'r-information-note')),card('FDD 조정 → 지분가치 연결',p('지분가치 = EV − Net Debt + (NWC − NWC 목표값). 계약상 가격 조정 메커니즘을 단순화한 시나리오이며 확정 거래가격이 아닙니다.','r-form-help'),p(m.ev_mode==='multiple'?'QoE 조정 × 입력 배수를 EV 변화로 연결합니다.':'EV 고정 모드에서는 QoE 조정을 가격에 자동 가산하지 않습니다.','r-form-help'),waterfall(ctx,c.price,'지분가치 전후 변화',m.unit),p('Net Debt 증가에는 음수 방향, NWC 증가에는 양수 방향을 적용합니다. NWC·Net Debt에 같은 경제 항목이 입력되면 가격 브리지를 보류합니다.','r-form-help')));
  if(c.price.available)root.append(ctx.metrics([['조정 전 지분가치',fmt(c.price.start)+' '+m.unit],['FDD 조정 영향',fmt(c.price.delta)+' '+m.unit],['조정 후 지분가치',fmt(c.price.end)+' '+m.unit]]));
 }
}
window.OrionDealVisuals={render};
})();
