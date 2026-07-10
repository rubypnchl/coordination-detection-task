# Null model summary for dev

This file summarises a matched randomisation null model.

For each tested candidate group, I generated random groups with the same key type and same post count. I then computed the same coordination score for each random group and compared the observed score against this null distribution.

Empirical p-value:

```text
p = (1 + number of null scores >= observed score) / (1 + number of null samples)
```

- Number of tested candidates: 50
- Null samples per candidate: 100
- Max candidates requested: 50

## Aggregate null results

- Mean null p-value: 0.0099
- Median null p-value: 0.0099
- Candidates with p <= 0.05: 50
- Candidates with p <= 0.10: 50

## Top candidates by null-adjusted score

| key_type   | key_value                                                                                                                                                  |   post_count |   account_count |   coordination_score |   null_mean_score |   null_95th_percentile |   null_p_value |   final_score_with_null |
|:-----------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------|-------------:|----------------:|---------------------:|------------------:|-----------------------:|---------------:|------------------------:|
| url        | youtu.be/qmcwyyronuy                                                                                                                                       |            4 |               4 |             0.891597 |          0.233053 |               0.44     |     0.00990099 |                0.88277  |
| url        | gaceta.es/espana/vox-logra-tumbar-la-zona-de-bajas-emisiones-de-malaga-acabamos-con-una-imposicion-del-pp-para-saquear-a-los-malaguenos-20260610-2009      |           16 |              14 |             0.86393  |          0.261838 |               0.2625   |     0.00990099 |                0.855377 |
| url        | www.lefigaro.fr/vox/politique/l-editorial-d-yves-threard-suppression-des-zfe-censuree-la-democratie-baillonnee-20260522                                    |            4 |               4 |             0.847171 |          0.218101 |               0.44     |     0.00990099 |                0.838784 |
| url        | mol.im/a/15854487                                                                                                                                          |            3 |               3 |             0.834347 |          0.230097 |               0.43     |     0.00990099 |                0.826086 |
| url        | youtu.be/vdtcbqgk79s                                                                                                                                       |            3 |               3 |             0.83     |          0.245061 |               0.43     |     0.00990099 |                0.821782 |
| url        | okdiario.com/madrid/alcorcon-gasta-3-millones-implantar-zona-bajas-emisiones-tantas-exenciones-que-no-afecta-nadie-17377546                                |            5 |               5 |             0.824563 |          0.214666 |               0.223458 |     0.00990099 |                0.8164   |
| url        | gaceta.es/espana/la-justicia-declara-nula-de-pleno-derecho-y-sin-costas-la-zona-de-bajas-emisiones-de-guadalajara-por-ser-contraria-a-la-ley-20260427-1809 |            4 |               4 |             0.819979 |          0.230279 |               0.44     |     0.00990099 |                0.811861 |
| url        | www.ecologistasenaccion.org/370591/ecologistas-propone-recuperar-la-zona-de-bajas-emisiones-inicial-y-ampliarla-en-2028                                    |            3 |               3 |             0.81584  |          0.233324 |               0.430118 |     0.00990099 |                0.807762 |
| url        | youtube.com/shorts/-bvn5byx8pk                                                                                                                             |            4 |               4 |             0.815285 |          0.226004 |               0.44     |     0.00990099 |                0.807213 |
| url        | lnk_219027793821549.example                                                                                                                                |            6 |               6 |             0.815244 |          0.223785 |               0.235195 |     0.00990099 |                0.807172 |
| url        | www.abc.es/espana/madrid/supremo-avala-anulacion-zonas-bajas-emisiones-madrid-20260421120858-nt.html                                                       |            5 |               5 |             0.80131  |          0.220027 |               0.223593 |     0.00990099 |                0.793376 |
| url        | cadenaser.com/andalucia/2026/06/10/los-tribunales-tumban-la-zona-de-bajas-emisiones-de-malaga-ser-malaga                                                   |            4 |               4 |             0.781854 |          0.233422 |               0.44     |     0.00990099 |                0.774113 |
| url        | youtu.be/_avq47n7gdk                                                                                                                                       |            8 |               8 |             0.777801 |          0.242136 |               0.2425   |     0.00990099 |                0.7701   |
| url        | youtu.be/oegxneevywy                                                                                                                                       |           11 |              11 |             0.775989 |          0.262227 |               0.2625   |     0.00990099 |                0.768305 |
| url        | lnk_273709032825232.example                                                                                                                                |            5 |               5 |             0.771861 |          0.219903 |               0.230499 |     0.00990099 |                0.764219 |
