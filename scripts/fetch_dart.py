#!/usr/bin/env python3
"""OpenDART annual CFS -> sourced dashboard JSON + raw JSON + Markdown report.
Python standard library only. Never place DART_API_KEY in a file or URL on GitHub.
"""
import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib import parse, request
import zipfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
KEY = os.environ.get('DART_API_KEY', '').strip()
BASE = 'https://opendart.fss.or.kr/api/'
YEARS = (2022, 2023, 2024, 2025)

# Exact XBRL taxonomy IDs; do NOT substring-match loosely and misattribute accounts.
ACCOUNTS = {
    'revenue': ('IS', ('ifrs-full_Revenue', 'ifrs_Revenue', 'ifrs-full_RevenueFromContractsWithCustomers')),
    'operating_profit': ('IS', ('dart_OperatingIncomeLoss',)),
    'net_income': ('IS', ('ifrs-full_ProfitLoss', 'ifrs_ProfitLoss')),
    'assets': ('BS', ('ifrs-full_Assets', 'ifrs_Assets')),
    'current_assets': ('BS', ('ifrs-full_CurrentAssets', 'ifrs_CurrentAssets')),
    'current_liabilities': ('BS', ('ifrs-full_CurrentLiabilities', 'ifrs_CurrentLiabilities')),
    'liabilities': ('BS', ('ifrs-full_Liabilities', 'ifrs_Liabilities')),
    'equity': ('BS', ('ifrs-full_Equity', 'ifrs_Equity')),
    'cfo': ('CF', ('ifrs-full_CashFlowsFromUsedInOperatingActivities', 'ifrs_CashFlowsFromUsedInOperatingActivities')),
}
REQUIRED = ('revenue', 'operating_profit', 'net_income', 'assets', 'liabilities', 'equity', 'current_assets', 'current_liabilities', 'cfo')


def api_bytes(endpoint, **params):
    """Never print full authenticated URLs, including exception details."""
    q = parse.urlencode({'crtfc_key': KEY, **params})
    try:
        with request.urlopen(request.Request(BASE+endpoint+'?'+q, headers={'User-Agent':'student-dart-financial-dashboard/1.0'}), timeout=45) as resp:
            return resp.read()
    except Exception:
        raise RuntimeError('DART 통신 실패: 인터넷, 인증키 상태 또는 요청 제한을 확인하세요.') from None


def api_json(endpoint, **params):
    try:
        result = json.loads(api_bytes(endpoint, **params).decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError):
        raise RuntimeError('DART가 JSON 형식의 응답을 반환하지 않았습니다.') from None
    if result.get('status') != '000':
        raise RuntimeError('DART 응답 오류 코드 {}: {}'.format(result.get('status'), result.get('message')))
    return result


def find_code():
    archive = zipfile.ZipFile(io.BytesIO(api_bytes('corpCode.xml')))
    xml_file = next((n for n in archive.namelist() if n.lower().endswith('.xml')), None)
    if not xml_file:
        raise RuntimeError('DART 기업고유번호 목록을 열 수 없습니다.')
    root = ElementTree.fromstring(archive.read(xml_file))
    found = []
    for node in root.findall('.//list'):
        if (node.findtext('stock_code') or '').strip() == '000720' and (node.findtext('corp_name') or '').strip() == '현대건설':
            found.append((node.findtext('corp_code') or '').strip())
    if len(found) != 1 or not re.fullmatch(r'\d{8}', found[0]):
        raise RuntimeError('현대건설(종목코드 000720) 고유번호를 하나로 확인하지 못했습니다.')
    return found[0]


def parse_amount(value):
    if value is None:
        return None
    s = str(value).replace(',', '').replace(' ', '').strip()
    if s in ('', '-', '—', '–'):
        return None
    if s.startswith('(') and s.endswith(')'):
        s = '-'+s[1:-1]
    if not re.fullmatch(r'-?\d+', s):
        return None
    return int(s)


def extract(data, key):
    statement, ids = ACCOUNTS[key]
    lines = [r for r in data.get('list', []) if r.get('sj_div') == statement]
    for account_id in ids:
        candidates = [r for r in lines if r.get('account_id') == account_id and r.get('currency', 'KRW') == 'KRW']
        values = {parse_amount(r.get('thstrm_amount')) for r in candidates}
        values.discard(None)
        if len(values) == 1:
            return next(iter(values)), None
        if len(values) > 1:
            return None, f'{key}: 동일 표준계정 {account_id}에 금액이 여러 개 있어 확인 필요'
    return None, f'{key}: 연결 {statement}에서 매칭되는 표준계정을 찾지 못함'


def div(a,b, scale=1):
    return round(a / b * scale, 4) if a is not None and b not in (None, 0) else None


def derive(rows):
    prior = None
    for row in rows:
        v = row['financials']; prev = prior['financials'] if prior else None
        ratio = {
            'revenue_growth_pct': round((v['revenue']/prev['revenue']-1)*100,4) if prev and v['revenue'] is not None and prev['revenue'] not in (None,0) else None,
            'operating_margin_pct': div(v['operating_profit'],v['revenue'],100),
            'net_margin_pct': div(v['net_income'],v['revenue'],100),
            'current_ratio_pct': div(v['current_assets'],v['current_liabilities'],100),
            'debt_to_equity_pct': div(v['liabilities'],v['equity'],100),
            'roa_pct': div(v['net_income'], (v['assets'] + prev['assets'])/2,100) if prev and all(x is not None for x in (v['net_income'],v['assets'],prev['assets'])) else None,
            'roe_pct': div(v['net_income'], (v['equity'] + prev['equity'])/2,100) if prev and all(x is not None for x in (v['net_income'],v['equity'],prev['equity'])) else None,
        }
        row['ratios'] = ratio
        prior = row
    return rows


def report_text(payload):
    labels={'revenue':'매출액','operating_profit':'영업이익','net_income':'당기순이익(연결 전체)','assets':'자산총계','liabilities':'부채총계','equity':'자본총계','current_assets':'유동자산','current_liabilities':'유동부채','cfo':'영업활동현금흐름'}
    ratlabels={'revenue_growth_pct':'매출증가율','operating_margin_pct':'영업이익률','net_margin_pct':'순이익률','current_ratio_pct':'유동비율','debt_to_equity_pct':'부채비율','roa_pct':'ROA (평균자산)','roe_pct':'ROE (평균총자본)'}
    rows = payload['rows']
    lines=['# 현대건설 2022~2025년 재무 분석 — DART 직접 수집','',
           '> 연간 사업보고서(11011), K-IFRS 연결(CFS), 금액 원(KRW). 수집시점: '+payload['updated_at']+'.','',
           '## 1. 공시 근거', '']
    for row in rows:
        lines.append(f"- {row['year']}: [DART 사업보고서 재무제표](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row['rcept_no']}) (접수번호 {row['rcept_no']})")
    lines += ['', '## 2. 주요 재무수치', '', '| 항목 (원) | '+' | '.join(str(r['year']) for r in rows)+' |','|---|'+'---:|'*len(rows)]
    for key,label in labels.items():
        lines.append('| '+label+' | '+' | '.join(f"{r['financials'][key]:,}" if r['financials'][key] is not None else '자료 확인 필요' for r in rows)+' |')
    lines += ['', '## 3. 재무비율', '', '| 지표 (%) | '+' | '.join(str(r['year']) for r in rows)+' |','|---|'+'---:|'*len(rows)]
    for key,label in ratlabels.items():
        lines.append('| '+label+' | '+' | '.join(f"{r['ratios'][key]:.2f}%" if r['ratios'][key] is not None else '—' for r in rows)+' |')
    lines += ['', '## 4. 분석 순서 (교수님 제공 재무가이드)', '',
      '1. **매출 성장:** 매출액 및 매출증가율. 원인(물량·단가·수주 인식)은 별도 주석 확인 전 추정하지 않음.',
      '2. **이익률:** 영업이익률·순이익률. 일회성 손익과 공사예정원가는 사업보고서 주석 확인 필요.',
      '3. **현금흐름:** CFO와 순이익 비교. CAPEX 미수집 상태에서 FCF 계산하지 않음.',
      '4. **차입 부담:** 유동비율·총부채/자본. 차입금만의 수치가 아니며 이자보상배율은 자료 확보 후 산출.',
      '5. **투자수익률:** ROA·ROE(전·당기 기말 잔액의 평균 사용). 2022년은 2021년 수치 미수집으로 계산하지 않음. ROIC는 미산출.',
      '6. **시장평가:** 해당 날짜 주가·EPS 등 미수집으로 PER/PBR/EV 배수 미산출.', '',
      '## 5. 건설업에서 별도로 확인할 자료', '',
      '- 수주 및 수주잔고, 계약자산(미청구공사), 매출채권·대손충당금, 공사손실충당부채, PF 보증·우발채무.',
      '- 이 항목들의 **금액과 원인은 현재 자동수집 범위 밖**이며 각 연도 사업보고서 주석에서 확인해야 함.', '',
      '## 6. 계산식·주의사항', '',
      '- 매출증가율 = (당기 매출 / 전기 매출 − 1) ×100.',
      '- 영업이익률 = 영업이익 / 매출액 ×100; 순이익률 = 당기순이익 / 매출액 ×100.',
      '- 유동비율 = 유동자산 / 유동부채 ×100; 부채비율 = 총부채 / 자본총계 ×100.',
      '- ROA = 당기순이익 / ((당기 총자산+전기 총자산)/2) ×100.',
      '- ROE = 연결 전체 순이익 / ((당기 연결 총자본+전기 연결 총자본)/2) ×100. 지배기업 소유주 기준 ROE와 혼용하지 않음.',
      '- 표준 XBRL 계정 매칭 실패·중복은 0으로 채우지 않고 결측 처리.',
      '- 공시 숫자와 해석을 구분하며, 공시 없이 증감 원인을 단정하지 않음.','']
    all_warn=[f"{r['year']}: {note}" for r in rows for note in r['warnings']]
    if all_warn:
        lines += ['## 7. 데이터 품질 확인 필요',''] + ['- '+n for n in all_warn] + ['']
    return '\n'.join(lines)


def main():
    if not KEY:
        raise RuntimeError('GitHub Settings → Secrets and variables → Actions에서 DART_API_KEY 등록 후 실행하세요.')
    code = find_code()
    rows=[]
    for year in YEARS:
        data=api_json('fnlttSinglAcntAll.json',corp_code=code,bsns_year=str(year),reprt_code='11011',fs_div='CFS')
        rawpath=ROOT/'data'/'raw'/f'dart_{year}.json'
        rawpath.parent.mkdir(parents=True,exist_ok=True)
        rawpath.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        records=data.get('list',[])
        receipts=sorted({r.get('rcept_no','') for r in records if re.fullmatch(r'\d{14}',r.get('rcept_no',''))})
        if len(receipts)!=1:
            raise RuntimeError(f'{year}: 연간 보고서 접수번호를 유일하게 확인하지 못했습니다.')
        financials={}; warnings=[]
        for key in REQUIRED:
            financials[key],warning=extract(data,key)
            if warning: warnings.append(warning)
        rows.append({'year':year,'rcept_no':receipts[0],'financials':financials,'warnings':warnings})
    payload={'company':'현대건설','stock_code':'000720','corp_code':code,'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
             'source':'OpenDART fnlttSinglAcntAll.json, annual 11011, consolidated CFS; unit KRW', 'rows':derive(rows)}
    dest=ROOT/'site'/'data'/'financials.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    rpt=ROOT/'report'/'analysis.md';rpt.parent.mkdir(parents=True,exist_ok=True)
    rpt.write_text(report_text(payload),encoding='utf-8')
    print(f"연간 공시 {len(rows)}건 수집 완료, 대시보드 데이터 및 보고서 생성. 항목 누락: {sum(len(r['warnings']) for r in rows)}건")

if __name__=='__main__':
    try:
        main()
    except RuntimeError as e:
        print('오류: '+str(e),file=sys.stderr)
        sys.exit(1)
