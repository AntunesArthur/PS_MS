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
        'pegged_orders_id': set()
    }

def insert_into_book(book, order):
    side = order['side']
    price = order['price']

    if price not in book[side]:
        book[side][price] = deque()
    book[side][price].append(order)

    book['orders_by_id'][order['id']] = order

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
    insert_into_book(book, book_order)

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
        insert_into_book(book, book_order)

    return book_order, trades

def cancel_order(book, order_id):
    order = book['orders_by_id'][order_id]
    remove_from_book(book, order)

def remove_from_book(book, order): #funcao responsavel por remover qualquer order do book, sera auxiliar para cancel e amend
    side = order['side']
    price = order['price']
    #remove exatamente a order que esta no book[side][price]
    book[side][price].remove(order)
    #se apos a remocao nos nao temos mais cota, deletamos
    if len(book[side][price]) == 0: del book[side][price]
    #sempre deletar do 'orders_by_id' para nao ficar la e acabar sendo solicitado novamente dando ValueError
    #pois ja foi removido do book[side]
    del book['orders_by_id'][order['id']]

def amend_order(book, order_id, new_price=None, new_qty=None):
    order = book['orders_by_id'][order_id]

    price_change = (new_price is not None) and (new_price != order['price'])
    #a mudanca so causa perda de prioridade caso a alteracao seja no preco, se apenas a quantidade esta sendo alterada
    #a priroidade continua a mesma
    if price_change:
        remove_from_book(book, order)
        order['price'] = new_price
        if new_qty is not None:
            order['qty'] = new_qty
            order['remaining_qty'] = new_qty
        order['sequence'] = next(_sequence_counter)
        insert_into_book(book, order)

    if not price_change:
        if new_qty is not None:
            order['qty'] = new_qty
            order['remaining_qty'] = new_qty

def pegged_orders(book, side, peg_reference, qty):
    if peg_reference == 'bid':
        if len(book['buy']) == 0:
            return "Nao ha acoes de referencia ainda"
        best_price, _ = book['buy'].peekitem(-1)
    else:  # peg_reference == 'offer'
        if len(book['sell']) == 0:
            return "Nao ha acoes de referencia ainda"
        best_price, _ = book['sell'].peekitem(0)

    book_order, trades = match_order(book, side, best_price, qty)

    book_order['order_type'] = 'peg'
    book_order['peg_reference'] = peg_reference

    if book_order['remaining_qty'] > 0:
        book['pegged_orders_id'].add(book_order['id'])

    return book_order, trades

def refresh_pegged_orders(book):
    for order_id in list(book['pegged_orders_id']):
        order = book['orders_by_id'][order_id]
        old_price = order['price']
        old_sequence = order['sequence']

        #remove temporariamente para ordem nao contar como sua propria referencia
        remove_from_book(book, order)

        ref_side = 'buy' if order['peg_reference'] == 'bid' else 'sell'

        if len(book[ref_side]) == 0:
            #sem nenhuma ordem de ref sobrando, mantem o preco anterior
            new_price = old_price
        elif order['peg_reference'] == 'bid':
            new_price, _ = book['buy'].peekitem(-1)
        else:
            new_price, _ = book['sell'].peekitem(0)

        order['price'] = new_price
        #so perde posicao na fila se o preco relamnete mudou

        order['sequence'] = old_sequence if new_price == old_price else next(_sequence_counter)

        insert_into_book(book, order)
