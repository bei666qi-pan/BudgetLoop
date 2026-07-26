# AI gateway source checkouts

Run `scripts/fetch-ai-gateways.sh` to reproduce the detached shallow New API
checkout declared in `manifest.yaml`. The generated `new-api/` directory is
ignored by the parent repository because it is its own Git checkout; the pinned
revision, release and license boundary remain versioned here.

New API runs as a separate AGPL-3.0 service and communicates with the MIT
BudgetLoop control plane over HTTP. BudgetLoop does not import or fork its Go or
web code and does not recreate its protocol conversion, channel administration,
weighted routing, retries, rate limiting or accounting.

Only legally authorized upstream services and credentials may be configured.
Operating a public generative-AI or resale service can create additional filing,
content-safety, privacy, tax and upstream-contract obligations.
