# PS_MS
# Matching Engine
Implementação de uma Matching Engine simplificada para um único ativo, suportando ordens limit, market e pegged, com cancelamento, alteração (amend) e visualização de livro-ofertas

## Como rodar
Dependência externa: `sortedcontainers`.
```bash
pip install sortedcontainers
python input.py
```

Comandos suportados no REPL:
```text
limit <buy|sell> <price> <qty>
market <buy|sell> <qty>
peg <bid|offer> <buy|sell> <qty>
cancel order <id>
amend order <id> [price <novo_preco>] [qty <nova_qty>]
print book
exit
```

## 1. Arquitetura escolhida
O projeto foi feito de forma estrutural, representando o estado inteiro da engine em um único dicionário (book), passado explicitamente para cada função. Essa escolhia prioriza simplicidade e legibilidade pro desafio, em detrimento do encapsulamento que uma abordagem orientada a objetos traria.

O book é composto por
```python
    {
        'buy': SortedDict(), #preco -> deque de ordens naquele preco
        'sell': SortedDict(), #preco -> deque de ordens naquele preco
        'orders_by_id': {}, #id -> ordem (lookup O(1) para cancel/amend)
        'pegged_orders_id': set(), #ids das ordens do tipo peg, para o refresh
    }
```
Por que `SortedDict` de `sortedcontainers`?

O requisito central de uma matching engine é responder rapidamente "qual o melhor preço de compra?" e "qual é o melhor preço de venda?" enquanto insere e retira novos preços. Um dicionário comum não mantém ordenação por chave, o que exigiria uma varredura O(N) toda vez que fosse consultado o melhor preço. `SortedDict` mantém as chaves já ordenadas, com inserção, remoção e acesso ao maior elemento em O(log N), via peekitem(0) e peekitem(-1).

Por que `deque` de `Collections`?

Cada nível de preço no book pode conter múltiplas ordens, a regra de prioridade exige respeitar a ordem de chegada (FIFO). `deque` oferece `append` (inserir no fim) e `popleft()` (remover do início) em O(1), o que é essencial para manter essa fila sem custo de reorganização a cada operação.

Por que `Decimal` de `decimals`?

Preços e quantidades usam `Decimal` em vez de `float` para evitar erros de arredondamento binário (ex: 0.1 + 0.2 = 0.3000000001 em `float`), que são inaceitáveis para valores financeiros

Por que `uuid` para os ids das ordens?

Cada ordem recebe um identificador via `uuid.uuid(4)`, garantindo unicidade sem depender de coordenação externa. Foi mantido por ser a abordagem mais robusta e convencional para identificação.

Porque um contador de `sequence` separado do `id`?

Além do `id`, cada ordem recebe um número `sequence` (via `itertools.count()`), usado como critério de desempate para a prioridade FIFO dentro de um mesmo nível de preço. Como o `uuid` é aleatório, ele não pode ser usado como critério de ordem de chegada; o contador garante isso.

Índices auxiliares: `orders_by_id` e `pegged_orders_id`
Sem um índice direto, cancelar ou alterar uma ordem exigiria uma varredura por todos os preços do book até encontrar, sendo O(N).
`orders_by_id` mapeia diretamente `id -> ordem`, tornando cancel e amend O(1) (mais o custo de manipualr a deque em si)
`pegged_orders_id` mantém um `set` com os ids das ordens do tipo peg, permitindo que `refresh_pegged_orders` saiba quais ordens revisar sem varrer o book inteiro.

## 2. Fluxo de funcionamento
- `insert_into_book` e `remove_from_book` são as duas únicas funções que tocam diretamente na estrutura do book (deques e `SortedDict`) e no índice `orders_by_id`. Todas as outras operações são construídas em cima dessas duas, evitando duplicar a lógica de manutenção de índice em múltiplos lugares

- `match_order` centraliza a lógica de casamento de orders dentro do book, ela é responsável para que a cada operação haja verificação se existe match e retorna em caso positivo.

- `place_market_order` implementa uma lógica de casamento para orders do tipo 'market', visto que essas não possuem preço e buscam ser consumidas o mais rápido possível. Caso não haja matching imediato ou apenas matching parcial para orders do tipo 'market' a sobra é descartada imediatamente.

- `refresh_pegged_orders` é chamada no final de toda operação que pode alterar o melhor preço do book, é diretamente responsável para que orders do tipo 'pegged' acompanhem o preço sempre que algo novo for adicionado/modificaod no book.

- `format_book` é uma função somente de leitura, sem alterações, usada tanto pelo comando `print book` quanto disponível para testes.

## 3. Decisões de design
**Trades não são agregados**. Assim como no exemplo do enunciado, os trades não são agregados. Ou seja, quando uma ordem consome múltiplas ordens do book o retorno final mostra exatamente quais ordens foram consumidas e a quantidade consumida de cada uma. Essa decisão foi tomada para preservar a rastreabilidade das operações.

**Amend perde prioridade apenas quando o preço muda**. Alterar somente a quantidade (para mais ou para menos) de uma operação mantém a sua posição na fila, já alterar o preço sempre reposiciona a operação no fim da fila, conforme foi exemplificado no enunciado. 

**Alteração de quantidade via amend substitui o valor restante diretamente**. Quando `qty` é alterada via amend, tanto `qty` quanto `remaining_qty` são atualizados para o novo valor. Ou seja, o amend define "quanto ainda falta preencher", não um ajuste sobre a quantidade original.

**Ordens pegged tentam casar imediatamente ao nascer**. Embora o enunciado descreva pegged orders apenas como ordens que acompanham um preço de referência, foi decidido que, ao serem criadas, elas tentam casar com o book oposto antes de entrar no book, do contrário, poderiam ficar flutuando até outra operação ser feita mesmo já tendo match ao nascerem. 

**Ordens pegged nunca usam a si mesma como referência de preço**. Ao recalcular o preço de uma ordem pegged, ela é temporariamente removida do book antes de consultar o melhor preço do lado de referência. Sem essa remoção, uma pegged que fosse a única ordem restante em um nível de preço se veria a si mesma como "o melhor preço", travando seu próprio acompanhamento.

**Pegged sem referência disponível não gera erro, apenas uma mensagem**. Se não existir nenhuma ordem no lado que a pegged deveria seguir (ex: peg to bid sem nenhuma ordem de compra no book), a criação é recusada com uma mensagem informativa.

**Se a referência de uma pegged desapareecer depois de criada, o preço é congelado no último valor conhecido**. 

**Bug encontrado e corrigido durante testes**. Ordens do book totalmente consumidas durante o matching eram removidas da fila (`deque`) e, quando aplicável, do `SortedDict` de preços, mas não eram removidas de `orders_by_id` nem de `pegged_orders_id`. Isso deixava entradas "fantasma" nesses índices auxiliares, causando um `KeyError` ao tentar reposicionar via `refresh_pegged_orders` uma ordem pegged que já havia sido totalmente consumida em um matching anterior. A correção garante que, sempre que uma ordem é totalmente consumida, ela é removida de todos os índices, não apenas da estrutura do book.

**Ordens do tipo peg são marcadas com `(peg)` para diferenciação visual.


