ToolGate

## Demo CLI

Install dependencies:

```bash
pip install pydantic typer pyyaml python-dotenv
```

Run the demo scenarios:

```bash
export GATEWAY_SECRET="dev-secret"
python -m gateway.demo.cli run --profile configs/policy_practical.yaml
```

Generate an approval token from an approval request:

```bash
python -m gateway.demo.cli approve --input-file approval.json
```

Receipts are written to `./receipts.log` by default (override with `--receipts`).
