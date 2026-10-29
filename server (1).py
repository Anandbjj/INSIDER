#!/usr/bin/env python3
import json
import os
import random
import string
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', '8000'))
ROUND_SECONDS = 75
BETWEEN_SECONDS = 25
TOTAL_ROUNDS = 6
MIN_PLAYERS = 3
MAX_PLAYERS = 8
STARTING_CASH = 10_000.0

PUBLIC_DIR = Path(__file__).parent / 'public'

STOCKS = {
    'TECH': {'name': 'NovaTech', 'ticker': 'NOVA', 'price': 100.0, 'icon': '💻'},
    'OIL': {'name': 'Titan Oil', 'ticker': 'TITN', 'price': 80.0, 'icon': '🛢️'},
    'MEME': {'name': 'MemeCo', 'ticker': 'MEME', 'price': 50.0, 'icon': '🚀'},
}

NEWS = [
    {'title': 'NovaTech beats earnings expectations', 'text': 'NovaTech reports a surprise jump in quarterly profit.', 'effects': {'TECH': 0.14, 'OIL': 0.0, 'MEME': 0.01}, 'tag': 'earnings'},
    {'title': 'NovaTech CEO arrested', 'text': 'The CEO is arrested as investigators launch a fraud probe.', 'effects': {'TECH': -0.20, 'OIL': 0.0, 'MEME': -0.01}, 'tag': 'shock'},
    {'title': 'Oil pipeline explodes', 'text': 'A major Titan Oil pipeline is shut down after an explosion.', 'effects': {'TECH': -0.01, 'OIL': -0.22, 'MEME': 0.02}, 'tag': 'shock'},
    {'title': 'Oil output hits a record', 'text': 'Titan Oil announces record production and stronger guidance.', 'effects': {'TECH': 0.0, 'OIL': 0.15, 'MEME': 0.01}, 'tag': 'earnings'},
    {'title': 'MemeCo goes viral on TikTok', 'text': 'A surprise trend sends MemeCo across social media overnight.', 'effects': {'TECH': 0.01, 'OIL': -0.01, 'MEME': 0.28}, 'tag': 'viral'},
    {'title': 'MemeCo gets hit by a short report', 'text': 'An influential research account alleges MemeCo is overvalued.', 'effects': {'TECH': 0.0, 'OIL': 0.01, 'MEME': -0.25}, 'tag': 'shock'},
    {'title': 'Fed signals easier policy', 'text': 'Markets rally after officials signal a softer stance on rates.', 'effects': {'TECH': 0.10, 'OIL': 0.06, 'MEME': 0.12}, 'tag': 'macro'},
    {'title': 'Inflation jumps unexpectedly', 'text': 'Hot inflation data hits risk assets across the market.', 'effects': {'TECH': -0.10, 'OIL': 0.08, 'MEME': -0.14}, 'tag': 'macro'},
    {'title': 'Huge creator buys MemeCo', 'text': 'A celebrity creator publicly reveals a major MemeCo position.', 'effects': {'TECH': 0.01, 'OIL': 0.0, 'MEME': 0.20}, 'tag': 'viral'},
    {'title': 'Titan Oil faces a regulatory fine', 'text': 'Regulators announce a major environmental penalty.', 'effects': {'TECH': 0.0, 'OIL': -0.12, 'MEME': 0.01}, 'tag': 'regulation'},
    {'title': 'NovaTech lands a massive government contract', 'text': 'NovaTech wins a multi-year technology contract.', 'effects': {'TECH': 0.18, 'OIL': 0.0, 'MEME': 0.02}, 'tag': 'contract'},
    {'title': 'Market-wide risk-off day', 'text': 'A surprise geopolitical headline pushes investors toward safety.', 'effects': {'TECH': -0.09, 'OIL': -0.06, 'MEME': -0.16}, 'tag': 'macro'},
]

rooms = {}
rooms_lock = threading.RLock()


def money(v):
    return round(float(v), 2)


def generate_code():
    while True:
        code = ''.join(random.choice(string.ascii_uppercase) for _ in range(4))
        if code not in rooms:
            return code


def portfolio_value(player, prices):
    total = player['cash']
    for symbol in STOCKS:
        total += player['holdings'][symbol] * prices[symbol]
        total -= player['shorts'][symbol] * prices[symbol]
    return money(total)


def starting_public_player(name, color_index):
    return {
        'name': name,
        'cash': STARTING_CASH,
        'holdings': {s: 0 for s in STOCKS},
        'shorts': {s: 0 for s in STOCKS},
        'role': None,
        'caught': False,
        'color_index': color_index,
        'order_submitted': False,
        'orders': {},
        'history': [STARTING_CASH],
        'trade_log': [],
        'big_moment': None,
    }


def make_room(host_name):
    host_name = host_name.strip()[:18]
    if not host_name:
        raise ValueError('Enter a name.')
    shuffled = list(range(len(NEWS)))
    random.shuffle(shuffled)
    code = generate_code()
    room = {
        'code': code,
        'created_at': time.time(),
        'host_id': None,
        'status': 'lobby',
        'round': 0,
        'round_seconds': ROUND_SECONDS,
        'round_started_at': None,
        'between_started_at': None,
        'prices': {s: STOCKS[s]['price'] for s in STOCKS},
        'previous_prices': {s: STOCKS[s]['price'] for s in STOCKS},
        'news_order': shuffled[:TOTAL_ROUNDS],
        'current_news': None,
        'next_news': None,
        'players': {},
        'regulator_used': False,
        'accusation': None,
        'event_feed': [],
        'resolution': None,
        'game_over': False,
        'lock': threading.RLock(),
    }
    pid = uuid.uuid4().hex[:10]
    room['host_id'] = pid
    room['players'][pid] = starting_public_player(host_name, 0)
    room['players'][pid]['id'] = pid
    rooms[code] = room
    return room, pid


def add_player(room, name):
    if len(room['players']) >= MAX_PLAYERS:
        raise ValueError('Room is full.')
    if room['status'] != 'lobby':
        raise ValueError('This game has already started.')
    clean = name.strip()[:18]
    if not clean:
        raise ValueError('Enter a name.')
    if any(p['name'].casefold() == clean.casefold() for p in room['players'].values()):
        raise ValueError('That name is already taken in this room.')
    pid = uuid.uuid4().hex[:10]
    index = len(room['players'])
    room['players'][pid] = starting_public_player(clean, index)
    room['players'][pid]['id'] = pid
    return pid


def assign_roles(room):
    ids = list(room['players'])
    random.shuffle(ids)
    insider = ids[0]
    regulator = ids[1] if len(ids) > 1 else None
    for pid in ids:
        room['players'][pid]['role'] = 'INSIDER' if pid == insider else ('REGULATOR' if pid == regulator else 'TRADER')


def set_round_news(room, round_number):
    idx = room['news_order'][round_number - 1]
    room['current_news'] = NEWS[idx]
    if round_number < TOTAL_ROUNDS:
        room['next_news'] = NEWS[room['news_order'][round_number]]
    else:
        room['next_news'] = None


def reset_orders(room):
    for p in room['players'].values():
        p['order_submitted'] = False
        p['orders'] = {}


def start_game(room):
    if len(room['players']) < MIN_PLAYERS:
        raise ValueError(f'Need at least {MIN_PLAYERS} players to start.')
    assign_roles(room)
    room['status'] = 'round'
    room['round'] = 1
    room['resolution'] = None
    reset_orders(room)
    set_round_news(room, 1)
    room['round_started_at'] = time.time()
    room['event_feed'].append({'type': 'system', 'text': 'Market opened. Day 1 begins.'})


def effective_order_value(player, symbol):
    o = player['orders'].get(symbol)
    if not o:
        return 0
    qty = max(0, int(o.get('qty', 0)))
    side = o.get('side')
    if side in ('BUY', 'COVER'):
        return qty
    if side in ('SELL', 'SHORT'):
        return -qty
    return 0


def clamp_order(player, symbol, side, qty, price):
    qty = max(0, int(qty))
    if qty <= 0:
        return 0
    if side == 'BUY':
        return min(qty, int(max(0, player['cash']) // price))
    if side == 'SELL':
        return min(qty, player['holdings'][symbol])
    if side == 'SHORT':
        # Conservative notional cap: up to 75% of current net worth at current price.
        max_short = int(max(0, portfolio_value(player, {**{s: price for s in STOCKS}})) * 0.75 // price)
        already = player['shorts'][symbol]
        return min(qty, max(0, max_short - already))
    if side == 'COVER':
        return min(qty, player['shorts'][symbol])
    return 0


def submit_order(room, pid, symbol, side, qty):
    player = room['players'][pid]
    if symbol not in STOCKS:
        raise ValueError('Unknown stock.')
    if side not in ('BUY', 'SELL', 'SHORT', 'COVER'):
        raise ValueError('Invalid order type.')
    if room['status'] != 'round':
        raise ValueError('Trading is closed.')
    price = room['prices'][symbol]
    capped = clamp_order(player, symbol, side, qty, price)
    player['orders'][symbol] = {'side': side, 'qty': capped}
    player['order_submitted'] = any(o['qty'] > 0 for o in player['orders'].values())


def resolve_round(room):
    if room['status'] != 'round':
        return
    old_prices = dict(room['prices'])
    demand = {s: 0 for s in STOCKS}
    for p in room['players'].values():
        for s in STOCKS:
            demand[s] += effective_order_value(p, s)

    effects = room['current_news']['effects']
    new_prices = {}
    for s in STOCKS:
        trader_count = max(1, len(room['players']))
        demand_impact = max(-0.07, min(0.07, demand[s] / (trader_count * 60.0)))
        noise = random.uniform(-0.018, 0.018)
        total = effects[s] + demand_impact + noise
        new_prices[s] = money(max(5.0, old_prices[s] * (1 + total)))

    room['previous_prices'] = old_prices
    room['prices'] = new_prices

    # Fill at the quoted opening price, then value positions at the new close.
    # Otherwise players cannot profit from correctly predicting today's headline.
    for pid, p in room['players'].items():
        before = portfolio_value(p, old_prices)
        for s, order in p['orders'].items():
            side, qty = order['side'], int(order['qty'])
            px = old_prices[s]
            if qty <= 0:
                continue
            if side == 'BUY':
                spend = qty * px
                if spend <= p['cash'] + 1e-9:
                    p['cash'] = money(p['cash'] - spend)
                    p['holdings'][s] += qty
                    p['trade_log'].append({'round': room['round'], 'symbol': s, 'side': side, 'qty': qty, 'price': px})
            elif side == 'SELL':
                qty = min(qty, p['holdings'][s])
                p['cash'] = money(p['cash'] + qty * px)
                p['holdings'][s] -= qty
                p['trade_log'].append({'round': room['round'], 'symbol': s, 'side': side, 'qty': qty, 'price': px})
            elif side == 'SHORT':
                p['cash'] = money(p['cash'] + qty * px)
                p['shorts'][s] += qty
                p['trade_log'].append({'round': room['round'], 'symbol': s, 'side': side, 'qty': qty, 'price': px})
            elif side == 'COVER':
                qty = min(qty, p['shorts'][s])
                p['cash'] = money(p['cash'] - qty * px)
                p['shorts'][s] -= qty
                p['trade_log'].append({'round': room['round'], 'symbol': s, 'side': side, 'qty': qty, 'price': px})
        after = portfolio_value(p, new_prices)
        p['history'].append(after)
        delta = after - before
        if abs(delta) > abs((p.get('big_moment') or {'delta': 0}).get('delta', 0)):
            p['big_moment'] = {'round': room['round'], 'delta': money(delta), 'value': after, 'news': room['current_news']['title']}

    # Public summary event.
    movers = []
    for s in STOCKS:
        pct = (new_prices[s] / old_prices[s] - 1) * 100
        movers.append((abs(pct), s, pct))
    movers.sort(reverse=True)
    room['resolution'] = {
        'round': room['round'],
        'news': room['current_news']['title'],
        'price_changes': {s: money((new_prices[s] / old_prices[s] - 1) * 100) for s in STOCKS},
        'leader': max(room['players'].values(), key=lambda p: portfolio_value(p, new_prices))['name'],
    }
    room['event_feed'].append({'type': 'resolution', 'text': f"Day {room['round']} closed. {room['current_news']['title']}"})
    room['round_started_at'] = None
    room['status'] = 'between'
    room['between_started_at'] = time.time()
    reset_orders(room)


def next_round(room):
    if room['status'] != 'between':
        return
    if room['round'] >= TOTAL_ROUNDS:
        finish_game(room)
        return
    room['round'] += 1
    room['between_started_at'] = None
    room['resolution'] = None
    set_round_news(room, room['round'])
    room['status'] = 'round'
    room['round_started_at'] = time.time()
    room['event_feed'].append({'type': 'system', 'text': f"Market opened. Day {room['round']} begins."})


def accuse(room, regulator_id, target_id):
    reg = room['players'][regulator_id]
    if reg['role'] != 'REGULATOR':
        raise ValueError('Only the Regulator can accuse.')
    if room['regulator_used']:
        raise ValueError('The Regulator already used the accusation.')
    if room['round'] < 4 or room['status'] != 'between':
        raise ValueError('The SEC investigation opens after Day 4 closes.')
    if target_id not in room['players'] or target_id == regulator_id:
        raise ValueError('Invalid target.')
    room['regulator_used'] = True
    target = room['players'][target_id]
    correct = target['role'] == 'INSIDER'
    room['accusation'] = {'by': regulator_id, 'target': target_id, 'correct': correct, 'target_name': target['name']}
    if correct:
        # The caught Insider loses everything; regulator gets a bonus.
        target['cash'] = 0
        for s in STOCKS:
            target['holdings'][s] = 0
            target['shorts'][s] = 0
        target['caught'] = True
        reg['cash'] = money(reg['cash'] + 3000)
        room['event_feed'].append({'type': 'alert', 'text': f"SEC: {target['name']} was caught insider trading. Regulator receives $3,000."})
    else:
        reg['cash'] = money(max(0, reg['cash'] - 2000))
        room['event_feed'].append({'type': 'alert', 'text': f"SEC: accusation against {target['name']} was wrong. Regulator loses $2,000."})
    for p in room['players'].values():
        p['history'][-1] = portfolio_value(p, room['prices'])


def finish_game(room):
    room['status'] = 'finished'
    room['game_over'] = True
    for p in room['players'].values():
        current = portfolio_value(p, room['prices'])
        if not p['history']:
            p['history'].append(current)
        else:
            p['history'][-1] = current
    room['round_started_at'] = None
    room['event_feed'].append({'type': 'system', 'text': 'Final bell. Market closed.'})


def maybe_progress(room):
    with room['lock']:
        if room['status'] == 'round' and room['round_started_at'] is not None:
            elapsed = time.time() - room['round_started_at']
            if elapsed >= room['round_seconds']:
                resolve_round(room)
        if room['status'] == 'between' and room['between_started_at'] is not None:
            if time.time() - room['between_started_at'] >= BETWEEN_SECONDS:
                next_round(room)


def public_state(room, pid):
    maybe_progress(room)
    with room['lock']:
        now = time.time()
        remaining = 0
        if room['status'] == 'round' and room['round_started_at']:
            remaining = max(0, room['round_seconds'] - (now - room['round_started_at']))
        elif room['status'] == 'between' and room['between_started_at']:
            remaining = max(0, BETWEEN_SECONDS - (now - room['between_started_at']))
        me = room['players'][pid]
        players_out = []
        for other_id, p in room['players'].items():
            players_out.append({
                'id': other_id,
                'name': p['name'],
                'portfolio': portfolio_value(p, room['prices']),
                'cash': money(p['cash']) if other_id == pid else None,
                'holdings': dict(p['holdings']) if other_id == pid else None,
                'shorts': dict(p['shorts']) if other_id == pid else None,
                'role': p['role'] if room['status'] == 'finished' or other_id == pid else None,
                'caught': p['caught'],
                'order_submitted': p['order_submitted'] if other_id == pid else None,
                'history': p['history'] if room['status'] == 'finished' else None,
                'big_moment': p['big_moment'] if room['status'] == 'finished' else None,
                'trade_log': p['trade_log'] if room['status'] == 'finished' else None,
            })
        return {
            'room': room['code'],
            'status': room['status'],
            'round': room['round'],
            'total_rounds': TOTAL_ROUNDS,
            'seconds_remaining': round(remaining, 1),
            'prices': dict(room['prices']),
            'previous_prices': dict(room['previous_prices']),
            'stocks': STOCKS,
            'news': room['current_news'] if room['status'] in ('round', 'between', 'finished') else None,
            'next_news_for_me': room['next_news'] if me['role'] == 'INSIDER' and room['status'] == 'round' else None,
            'me': {
                'id': pid,
                'name': me['name'],
                'role': me['role'],
                'cash': money(me['cash']),
                'portfolio': portfolio_value(me, room['prices']),
                'holdings': dict(me['holdings']),
                'shorts': dict(me['shorts']),
                'orders': dict(me['orders']),
                'caught': me['caught'],
                'order_submitted': me['order_submitted'],
                'history': me['history'],
                'big_moment': me['big_moment'],
            },
            'players': players_out,
            'regulator_used': room['regulator_used'],
            'accusation': room['accusation'],
            'resolution': room['resolution'],
            'feed': room['event_feed'][-8:],
            'host_id': room['host_id'],
            'server_time': now,
        }


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _send(self, status, data, content_type='application/json; charset=utf-8'):
        if isinstance(data, str):
            body = data.encode('utf-8')
        else:
            body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/health':
            return self._send(200, {'ok': True})
        if parsed.path == '/api/state':
            q = parse_qs(parsed.query)
            room_code = q.get('room', [''])[0].upper()
            pid = q.get('player', [''])[0]
            with rooms_lock:
                room = rooms.get(room_code)
            if not room or pid not in room['players']:
                return self._send(404, {'error': 'Room/player not found.'})
            return self._send(200, public_state(room, pid))
        if parsed.path.startswith('/api/room/'):
            return self._send(405, {'error': 'Use POST to join/start/create actions.'})
        # static files
        path = parsed.path.lstrip('/') or 'index.html'
        target = (PUBLIC_DIR / path).resolve()
        try:
            target.relative_to(PUBLIC_DIR.resolve())
        except ValueError:
            return self._send(404, 'Not found', 'text/plain; charset=utf-8')
        if not target.exists() or not target.is_file():
            return self._send(404, 'Not found', 'text/plain; charset=utf-8')
        ctype = 'text/plain; charset=utf-8'
        if target.suffix == '.html': ctype = 'text/html; charset=utf-8'
        elif target.suffix == '.js': ctype = 'text/javascript; charset=utf-8'
        elif target.suffix == '.css': ctype = 'text/css; charset=utf-8'
        return self._send(200, target.read_text(encoding='utf-8'), ctype)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', '0'))
        if length < 0 or length > 4096:
            return self._send(413, {'error': 'Request too large.'})
        try:
            payload = json.loads(self.rfile.read(length) or '{}')
        except Exception:
            return self._send(400, {'error': 'Invalid JSON.'})

        try:
            if parsed.path == '/api/create':
                name = str(payload.get('name', ''))
                with rooms_lock:
                    room, pid = make_room(name)
                return self._send(200, {'room': room['code'], 'player': pid})

            if parsed.path == '/api/join':
                room_code = str(payload.get('room', '')).upper().strip()
                name = str(payload.get('name', ''))
                with rooms_lock:
                    room = rooms.get(room_code)
                if not room:
                    raise ValueError('Room not found.')
                with room['lock']:
                    pid = add_player(room, name)
                return self._send(200, {'room': room_code, 'player': pid})

            if parsed.path == '/api/action':
                room_code = str(payload.get('room', '')).upper().strip()
                pid = str(payload.get('player', ''))
                action = payload.get('action')
                with rooms_lock:
                    room = rooms.get(room_code)
                if not room or pid not in room['players']:
                    raise ValueError('Room/player not found.')
                with room['lock']:
                    maybe_progress(room)
                    if action == 'start':
                        if pid != room['host_id']:
                            raise ValueError('Only the host can start.')
                        start_game(room)
                    elif action == 'order':
                        submit_order(room, pid, str(payload.get('symbol')), str(payload.get('side')), int(payload.get('qty', 0)))
                    elif action == 'next_round':
                        if pid != room['host_id']:
                            raise ValueError('Only the host can advance.')
                        next_round(room)
                    elif action == 'accuse':
                        accuse(room, pid, str(payload.get('target')))
                    elif action == 'force_resolve':
                        if pid != room['host_id']:
                            raise ValueError('Only the host can force resolution.')
                        resolve_round(room)
                    else:
                        raise ValueError('Unknown action.')
                return self._send(200, public_state(room, pid))

            return self._send(404, {'error': 'Not found.'})
        except ValueError as e:
            return self._send(400, {'error': str(e)})
        except Exception as e:
            return self._send(500, {'error': 'Server error', 'detail': str(e)})


def cleanup_loop():
    while True:
        time.sleep(60)
        cutoff = time.time() - 4 * 3600
        with rooms_lock:
            for code in list(rooms):
                if rooms[code]['created_at'] < cutoff:
                    del rooms[code]


if __name__ == '__main__':
    threading.Thread(target=cleanup_loop, daemon=True).start()
    print(f'INSIDER running on http://localhost:{PORT}')
    print('For LAN play, use your computer\'s local IP address, e.g. http://192.168.x.x:8000')
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down.')
        server.server_close()
