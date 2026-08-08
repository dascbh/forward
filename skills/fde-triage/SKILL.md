---
name: fde-triage
description: Dimensiona uma demanda e decide quais papéis e quantas rodadas adversariais ativam. Use SEMPRE antes de começar qualquer trabalho de implementação num projeto sob o kernel — mudança de uma linha ou feature inteira. Use quando o usuário disser que o processo está pesado demais para o tamanho da tarefa, ou pedir para "pular etapas". É o caminho legítimo para reduzir cerimônia sem relaxar critério.
---

# fde-triage

Se o fluxo completo roda numa mudança de três linhas, o framework é desligado na segunda semana. Por isso o dimensionamento é código, não bom senso.

```bash
python bin/triage.py --surfaces 2 --loc 120
```

## O que escala

Papéis ativos, rodadas adversariais, exigência de ADR.

## O que nunca escala

Os invariantes. Em XS e em L, os sete valem igual. O que varia é a **fronteira coberta**, não o **critério aplicado**.

Quando o usuário reclamar do peso do processo: rode triage e mostre o plano reduzido. Quando pedir para desligar o gate: explique que não existe chave, e que o caminho é encolher o escopo da entrega até caber no padrão — não o contrário.
