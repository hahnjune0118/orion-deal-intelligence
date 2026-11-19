"""Reproduce the public synthetic MVP experiment, without local deal data."""
import csv
import hashlib
import json
from pathlib import Path

from orion.rules.benchmark import evaluate


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/'build'/'rules-mvp-evaluation';output.mkdir(parents=True,exist_ok=True)
    result=evaluate()
    result['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src/orion/rules').glob('*.py')}
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (output/'policy-comparison.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result['rows'][0]));writer.writeheader();writer.writerows(result['rows'])
    with (output/'independent-review-template.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['case','question_id','reviewer','source_relevance_0_to_2','actionability_0_to_2','critical_0_or_1','notes'])
        for case in sorted({r['case'] for r in result['rows']}):
            for i in range(5):writer.writerow([case,'eval.'+str(i),'','','','',''])
    print(f"Completed {len(result['rows'])} authored synthetic policy comparisons; independent review not run.")
    print(output)


if __name__=='__main__':main()
