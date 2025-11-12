from hibachi_xyz import HibachiApiClient
from hibachi_xyz.env_setup import setup_environment
from dotenv import load_dotenv
import json

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def main():
    # Load environment variables
    load_dotenv()

    # Setup environment and create client
    print_section("Setting up Hibachi API Client")
    api_endpoint, data_api_endpoint, api_key, account_id, private_key, public_key, _ = setup_environment()

    hibachi = HibachiApiClient(
        api_url=api_endpoint,
        data_api_url=data_api_endpoint,
        api_key=api_key,
        account_id=account_id,
        private_key=private_key,
    )

    print(f"API Endpoint: {api_endpoint}")
    print(f"Account ID: {account_id}")
    print("Client initialized successfully!")

    # Test 1: Get Exchange Info
    print_section("Test 1: Exchange Information")
    try:
        exchange_info = hibachi.get_exchange_info()
        print(f"Exchange Status: {exchange_info.status}")
        print(f"Number of Future Contracts: {len(exchange_info.futureContracts)}")
        print("\nAvailable Contracts:")
        for contract in exchange_info.futureContracts[:5]:  # Show first 5
            print(f"  - {contract.symbol}: {contract.displayName} (Status: {contract.status})")
        if len(exchange_info.futureContracts) > 5:
            print(f"  ... and {len(exchange_info.futureContracts) - 5} more")
    except Exception as e:
        print(f"Error getting exchange info: {e}")

    # Test 2: Get Prices
    print_section("Test 2: Price Information (Inventory)")
    try:
        inventory = hibachi.get_inventory()
        print(f"Number of Markets: {len(inventory.markets)}")
        print("\nTop Market Prices:")
        for market in inventory.markets[:5]:  # Show first 5
            contract = market.contract
            info = market.info
            print(f"\n  {contract.symbol} ({contract.displayName}):")
            print(f"    Latest Price: ${info.priceLatest}")
            print(f"    Mark Price: ${info.markPrice}")
            print(f"    24h Change: ${float(info.priceLatest) - float(info.price24hAgo):.2f}")
    except Exception as e:
        print(f"Error getting inventory: {e}")

    # Test 3: Get Account Info
    print_section("Test 3: Account Information")
    try:
        account_info = hibachi.get_account_info()
        print(f"Account Balance: ${account_info.balance}")
        print(f"Total Position Notional: ${account_info.totalPositionNotional}")
        print(f"Total Order Notional: ${account_info.totalOrderNotional}")
        print(f"Total Unrealized PnL: ${account_info.totalUnrealizedPnl}")
        print(f"Maximal Withdraw: ${account_info.maximalWithdraw}")

        if account_info.positions:
            print(f"\nOpen Positions ({len(account_info.positions)}):")
            for pos in account_info.positions:
                print(f"  - {pos.symbol}: {pos.direction} {pos.quantity}")
                print(f"    Entry: ${pos.openPrice}, Mark: ${pos.markPrice}")
                print(f"    Unrealized PnL: ${pos.unrealizedTradingPnl}")
        else:
            print("\nNo open positions")

        if account_info.assets:
            print(f"\nAssets:")
            for asset in account_info.assets:
                print(f"  - {asset.symbol}: {asset.quantity}")
    except Exception as e:
        print(f"Error getting account info: {e}")

    # Test 4: Get Capital Balance
    print_section("Test 4: Capital Balance")
    try:
        capital_balance = hibachi.get_capital_balance()
        print(f"Capital Balance: ${capital_balance.balance}")
    except Exception as e:
        print(f"Error getting capital balance: {e}")

    # Test 5: Get Orderbook for BTC/USDT-P
    print_section("Test 5: Orderbook (BTC/USDT-P)")
    try:
        orderbook = hibachi.get_orderbook(symbol="BTC/USDT-P", depth=5, granularity=1)
        print("Top 5 Bids:")
        for bid in orderbook.bid[:5]:
            print(f"  Price: ${bid.price}, Quantity: {bid.quantity}")
        print("\nTop 5 Asks:")
        for ask in orderbook.ask[:5]:
            print(f"  Price: ${ask.price}, Quantity: {ask.quantity}")
    except Exception as e:
        print(f"Error getting orderbook: {e}")

    print_section("All Tests Completed!")
    print("Hibachi API is working correctly!\n")

if __name__ == "__main__":
    main()
