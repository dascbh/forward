---
name: fde-review
description: Executa a revisão adversarial em contexto isolado, com ordem de ataque derivada dos pesos do projeto. Use antes de promover qualquer artefato, quando o usuário pedir revisão, code review, red team, "tenta quebrar isso", ou perguntar se algo está seguro/robusto o suficiente. Use SEMPRE em worktree isolada — revisor que vê o raciocínio de quem construiu concorda com ele mesmo.
---

# fde-review

```bash
python bin/review.py <demand-id> --plan-only    # ver o plano
python bin/review.py <demand-id> --isolate      # worktree isolada + esqueleto
```

## Regras que não se negociam

**Isolamento (I2).** O revisor recebe artefato e especificação. Não recebe o contexto, o histórico nem o raciocínio de quem construiu. Se você está no mesmo thread que produziu o código, você **não pode** ser o revisor — crie a worktree e rode ali.

**Sem correção (I3).** O papel adversarial registra em `reviews/<id>/findings.toml` e para. Corrigir é do papel de implementação. Revisor que conserta o que achou apaga o registro do achado.

**Sucesso é achado.** A meta não é aprovar. Uma revisão que não encontrou nada é suspeita antes de ser boa notícia — declare quantas rodadas rodou e o que sondou.

## Ordem

Derivada dos pesos do vetor A, não da sua intuição sobre o que é interessante. Peso alto ataca primeiro e ganha mais rodadas. Atributo com peso baixo ainda recebe pelo menos uma rodada — piso, não zero.
