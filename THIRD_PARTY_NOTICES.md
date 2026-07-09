# Third-party notices

The Apache-2.0 license in this repository applies only to original Kelvin
Assistant source code and documentation unless a file states otherwise.
Third-party software, models, datasets, and user-provided documents remain
subject to their own terms.

## Direct Python dependencies

The following direct dependencies are installed from their upstream packages;
they are not vendored in this repository.

| Component | Resolved version | SPDX license |
| --- | ---: | --- |
| FastAPI | 0.138.1 | MIT |
| Pydantic Settings | 2.14.2 | MIT |
| psycopg | 3.3.4 | LGPL-3.0-only with exceptions |
| psycopg-binary | 3.3.4 | LGPL-3.0-only with exceptions |
| Uvicorn | 0.49.0 | BSD-3-Clause |
| HTTPX2 | 2.5.0 | BSD-3-Clause |
| mypy (development) | 2.1.0 | MIT |
| pytest (development) | 9.1.1 | MIT |
| pytest-cov (development) | 7.1.0 | MIT |
| Ruff (development) | 0.15.20 | MIT |

Exact resolved versions, including transitive dependencies, are recorded in
`uv.lock`. Before distributing an offline dependency bundle, generate and
review a complete software bill of materials and include all required upstream
license texts and notices.

## Models and planned integrations

Model weights are not part of the Kelvin Assistant source distribution.
Gemma models are governed by the applicable Google Gemma terms:

https://ai.google.dev/gemma/terms

Open WebUI is governed by its own current and historical license terms:

https://github.com/open-webui/open-webui/blob/main/LICENSE

Every new runtime component, model, voice, dataset, or connector must be
reviewed before it is added to an offline distribution.
