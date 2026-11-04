<p align="center">
  <img src="docs/assets/banner.svg" alt="rulelab" width="560">
</p>

<p align="center">
  <a href="https://github.com/diegoperezg7/rulelab/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/diegoperezg7/rulelab/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Licencia: MIT" src="https://img.shields.io/badge/license-MIT-5d51d1"></a>
  <a href="https://github.com/diegoperezg7/rulelab/releases"><img alt="Release" src="https://img.shields.io/github/v/release/diegoperezg7/rulelab?color=5d51d1"></a>
  <a href="https://github.com/diegoperezg7/rulelab/stargazers"><img alt="Estrellas" src="https://img.shields.io/github/stars/diegoperezg7/rulelab?style=flat&color=5d51d1"></a>
</p>

<p align="center"><b>Descubre qué líneas de tu AGENTS.md se ganan sus tokens.</b><br>
Quita una regla cada vez y mide acierto y coste en tareas reales.</p>

<p align="center"><a href="README.md">Read in English</a> · <a href="https://diegoperezg7.github.io/rulelab/">Informe de ejemplo</a></p>

<p align="center"><img src="docs/assets/demo.gif" alt="rulelab split y rulelab demo en un terminal" width="820"></p>

<p align="center"><a href="https://diegoperezg7.github.io/rulelab/"><img src="docs/assets/report-light.png" alt="Informe HTML de rulelab" width="820"></a></p>

## Por qué

Cada línea de `AGENTS.md` o `CLAUDE.md` se envía al modelo en cada llamada. ¿Merece la pena?

La mejor evidencia hasta ahora dice que a menudo no. Gloaguen et al. (ETH Zúrich y LogicStar.ai,
[arXiv 2602.11988](https://arxiv.org/abs/2602.11988)) pusieron a Claude Code, Codex y Qwen Code
sobre SWE-bench Lite y CTXbench (138 tareas de 12 repositorios) y vieron que los ficheros de
contexto **no mejoran en general el acierto** y suben el coste de inferencia **más de un 20 % de
media**:

| Fichero de contexto | Acierto | Coste de inferencia |
| --- | --- | --- |
| Escrito por un LLM | −0,5 % (SWE-bench Lite), −2 % (CTXbench) | +20 %, +23 % |
| Escrito por desarrolladores | +2,4 % (no significativo) | hasta +19 % |

También vieron que las descripciones generales del repositorio no ayudan. Eso es la media de
muchos repos. A ti te importan tu fichero, tu repo y tu modelo, y el paper mide ficheros
enteros, no las reglas sueltas que de verdad borrarías.

rulelab hace ese experimento sobre **tu** repo, **regla a regla**.

| | Qué mide | Tareas |
| --- | --- | --- |
| [fernforge/ruleprof](https://github.com/fernforge/ruleprof) (0★) | Quita reglas de una en una y mira si el agente **obedece** cada regla | De juguete |
| [sx4im/skillcheck](https://github.com/sx4im/skillcheck) (29★) | A/B a ciegas del **fichero entero** frente a no tenerlo | Tus prompts |
| **rulelab** | Quita reglas de una en una y mide **acierto y coste** por regla | Arreglos reales del historial de tu repo, puntuados con sus propios tests |

Estrellas comprobadas con la API de GitHub el 3 nov 2026.

## Inicio rápido

Mira una ejecución real grabada (sin API key, sin Docker, en menos de un minuto):

```bash
uvx --from git+https://github.com/diegoperezg7/rulelab@v0.1.1 rulelab demo --open
```

o desde un clon:

```bash
git clone https://github.com/diegoperezg7/rulelab && cd rulelab && uv run rulelab demo --open
```

`uvx rulelab` llegará pronto a PyPI.

Después, sobre tu propio fichero y repo (necesita Docker, y Ollama o una API key):

```bash
rulelab split AGENTS.md                                   # cómo se parte el fichero, gratis
rulelab run AGENTS.md --repo . --dry-run                  # plan y coste estimado, gratis
rulelab run AGENTS.md --repo . --model ollama/qwen3:4b    # modelo local, 0 USD
rulelab run AGENTS.md --repo . --model mistral/ministral-14b-latest --price 0.2,0.2 -j 3
```

## Salida de ejemplo

```text
$ rulelab demo
Recorded run · real results from rulelab run on 2026-11-03 · rulelab 0.1.0 · Darwin arm64 (Apple M4, 16 GB RAM)
AGENTS.md · model mistral/ministral-14b-latest · 4 tasks × 2 repeats × 8 configs · 64 runs · 0.7376 USD
full file 2/8 · no file 1/8 · file effect +12 pp [−21, +39]
file tokens per run, estimated if resent on every call: ≈4,305 · measured difference vs no file: +776 [−15,405, +17,616]
 rule                    ≈tok   effect (pp, 95% CI)   verdict        USD/month
 R1 Repository overview    88        +12 [−21, +41]   inconclusive        0.23
 R2 Running tests          47          0 [−26, +25]   inconclusive        0.12
 R3 How to fix a bug       56        +12 [−20, +40]   inconclusive        0.15
 R4 Lexer and keywords     68          0 [−26, +27]   inconclusive        0.18
 R5 Code style             34          0 [−26, +27]   inconclusive        0.09
 R6 Communication          30          0 [−26, +26]   inconclusive        0.08
Small sample: most rules are inconclusive. [...]
```

**Lo que dice esta ejecución grabada, sin adornos.** La demo es un `rulelab run` real de un
[AGENTS.md](examples/demo/AGENTS.md) de 6 reglas (incluye una descripción general del repositorio,
como en el paper) sobre las 4 tareas más recientes de la demo de commitarena: arreglos de bugs de
[sqlparse](https://github.com/andialbrecht/sqlparse), puntuados con los tests de sqlparse
([tasks.json](examples/demo/tasks.json)). Modelo `mistral/ministral-14b-latest`, 15 pasos de agente,
2 repeticiones, commitarena 0.1.1: 64 ejecuciones, 27 minutos, 0,74 USD. El modelo se eligió con
un sondeo de 4 ejecuciones porque resolvía algunas tareas pero no todas (1 de 4), así que la línea
base no es ni 0 % ni 100 % y un efecto podría aparecer.

Pasaron 13 de 64 ejecuciones. El fichero completo pasó 2/8 y sin fichero 1/8 (+12 pp, intervalo de
−21 a +39). Quitar la descripción del repositorio o la regla de cómo arreglar un bug bajó el
acierto de 2/8 a 1/8, pero con 4 tareas y 2 repeticiones eso es una sola ejecución de diferencia:
**todas las reglas salen no concluyentes**, y el informe lo dice en vez de forzar un veredicto. Lo
que sí deja claro es el precio: el fichero son ≈328 tokens reenviados en cada una de las ~13
llamadas al modelo; reenviado en cada una sumaría ≈4.305 tokens de entrada por ejecución estimados. La diferencia medida de verdad en esta ejecución (fichero completo frente a sin fichero) fue de +776 tokens de entrada por ejecución, con un intervalo amplio, porque las trayectorias del agente varían mucho más que eso. Para tener un veredicto, usa más
tareas y repeticiones sobre tu propio repo.

Una ejecución anterior más grande (144 ejecuciones con codestral sobre una versión previa de
commitarena) resolvió 1 de 144 tareas y no se publica como resultado; sí demostró que la ejecución
sobrevive a errores del motor, cortes por presupuesto e interrupciones (`--resume`).

El informe completo, con el fichero anotado, está publicado en
**[diegoperezg7.github.io/rulelab](https://diegoperezg7.github.io/rulelab/)** (EN/ES, claro/oscuro).
Capturas: [claro](docs/assets/report-light.png) · [oscuro](docs/assets/report-dark.png) ·
[móvil](docs/assets/report-mobile.png).

## Cómo funciona

```mermaid
flowchart LR
  F[AGENTS.md / CLAUDE.md] --> S[partir en reglas<br/>por sección o viñeta]
  S --> C["configuraciones:<br/>sin fichero · completo · completo sin R1 … Rn"]
  R[tu repo] --> M[commitarena mine:<br/>commits reales que arreglan un bug con test]
  C --> X{{cada config × cada tarea × 3 repeticiones}}
  M --> X
  X --> D[sandbox Docker sin red:<br/>el agente edita código, el modelo se llama desde el host]
  D --> T[los tests del repo deciden si pasa]
  T --> B[intervalo bootstrap por regla:<br/>ayuda · sin efecto · empeora · no concluyente]
  B --> H[informe HTML + results.json]
```

1. **Partir.** `--granularity section` (por defecto) convierte cada encabezado en una regla;
   `bullet`, cada viñeta de primer nivel o párrafo. Un `# Título` suelto se mantiene en todas las
   configuraciones. Compruébalo con `rulelab split`.
2. **Configuraciones.** Sin fichero, fichero completo y fichero completo sin cada regla. Con
   *n* reglas son *n* + 2 configuraciones.
3. **Tareas.** Arreglos de bugs reales de tu historial de git, minados por
   [commitarena](https://github.com/diegoperezg7/commitarena): commits que añaden un test que falla
   antes del arreglo. El agente recibe los tests que fallan, nunca el mensaje del commit.
4. **Ejecuciones.** Cada configuración corre cada tarea `--repeats` veces (3 por defecto) en el
   mismo sandbox Docker sin red (2 CPU, 2 GB). El fichero se escribe en la raíz del repo y se añade
   al prompt de sistema (`--inject both|repo|prompt`). Antes se quita el AGENTS.md/CLAUDE.md propio
   del repo, así que «sin fichero» es sin fichero de verdad.
5. **Veredicto.** Efecto de una regla = acierto con el fichero completo − acierto sin ella. El
   intervalo del 95 % sale de un bootstrap en dos niveles (se remuestrean tareas y el acierto por
   tarea se saca de una posterior Beta(s+½, f+½), para que 3/3 frente a 3/3 no parezca una
   certeza). **Ayuda** si todo el intervalo está por encima de 0, **empeora** si está por debajo,
   **sin efecto** si cabe dentro de ±10 pp (`--margin`) y **no concluyente** en otro caso.
6. **Coste.** Tokens por regla (≈ caracteres / 4), la diferencia medida de tokens de entrada por
   ejecución y una proyección mensual: tokens de la regla × llamadas al modelo por ejecución ×
   sesiones al mes × precio de entrada.

### Leer el resultado con honestidad

Con 6 tareas y 3 repeticiones solo se distinguen del ruido los efectos grandes, así que **la
mayoría de reglas saldrán no concluyentes**. El informe lo dice tal cual en vez de forzar un
veredicto. «No concluyente» no es «inútil»: significa que este experimento no puede decidirlo.
Añade tareas (`--max-tasks`) o repeticiones antes de borrar una regla por eso.

## Configuración

| Opción | Por defecto | Qué hace |
| --- | --- | --- |
| `--repo` | | Repo git (ruta o URL) del que minar tareas |
| `--tasks-file` | | Reusar un `tasks.json` de `commitarena mine` |
| `--only` | todas | Ids de tarea separados por comas |
| `--max-tasks` | 6 | Tareas a minar con `--repo` |
| `--model`, `-m` | `ollama/qwen3:4b` | `ollama/…`, `mistral/…`, `openrouter/…`, `openai/…` |
| `--granularity`, `-g` | `section` | `section` o `bullet` |
| `--repeats`, `-n` | 3 | Ejecuciones por tarea y configuración |
| `--max-cost` | 1.0 | Tope de gasto en USD, comprobado antes de cada ejecución. Los modelos locales cuentan 0 |
| `--inject` | `both` | El fichero en la raíz del repo, en el prompt de sistema o en ambos |
| `--max-steps` | 30 | Llamadas al modelo por ejecución |
| `--concurrency`, `-j` | 1 | Ejecuciones a la vez, cada una en su sandbox |
| `--price` | | `IN,OUT` en USD por 1M de tokens para modelos sin precio conocido |
| `--price-source` | | De dónde sale ese precio; aparece en el informe |
| `--sessions-per-month` | 1000 | Para la proyección de coste mensual |
| `--out`, `-o` | `rulelab-results` | Escribe `results.json` (tras cada ejecución) y `report.html` |
| `--resume` | | Continuar una ejecución interrumpida o parada por presupuesto |
| `--dry-run` | | Solo imprime el plan y la estimación |

Antes de ejecutar nada, rulelab imprime el número de ejecuciones del agente y el coste estimado.
Si la estimación supera `--max-cost`, se para y te dice qué cantidad pasar. No se gasta nada
hasta que lo permites.

**Modelos locales pequeños.** Ollama sirve los modelos con un contexto de 4.096 tokens por
defecto. Una ejecución del agente necesita mucho más, y en nuestra prueba `qwen3:4b` gastó esa
ventana pensando y nunca llegó a ejecutar un comando. Arranca Ollama con una ventana mayor (por
ejemplo `OLLAMA_CONTEXT_LENGTH=32768 ollama serve`) antes de usar un modelo local.

**Las claves** se leen solo de variables de entorno: `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`,
`OPENAI_API_KEY` (ver [.env.example](.env.example)). Ollama no necesita ninguna (`OLLAMA_HOST`
para apuntar a otro sitio). rulelab no envía telemetría.

`rulelab report results.json` regenera el informe con otro `--margin`, `--price-in` o
`--sessions-per-month` sin volver a ejecutar nada.

## Hoja de ruta

Fuera de la v0.1:

- Tareas sintéticas para repos sin suficiente historial de arreglos.
- Comprobación de obediencia (¿siguió el agente la regla?) como segunda señal junto al acierto.
- `.cursor/rules` y skills.
- Interacciones entre reglas (quitar parejas o grupos).
- Reescritura automática de reglas que cuestan más de lo que ayudan.
- Publicación en PyPI (cuando commitarena esté en PyPI; PyPI no acepta la dependencia actual desde GitHub).

## Parte de una serie

Herramientas open source para medir agentes y LLMs con tus propios datos:

- [memarena](https://github.com/diegoperezg7/memarena): Compara capas de memoria con tus propias conversaciones.
- [parsearena](https://github.com/diegoperezg7/parsearena): Compara parsers de PDF lado a lado y su efecto en la recuperación.
- [commitarena](https://github.com/diegoperezg7/commitarena): Reproduce fixes reales de tu historial de git con cualquier modelo.
- [toolbloat](https://github.com/diegoperezg7/toolbloat): Mide el coste en tokens de tu pila MCP y los errores al elegir tool.
- [doesitfire](https://github.com/diegoperezg7/doesitfire): Comprueba si tu SKILL.md se activa en Claude Code, Codex y OpenCode.

## Licencia

[MIT](LICENSE) © 2026 Diego Pérez. Las tareas de la demo contienen código y tests de
[andialbrecht/sqlparse](https://github.com/andialbrecht/sqlparse) (BSD-3-Clause, ver
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)), tomadas de la demo de commitarena; el AGENTS.md
de la demo en [`examples/demo`](examples/demo) se escribió para este proyecto.
