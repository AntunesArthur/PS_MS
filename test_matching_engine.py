from decimal import Decimal

from matching_engine import (
    create_book,
    place_limit_order,
    place_market_order,
    match_order,
    cancel_order,
    amend_order,
    pegged_orders,
    refresh_pegged_orders,
)


# ---------------------------------------------------------------------------
# Matching básico (reproduzindo o exemplo do enunciado)
# ---------------------------------------------------------------------------

def test_market_buy_consome_multiplas_ordens_no_mesmo_preco():
    book = create_book()
    place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))
    place_limit_order(book, 'sell', Decimal('20'), Decimal('100'))
    place_limit_order(book, 'sell', Decimal('20'), Decimal('200'))

    trades = place_market_order(book, 'buy', Decimal('150'))

    # consome os 100 da primeira ordem, depois 50 da segunda
    assert trades == [
        {'price': Decimal('20'), 'qty': Decimal('100')},
        {'price': Decimal('20'), 'qty': Decimal('50')},
    ]


def test_market_buy_preenche_so_o_disponivel_e_descarta_resto():
    book = create_book()
    place_limit_order(book, 'sell', Decimal('20'), Decimal('150'))

    trades = place_market_order(book, 'buy', Decimal('200'))

    # so tinha 150 disponivel; os outros 50 nao sao preenchidos nem ficam no book
    assert trades == [{'price': Decimal('20'), 'qty': Decimal('150')}]
    assert len(book['sell']) == 0


def test_market_sell_casa_com_book_de_compra():
    book = create_book()
    place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))

    trades = place_market_order(book, 'sell', Decimal('200'))

    assert trades == [{'price': Decimal('10'), 'qty': Decimal('100')}]


# ---------------------------------------------------------------------------
# Prioridade FIFO dentro do mesmo nível de preço
# ---------------------------------------------------------------------------

def test_fifo_respeita_ordem_de_chegada_no_mesmo_preco():
    book = create_book()
    primeira = place_limit_order(book, 'sell', Decimal('20'), Decimal('50'))
    segunda = place_limit_order(book, 'sell', Decimal('20'), Decimal('50'))

    place_market_order(book, 'buy', Decimal('50'))

    # a primeira ordem deve ter sido totalmente consumida e removida do indice
    assert primeira['id'] not in book['orders_by_id']
    # a segunda continua no book, intacta
    assert segunda['id'] in book['orders_by_id']
    assert book['orders_by_id'][segunda['id']]['remaining_qty'] == Decimal('50')


# ---------------------------------------------------------------------------
# Fill parcial
# ---------------------------------------------------------------------------

def test_fill_parcial_mantem_sobra_da_ordem_do_book():
    book = create_book()
    place_limit_order(book, 'sell', Decimal('20'), Decimal('200'))

    place_market_order(book, 'buy', Decimal('50'))

    best_price, queue = book['sell'].peekitem(0)
    assert best_price == Decimal('20')
    assert queue[0]['remaining_qty'] == Decimal('150')


def test_limit_order_que_cruza_parcialmente_o_book_fica_com_sobra_no_book():
    book = create_book()
    place_limit_order(book, 'sell', Decimal('20'), Decimal('50'))

    book_order, trades = match_order(book, 'buy', Decimal('25'), Decimal('80'))

    assert trades == [{'price': Decimal('20'), 'qty': Decimal('50')}]
    assert book_order['remaining_qty'] == Decimal('30')
    # a sobra deve estar alocada no book de compra, ao preco da ordem original (25)
    best_price, queue = book['buy'].peekitem(-1)
    assert best_price == Decimal('25')
    assert queue[0]['id'] == book_order['id']


def test_limit_order_que_nao_cruza_vai_inteira_para_o_book():
    book = create_book()
    place_limit_order(book, 'sell', Decimal('20'), Decimal('50'))

    book_order, trades = match_order(book, 'buy', Decimal('15'), Decimal('30'))

    assert trades == []
    assert book_order['remaining_qty'] == Decimal('30')
    best_price, _ = book['buy'].peekitem(-1)
    assert best_price == Decimal('15')


# ---------------------------------------------------------------------------
# Cancelamento
# ---------------------------------------------------------------------------

def test_cancel_remove_ordem_do_book_e_do_indice():
    book = create_book()
    order = place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))

    cancel_order(book, order['id'])

    assert order['id'] not in book['orders_by_id']
    assert len(book['buy']) == 0


def test_cancel_de_uma_entre_duas_ordens_no_mesmo_preco_preserva_a_outra():
    book = create_book()
    order1 = place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))
    order2 = place_limit_order(book, 'buy', Decimal('10'), Decimal('50'))

    cancel_order(book, order1['id'])

    best_price, queue = book['buy'].peekitem(-1)
    assert best_price == Decimal('10')
    assert len(queue) == 1
    assert queue[0]['id'] == order2['id']


# ---------------------------------------------------------------------------
# Amend
# ---------------------------------------------------------------------------

def test_amend_qty_mantem_prioridade_na_fila():
    book = create_book()
    order = place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))
    sequence_antes = order['sequence']

    amend_order(book, order['id'], new_qty=Decimal('60'))

    assert order['qty'] == Decimal('60')
    assert order['remaining_qty'] == Decimal('60')
    assert order['sequence'] == sequence_antes  # nao perdeu prioridade


def test_amend_price_perde_prioridade_e_migra_de_nivel():
    book = create_book()
    order = place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))
    sequence_antes = order['sequence']

    amend_order(book, order['id'], new_price=Decimal('9.98'))

    assert order['price'] == Decimal('9.98')
    assert order['sequence'] != sequence_antes  # perdeu prioridade
    assert Decimal('10') not in book['buy']
    best_price, queue = book['buy'].peekitem(-1)
    assert best_price == Decimal('9.98')
    assert queue[0]['id'] == order['id']


# ---------------------------------------------------------------------------
# Pegged orders
# ---------------------------------------------------------------------------

def test_pegged_nasce_com_preco_igual_ao_bid_atual():
    book = create_book()
    place_limit_order(book, 'buy', Decimal('10'), Decimal('200'))

    book_order, trades = pegged_orders(book, 'buy', 'bid', Decimal('150'))

    assert trades == []
    assert book_order['price'] == Decimal('10')
    assert book_order['id'] in book['pegged_orders_id']


def test_pegged_sem_referencia_disponivel_retorna_mensagem():
    book = create_book()

    resultado = pegged_orders(book, 'buy', 'bid', Decimal('100'))

    assert isinstance(resultado, str)
    assert len(book['orders_by_id']) == 0


def test_pegged_acompanha_novo_melhor_preco():
    book = create_book()
    place_limit_order(book, 'buy', Decimal('10'), Decimal('200'))
    book_order, _ = pegged_orders(book, 'buy', 'bid', Decimal('150'))

    place_limit_order(book, 'buy', Decimal('10.1'), Decimal('300'))
    refresh_pegged_orders(book)

    atualizado = book['orders_by_id'][book_order['id']]
    assert atualizado['price'] == Decimal('10.1')


def test_pegged_nao_usa_a_si_mesma_como_referencia():
    book = create_book()
    order_base = place_limit_order(book, 'buy', Decimal('10'), Decimal('50'))
    place_limit_order(book, 'buy', Decimal('9.5'), Decimal('50'))
    book_order, _ = pegged_orders(book, 'buy', 'bid', Decimal('30'))

    # cancela a ordem que dava referencia ao preco 10, deixando so a pegged nesse nivel
    cancel_order(book, order_base['id'])

    atualizado = book['orders_by_id'][book_order['id']]
    assert atualizado['price'] == Decimal('9.5')


def test_pegged_totalmente_executada_nao_entra_no_indice():
    book = create_book()
    place_limit_order(book, 'buy', Decimal('10'), Decimal('50'))
    place_limit_order(book, 'sell', Decimal('12'), Decimal('50'))

    book_order, trades = pegged_orders(book, 'sell', 'bid', Decimal('30'))

    assert trades == [{'price': Decimal('10'), 'qty': Decimal('30')}]
    assert book_order['remaining_qty'] == Decimal('0')
    assert book_order['id'] not in book['pegged_orders_id']


# ---------------------------------------------------------------------------
# Regressão do bug de indices fantasma (orders_by_id / pegged_orders_id)
# ---------------------------------------------------------------------------

def test_ordem_totalmente_consumida_eh_removida_dos_indices_auxiliares():
    book = create_book()
    order = place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))

    place_market_order(book, 'sell', Decimal('100'))

    assert order['id'] not in book['orders_by_id']


def test_pegged_consumida_por_matching_nao_deixa_fantasma_para_refresh():
    book = create_book()
    place_limit_order(book, 'buy', Decimal('10'), Decimal('100'))
    pegged, _ = pegged_orders(book, 'buy', 'bid', Decimal('150'))

    # consome a limit original e a pegged inteira em uma unica ordem de venda
    match_order(book, 'sell', Decimal('10'), Decimal('300'))

    # nao deveria lancar KeyError, e o indice de pegged deve estar limpo
    assert pegged['id'] not in book['pegged_orders_id']
    assert pegged['id'] not in book['orders_by_id']