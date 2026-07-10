# Null model summary for eval

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

| key_type   | key_value                                                                                                                                                               |   post_count |   account_count |   coordination_score |   null_mean_score |   null_95th_percentile |   null_p_value |   final_score_with_null |
|:-----------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------:|----------------:|---------------------:|------------------:|-----------------------:|---------------:|------------------------:|
| url        | www.palestinechronicle.com/up-to-19-million-palestinians-internally-displaced-in-gaza-unrwa                                                                             |            4 |               3 |             0.847905 |          0.287356 |               0.482415 |     0.00990099 |                0.83951  |
| url        | www.haaretz.com/gaza/2026-06-13/ty-article/.premium/unrwa-fires-70-staff-accused-by-israel-of-hamas-ties-amid-fears-of-idf-attacks/0000019e-bfd4-d5d3-a9ff-fff55f580000 |            3 |               3 |             0.833753 |          0.321031 |               0.521703 |     0.00990099 |                0.825498 |
| url        | lnk_136918978445400.example                                                                                                                                             |            3 |               3 |             0.822683 |          0.312559 |               0.48568  |     0.00990099 |                0.814538 |
| url        | www.reuters.com/world/middle-east/israel-establish-defence-offices-former-unrwa-east-jerusalem-compound-2026-05-17                                                      |            4 |               4 |             0.818754 |          0.270268 |               0.477614 |     0.00990099 |                0.810648 |
| url        | nius.de/articles/c54989ff-3052-469f-9226-667e13f77f41                                                                                                                   |            6 |               5 |             0.79033  |          0.251999 |               0.46     |     0.00990099 |                0.782505 |
| url        | lnk_271286450936445.example                                                                                                                                             |            4 |               4 |             0.784636 |          0.256001 |               0.445568 |     0.00990099 |                0.776868 |
| url        | lnk_86480607605220.example                                                                                                                                              |            4 |               4 |             0.7775   |          0.261289 |               0.468692 |     0.00990099 |                0.769802 |
| url        | www.jpost.com/middle-east/article-899656                                                                                                                                |            4 |               4 |             0.774232 |          0.267989 |               0.478886 |     0.00990099 |                0.766566 |
| url        | trib.al/xggm4l2                                                                                                                                                         |            3 |               3 |             0.773199 |          0.298153 |               0.493867 |     0.00990099 |                0.765544 |
| url        | lnk_196497459936007.example                                                                                                                                             |           11 |               9 |             0.770135 |          0.271139 |               0.300447 |     0.00990099 |                0.76251  |
| url        | niw.nl/een-paar-rotte-appels-unrwa-ontslaat-70-medewerkers-om-hamasbanden                                                                                               |            3 |               3 |             0.756654 |          0.326006 |               0.495033 |     0.00990099 |                0.749162 |
| url        | www.nikkei.com/article/dgxzqocb172ts0x10c26a5000000                                                                                                                     |            5 |               5 |             0.752293 |          0.266847 |               0.457976 |     0.00990099 |                0.744845 |
| url        | youtube.com/shorts/jqz3wtkvsmm                                                                                                                                          |            5 |               5 |             0.75     |          0.274971 |               0.458282 |     0.00990099 |                0.742574 |
| url        | www.iltempo.it/esteri/2026/05/06/news/gaza-agenzia-usa-contro-unrwa-altri-4-membri-coinvolti-nel-7-ottobre--47597555                                                    |            3 |               3 |             0.745303 |          0.288943 |               0.491033 |     0.00990099 |                0.737924 |
| url        | youtu.be/fgeiwgpjiwq                                                                                                                                                    |            4 |               4 |             0.743947 |          0.267925 |               0.486199 |     0.00990099 |                0.736581 |
