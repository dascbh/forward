---
name: fde-doctor
description: Mostra o tier de capacidade da ferramenta agêntica em uso e o que está DE FATO enforçado versus apenas sugerido. Use quando o usuário assumir que uma regra vai bloquear algo, quando trocar de ferramenta, quando perguntar se o padrão "está ativo", ou antes de prometer garantia de rigor a um cliente. Use no início de qualquer sessão num repositório sob o kernel que você ainda não inspecionou.
---

# fde-doctor

```bash
python bin/fde/doctor.py
```

Parece acessório e é o comando mais importante politicamente: impede que alguém ache que tem parede quando tem só recomendação.

## Tiers

| tier | significa |
|---|---|
| `loop` | hook + restrição de ferramenta por papel. Bloqueia antes da escrita. |
| `commit` | sem hook, mas há subagente/worktree. Papéis reais, gate no git. |
| `advisory` | só arquivo de instrução. Papéis são convenção, gate é o CI. |

## Ao relatar

Seja explícito sobre a diferença. Se o tier é `advisory`, diga que os papéis são convenção naquela ferramenta e que o bloqueio real acontece no commit e no CI — não deixe o usuário acreditar em garantia que não existe.

Prometer paridade entre ferramentas e entregar teatro em três de cinco é o que queima framework aberto. A honestidade sobre o tier é o que sustenta a adoção.
