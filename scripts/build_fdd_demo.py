"""Rebuild the explicitly synthetic FDD teaching pack (no client/source data)."""
from pathlib import Path
import csv
from decimal import Decimal as D
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1] / "src/orion/resources/fdd_lab"


def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    documents = []

    def write(name, rows, description):
        with (ROOT / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        documents.append(dict(id=name.removesuffix(".csv"), filename=name, version=1,
                              description=description, classification="synthetic",
                              sha256=hashlib.sha256((ROOT / name).read_bytes()).hexdigest()))

    opening = dict(ar=280, inventory=110, other_assets=24, ap=180, other_liabilities=40)
    months, trial, segments = [], [], []
    previous_nwc = sum(opening[k] for k in ("ar", "inventory", "other_assets")) - opening["ap"] - opening["other_liabilities"]
    for i in range(24):
        year, month = 2024 + i // 12, i % 12 + 1
        period = f"{year}-{month:02}"
        season = [0, -30, 10, 20, 0, 30, -20, 10, 40, 50, 70, 120][month - 1]
        revenue = 900 + i * 16 + season
        cogs = D(revenue) * D("0.48")
        opex = D(220) + D(revenue) * D("0.18")
        if period == "2025-07":
            opex += 35  # Recorded, non-recurring litigation expense.
        if period == "2025-09":
            opex += 18  # Recorded shareholder personal expense.
        ar, inventory, ap = 280 + i * 6, 110 + i * 2, 180 + i * 3
        other_assets, other_liabilities = 24 + i // 4, 40 + i // 3
        nwc = ar + inventory + other_assets - ap - other_liabilities
        ebitda = D(revenue) - cogs - opex
        da, interest, tax_paid = D(22 + i // 12 * 3), D(6), D(18 + i // 12 * 4)
        noncash, other_operating = D(2), D(-1)
        ocf = ebitda - interest - tax_paid - D(nwc - previous_nwc) + noncash + other_operating
        row = dict(period=period, revenue=revenue, cogs=cogs, opex=opex, da=da,
                   ar=ar, inventory=inventory, other_assets=other_assets, ap=ap,
                   other_liabilities=other_liabilities, cash=180 + i * 4,
                   restricted_cash=30, borrowings=900 - i * 5, lease_liability=120,
                   interest_paid=interest, tax_paid=tax_paid, noncash=noncash,
                   other_operating=other_operating, operating_cash=ocf,
                   maintenance_capex=12, growth_capex=18 + i // 12 * 2)
        months.append(row)
        trial.append(dict(period=period, revenue=D(revenue) - (12 if period == "2025-12" else 0),
                          cogs=cogs, opex=opex, da=da))
        for segment, share in [("기업 구독", D("0.60")), ("중견기업 구독", D("0.25")), ("구축 서비스", D("0.15"))]:
            segments.append(dict(period=period, segment=segment, revenue=D(revenue) * share,
                                 cogs=cogs * share))
        previous_nwc = nwc
    write("monthly_financials.csv", months, "관리손익·재무상태·현금흐름 | 월별, 비용·잔액은 양수; other_operating은 부호 있는 현금 영향")
    write("trial_balance.csv", trial, "시산표 손익 집계 | 2025-12 매출 12의 미전기 차이를 의도적으로 포함")
    write("gl_balances.csv", [dict(period=r['period'], account_code=code, account_name=name,
                                 balance=D(str(r[metric])) * sign)
                              for r in trial for code, name, metric, sign in
                              [('4000', '구독·구축 매출', 'revenue', -1), ('5000', '매출원가', 'cogs', 1),
                               ('6000', '영업비용', 'opex', 1), ('6500', '감가상각비', 'da', 1)]],
          "총계정원장 계정별 월 잔액 집계 | 차변 + / 대변 −, 계정 매핑 후 시산표와 대사")
    statutory = []
    for year in (2024, 2025):
        for metric in ("revenue", "cogs", "opex", "da"):
            statutory.append(dict(year=year, metric=metric,
                                  amount=sum(D(str(r[metric])) for r in trial if r["period"].startswith(str(year)))))
    write("statutory_financials.csv", statutory, "연간 외부재무제표 역할의 합성 수치; 실제 감사자료가 아님")
    write("revenue_segments.csv", segments, "상호 배타적인 사업부문별 월 매출·원가; 관리손익 합계와 일치")
    write("adjustment_ledger.csv", [
        dict(id="GL-001", period="2025-07", account="litigation_expense", amount=35, description="일회성 소송 합의 비용, 관리손익에 포함"),
        dict(id="GL-002", period="2025-09", account="shareholder_personal", amount=18, description="주주 개인 비용, 관리손익에 포함"),
        dict(id="GL-003", period="2025-12", account="maintenance_underaccrual", amount=12, description="지속 발생 유지보수 비용 미계상; EBITDA 차감 및 별도 부채성 항목"),
        dict(id="GL-004", period="2025-12", account="ar_reserve", amount=20, description="91일 초과 채권에 대한 추가 충당금 후보"),
        dict(id="GL-005", period="2025-12", account="bonus_payable", amount=25, description="거래 전 미지급 성과급; 월별 NWC 기타부채에 포함되지 않음"),
    ], "조정 후보의 계정·기간·금액을 확인하는 합성 원장 발췌")
    end = months[-1]
    aging = []
    for account in ("ar", "inventory", "ap"):
        first = D(str(end[account]))
        amounts = [first * D("0.65"), first * D("0.20"), first * D("0.10")]
        amounts.append(first - sum(amounts))
        for bucket, amount in zip(("0–30일", "31–60일", "61–90일", "91일 이상"), amounts):
            aging.append(dict(period="2025-12", account=account, bucket=bucket, amount=amount))
    write("aging.csv", aging, "2025-12 AR·재고·AP 연령; 총액이 월별 잔액에 대사됨")
    budget = []
    for i in range(12):
        revenue = D(1500 + i * 20)
        budget.append(dict(period=f"2026-{i + 1:02}", revenue=revenue,
                           ebitda=revenue * D("0.24"), contracted_revenue=revenue * D("0.60"),
                           capacity_revenue=1700, assumption="합성 경영계획, 확정 실적이 아님"))
    write("budget.csv", budget, "2026 합성 경영계획과 계약 커버리지·매출 환산 공급능력 가정")
    manifest = dict(schema=1, classification="synthetic", company="Northstar FDD Lab",
                    notice="기존 Northstar 증빙팩과 별개의 재무 분석 검증용 합성 자료. 실제 회사·감사자료가 아닙니다.",
                    currency="USD", unit="천 달러", start="2024-01", end="2025-12",
                    opening_period="2023-12", opening_nwc=opening, documents=documents)
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline='\n')


if __name__ == "__main__":
    build()
