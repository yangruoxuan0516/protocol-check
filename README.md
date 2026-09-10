# build project skeletion, with simple 02.01 examples
cd /path/to/protocol_check

python -m pip install -e ".[test]"

cp config.example.toml config.toml

*Edit config.toml locally with the real Qwen endpoint and API key.*

python -m compileall .

python -m pytest -q

*Run checks against real data:*

python run.py \
  --input /path/to/nios.jsonl \
  --check COR-02.01.single_shall \
  --output outputs/single_shall.jsonl

python run.py \
  --input /path/to/nios.jsonl \
  --check COR-02.01.factual_correct \
  --limit 10 \
  --output outputs/factual_correct_sample.jsonl

python run.py \
  --input /path/to/nios.jsonl \
  --requirement COR-02.01 \
  --output outputs/cor_02_01.jsonl

python run.py \
  --input /path/to/nios.jsonl \
  --all \
  --output outputs/all_results.jsonl



# previous checks were single-nio only, now add a cross-nio check

python run.py \
  --input nios.jsonl \
  --check COR-02.12.not_duplicate \
  --limit 5 \
  --output outputs/not_duplicate_5.jsonl



# add 664 retrieval, retrieve only, not input to qwen yet

Inspect five configured protocol requirements:
python run.py \
  --inspect-standard-retrieval \
  --limit 5 \
  --top-k 5 \
  -o retrieval_outputs/arinc_retrieval_5.jsonl

Equivalent with explicit protocol input:
python run.py \
  --input /path/to/protocol.jsonl \
  --inspect-standard-retrieval \
  --limit 5 \
  --top-k 5 \
  -o retrieval_outputs/arinc_retrieval_5.jsonl

Force cache rebuilding:
python run.py \
  --inspect-standard-retrieval \
  --limit 5 \
  --top-k 5 \
  --rebuild-embeddings \
  -o retrieval_outputs/arinc_retrieval_rebuilt.jsonl

Rerun while replacing an existing inspection output:
python run.py \
  --inspect-standard-retrieval \
  --limit 5 \
  --top-k 5 \
  --overwrite \
  -o retrieval_outputs/arinc_retrieval_5.jsonl


# add factual check with 664 ref
Run against a one-record JSONL containing the selected NIO:
python run.py \
  --input /path/to/selected_nio.jsonl \
  --check COR-02.01.factual_correct_arinc \
  -o outputs/factual_arinc_selected.jsonl

Run on the first five NIO records:
python run.py \
  --check COR-02.01.factual_correct_arinc \
  --limit 5 \
  -o outputs/factual_arinc_5.jsonl
  
Compare both factual implementations on the same first five targets:
python run.py \
  --requirement COR-02.01 \
  --limit 5 \
  -o outputs/cor_02_01_comparison_5.jsonl


# build an offline Matrix + Result Explorer report

The report reads the protocol path from `[data].protocol` in `config.toml`.
Select the result files explicitly with either a directory or a file list:

python reporting/build_report.py \
  --results-dir results/final \
  -o reports/protocol_report.html

python reporting/build_report.py \
  --results \
    outputs/single_shall.jsonl \
    outputs/factual_correct_arinc.jsonl \
    outputs/not_duplicate.jsonl \
  -o reports/protocol_report.html

The generated HTML is self-contained and can be opened directly without a
web server or network connection. Use `--overwrite` to replace an existing
report file explicitly.
