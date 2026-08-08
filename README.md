# fde-kernel

Kernel de entrega para forward-deployed engineering. Trata **revisão empírica** e
**revisão adversarial** como invariantes de gate, não como fases de metodologia.

Portável entre ferramentas agênticas: Claude Code, Codex, Cursor, Copilot, Kiro,
Gemini CLI, Windsurf, Aider. A camada de instrução usa padrões governados pela
Agentic AI Foundation (AGENTS.md, Agent Skills); a camada de enforcement mora no
repositório, não na IDE.

> `fde-kernel` é nome de trabalho. Trocar exige editar um campo em
> `.claude-plugin/plugin.json` e o prefixo das skills.

---

## O problema

O modelo FDE tem análise organizacional densa e **nenhum critério técnico de
aceite**. O playbook canônico traz sete lições de org-design — contratar
engenheiro-diplomata, embedar no cliente, entregar no dia um, tratar discovery
como engenharia, construir ontologia do cliente, rotear feedback pelo FDE,
recusar o papel de integrador — e zero definição de "pronto para produção".

Sem isso, FDE é venda com PoC rápido, e a crítica de que gera lock-in e
funcionalidade limitada procede.

Este kernel não afirma pioneirismo em revisão empírica nem em adversarial. Ambas
têm linhagem: eval-driven development de um lado; debate como supervisão, red
teaming e arquiteturas challenger/solver do outro. A afirmação é mais estreita e
defensável: **nenhum framework de FDE hoje trata as duas como gate de entrega, e
sem isso PoC não vira produção.**

---

## Como o rigor sobrevive à velocidade

"Entregar no dia um" nunca foi "produção no dia um" — era rodar em dado real em
vez de slide. A regra do kernel:

> **O rigor é constante. A superfície varia.**

No dia um você entrega algo mínimo mas real: roda em dado de produção, tem eval,
tem observabilidade, poderia ficar de pé indefinidamente. Escopo encolhe; padrão
nunca. É o que qualifica a demo em vez de sacrificá-la — não "olha o que dá para
fazer", e sim "isto já funciona no seu ambiente, e aqui está a medida".

Consequência assumida: existem engajamentos que o kernel **recusa**. Cliente sem
acesso a dado real, sem ambiente onde promover, sem ninguém para receber a
operação. `fde doctor` e o gate deixam isso visível antes do contrato.

---

## Os sete invariantes

Definidos em [`spec/invariants.toml`](spec/invariants.toml). **Não têm chave de
configuração.** Quem precisa operar sem um deles faz fork — o fork é visível; a
exceção silenciosa não seria.

| id | invariante |
|---|---|
| I1 | Mudança de comportamento não entra sem entrada correspondente na suíte de eval |
| I2 | A revisão adversarial recebe artefato + spec, nunca o raciocínio de quem construiu |
| I3 | Sucesso do adversarial é achado, não aprovação — e ele não pode corrigir |
| I4 | Critério de promoção declarado, versionado e datado **antes** da construção |
| I5 | O que não é observável não é verificável: piso de observabilidade |
| I6 | O gate roda no ambiente do cliente, sem o FDE presente |
| I7 | Handoff entre papéis é por artefato em disco, nunca por conversa |

---

## Os dois vetores

Atributo de qualidade e domínio técnico são coisas diferentes e não compartilham
orçamento. Misturá-los faria "peso baixo em QA" significar menos teste, o que
colide com I1.

**Vetor A — atributos de qualidade.** Orçamento **fechado** de 100 pontos. É o
que o cliente aloca e assina; vira registro datado do que ele disse que
importava. Se tudo pudesse ser alto, ninguém escolheu nada.

Governa: ordem de ataque adversarial, rodadas por dimensão, dimensionamento da
suíte, o que trava merge acima do piso.

**Vetor B — domínios técnicos.** Profundidade 0–3, **derivada** da stack +
triagem. Override é *upward-only*: o cliente eleva, nunca reduz. Peso baixo em
modelagem de dados num sistema data-heavy não é preferência, é erro — e o
framework não deve permitir errar por configuração.

Segurança aparece nos dois de propósito: no A é o que a entrega **garante**; no B
é **quanto trabalho de especialista** entra.

### Pisos

Peso move rigor para cima ou redistribui ênfase. Nunca desce abaixo do piso, e
peso zero não existe. Três pisos são altos: correção funcional (é a definição de
entregue), observabilidade (sem ela nada mais é verificável depois do deploy), e
segurança — cujo piso é **escalado pela classe de dado** na triagem e não desce
por peso. No vetor B, QA nunca é 0.

---

## Os cinco papéis

Papel não é cargo. `spec/roles.toml` define cinco porque cada um tem **acesso
diferente** — ferramenta, contexto, artefato. Papel que roda o mesmo modelo, no
mesmo contexto, com as mesmas ferramentas que outro é o mesmo papel de chapéu
diferente, e o "arquiteto" aprova o que ele mesmo desenhou.

O que produz separação real: `denied_tools` (o papel não consegue), `isolation`
(o papel não vê), handoff por artefato (I7).

PM, PO, squad lead e tech lead foram colapsados. Existem em organograma humano
porque humano não tem contexto compartilhado. Agente tem.

---

## Enforcement: três tiers, declarados

A camada de instrução é agnóstica. A de enforcement não é e nunca vai ser — hook,
restrição de ferramenta e worktree são implementação de cada ferramenta, com
capacidade desigual. Por isso **o invariante mora no repositório**: git hook + CI
funcionam com qualquer agente, com dev humano, e continuam funcionando depois que
o FDE sai (I6).

| tier | significa |
|---|---|
| `loop` | hook + restrição por papel. Bloqueia antes da escrita. |
| `commit` | sem hook, mas há subagente/worktree. Papéis reais, gate no git. |
| `advisory` | só instrução. Papéis são convenção, gate é o CI. |

`fde doctor` declara o tier e separa o que está **enforçado** do que é apenas
**sugerido**. Prometer paridade e entregar teatro em três de cinco ferramentas é
o que queima framework aberto.

---

## Uso

Zero dependência externa. Python 3.11+ (`tomllib` é stdlib). Roda no repo do
cliente sem instalar nada.

```bash
# 1. parametrizar (detecta a stack; pergunta só o que não dá para inferir)
python bin/init.py
#    ou não-interativo:
python bin/init.py --yes --data-class pessoal --reversibility irreversivel

# 2. compilar os artefatos nativos da ferramenta em uso
python bin/compile.py
git config core.hooksPath .githooks

# 3. ver o que está de fato enforçado
python bin/fde/doctor.py

# 4. por demanda
python bin/triage.py --surfaces 2 --loc 120     # dimensiona
python bin/review.py DEM-001 --isolate          # adversarial isolado
python bin/fde/verify.py --all                  # gate (o mesmo do CI)
```

### Comandos como skills

Cada comando tem skill correspondente em `skills/` no formato Agent Skills —
portátil, lida por ~30 ferramentas. `commands/` não é usado: é formato legado no
Claude Code e não é padrão aberto.

A lógica vive em `bin/` como script determinístico, nunca em prompt. Três razões:
roda no CI sem agente nenhum, não varia entre ferramentas nem entre execuções do
mesmo modelo, e é testável. Detecção de stack dentro de prompt é diferente toda
terça.

---

## Configuração

`fde.config.toml` é o declarativo único, versionado. Diff auditável,
recompilação idempotente, projeto novo parametrizado por cópia, modo
não-interativo para CI.

Duas naturezas, deliberadamente separadas: **parametrizável** (comandos de build
e teste, caminhos, classe de dado, pesos, profundidade) e **fixo** (os
invariantes). Fixo não é campo do arquivo — não existe chave.

Arquivo gerado leva `FDE-KERNEL:GENERATED` no topo. Editar à mão é perda
garantida no próximo `sync`; o conserto é na fonte.

---

## Limites conhecidos

- `evals/` é a interface esperada, mas o kernel não impõe framework de eval.
  Inspect AI, promptfoo, DeepEval e suíte caseira funcionam igual.
- No tier `advisory` os papéis são convenção. O gate ainda vale, no commit e no CI.
- `git worktree` é requisito para o isolamento forçado fora do tier `loop`.
- Adapters cobertos: Claude Code (`loop`), Codex e Cursor (`commit`). Copilot,
  Kiro, Gemini CLI e Windsurf funcionam via AGENTS.md em `advisory` até ganharem
  adapter próprio.
- "Adversarial" em ML já significa adversarial examples e GANs. Aqui significa
  contraditório de processo. Vale desambiguar na primeira menção a quem vem de ML.

## Licença

Apache-2.0.
