"""
Aggressively close position using market order
"""

from hibachi_xyz import HibachiApiClient, Side
from hibachi_xyz.env_setup import setup_environment
from dotenv import load_dotenv
import time

def main():
    load_dotenv()

    api_endpoint, data_api_endpoint, api_key, account_id, private_key, _, _ = setup_environment()

    hibachi = HibachiApiClient(
        api_url=api_endpoint,
        data_api_url=data_api_endpoint,
        api_key=api_key,
        account_id=account_id,
        private_key=private_key,
    )

    print("="*60)
    print("  CLOSING POSITION WITH MARKET ORDER")
    print("="*60)

    # Cancel any pending orders first
    print("\n🚫 Cancelling all pending orders...")
    try:
        hibachi.cancel_all_orders()
        print("✅ All orders cancelled")
        time.sleep(2)
    except Exception as e:
        print(f"⚠️  {e}")

    # Get account info
    account_info = hibachi.get_account_info()

    if not account_info.positions:
        print("\n✅ No open positions to close")
        return

    for pos in account_info.positions:
        print(f"\n📊 Found Position:")
        print(f"   Symbol: {pos.symbol}")
        print(f"   Direction: {pos.direction}")
        print(f"   Quantity: {pos.quantity}")
        print(f"   Unrealized PnL: ${pos.unrealizedTradingPnl}")

        quantity = float(pos.quantity)

        # Use MARKET order to close immediately (will pay taker fee but closes fast)
        if pos.direction == "Long":
            print(f"\n🔴 Closing LONG with MARKET SELL")
            try:
                nonce, order_id = hibachi.place_market_order(
                    symbol=pos.symbol,
                    quantity=quantity,
                    side=Side.SELL,
                    max_fees_percent=0.001
                )
                print(f"✅ Market sell executed: {order_id}")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print(f"\n🟢 Closing SHORT with MARKET BUY")
            try:
                nonce, order_id = hibachi.place_market_order(
                    symbol=pos.symbol,
                    quantity=quantity,
                    side=Side.BUY,
                    max_fees_percent=0.001
                )
                print(f"✅ Market buy executed: {order_id}")
            except Exception as e:
                print(f"❌ Error: {e}")

    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)

    # Check final status
    account_info = hibachi.get_account_info()
    print(f"\n💰 Final Balance: ${float(account_info.balance):.2f}")

    if account_info.positions:
        print(f"\n⚠️  Still have open positions!")
    else:
        print(f"\n✅ Position closed successfully!")

if __name__ == "__main__":
    main()
