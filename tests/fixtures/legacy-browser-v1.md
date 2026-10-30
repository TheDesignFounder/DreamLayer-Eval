# Legacy bundle fixture

`legacy-browser-v1.zip` is the original synthetic offline browser experiment from
the schema-1 implementation. The bundled media are programmatic test fixtures,
not user research data. SHA-256:

`584a1774f820e7325d0c5cd54d570bed38de5b48ea0250093e86d87d624274cf`

Keep this file immutable. Browser and replay tests use its old evaluator records
to detect silent re-evaluation, judge re-submission, or lost supersession links.
Runtime results belong in the ignored `.research/` directory or a CI artifact.
