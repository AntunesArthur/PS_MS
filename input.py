from decimal import Decimal, InvalidOperation

from matching_engine import (
    create_book,
    place_limit_order,
    place_market_order,
    match_order,
    cancel_order,
    amend_order,
    pegged_orders,
    format_book,
)


def print_trades(trades):
    for trade in trades:
        print(f"Trade, price: {trade['price']}, qty: {trade['qty']}")


def handle_limit(book, tokens):
    # limit <buy|sell> <price> <qty>
    if len(tokens) != 4:
        print("Erro: formato esperado e 'limit <buy|sell> <price> <qty>'")
        return

    side, price_str, qty_str = tokens[1], tokens[2], tokens[3]
    if side not in ('buy', 'sell'):
        print(f"Erro: side invalido '{side}'")
        return

    try:
        price = Decimal(price_str)
        qty = Decimal(qty_str)
    except InvalidOperation:
        print("Erro: valores numericos invalidos")
        return

    if qty <= 0 or price <= 0:
        print("Erro: preco e quantidade devem ser positivos")
        return

    # match_order ja cuida de tentar casar e inserir o que sobrar
    book_order, trades = match_order(book, side, price, qty)
    print(f"Order created: {side} {qty} @ {price} {book_order['id']}")
    print_trades(trades)


def handle_market(book, tokens):
    # market <buy|sell> <qty>
    if len(tokens) != 3:
        print("Erro: formato esperado e 'market <buy|sell> <qty>'")
        return

    side, qty_str = tokens[1], tokens[2]
    if side not in ('buy', 'sell'):
        print(f"Erro: side invalido '{side}'")
        return

    try:
        qty = Decimal(qty_str)
    except InvalidOperation:
        print("Erro: quantidade invalida")
        return

    if qty <= 0:
        print("Erro: quantidade deve ser positiva")
        return

    trades = place_market_order(book, side, qty)
    print_trades(trades)


def handle_cancel(book, tokens):
    # cancel order <id>
    if len(tokens) != 3 or tokens[1] != 'order':
        print("Erro: formato esperado e 'cancel order <id>'")
        return

    order_id = tokens[2]
    if order_id not in book['orders_by_id']:
        print(f"Erro: ordem '{order_id}' nao encontrada")
        return

    cancel_order(book, order_id)
    print("Order cancelled")


def handle_amend(book, tokens):
    # amend order <id> price <new_price>
    # amend order <id> qty <new_qty>
    # amend order <id> price <new_price> qty <new_qty>
    if len(tokens) < 5 or tokens[1] != 'order':
        print("Erro: formato esperado e 'amend order <id> [price <val>] [qty <val>]'")
        return

    order_id = tokens[2]
    if order_id not in book['orders_by_id']:
        print(f"Erro: ordem '{order_id}' nao encontrada")
        return

    new_price = None
    new_qty = None
    rest = tokens[3:]

    try:
        i = 0
        while i < len(rest):
            if rest[i] == 'price':
                new_price = Decimal(rest[i + 1])
                i += 2
            elif rest[i] == 'qty':
                new_qty = Decimal(rest[i + 1])
                i += 2
            else:
                print(f"Erro: campo desconhecido '{rest[i]}'")
                return
    except (InvalidOperation, IndexError):
        print("Erro: valores invalidos para amend")
        return

    if new_price is None and new_qty is None:
        print("Erro: informe price e/ou qty para alterar")
        return

    amend_order(book, order_id, new_price=new_price, new_qty=new_qty)
    print("Order amended")


def handle_peg(book, tokens):
    # peg <bid|offer> <buy|sell> <qty>
    if len(tokens) != 4:
        print("Erro: formato esperado e 'peg <bid|offer> <buy|sell> <qty>'")
        return

    peg_reference, side, qty_str = tokens[1], tokens[2], tokens[3]
    if peg_reference not in ('bid', 'offer'):
        print(f"Erro: referencia invalida '{peg_reference}'")
        return
    if side not in ('buy', 'sell'):
        print(f"Erro: side invalido '{side}'")
        return

    try:
        qty = Decimal(qty_str)
    except InvalidOperation:
        print("Erro: quantidade invalida")
        return

    result = pegged_orders(book, side, peg_reference, qty)
    if isinstance(result, str):
        # pegged_orders devolve uma string quando nao ha referencia disponivel
        print(result)
        return

    book_order, trades = result
    print(f"Order created: peg {peg_reference} {side} {qty} {book_order['id']}")
    print_trades(trades)


def handle_print_book(book, tokens):
    print(format_book(book))


COMMANDS = {
    'limit': handle_limit,
    'market': handle_market,
    'cancel': handle_cancel,
    'amend': handle_amend,
    'peg': handle_peg,
    'print': handle_print_book,
}


def main():
    book = create_book()
    print("Matching engine iniciada. Digite 'exit' para sair.")

    while True:
        try:
            line = input(">>> ").strip()
        except EOFError:
            break

        if not line:
            continue
        if line == 'exit':
            break

        tokens = line.split()
        command = tokens[0]

        handler = COMMANDS.get(command)
        if handler is None:
            print(f"Erro: comando desconhecido '{command}'")
            continue

        handler(book, tokens)


if __name__ == "__main__":
    main()