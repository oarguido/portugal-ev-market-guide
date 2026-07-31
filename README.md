# Carro da Liliana

Comparador offline do mercado português de automóveis novos 100% elétricos
(BEV) cujo PVP ou campanha atual com IVA não ultrapassa 40.000 €. Condições de
campanha são apresentadas separadamente; híbridos, PHEV, extensores de autonomia,
combustão, comerciais, usados e importações não oficiais ficam fora do catálogo.

## Abrir a aplicação

```sh
make serve
```

O comando mostra o endereço a abrir. Prefere <http://localhost:8000>; se essa
porta estiver ocupada, escolhe automaticamente a próxima porta livre. Também
pode abrir `web/index.html` diretamente, porque os dados e recursos usados pela
interface são locais.

## Atualizar os dados

`data/vehicles/pt_market.json` é a fonte de verdade dos automóveis e
`data/dealers/near_sao_mamede.json` contém um concessionário oficial preferencial
por marca, escolhido pela proximidade a São Mamede de Infesta. O bundle que o
browser carrega é sempre regenerado a partir destes JSONs.

```sh
make update          # verifica alterações nas fontes, valida, compila e testa
make update-photos   # atualiza também as imagens oficiais em falta
make update-photos-all # recaptura todas as imagens para auditoria visual
make prune-images    # arquiva imagens que nenhum modelo referencia
make lint            # ruff sobre scripts e testes
make validate        # valida e recompila sem acesso à rede
make freshness       # falha se houver verificações antigas ou campanhas expiradas
make budgets         # falha se as fotografias excederem o orçamento de peso
make links           # verifica fontes e páginas dos concessionários
make test            # executa a suíte de regressão
make audit           # lint, dados, frescura, testes e todos os links
make sequential      # update → fotografias em falta → auditoria final
```

`make lint` corre o `ruff` através do `uv`, com a versão fixada em
`pyproject.toml` para que local e CI apliquem exatamente as mesmas regras. Sem
`uv` instalado, `make lint RUFF=ruff` usa o `ruff` do sistema.

O atualizador guarda fingerprints do texto visível das páginas oficiais em
`data/source_snapshots.json`, ignorando scripts, estilos e atributos dinâmicos.
Mantém também o hash bruto para diagnóstico. Se o conteúdo relevante mudar,
interrompe o processo para que preço, autonomia e condições sejam revistos.
Depois da revisão, execute:

```sh
make update-accept
```

O guia interativo da EVMag é monitorizado como radar secundário de mercado. Serve
para encontrar possíveis modelos em falta, mas nunca substitui a confirmação em
fontes oficiais portuguesas: a tabela também contém lançamentos futuros, veículos
comerciais, preços aproximados e entradas potencialmente duplicadas.

`make sequential` executa apenas a parte automatizada sobre as fontes já
registadas. Para imediatamente se uma etapa falhar ou se `make update` detetar
fontes alteradas. Nunca aceita fingerprints automaticamente e não substitui a
pesquisa manual de novos modelos descrita em `AGENTS.md`.

O validador rejeita links inválidos, fotografias em falta, powertrains que não
sejam BEV, datas mal formadas, variantes cujo preço elegível exceda 40.000 € e
marcas sem concessionário oficial próximo registado.

As verificações que dependem do calendário — fontes com mais de 45 dias e
campanhas já expiradas — são reportadas como `AVISO` pelo `make validate` e só
fazem falhar o `make freshness`, incluído no `make audit`. A separação é
deliberada: caso contrário o catálogo deixaria de compilar sozinho ao fim de 45
dias e a suíte de testes passaria a falhar por efeito do tempo, e não por
regressão.

`make links` distingue as fontes que foram realmente lidas das que apenas
responderam com proteção anti-bot, e imprime a contagem no fim:

```text
LIGAÇÕES: 100 no total, 69 verificadas, 31 não verificadas, 0 quebradas
```

Só as ligações quebradas fazem falhar o comando. Um HTTP 403, 429 ou uma ausência
de resposta a `urllib` não prova que a página mudou, mas também não prova que
continua igual: essas fontes são listadas para revisão num browser real, como
exige a secção 4 do `AGENTS.md`. Um resumo verde sem esta contagem esconderia que
quase um terço das fontes não foi verificado.

O peso das fotografias é reportado como `AVISO` pelo `make validate` e só faz
falhar o `make budgets`, que fica fora do `make audit`. Uma fotografia pesada é um
problema de desempenho, não uma regressão de correção — e uma fotografia oficial
correta vale mais que o orçamento.

## Automação no GitHub

| Workflow | Quando corre | O que faz |
|----------|-------------|-----------|
| `ci.yml` | push em `main`, pull requests | `make lint`, `make validate`, `make test` e confirma que o bundle compilado está commitado |
| `data-health.yml` | segunda-feira 06:00 UTC, ou manualmente | `make freshness` e `make links`; abre ou comenta uma issue com a etiqueta `dados-frescura` quando algo apodrece |

A separação é a mesma dos comandos locais: o `ci.yml` verifica o que uma
alteração pode quebrar, o `data-health.yml` verifica o que o calendário quebra
sozinho. O GitHub desativa workflows agendados depois de 60 dias sem atividade no
repositório — se as issues semanais pararem, é a primeira coisa a confirmar.

## Estrutura

```text
data/                 veículos, concessionários e fingerprints
web/                  aplicação estática e todos os seus assets locais
scripts/              compilação, validação e atualização
scripts/legacy/       utilitários antigos preservados para referência
tests/                testes automáticos
archive/              histórico local ignorado, sempre fora do build
graphify-out/         grafo técnico local e reproduzível, ignorado pelo Git
```

Regra de inclusão: um modelo só pode entrar no catálogo se for 100% elétrico,
tiver pelo menos uma variante disponível em Portugal por até 40.000 € com IVA,
uma fotografia correta e um concessionário oficial preferencial próximo de São
Mamede de Infesta. Confirme stock, preço final e marcação diretamente com o stand.

## Repositório público e licenças

O código e a documentação originais são disponibilizados sob a
[licença MIT](LICENSE). Fotografias, marcas e recursos de terceiros não são
abrangidos por essa licença; consulte [ASSET_NOTICE.md](ASSET_NOTICE.md).

Propostas comerciais, emails, documentos de pesquisa, relatórios de QA e
artefactos locais não fazem parte do repositório. A validação automática de cada
push e pull request é executada pelo GitHub Actions sem consultar fontes
externas, evitando falhas causadas por proteção anti-bot ou indisponibilidade
temporária.
