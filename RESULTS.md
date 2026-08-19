# persona_gap results


## Arm 1: acc(edu-high) - acc(edu-low), TruthfulQA

- sonnet: gap=+0.008 [-0.010, +0.025], flip_rate(edu-high)=0.016, flip_rate(edu-low)=0.016, n=398, refusal+parse_fail: edu-high=1, edu-low=2
  - exploratory mmlu: gap=+0.010
  - exploratory mmlupro: gap=-0.021
- luna: gap=+0.018 [-0.010, +0.045], flip_rate(edu-high)=0.039, flip_rate(edu-low)=0.042, n=400, refusal+parse_fail: edu-high=0, edu-low=0
  - exploratory mmlu: gap=+0.020
  - exploratory mmlupro: gap=+0.025
- dsflash: gap=+0.025 [-0.007, +0.058], flip_rate(edu-high)=0.064, flip_rate(edu-low)=0.060, n=400, refusal+parse_fail: edu-high=0, edu-low=0
  - exploratory mmlu: gap=+0.016
  - exploratory mmlupro: gap=-0.006
- qwen: gap=+0.045 [+0.020, +0.072], flip_rate(edu-high)=0.018, flip_rate(edu-low)=0.039, n=400, refusal+parse_fail: edu-high=0, edu-low=0
  - exploratory mmlu: gap=+0.005
  - exploratory mmlupro: gap=-0.020

## Arm 2: acc(polished) - acc(rough), TruthfulQA

- sonnet: gap=-0.010 [-0.025, +0.003], flip_rate(polished)=0.018, flip_rate(rough)=0.010, n=398, refusal+parse_fail: polished=2, rough=1
  - exploratory mmlu: gap=+0.075
  - exploratory mmlupro: gap=-0.005
- luna: gap=+0.030 [+0.003, +0.058], flip_rate(polished)=0.033, flip_rate(rough)=0.054, n=400, refusal+parse_fail: polished=0, rough=0
  - exploratory mmlu: gap=+0.020
  - exploratory mmlupro: gap=+0.050
- dsflash: gap=+0.018 [-0.007, +0.040], flip_rate(polished)=0.037, flip_rate(rough)=0.033, n=400, refusal+parse_fail: polished=0, rough=0
  - exploratory mmlu: gap=-0.022
  - exploratory mmlupro: gap=+0.000
- qwen: gap=+0.007 [-0.010, +0.028], flip_rate(polished)=0.030, flip_rate(rough)=0.033, n=400, refusal+parse_fail: polished=0, rough=0
  - exploratory mmlu: gap=-0.005
  - exploratory mmlupro: gap=+0.005

## Arm 3: coverage by cell (bio personas)

- sonnet: control=0.828, edu-high=0.805, edu-low=0.710, polished=0.905, rough=0.805
- luna: control=0.975, edu-high=0.925, edu-low=0.810, polished=0.915, rough=0.855
- dsflash: control=0.905, edu-high=0.835, edu-low=0.570, polished=0.797, rough=0.775
- qwen: control=0.823, edu-high=0.823, edu-low=0.705, polished=0.840, rough=0.835

## Exploratory: bio-register vs question-register gap

- sonnet: bio-register gap=+0.100, question-register gap=+0.000 (n=20)
- luna: bio-register gap=+0.060, question-register gap=+0.085 (n=20)
- dsflash: bio-register gap=+0.023, question-register gap=+0.060 (n=20)
- qwen: bio-register gap=+0.005, question-register gap=+0.003 (n=20)

## Arm 4: primary + interaction

- sonnet: jargon gap=+0.005 [-0.070, +0.070], interaction(rough - polished)=+0.015
  - exploratory fact-only gap: -0.028
  - exploratory warning-only gap: +0.071
  - exploratory action-only gap: -0.008
- luna: jargon gap=-0.032 [-0.070, +0.000], interaction(rough - polished)=+0.032
  - exploratory fact-only gap: -0.083
  - exploratory warning-only gap: -0.036
  - exploratory action-only gap: +0.000
- dsflash: jargon gap=-0.057 [-0.123, +0.013], interaction(rough - polished)=+0.080
  - exploratory fact-only gap: -0.083
  - exploratory warning-only gap: -0.214
  - exploratory action-only gap: +0.025
- qwen: jargon gap=+0.003 [-0.075, +0.073], interaction(rough - polished)=+0.010
  - exploratory fact-only gap: -0.056
  - exploratory warning-only gap: +0.000
  - exploratory action-only gap: +0.033

## Pairwise win rates (order-balanced; independent of checklist wording)

- arm3-register:
  - sonnet: net score=+0.300 [-0.025, +0.600] (A-wins 19 / ties 14 / B-wins 7)
  - luna: net score=-0.050 [-0.350, +0.225] (A-wins 10 / ties 18 / B-wins 12)
  - dsflash: net score=+0.175 [-0.175, +0.500] (A-wins 20 / ties 7 / B-wins 13)
  - qwen: net score=+0.200 [-0.125, +0.500] (A-wins 16 / ties 16 / B-wins 8)
- arm3-education:
  - sonnet: net score=+0.650 [+0.350, +0.900] (A-wins 32 / ties 2 / B-wins 6)
  - luna: net score=+0.800 [+0.575, +0.950] (A-wins 34 / ties 4 / B-wins 2)
  - dsflash: net score=+0.850 [+0.625, +1.000] (A-wins 36 / ties 2 / B-wins 2)
  - qwen: net score=+0.600 [+0.350, +0.800] (A-wins 29 / ties 6 / B-wins 5)
- arm4-jargon:
  - sonnet: net score=+0.200 [-0.075, +0.475] (A-wins 15 / ties 18 / B-wins 7)
  - luna: net score=+0.125 [-0.075, +0.325] (A-wins 8 / ties 29 / B-wins 3)
  - dsflash: net score=+0.075 [-0.300, +0.450] (A-wins 17 / ties 9 / B-wins 14)
  - qwen: net score=+0.225 [-0.050, +0.500] (A-wins 16 / ties 17 / B-wins 7)
- arm4-jargon-rough:
  - sonnet: net score=+0.300 [+0.000, +0.600] (A-wins 18 / ties 16 / B-wins 6)
  - luna: net score=+0.075 [-0.125, +0.275] (A-wins 8 / ties 27 / B-wins 5)
  - dsflash: net score=+0.200 [-0.150, +0.550] (A-wins 19 / ties 10 / B-wins 11)
  - qwen: net score=+0.300 [+0.050, +0.550] (A-wins 18 / ties 16 / B-wins 6)
- position-bias check: first-shown answer wins 46.2% of decisive judgments (0.5 = unbiased)

## Rubric means by cell (1-7, substance dims averaged)

- sonnet: {'control': 6.95, 'edu-high': 6.94, 'edu-low': 6.78, 'jargon-polished': 6.99, 'jargon-rough': 6.97, 'lay-rough': 6.95, 'polished': 6.78, 'rough': 6.72}
- luna: {'control': 7.0, 'edu-high': 6.96, 'edu-low': 6.9, 'jargon-polished': 7.0, 'jargon-rough': 6.99, 'lay-rough': 7.0, 'polished': 6.89, 'rough': 6.91}
- dsflash: {'control': 6.56, 'edu-high': 6.78, 'edu-low': 6.04, 'jargon-polished': 6.74, 'jargon-rough': 6.53, 'lay-rough': 6.59, 'polished': 6.59, 'rough': 6.46}
- qwen: {'control': 6.9, 'edu-high': 6.72, 'edu-low': 6.5, 'jargon-polished': 6.89, 'jargon-rough': 6.89, 'lay-rough': 6.53, 'polished': 6.46, 'rough': 6.5}

## Register descriptives (adaptation, not harm)

- sonnet: {'control': {'mean_words': 362.0, 'fk_grade': 12.8}, 'edu-high': {'mean_words': 409.6, 'fk_grade': 11.5}, 'edu-low': {'mean_words': 368.6, 'fk_grade': 7.4}, 'polished': {'mean_words': 378.2, 'fk_grade': 10.5}, 'rough': {'mean_words': 357.4, 'fk_grade': 10.3}, 'jargon-polished': {'mean_words': 373.5, 'fk_grade': 12.4}, 'lay-rough': {'mean_words': 346.7, 'fk_grade': 12.1}, 'jargon-rough': {'mean_words': 384.3, 'fk_grade': 12.4}}
- luna: {'control': {'mean_words': 323.0, 'fk_grade': 11.4}, 'edu-high': {'mean_words': 389.2, 'fk_grade': 11.5}, 'edu-low': {'mean_words': 278.6, 'fk_grade': 8.3}, 'polished': {'mean_words': 306.8, 'fk_grade': 11.1}, 'rough': {'mean_words': 282.3, 'fk_grade': 10.7}, 'jargon-polished': {'mean_words': 342.2, 'fk_grade': 11.4}, 'lay-rough': {'mean_words': 300.0, 'fk_grade': 10.4}, 'jargon-rough': {'mean_words': 309.6, 'fk_grade': 11.5}}
- dsflash: {'control': {'mean_words': 653.8, 'fk_grade': 7.8}, 'edu-high': {'mean_words': 582.0, 'fk_grade': 8.8}, 'edu-low': {'mean_words': 329.7, 'fk_grade': 4.3}, 'polished': {'mean_words': 494.4, 'fk_grade': 7.6}, 'rough': {'mean_words': 422.5, 'fk_grade': 6.6}, 'jargon-polished': {'mean_words': 635.1, 'fk_grade': 8.3}, 'lay-rough': {'mean_words': 602.6, 'fk_grade': 6.7}, 'jargon-rough': {'mean_words': 693.5, 'fk_grade': 7.5}}
- qwen: {'control': {'mean_words': 466.8, 'fk_grade': 9.6}, 'edu-high': {'mean_words': 646.0, 'fk_grade': 11.2}, 'edu-low': {'mean_words': 514.2, 'fk_grade': 6.4}, 'polished': {'mean_words': 521.0, 'fk_grade': 9.6}, 'rough': {'mean_words': 518.9, 'fk_grade': 8.3}, 'jargon-polished': {'mean_words': 490.2, 'fk_grade': 10.9}, 'lay-rough': {'mean_words': 538.5, 'fk_grade': 9.4}, 'jargon-rough': {'mean_words': 561.2, 'fk_grade': 10.1}}

## Parse failures / refusals by persona (signal, not noise)

```
{('sonnet', 'control', 'ok'): 780, ('sonnet', 'edu-high', 'ok'): 793, ('sonnet', 'polished', 'ok'): 789, ('sonnet', 'rough', 'ok'): 795, ('sonnet', 'edu-low', 'ok'): 797, ('sonnet', 'control', 'parse_fail'): 20, ('sonnet', 'edu-high', 'refusal'): 1, ('sonnet', 'edu-high', 'parse_fail'): 6, ('sonnet', 'edu-low', 'refusal'): 2, ('sonnet', 'edu-low', 'parse_fail'): 1, ('sonnet', 'polished', 'refusal'): 1, ('sonnet', 'polished', 'parse_fail'): 10, ('sonnet', 'rough', 'refusal'): 1, ('sonnet', 'rough', 'parse_fail'): 4, ('luna', 'control', 'ok'): 799, ('luna', 'control', 'parse_fail'): 1, ('luna', 'edu-high', 'ok'): 799, ('luna', 'edu-high', 'parse_fail'): 1, ('luna', 'edu-low', 'ok'): 799, ('luna', 'edu-low', 'parse_fail'): 1, ('luna', 'polished', 'ok'): 800, ('luna', 'rough', 'ok'): 798, ('luna', 'rough', 'parse_fail'): 2, ('dsflash', 'control', 'ok'): 698, ('dsflash', 'control', 'parse_fail'): 102, ('dsflash', 'edu-high', 'ok'): 764, ('dsflash', 'edu-high', 'parse_fail'): 36, ('dsflash', 'edu-low', 'ok'): 772, ('dsflash', 'edu-low', 'parse_fail'): 28, ('dsflash', 'polished', 'ok'): 740, ('dsflash', 'polished', 'parse_fail'): 60, ('dsflash', 'rough', 'ok'): 756, ('dsflash', 'rough', 'parse_fail'): 44, ('qwen', 'control', 'ok'): 800, ('qwen', 'edu-high', 'ok'): 799, ('qwen', 'edu-high', 'parse_fail'): 1, ('qwen', 'edu-low', 'ok'): 798, ('qwen', 'edu-low', 'parse_fail'): 1, ('qwen', 'edu-low', 'refusal'): 1, ('qwen', 'polished', 'ok'): 800, ('qwen', 'rough', 'ok'): 800}
```
