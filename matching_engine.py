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
    book_order = {
        'id': str(uuid.uuid4()),
                'side': side,
                'order_type': 'limit',
                'price': price,
                'qty': qty,
                'remaining_qty': qty,
                'sequence': next(_sequence_counter)
    }
    if price not in book[side]:
        book[side][price] = deque()
    book[side][price].append(book_order)

    book['orders_by_id'][book_order['id']] = book_order

    return book_order


