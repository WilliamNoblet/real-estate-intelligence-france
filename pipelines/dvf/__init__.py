"""Pipeline DVF (Phase 2). Source : DVF géolocalisées (geo-dvf).

Étapes : download -> validate -> parse (+ regroupement id_mutation) -> normalize
-> quality -> load -> aggregate. Idempotent (SHA256 + ingestion_batch) ;
raw immuable dans data/raw/dvf/."""
