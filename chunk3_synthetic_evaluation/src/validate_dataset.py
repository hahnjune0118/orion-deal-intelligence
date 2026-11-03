import json,sys
from orion.synthetic import validate_dataset
if __name__=='__main__':
    report=validate_dataset(sys.argv[1] if len(sys.argv)>1 else 'chunk3_synthetic_evaluation')
    print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
