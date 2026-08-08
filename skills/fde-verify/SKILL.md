---
name: fde-verify
description: Roda o gate de invariantes — exatamente o mesmo verificador que o pre-commit e o CI executam. Use antes de qualquer commit, antes de abrir PR, quando um commit for rejeitado pelo hook, ou quando o usuário perguntar se algo "está pronto", "pode subir", "está em condição de produção". Use também para explicar por que um gate reprovou.
---

# fde-verify

```bash
python bin/fde/verify.py --staged           # pre-commit (rápido)
python bin/fde/verify.py --all              # CI (completo)
python bin/fde/verify.py --gate eval        # um gate
python bin/fde/verify.py --format json      # máquina
```

## Ao explicar uma reprovação

Diga qual invariante, por que ele existe, e qual é o conserto. Não sugira contornar — não há chave de bypass, e procurar uma é o comportamento que o framework existe para impedir.

| gate | o que faltou | conserto |
|---|---|---|
| I1 | mudança de comportamento sem entrada de eval | escreva o failure mode e o evaluator |
| I2 | revisão adversarial não rodou isolada | `fde review <id> --isolate` |
| I3 | papel adversarial tocou código | reverta; achado vai em `reviews/`, correção é de outro papel |
| I4 | critério de aceite ausente ou sem data | declare antes de construir; datado |
| I5 | atributo declarado sem sinal | instrumente ou reduza o que foi declarado |
| I6 | gate não roda sem o FDE | `fde sync` recopia o runtime |
| I7 | handoff sem artefato em disco | crie a estrutura; não passe contexto por conversa |
