"""Original public synthetic worlds and separately authored documentary exhibits.

No real persons, counterparties, company records, or confidential templates.
Dollar amounts are integer USD; datasets are educational fictional situations.
"""
from __future__ import annotations


def paragraph(key, text):
    return {'key': key, 'text': text}


def table(key, columns, rows):
    return {'key': key, 'columns': columns, 'rows': rows}


def doc(key, title, stage, paragraphs, tables=(), origin='company', date=None, period='FY2025 and FY2027 plan', version=1):
    return dict(key=key,title=title,stage=stage,paragraphs=paragraphs,tables=list(tables),origin=origin,
                date=date or ['2026-11-03','2026-11-05','2026-11-12','2026-11-18','2026-11-25'][stage],
                period=period,version=version)


def northstar():
    """Expanded research case; independent of legacy ns source contract fixtures."""
    documents = [
      doc('cim','Northstar Analytics Investment Overview',0,[
        paragraph('purpose','SYNTHETIC DATA. Fictional CIM for academic preliminary investment screening. All names, customers, amounts and documents are invented. This is management reporting, not an independently verified investment conclusion.'),
        paragraph('traction','Management reports four enterprise customers and committed annual recurring revenue of USD 1,800,000: Quartz USD 720,000, Vale USD 480,000, Aster USD 240,000 and Birch USD 360,000.'),
        paragraph('gross_margin','FY2025 revenue was USD 1,200,000 and reported gross profit was USD 840,000, a 70% gross margin. The presentation includes only cloud hosting and routine support within cost of revenue.'),
        paragraph('margin_a','Management estimates Aster annual subscription revenue of USD 240,000 and annual delivery costs of USD 96,000, giving positive contribution of USD 144,000. Implementation effort and incremental inference usage have not been costed.'),
        paragraph('strength','Quartz and Vale renewed their support subscriptions during FY2025. The delivery team retained the same four senior engineers throughout the year. Product use remains concentrated in document analytics.'),
        paragraph('unknown','No customer ownership certificates, source-level inference logs or reconciled customer contribution schedules are attached. Management expects two new paying enterprise deployments by October 2027.')
      ]),
      doc('financial','Northstar Historical Financial Performance',0,[
        paragraph('basis','SYNTHETIC DATA. Management financial statements in whole USD. FY2025 revenue recognition is distinct from invoicing and cash receipts. No audit or independent verification is represented. FY2025 implementation payroll is recorded in operating expenses, so the gross-margin classification omits those delivery costs without omitting them from total company EBITDA.'),
        paragraph('income','FY2025 revenue USD 1,200,000 less reported cost of revenue USD 360,000 and operating expense excluding depreciation USD 720,000 equals EBITDA USD 120,000. Depreciation USD 40,000, interest USD 20,000 and tax USD 10,000 yield net income USD 50,000.'),
        paragraph('revenue','FY2025 recognized revenue is Quartz USD 720,000 plus Vale USD 480,000. Aster and Birch contributed zero recognized revenue in FY2025. Contract headline values and forecast ARR are excluded.'),
        paragraph('cashflow','FY2025 cash increased by USD 150,000: cash from operations USD 110,000, CAPEX USD 80,000, new debt USD 50,000 and new equity USD 70,000. Opening cash USD 300,000 and closing cash USD 450,000.'),
        paragraph('nwc','Operating NWC is receivables plus prepaid operating costs less trade payables, accrued operating costs and deferred revenue: FY2024 negative USD 100,000; FY2025 negative USD 120,000. Cash and debt are excluded.')
      ],[
        table('income_table',['Metric USD','FY2024','FY2025'],[['Revenue',800000,1200000],['Cost of revenue',280000,360000],['Operating expense ex depreciation',620000,720000],['EBITDA',-100000,120000],['Depreciation',30000,40000],['Interest',20000,20000],['Tax',0,10000],['Net income',-150000,50000]]),
        table('balance',['Metric USD','FY2024','FY2025'],[['Cash',300000,450000],['Accounts receivable',100000,180000],['Prepaids',40000,60000],['Net PPE',180000,220000],['Total assets',620000,910000],['Debt',200000,250000],['Trade payables',60000,90000],['Accrued costs',80000,110000],['Deferred revenue',100000,160000],['Equity',180000,300000],['Total liabilities and equity',620000,910000]])
      ],period='FY2024 and FY2025'),
      doc('plan','Northstar Revenue Forecast and Delivery Capacity',0,[
        paragraph('basis','SYNTHETIC DATA. Management plan version 1 dated 2026-11-03. Forecasts are management assumptions, not signed orders. Revenue and delivery costs use calendar FY2027.'),
        paragraph('forecast','The FY2027 plan comprises USD 1,200,000 from existing customers plus eight new deployments at USD 100,000 recognized revenue each, totaling USD 2,000,000. Cost of revenue is USD 600,000, operating expense USD 1,000,000 and EBITDA USD 400,000.'),
        paragraph('capacity','Two delivery squads can each complete two new deployments per year under the current staffing model, for four deployments. No signed outsourcing arrangement, approved hiring plan or faster delivery validation is provided.'),
        paragraph('version','The commercial plan counts eight new deployments while the signed headcount budget remains at two squads. USD 100,000 per deployment is an initial generic planning assumption, not a customer-specific revenue recognition schedule. A revised capacity and contract-term revenue forecast is requested but not supplied.'),
        paragraph('strength','Recurring revenue from the two existing accounts is held flat in the forecast. The plan does not assume price increases for those accounts.')
      ],[table('forecast_table',['Driver','FY2027'],[['Existing revenue USD',1200000],['Planned new deployments',8],['Revenue per deployment USD',100000],['Forecast revenue USD',2000000],['Squads',2],['Deployments per squad',2],['Current capacity deployments',4],['Capacity constrained revenue USD',1600000]])],period='FY2027'),
      doc('crm','Northstar Customer Pipeline and Initial Management Answers',0,[
        paragraph('basis','SYNTHETIC DATA. CRM snapshot and initial management Q&A dated 2026-11-03. Pipeline classifications are recorded separately from legal contract status.'),
        paragraph('taxonomy','Quartz and Vale are existing paying customers. Aster has a completed technical proof of concept but no executed commercial contract in the supplied pack. Birch has a nonbinding letter of interest, no executed contract and no deployment.'),
        paragraph('arr','Management labels the Aster USD 240,000 and Birch USD 360,000 pipeline opportunities as committed ARR in the CIM. Under this CRM snapshot they remain unsigned opportunities and are not committed recurring contract revenue.'),
        paragraph('qa_repeat','Management repeats that there are four enterprise customers. This answer is based on the same CRM export used for the CIM and is not a separate customer confirmation.'),
        paragraph('qa_cost','Management says cloud and standard support are included in gross margin, but states that implementation payroll and variable inference usage require a separate allocation exercise.'),
        paragraph('qa_missing','Management has not provided beneficial ownership evidence for the prospective customers. Client names alone do not establish independence.')
      ],[table('pipeline',['Customer','Status','Annual value USD','Signed on 2026-11-03'],[['Quartz','Paying renewal',720000,'Yes'],['Vale','Paying renewal',480000,'Yes'],['Aster','Technical PoC',240000,'No'],['Birch','Letter of interest',360000,'No']])]),
      doc('contract','Northstar Aster Commercial Contract and PoC Schedule',1,[
        paragraph('basis','SYNTHETIC DATA. Simulated counterparty contract exhibit, not an authentic third-party document. Executed on 2026-11-05; service term 2026-12-01 through 2027-11-30.'),
        paragraph('signed','Aster and Northstar signed a commercial contract for annual subscription fees USD 240,000 and a one-time implementation fee USD 60,000. Total first-year contractual value is USD 300,000. The PoC memorandum has been replaced by the commercial contract.'),
        paragraph('conditions','Acceptance requires an agreed benchmark test and a customer acceptance certificate. The first invoice is USD 120,000 comprising USD 60,000 implementation plus USD 60,000 for the first subscription quarter.'),
        paragraph('not_received','This exhibit contains no acceptance certificate, issued invoice or bank receipt. A signature alone does not demonstrate recognized revenue, completed acceptance or collection.'),
        paragraph('birch','Birch remains at nonbinding letter-of-interest stage as of 2026-11-05.')
      ],origin='counterparty',period='2026-12-01 through 2027-11-30'),
      doc('execution','Northstar Aster Deployment Billing and Collection Evidence',2,[
        paragraph('basis','SYNTHETIC DATA. Simulated acceptance, invoice and bank remittance extracts. No actual customer or bank records are used.'),
        paragraph('accept','Aster signed acceptance certificate AC-01 on 2026-11-12 after all contractual benchmark tests passed. Deployment status is accepted; this certificate covers Aster only.'),
        paragraph('invoice','Invoice INV-01 dated 2026-11-12 is USD 120,000: implementation USD 60,000 and subscription prebilling USD 60,000. The invoice face amount is not recognized subscription revenue on that date.'),
        paragraph('receipt','Remittance RC-01 matched to INV-01 records USD 90,000 cash received on 2026-11-12. USD 30,000 remains outstanding; neither full collection nor an overdue balance is asserted.'),
        paragraph('recognition','On acceptance USD 60,000 implementation revenue is recognized. Subscription revenue begins on 2026-12-01. The remaining USD 60,000 of invoicing is deferred revenue at 2026-11-12.'),
        paragraph('missing','No new Birch contract or customer ownership confirmation is included. Aster acceptance and cash evidence must not be extrapolated to Birch.')
      ],origin='counterparty',period='2026-11-12'),
      doc('cost','Northstar Customer Contribution and Delivery Cost Schedule',3,[
        paragraph('basis','SYNTHETIC DATA. Revised customer cost schedule version 2 dated 2026-11-18, replacing management margin assumptions in the CIM. Cost allocation is a management schedule, not independent audit evidence.'),
        paragraph('aster_cost','For Aster, annual subscription revenue USD 240,000 less cloud USD 84,000, inference USD 108,000 and recurring support USD 72,000 gives recurring contribution negative USD 24,000. Implementation revenue USD 60,000 less implementation labor USD 90,000 gives negative USD 30,000; full first-year contribution is negative USD 54,000.'),
        paragraph('omitted','The original Aster estimate of USD 96,000 delivery cost omitted USD 108,000 inference and USD 60,000 incremental support allocation. The revised recurring cost total is USD 264,000. Initial and revised figures use different coverage, not an unexplained arithmetic discrepancy.'),
        paragraph('birch_cost','Birch planned annual revenue USD 360,000, recurring costs USD 240,000 and planned contribution USD 120,000 remain estimates because no live workload measurement is supplied.'),
        paragraph('completeness','The cost schedule explicitly includes implementation, cloud, inference and support categories. Customer-specific usage logs, time sheets and third-party invoice checks have not been provided; economic recovery remains unverified.')
      ],[table('cost_table',['Aster driver','USD'],[['Subscription revenue',240000],['Cloud',84000],['Inference',108000],['Recurring support',72000],['Recurring contribution',-24000],['Implementation revenue',60000],['Implementation labor',90000],['First year contribution',-54000]])],version=2,period='Aster contract year 2026-12-01 through 2027-11-30'),
      doc('followup','Northstar Follow Up Commercial and Ownership Evidence',4,[
        paragraph('basis','SYNTHETIC DATA. Fictional follow-up management response with simulated contract, acceptance and ownership extracts dated 2026-11-25.'),
        paragraph('birch_signed','Birch signed an annual subscription contract for USD 360,000 on 2026-11-22. Its acceptance certificate dated 2026-11-25 records benchmark completion; the first USD 90,000 quarterly invoice was paid in full on that date.'),
        paragraph('ownership','The simulated ownership registry states that Birch is wholly owned by Aster. These two legal counterparties therefore do not establish two independently controlled customer groups.'),
        paragraph('count','Management corrects the initial customer taxonomy: on 2026-11-03 there were two paying customers, one PoC and one unsigned prospect. On 2026-11-25 Aster and Birch have paid contracts but form one control group.'),
        paragraph('cost_response','No revised pricing agreement, inference-usage reduction or independently verified customer cost reduction is supplied. Aster contribution remains negative in the latest supplied cost schedule.'),
        paragraph('residual','Management has not produced an additional independently controlled new customer, Aster remaining cash receipt, or a supported eight-deployment capacity plan.')
      ],origin='counterparty',period='2026-11-22 through 2026-11-25')
    ]
    questions = [
      ('contract_a','h1','Aster executed paid contract',['contract_a'],5,5,'Executed Aster commercial contract','Verify counterparty signatures, annual fee, term and acceptance conditions.'),
      ('contract_b','h1','Birch executed paid contract',['contract_b'],5,4,'Executed Birch commercial contract','Verify signatures, service term and binding recurring consideration.'),
      ('execution_a','h1','Aster acceptance and first cash',['accept_a','cash_a'],5,3,'Aster acceptance certificate and matched bank remittance','Match acceptance tests and first cash receipt to an issued invoice; identify the unpaid balance separately.'),
      ('margin_a','h2','Aster full customer contribution',['margin_a'],5,2,'Aster complete recurring and implementation cost bridge','Show positive recurring contribution after cloud, inference and support and nonnegative total first-year contribution after implementation.'),
      ('independence','h1','Independence of the two new customer groups',['independence'],4,4,'Beneficial ownership and customer group confirmation','Demonstrate that the two new paying customers are not under common control.'),
      ('execution_b','h1','Birch acceptance and first cash',['accept_b','cash_b'],4,3,'Birch acceptance certificate and matched bank remittance','Match completed benchmarks and the first payment to the Birch contract and invoice.'),
      ('count','h3','Corrected initial customer classification',['count'],4,2,'Dated customer taxonomy bridge','Reconcile paying customers, PoCs and unsigned prospects across CIM and CRM on 2026-11-03.'),
      ('arr','h3','Committed ARR reconciliation',['arr'],3,4,'Signed contract ARR reconciliation','Reconcile USD 1,800,000 presented ARR to signed recurring obligations as of 2026-11-03; exclude unsigned pipeline.'),
      ('capacity','h3','Deployable growth forecast',['capacity'],4,1,'Signed hiring or outsourcing plan and deployment model','Reconcile eight planned deployments to two squads at two deployments each, or revise forecast to supported capacity.'),
      ('margin_b','h2','Measured Birch contribution',['margin_b'],3,3,'Birch measured workload and complete cost schedule','Confirm positive recurring contribution from measured live costs, not planned margins.'),
      ('revenue','h3','Recognized revenue to ledger',['revenue'],2,5,'Revenue ledger and invoice recognition bridge','Tie FY2025 customer recognized revenue to USD 1,200,000; distinguish invoice amount, cash and contract value.'),
      ('costs','h2','Complete cost category coverage',['costs'],3,2,'Complete customer cost category schedule','Include implementation labor, cloud, inference and recurring support; distinguish coverage from independent verification.'),
      ('balance','h3','Aster outstanding collection',['balance'],2,3,'Aster subsequent cash receipt and receivables aging','Resolve USD 30,000 remaining on INV-01 with a matched receipt or a documented collectible balance assessment.')
    ]
    evidence = [
      ('cim_traction','cim','traction','h1','context',[],2,'management_crm','company_reported',None),
      ('cim_margin','cim','gross_margin','h2','context',[],2,'management_margin','company_reported',None),
      ('cim_aster','cim','margin_a','h2','supports',['margin_a'],2,'management_aster_cost','company_reported','aster_margin'),
      ('cim_strength','cim','strength','h3','context',[],2,'management_history','company_reported',None),
      ('fin_revenue','financial','revenue','h3','context',[],3,'fy25_accounting','company_reported',None),
      ('fin_income','financial','income','h2','context',[],3,'fy25_accounting','company_reported',None),
      ('fin_cash','financial','cashflow','h3','context',[],3,'fy25_accounting','company_reported',None),
      ('forecast','plan','forecast','h3','context',[],2,'forecast_v1','company_reported',None),
      ('capacity','plan','capacity','h3','refutes',['capacity'],3,'capacity_budget','company_reported','capacity'),
      ('taxonomy','crm','taxonomy','h3','refutes',['count'],3,'management_crm','company_reported','customer_count'),
      ('arr','crm','arr','h3','refutes',['arr'],3,'management_crm','company_reported','arr'),
      ('qa_repeat','crm','qa_repeat','h1','context',[],2,'management_crm','company_reported',None),
      ('qa_cost','crm','qa_cost','h2','context',[],3,'management_margin','company_reported',None),
      ('contract_a','contract','signed','h1','supports',['contract_a'],4,'aster_contract','counterparty_reported',None),
      ('contract_conditions','contract','conditions','h1','context',[],4,'aster_contract','counterparty_reported',None),
      ('accept_a','execution','accept','h1','supports',['accept_a'],4,'aster_execution','counterparty_reported',None),
      ('cash_a','execution','receipt','h1','supports',['cash_a'],4,'aster_execution','counterparty_reported',None),
      ('invoice_a','execution','invoice','h3','context',[],4,'aster_execution','counterparty_reported',None),
      ('recognition','execution','recognition','h3','context',[],3,'aster_execution','counterparty_reported',None),
      ('cost_a','cost','aster_cost','h2','refutes',['margin_a'],3,'aster_cost_v2','company_reported','aster_margin'),
      ('cost_coverage','cost','completeness','h2','supports',['costs'],3,'aster_cost_v2','company_reported',None),
      ('birch_plan','cost','birch_cost','h2','context',[],2,'birch_cost_plan','company_reported',None),
      ('contract_b','followup','birch_signed','h1','supports',['contract_b','accept_b','cash_b'],4,'birch_contract_execution','counterparty_reported',None),
      ('ownership','followup','ownership','h1','refutes',['independence'],4,'ownership_registry','counterparty_reported','ownership'),
      ('count_corrected','followup','count','h3','supports',['count'],3,'taxonomy_correction','company_reported','customer_count'),
      ('cost_residual','followup','cost_response','h2','context',[],3,'aster_cost_v2','company_reported',None)
    ]
    return dict(case='nb', name='Northstar Analytics', business='Enterprise AI subscription and implementation services', documents=documents, questions=questions,evidence=evidence,
        hypotheses={
          'h1':('By 2027-10-31 at least two newly acquired independently controlled enterprise customer groups have signed paid contracts, accepted deployment and a matched first cash receipt.','Two independent new groups; all commercial milestones met by 2027-10-31.','revenue_quality'),
          'h2':('For the Aster and Birch first contract years recurring customer contribution is positive and total first-year contribution is nonnegative after all implementation and delivery costs.','Recurring contribution > 0 and first-year total contribution >= 0 for each new customer.','unit_economics'),
          'h3':('The FY2025 recognized revenue and 2026-11-03 commercial claims reconcile within 5 percent and the FY2027 forecast is supported by documented delivery capacity.','Revenue/ARR reconciliation variance <= 5%; dated customer taxonomy and capacity support all planned deployments.','revenue_quality')},
        source_claims=[('traction','cim','traction','company_reported','Four customers and committed ARR USD 1,800,000','h3','contradicted'),('margin','cim','margin_a','company_reported','Aster has positive customer contribution','h2','partial'),('capacity','plan','forecast','company_reported','Eight new deployments support FY2027 revenue USD 2,000,000','h3','contradicted')],
        expected_top3={0:['contract_a','contract_b','execution_a'],1:['contract_b','execution_a','margin_a'],2:['contract_b','margin_a','independence'],3:['contract_b','margin_a','independence'],4:['margin_a','independence','arr']},
        event_reasons={1:'Only Aster contract is satisfied. Acceptance and cash are separate milestones; Birch remains unsigned.',2:'Aster acceptance and first receipt satisfy the execution request. The USD 30,000 unpaid balance remains a separate question.',3:'Cost categories become complete but Aster contribution is contradicted. The Top-3 is unchanged because its pre-existing gap already had maximum severity.',4:'Birch contract and execution resolve; common ownership contradicts independent customer validation. Corrected historical count resolves only the taxonomy request.'},
        world={'synthetic':True,'currency':'USD','income_2024':{'revenue':800000,'cogs':280000,'opex':620000,'ebitda':-100000,'depreciation':30000,'interest':20000,'tax':0,'net_income':-150000},'income_2025':{'revenue':1200000,'cogs':360000,'opex':720000,'ebitda':120000,'depreciation':40000,'interest':20000,'tax':10000,'net_income':50000},'balance_2024':{'cash':300000,'ar':100000,'prepaid':40000,'ppe':180000,'assets':620000,'debt':200000,'ap':60000,'accrued':80000,'deferred':100000,'equity':180000},'balance_2025':{'cash':450000,'ar':180000,'prepaid':60000,'ppe':220000,'assets':910000,'debt':250000,'ap':90000,'accrued':110000,'deferred':160000,'equity':300000},'cashflow_2025':{'cfo':110000,'capex':80000,'debt_raised':50000,'equity_raised':70000,'cash_change':150000},'customers_revenue_2025':{'Quartz':720000,'Vale':480000,'Aster':0,'Birch':0},'forecast':{'existing':1200000,'deployments':8,'per_deployment':100000,'revenue':2000000,'squads':2,'capacity_per_squad':2,'supported_revenue':1600000},'aster':{'subscription':240000,'cloud':84000,'inference':108000,'support':72000,'recurring_contribution':-24000,'implementation_revenue':60000,'implementation_cost':90000,'first_year_contribution':-54000,'billed':120000,'cash_received':90000,'receivable':30000,'recognized_on_acceptance':60000,'deferred':60000},'intentional_exceptions':[{'id':'nb_exception_arr','documents':['cim','crm'],'fact':'USD 600,000 unsigned pipeline is included in CIM committed ARR; supported signed ARR on T0 is USD 1,200,000.','visible_stage':0},{'id':'nb_exception_count','documents':['cim','crm'],'fact':'Four enterprise labels include two paying customers, one PoC and one prospect.','visible_stage':0},{'id':'nb_exception_capacity','documents':['plan'],'fact':'Eight deployments exceed documented capacity of four; arithmetic of management forecast still reconciles.','visible_stage':0},{'id':'nb_exception_margin','documents':['cim','cost'],'fact':'Management margin excludes inference and incremental support; revised cost coverage gives negative contribution.','visible_stage':3},{'id':'nb_exception_contract_forecast','documents':['plan','contract'],'fact':'The old USD 100,000 per-deployment planning assumption is not updated for Aster signed fees. Eleven FY2027 service months imply USD 220,000 subscription revenue if contractual performance occurs; a revised forecast and recognition bridge are missing.','visible_stage':1},{'id':'nb_exception_ownership','documents':['followup'],'fact':'Aster owns Birch; two legal customers do not make two independent groups.','visible_stage':4}]})
