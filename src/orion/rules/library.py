"""Versioned Korean question library. Defaults are rubrics, never company facts."""
VERSION = 'rules-library-1.0.0'

TOPICS = {
    'revenue': dict(label='매출의 정의·기간 귀속', pattern=r'매출|수익|revenue|sales',
                    hypothesis='{company}의 {period} 매출은 일관된 정의와 기간 귀속 기준으로 증빙할 수 있다.',
                    counter='매출 정의·범위·귀속 시점이 일관되지 않거나 확인되지 않는다.'),
    'customer': dict(label='고객 집중·계약 지속성', pattern=r'고객|계약|customer|contract|client',
                     hypothesis='{company}의 {period} 고객 매출과 계약 지속성을 고객별 자료로 확인할 수 있다.',
                     counter='주요 고객 의존도·해지 조건 또는 고객별 매출 근거가 확인되지 않는다.'),
    'cash': dict(label='매출과 수금의 일관성', pattern=r'수금|미수|채권|현금|cash|receivable|collection',
                 hypothesis='{company}의 {period} 매출과 채권·수금의 차이를 설명하고 검증할 수 있다.',
                 counter='매출 인식과 실제 수금 사이의 차이가 설명되지 않는다.'),
    'recurring': dict(label='반복매출의 실재성', pattern=r'반복매출|구독|갱신|\bARR\b|\bNRR\b|recurring|subscription|retention',
                      hypothesis='{company}의 {period} 반복매출은 유효 계약과 명시된 산정 기준으로 뒷받침된다.',
                      counter='단발성·해지·미서명 계약 등이 반복매출에 포함됐거나 정의가 불명확하다.'),
    'margin': dict(label='이익·원가의 지속성', pattern=r'원가|마진|공헌|일회성|margin|cost|EBITDA',
                   hypothesis='{company}의 {period} 이익과 주요 원가를 설명하고 반복성을 확인할 수 있다.',
                   counter='원가 누락이나 일회성 항목 때문에 반복 이익을 확인하기 어렵다.'),
    'growth': dict(label='성장 계획의 실행 근거', pattern=r'성장|전망|계획|수주|forecast|growth|pipeline|capacity',
                   hypothesis='{company}의 {period} 성장 계획은 수주·인력·공급능력의 근거로 검증할 수 있다.',
                   counter='성장 계획이 계약·인력·공급능력의 근거 없이 제시되어 있다.'),
    'capex': dict(label='설비투자·자금 소요', pattern=r'설비|유지보수|투자지출|CAPEX|equipment|maintenance',
                  hypothesis='{company}의 {period} 설비 유지·확장 투자와 자금 소요를 구분해 설명할 수 있다.',
                  counter='유지 투자나 투자 자금 소요가 누락되거나 구분되지 않는다.'),
}


def rule(topic, key, title, request, criterion, importance=4, *, parent=None, answer=None, mandatory=False):
    return dict(id=topic+'.'+key, topic=topic, title=title, request=request, criterion=criterion,
                importance=importance, obtainability=3, parent=topic+'.'+parent if parent else None,
                answer=answer, mandatory=mandatory)


RULES = [
    rule('revenue','definition','{period} 매출의 범위·정의·인식 기준은 무엇입니까?', '매출 인식 정책, 법인·제품별 매출표, 기간 구분', '대상·기간·단위와 인식 기준을 원문에서 확인',5,mandatory=True),
    rule('revenue','ledger','{period} 공시/관리 매출과 원장·계약의 차이를 설명해 주십시오.', '관리 매출–원장–계약 대사표와 차이 설명', '비교 범위·금액·차이를 같은 기준으로 대사',5),
    rule('revenue','cutoff','기말 전후 매출의 실제 이행·검수 시점을 확인할 수 있습니까?', '기말 전후 거래 명세, 납품·검수 및 수정 전표', '거래별 이행 시점과 매출 인식 시점 비교',4,parent='definition',answer='support'),
    rule('revenue','restate','정의·범위 차이를 반영하면 {period} 매출은 어떻게 달라집니까?', '정의별 매출 재산정표와 제외 내역', '원문 수치를 보존하고 별도 재산정 근거 제시',5,parent='definition',answer='contradict'),
    rule('customer','concentration','{period} 상위 고객별 매출 비중과 특수관계는 어떻습니까?', '고객별 매출·그룹 분류·특수관계 내역', '분모·연결 범위·고객 그룹 기준과 합계 확인',5),
    rule('customer','terms','주요 고객의 갱신·해지·최소 구매 조건은 무엇입니까?', '주요 고객 계약과 변경 합의', '유효 기간과 해지·갱신 권리를 계약 원문에서 확인',4),
    rule('customer','independence','상위 고객 집단의 실질적 독립성을 확인할 수 있습니까?', '실질 소유·공통 지배 관계 확인 자료', '다른 법인명을 독립 고객으로 자동 인정하지 않고 관계 확인',4,parent='concentration',answer='support'),
    rule('cash','bridge','{period} 인식 매출·청구·채권·수금 간 차이를 설명해 주십시오.', '매출–청구–채권–입금 연결표', '동일 거래·기간·통화 기준으로 원인과 금액 확인',5),
    rule('cash','aging','장기 미수금의 연령과 후속 회수 내역은 어떻습니까?', '채권 연령표, 후속 수금 명세, 대손 기준', '잔액 기준일과 회수 증거 연결',4),
    rule('cash','bank','입금 내역을 청구서·고객·은행 원천과 연결할 수 있습니까?', '입금 원천, 청구서, 매칭 내역', '단순 회사 설명과 독립 원천의 확인을 구분',4,parent='bridge',answer='support'),
    rule('cash','unpaid','설명되지 않은 차이·장기 미수금의 회수 가능성 근거는 무엇입니까?', '차이 원인, 분쟁·연체 및 회수 계획 증빙', '확인된 사실과 회수 가정을 구분',5,parent='bridge',answer='contradict'),
    rule('recurring','definition','반복매출의 정의와 단발성·해지·미서명 계약 제외 기준은 무엇입니까?', '반복매출 산식·정의, 포함/제외 계약 목록', '용어 기재만으로 정의 확인 완료 처리하지 않음',5),
    rule('recurring','contracts','{period} 반복매출을 유효 계약별로 뒷받침할 수 있습니까?', '계약별 반복매출 산정표와 서명 계약', '금액·기간·갱신·해지 상태를 계약 원문과 연결',5),
    rule('recurring','cohort','확정한 정의로 고객 유지·이탈·확장 매출을 대사할 수 있습니까?', '고객 코호트와 기초–신규–확장–이탈 연결표', '같은 고객 집단·기간·분모로 대사',4,parent='definition',answer='support'),
    rule('recurring','correct','제외 대상 계약을 반영한 반복매출 재산정 결과는 무엇입니까?', '제외 내역과 재산정 근거', '확인된 정의 차이와 금액 영향을 구분',5,parent='definition',answer='contradict'),
    rule('margin','costs','{period} 이익 산정에 누락된 원가·이행 비용은 없습니까?', '원가 항목표, 인건비·외주·운영비 연결표', '포함 범위와 원천을 확인; 미확인을 누락 사실로 단정하지 않음',5),
    rule('margin','oneoff','일회성으로 분류한 비용·수익의 반복성 근거는 무엇입니까?', '항목별 내역, 발생 사유와 전후 기간 이력', '반복성 판단과 회사 주장 구분',4),
    rule('margin','customer','고객별 이익에 구축·지원·유지 비용이 모두 포함됐습니까?', '고객별 원가 및 공헌이익 연결표', '반복·초기 구축 비용을 구분해 확인',4,parent='costs',answer='support'),
    rule('growth','backlog','{period} 성장 계획 중 서명된 계약·확정 수주로 뒷받침되는 범위는 무엇입니까?', '계획–서명 계약–수주 연결표', '미서명 영업 기회와 계약을 구분',4),
    rule('growth','capacity','성장 계획에 필요한 인력·공급능력·운영자금 근거는 무엇입니까?', '인력 계획, 공급능력 및 자금 계획', '보고된 계획과 실제 확보한 자원을 구분',4),
    rule('growth','stress','수주 지연·고객 이탈 시 계획의 민감도는 어떻습니까?', '계획 가정과 대체 시나리오', '기준·변경 가정과 결과를 구분',4,parent='backlog',answer='contradict'),
    rule('capex','split','{period} 유지 투자와 확장 투자를 어떻게 구분했습니까?', '설비별 투자 내역과 분류 근거', '분류 기준과 관련 증빙 확인',4),
    rule('capex','funding','필수 투자·유지 비용을 충당할 자금은 확보되어 있습니까?', '투자 일정, 자금 조달·지출 근거', '확보된 자금과 조달 계획을 구분',4),
]
BY_ID = {r['id']: r for r in RULES}
