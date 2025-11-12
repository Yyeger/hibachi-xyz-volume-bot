"""
Maker-Only Volume Generation Bot V3 with Directional Switching
- Places orders that rest on the book as maker orders to avoid fees
- SMART DIRECTIONAL STRATEGY: Automatically switches between LONG and SHORT
- On loss > $0.50: flips direction (LONG ↔ SHORT)
- On profit: continues with current direction
- Fixed outlier filtering (no more inverted market swaps!)
- Market trend detection and adaptive pricing
- 2 minute wait between entry and exit (optimized for volume)
- 20 minute max position hold (gives market time to recover while limiting losses)
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

class MarketDirectionTracker:
    """Track market direction and auto-switch on losses"""
    def __init__(self):
        self.price_history = []
        self.current_direction = "LONG"  # Start with long positions
        self.last_cycle_pnl = 0

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
        """Record if cycle was profitable and decide direction for next cycle"""
        self.last_cycle_pnl = pnl
        if pnl < -0.50:  # Loss greater than 50 cents
            self.flip_direction()
            print_flush(f"[{ts()}] 💥 Loss detected (${pnl:.2f}) - FLIPPED to {self.current_direction}")
            return True  # Direction flipped
        else:
            print_flush(f"[{ts()}] ✅ Profitable cycle (${pnl:.2f}) - Continuing {self.current_direction}")
        return False  # Direction unchanged

    def flip_direction(self):
        """Flip trading direction between LONG and SHORT"""
        self.current_direction = "SHORT" if self.current_direction == "LONG" else "LONG"

class TradingStats:
    """Track all trading activity with directional metrics"""
    def __init__(self):
        self.start_time = time.time()
        self.start_balance = 0
        self.end_balance = 0
        self.long_cycles = 0
        self.short_cycles = 0
        self.failed_buys = 0
        self.failed_sells = 0
        self.total_buy_adjustments = 0
        self.total_sell_adjustments = 0
        self.total_volume = 0
        self.total_fees_paid = 0
        self.profitable_cycles = 0
        self.losing_cycles = 0
        self.direction_flips = 0
        self.cycle_details = []

    def add_cycle(self, direction, buy_price, sell_price, quantity, pnl, 
                  buy_adjustments, sell_adjustments, fees_paid=0):
        self.cycle_details.append({
            'direction': direction,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'quantity': quantity,
            'pnl': pnl,
            'buy_adjustments': buy_adjustments,
            'sell_adjustments': sell_adjustments,
            'fees_paid': fees_paid,
            'volume': (buy_price + sell_price) * quantity
        })
        
        if direction == "LONG":
            self.long_cycles += 1
        else:
            self.short_cycles += 1
            
        self.total_volume += (buy_price + sell_price) * quantity
        self.total_fees_paid += fees_paid

        if pnl > 0:
            self.profitable_cycles += 1
        else:
            self.losing_cycles += 1

        self.total_buy_adjustments += buy_adjustments
        self.total_sell_adjustments += sell_adjustments

    def print_recap(self, direction_tracker):
        duration = (time.time() - self.start_time) / 60
        total_pnl = self.end_balance - self.start_balance
        total_completed = self.long_cycles + self.short_cycles

        print_flush("\n" + "="*70)
        print_flush("  FINAL RECAP - MAKER-ONLY V3 WITH DIRECTIONAL SWITCHING")
        print_flush("="*70)

        print_flush(f"\n⏱️  DURATION: {duration:.1f} minutes ({duration/60:.2f} hours)")

        print_flush(f"\n💰 BALANCE:")
        print_flush(f"   Starting: ${self.start_balance:.2f}")
        print_flush(f"   Ending:   ${self.end_balance:.2f}")
        print_flush(f"   Total P&L: ${total_pnl:.4f} ({(total_pnl/self.start_balance)*100:.4f}%)")

        print_flush(f"\n📊 TRADING ACTIVITY:")
        print_flush(f"   Long Cycles: {self.long_cycles}")
        print_flush(f"   Short Cycles: {self.short_cycles}")
        print_flush(f"   Total Completed: {total_completed}")
        print_flush(f"   Profitable Cycles: {self.profitable_cycles}")
        print_flush(f"   Losing Cycles: {self.losing_cycles}")
        if total_completed > 0:
            win_rate = (self.profitable_cycles / total_completed) * 100
            print_flush(f"   Win Rate: {win_rate:.1f}%")
        print_flush(f"   Failed Buys: {self.failed_buys}")
        print_flush(f"   Failed Sells: {self.failed_sells}")
        print_flush(f"   Direction Flips: {self.direction_flips}")
        print_flush(f"   Total Volume Generated: ${self.total_volume:,.2f}")
        print_flush(f"   Total Fees Paid: ${self.total_fees_paid:.4f} (Should be $0)")

        print_flush(f"\n🔧 PRICE ADJUSTMENTS:")
        print_flush(f"   Total Buy Adjustments: {self.total_buy_adjustments}")
        print_flush(f"   Total Sell Adjustments: {self.total_sell_adjustments}")

        if total_completed > 0:
            avg_volume = self.total_volume / total_completed
            avg_pnl = total_pnl / total_completed
            print_flush(f"\n📈 AVERAGES (per completed cycle):")
            print_flush(f"   Volume: ${avg_volume:.2f}")
            print_flush(f"   P&L: ${avg_pnl:.4f}")
            print_flush(f"   Volume per hour: ${self.total_volume / (duration/60):,.2f}")

        print_flush("\n" + "="*70)

def filter_outlier_prices(prices, max_deviation_percent=2.0):
    """
    Filter out outlier prices that are too far from the median
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

        # Calculate weighted average of top 3 orders
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
            if bid_deviation > 0.01:
                print_flush(f"[{ts()}] ⚠️  Best bid ${best_bid_simple:.2f} deviates from weighted ${weighted_bid:.2f}")
                best_bid = weighted_bid
            else:
                best_bid = best_bid_simple
        else:
            best_bid = best_bid_simple

        if best_ask_simple and weighted_ask:
            ask_deviation = abs(best_ask_simple - weighted_ask) / weighted_ask
            if ask_deviation > 0.01:
                print_flush(f"[{ts()}] ⚠️  Best ask ${best_ask_simple:.2f} deviates from weighted ${weighted_ask:.2f}")
                best_ask = weighted_ask
            else:
                best_ask = best_ask_simple
        else:
            best_ask = best_ask_simple

        # Validate that bid/ask are not inverted
        if best_bid and best_ask and best_bid >= best_ask:
            print_flush(f"[{ts()}] ⚠️  Outlier filtering produced invalid result: Bid ${best_bid:.2f} >= Ask ${best_ask:.2f}")
            print_flush(f"[{ts()}] 🔄 Using weighted average prices")
            best_bid = weighted_bid
            best_ask = weighted_ask

            # If weighted prices are still invalid, use median approach
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
    """
    print_flush(f"[{ts()}] 🟢 MAKER BUY STRATEGY (fee-free)")

    best_bid, best_ask = get_robust_market_prices(hibachi, symbol)
    if not best_bid:
        return False, 0, None, 0

    trend_tracker.add_price_point(best_bid)
    tick_size = 0.01
    offset = tick_size * 30 if trend_tracker.is_downtrend() else tick_size * 20
    current_price = best_bid - offset

    spread = best_ask - best_bid
    print_flush(f"[{ts()}] Market: Bid ${best_bid:.2f} | Ask ${best_ask:.2f} | Spread ${spread:.2f}")
    print_flush(f"[{ts()}] 📍 Placing MAKER buy @ ${current_price:.2f} (${offset:.2f} below bid)")

    adjustment_count = 0
    adjustment_interval = 60

    try:
        nonce, order_id = hibachi.place_limit_order(
            symbol=symbol,
            quantity=quantity,
            price=current_price,
            side=Side.BUY,
            max_fees_percent=0.00045
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

        if since_last_update >= 15:
            print_flush(f"[{ts()}] [{elapsed}s] Waiting for maker buy fill... (next check in {adjustment_interval - since_last_adj}s)")
            last_update = time.time()

        try:
            order = hibachi.get_order_details(order_id=order_id)
            status = str(order.status)

            if "FILLED" in status:
                print_flush(f"[{ts()}] ✅ MAKER BUY FILLED in {elapsed}s @ ${current_price:.2f} (no fees!)")
                return True, current_price, order_id, adjustment_count

        except Exception as e:
            if since_last_update >= 15:
                print_flush(f"[{ts()}] ⚠️  Check error: {str(e)[:50]}")

        if since_last_adj >= adjustment_interval:
            adjustment_count += 1

            print_flush(f"[{ts()}] ⏰ Adjusting buy price (#{adjustment_count})")
            try:
                hibachi.cancel_order(order_id=order_id)
                time.sleep(1)
            except:
                pass

            print_flush(f"[{ts()}] 📊 Refreshing market prices...")
            best_bid, best_ask = get_robust_market_prices(hibachi, symbol)

            if not best_bid:
                print_flush(f"[{ts()}] ⚠️  Could not get fresh prices, retrying...")
                time.sleep(5)
                continue

            trend_tracker.add_price_point(best_bid)

            print_flush(f"[{ts()}] Market now: Bid ${best_bid:.2f} | Ask ${best_ask:.2f}")

            if adjustment_count <= 3:
                offset = max(0.20 - (adjustment_count * 0.05), 0.05)
                current_price = best_bid - offset
            elif adjustment_count <= 6:
                offset = 0.01
                current_price = best_bid - offset
            else:
                current_price = best_bid

            try:
                nonce, order_id = hibachi.place_limit_order(
                    symbol=symbol,
                    quantity=quantity,
                    price=current_price,
                    side=Side.BUY,
                    max_fees_percent=0.00045
                )
                print_flush(f"[{ts()}] ✅ New maker order placed: {order_id}")
                last_adjustment = time.time()
            except Exception as e:
                print_flush(f"[{ts()}] ❌ Error placing order: {e}")
                time.sleep(5)
                continue

def place_maker_sell_order(hibachi, symbol, quantity, entry_price, trend_tracker, is_short=False):
    """
    Place sell order as a MAKER order (above best ask) to avoid fees
    SMART ADAPTIVE: Adjusts based on current P&L potential
    For longs: entry_price is buy_price, profit when sell > entry
    For shorts: entry_price is sell_price, profit when buy < entry
    """
    print_flush(f"[{ts()}] 🔴 SMART ADAPTIVE MAKER SELL STRATEGY")

    best_bid, best_ask = get_robust_market_prices(hibachi, symbol)
    if not best_bid:
        return False, 0, None, 0

    trend_tracker.add_price_point(best_ask)

    # Calculate potential P&L
    if is_short:
        potential_pnl = (entry_price - best_bid) * quantity
    else:
        potential_pnl = (best_ask - entry_price) * quantity

    tick_size = 0.01
    print_flush(f"[{ts()}] Market: Bid ${best_bid:.2f} | Ask ${best_ask:.2f}")
    print_flush(f"[{ts()}] Entry Price: ${entry_price:.2f}")
    print_flush(f"[{ts()}] Potential P&L at market: ${potential_pnl:+.2f}")

    # ADAPTIVE STRATEGY based on P&L potential
    if potential_pnl >= 3.0:
        offset = 1.50
        current_price = best_ask + offset
        print_flush(f"[{ts()}] 🚀 High profit zone! Aggressive ask @ ${current_price:.2f} (+${offset:.2f})")
    elif potential_pnl >= 1.5:
        offset = 0.80
        current_price = best_ask + offset
        print_flush(f"[{ts()}] 📈 Good profit zone! Patient ask @ ${current_price:.2f} (+${offset:.2f})")
    elif potential_pnl >= 0.50:
        offset = 0.30
        current_price = best_ask + offset
        print_flush(f"[{ts()}] ✅ Small profit zone! Reasonable ask @ ${current_price:.2f} (+${offset:.2f})")
    elif potential_pnl >= -0.20:
        offset = 0.20
        current_price = max(best_ask + offset, entry_price + 0.10)
        print_flush(f"[{ts()}] ⚖️  Near breakeven, ask @ ${current_price:.2f}")
    elif potential_pnl >= -1.0:
        offset = 0.10
        current_price = best_ask + offset
        print_flush(f"[{ts()}] ⚠️  Small loss territory, ask @ ${current_price:.2f} (+${offset:.2f})")
    else:
        offset = 0.05
        current_price = best_ask + offset
        print_flush(f"[{ts()}] 🔴 Significant loss, aggressive ask @ ${current_price:.2f} (+${offset:.2f})")

    adjustment_count = 0
    adjustment_interval = 30
    max_wait_time = 1200  # 20 minutes max

    try:
        nonce, order_id = hibachi.place_limit_order(
            symbol=symbol,
            quantity=quantity,
            price=current_price,
            side=Side.SELL,
            max_fees_percent=0.00045
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

        if since_last_update >= 15:
            print_flush(f"[{ts()}] [{elapsed}s] Waiting for maker sell fill... (next check in {adjustment_interval - since_last_adj}s)")
            last_update = time.time()

        try:
            order = hibachi.get_order_details(order_id=order_id)
            status = str(order.status)

            if "FILLED" in status:
                print_flush(f"[{ts()}] ✅ MAKER SELL FILLED in {elapsed}s @ ${current_price:.2f} (no fees!)")
                final_pnl = (current_price - entry_price) * quantity if not is_short else (entry_price - current_price) * quantity
                print_flush(f"[{ts()}] Trade P&L: ${final_pnl:+.4f}")
                return True, current_price, order_id, adjustment_count

        except Exception as e:
            if since_last_update >= 15:
                print_flush(f"[{ts()}] ⚠️  Check error: {str(e)[:50]}")

        if since_last_adj >= adjustment_interval or elapsed >= max_wait_time:
            adjustment_count += 1

            print_flush(f"[{ts()}] ⏰ Adjusting sell price (#{adjustment_count})")
            try:
                hibachi.cancel_order(order_id=order_id)
                time.sleep(1)
            except:
                pass

            print_flush(f"[{ts()}] 📊 Refreshing market prices...")
            best_bid, best_ask = get_robust_market_prices(hibachi, symbol)

            if not best_bid:
                print_flush(f"[{ts()}] ⚠️  Could not get fresh prices, retrying...")
                time.sleep(5)
                continue

            trend_tracker.add_price_point(best_ask)

            # Recalculate P&L potential
            if is_short:
                potential_pnl = (entry_price - best_bid) * quantity
            else:
                potential_pnl = (best_ask - entry_price) * quantity

            print_flush(f"[{ts()}] Market now: Bid ${best_bid:.2f} | Ask ${best_ask:.2f}")
            print_flush(f"[{ts()}] Potential P&L at market: ${potential_pnl:+.2f}")

            # Force close if max wait reached
            if elapsed >= max_wait_time:
                current_price = best_ask + 0.01
                print_flush(f"[{ts()}] ⏰ MAX WAIT (20 min) REACHED - Closing position: ${current_price:.2f}")

            # SMART ADAPTIVE STRATEGY: Adjust based on market conditions
            elif potential_pnl >= 3.0:
                offset = max(1.20 - (adjustment_count * 0.15), 0.50)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] 🚀 High profit! Adjusting ask @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= 1.5:
                offset = max(0.60 - (adjustment_count * 0.10), 0.30)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] 📈 Good profit zone! Ask @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= 0.50:
                offset = max(0.30 - (adjustment_count * 0.05), 0.15)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] ✅ Decent profit! Ask @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= 0.0:
                offset = max(0.15 - (adjustment_count * 0.03), 0.05)
                current_price = best_ask + offset
                print_flush(f"[{ts()}] ⚖️  Small/no profit. Taking @ ${current_price:.2f} (+${offset:.2f})")

            elif potential_pnl >= -1.0:
                if adjustment_count <= 3:
                    offset = 0.10 - (adjustment_count * 0.02)
                else:
                    offset = 0.02
                current_price = best_ask + offset
                print_flush(f"[{ts()}] ⚠️  Small loss. Aggressive ask @ ${current_price:.2f} (+${offset:.2f})")

            else:
                offset = 0.01
                current_price = best_ask + offset
                print_flush(f"[{ts()}] 🔴 BIG LOSS! Cutting losses @ ${current_price:.2f}")

            try:
                nonce, order_id = hibachi.place_limit_order(
                    symbol=symbol,
                    quantity=quantity,
                    price=current_price,
                    side=Side.SELL,
                    max_fees_percent=0.00045
                )
                print_flush(f"[{ts()}] ✅ New maker order placed: {order_id}")
                last_adjustment = time.time()
            except Exception as e:
                print_flush(f"[{ts()}] ❌ Error placing order: {e}")
                time.sleep(5)
                continue

def run_long_cycle(hibachi, symbol, quantity, stats, trend_tracker):
    """Execute a LONG cycle: Buy low, Sell high"""
    print_flush(f"\n[{ts()}] " + "="*60)
    print_flush(f"[{ts()}] 🟢 STARTING LONG CYCLE (Buy → Wait → Sell)")
    print_flush(f"[{ts()}] " + "="*60)

    # Record starting balance
    try:
        account = hibachi.get_account_info()
        balance_before = float(account.balance)
        print_flush(f"[{ts()}] 💰 Balance: ${balance_before:.2f}")
    except Exception as e:
        print_flush(f"[{ts()}] ⚠️  Error getting balance: {e}")
        balance_before = 0

    # STEP 1: BUY (open long position)
    print_flush(f"\n[{ts()}] 🛒 STEP 1: MAKER BUY {quantity} {symbol}")
    buy_success, buy_price, buy_order_id, buy_adjustments = place_maker_buy_order(
        hibachi, symbol, quantity, trend_tracker
    )

    if not buy_success:
        print_flush(f"[{ts()}] ❌ Buy failed")
        stats.failed_buys += 1
        return False, 0

    # Verify position opened
    time.sleep(2)
    try:
        account = hibachi.get_account_info()
        position = next((p for p in account.positions if p.symbol == symbol), None)
        if not position:
            print_flush(f"[{ts()}] ⚠️  Position not found!")
            stats.failed_buys += 1
            return False, 0
        print_flush(f"[{ts()}] ✅ Position opened: {position.quantity} @ ${position.openPrice}")
    except Exception as e:
        print_flush(f"[{ts()}] ⚠️  Error verifying position: {e}")

    # STEP 2: WAIT 2 MINUTES
    #await_duration = 120
    #print_flush(f"\n[{ts()}] ⏸️  WAITING {wait_duration} SECONDS (2 minutes)")
    #wait_start = time.time()
    #while time.time() - wait_start < wait_duration:
    #    elapsed = int(time.time() - wait_start)
    #    remaining = wait_duration - elapsed
    #    if remaining % 30 == 0 and remaining > 0:
    #        minutes_left = remaining // 60
    #        seconds_left = remaining % 60
    #        print_flush(f"[{ts()}] Waiting... {minutes_left}m {seconds_left}s remaining")
    #    time.sleep(5)

    #print_flush(f"[{ts()}] ✅ Wait complete")

    # STEP 3: SELL (close long position)
    print_flush(f"\n[{ts()}] 💵 STEP 2: MAKER SELL {quantity} {symbol}")
    sell_success, sell_price, sell_order_id, sell_adjustments = place_maker_sell_order(
        hibachi, symbol, quantity, buy_price, trend_tracker, is_short=False
    )

    if not sell_success:
        print_flush(f"[{ts()}] ❌ Sell failed - position may still be open!")
        stats.failed_sells += 1
        return False, 0

    # Calculate P&L
    time.sleep(2)
    try:
        account = hibachi.get_account_info()
        balance_after = float(account.balance)
        cycle_pnl = balance_after - balance_before
        print_flush(f"[{ts()}] 💰 LONG Cycle P&L: ${cycle_pnl:+.4f}")
    except Exception as e:
        print_flush(f"[{ts()}] Error calculating P&L: {e}")
        cycle_pnl = 0

    # Log successful cycle
    stats.add_cycle("LONG", buy_price, sell_price, quantity, cycle_pnl,
                   buy_adjustments, sell_adjustments, 0)
    print_flush(f"[{ts()}] ✅ LONG CYCLE COMPLETED!")
    return True, cycle_pnl

def run_short_cycle(hibachi, symbol, quantity, stats, trend_tracker):
    """Execute a SHORT cycle: Sell high, Buy low"""
    print_flush(f"\n[{ts()}] " + "="*60)
    print_flush(f"[{ts()}] 🔴 STARTING SHORT CYCLE (Sell → Wait → Buy)")
    print_flush(f"[{ts()}] " + "="*60)

    # Record starting balance
    try:
        account = hibachi.get_account_info()
        balance_before = float(account.balance)
        print_flush(f"[{ts()}] 💰 Balance: ${balance_before:.2f}")
    except Exception as e:
        print_flush(f"[{ts()}] ⚠️  Error getting balance: {e}")
        balance_before = 0

    # STEP 1: SELL (open short position)
    print_flush(f"\n[{ts()}] 📉 STEP 1: MAKER SELL {quantity} {symbol} (OPEN SHORT)")
    # Get market reference for entry
    best_bid, best_ask = get_robust_market_prices(hibachi, symbol)
    if not best_bid:
        print_flush(f"[{ts()}] ⚠️  Could not get market prices")
        return False, 0
    
    sell_success, sell_price, sell_order_id, sell_adjustments = place_maker_sell_order(
        hibachi, symbol, quantity, best_ask, trend_tracker, is_short=True
    )

    if not sell_success:
        print_flush(f"[{ts()}] ❌ Short open failed")
        stats.failed_sells += 1
        return False, 0

    # Verify short position opened
    time.sleep(2)
    try:
        account = hibachi.get_account_info()
        position = next((p for p in account.positions if p.symbol == symbol), None)
        if not position:
            print_flush(f"[{ts()}] ⚠️  Short position not found!")
            return False, 0
        print_flush(f"[{ts()}] ✅ Short opened: {position.quantity} @ ${position.openPrice} ({position.direction})")
    except Exception as e:
        print_flush(f"[{ts()}] ⚠️  Error verifying position: {e}")

    # STEP 2: WAIT 2 MINUTES
    #wait_duration = 120
    #print_flush(f"\n[{ts()}] ⏸️  WAITING {wait_duration} SECONDS (2 minutes)")
    #wait_start = time.time()
    #while time.time() - wait_start < wait_duration:
     #   elapsed = int(time.time() - wait_start)
      #  remaining = wait_duration - elapsed
       # if remaining % 30 == 0 and remaining > 0:
        #    minutes_left = remaining // 60
         #   seconds_left = remaining % 60
          #  print_flush(f"[{ts()}] Waiting... {minutes_left}m {seconds_left}s remaining")
        #time.sleep(5)

    #print_flush(f"[{ts()}] ✅ Wait complete")

    # STEP 3: BUY (close short position)
    print_flush(f"\n[{ts()}] 🛒 STEP 2: MAKER BUY {quantity} {symbol} (CLOSE SHORT)")
    buy_success, buy_price, buy_order_id, buy_adjustments = place_maker_buy_order(
        hibachi, symbol, quantity, trend_tracker
    )

    if not buy_success:
        print_flush(f"[{ts()}] ❌ Short close failed - position may still be open!")
        stats.failed_buys += 1
        return False, 0

    # Calculate P&L for short: profit when sell_price > buy_price
    time.sleep(2)
    try:
        account = hibachi.get_account_info()
        balance_after = float(account.balance)
        cycle_pnl = balance_after - balance_before
        print_flush(f"[{ts()}] 💰 SHORT Cycle P&L: ${cycle_pnl:+.4f} (Sell ${sell_price:.2f} → Buy ${buy_price:.2f})")
    except Exception as e:
        print_flush(f"[{ts()}] Error calculating P&L: {e}")
        cycle_pnl = 0

    # Log successful cycle (note: buy_price is exit, sell_price is entry for shorts)
    stats.add_cycle("SHORT", buy_price, sell_price, quantity, cycle_pnl,
                   buy_adjustments, sell_adjustments, 0)
    print_flush(f"[{ts()}] ✅ SHORT CYCLE COMPLETED!")
    return True, cycle_pnl

def run_trading_cycle(hibachi, symbol, quantity, stats, trend_tracker):
    """Execute one complete cycle based on current market direction"""
    direction = trend_tracker.current_direction
    
    if direction == "LONG":
        return run_long_cycle(hibachi, symbol, quantity, stats, trend_tracker)
    else:
        return run_short_cycle(hibachi, symbol, quantity, stats, trend_tracker)

def main():
    load_dotenv()

    # CONFIGURATION
    SYMBOL = "ETH/USDT-P"
    QUANTITY = 0.0006
    RUN_DURATION_MINUTES = 2000
    MIN_BALANCE_REQUIRED = 0.01

    print_flush("="*70)
    print_flush("  MAKER-ONLY VOLUME BOT V3 - DIRECTIONAL AUTO-SWITCHING")
    print_flush("  Trade Size: {QUANTITY} ETH")
    print_flush("  Strategy: Flip LONG ↔ SHORT on each loss > $0.50")
    print_flush("  Features: Zero fees + Smart adaptive + Outlier filtering")
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
    trend_tracker = MarketDirectionTracker()

    # Get starting balance
    print_flush(f"\n[{ts()}] Initializing...")
    try:
        account = hibachi.get_account_info()
        stats.start_balance = float(account.balance)
        print_flush(f"[{ts()}] 💰 Starting Balance: ${stats.start_balance:.2f}")
        print_flush(f"[{ts()}] 📊 Initial Direction: {trend_tracker.current_direction}")
        
        # Show fee rates
        maker_fee = float(account.tradeMakerFeeRate)
        taker_fee = float(account.tradeTakerFeeRate)
        print_flush(f"[{ts()}] 📊 Fee Rates: Maker {maker_fee*100:.3f}% | Taker {taker_fee*100:.3f}%")
        print_flush(f"[{ts()}] ✅ Target: All trades as MAKER (0% fees)")
    except Exception as e:
        print_flush(f"[{ts()}] ❌ Error: {e}")
        return

    if stats.start_balance < MIN_BALANCE_REQUIRED:
        print_flush(f"[{ts()}] ❌ Insufficient balance")
        return

    end_time_formatted = datetime.fromtimestamp(time.time() + RUN_DURATION_MINUTES*60).strftime('%H:%M:%S')
    print_flush(f"\n[{ts()}] 🚀 Starting session...")
    print_flush(f"[{ts()}] Will run until {end_time_formatted}")
    print_flush(f"[{ts()}] Direction will auto-flip on losses > $0.50\n")

    # Main trading loop
    bot_start_time = time.time()
    end_time = bot_start_time + (RUN_DURATION_MINUTES * 60)

    while time.time() < end_time:
        remaining_time = (end_time - time.time()) / 60
        print_flush(f"\n[{ts()}] ⏱️  {remaining_time:.1f} minutes remaining")
        print_flush(f"[{ts()}] 📊 Current Direction: {trend_tracker.current_direction}")

        # Check balance
        try:
            account = hibachi.get_account_info()
            current_balance = float(account.balance)
            if current_balance < MIN_BALANCE_REQUIRED:
                print_flush(f"[{ts()}] ⚠️  Balance too low - stopping")
                break
        except:
            pass

        # Execute cycle
        success, pnl = run_trading_cycle(hibachi, SYMBOL, QUANTITY, stats, trend_tracker)

        if success:
            # Record result and check if direction should flip
            flipped = trend_tracker.record_cycle_result(pnl)
            if flipped:
                stats.direction_flips += 1
        else:
            print_flush(f"[{ts()}] Cycle failed, waiting 30s before retry...")
            time.sleep(30)

        # Small delay between cycles
        if time.time() < end_time:
            print_flush(f"[{ts()}] Waiting 10s before next cycle...")
            time.sleep(10)

    # Session complete
    print_flush(f"\n[{ts()}] ⏰ SESSION COMPLETE!")

    try:
        account = hibachi.get_account_info()
        stats.end_balance = float(account.balance)

        if account.positions:
            print_flush(f"\n[{ts()}] ⚠️  WARNING: Open positions detected!")
            for pos in account.positions:
                if pos.symbol == SYMBOL:
                    print_flush(f"[{ts()}]    {pos.symbol}: {pos.direction} {pos.quantity} @ ${pos.openPrice}")
    except:
        pass

    stats.print_recap(trend_tracker)
    print_flush(f"\n[{ts()}] 🎉 Trading session complete - Directional switching active\n")

if __name__ == "__main__":
    main()
