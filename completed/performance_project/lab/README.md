# Lab

Shared measurement tools and templates. Only
[experiment.py](api/starter_code/app/experiment.py) knows which engine is
behind the API; everything else here is engine-agnostic.

| Item                                           | Purpose                                                                                      |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [measurement_ladder.md](measurement_ladder.md) | Look → Ask (plan) → Time → Stress                                                            |
| [fairness.md](fairness.md)                     | Rules for honest comparisons                                                                 |
| [api/](api/README.md)                          | The measurement API: starter code, FastAPI basics, route contract, experiment.py, driver     |
| [load_scenarios.md](load_scenarios.md)         | Load scenarios and which engines run which                                                   |
| [loadtest/](loadtest/README.md)                | `loadtest.py`: many requests at once, with latency percentiles                               |
| [findings_template.md](findings_template.md)   | Course-wide FINDINGS template                                                                |
