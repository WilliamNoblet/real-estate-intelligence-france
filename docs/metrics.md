# Dictionnaire des métriques

Pour chaque métrique : définition, formule, sources, hypothèses, biais (§118). À compléter au fil des phases.

## Prix / annonces (prix DEMANDÉ)
- `asking_price_per_m2 = price_eur / surface_m2`
- `total_price_drop_pct = (current_price - initial_price) / initial_price * 100`
- `observed_days_online = last_seen_at - first_seen_at` (⚠ *observé*, pas *publié* — §48)
- `days_before_first_drop`, `price_decrease_count`, `lowest_price`…

## Transactions (prix PAYÉ — DVF)
- `price_per_m2` (transaction), `median_transaction_price_per_m2`, `Q1`, `Q3`, `year_over_year_change`.
- Comparables : **médiane / Q1 / Q3 / IQR / n** sur un rayon+période élargis en zone peu dense (§63-64).

## Écart marché (à formuler avec prudence, §66)
- `market_gap_pct = (asking_price_per_m2 - local_dvf_median_per_m2) / local_dvf_median_per_m2 * 100`
- Formulation : « +X % vs la médiane des transactions comparables sélectionnées » — **jamais** « surévalué de X % ».

## Biais à toujours exposer (§132)
Prix demandé ≠ prix payé · retrait ≠ vente · `first_seen` ≠ publication · adresse parfois approximative · échantillon = seulement les sources couvertes (`source_coverage`, §71).
