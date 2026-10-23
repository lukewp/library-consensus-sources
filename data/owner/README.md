# Owner type and access model

`out-*.jsonl` holds one line per platform domain:

```json
{"domain": "...", "owner": "...", "owner_type": "commercial|nonprofit|educational|government|intergovernmental|individual|unknown", "access_model": "free|free_with_account|freemium|subscription|institutional|pay_per_use|mixed|unknown", "category": "...", "confidence": "high|medium|low"}
```

The lines were produced by a language model (Claude), from each domain plus the sample titles and vendor names the libraries gave for it. No web lookups were used at this step. Confidence is the model's own, so treat `low`, and `unknown` values, as unverified.

To reproduce: run `scripts/make_domains.py`, split `data/domains.json` into batches of 250 (`domain`, the first 3 `titles`, the first 2 `vendors`, `max_libraries`), and give each batch to a model with the definitions in `METHOD.md` §4. Corrections are welcome as pull requests to these files.
