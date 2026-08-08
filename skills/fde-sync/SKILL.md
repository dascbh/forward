---
name: fde-sync
description: Recompila os artefatos nativos a partir de fde.config.toml e detecta drift em arquivo gerado que foi editado à mão. Use sempre que o usuário alterar pesos, mudar de ferramenta agêntica, adicionar uma stack ao projeto, ou quando um arquivo com o marcador FDE-KERNEL:GENERATED parecer inconsistente com a configuração. Use também quando o usuário perguntar por que uma regra "não está pegando" ou "sumiu".
---

# fde-sync

Regenera. Idempotente.

```bash
python bin/compile.py            # regenera
python bin/compile.py --check    # valida sem escrever
```

## Drift

Todo arquivo emitido leva `FDE-KERNEL:GENERATED` no topo. Editar à mão é perda garantida: o próximo `sync` sobrescreve.

Se o usuário editou um arquivo gerado, o conserto é **na fonte** — `fde.config.toml` para o que é do projeto, `spec/` para o que é do kernel — e então recompilar. Nunca sugira "editar direto e não rodar sync": isso quebra a garantia de que o padrão é o mesmo em todas as ferramentas.

## Quando a ferramenta muda

O usuário trocou de Cursor para Claude Code, ou passou a usar as duas? Só rode `sync`. A fonte é a mesma; o que muda é qual adapter emite. Confira o resultado com `fde-doctor` — o tier de enforcement muda com a ferramenta e o usuário precisa saber disso.
