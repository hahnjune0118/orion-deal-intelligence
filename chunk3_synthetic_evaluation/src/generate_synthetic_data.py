"""Run from installed integrated repository: python this_file.py OUTPUT_DIRECTORY."""
import json,sys
from orion.synthetic import generate_dataset
if __name__=='__main__':print(json.dumps(generate_dataset(sys.argv[1] if len(sys.argv)>1 else 'chunk3_synthetic_evaluation'),indent=2))
