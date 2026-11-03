"""Original manufacturing case authored for this academic dataset.

All entities, customers, contracts and records are fictional. Source documents
and hidden world values are distinct; the former contain deliberate, labelled
management misstatements and incomplete verification. This case was authored
alongside Northstar and is not a genuinely blinded external holdout.
"""
from .cases import doc, paragraph, table


def manufacturing():
    documents = [
        doc('financial', 'Ridgeway Homeware Historical Financial Statements', 0, [
            paragraph('basis', 'SYNTHETIC DATA. Fictional management accounts for a domestic producer of reusable kitchen storage and cookware. All amounts are whole USD. The statements are internally reconciled educational exhibits, not audited accounts.'),
            paragraph('income', 'FY2025 revenue USD 10,000,000 less cost of sales USD 6,400,000 and net operating expense excluding depreciation USD 2,300,000 gives reported EBITDA USD 1,300,000. Depreciation USD 400,000, interest USD 150,000 and tax USD 150,000 give net income USD 600,000.'),
            paragraph('normalization', 'Net operating expense of USD 2,300,000 comprises USD 2,600,000 gross expense less a USD 300,000 insurance recovery received in cash. Gross expense includes USD 100,000 relocation expense. Removing the insurance recovery and adding back relocation gives a provisional normalized EBITDA of USD 1,100,000. Insurance settlement and proof that relocation will not recur have not been supplied.'),
            paragraph('cashflow', 'FY2025 cash from operations is USD 0: net income USD 600,000 plus depreciation USD 400,000 less USD 1,000,000 increase in operating NWC. CAPEX USD 1,000,000, debt raised USD 600,000, equity raised USD 200,000 and dividends USD 100,000 produce a USD 300,000 cash decrease from USD 600,000 to USD 300,000.'),
            paragraph('profit', 'Management describes FY2025 reported EBITDA of USD 1,300,000 as USD 1,300,000 operating cash generated. The supplied cash-flow reconciliation instead reports zero cash from operations; EBITDA growth from USD 1,200,000 does not make EBITDA equivalent to cash flow.'),
        ], [
            table('income_table', ['Metric USD', 'FY2024', 'FY2025'], [
                ['Revenue', 8000000, 10000000], ['Cost of revenue', 4800000, 6400000],
                ['Operating expense ex depreciation', 2000000, 2300000], ['EBITDA', 1200000, 1300000],
                ['Depreciation', 300000, 400000], ['Interest', 100000, 150000], ['Tax', 200000, 150000], ['Net income', 600000, 600000],
            ]),
            table('balance', ['Metric USD', 'FY2024', 'FY2025'], [
                ['Cash', 600000, 300000], ['Accounts receivable', 1200000, 1600000], ['Inventory', 1500000, 2400000],
                ['Prepaids', 100000, 100000], ['Net PPE', 2000000, 2600000], ['Total assets', 5400000, 7000000],
                ['Debt', 1800000, 2400000], ['Trade payables', 900000, 1100000], ['Accrued costs', 300000, 400000],
                ['Deferred revenue', 0, 0], ['Equity', 2400000, 3100000], ['Total liabilities and equity', 5400000, 7000000],
            ]),
        ], period='FY2024 and FY2025'),
        doc('sales', 'Ridgeway Sales Mix and Customer Concentration', 0, [
            paragraph('basis', 'SYNTHETIC DATA. FY2025 management sales schedules reconcile to recognized revenue. Customer identities are invented; customer labels do not demonstrate credit quality or future order commitments.'),
            paragraph('customers', 'FY2025 recognized revenue is Brindle Retail USD 4,500,000, Fern Wholesale USD 2,000,000, Hearth Distribution USD 1,500,000 and direct-to-consumer sales USD 2,000,000. Brindle represents 45% of total revenue.'),
            paragraph('products', 'FY2025 recognized revenue comprises 60,000 storage-unit equivalents at USD 100 and 20,000 cookware-unit equivalents at USD 200: USD 6,000,000 plus USD 4,000,000 equals USD 10,000,000.'),
            paragraph('geography', 'Domestic revenue is USD 8,000,000 and export revenue USD 2,000,000. The export channel grew, but domestic business still comprises 80% of recognized revenue.'),
            paragraph('contracts', 'Brindle annual purchase forecasts are nonbinding. No minimum-volume commitment or signed FY2027 order book is supplied. Management calls the customer base diversified despite the 45% single-customer exposure.'),
            paragraph('strength', 'No product category accounts for all sales, and 20% of revenue comes from direct-to-consumer sales. These are documented mix characteristics, not independent proof of customer retention.'),
        ], [table('customer_table', ['Customer', 'FY2025 recognized revenue USD'], [
            ['Brindle Retail', 4500000], ['Fern Wholesale', 2000000], ['Hearth Distribution', 1500000], ['Direct to consumer', 2000000],
        ])], period='FY2025'),
        doc('inventory', 'Ridgeway Inventory Aging and Operating Working Capital', 0, [
            paragraph('basis', 'SYNTHETIC DATA. Management inventory ledger and working-capital schedules at 2025-12-31. Physical count evidence and signed subsequent-sales records are not initially included.'),
            paragraph('stock', 'Recorded inventory is USD 2,400,000: raw materials USD 800,000, work in progress USD 400,000 and finished goods USD 1,200,000. Management says all stock is readily saleable and no write-down is required.'),
            paragraph('aging', 'Finished goods older than 270 days have book cost USD 700,000. Management estimates their net realizable value at USD 500,000, implying a potential USD 200,000 write-down not booked in the historical statements. No signed clearance orders or independent valuation supports that estimate.'),
            paragraph('growth', 'Revenue increased 25% from USD 8,000,000 to USD 10,000,000, whereas inventory increased 60% from USD 1,500,000 to USD 2,400,000. Closing inventory divided by annual cost of sales multiplied by 365 is 114.0625 days in FY2024 and 136.875 days in FY2025; this is a closing-balance diagnostic, not average inventory turnover.'),
            paragraph('nwc', 'Operating NWC is trade receivables plus inventory plus prepaids less trade payables and accrued operating costs. It increased from USD 1,600,000 in FY2024 to USD 2,600,000 in FY2025. Cash, debt and tax are excluded from this case definition.'),
            paragraph('receivables', 'USD 400,000 of FY2025 closing receivables is owed by Brindle, including USD 150,000 past due more than 90 days. Subsequent collection evidence and an expected-loss review are absent.'),
        ], [table('inventory_table', ['Inventory category', 'FY2025 book cost USD'], [
            ['Raw materials', 800000], ['Work in progress', 400000], ['Finished goods', 1200000], ['Total inventory', 2400000],
        ])], period='2024-12-31 and 2025-12-31'),
        doc('plant', 'Ridgeway Manufacturing Capacity and CAPEX Schedule', 0, [
            paragraph('basis', 'SYNTHETIC DATA. Management plant schedule. Standardized production-slot equivalents are used for planning and are distinct from the product-unit quantities in the sales schedule.'),
            paragraph('capacity', 'Current practical capacity is 100,000 standardized production-slot equivalents per year. The FY2027 plan requires 120,000 equivalents. An additional 20,000-slot press has neither an executed purchase order nor committed financing in the supplied pack.'),
            paragraph('capex', 'FY2025 CAPEX USD 1,000,000 consists of USD 600,000 replacement and safety work required to sustain existing operations and USD 400,000 expansion projects. Management initially describes the entire USD 1,000,000 as discretionary growth investment.'),
            paragraph('maintenance', 'Management engineering logs classify the USD 600,000 replacement and safety amount as maintenance CAPEX. Supplier invoices, asset-condition reports and the recurring maintenance budget have not been independently checked.'),
            paragraph('ppe', 'Opening net PPE USD 2,000,000 plus FY2025 additions USD 1,000,000 less depreciation USD 400,000 equals closing net PPE USD 2,600,000. There are no disposals, impairments or revaluations in the supplied roll-forward.'),
            paragraph('strength', 'Existing plant supports current sales volume without the proposed new press. The additional equipment is a growth dependency, not a condition for maintaining all current operations.'),
        ], [table('capex_table', ['FY2025 category', 'USD'], [['Maintenance and safety', 600000], ['Expansion', 400000], ['Total', 1000000]])], period='FY2025 actual and FY2027 capacity'),
        doc('forecast', 'Ridgeway FY2027 Management Plan and Initial Q&A', 0, [
            paragraph('basis', 'SYNTHETIC DATA. Management plan version 1, dated 2026-11-03. Forecasts are assumptions and have no independent assurance. No unprovided FY2026 actual result is assumed.'),
            paragraph('revenue', 'FY2027 revenue is forecast as 120,000 standardized production-slot equivalents at a blended USD 100 revenue per equivalent, totaling USD 12,000,000. Cost of sales USD 7,560,000 and operating expense excluding depreciation USD 2,740,000 produce forecast EBITDA USD 1,700,000.'),
            paragraph('capacity_gap', 'The plan assumes the additional press will be available for the whole year. With current practical capacity of 100,000 equivalents and the same blended revenue rate, supported capacity would produce USD 10,000,000. No funded installation schedule supports the additional capacity.'),
            paragraph('inventory_target', 'The FY2027 plan reduces closing inventory to USD 1,200,000 while cost of sales rises to USD 7,560,000. The target implies 57.9365 closing-inventory days, compared with 136.875 days in FY2025. No signed inventory clearance program or documented lead-time improvement supports the reduction.'),
            paragraph('nwc_target', 'Planned operating NWC is USD 1,500,000: receivables USD 1,800,000 plus inventory USD 1,200,000 plus prepaids USD 100,000 less trade payables USD 1,200,000 and accrued operating costs USD 400,000. Relative to FY2025, the plan assumes USD 1,100,000 cash release from working capital.'),
            paragraph('qa', 'Management repeats that EBITDA growth proves cash generation, that all CAPEX is expansion and that inventory will halve. These answers repeat the management financial and plant schedules; they are not independent confirmations.'),
        ], [table('forecast_table', ['FY2027 driver', 'Value'], [
            ['Planned production equivalents', 120000], ['Current capacity equivalents', 100000], ['Revenue per equivalent USD', 100],
            ['Revenue USD', 12000000], ['Cost of sales USD', 7560000], ['Operating expense USD', 2740000], ['EBITDA USD', 1700000],
            ['Inventory USD', 1200000], ['Operating NWC USD', 1500000],
        ])], period='FY2027'),
        doc('count', 'Ridgeway Follow-up Warehouse Count and Ledger Reconciliation', 1, [
            paragraph('basis', 'SYNTHETIC DATA. Fictional warehouse-custodian count records delivered on 2026-11-05, covering an observed physical count at 2025-12-31. No real custodian, signature or assurance opinion is represented.'),
            paragraph('counted', 'The custodian count schedule totals raw materials USD 800,000, work in progress USD 400,000 and finished goods USD 1,200,000 at the ledger unit costs. Standardized kit-equivalent counts are respectively 8,000, 4,000 and 6,000, matching the book quantities at USD 100, USD 100 and USD 200 per equivalent. Counted quantities reconcile to the USD 2,400,000 inventory ledger with zero quantity variance across all three storage areas at 2025-12-31.'),
            paragraph('limits', 'This count supports quantities and physical existence only. It does not establish net realizable value, product saleability, inventory ownership or absence of liens. The USD 700,000 aged finished-goods balance is included in the count.'),
            paragraph('residual', 'No signed clearance orders, new press financing, supporting insurance settlement, Brindle subsequent cash receipts or revised working-capital operating plan accompany the count.'),
        ], [table('physical_count', ['Category', 'Book units', 'Counted units', 'Cost per unit USD', 'Ledger value USD'], [
            ['Raw material kit equivalents', 8000, 8000, 100, 800000],
            ['Work in progress kit equivalents', 4000, 4000, 100, 400000],
            ['Finished goods kit equivalents', 6000, 6000, 200, 1200000],
        ])], origin='counterparty', period='Count date 2025-12-31; received 2026-11-05'),
    ]
    questions = [
        ('inventory_count', 'h1', 'Inventory physical existence and quantity reconciliation', ['inventory_count'], 5, 5, 'Dated warehouse count and complete inventory-ledger reconciliation', 'Reconcile all three warehouse categories at 2025-12-31 to the USD 2,400,000 ledger; explain quantity variance above 1%.'),
        ('inventory_valuation', 'h1', 'Aged inventory recoverability', ['inventory_valuation'], 5, 4, 'Aged SKU listing, signed subsequent-sales evidence and net-realizable-value calculation', 'Test the USD 700,000 aged finished goods and determine whether any required impairment exceeds USD 100,000; count evidence alone is insufficient.'),
        ('ebitda', 'h2', 'Normalized recurring EBITDA', ['ebitda'], 5, 3, 'Insurance settlement, relocation invoices and recurring-profit bridge', 'Substantiate removal of USD 300,000 insurance recovery and the USD 100,000 relocation add-back; verify normalized FY2025 EBITDA of at least USD 1,100,000.'),
        ('working_capital', 'h1', 'Working-capital and collection requirements', ['working_capital'], 4, 4, 'Monthly NWC bridge, Brindle cash receipts and supported FY2027 inventory plan', 'Reconcile FY2025 NWC USD 2,600,000 and substantiate the proposed USD 1,100,000 release without unverified overdue collections or clearance assumptions.'),
        ('maintenance_capex', 'h2', 'Maintenance versus expansion CAPEX', ['maintenance_capex'], 4, 3, 'Asset-condition review, supplier invoices and maintenance budget', 'Separate the USD 600,000 sustaining investment from USD 400,000 expansion and test the sustainable maintenance cash requirement.'),
        ('cash_conversion', 'h2', 'Profitability to free-cash conversion', ['cash_conversion'], 4, 2, 'Operating cash-flow bridge and recurring maintenance forecast', 'Reconcile FY2025 EBITDA to zero CFO and negative USD 600,000 cash after maintenance CAPEX; demonstrate positive normalized cash generation before assuming it.'),
        ('concentration', 'h3', 'Customer concentration and minimum orders', ['concentration'], 3, 4, 'Brindle signed commitments, concentration bridge and customer scenario', 'Determine whether dependence can be reduced below 40% of revenue; do not count nonbinding customer forecasts as orders.'),
        ('capacity', 'h3', 'Funded practical manufacturing capacity', ['capacity'], 4, 1, 'Executed press purchase order, committed financing and installation schedule', 'Support 120,000 production-slot equivalents during FY2027 or revise the USD 12,000,000 forecast to the documented 100,000-slot capacity.'),
        ('sales_mix', 'h3', 'Product and channel revenue reconciliation', ['sales_mix'], 3, 3, 'Sales ledger by product, customer and geography', 'Tie storage USD 6,000,000 and cookware USD 4,000,000 to customer and geographic totals of USD 10,000,000 for FY2025.'),
    ]
    evidence = [
        ('income', 'financial', 'income', 'h2', 'context', [], 3, 'fy25_management_accounts', 'company_reported', None),
        ('normalization', 'financial', 'normalization', 'h2', 'context', [], 3, 'fy25_management_accounts', 'company_reported', 'reported_normalized_ebitda'),
        ('cashflow', 'financial', 'cashflow', 'h2', 'refutes', ['cash_conversion'], 3, 'fy25_management_accounts', 'company_reported', 'profit_cash'),
        ('profit_claim', 'financial', 'profit', 'h2', 'context', [], 2, 'management_cash_claim', 'company_reported', 'profit_cash'),
        ('customers', 'sales', 'customers', 'h3', 'refutes', ['concentration'], 3, 'sales_ledger', 'company_reported', 'concentration'),
        ('products', 'sales', 'products', 'h3', 'context', [], 3, 'sales_ledger', 'company_reported', None),
        ('geography', 'sales', 'geography', 'h3', 'context', [], 3, 'sales_ledger', 'company_reported', None),
        ('contracts', 'sales', 'contracts', 'h3', 'context', [], 3, 'brindle_pipeline', 'company_reported', None),
        ('sales_strength', 'sales', 'strength', 'h3', 'context', [], 2, 'sales_ledger', 'company_reported', None),
        ('inventory_claim', 'inventory', 'stock', 'h1', 'supports', ['inventory_valuation'], 2, 'management_inventory', 'company_reported', 'aged_stock'),
        ('aged_stock', 'inventory', 'aging', 'h1', 'refutes', ['inventory_valuation'], 3, 'management_inventory', 'company_reported', 'aged_stock'),
        ('inventory_growth', 'inventory', 'growth', 'h1', 'context', [], 3, 'management_inventory', 'company_reported', None),
        ('nwc', 'inventory', 'nwc', 'h1', 'context', [], 3, 'fy25_management_accounts', 'company_reported', None),
        ('receivables', 'inventory', 'receivables', 'h1', 'context', [], 3, 'brindle_receivables', 'company_reported', None),
        ('capacity', 'plant', 'capacity', 'h3', 'refutes', ['capacity'], 3, 'engineering_plan', 'company_reported', 'capacity'),
        ('capex', 'plant', 'capex', 'h2', 'refutes', ['maintenance_capex'], 3, 'engineering_plan', 'company_reported', 'capex_classification'),
        ('maintenance', 'plant', 'maintenance', 'h2', 'context', [], 3, 'engineering_plan', 'company_reported', None),
        ('ppe', 'plant', 'ppe', 'h2', 'context', [], 3, 'fy25_management_accounts', 'company_reported', None),
        ('forecast_revenue', 'forecast', 'revenue', 'h3', 'context', [], 2, 'forecast_v1', 'company_reported', None),
        ('forecast_inventory', 'forecast', 'inventory_target', 'h1', 'refutes', ['working_capital'], 3, 'forecast_v1', 'company_reported', 'inventory_plan'),
        ('forecast_qa', 'forecast', 'qa', 'h2', 'context', [], 2, 'management_cash_claim', 'company_reported', None),
        ('warehouse_count', 'count', 'counted', 'h1', 'supports', ['inventory_count'], 4, 'custodian_count', 'counterparty_reported', None),
        ('count_scope', 'count', 'limits', 'h1', 'context', [], 4, 'custodian_count', 'counterparty_reported', None),
    ]
    return dict(
        case='mf', name='Ridgeway Homeware', business='Kitchen storage and cookware manufacturing',
        documents=documents, questions=questions, evidence=evidence,
        hypotheses={
            'h1': ('FY2025 inventory and operating working capital are supportable: inventory count variance is at most 1%, no inventory impairment above USD 100,000 is required, and the planned FY2027 USD 1,100,000 NWC release is backed by collection and inventory actions.', 'Count variance <= 1%; inventory impairment <= USD 100,000; documented actions support the FY2027 NWC release.', 'nwc'),
            'h2': ('Recurring FY2025 EBITDA is at least USD 1,100,000 after substantiated normalization and cash generated from operations after sustainable maintenance CAPEX is positive.', 'Normalized EBITDA >= USD 1,100,000; operating cash less maintenance CAPEX > 0, with maintenance/expansion classification substantiated.', 'ebitda'),
            'h3': ('The FY2027 USD 12,000,000 revenue forecast is supported by funded practical production capacity and binding demand, with no customer exceeding 40% of revenue and reconciled historical product sales.', '120,000 production-slot equivalents are funded and available in FY2027; largest customer share <= 40%; FY2025 sales reconcile.', 'revenue_quality'),
        },
        source_claims=[
            ('inventory', 'inventory', 'stock', 'company_reported', 'All recorded inventory is readily saleable and no write-down is needed.', 'h1', 'contradicted'),
            ('cash', 'financial', 'profit', 'company_reported', 'FY2025 reported EBITDA of USD 1,300,000 equals operating cash generated.', 'h2', 'contradicted'),
            ('capex', 'plant', 'capex', 'company_reported', 'The entire FY2025 CAPEX amount is discretionary expansion.', 'h2', 'contradicted'),
            ('growth', 'forecast', 'revenue', 'company_reported', 'Existing and planned operations support FY2027 revenue USD 12,000,000.', 'h3', 'contradicted'),
        ],
        expected_top3={0: ['inventory_count', 'inventory_valuation', 'ebitda'], 1: ['inventory_valuation', 'ebitda', 'working_capital']},
        event_reasons={1: 'The dated complete count satisfies inventory quantity reconciliation only. Aged-stock recoverability, normalization support and the working-capital release remain open; physical existence does not establish valuation.'},
        world={
            'synthetic': True, 'currency': 'USD',
            'income_2024': {'revenue': 8000000, 'cogs': 4800000, 'opex': 2000000, 'ebitda': 1200000, 'depreciation': 300000, 'interest': 100000, 'tax': 200000, 'net_income': 600000},
            'income_2025': {'revenue': 10000000, 'cogs': 6400000, 'opex': 2300000, 'ebitda': 1300000, 'depreciation': 400000, 'interest': 150000, 'tax': 150000, 'net_income': 600000},
            'balance_2024': {'cash': 600000, 'ar': 1200000, 'inventory': 1500000, 'prepaid': 100000, 'ppe': 2000000, 'assets': 5400000, 'debt': 1800000, 'ap': 900000, 'accrued': 300000, 'deferred': 0, 'equity': 2400000},
            'balance_2025': {'cash': 300000, 'ar': 1600000, 'inventory': 2400000, 'prepaid': 100000, 'ppe': 2600000, 'assets': 7000000, 'debt': 2400000, 'ap': 1100000, 'accrued': 400000, 'deferred': 0, 'equity': 3100000},
            'cashflow_2025': {'cfo': 0, 'capex': 1000000, 'debt_raised': 600000, 'equity_raised': 200000, 'dividends': 100000, 'cash_change': -300000},
            'customers_revenue_2025': {'Brindle Retail': 4500000, 'Fern Wholesale': 2000000, 'Hearth Distribution': 1500000, 'Direct to consumer': 2000000},
            'product_revenue_2025': {'storage_units': 60000, 'storage_price': 100, 'cookware_units': 20000, 'cookware_price': 200, 'storage_revenue': 6000000, 'cookware_revenue': 4000000},
            'geography_revenue_2025': {'domestic': 8000000, 'export': 2000000},
            'inventory_2025': {'raw_materials': 800000, 'wip': 400000, 'finished_goods': 1200000, 'total': 2400000, 'aged_finished_cost': 700000, 'aged_finished_estimated_nrv': 500000, 'potential_write_down': 200000, 'count_variance': 0},
            'normalization': {'reported_ebitda': 1300000, 'insurance_recovery': 300000, 'relocation_addback': 100000, 'provisional_normalized_ebitda': 1100000},
            'capex': {'maintenance': 600000, 'expansion': 400000, 'total': 1000000, 'cfo_less_maintenance': -600000},
            'forecast': {'planned_equivalents': 120000, 'capacity_equivalents': 100000, 'per_equivalent': 100, 'revenue': 12000000, 'supported_revenue': 10000000, 'cogs': 7560000, 'opex': 2740000, 'ebitda': 1700000, 'ar': 1800000, 'inventory': 1200000, 'prepaid': 100000, 'ap': 1200000, 'accrued': 400000, 'nwc': 1500000, 'nwc_release_vs_2025': 1100000},
            'intentional_exceptions': [
                {'id': 'mf_exception_inventory', 'documents': ['inventory'], 'fact': 'Management no-write-down claim conflicts with a USD 200,000 estimated NRV shortfall. Historical statements intentionally preserve unadjusted book inventory; the estimate is provisional.', 'visible_stage': 0},
                {'id': 'mf_exception_cash', 'documents': ['financial'], 'fact': 'Reported EBITDA increases while CFO is zero and CFO after maintenance CAPEX is negative USD 600,000.', 'visible_stage': 0},
                {'id': 'mf_exception_capex', 'documents': ['plant'], 'fact': 'Management calls all CAPEX expansion although engineering schedules identify USD 600,000 maintenance.', 'visible_stage': 0},
                {'id': 'mf_exception_capacity', 'documents': ['plant', 'forecast'], 'fact': 'Forecast requires 120,000 production-slot equivalents against existing capacity of 100,000 with no funded additional press.', 'visible_stage': 0},
                {'id': 'mf_exception_inventory_plan', 'documents': ['inventory', 'forecast'], 'fact': 'Inventory halves while planned cost of sales grows; the calculated 57.9365 closing-inventory days lack documented clearance or lead-time support.', 'visible_stage': 0},
                {'id': 'mf_exception_concentration', 'documents': ['sales'], 'fact': 'A diversified-customer claim conflicts with the 45% Brindle concentration and nonbinding orders.', 'visible_stage': 0},
            ],
        },
    )
