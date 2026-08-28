from sortedcontainers import SortedDict
from collections import deque
from decimal import Decimal
from itertools import count
import uuid 

_sequence_counter = count()

def create_book():
    #Retorna apenas a estrutura vazia do book, que utilizaremos para auxiliar nos trades
    return {
        'buy': SortedDict(),
        'sell': SortedDict(),
        'orders_by_id': {},
    }
def place_limit_order(book, side, price, qty):
    #book_order utilizado para alocarmos as novas infos de toda nova ordem que chegar
    book_order = {
        'id': str(uuid.uuid4()),
                'side': side,
                'order_type': 'limit',
                'price': price,
                'qty': qty,
                'remaining_qty': qty,
                'sequence': next(_sequence_counter)
    }
    #criamos uma fila dentro do nosso dic para respeitar a ordem das solicitacoes de compra ou venda
    if price not in book[side]:
        book[side][price] = deque()
    book[side][price].append(book_order)

    book['orders_by_id'][book_order['id']] = book_order

    return book_order

def place_market_order(book, side, qty):
    #criamos um book_order para alocarmos as novas infos de toda ordem nova, assim como na funcao
    #place_limit_order
    book_order = {
        'id': str(uuid.uuid4()),
        'side': side,
        'price': None,
        'order_type': 'market',
        'qty': qty,
        'remaining_qty': qty,
        'sequence': next(_sequence_counter),
    }
    #lista para guardar os trades que fizermos
    trades = []

    opposite_side = 'sell' if side == 'buy' else 'buy'

    #nos so mantemos as compras/vendas em market_order enquanto nao tivermos vendido/comprado todas
    #as acoes solicitadas e que tenham acoes suficientes pra isso, isto e 'len(book[side]) > 0'
    while book_order['remaining_qty'] > 0 and len(book[opposite_side]) > 0:
        #nesse ponto criamos uma tupla com o melhor preco de compra/venda e as informacoes da exata
        #compra ou venda que esta sendo feito, a queue  
        if side == 'buy':
            best_price, queue = book['sell'].peekitem(0)
        if side == 'sell':
            best_price, queue = book['buy'].peekitem(-1)

        #da nossa queue pegamos sempre o primeiro (FIFO)
        resting_order = queue[0]

        #as 4 linhas abaixos sao responsaveis por computar a quantidade de trading feita, salvar eleas
        #na lista e tambem atualizar a quantidade que falta para comprarmos/vendermos do market
        #e a quantidade que talvez tenha sobrado da nossa queue
        traded_qty = min(book_order['remaining_qty'], resting_order['remaining_qty'])

        trades.append({'price': best_price, 'qty': traded_qty})

        book_order['remaining_qty'] -= traded_qty

        resting_order['remaining_qty'] -= traded_qty

        if resting_order['remaining_qty'] == 0:
            #se vendemos todas as cotas de uma ordem, descartamos ela pois seu papel ja foi cumprido
            queue.popleft()
            if len(queue) == 0 and side == 'buy':
                del book['sell'][best_price]
            elif len(queue) == 0 and side == 'sell':
                del book['buy'][best_price]

    return trades

def match_order(book, side, price, qty):
    book_order = {
        'id': str(uuid.uuid4()),
        'side': side,
        'price': price,
        'order_type': 'limit',
        'qty': qty,
        'remaining_qty': qty,
        'sequence': next(_sequence_counter)
    }

    trades = []
    opposite_side = "sell" if side == 'buy' else 'buy'

    while len(book[opposite_side]) != 0 and book_order['remaining_qty'] > 0:
        if side == 'buy':
            best_price, queue = book[opposite_side].peekitem(0)
        if side == 'sell':
            best_price, queue = book[opposite_side].peekitem(-1)
        #antes de prosseguir com qualquer decisao observamos os precos,
        #se estamos querendo comprar e o melhor preco de venda e maior do que o preco que queremos pagar
        #isso implica que no momento nao ha 
        if side == 'buy' and best_price > price: break
        if side == 'sell' and best_price < price: break

        resting_order = queue[0]

        traded_qty = min(book_order['remaining_qty'], resting_order['remaining_qty'])

        trades.append({'price': best_price, 'qty': traded_qty})

        book_order['remaining_qty'] -= traded_qty

        resting_order['remaining_qty'] -= traded_qty

        if resting_order['remaining_qty'] == 0:
            queue.popleft()
            if len(queue) == 0:
                del book[opposite_side][best_price]

    if book_order['remaining_qty'] > 0:
        place_limit_order(book, side, price, book_order['remaining_qty'])

    return trades

def cancel_order(book, order_id):
    #buscando diretamente o id do cara que queremos apagar
    order = book['orders_by_id'][order_id]

    #tendo ela na mao, conseguimos inferir imediatamente onde ele esta e a qual preco esta cotado
    side = order['side']
    price = order['price']
    #remove a primeira ocorrencia que for igual ao valor passado (order), ou seja, ela remove
    #exatamente o dic que for igual ao da ocorrencia que estamos procurando, sendo assim capaz de remover
    #percorrendo ele
    book[side][price].remove(order)

    #se apos a remocao nos nao temos mais cotas, entao deletamos
    if len(book[side][price]) == 0: del book[side][price]

    #sempre deletar do 'orders_by_id', para nao ficar la e acabar sendo solicitado novamente e dando ValueError
    #pois ja foi removido do book[side]
    del book['orders_by_id'][order_id]
