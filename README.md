# build project skeletion, with simple 02.01 examples
cd /path/to/protocol_check

python3.9 -m pip install -e ".[test]"

cp config.example.toml config.toml

*Edit config.toml locally with the real Qwen endpoint and API key.*

python3.9 -m compileall .

python3.9 -m pytest -q

*Run checks against real data:*

python3.9 run.py \
  --input /path/to/nios.jsonl \
  --check COR-02.01.single_shall \
  --output outputs/single_shall.jsonl

python3.9 run.py \
  --input /path/to/nios.jsonl \
  --check COR-02.01.factual_correct \
  --limit 10 \
  --output outputs/factual_correct_sample.jsonl

python3.9 run.py \
  --input /path/to/nios.jsonl \
  --requirement COR-02.01 \
  --output outputs/cor_02_01.jsonl

python3.9 run.py \
  --input /path/to/nios.jsonl \
  --all \
  --output outputs/all_results.jsonl



# previous checks were single-nio only, now add a cross-nio check

python3.9 run.py \
  --input nios.jsonl \
  --check COR-02.12.not_duplicate \
  --limit 5 \
  --output outputs/not_duplicate_5.jsonl