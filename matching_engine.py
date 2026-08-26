from sortedcontainers import SortedDict
from collections import deque
from decimal import Decimal
from itertools import count

def create_book():
    #Retorna apenas a estrutura vazia do book, que utilizaremos para auxiliar nos trades
    return {
        'buy': SortedDict(),
        'sell': SortedDict(),
        'orders_by_id': {},
    }
    