# AGENTS.md — contrato operacional do projeto

Este documento é o runbook obrigatório para qualquer agente (OpenAI, Anthropic,
Google ou outro) que altere este repositório. Não assumir contexto de conversas
anteriores nem conhecimento próprio atualizado: o estado do repositório e as
fontes verificadas nesta execução são a única base de trabalho.

## 1. Objetivo e idioma

Manter uma aplicação estática e offline, em Português de Portugal, que compare
automóveis de passageiros novos, 100% elétricos e oficialmente disponíveis em
Portugal. Só ofertas particulares confirmadas, com IVA e variante demonstrados,
podem provar o limite de 40.000 €.

- Escrever interface, dados, documentação e mensagens em Português de Portugal.
- Usar EUR, km, kWh, kW, cv e datas ISO `AAAA-MM-DD`.
- Não transformar o catálogo numa lista de anúncios, usados ou importações.
- Não apresentar uma referência como facto. Valores incertos podem permanecer
  visíveis, mas têm de ser ofertas `reference`, com rótulo explícito e sem
  semântica de PVP particular, IVA incluído ou elegibilidade.
- Em campos numéricos técnicos, `null` significa “por confirmar”; nunca usar
  zero, texto aproximado ou inferência.

## 2. Regras de publicação e inclusão não negociáveis

Um modelo só pode ser marcado `confirmed_eligible` quando todas as condições
seguintes forem verdadeiras:

1. É um automóvel ligeiro de passageiros M1.
2. É novo e exclusivamente BEV (sem motor de combustão).
3. Está oficialmente disponível para encomenda ou compra em Portugal agora.
4. Existe pelo menos uma oferta `confirmed` de uma variante exacta, para
   particulares, com IVA incluído ou derivado deterministicamente, até 40.000 €.
5. A oferta tem prova literal, fonte oficial PT, condições e validade sem
   omissões.
6. Existe página/fonte oficial portuguesa, data de verificação e fontes dos
   factos relevantes.
7. Existe uma fotografia local correta do modelo.
8. Existe exatamente um concessionário oficial preferencial da marca, com venda
   de veículos novos, escolhido pela proximidade a São Mamede de Infesta.

Entradas `potential_reference` podem permanecer no catálogo para investigação,
desde que cada montante seja mostrado como referência. Não são inclusão
elegível, não contam no limite e não podem alimentar ranking, filtros de preço
ou financiamento automático.

Excluir sempre:

- gasolina, diesel, GPL ou outro veículo de combustão;
- mild hybrid, full hybrid, PHEV, range-extender e REEV;
- comerciais N1, derivados comerciais e veículos sem homologação M1;
- usados, seminovos, viaturas de serviço e importações não oficiais;
- conceitos, anúncios futuros e modelos apenas “a chegar” ou sem encomendas PT;
- variantes cujo único preço `confirmed` exceda 40.000 € com IVA;
- referências sem fonte original, data de registo ou classificação explícita.

Um modelo pode permanecer com variantes de referência, mas o estado deve ser
`potential_reference` ou `not_demonstrated`. Não incluir uma variante acima do
limite como elegível só porque outra versão do mesmo modelo é elegível.

## 3. Fontes de verdade e ficheiros gerados

Editar:

- `data/vehicles/pt_market.json`: fonte de verdade dos veículos, schema 3.
- `data/dealers/near_sao_mamede.json`: fonte de verdade dos concessionários,
  schema 1.
- `web/assets/images/vehicles/`: fotografias locais.
- código, testes e documentação quando o comportamento mudar.

Não editar manualmente:

- `web/assets/js/car_data.js`: é gerado por `scripts/compile_data.py`.
- `data/source_snapshots.json`: é gerido pelo atualizador depois da revisão.
- `archive/`: é histórico e nunca entra no build.

A interface offline carrega exclusivamente o bundle compilado e os assets locais.
Uma alteração no JSON que não seja compilada não chegou à aplicação.

Os módulos em `web/assets/js/` são carregados por `web/index.html` e um teste
exige que o conjunto seja exatamente igual: acrescentar um módulo sem o registar
no HTML falha. Todo o valor vindo do catálogo que seja interpolado em `innerHTML`
tem de passar por `escapeHtml` (`web/assets/js/html.js`). Não é teatro de
segurança: o catálogo é editado à mão e um nome legítimo como "Silva & Filhos" ou
uma condição de campanha com aspas produz HTML inválido ou atributos truncados.
Escapar na fronteira do render torna a aplicação independente do conteúdo dos
dados. Nenhuma fotografia é carregada sem `loading="lazy"`.

## 4. Hierarquia das fontes

Usar, por ordem de preferência:

1. configurador, tabela de preços ou campanha da marca/importador oficial PT;
2. página oficial portuguesa do modelo e ficha técnica oficial;
3. PDF oficial português atual;
4. concessionário oficialmente autorizado em Portugal, quando a marca/importador
   não publica o preço diretamente.

Fontes secundárias (EVMag, imprensa, bases de dados, comparadores, fóruns ou
resultados de pesquisa) servem apenas para descobrir candidatos e inconsistências.
Nunca são prova final de preço, disponibilidade, categoria, especificação ou
elegibilidade.

Uma fonte europeia ou de outro país não prova preço nem disponibilidade em
Portugal. Pode ajudar a localizar uma especificação, mas o valor só entra quando
for confirmado para a variante portuguesa.

Quando uma página devolver 403/429:

- abrir a página num browser real;
- verificar visualmente o conteúdo e a data;
- não interpretar o 403/429 como prova de que os dados continuam iguais;
- manter a URL oficial como fonte se o conteúdo tiver sido efetivamente revisto.

## 5. O que significa “atualização completa”

Uma atualização completa tem duas partes distintas. Ambas são obrigatórias.

### A. Monitorizar o universo já conhecido

```sh
make update
```

O comando descarrega as fontes já registadas, compara fingerprints, valida,
compila e executa testes. Resultados:

- código 0: fontes conhecidas sem alterações bloqueantes e testes aprovados;
- código 1: falha de rede, fonte ou validação;
- código 2: uma ou mais páginas mudaram e exigem revisão.

O fingerprint semântico deteta alterações no texto visível e ignora scripts,
estilos e atributos dinâmicos. O hash bruto fica apenas para diagnóstico. Mesmo
assim, uma alteração detetada não determina automaticamente qual facto mudou.
O atualizador repete até três vezes falhas transitórias de ligação, timeout e
HTTP 500/502/503/504; uma falha persistente continua a bloquear a atualização.

O fluxo de preços v3 não publica números extraídos sem prova. `refresh_prices`
gera propostas em `data/price_proposals.json`; cada proposta leva classificação,
fonte, mercado, data de registo, estado de IVA/público/variante e excerto literal
quando este existir. Só uma revisão documental pode promover uma proposta a
`confirmed`; uma oferta antiga ou incerta permanece `reference` e nunca altera
elegibilidade, ranking, filtros ou financiamento. `make validate` e a compilação
devem rejeitar ofertas sem o contrato v3, mas aceitam referências completas e
explicitamente rotuladas.

### B. Redescobrir o mercado

`make update` não encontra sozinho todas as marcas ou modelos novos. O agente tem
de fazer uma pesquisa de mercado atual:

1. Rever todas as entradas das fontes de descoberta, incluindo o guia EVMag.
2. Rever as gamas BEV de passageiros nos sites oficiais portugueses.
3. Procurar lançamentos, novas versões, campanhas, descontinuações e alterações
   de preço desde `last_verified`.
4. Comparar os candidatos encontrados com `(brand, model)` e variantes existentes.
5. Para cada candidato, registar mentalmente ou no relatório final uma decisão:
   incluir, excluir ou pendente, com o motivo e a fonte.
6. Confirmar todos os candidatos potencialmente elegíveis em fontes oficiais PT.

“Varrer o mercado” não significa copiar uma lista secundária. Significa usá-la
como radar e fechar cada decisão em fontes oficiais.

## 6. Fluxo de atualização de um modelo existente

Para cada modelo e variante:

1. Abrir todas as `data_sources`.
2. Confirmar que o modelo continua disponível, novo, M1 e BEV.
3. Confirmar a designação exata da versão portuguesa.
4. Classificar cada oferta como `confirmed` ou `reference`; só confirmar preço
   com IVA quando público particular, variante exacta e prova literal estiverem
   presentes.
5. Confirmar autonomia WLTP combinada, bateria e potência.
6. Rever condições, validade, financiamento, retoma, stock e despesas.
7. Atualizar apenas os valores demonstrados pela fonte; valores antigos sem
   revisão tornam-se ofertas `reference` com `legacy_unverified: true`.
8. Cada referência conserva URL e `recorded_on`, mas usa `verified_on: null` e
   nunca pode alimentar elegibilidade, ranking, filtros ou financiamento.
9. Definir campos técnicos não demonstrados como `null`; não conservar valores
   antigos como se tivessem sido confirmados.
10. Atualizar `last_verified` e todos os `data_sources[].verified_on` apenas
    depois da revisão real.
11. Remover uma variante que deixou de estar oficialmente disponível; não a
    promover só porque conserva um preço de referência.
12. Remover o modelo apenas quando deixar de ter base documental para estar no
    mercado, não por faltar confirmação de preço.

Não atualizar uma data de verificação em massa sem abrir e rever as fontes.

## 7. Fluxo de entrada de um modelo novo

Executar pela ordem seguinte:

1. Confirmar BEV, M1, novo e oficialmente encomendável em Portugal.
2. Para `confirmed_eligible`, confirmar pelo menos uma variante até 40.000 €
   com IVA, público particular, variante exacta e prova literal.
3. Para uma entrada de investigação, registar referência com fonte original,
   data de registo e rótulo explícito; nunca a chamar PVP particular.
4. Recolher página do modelo e fonte oficial de preço/campanha.
5. Criar o modelo e variantes em `data/vehicles/pt_market.json`.
6. Adicionar/confirmar o concessionário da marca mais próximo.
7. Guardar e auditar visualmente uma fotografia correta.
8. Executar `make validate && make test`.
9. Abrir a aplicação e confirmar pesquisa, cartão, estado do preço, imagem,
   fonte e stand.

Não compilar/publicar primeiro para “preencher depois”. Fotografia, fonte e
concessionário são pré-condições.

## 8. Estrutura canónica dos veículos

O catálogo raiz deve manter:

- `schema_version: 3`, `market: "PT"`, `currency: "EUR"`;
- `last_verified`, `scope`, `discovery_sources` e `models`;
- limite explícito de 40.000 € com IVA, `powertrain: "BEV"` e política de
  referências.

Cada modelo requer pelo menos:

- `brand`, `model`, `powertrain`, `segment`, `release_year`;
- `availability_status: "available"` e `eligibility_status`/`eligibility_tier`
  com um de `confirmed_eligible`, `potential_reference` ou
  `not_demonstrated`;
- `official_link`, `image_path`, `last_verified`;
- `data_sources` não vazio;
- `variants` não vazio.

Cada variante requer pelo menos:

- `name`;
- `battery_capacity_kwh`;
- `wltp_range_combined_km`;
- `power_kw` e `power_hp`;
- `battery_technology`, com `null` para cada campo técnico não demonstrado;
- `pricing.offers`, mesmo que a lista esteja vazia.

Cada `pricing.offers[]` usa o contrato v3:

- `kind`: `list_price` ou `campaign_price`;
- `classification`: `confirmed` ou `reference`;
- `amount_eur`, `currency`, `market`, `source_url`, `source_authority` e
  `source_type`;
- `vat` e `vat_included`, onde `null` significa IVA por confirmar e
  `included`/`derived` só podem aparecer com prova confirmada;
- `customer`, `variant`, `conditions` e `validity`, com `valid_from` e
  `valid_until` mesmo quando ambos são `null`;
- `proof`, com `status`, autoridade, fonte, tipo, mercado, público, variante,
  base de IVA, `recorded_on`, `verified_on` e `literal_excerpt`;
- `evidence`, como excerto literal ou `null`, e `evidence_record`, com URL
  original, `recorded_on`, `verified_on` e o mesmo excerto;
- `derivation`, ou `null` quando não existe derivação;
- `recorded_on` e `verified_on` no próprio objecto.

Regras de preço:

- A aplicação pode escolher campanha antes de PVP apenas dentro da coorte
  `confirmed_eligible`; referências têm percurso e rótulo separados.
- Uma campanha confirmada exige condições explícitas; nunca ocultar financiamento,
  retoma, stock, versão limitada, despesas ou destinatários.
- Uma referência legada conserva `legacy_unverified: true`, fonte original,
  `recorded_on` e `verified_on: null`. Excerto inexistente fica `null`; nunca
  fabricar prova.
- `classification: reference` nunca significa PVP particular, IVA incluído,
  elegibilidade, preço filtrável ou entrada automática no financiamento.
- `classification: confirmed` exige público particular, variante exacta, IVA
  incluído ou derivação determinística, autoridade oficial PT e prova literal.
- Se não existir validade publicada, usar `null` e indicar nas condições que deve
  ser confirmada; nunca inventar uma data.
- Uma conversão exacta de preço oficial sem IVA para IVA português só é aceitável
  quando for aritmética determinística, estiver claramente declarada em
  `derivation` e a fonte original permanecer registada. Não arredondar nem
  chamar PVP oficial ao valor derivado.

### Estados e etiquetas obrigatórias

- `confirmed_eligible`: pelo menos uma oferta confirmada exacta, particular,
  com IVA e até 40.000 €. É a única coorte que prova o limite.
- `potential_reference`: existe montante de referência, mas falta pelo menos
  uma prova de IVA, público, variante, validade ou confirmação atual.
- `not_demonstrated`: não existe oferta numérica com base suficiente para sequer
  servir de referência.
- Interface e relatórios devem escrever junto ao montante `Confirmado`,
  `Referência — IVA por confirmar`, `Referência — público por confirmar` ou
  `Referência — versão/condições por confirmar`. Nunca esconder o estado apenas
  num tooltip.

### Tecnologia da bateria por variante

Cada variante mantém `battery_technology` com `chemistry`, `generation`,
`architecture`, `source_url` e `verified_on`. `null` significa “por confirmar”;
não autoriza inferência pela marca, plataforma ou capacidade. Uma química só é
preenchida quando a fonte oficial a demonstra para aquela variante exacta.

### Intervalos publicados para a gama inteira

Muitas marcas publicam autonomia, potência ou consumo como um intervalo que cobre
a gama toda — "444 – 569 km" para baterias de "57,7 e 73,1 kWh" — e não por
versão. Nesse caso, para a versão de menor capacidade regista-se o **extremo
inferior** do intervalo.

A regra é segura porque anda no mesmo sentido do preço: a versão elegível é
quase sempre a de bateria mais pequena, e é a essa que corresponde a autonomia
mais curta. Mais bateria custa mais dinheiro e dá mais autonomia, por isso o
extremo inferior nunca sobrevaloriza a versão barata. Um comparador que erre tem
de errar por defeito.

Condições, iguais às da conversão de IVA:

1. o intervalo tem de estar publicado na fonte oficial portuguesa;
2. a versão registada tem de ser mesmo a de menor capacidade da gama;
3. a derivação fica escrita em `range_note` na variante, para ninguém confundir
   o valor com um número medido para aquela versão;
4. a fonte que publica o intervalo fica registada em `data_sources`.

Não usar esta regra para inventar o extremo superior, nem para preencher um
valor quando a fonte não publica intervalo nenhum. Sem intervalo publicado, o
valor continua a exigir confirmação.

Para `data_sources`, usar URLs HTTPS oficiais, um `type` descritivo coerente com
os valores existentes (`official_model`, `official_campaign`,
`official_price_sheet`, etc.) e `verified_on` igual a `last_verified`. Em cada
oferta, `source_authority` distingue `manufacturer_or_importer_pt` de
`authorised_dealer_pt`; `market` é sempre `PT`.

Formato:

- JSON UTF-8, indentação de dois espaços e newline final;
- números como números, booleanos como booleanos e desconhecidos como `null`;
- não criar strings como `"N/A"`, `"por confirmar"` ou `"~400"` em campos
  numéricos;
- não duplicar `(brand, model)` nem nomes de variante dentro do modelo.

## 9. Concessionários próximos

`data/dealers/near_sao_mamede.json` tem exatamente uma entrada por marca ativa.
O conjunto de marcas tem de ser igual ao conjunto de marcas do catálogo.

Para escolher/atualizar:

1. Usar o localizador oficial da marca para provar autorização e venda de novos.
2. Identificar os pontos de venda na área do Porto/Matosinhos/Maia.
3. Comparar distância/tempo desde “São Mamede de Infesta, Matosinhos”.
4. Escolher o mais próximo verificável; não escolher apenas o mais conhecido.
5. Confirmar que `services` contém `sales`.
6. Registar nome, morada, código postal, localidade, telefone, email se publicado,
   URL oficial, URL de mapa e `verified_on`.

Uma mesma instalação multimarca pode aparecer uma vez por cada marca que vende.
Google Maps ajuda na distância e navegação, mas a autorização deve vir da marca
ou do concessionário oficial.

Ao adicionar a primeira viatura de uma marca, adicionar o concessionário na mesma
alteração. Ao remover a última viatura, remover também a entrada dessa marca.

## 10. Fotografias

Cada modelo requer uma fotografia local correspondente ao modelo exato:

```text
web/assets/images/vehicles/<marca-modelo>/official.jpg
```

PNG também é aceite quando o `image_path` coincidir.

A imagem deve:

- mostrar claramente o exterior do modelo correto;
- vir preferencialmente da página oficial usada como fonte;
- não ser logótipo, interior, detalhe, conceito, modelo anterior ou outro carro;
- ter resolução útil e ficheiro superior a 5 KB;
- funcionar offline.

Existe também um orçamento de peso: 500 KB por fotografia e 12 MB no total. Os
cartões mostram a imagem com 180 px de altura, por isso um ficheiro de 2 MB envia
ordens de grandeza mais bytes do que o ecrã usa. O orçamento é um `AVISO` no
`make validate` e só faz falhar o `make budgets` — a correção é reamostrar e
recomprimir a mesma fotografia oficial, nunca trocá-la por outra mais leve de
outro modelo ou de outra fonte. Depois de recomprimir, repetir a auditoria visual.

Comandos:

```sh
make update-photos       # captura apenas fotografias ausentes/inválidas
make update-photos-all   # recaptura todas para uma auditoria completa
make prune-images        # arquiva ficheiros que nenhum image_path referencia
```

Estes comandos usam `agent-browser`. Se não estiver disponível, guardar a imagem
oficial por outro browser, atualizar `image_path` e cumprir a mesma auditoria.

A seleção automática é apenas uma proposta. Depois da captura, abrir visualmente
todas as imagens novas/substituídas e comparar marca + modelo com o JSON. O
validador verifica ficheiro e tamanho, não reconhece o automóvel.

## 11. Alterações de fontes e aceitação

Se `make update` reportar fontes alteradas:

1. Não executar imediatamente `make update-accept`.
2. Abrir cada URL alterada.
3. Identificar se mudou preço, variante, especificação, disponibilidade,
   condições, fotografia ou apenas layout/cookies.
4. Atualizar os JSONs e fotografias quando necessário.
5. Executar `make validate && make test`.
6. Resumir as alterações e evidências ao utilizador/revisor.
7. Só depois de revisão humana explícita executar:

```sh
make update-accept
```

Aceitar o fingerprint significa “esta versão foi revista”, não “a página mudou”.
Nunca aceitar alterações de fontes às cegas só para fazer o comando passar.

## 12. Comandos operacionais

```sh
make serve              # serve a aplicação; procura outra porta se 8000 estiver ocupada
make lint               # ruff sobre scripts/ e tests/
make validate           # valida JSON/fotos/schema v3 e recompila; não usa rede
make test               # testes Python e JavaScript
make links              # verifica fontes e concessionários; usa rede
make budgets            # falha se as fotografias excederem o orçamento de peso
make update             # monitoriza fontes, gera propostas, valida schema v3 e testa
make update-accept      # aceita fingerprints após revisão explícita
make update-photos      # captura fotografias em falta e testa
make update-photos-all  # recaptura todas as fotografias e testa
make prune-images       # arquiva imagens não referenciadas e testa
make audit              # lint, valida, frescura, testa e verifica todos os links
make sequential         # update → fotos em falta → auditoria, por esta ordem
```

`make links` verifica as fontes em paralelo, alternando entre domínios para não
disparar HTTP 429, e termina com uma contagem explícita:

```text
LIGAÇÕES: 100 no total, 69 verificadas, 31 não verificadas, 0 quebradas
```

Só as quebradas fazem falhar. As não verificadas responderam 403/429 ou não
responderam a `urllib` e ficam listadas: **essas fontes têm de ser abertas num
browser real** antes de qualquer afirmação sobre o seu preço ou condições. Um
`make links` verde não significa que todas as fontes foram lidas.

`make budgets` fica deliberadamente fora do `make audit`. O peso das fotografias
é um aviso de desempenho, não uma regressão: nunca substituir uma fotografia
oficial correta por uma errada só para respeitar o orçamento.

`make sequential` para no primeiro erro. Não executa `make update-accept`, não
aceita fontes alteradas e não substitui a redescoberta manual do mercado.

Depois de qualquer alteração de dados, executar obrigatoriamente:

```sh
make validate && make test
```

Antes de declarar uma atualização completa concluída, executar:

```sh
make audit
```

Falhas de rede em `make links` não autorizam remover fontes automaticamente.
Repetir, abrir no browser e distinguir indisponibilidade temporária de URL morta.

## 13. Auditoria da aplicação

Depois dos testes automáticos:

1. Abrir `web/index.html` diretamente para confirmar funcionamento offline.
2. Executar `make serve` e abrir o URL indicado para a auditoria normal.
3. Confirmar contagem de modelos/variantes.
4. Pesquisar modelos com acentos, pontuação e pequenas gralhas.
5. Confirmar “Melhor preço/autonomia”, filtros e anos.
6. Abrir cartões de modelos alterados e verificar preço, condições, fotografia,
   autonomia, fonte e concessionário.
7. Confirmar que links oficiais e mapas abrem no destino correto.
8. Verificar consola do browser e ausência de recursos remotos indispensáveis.

## 14. Critério de conclusão

Uma tarefa só está concluída quando:

- o radar de mercado e as gamas oficiais relevantes foram revistos;
- inclusões/exclusões estão justificadas;
- dados alterados têm fontes oficiais e datas atuais;
- preços/campanhas não escondem condições;
- todas as marcas ativas têm exatamente um concessionário preferencial;
- fotografias novas/substituídas foram vistas e correspondem aos modelos;
- `web/assets/js/car_data.js` foi regenerado, nunca editado à mão;
- `make validate && make test` passou;
- numa atualização completa, `make audit` passou ou uma falha externa ficou
  claramente documentada;
- o relatório final indica modelos adicionados/removidos, preços alterados,
  fontes que mudaram, fotografias substituídas e qualquer ponto pendente.

## 15. Limites honestos da automação

O projeto é reproduzível e independente do fornecedor do agente, mas não é um
robot de publicação sem supervisão:

- fingerprints detetam mudanças, não interpretam páginas;
- a descoberta de mercado exige pesquisa atual;
- disponibilidade M1 e campanhas exigem julgamento documental;
- proximidade do concessionário exige comparação geográfica;
- correspondência da fotografia exige inspeção visual;
- `make update-accept` exige revisão humana explícita.

“Autossustentável” neste projeto significa que um agente novo consegue continuar
o trabalho apenas com este repositório e fontes atuais, com validações e gates
claros — não que possa inventar ou publicar dados sem revisão.

## 16. Higiene do repositório público

Antes de preparar um commit público:

1. Executar `git add --dry-run .` e rever a lista completa.
2. Nunca publicar `data/documents/`, que pode conter propostas, emails e dados
   pessoais; as provas publicáveis permanecem registadas por URL nos JSON.
3. Não publicar `archive/`, `dogfood-output/`, `graphify-out/`, ambientes virtuais
   ou outros artefactos locais reproduzíveis.
4. Executar `make prune-images` para manter na pasta ativa apenas a fotografia
   referenciada por cada modelo.
5. Procurar segredos, tokens, chaves e caminhos absolutos antes do primeiro push.
6. Confirmar `make validate && make test`.

A licença MIT cobre apenas código e documentação originais. Fotografias, marcas,
ícones e outros recursos de terceiros obedecem a `ASSET_NOTICE.md` e às licenças
dos respetivos titulares.
