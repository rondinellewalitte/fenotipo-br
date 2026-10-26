"""Render the Exp 03 report from result files. Every number comes from a file under results/
(CLAUDE.md, rule 2); derived values are computed here, not typed. Written and committed before
the full run, against the pilot files, so the report's structure does not follow its results.

    uv run python reports/build_exp03.py                       # full run -> reports/exp03.md
    uv run python reports/build_exp03.py --pilot --out X.md    # test render from the pilot
"""
# ruff: noqa: E501  (the Markdown template below is prose; long lines are intended)

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R3 = ROOT / "results" / "exp03"
OUT = ROOT / "reports" / "exp03.md"
MODELS = {"qwen3-4b": "Qwen3-4B Instruct 2507", "gemma3-4b": "Gemma 3 4B"}
ARMS = {
    "A": "A, direto em PT",
    "B": "B, traduz antes",
    "C": "C, índice bilíngue",
}
REG = {"technical": "só técnico", "lay": "só leigo", "both": "ambos"}
SIM = {"<50": "< 50", "50-80": "50–80", ">=80": "≥ 80"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dec(x: float | None, d: int = 3) -> str:
    if x is None:
        return "—"
    if abs(x) < 0.5 * 10**-d:  # no "−0,000"
        x = 0.0
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def sgn(x: float | None, d: int = 3) -> str:
    return "—" if x is None else ("+" if x >= 0 else "") + dec(x, d)


def pct(x: float | None, d: int = 1) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%".replace(".", ",")


def num(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def ci(pair) -> str:
    return "—" if not pair else f"{dec(pair[0])} a {dec(pair[1])}"


def usd(x: float) -> str:
    return f"US$ {x:.2f}".replace(".", ",")


def src(path: Path) -> str:
    return f"`{path.relative_to(ROOT).as_posix()}`"


def yes(b: bool) -> str:
    return "sim" if b else "não"


def render(base: Path, set_name: str) -> str:
    c, m = load(base / "config.json"), load(base / "metrics.json")
    vcfg = load(R3 / f"vignettes_config_{set_name}.json")
    kappa = load(R3 / "pilot" / "register_kappa.json")
    hyp_path = base / "hypotheses.json"
    hyp = load(hyp_path) if hyp_path.exists() else None
    arms, comp = m["arms"], m["comparisons"]
    base_arm = arms["none/baseline"]
    vs = vcfg["summary"]
    oll = c["ollama"]
    models = [k for k in MODELS if f"{k}/A" in arms]

    main = [
        "| Modelo | Braço | Precisão | Recall | F1 micro | F1 macro | FP em negação | s/caso (mediana) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in models:
        for a, label in ARMS.items():
            s = arms[f"{k}/{a}"]
            main.append(
                f"| {MODELS[k]} | {label} | {dec(s['micro']['precision'])} | {dec(s['micro']['recall'])} "
                f"| **{dec(s['micro']['f1'])}** | {dec(s['macro']['f1'])} | {pct(s['negation_fp']['rate'])} "
                f"| {dec(s['seconds_per_case']['median'], 1)} |"
            )
    main.append(
        f"| — | Baseline sem LLM (τ = {dec(m['baseline_tau'], 2)}) | {dec(base_arm['micro']['precision'])} "
        f"| {dec(base_arm['micro']['recall'])} | **{dec(base_arm['micro']['f1'])}** | {dec(base_arm['macro']['f1'])} "
        f"| {pct(base_arm['negation_fp']['rate'])} | {dec(base_arm['seconds_per_case']['median'], 1)} |"
    )

    cmp_rows = [
        "| Modelo | Comparação | Diferença de F1 | IC95 | IC 97,5% |",
        "|---|---|---|---|---|",
    ]
    for k in models:
        for name in ("A-B", "C-A", "A-baseline", "B-baseline", "C-baseline"):
            d = comp[k][name]
            cmp_rows.append(
                f"| {MODELS[k]} | {name.replace('-', ' − ')} | {sgn(d['diff'])} | {ci(d['ci95'])} | {ci(d['ci97_5'])} |"
            )

    hyp_rows: list[str] = []
    if hyp:
        hyp_rows = [
            "| Hipótese | " + " | ".join(MODELS[k] for k in models) + " | Nos dois |",
            "|---|" + "---|" * (len(models) + 1),
        ]
        for name, h in hyp["hypotheses"].items():
            per = " | ".join(yes(h["per_model"][k]["confirmed"]) for k in models)
            hyp_rows.append(f"| `{name}` | {per} | **{yes(h['confirmed_both_models'])}** |")
        hyp_rows += [
            "",
            "| Expectativa (descritiva) | " + " | ".join(MODELS[k] for k in models) + " |",
            "|---|" + "---|" * len(models),
        ]
        for name, e in hyp["expectations"].items():
            hyp_rows.append(f"| `{name}` | " + " | ".join(yes(e[k]) for k in models) + " |")

    reg = m["register"]["d2"]
    reg_rows = [
        "| Modelo | Braço | "
        + " | ".join(f"Recall {v}" for v in REG.values())
        + " | Técnico − leigo (IC95) |",
        "|---|---|" + "---|" * (len(REG) + 1),
    ]
    for key in [f"{k}/{a}" for k in models for a in ARMS] + ["none/baseline"]:
        r = reg[key]
        model, arm = key.split("/")
        label = "Baseline" if arm == "baseline" else ARMS[arm]
        cells = " | ".join(
            f"{dec(r['recall'][g]['recall'])} (n = {r['recall'][g]['n']})" for g in REG
        )
        tml = r["technical_minus_lay"]
        reg_rows.append(
            f"| {MODELS.get(model, '—')} | {label} | {cells} | {sgn(tml['diff'])} ({ci(tml['ci95'])}) |"
        )
    between = ["| Modelo | Grupo | A − B (IC95) | C − A (IC95) |", "|---|---|---|---|"]
    for k in models:
        for g, label in REG.items():
            b = reg[f"{k}/between_arms"][g]
            between.append(
                f"| {MODELS[k]} | {label} | {sgn(b['A-B']['diff'])} ({ci(b['A-B']['ci95'])}) "
                f"| {sgn(b['C-A']['diff'])} ({ci(b['C-A']['ci95'])}) |"
            )

    strata = [
        "| Modelo | Estrato | n | Recall A | Recall B | Recall C | A − B |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in models:
        for col, keys in (
            ("sim_bin", SIM),
            (
                "phrase_is_pt_label",
                {"True": "frase = rótulo PT oficial", "False": "frase ≠ rótulo PT oficial"},
            ),
            ("has_pt_label", {"True": "termo com rótulo PT", "False": "termo sem rótulo PT"}),
        ):
            for key, label in keys.items():
                ra = arms[f"{k}/A"]["recall_by_stratum"][col].get(key)
                if ra is None:
                    continue
                rb = arms[f"{k}/B"]["recall_by_stratum"][col][key]
                rc = arms[f"{k}/C"]["recall_by_stratum"][col][key]
                name = f"similaridade com o rótulo inglês {label}" if col == "sim_bin" else label
                strata.append(
                    f"| {MODELS[k]} | {name} | {ra['n']} | {dec(ra['recall'])} | {dec(rb['recall'])} "
                    f"| {dec(rc['recall'])} | {sgn(ra['recall'] - rb['recall'])} |"
                )

    d1 = [
        "| Modelo | Braço | Recall: termo do HPO no texto (D1 técnico/ambos) | Recall: sem termo do HPO (D1 leigo) |",
        "|---|---|---|---|",
    ]
    for key in [f"{k}/{a}" for k in models for a in ARMS] + ["none/baseline"]:
        r = arms[key]["recall_by_stratum"]["register_d1"]
        model, arm = key.split("/")
        label = "Baseline" if arm == "baseline" else ARMS[arm]
        with_term = [r[g] for g in ("technical", "both") if g in r]
        n_with = sum(x["n"] for x in with_term)
        rec_with = sum(x["recall"] * x["n"] for x in with_term) / n_with if n_with else None
        lay = r.get("lay")
        d1.append(
            f"| {MODELS.get(model, '—')} | {label} | {dec(rec_with)} (n = {n_with}) "
            f"| {dec(lay['recall'] if lay else None)} (n = {lay['n'] if lay else 0}) |"
        )

    retr = [
        "| Modelo | Braço | Teto de recuperação | Perda na escolha | Achados/caso | NONE | Near-miss (% dos FP) | Mão↔pé (% dos FP) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in models:
        for a, label in ARMS.items():
            s = arms[f"{k}/{a}"]
            retr.append(
                f"| {MODELS[k]} | {label} | {dec(s['retrieval_ceiling_recall'])} | {dec(s['selection_loss'])} "
                f"| {dec(s['findings_per_case'], 1)} | {pct(s['none_rate'])} | {pct(s['near_miss']['share_of_fp'])} "
                f"| {pct(s['hand_foot_swap']['share_of_fp'])} |"
            )
    oracle = m["oracle_spans_bge_m3_en_index"]
    vram = max((v.get("peak_vram_mib") or 0) for v in c["stages"].values() if isinstance(v, dict))
    on_gpu = all(
        p["size"] == p["size_vram"]
        for v in c["stages"].values()
        if isinstance(v, dict)
        for p in v.get("ollama_ps") or []
    )
    digests = ", ".join(f"`{v['tag']}` ({v['digest'][:12]})" for v in oll["models"].values())
    title_set = "run completo" if set_name == "full" else "piloto, teste de renderização"

    return f"""# Exp 03: extração de fenótipos de vinhetas em PT-BR com LLMs locais ({title_set})

R. Walitte (ORCID 0009-0004-1776-2754). Gerado por `reports/build_exp03.py` a partir de {src(base)}. Código: `{c["git"]["commit"][:7]}`. Pré-registro: {src(R3 / "PREREG.md")}.

> **Apoio à pesquisa, não é ferramenta diagnóstica.** Nada aqui deve orientar conduta clínica (ANVISA RDC 657/2022). As vinhetas são sintéticas, derivadas de casos publicados; não há dado de paciente.

## Pergunta

Em texto clínico em português do Brasil, um LLM pequeno que roda localmente (4B parâmetros, GPU de notebook com 6 GB) extrai os fenótipos e os mapeia para o HPO:

- **direto em português** (braço A) tão bem quanto **traduzindo antes para o inglês** (B)?
- melhor quando o índice de busca também tem os **rótulos PT oficiais** (C)?
- melhor que uma busca só por embeddings, **sem LLM** (baseline)?

## Dados e métodos

- **Casos:** {num(c["n_cases"])} casos do Phenopacket Store {c["phenopacket_store_release"]}, um por gene, com 3 a 15 termos observados; HPO {c["hpo_release"]}.
  - Gabarito: {num(m["n_gold_terms"])} termos. Negações mostradas na vinheta: {num(m["n_negated_terms"])}.
  - Termos fora do gabarito por falta de trecho na vinheta: {num(len(vs["dropped_items_final"]))}. Casos trocados por reserva: {num(vs["n_replacements"])}.
- **Vinhetas:** escritas por `{vcfg["generator"]["model"]}` (prompt `{vcfg["generator"]["prompt"]}`), que nunca é extrator neste experimento.
  - Custo deste conjunto: {usd(vs["cost_usd"])} em {num(vs["api_calls"])} chamadas. Gasto acumulado do Exp 03: {usd(vcfg["spent_usd_total"])} ({src(R3 / f"vignettes_config_{set_name}.json")}).
- **Extratores:** {digests}, via Ollama {oll["ollama_version"]}, temperatura 0, seed {c["seed"]}, contexto de {num(c["llm_options"]["num_ctx"])} tokens. Prompts congelados após o piloto ({src(R3 / "frozen.json")}).
- **Busca:** `{c["retrieval"]["model"]}`, 10 candidatos por achado entre os termos sob HP:0000118.
  - Índice EN: {num(c["retrieval"]["index_en"]["n_texts"])} textos. Índice bilíngue: {num(c["retrieval"]["index_bi"]["n_texts"])} textos, incluindo {num(c["retrieval"]["index_bi"]["n_pt_labels"])} rótulos PT oficiais.
  - O seletor vê o achado e, para cada candidato, ID e rótulo inglês, igual nos três braços.
- **Desfecho primário:** F1 micro por termo, com ID exato, A contra B, pareado por caso.
  - Bootstrap de casos: {num(m["bootstrap"]["n_boot"])} reamostragens, seed {m["bootstrap"]["seed"]}.
  - O H1 usa o IC 97,5% (dois modelos) com margem de não inferioridade de −0,03.
- **Registro clínico de cada termo (D2):** "só técnico", "só leigo" ou "ambos", rotulado às cegas antes da extração.
  - Conferência humana de 40 itens: kappa de Cohen {dec(kappa["cohen_kappa"], 2)} (IC95 {ci(kappa["cohen_kappa_ci95"])}). O estrato é {"confirmatório" if kappa["d2_strata_status"] == "confirmatory" else "exploratório"} ({src(R3 / "pilot" / "register_kappa.json")}).

## Resultados

### Resultado principal

{chr(10).join(main)}

Fonte: {src(base / "metrics.json")}.

### Comparações pareadas

{chr(10).join(cmp_rows)}

Fonte: {src(base / "metrics.json")} → `comparisons`.

### Hipóteses pré-registradas

{chr(10).join(hyp_rows) if hyp_rows else "Não avaliadas: as hipóteses só são julgadas no run completo."}

{f"Fonte: {src(hyp_path)}. Critérios em {src(R3 / 'PREREG.md')}." if hyp else ""}

### Traduzir antes ajuda onde? Estratos de retrotradução

A ameaça pré-registrada: o gerador escreveu em português a partir do rótulo inglês, e traduzir de volta pode recuperar esse rótulo de forma artificial. Se fosse isso, a vantagem do B ficaria nas frases parecidas com o rótulo inglês (similaridade ≥ 80).

{chr(10).join(strata)}

Fonte: {src(base / "metrics.json")} → `recall_by_stratum`.

### Linguagem leiga e técnica (registro clínico, D2)

{chr(10).join(reg_rows)}

{chr(10).join(between)}

**Termo do HPO presente no texto (D1, regra literal, descritivo):** a vinheta traz o rótulo PT oficial ou um cognato do rótulo inglês? É a pergunta sobre a tradução incompleta do HPO, não sobre linguagem leiga.

{chr(10).join(d1)}

Fonte: {src(base / "metrics.json")} → `register.d2` e `recall_by_stratum.register_d1`. Ressalva: o rotulador tende a marcar "ambos" em frases de fronteira, o que muda o nível absoluto de cada grupo, mas não a comparação entre braços (PREREG, Desvios).

### Onde se perde: busca, escolha e erros

{chr(10).join(retr)}

- **Oráculo de frases:** com a frase exata do gerador, sem LLM, o bge-m3 põe o termo certo em 1º lugar em {pct(oracle["top1"])} e entre os 10 primeiros em {pct(oracle["top10"])} dos {num(oracle["n_gold_phrases"])} termos.
- **Falsos positivos por categoria** e exemplos de cada erro: {src(base / "errors.csv")}.

### Custo computacional

- O pico de memória da GPU foi de {num(vram)} MiB, com a GPU inteira contada. Os modelos ficaram {"100% na GPU" if on_gpu else "parcialmente fora da GPU"}.
- O run levou {dec(c["wall_seconds"] / 3600, 1)} h ao todo ({src(base / "config.json")}).

## Limitações

- **Texto sintético.** As vinhetas foram escritas por um LLM a partir de listas curadas. Não têm erros de digitação nem abreviações variadas, e a mesma queixa aparece em linguagem leiga e técnica de forma regular. Os números valem para esse cenário.
- **Contaminação.** Os casos vêm de artigos publicados. O gerador pode ter visto o artigo; os extratores podem ter visto o artigo ou o Phenopacket Store.
- **Retrotradução.** Ver a tabela de estratos acima.
- **Rótulos de registro.** Foram feitos por um agente e conferidos pelo autor, que não é clínico, com viés do rotulador para "ambos". A revisão por um geneticista está prevista no contato com a Rede RARAS.
- **Quantização.** Os resultados valem para as versões Q4_K_M dos modelos.

## Próximos passos

1. **Exp 04:** o mesmo protocolo com o Claude via API como extrator (custo separado), sabendo que o texto foi escrito por um modelo da mesma família.
2. **Revisão por geneticista** das vinhetas e dos rótulos de registro.
3. **Notas clínicas reais em português** (SemClinBr, após o acordo de uso).
4. **Efeito dos erros de extração no ranqueamento de genes e doenças.**
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="render from results/exp03/pilot")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    base, set_name = (R3 / "pilot", "pilot") if args.pilot else (R3, "full")
    if args.pilot and args.out == OUT:
        raise SystemExit("--pilot renders a test file: pass --out outside reports/")
    md = render(base, set_name)
    args.out.write_text(md, encoding="utf-8")
    print(f"-> {args.out} ({len(md.split())} words)")


if __name__ == "__main__":
    main()
