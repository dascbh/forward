---
name: fde-init
description: Parametriza um projeto sob o FDE kernel — detecta a stack, entrevista só o que a detecção não resolve, aloca o vetor de pesos e compila os artefatos nativos da ferramenta em uso. Use sempre que o usuário for começar um projeto novo, adotar o kernel num repositório existente, ou mencionar "setup", "bootstrap", "parametrizar", "adotar o padrão", "clonar o framework". Use também quando o usuário pedir para construir algo (plataforma, serviço, agente) num repositório que ainda não tem fde.config.toml.
---

# fde-init

Parametriza o projeto. Roda uma vez; depois use `fde-sync`.

## Ordem obrigatória

1. **Detecte, não pergunte.** `python bin/detect_stack.py` resolve linguagem, runner, frontend, banco, API, CI, IaC e bibliotecas de IA a partir de arquivo no repositório. Perguntar o que dá para inferir produz resposta pior que a inferência.

2. **Confirme em bloco.** Mostre tudo que foi detectado de uma vez e peça uma confirmação. Nunca uma pergunta por item.

3. **Entreviste só o não resolvido.** Três coisas não são inferíveis de arquivo e mudam o piso: classe do dado mais sensível, reversibilidade de um erro em produção, e se há loop de agente. Pergunte essas e mais nada.

4. **Aloque o vetor A com o usuário.** Orçamento fechado de 100 pontos entre os oito atributos de qualidade. O default do `init` é ponto de partida, não recomendação neutra — o usuário move. Explique o que o peso faz: ordena o ataque adversarial, dimensiona a suíte, decide o que trava merge acima do piso.

5. **Não negocie o vetor B.** A profundidade dos domínios técnicos é derivada da stack + triagem. Se o usuário quiser reduzir, explique que override é upward-only: peso baixo em modelagem de dados num sistema data-heavy não é preferência, é erro.

6. **Compile.** `python bin/compile.py`.

## Comando

```bash
python bin/init.py                    # interativo
python bin/init.py --yes \
  --data-class pessoal \
  --reversibility irreversivel        # CI / não-interativo
python bin/compile.py
git config core.hooksPath .githooks
```

## O que NÃO fazer

Não ofereça desligar gate, relaxar piso ou pular etapa para "ir mais rápido no começo". O escopo encolhe; o padrão não. Se o usuário insistir, mostre `fde-triage` — o caminho legítimo para reduzir cerimônia é dimensionar a demanda, não relaxar o critério.
