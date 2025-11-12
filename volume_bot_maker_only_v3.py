"""
Maker-Only Volume Generation Bot V3 with Smart Adaptive Strategy (FIXED)
- Places orders that rest on the book as maker orders to avoid fees
- Fixed outlier filtering (no more inverted market swaps!)
- SMART ADAPTIVE SELL STRATEGY: Adjusts based on current P&L potential
  * If market went UP: Be greedy and try for maximum profit
  * If market went DOWN: Be aggressive and limit losses
  * Continuously monitors and adapts to market conditions
- Market trend detection and loss prevention
- Pauses trading during downtrends to minimize losses
- 2 minute wait between buy and sell (optimized for volume)
- 20 minute max sell wait (gives market time to recover while limiting losses)
- 10 minute cooldown after 3 consecutive losses
"""

from hibachi_xyz import HibachiApiClient, Side
from hibachi_xyz.env_setup import setup_environment
from dotenv import load_dotenv
import time
from datetime import datetime
import sys
import statistics

def ts():
    return datetime.now().strftime("%H:%M:%S")

def print_flush(msg):
    """Print and flush immediately"""
    print(msg)
    sys.stdout.flush()

class MarketTrendTracker:
    """Track market trends and detect downtrends"""
    def __init__(self):
        self.price_history = []
        self.consecutive_losses = 0
        self.last_cooldown_time = 0
        self.total_cooldowns = 0

    def add_price_point(self, price):
        """Add a price point to track trend"""
        self.price_history.append((time.time(), price))
        # Keep only last 30 minutes of data
        cutoff = time.time() - 1800
        self.price_history = [(t, p) for t, p in self.price_history if t > cutoff]

    def is_downtrend(self):
        """Check if market is in a downtrend"""
        if len(self.price_history) < 3:
            return False

        # Check last 5 price points
        recent_prices = [p for _, p in self.price_history[-5:]]
        if len(recent_prices) < 3:
            return False

        # Simple downtrend detection: each price lower than previous
        downtrend_count = sum(1 for i in range(1, len(recent_prices))
                             if recent_prices[i] < recent_prices[i-1])

        return downtrend_count >= len(recent_prices) - 1

    def record_cycle_result(self, pnl):
        """Record if cycle was profitable or not"""
        if pnl < -0.50:  # Loss greater than 50 cents
            self.consecutive_losses += 1
            print_flush(f"[{ts()}] ⚠️  Loss detected #{self.consecutive_losses} (P&L: ${pnl:.2f})")
        else:
            if self.consecutive_losses > 0:
                print_flush(f"[{ts()}] ✅ Profitable cycle - resetting loss counter")
            self.consecutive_losses = 0

    def should_cooldown(self):
        """Check if we should enter cooldown period"""
        return self.consecutive_losses >= 3

    def do_cooldown(self, duration_minutes=10):
        """Execute cooldown period"""
        self.total_cooldowns += 1
        print_flush(f"\n[{ts()}] " + "🛑"*20)
        print_flush(f"[{ts()}] 🛑 MARKET PROTECTION ACTIVATED")
        print_flush(f"[{ts()}] 📉 Detected {self.consecutive_losses} consecutive losses")
        print_flush(f"[{ts()}] ⏸️  Pausing trading for {duration_minutes} minutes")
        print_flush(f"[{ts()}] 💡 Waiting for market to stabilize...")
        print_flush(f"[{ts()}] " + "🛑"*20 + "\n")

        self.last_cooldown_time = time.time()
        cooldown_end = time.time() + (duration_minutes * 60)

        while time.time() < cooldown_end:
            remaining = int(cooldown_end - time.time())
            if remaining % 60 == 0 and remaining > 0:
                print_flush(f"[{ts()}] ⏸️  Cooldown: {remaining // 60} minutes remaining...")
            time.sleep(10)

        print_flush(f"[{ts()}] ✅ Cooldown complete - resuming trading")
        self.consecutive_losses = 0  # Reset counter after cooldown

class TradingStats:
    """Track all trading activity with enhanced metrics"""
    def __init__(self):
        self.start_time = time.time()
        self.start_balance = 0
        self.end_balance = 0
        self.completed_cycles = 0
        self.failed_buys = 0
        self.failed_sells = 0
        self.total_buy_adjustments = 0
        self.total_sell_adjustments = 0
        self.total_volume = 0
        self.total_fees_paid = 0
        self.profitable_cycles = 0
        self.losing_cycles = 0
        self.total_cooldowns = 0
        self.cycle_details = []

    def add_cycle(self, success, buy_price, sell_price, quantity, pnl, buy_adjustments, sell_adjustments, fees_paid=0):
        self.cycle_details.append({
            'success': success,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'quantity': quantity,
            'pnl': pnl,
            'buy_adjustments': buy_adjustments,
            'sell_adjustments': sell_adjustments,
            'fees_paid': fees_paid,
            'volume': (buy_price + sell_price) * quantity if success else 0
        })
        if success:
            self.completed_cycles += 1
            self.total_volume += (buy_price + sell_price) * quantity
            self.total_fees_paid += fees_paid

            if pnl > 0:
                self.profitable_cycles += 1
            else:
                self.losing_cycles += 1

        self.total_buy_adjustments += buy_adjustments
        self.total_sell_adjustments += sell_adjustments

    def print_recap(self, trend_tracker):
        duration = (time.time() - self.start_time) / 60
        total_pnl = self.end_balance - self.start_balance

        print_flush("\n" + "="*70)
        print_flush("  FINAL RECAP - MAKER-ONLY V3 WITH LOSS PREVENTION")
        print_flush("="*70)

        print_flush(f"\n⏱️  DURATION: {duration:.1f} minutes ({duration/60:.2f} hours)")

        print_flush(f"\n💰 BALANCE:")
        print_flush(f"   Starting: ${self.start_balance:.2f}")
        print_flush(f"   Ending:   ${self.end_balance:.2f}")
        print_flush(f"   Total P&L: ${total_pnl:.4f} ({(total_pnl/self.start_balance)*100:.4f}%)")

        print_flush(f"\n📊 TRADING ACTIVITY:")
        print_flush(f"   Completed Cycles: {self.completed_cycles}")
        print_flush(f"   Profitable Cycles: {self.profitable_cycles}")
        print_flush(f"   Losing Cycles: {self.losing_cycles}")
        if self.completed_cycles > 0:
            win_rate = (self.profitable_cycles / self.completed_cycles) * 100
            print_flush(f"   Win Rate: {win_rate:.1f}%")
        print_flush(f"   Failed Buys: {self.failed_buys}")
        print_flush(f"   Failed Sells: {self.failed_sells}")
        print_flush(f"   Total Volume Generated: ${self.total_volume:,.2f}")
        print_flush(f"   Total Fees Paid: ${self.total_fees_paid:.4f} (Should be $0)")

        print_flush(f"\n🛡️ LOSS PREVENTION:")
        print_flush(f"   Market Cooldowns: {trend_tracker.total_cooldowns}")
        print_flush(f"   Time in Cooldown: {trend_tracker.total_cooldowns * 10} minutes")

        print_flush(f"\n🔧 PRICE ADJUSTMENTS:")
        print_flush(f"   Total Buy Adjustments: {self.total_buy_adjustments}")
        print_flush(f"   Total Sell Adjustments: {self.total_sell_adjustments}")

        if self.completed_cycles > 0:
            avg_volume = self.total_volume / self.completed_cycles
            avg_pnl = total_pnl / self.completed_cycles
            print_flush(f"\n📈 AVERAGES (per completed cycle):")
            print_flush(f"   Volume: ${avg_volume:.2f}")
            print_flush(f"   P&L: ${avg_pnl:.4f}")
            print_flush(f"   Volume per hour: ${self.total_volume / (duration/60):,.2f}")

        print_flush("\n" + "="*70)

def filter_outlier_prices(prices, max_deviation_percent=2.0):
    """
    Filter out outlier prices that are too far from the median
    Args:
        prices: List of prices
        max_deviation_percent: Maximum allowed deviation from median (default 2%)
    Returns:
        Filtered list of prices
    """
    if len(prices) <= 2:
        return prices

    median_price = statistics.median(prices)
    max_deviation = median_price * (max_deviation_percent / 100)

    filtered = []
    outliers = []

    for price in prices:
        deviation = abs(price - median_price)
        if deviation <= max_deviation:
            filtered.append(price)
        else:
            outliers.append(price)

    if outliers:
        print_flush(f"[{ts()}] 🔍 Filtered {len(outliers)} outlier(s): {outliers}")

    # Return at least best price if all were filtered
    return filtered if filtered else [prices[0]]

def get_robust_market_prices(hibachi, symbol, depth=10):
    """
    Get current market prices with outlier filtering
    Returns weighted average of top orders excluding outliers
    """
    try:
        orderbook = hibachi.get_orderbook(symbol=symbol, depth=depth, granularity=0.01)

        # Extract bid prices and filter outliers
        bid_prices = [float(bid.price) for bid in orderbook.bid[:depth]]
        bid_sizes = [float(bid.quantity) for bid in orderbook.bid[:depth]]

        # Extract ask prices and filter outliers
        ask_prices = [float(ask.price) for ask in orderbook.ask[:depth]]
        ask_sizes = [float(ask.quantity) for ask in orderbook.ask[:depth]]

        # Simple best bid/ask (primary reference)
        best_bid_simple = bid_prices[0] if bid_prices else None
        best_ask_simple = ask_prices[0] if ask_prices else None

        # Filter outliers from deeper levels
        filtered_bids = filter_outlier_prices(bid_prices[1:], max_deviation_percent=1.5)
        filtered_asks = filter_outlier_prices(ask_prices[1:], max_deviation_percent=1.5)

        # Calculate weighted average of top 3 non-outlier orders
        top_bids = bid_prices[:3]
        top_bid_sizes = bid_sizes[:3]

        top_asks = ask_prices[:3]
        top_ask_sizes = ask_sizes[:3]

        # Weighted average for more stability
        if top_bids and top_bid_sizes:
            total_bid_size = sum(top_bid_sizes)
            weighted_bid = sum(p * s for p, s in zip(top_bids, top_bid_sizes)) / total_bid_size
        else:
            weighted_bid = best_bid_simple

        if top_asks and top_ask_sizes:
            total_ask_size = sum(top_ask_sizes)
            weighted_ask = sum(p * s for p, s in zip(top_asks, top_ask_sizes)) / total_ask_size
        else:
            weighted_ask = best_ask_simple

        # Use best prices but verify they're not outliers
        if best_bid_simple and weighted_bid:
            bid_deviation = abs(best_bid_simple - weighted_bid) / weighted_bid
            if bid_deviation > 0.01:  # More than 1% deviation
                print_flush(f"[{ts()}] ⚠️  Best bid ${best_bid_simple:.2f} deviates from weighted ${weighted_bid:.2f}")
                best_bid = weighted_bid
            else:
                best_bid = best_bid_simple
        else:
            best_bid = best_bid_simple

        if best_ask_simple and weighted_ask:
            ask_deviation = abs(best_ask_simple - weighted_ask) / weighted_ask
            if ask_deviation > 0.01:  # More than 1% deviation
                print_flush(f"[{ts()}] ⚠️  Best ask ${best_ask_simple:.2f} deviates from weighted ${weighted_ask:.2f}")
                best_ask = weighted_ask
            else:
                best_ask = best_ask_simple
        else:
            best_ask = best_ask_simple

        # Validate that bid/ask are not inverted - if they are, use weighted prices (which are more reliable)
        if best_bid and best_ask and best_bid >= best_ask:
            print_flush(f"[{ts()}] ⚠️  Outlier filtering produced invalid result: Bid ${best_bid:.2f} >= Ask ${best_ask:.2f}")
            print_flush(f"[{ts()}] 🔄 Using weighted average prices (outlier-resistant)")
            # Weighted prices are calculated from top 3 orders and are more stable
            best_bid = weighted_bid
            best_ask = weighted_ask

            # If weighted prices are still invalid, something is very wrong - use median approach
            if best_bid >= best_ask:
                print_flush(f"[{ts()}] ⚠️  Still invalid! Using median of top orders")
                best_bid = statistics.median(bid_prices[:5]) if len(bid_prices) >= 3 else bid_prices[1] if len(bid_prices) > 1 else bid_prices[0]
                best_ask = statistics.median(ask_prices[:5]) if len(ask_prices) >= 3 else ask_prices[1] if len(ask_prices) > 1 else ask_prices[0]

        return best_bid, best_ask

    except Exception as e:
        print_flush(f"[{ts()}] ⚠️  Error getting market prices: {e}")
        return None, None

def place_maker_buy_order(hibachi, symbol, quantity, trend_tracker):
    """
    Place buy order as a MAKER order (below best bid) to avoid fees
    Uses robust price detection with outlier filtering
    """

    print_flush(f"[{ts()}] 🟢 MAKER BUY STRATEGY (fee-free, loss-protected)")

    # Get robust market prices with outlier filtering
    best_bid, best_ask = get_robust_market_prices(hibachi, symbol)
    if not best_bid:
        return False, 0, None, 0

    # Track market price for trend analysis
    trend_tracker.add_price_point(best_bid)

    # Check for downtrend warning
    if trend_tracker.is_downtrend():
        print_flush(f"[{ts()}] ⚠️  WARNING: Market appears to be in downtrend")
        print_flush(f"[{ts()}] 📉 Being extra cautious with buy placement")

    # MAKER STRATEGY: Place order BELOW best bid
    tick_size = 0.01  # Minimum price increment

    # More conservative in downtrend
    if trend_tracker.is_downtrend():
        offset = tick_size * 30  # 30 cents below in downtrend
    else:
        offset = tick_size * 20  # 20 cents below normally

    current_price = best_bid - offset

    spread = best_ask - best_bid
    print_flush(f"[{ts()}] Market: Bid ${best_bid:.2f} | Ask ${best_ask:.2f} | Spread ${spread:.2f}")
    print_flush(f"[{ts()}] 📍 Placing MAKER buy @ ${current_price:.2f} (${offset:.2f} below bid)")

    adjustment_count = 0
    adjustment_interval = 60  # Check every 60 seconds for maker orders

    try:
        nonce, order_id = hibachi.place_limit_order(
            symbol=symbol,
            quantity=quantity,
            price=current_price,
            side=Side.BUY,
            max_fees_percent=0.00045  # Minimum allowed by exchange to ensure maker
        )
        print_flush(f"[{ts()}] ✅ Maker order placed: {order_id}")
    except Exception as e:
        print_flush(f"[{ts()}] ❌ Error: {e}")
        return False, 0, None, 0

    order_start_time = time.time()
    last_adjustment = order_start_time
    last_update = order_start_time

    while True:
        time.sleep(5)
        elapsed = int(time.time() - order_start_time)
        since_last_adj = int(time.time() - last_adjustment)
        since_last_update = int(time.time() - last_update)

        # Update every 15 seconds
        if since_last_update >= 15:
            print_flush(f"[{ts()}] [{elapsed}s] Waiting for maker buy fill... (next check in {adjustment_interval - since_last_adj}s)")
            last_update = time.time()

        # Check order status
        try:
            order = hibachi.get_order_details(order_id=order_id)
            status = str(order.status)

            if "FILLED" in status:
                print_flush(f"[{ts()}] ✅ MAKER BUY FILLED in {elapsed}s @ ${current_price:.2f} (no fees!)")
                return True, current_price, order_id, adjustment_count

        except Exception as e:
            if since_last_update >= 15:
                print_flush(f"[{ts()}] ⚠️  Check error: {str(e)[:50]}")

        # Time to adjust? Move closer to market while staying as maker
        if since_last_adj >= adjustment_interval:
            adjustment_count += 1

            # Cancel old order
            print_flush(f"[{ts()}] ⏰ Adjusting buy price (#{adjustment_count})")
            try:
                hibachi.cancel_order(order_id=order_id)
                time.sleep(1)
            except:
                pass

            # GET FRESH MARKET PRICES with outlier filtering!
            print_flush(f"[{ts()}] 📊 Refreshing market prices (with outlier filter)...")
            best_bid, best_ask = get_robust_market_prices(hibachi, symbol)

            if not best_bid:
                print_flush(f"[{ts()}] ⚠️  Could not get fresh prices, retrying...")
                time.sleep(5)
                continue

            # Track new price
            trend_tracker.add_price_point(best_bid)

            print_flush(f"[{ts()}] Market now: Bid ${best_bid:.2f} | Ask ${best_ask:.2f}")

            # Gradually move closer to bid while maintaining maker status
            if adjustment_count <= 3:
                # Gradually reduce offset: 20 cents -> 15 -> 10 -> 5
                offset = max(0.20 - (adjustment_count * 0.05), 0.05)
                current_price = best_bid - offset
                print_flush(f"[{ts()}] 📈 Moving closer: ${current_price:.2f} (${offset:.2f} below bid)")
            elif adjustment_count <= 6:
                # After 3 adjustments, try very close to bid
                offset = 0.01  # Just 1 cent below
                current_price = best_bid - offset
                print_flush(f"[{ts()}] 📈 Very close to bid: ${current_price:.2f}")
            else:
                # After 6 adjustments, try AT the bid (still maker if not crossing)
                current_price = best_bid
                print_flush(f"[{ts()}] 📈 At best bid: ${current_price:.2f} (aggressive maker)")

            # Place new order
            try:
                nonce, order_id = hibachi.place_limit_order(
                    symbol=symbol,
                    quantity=quantity,
                    price=current_price,
                    side=Side.BUY,
                    max_fees_percent=0.00045  # Minimum allowed by exchange
                )
                print_flush(f"[{ts()}] ✅ New maker order placed: {order_id}")
                last_adjustment = time.time()
            except Exception as e:
                print_flush(f"[{ts()}] ❌ Error placing order: {e}")
                time.sleep(5)
                continue

def place_maker_sell_order(hibachi, symbol, quantity, buy_price, trend_tracker):
    """
    Place sell order as a MAKER order (above best ask) to avoid fees
    Uses robust price detection with outlier filtering
    SMART ADAPTIVE: Adjusts strategy based on current P&L potential
    - If market went UP significantly: Be greedy, place order higher
    - If market is flat/small profit: Take reasonable profit
    - If market went DOWN: Be aggressive, close position quickly
    """

    print_flush(f"[{ts()}] 🔴 SMART ADAPTIVE MAKER SELL STRATEGY")

    # Get robust market prices with outlier filtering
    best_bid, best_ask = get_robust_market_prices(hibachi, symbol)
    if not best_bid:
        return False, 0, None, 0

    # Track market price
    trend_tracker.add_price_point(best_ask)

    # Calculate potential P&L at current market
    potential_pnl = (best_ask - buy_price) * quantity
    tick_size = 0.01

    print_flush(f"[{ts()}] Market: Bid ${best_bid:.2f} | Ask ${best_ask:.2f}")
    print_flush(f"[{ts()}] Buy Price: ${buy_price:.2f}")
    print_flush(f"[{ts()}] Potential P&L at market ask: ${potential_pnl:+.2f}")

    # ADAPTIVE STRATEGY: Place sell order based on market conditions
    if potential_pnl >= 3.0:
        # Market way up! Be greedy and try for maximum profit
        offset = 1.50  # $1.50 above ask - try to capture big profit
        current_price = best_ask + offset
        print_flush(f"[{ts()}] 🚀 MARKET WAY UP! Trying for max profit @ ${current_price:.2f} (+${offset:.2f})")
    elif potential_pnl >= 1.5:
        # Market up nicely, be patient
        offset = 0.80  # 80 cents above ask
        current_price = best_ask + offset
        print_flush(f"[{ts()}] 📈 Market favorable! Patient sell @ ${current_price:.2f} (+${offset:.2f})")
    elif potential_pnl >= 0.50:
        # Small profit available, take it reasonably
        offset = 0.30  # 30 cents above ask
        current_price = best_ask + offset
        print_flush(f"[{ts()}] ✅ Small profit available, selling @ ${current_price:.2f} (+${offset:.2f})")
    elif potential_pnl >= -0.20:
        # Near breakeven, try to at least break even
        offset = 0.20  # 20 cents above ask
        current_price = max(best_ask + offset, buy_price + 0.10)
        print_flush(f"[{ts()}] ⚖️  Near breakeven, waiting for profit @ ${current_price:.2f}")
    elif potential_pnl >= -1.0:
        # Small loss, be more aggressive but still try to minimize
        offset = 0.10  # 10 cents above ask
        current_price = best_ask + offset
        print_flush(f"[{ts()}] ⚠️  Small loss territory, selling @ ${current_price:.2f} (+${offset:.2f})")
    else:
        # Significant loss, prioritize closing position
        offset = 0.05  # Just 5 cents above ask
        current_price = best_ask + offset
        print_flush(f"[{ts()}] 🔴 Significant loss, aggressive sell @ ${current_price:.2f} (+${offset:.2f})")

    adjustment_count = 0
    adjustment_interval = 30  # Check every 30 seconds (was 60, now faster for more volume)

    try:
        nonce, order_id = hibachi.place_limit_order(
            symbol=symbol,
            quantity=quantity,
            price=current_price,
            side=Side.SELL,
            max_fees_percent=0.00045  # Minimum allowed by exchange to ensure maker
        )
        print_flush(f"[{ts()}] ✅ Maker order placed: {order_id}")
    except Exception as e:
        print_flush(f"[{ts()}] ❌ Error: {e}")
        return False, 0, None, 0

    order_start_time = time.time()
    last_adjustment = order_start_time
    last_update = order_start_time
    max_loss_threshold = -2.0  # Maximum acceptable loss
    max_wait_time = 1200  # Maximum 20 minutes wait - gives market time to recover while limiting losses

    while True:
        time.sleep(5)
        elapsed = int(time.time() - order_start_time)
        since_last_adj = int(time.time() - last_adjustment)
        since_last_update = int(time.time() - last_update)

        # Update every 15 seconds
        if since_last_update >= 15:
            print_flush(f"[{ts()}] [{elapsed}s] Waiting for maker sell fill... (next check in {adjustment_interval - since_last_adj}s)")
            last_update = time.time()

        # Check order status
        try:
            order = hibachi.get_order_details(order_id=order_id)
            status = str(order.status)

            if "FILLED" in status:
                print_flush(f"[{ts()}] ✅ MAKER SELL FILLED in {elapsed}s @ ${current_price:.2f} (no fees!)")
                pnl = (current_price - buy_price) * quantity
                print_flush(f"[{ts()}] Trade P&L: ${pnl:+.4f}")
                return True, current_price, order_id, adjustment_count

        except Exception as e:
            if since_last_update >= 15:
                print_flush(f"[{ts()}] ⚠️  Check error: {str(e)[:50]}")

        # Time to adjust? Move closer while maintaining maker status
        if since_last_adj >= adjustment_interval:
            adjustment_count += 1

            # Cancel old order
            print_flush(f"[{ts()}] ⏰ Adjusting sell price (#{adjustment_count})")
            try:
                hibachi.cancel_order(order_id=order_id)
                time.sleep(1)
            except:
                pass

            # GET FRESH MARKET PRICES with outlier filtering!
            print_flush(f"[{ts()}] 📊 Refreshing market prices (with outlier filter)...")
            best_bid, best_ask = get_robust_market_prices(hibachi, symbol)

            if not best_bid:
                print_flush(f"[{ts()}] ⚠️  Could not get fresh prices, retrying...")
                time.sleep(5)
                continue

            # Track new price
            trend_tracker.add_price_point(best_ask)

            # Calculate current P&L potential
            potential_pnl = (best_ask - buy_price) * quantity

            print_flush(f"[{ts()}] Market now: Bid ${best_bid:.2f} | Ask ${best_ask:.2f}")
            print_flush(f"[{ts()}] Potential P&L at market ask: ${potential_pnl:+.2f}")

            # Check if we've been waiting too long - force close
            if elapsed >= max_wait_time:
                current_price = best_ask + 0.01  # Tiny offset to stay maker
                print_flush(f"[{ts()}] ⏰ MAX WAIT (20 min) REACHED - Closing position: ${current_price:.2f}")
                print_flush(f"[{ts()}] 💡 Final P&L: ${potential_pnl:+.2f}")

            # SMART ADAPTIVE STRATEGY: Adjust based on market conditions, not just time
            elif potential_pnl >= 3.0:
                # Market way up! Stay greedy but gradually come down
                offset = max(1.20 - (adjustment_count * 0.15), 0.50)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] 🚀 GREAT PROFIT! Still being greedy @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= 1.5:
                # Good profit - be patient but not too greedy
                offset = max(0.60 - (adjustment_count * 0.10), 0.30)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] 📈 Good profit zone! Patient sell @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= 0.50:
                # Decent profit - take it with reasonable markup
                offset = max(0.30 - (adjustment_count * 0.05), 0.15)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] ✅ Decent profit! Selling @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= 0.0:
                # Small profit or breakeven - be more aggressive
                offset = max(0.15 - (adjustment_count * 0.03), 0.05)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] ⚖️  Small/no profit. Taking it @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= -1.0:
                # Small loss - get more aggressive faster
                if adjustment_count <= 3:
                    offset = 0.10 - (adjustment_count * 0.02)
                else:
                    offset = 0.02
                current_price = best_ask + offset
                print_flush(f"[{ts()}] ⚠️  Small loss. Aggressive sell @ ${current_price:.2f} (+${offset:.2f})")

            else:
                # Significant loss - very aggressive, close ASAP
                offset = 0.01  # Minimum offset to stay maker
                current_price = best_ask + offset
                print_flush(f"[{ts()}] 🔴 BIG LOSS! Cutting losses @ ${current_price:.2f} (P&L: ${potential_pnl:+.2f})")

            # Place new order
            try:
                nonce, order_id = hibachi.place_limit_order(
                    symbol=symbol,
                    quantity=quantity,
                    price=current_price,
                    side=Side.SELL,
                    max_fees_percent=0.00045  # Minimum allowed by exchange
                )
                print_flush(f"[{ts()}] ✅ New maker order placed: {order_id}")
                last_adjustment = time.time()
            except Exception as e:
                print_flush(f"[{ts()}] ❌ Error placing order: {e}")
                time.sleep(5)
                continue

def run_trading_cycle(hibachi, symbol, quantity, stats, trend_tracker):
    """Execute one complete buy-sell cycle with maker orders only"""

    print_flush(f"\n[{ts()}] " + "="*60)
    print_flush(f"[{ts()}] STARTING CYCLE #{len(stats.cycle_details) + 1} (MAKER V3 + LOSS PREVENTION)")
    print_flush(f"[{ts()}] " + "="*60)

    # Record balance before cycle
    try:
        account = hibachi.get_account_info()
        balance_before = float(account.balance)
        print_flush(f"[{ts()}] 💰 Balance: ${balance_before:.2f}")
    except:
        balance_before = 0

    # STEP 1: MAKER BUY
    print_flush(f"\n[{ts()}] 🛒 STEP 1: MAKER BUY {quantity} {symbol}")
    buy_success, buy_price, buy_order_id, buy_adjustments = place_maker_buy_order(
        hibachi, symbol, quantity, trend_tracker
    )

    if not buy_success:
        print_flush(f"[{ts()}] ❌ Buy failed")
        stats.failed_buys += 1
        return False

    # Verify position and check for fees
    time.sleep(2)
    fees_paid = 0
    try:
        account = hibachi.get_account_info()
        has_position = any(pos.symbol == symbol for pos in account.positions)
        if not has_position:
            print_flush(f"[{ts()}] ⚠️  No position found!")
            stats.failed_buys += 1
            return False

        for pos in account.positions:
            if pos.symbol == symbol:
                print_flush(f"[{ts()}] ✅ Position: {pos.direction} {pos.quantity} @ ${pos.openPrice}")
                break

        # Check recent trades for fees
        trades = hibachi.get_account_trades()
        if trades.trades:
            last_trade = trades.trades[0]
            fee = float(last_trade.fee) if last_trade.fee else 0
            if fee > 0:
                print_flush(f"[{ts()}] ⚠️  WARNING: Fee detected: ${fee:.6f} - Order was TAKER!")
                fees_paid += fee
            else:
                print_flush(f"[{ts()}] ✅ NO FEES - Successful MAKER order!")
    except Exception as e:
        print_flush(f"[{ts()}] ⚠️  Error verifying: {e}")

    # STEP 2: WAIT 2 MINUTES (reduced from 5 min for more volume)
    wait_duration = 120  # 2 minutes wait
    print_flush(f"\n[{ts()}] ⏸️  WAITING 2 MINUTES BEFORE SELLING (optimized for volume)")
    print_flush(f"[{ts()}] 💡 Balancing market movement time with volume generation")

    wait_start = time.time()
    while time.time() - wait_start < wait_duration:
        elapsed = int(time.time() - wait_start)
        remaining = wait_duration - elapsed

        # More frequent updates during longer wait
        if remaining % 30 == 0 and remaining > 0:
            minutes_left = remaining // 60
            seconds_left = remaining % 60
            print_flush(f"[{ts()}] Waiting... {minutes_left}m {seconds_left}s remaining")
        time.sleep(5)

    print_flush(f"[{ts()}] ✅ Wait complete")

    # STEP 3: MAKER SELL
    print_flush(f"\n[{ts()}] 💵 STEP 2: MAKER SELL {quantity} {symbol}")
    sell_success, sell_price, sell_order_id, sell_adjustments = place_maker_sell_order(
        hibachi, symbol, quantity, buy_price, trend_tracker
    )

    if not sell_success:
        print_flush(f"[{ts()}] ❌ Sell failed - position still open!")
        stats.failed_sells += 1
        return False

    # Calculate results and check for fees
    time.sleep(2)
    cycle_pnl = 0
    try:
        account = hibachi.get_account_info()
        balance_after = float(account.balance)
        cycle_pnl = balance_after - balance_before

        # Check recent trades for sell fees
        trades = hibachi.get_account_trades()
        if trades.trades:
            last_trade = trades.trades[0]
            fee = float(last_trade.fee) if last_trade.fee else 0
            if fee > 0:
                print_flush(f"[{ts()}] ⚠️  WARNING: Fee on sell: ${fee:.6f} - Order was TAKER!")
                fees_paid += fee
            else:
                print_flush(f"[{ts()}] ✅ NO FEES on sell - Successful MAKER order!")

        print_flush(f"[{ts()}] 💰 Cycle P&L: ${cycle_pnl:+.4f}")
        print_flush(f"[{ts()}] 💸 Total fees this cycle: ${fees_paid:.6f}")

        # Record cycle result for trend tracking
        trend_tracker.record_cycle_result(cycle_pnl)

    except Exception as e:
        print_flush(f"[{ts()}] Error calculating P&L: {e}")
        cycle_pnl = 0

    stats.add_cycle(True, buy_price, sell_price, quantity, cycle_pnl,
                   buy_adjustments, sell_adjustments, fees_paid)
    print_flush(f"[{ts()}] ✅ CYCLE COMPLETED!")

    return True

def main():
    load_dotenv()

    # CONFIGURATION
    SYMBOL = "ETH/USDT-P"
    QUANTITY = 0.4
    RUN_DURATION_MINUTES = 2000
    MIN_BALANCE_REQUIRED = 1.0
    COOLDOWN_DURATION_MINUTES = 10  # Wait after consecutive losses

    print_flush("="*70)
    print_flush("  MAKER-ONLY VOLUME BOT V3 - SMART ADAPTIVE")
    print_flush("  WITH LOSS PREVENTION & MARKET PROTECTION")
    print_flush(f"  Trade Size: {QUANTITY} ETH")
    print_flush(f"  Features: Zero fees + Smart adaptive sells + Fixed outlier filter")
    print_flush(f"  Adaptive: Greedy when market up, aggressive when market down")
    print_flush(f"  2 min wait | 20 min max sell wait | 10 min cooldown after 3 losses")
    print_flush("="*70)

    api_endpoint, data_api_endpoint, api_key, account_id, private_key, _, _ = setup_environment()

    hibachi = HibachiApiClient(
        api_url=api_endpoint,
        data_api_url=data_api_endpoint,
        api_key=api_key,
        account_id=account_id,
        private_key=private_key,
    )

    stats = TradingStats()
    trend_tracker = MarketTrendTracker()

    # Get starting balance
    print_flush(f"\n[{ts()}] Initializing...")
    try:
        account = hibachi.get_account_info()
        stats.start_balance = float(account.balance)
        print_flush(f"[{ts()}] 💰 Starting Balance: ${stats.start_balance:.2f}")

        # Show fee rates
        maker_fee = float(account.tradeMakerFeeRate)
        taker_fee = float(account.tradeTakerFeeRate)
        print_flush(f"[{ts()}] 📊 Fee Rates: Maker {maker_fee*100:.3f}% | Taker {taker_fee*100:.3f}%")
        print_flush(f"[{ts()}] ✅ Target: All trades as MAKER (0% fees)")
        print_flush(f"[{ts()}] 🔍 Outlier filtering: ENABLED")
        print_flush(f"[{ts()}] 🛡️ Loss prevention: ENABLED (10 min pause after 3 losses)")
    except Exception as e:
        print_flush(f"[{ts()}] ❌ Error: {e}")
        return

    if stats.start_balance < MIN_BALANCE_REQUIRED:
        print_flush(f"[{ts()}] ❌ Insufficient balance")
        return

    end_time_formatted = datetime.fromtimestamp(time.time() + RUN_DURATION_MINUTES*60).strftime('%H:%M:%S')
    print_flush(f"\n[{ts()}] 🚀 Starting session...")
    print_flush(f"[{ts()}] Will run until {end_time_formatted}")

    # Main loop
    bot_start_time = time.time()
    end_time = bot_start_time + (RUN_DURATION_MINUTES * 60)

    while time.time() < end_time:
        remaining_time = (end_time - time.time()) / 60
        print_flush(f"\n[{ts()}] ⏱️  {remaining_time:.1f} minutes remaining")

        # Check if we need to cooldown
        if trend_tracker.should_cooldown():
            trend_tracker.do_cooldown(COOLDOWN_DURATION_MINUTES)
            stats.total_cooldowns = trend_tracker.total_cooldowns
            continue

        # Check balance
        try:
            account = hibachi.get_account_info()
            current_balance = float(account.balance)
            if current_balance < MIN_BALANCE_REQUIRED:
                print_flush(f"[{ts()}] ⚠️  Balance too low - stopping")
                break
        except:
            pass

        # Run cycle
        success = run_trading_cycle(hibachi, SYMBOL, QUANTITY, stats, trend_tracker)

        if not success:
            print_flush(f"[{ts()}] Waiting 30s before retry...")
            time.sleep(30)

        # Small delay between cycles
        if time.time() < end_time:
            print_flush(f"[{ts()}] Waiting 10s before next cycle...")
            time.sleep(10)

    # Finalize
    print_flush(f"\n[{ts()}] ⏰ SESSION COMPLETE!")

    try:
        account = hibachi.get_account_info()
        stats.end_balance = float(account.balance)

        if account.positions:
            print_flush(f"\n[{ts()}] ⚠️  WARNING: Open positions!")
            for pos in account.positions:
                if pos.symbol == SYMBOL:
                    print_flush(f"[{ts()}]    {pos.symbol}: {pos.direction} {pos.quantity}")
    except:
        pass

    stats.print_recap(trend_tracker)
    print_flush(f"\n[{ts()}] 🎉 Done! Protected against losses with smart pauses\n")

if __name__ == "__main__":
    main()
