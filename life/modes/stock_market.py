"""Mode: mkt — Agent-Based Stock Market simulation."""
import curses
import math
import random
import time

from life.constants import SPEEDS

# ── Presets ──────────────────────────────────────────────────────────
# (name, description, n_fundamental, n_chartist, n_noise, n_market_maker,
#  fundamental_value, volatility, trend_strength, herd_factor)
MKT_PRESETS = [
    ("Bull Run",
     "Strong fundamentalist demand drives steady uptrend",
     60, 30, 20, 2, 100.0, 0.02, 0.6, 0.3),
    ("Flash Crash",
     "Chartist feedback loop triggers sudden collapse",
     15, 60, 30, 1, 100.0, 0.05, 0.9, 0.7),
    ("Bubble & Pop",
     "Herd mania inflates a bubble that eventually bursts",
     10, 40, 40, 2, 100.0, 0.03, 0.8, 0.9),
    ("Efficient Market",
     "Fundamentalists dominate — price tracks fair value",
     80, 10, 10, 5, 100.0, 0.01, 0.2, 0.1),
    ("Herd Mania",
     "Noise traders amplify sentiment waves",
     10, 20, 70, 1, 100.0, 0.04, 0.5, 0.95),
    ("Market Maker Dominance",
     "Market makers provide liquidity and stabilize spreads",
     20, 20, 20, 15, 100.0, 0.02, 0.3, 0.2),
]

# ── View modes ───────────────────────────────────────────────────────
VIEW_MODES = ["price", "orderbook", "wealth", "sentiment"]
VIEW_LABELS = {
    "price": "Price Chart",
    "orderbook": "Order Book Depth",
    "wealth": "Agent Wealth Heatmap",
    "sentiment": "Sentiment Map",
}


# ── Agent class ──────────────────────────────────────────────────────
class Agent:
    __slots__ = ("kind", "cash", "shares", "sentiment", "momentum",
                 "last_order_price", "wealth_history")

    def __init__(self, kind, cash=10000.0):
        self.kind = kind  # "fundamental", "chartist", "noise", "market_maker"
        self.cash = cash
        self.shares = 0
        self.sentiment = random.uniform(-1, 1)
        self.momentum = 0.0
        self.last_order_price = 0.0
        self.wealth_history = []


# ── Order book entry ─────────────────────────────────────────────────
class Order:
    __slots__ = ("side", "price", "qty", "agent_idx")

    def __init__(self, side, price, qty, agent_idx):
        self.side = side  # "bid" or "ask"
        self.price = price
        self.qty = qty
        self.agent_idx = agent_idx


# ════════════════════════════════════════════════════════════════════
#  Mode lifecycle
# ════════════════════════════════════════════════════════════════════

def _enter_mkt_mode(self):
    """Enter Stock Market mode — show preset menu."""
    self.mkt_menu = True
    self.mkt_menu_sel = 0
    self._flash("Stock Market Simulation — select a scenario")


def _exit_mkt_mode(self):
    """Exit Stock Market mode."""
    self.mkt_mode = False
    self.mkt_menu = False
    self.mkt_running = False
    self.mkt_agents = []
    self.mkt_price_history = []
    self.mkt_bids = []
    self.mkt_asks = []
    self._flash("Stock Market mode OFF")


def _mkt_init(self, preset_idx):
    """Initialize simulation from preset."""
    (name, _desc, n_fund, n_chart, n_noise, n_mm,
     fv, vol, trend, herd) = self.MKT_PRESETS[preset_idx]

    self.mkt_preset_name = name
    self.mkt_generation = 0
    self.mkt_running = False
    self.mkt_fundamental_value = fv
    self.mkt_volatility = vol
    self.mkt_trend_strength = trend
    self.mkt_herd_factor = herd

    # Current price
    self.mkt_price = fv
    self.mkt_price_history = [fv]
    self.mkt_open_prices = [fv]
    self.mkt_high_prices = [fv]
    self.mkt_low_prices = [fv]
    self.mkt_close_prices = [fv]
    self.mkt_volumes = [0]

    # Create agents
    self.mkt_agents = []
    for _ in range(n_fund):
        a = Agent("fundamental", cash=random.uniform(8000, 15000))
        a.shares = random.randint(0, 20)
        self.mkt_agents.append(a)
    for _ in range(n_chart):
        a = Agent("chartist", cash=random.uniform(5000, 12000))
        a.shares = random.randint(0, 15)
        self.mkt_agents.append(a)
    for _ in range(n_noise):
        a = Agent("noise", cash=random.uniform(3000, 10000))
        a.shares = random.randint(0, 10)
        self.mkt_agents.append(a)
    for _ in range(n_mm):
        a = Agent("market_maker", cash=random.uniform(50000, 100000))
        a.shares = random.randint(50, 200)
        self.mkt_agents.append(a)

    # Order book
    self.mkt_bids = []  # sorted descending by price
    self.mkt_asks = []  # sorted ascending by price

    # Volume tracking
    self.mkt_tick_volume = 0
    self.mkt_candle_ticks = 5  # ticks per candle

    # Sentiment tracking
    self.mkt_global_sentiment = 0.0

    # View mode
    self.mkt_view_idx = 0
    self.mkt_view = VIEW_MODES[0]

    self.mkt_menu = False
    self.mkt_mode = True
    self._flash(f"Stock Market: {name} — Space to start")


# ════════════════════════════════════════════════════════════════════
#  Simulation step
# ════════════════════════════════════════════════════════════════════

def _mkt_step(self):
    """Advance the market simulation by one tick."""
    agents = self.mkt_agents
    price = self.mkt_price
    fv = self.mkt_fundamental_value
    vol = self.mkt_volatility
    trend = self.mkt_trend_strength
    herd = self.mkt_herd_factor
    history = self.mkt_price_history

    # Slowly drift fundamental value (random walk)
    self.mkt_fundamental_value += random.gauss(0, 0.1)
    fv = self.mkt_fundamental_value

    # Compute recent trend from history
    lookback = min(20, len(history))
    if lookback >= 2:
        recent_return = (history[-1] - history[-lookback]) / max(history[-lookback], 0.01)
    else:
        recent_return = 0.0

    # Compute global sentiment (average of all agent sentiments)
    total_sent = sum(a.sentiment for a in agents)
    self.mkt_global_sentiment = total_sent / max(len(agents), 1)

    # Clear order book for this tick
    self.mkt_bids = []
    self.mkt_asks = []

    # Each agent places orders
    for idx, agent in enumerate(agents):
        if agent.kind == "fundamental":
            # Buy if price < fv, sell if price > fv
            gap = (fv - price) / max(price, 0.01)
            agent.sentiment = max(-1, min(1, gap * 3.0 + random.gauss(0, 0.1)))
            if gap > 0.02 and agent.cash > price:
                bid_price = price * (1.0 + random.uniform(0, 0.01))
                qty = max(1, int(agent.cash * abs(gap) / max(price, 0.01)))
                qty = min(qty, 5)
                self.mkt_bids.append(Order("bid", bid_price, qty, idx))
            elif gap < -0.02 and agent.shares > 0:
                ask_price = price * (1.0 - random.uniform(0, 0.01))
                qty = max(1, min(agent.shares, 3))
                self.mkt_asks.append(Order("ask", ask_price, qty, idx))

        elif agent.kind == "chartist":
            # Follow trend and momentum
            agent.momentum = trend * recent_return + (1 - trend) * agent.momentum
            agent.sentiment = max(-1, min(1,
                agent.momentum * 5.0 + herd * self.mkt_global_sentiment
                + random.gauss(0, 0.1)))
            if agent.sentiment > 0.2 and agent.cash > price:
                bid_price = price * (1.0 + random.uniform(0, 0.02))
                qty = max(1, int(abs(agent.sentiment) * 3))
                qty = min(qty, 5)
                self.mkt_bids.append(Order("bid", bid_price, qty, idx))
            elif agent.sentiment < -0.2 and agent.shares > 0:
                ask_price = price * (1.0 - random.uniform(0, 0.02))
                qty = max(1, min(agent.shares, int(abs(agent.sentiment) * 3)))
                self.mkt_asks.append(Order("ask", ask_price, qty, idx))

        elif agent.kind == "noise":
            # Random trading with herd influence
            agent.sentiment = max(-1, min(1,
                herd * self.mkt_global_sentiment
                + random.gauss(0, 0.5)))
            if random.random() < 0.3:  # only trade 30% of ticks
                if agent.sentiment > 0 and agent.cash > price:
                    bid_price = price * (1.0 + random.uniform(-0.01, 0.03))
                    self.mkt_bids.append(Order("bid", bid_price, 1, idx))
                elif agent.sentiment < 0 and agent.shares > 0:
                    ask_price = price * (1.0 + random.uniform(-0.03, 0.01))
                    self.mkt_asks.append(Order("ask", ask_price, 1, idx))

        elif agent.kind == "market_maker":
            # Provide liquidity on both sides
            spread = vol * price * 0.5
            mid = price
            agent.sentiment = 0.0  # neutral
            if agent.cash > price * 2:
                bid_price = mid - spread * random.uniform(0.5, 1.5)
                self.mkt_bids.append(Order("bid", bid_price, random.randint(1, 5), idx))
            if agent.shares > 2:
                ask_price = mid + spread * random.uniform(0.5, 1.5)
                self.mkt_asks.append(Order("ask", ask_price, random.randint(1, 5), idx))

    # Sort order book
    self.mkt_bids.sort(key=lambda o: -o.price)  # highest first
    self.mkt_asks.sort(key=lambda o: o.price)     # lowest first

    # Match orders
    tick_volume = 0
    tick_prices = []
    while self.mkt_bids and self.mkt_asks:
        best_bid = self.mkt_bids[0]
        best_ask = self.mkt_asks[0]
        if best_bid.price >= best_ask.price:
            trade_price = (best_bid.price + best_ask.price) / 2.0
            trade_qty = min(best_bid.qty, best_ask.qty)

            # Execute trade
            buyer = agents[best_bid.agent_idx]
            seller = agents[best_ask.agent_idx]
            cost = trade_price * trade_qty
            if buyer.cash >= cost and seller.shares >= trade_qty:
                buyer.cash -= cost
                buyer.shares += trade_qty
                seller.cash += cost
                seller.shares -= trade_qty
                tick_volume += trade_qty
                tick_prices.append(trade_price)

            best_bid.qty -= trade_qty
            best_ask.qty -= trade_qty
            if best_bid.qty <= 0:
                self.mkt_bids.pop(0)
            if best_ask.qty <= 0:
                self.mkt_asks.pop(0)
        else:
            break

    # Update price
    if tick_prices:
        self.mkt_price = tick_prices[-1]
    else:
        # No trades — nudge price by noise
        self.mkt_price *= (1.0 + random.gauss(0, vol * 0.1))

    # Clamp price to positive
    self.mkt_price = max(0.01, self.mkt_price)

    # Record history
    self.mkt_price_history.append(self.mkt_price)
    self.mkt_tick_volume = tick_volume

    # Update candle data
    gen = self.mkt_generation
    ct = self.mkt_candle_ticks
    if gen % ct == 0:
        # New candle
        self.mkt_open_prices.append(self.mkt_price)
        self.mkt_high_prices.append(self.mkt_price)
        self.mkt_low_prices.append(self.mkt_price)
        self.mkt_close_prices.append(self.mkt_price)
        self.mkt_volumes.append(tick_volume)
    else:
        # Update current candle
        if self.mkt_price > self.mkt_high_prices[-1]:
            self.mkt_high_prices[-1] = self.mkt_price
        if self.mkt_price < self.mkt_low_prices[-1]:
            self.mkt_low_prices[-1] = self.mkt_price
        self.mkt_close_prices[-1] = self.mkt_price
        self.mkt_volumes[-1] += tick_volume

    # Update agent wealth histories
    for agent in agents:
        w = agent.cash + agent.shares * self.mkt_price
        agent.wealth_history.append(w)
        if len(agent.wealth_history) > 200:
            agent.wealth_history.pop(0)

    self.mkt_generation += 1

    # Keep price history bounded
    if len(self.mkt_price_history) > 2000:
        self.mkt_price_history = self.mkt_price_history[-1500:]


# ════════════════════════════════════════════════════════════════════
#  Key handling
# ════════════════════════════════════════════════════════════════════

def _handle_mkt_menu_key(self, key):
    """Handle input in preset menu."""
    n = len(self.MKT_PRESETS)
    if key in (ord("j"), curses.KEY_DOWN):
        self.mkt_menu_sel = (self.mkt_menu_sel + 1) % n
    elif key in (ord("k"), curses.KEY_UP):
        self.mkt_menu_sel = (self.mkt_menu_sel - 1) % n
    elif key in (ord("\n"), ord("\r")):
        self._mkt_init(self.mkt_menu_sel)
    elif key in (ord("q"), 27):
        self.mkt_menu = False
        self._flash("Stock Market cancelled")
    return True


def _handle_mkt_key(self, key):
    """Handle input in active simulation."""
    if key == ord(" "):
        self.mkt_running = not self.mkt_running
    elif key in (ord("n"), ord(".")):
        for _ in range(self.mkt_steps_per_frame):
            self._mkt_step()
    elif key == ord("r"):
        idx = next((i for i, p in enumerate(self.MKT_PRESETS)
                    if p[0] == self.mkt_preset_name), 0)
        self._mkt_init(idx)
        self.mkt_running = False
    elif key in (ord("R"), ord("m")):
        self.mkt_mode = False
        self.mkt_running = False
        self.mkt_menu = True
        self.mkt_menu_sel = 0
    elif key == ord("v"):
        self.mkt_view_idx = (self.mkt_view_idx + 1) % len(VIEW_MODES)
        self.mkt_view = VIEW_MODES[self.mkt_view_idx]
        self._flash(f"View: {VIEW_LABELS[self.mkt_view]}")
    elif key == ord("+") or key == ord("="):
        self.mkt_steps_per_frame = min(20, self.mkt_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.mkt_steps_per_frame}")
    elif key == ord("-"):
        self.mkt_steps_per_frame = max(1, self.mkt_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.mkt_steps_per_frame}")
    elif key == ord("<") or key == ord(","):
        self.speed_idx = max(0, self.speed_idx - 1)
    elif key == ord(">"):
        self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
    elif key in (ord("q"), 27):
        self._exit_mkt_mode()
    else:
        return True
    return True


# ════════════════════════════════════════════════════════════════════
#  Drawing — Menu
# ════════════════════════════════════════════════════════════════════

def _draw_mkt_menu(self, max_y, max_x):
    """Draw preset selection menu."""
    self.stdscr.erase()
    title = "── Agent-Based Stock Market ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, *_rest) in enumerate(self.MKT_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        line = f"  {name:<26s}  {desc}"
        attr = curses.color_pair(6)
        if i == self.mkt_menu_sel:
            attr = curses.color_pair(7) | curses.A_REVERSE
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
        except curses.error:
            pass

    # Footer info
    fy = 3 + len(self.MKT_PRESETS) * 2 + 1
    if fy < max_y - 3:
        info_lines = [
            "Agent types: Fundamentalists · Chartists · Noise traders · Market makers",
            "Views: [v] Price chart | Order book | Wealth heatmap | Sentiment map",
        ]
        for j, line in enumerate(info_lines):
            try:
                self.stdscr.addstr(fy + j, 4, line[:max_x - 6],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    hint = " [j/k]=navigate  [Enter]=select  [q]=cancel"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


# ════════════════════════════════════════════════════════════════════
#  Drawing — Active simulation
# ════════════════════════════════════════════════════════════════════

def _draw_mkt(self, max_y, max_x):
    """Draw the active stock market simulation."""
    self.stdscr.erase()
    view = self.mkt_view
    state = "▶ RUNNING" if self.mkt_running else "⏸ PAUSED"
    gen = self.mkt_generation
    price = self.mkt_price
    fv = self.mkt_fundamental_value

    # Count agents by type
    n_fund = sum(1 for a in self.mkt_agents if a.kind == "fundamental")
    n_chart = sum(1 for a in self.mkt_agents if a.kind == "chartist")
    n_noise = sum(1 for a in self.mkt_agents if a.kind == "noise")
    n_mm = sum(1 for a in self.mkt_agents if a.kind == "market_maker")

    # Title bar
    chg = ((price / self.mkt_price_history[0]) - 1.0) * 100 if self.mkt_price_history else 0
    chg_s = f"+{chg:.1f}%" if chg >= 0 else f"{chg:.1f}%"
    title = (f" MKT: {self.mkt_preset_name}  |  tick {gen}"
             f"  |  ${price:.2f} ({chg_s})"
             f"  |  FV:${fv:.2f}"
             f"  |  {state}")
    try:
        cp = curses.color_pair(2) if chg >= 0 else curses.color_pair(5)
        self.stdscr.addstr(0, 0, title[:max_x - 1], cp | curses.A_BOLD)
    except curses.error:
        pass

    if view == "price":
        _draw_mkt_price_chart(self, max_y, max_x)
    elif view == "orderbook":
        _draw_mkt_orderbook(self, max_y, max_x)
    elif view == "wealth":
        _draw_mkt_wealth(self, max_y, max_x)
    elif view == "sentiment":
        _draw_mkt_sentiment(self, max_y, max_x)

    # Agent population bar (row max_y - 3)
    pop_y = max_y - 3
    if pop_y > 2:
        total = len(self.mkt_agents)
        bar_w = min(50, max_x - 30)
        if total > 0 and bar_w > 4:
            fw = max(1, int(bar_w * n_fund / total))
            cw = max(1, int(bar_w * n_chart / total))
            nw = max(1, int(bar_w * n_noise / total))
            mw = bar_w - fw - cw - nw
            if mw < 0:
                mw = 0
            bx = 2
            try:
                self.stdscr.addstr(pop_y, bx, "█" * fw, curses.color_pair(4))
                bx += fw
                self.stdscr.addstr(pop_y, bx, "█" * cw, curses.color_pair(3))
                bx += cw
                self.stdscr.addstr(pop_y, bx, "█" * nw, curses.color_pair(1))
                bx += nw
                if mw > 0:
                    self.stdscr.addstr(pop_y, bx, "█" * mw, curses.color_pair(2))
                    bx += mw
                legend = f"  F:{n_fund} C:{n_chart} N:{n_noise} MM:{n_mm}"
                self.stdscr.addstr(pop_y, bx + 1, legend[:max_x - bx - 2],
                                   curses.color_pair(6))
            except curses.error:
                pass

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        sent = self.mkt_global_sentiment
        sent_s = f"+{sent:.2f}" if sent >= 0 else f"{sent:.2f}"
        info = (f" Tick {gen}  |  Vol={self.mkt_tick_volume}"
                f"  |  Sent={sent_s}"
                f"  |  Bids={len(self.mkt_bids)} Asks={len(self.mkt_asks)}"
                f"  |  View: {VIEW_LABELS[view]}"
                f"  |  steps/f={self.mkt_steps_per_frame}")
        try:
            self.stdscr.addstr(info_y, 0, info[:max_x - 1], curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [v]=view [+/-]=speed [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ────────────────────────────────────────────────────────────────────
#  View: ASCII Candlestick Price Chart
# ────────────────────────────────────────────────────────────────────

def _draw_mkt_price_chart(self, max_y, max_x):
    """Draw ASCII candlestick chart of price history."""
    chart_top = 2
    chart_bot = max_y - 5
    chart_h = chart_bot - chart_top
    if chart_h < 5:
        return

    opens = self.mkt_open_prices
    highs = self.mkt_high_prices
    lows = self.mkt_low_prices
    closes = self.mkt_close_prices

    # Available width for candles (leave 10 chars for price axis)
    chart_w = max_x - 12
    if chart_w < 10:
        return

    # Show as many candles as fit (each candle = 2 chars wide)
    candle_w = 2
    max_candles = chart_w // candle_w
    n_candles = min(len(opens), max_candles)
    if n_candles < 1:
        return

    start = len(opens) - n_candles
    vis_opens = opens[start:]
    vis_highs = highs[start:]
    vis_lows = lows[start:]
    vis_closes = closes[start:]

    # Price range
    all_highs = vis_highs
    all_lows = vis_lows
    p_max = max(all_highs) if all_highs else 100
    p_min = min(all_lows) if all_lows else 100
    p_range = p_max - p_min
    if p_range < 0.01:
        p_range = 1.0
        p_min = p_max - 0.5

    # Draw price axis labels
    for i in range(0, chart_h, max(1, chart_h // 5)):
        price_val = p_max - (i / max(chart_h - 1, 1)) * p_range
        label = f"${price_val:>7.2f}"
        try:
            self.stdscr.addstr(chart_top + i, max_x - 10, label[:10],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Draw fundamental value line
    fv = self.mkt_fundamental_value
    if p_min <= fv <= p_max:
        fv_row = chart_top + int((p_max - fv) / p_range * (chart_h - 1))
        if chart_top <= fv_row < chart_bot:
            for x in range(0, chart_w, 3):
                try:
                    self.stdscr.addstr(fv_row, x, "·",
                                       curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass

    def price_to_row(p):
        r = chart_top + int((p_max - p) / p_range * (chart_h - 1))
        return max(chart_top, min(chart_bot - 1, r))

    # Draw candles
    for i in range(n_candles):
        o, h, l, c = vis_opens[i], vis_highs[i], vis_lows[i], vis_closes[i]
        x = i * candle_w

        row_h = price_to_row(h)
        row_l = price_to_row(l)
        row_o = price_to_row(o)
        row_c = price_to_row(c)

        bullish = c >= o
        color = curses.color_pair(2) if bullish else curses.color_pair(5)

        # Draw wick (high to low)
        for r in range(row_h, row_l + 1):
            try:
                self.stdscr.addstr(r, x, "│", color | curses.A_DIM)
            except curses.error:
                pass

        # Draw body (open to close)
        body_top = min(row_o, row_c)
        body_bot = max(row_o, row_c)
        if body_top == body_bot:
            # Doji
            try:
                self.stdscr.addstr(body_top, x, "─" + "─",
                                   color | curses.A_BOLD)
            except curses.error:
                pass
        else:
            for r in range(body_top, body_bot + 1):
                ch = "██" if bullish else "░░"
                try:
                    self.stdscr.addstr(r, x, ch, color | curses.A_BOLD)
                except curses.error:
                    pass

    # Also draw a simple price line from tick history below if space
    # (price sparkline on the axis margin)
    ph = self.mkt_price_history
    if len(ph) > 1:
        spark_chars = "▁▂▃▄▅▆▇█"
        vis = ph[-min(len(ph), 20):]
        s_min = min(vis)
        s_max = max(vis)
        s_range = s_max - s_min if s_max > s_min else 1.0
        spark = ""
        for p in vis:
            idx = int((p - s_min) / s_range * (len(spark_chars) - 1))
            idx = max(0, min(len(spark_chars) - 1, idx))
            spark += spark_chars[idx]
        try:
            self.stdscr.addstr(chart_bot + 1, 2, f"Recent: {spark}",
                               curses.color_pair(4))
        except curses.error:
            pass


# ────────────────────────────────────────────────────────────────────
#  View: Order Book Depth
# ────────────────────────────────────────────────────────────────────

def _draw_mkt_orderbook(self, max_y, max_x):
    """Draw order book depth visualization."""
    chart_top = 2
    chart_bot = max_y - 5
    chart_h = chart_bot - chart_top
    if chart_h < 5:
        return

    mid_x = max_x // 2
    bids = self.mkt_bids
    asks = self.mkt_asks

    # Aggregate bids/asks into price levels
    bid_levels = {}
    for o in bids:
        p = round(o.price, 1)
        bid_levels[p] = bid_levels.get(p, 0) + o.qty
    ask_levels = {}
    for o in asks:
        p = round(o.price, 1)
        ask_levels[p] = ask_levels.get(p, 0) + o.qty

    bid_sorted = sorted(bid_levels.items(), key=lambda x: -x[0])[:chart_h]
    ask_sorted = sorted(ask_levels.items(), key=lambda x: x[0])[:chart_h]

    max_qty = 1
    for _, q in bid_sorted:
        if q > max_qty:
            max_qty = q
    for _, q in ask_sorted:
        if q > max_qty:
            max_qty = q

    # Header
    try:
        self.stdscr.addstr(chart_top, 2, "BIDS (Buy Orders)",
                           curses.color_pair(2) | curses.A_BOLD)
        self.stdscr.addstr(chart_top, mid_x + 2, "ASKS (Sell Orders)",
                           curses.color_pair(5) | curses.A_BOLD)
    except curses.error:
        pass

    bar_max = mid_x - 14

    # Draw bid levels (right-aligned bars growing left)
    for i, (price, qty) in enumerate(bid_sorted):
        y = chart_top + 2 + i
        if y >= chart_bot:
            break
        bar_w = max(1, int(qty / max_qty * bar_max))
        label = f"${price:>7.1f} [{qty:>3d}]"
        try:
            self.stdscr.addstr(y, 2, label, curses.color_pair(2))
            self.stdscr.addstr(y, 16, "█" * bar_w,
                               curses.color_pair(2) | curses.A_DIM)
        except curses.error:
            pass

    # Draw ask levels
    for i, (price, qty) in enumerate(ask_sorted):
        y = chart_top + 2 + i
        if y >= chart_bot:
            break
        bar_w = max(1, int(qty / max_qty * bar_max))
        label = f"${price:>7.1f} [{qty:>3d}]"
        try:
            self.stdscr.addstr(y, mid_x + 2, label, curses.color_pair(5))
            self.stdscr.addstr(y, mid_x + 16, "█" * bar_w,
                               curses.color_pair(5) | curses.A_DIM)
        except curses.error:
            pass

    # Spread info
    if bid_sorted and ask_sorted:
        best_bid = bid_sorted[0][0]
        best_ask = ask_sorted[0][0]
        spread = best_ask - best_bid
        spread_pct = (spread / self.mkt_price * 100) if self.mkt_price > 0 else 0
        spread_txt = f"Spread: ${spread:.2f} ({spread_pct:.2f}%)"
        try:
            self.stdscr.addstr(chart_bot, max(0, (max_x - len(spread_txt)) // 2),
                               spread_txt, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass


# ────────────────────────────────────────────────────────────────────
#  View: Agent Wealth Heatmap
# ────────────────────────────────────────────────────────────────────

def _draw_mkt_wealth(self, max_y, max_x):
    """Draw agent wealth distribution as a heatmap grid."""
    chart_top = 2
    chart_bot = max_y - 5
    chart_h = chart_bot - chart_top
    if chart_h < 3:
        return

    agents = self.mkt_agents
    n = len(agents)
    if n == 0:
        return

    # Compute wealth for each agent
    price = self.mkt_price
    wealths = [a.cash + a.shares * price for a in agents]
    w_min = min(wealths) if wealths else 0
    w_max = max(wealths) if wealths else 1
    w_range = w_max - w_min if w_max > w_min else 1.0

    # Layout agents in a grid
    cols = min((max_x - 2) // 3, n)
    if cols < 1:
        cols = 1
    rows = min(chart_h, (n + cols - 1) // cols)

    heat_chars = " ░▒▓█"
    kind_colors = {
        "fundamental": 4,  # cyan
        "chartist": 3,     # yellow
        "noise": 1,        # white/magenta
        "market_maker": 2, # green
    }

    for i, agent in enumerate(agents):
        r = i // cols
        c = i % cols
        y = chart_top + r
        x = 2 + c * 3
        if y >= chart_bot or x >= max_x - 3:
            continue

        w = wealths[i]
        intensity = (w - w_min) / w_range
        ci = int(intensity * (len(heat_chars) - 1))
        ci = max(0, min(len(heat_chars) - 1, ci))
        ch = heat_chars[ci] * 2

        color = kind_colors.get(agent.kind, 6)
        attr = curses.color_pair(color)
        if intensity > 0.8:
            attr |= curses.A_BOLD
        elif intensity < 0.2:
            attr |= curses.A_DIM

        try:
            self.stdscr.addstr(y, x, ch, attr)
        except curses.error:
            pass

    # Legend
    legend_y = chart_bot
    if legend_y < max_y - 4:
        legend = (f"Wealth: ${w_min:.0f} — ${w_max:.0f}"
                  f"  |  Avg: ${sum(wealths)/n:.0f}")
        try:
            self.stdscr.addstr(legend_y, 2, legend[:max_x - 4],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Top/bottom performers
    if n >= 2:
        sorted_agents = sorted(zip(wealths, agents), reverse=True)
        top_y = legend_y + 1
        if top_y < max_y - 4:
            top_w, top_a = sorted_agents[0]
            bot_w, bot_a = sorted_agents[-1]
            perf = f"Top: {top_a.kind} ${top_w:.0f}  |  Bottom: {bot_a.kind} ${bot_w:.0f}"
            try:
                self.stdscr.addstr(top_y, 2, perf[:max_x - 4],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass


# ────────────────────────────────────────────────────────────────────
#  View: Sentiment Map
# ────────────────────────────────────────────────────────────────────

def _draw_mkt_sentiment(self, max_y, max_x):
    """Draw agent sentiment visualization."""
    chart_top = 2
    chart_bot = max_y - 5
    chart_h = chart_bot - chart_top
    if chart_h < 3:
        return

    agents = self.mkt_agents
    n = len(agents)
    if n == 0:
        return

    # Layout agents in a grid
    cols = min((max_x - 2) // 3, n)
    if cols < 1:
        cols = 1

    sent_blocks = "▁▂▃▄▅▆▇█"

    for i, agent in enumerate(agents):
        r = i // cols
        c = i % cols
        y = chart_top + r
        x = 2 + c * 3
        if y >= chart_bot or x >= max_x - 3:
            continue

        s = agent.sentiment  # -1 to 1
        # Map sentiment: positive = green, negative = red
        if s >= 0:
            color = curses.color_pair(2)  # green
            si = int(s * (len(sent_blocks) - 1))
        else:
            color = curses.color_pair(5)  # red
            si = int(abs(s) * (len(sent_blocks) - 1))
        si = max(0, min(len(sent_blocks) - 1, si))

        ch = sent_blocks[si]
        kind_marker = agent.kind[0].upper()  # F/C/N/M
        attr = color
        if abs(s) > 0.7:
            attr |= curses.A_BOLD

        try:
            self.stdscr.addstr(y, x, kind_marker + ch, attr)
        except curses.error:
            pass

    # Sentiment histogram at bottom
    hist_y = chart_bot
    if hist_y < max_y - 4:
        # Simple histogram: count bullish vs bearish
        bullish = sum(1 for a in agents if a.sentiment > 0.1)
        bearish = sum(1 for a in agents if a.sentiment < -0.1)
        neutral = n - bullish - bearish
        bar_w = min(40, max_x - 35)
        if n > 0 and bar_w > 4:
            bull_w = max(0, int(bar_w * bullish / n))
            bear_w = max(0, int(bar_w * bearish / n))
            neut_w = bar_w - bull_w - bear_w
            if neut_w < 0:
                neut_w = 0
            bx = 2
            try:
                if bull_w > 0:
                    self.stdscr.addstr(hist_y, bx, "█" * bull_w,
                                       curses.color_pair(2))
                bx += bull_w
                if neut_w > 0:
                    self.stdscr.addstr(hist_y, bx, "█" * neut_w,
                                       curses.color_pair(6))
                bx += neut_w
                if bear_w > 0:
                    self.stdscr.addstr(hist_y, bx, "█" * bear_w,
                                       curses.color_pair(5))
                bx += bear_w
                label = f"  Bull:{bullish} Neutral:{neutral} Bear:{bearish}"
                self.stdscr.addstr(hist_y, bx + 1, label[:max_x - bx - 2],
                                   curses.color_pair(6))
            except curses.error:
                pass

    # Global sentiment
    gs = self.mkt_global_sentiment
    gs_label = f"Global Sentiment: {gs:+.3f}"
    gs_y = chart_bot + 1
    if gs_y < max_y - 4:
        gs_color = curses.color_pair(2) if gs >= 0 else curses.color_pair(5)
        try:
            self.stdscr.addstr(gs_y, 2, gs_label[:max_x - 4], gs_color)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════
#  Registration
# ════════════════════════════════════════════════════════════════════

def register(App):
    """Register stock market mode methods on the App class."""
    App._enter_mkt_mode = _enter_mkt_mode
    App._exit_mkt_mode = _exit_mkt_mode
    App._mkt_init = _mkt_init
    App._mkt_step = _mkt_step
    App._handle_mkt_menu_key = _handle_mkt_menu_key
    App._handle_mkt_key = _handle_mkt_key
    App._draw_mkt_menu = _draw_mkt_menu
    App._draw_mkt = _draw_mkt
    App.MKT_PRESETS = MKT_PRESETS
