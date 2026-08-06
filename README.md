# Carro da Liliana

Comparador offline do mercado português de automóveis novos 100% elétricos
(BEV). Só ofertas particulares confirmadas, com IVA e variante demonstrados,
provam o limite de 40.000 €. Ofertas incertas permanecem visíveis como
referências explicitamente rotuladas, sem semântica de PVP particular, IVA
incluído ou elegibilidade; híbridos, PHEV, extensores de autonomia, combustão,
comerciais, usados e importações não oficiais ficam fora do catálogo.

## Abrir a aplicação

```sh
make serve
```

O comando mostra o endereço a abrir. Prefere <http://localhost:8000>; se essa
porta estiver ocupada, escolhe automaticamente a próxima porta livre. Também
pode abrir `web/index.html` diretamente, porque os dados e recursos usados pela
interface são locais.

## Atualizar os dados

`data/vehicles/pt_market.json` é a fonte de verdade dos automóveis (schema 3) e
`data/dealers/near_sao_mamede.json` contém um concessionário oficial preferencial
por marca, escolhido pela proximidade a São Mamede de Infesta. O bundle que o
browser carrega é sempre regenerado a partir destes JSONs.

```sh
make update          # monitoriza fontes, gera propostas, valida schema v3 e testa
make update-photos   # atualiza também as imagens oficiais em falta
make update-photos-all # recaptura todas as imagens para auditoria visual
make prune-images    # arquiva imagens que nenhum modelo referencia
make lint            # ruff sobre scripts e testes
make validate        # valida schema v3 e compila fail-closed; não usa rede
make freshness       # acrescenta frescura global e campanhas expiradas
make budgets         # falha se as fotografias excederem o orçamento de peso
make links           # verifica fontes e páginas dos concessionários
make test            # executa a suíte de regressão
make audit           # lint, dados, frescura, testes e todos os links
make sequential      # update → fotografias em falta → auditoria final
```

## Política de preços e elegibilidade

Cada variante usa `pricing.offers[]`. Uma oferta `confirmed` exige fonte oficial
PT, variante exacta, público particular, IVA incluído ou derivado exatamente,
condições completas, validade explícita quando publicada e prova literal. Só
essa oferta pode criar o estado `confirmed_eligible`, provar o limite de 40.000 €
e alimentar ranking, filtros de preço ou financiamento automático.

Uma oferta `reference` conserva montante, fonte original e `recorded_on`, mas
mantém `legacy_unverified: true`, `verified_on: null` e IVA/público/variante por
confirmar quando não demonstrados. Nunca é apresentada como PVP particular
confirmado. A interface deve mostrar junto ao montante `Confirmado`,
`Referência — IVA por confirmar`, `Referência — público por confirmar` ou
`Referência — versão/condições por confirmar`; não esconder o estado num tooltip.

Estados de modelo/variante:

- `confirmed_eligible`: existe oferta exacta confirmada até 40.000 €;
- `potential_reference`: existe montante de referência, sem prova suficiente;
- `not_demonstrated`: não existe montante com base suficiente para referência.

`null` significa “por confirmar” em campos técnicos e de IVA. A química da
bateria só é preenchida quando demonstrada para a variante exacta; não inferir
química pela marca, plataforma ou capacidade.

Hierarquia de fontes: configurador, tabela de preços ou campanha da
marca/importador oficial PT; página portuguesa e ficha técnica oficial; PDF
oficial português atual; concessionário oficialmente autorizado em Portugal
quando a marca não publica o preço. EVMag, imprensa e comparadores servem apenas
como radar de descoberta. Cada oferta regista `source_authority` como
`manufacturer_or_importer_pt` ou `authorised_dealer_pt`, e `market` como `PT`.

`make update` monitoriza fontes conhecidas e redescobre candidatos, mas a leitura
de preços gera propostas em `data/price_proposals.json`. Proposta sem prova não
é publicada como confirmada. `make validate` rejeita ofertas sem contrato v3 e
provas `confirmed`/atuais envelhecidas; `compile_data.py` repete a validação
antes de escrever bundle ou índice, por isso falha sem publicar catálogo inválido.
Referências `legacy_unverified` completas continuam aceites e explicitamente
classificadas. `make update-accept` continua reservado à revisão humana explícita
de fingerprints.

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
sejam BEV, datas mal formadas, ofertas v3 incompletas e marcas sem concessionário
oficial próximo registado. Só ofertas confirmadas até 40.000 € criam elegibilidade;
referências incompletas continuam visíveis com rótulo próprio.

As verificações de calendário têm duas camadas. `make validate` falha fechado
quando prova `confirmed` ou referência atual (`proof.status: "verified"`) tem
mais de 45 dias; como a compilação chama a mesma validação antes de escrever o
bundle, evidência envelhecida não chega à aplicação. Referências legadas com
`proof.status: "legacy_unverified"` e `verified_on: null` continuam publicáveis
como referência, nunca como preço confirmado.

`make freshness` acrescenta verificações globais: fontes de descoberta, modelos
e concessionários com mais de 45 dias, além de campanhas expiradas. Essas
verificações fazem falhar `make freshness` e `make audit`; não substituem a
validação fail-closed de ofertas executada por `make validate`.

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
| `ci.yml` | push em `main`, pull requests | `make verificar`: lint, dados, compilação e testes; confirma que o bundle compilado está commitado |
| `data-health.yml` | segunda-feira 06:00 UTC, ou manualmente | `make validate`, `make freshness` e `make links`; abre ou comenta uma issue com a etiqueta `dados-frescura` quando algo falha |

O `ci.yml` corre `make verificar`: lint, validação fail-closed, compilação e
testes, incluindo rejeição de provas confirmadas/atuais envelhecidas. O
`data-health.yml` repete validação no calendário e acrescenta frescura global e
ligações externas; cada falha fica registada numa issue. `make verificar` não
corre `make freshness` nem `make links`: indisponibilidade externa não deve
reprovar um pull request. O GitHub desativa workflows agendados depois de 60
dias sem atividade no repositório — se as issues semanais pararem, é a primeira
coisa a confirmar.

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

Regra de inclusão elegível: um modelo só pode ser `confirmed_eligible` se for
100% elétrico, tiver pelo menos uma variante disponível em Portugal com oferta
confirmada para particulares até 40.000 € com IVA, uma fotografia correta e um
concessionário oficial preferencial próximo de São Mamede de Infesta. Modelos
`potential_reference` podem ficar no catálogo para investigação, mas não provam
o limite. Confirme stock, preço final e marcação diretamente com o stand.

## Repositório público e licenças

O código e a documentação originais são disponibilizados sob a
[licença MIT](LICENSE). Fotografias, marcas e recursos de terceiros não são
abrangidos por essa licença; consulte [ASSET_NOTICE.md](ASSET_NOTICE.md).

Propostas comerciais, emails, documentos de pesquisa, relatórios de QA e
artefactos locais não fazem parte do repositório. A validação automática de cada
push e pull request é executada pelo GitHub Actions sem consultar fontes
externas, evitando falhas causadas por proteção anti-bot ou indisponibilidade
temporária.
