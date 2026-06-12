# KRAKEN-TERMINAL

Kraken CLI — trade, query, and manage your Kraken account from the terminal

Usage: kraken [OPTIONS] [COMMAND]

Commands:
  assets             Get asset info
  auth               Manage API credentials
  balance            Get all cash balances
  closed-orders      Get closed orders
  credit-lines       Get credit line details (VIP only)
  deposit            Deposit methods and addresses
  earn               Earn/staking commands
  export-delete      Delete export report
  export-report      Request an export report
  export-retrieve    Download export report
  export-status      Check export report status
  extended-balance   Get extended balances (balance, credit, credit_used, hold_trade)
  futures            Futures trading and market data
  ledgers            Get ledger entries
  mcp                Start a built-in MCP (Model Context Protocol) server over stdio
  ohlc               Get OHLC candle data
  open-orders        Get open orders
  order              Place and manage spot orders
  orderbook-grouped  Get grouped order book
  orderbook          Get L2 order book
  orderbook-l3       Get L3 order book (authenticated)
  pairs              Get tradable asset pairs
  paper              Spot paper trading (simulated, no real money). For futures paper trading, use `kraken futures paper`
  positions          Get open margin positions
  query-ledgers      Query specific ledger entries
  query-orders       Query specific orders
  query-trades       Query specific trades
  server-time        Get server time
  setup              Guided first-time setup wizard
  shell              Interactive REPL shell
  spreads            Get recent spreads
  status             Get system status and trading mode
  subaccount         Subaccount management
  ticker             Get ticker information
  trade-balance      Get margin/equity trade balance
  trades             Get recent trades
  trades-history     Get trade history
  volume             Get trade volume and fees
  wallet-transfer    Transfer between wallets
  withdraw           Make a withdrawal
  withdrawal         Withdrawal methods
  ws                 WebSocket streaming commands
  help               Print this message or the help of the given subcommand(s)

Options:
  -o, --output <OUTPUT>
          Output format: table (default) or json [possible values: table, json]
  -v, --verbose
          Show request/response details on stderr
      --api-url <API_URL>
          Override Spot API base URL
      --futures-url <FUTURES_URL>
          Override Futures API base URL
      --api-key <API_KEY>
          API key override (takes precedence over env/config)
      --api-secret <API_SECRET>
          API secret override (prefer --api-secret-stdin for security)
      --api-secret-stdin
          Read API secret from stdin (mutually exclusive with --api-secret and --api-secret-file)
      --api-secret-file <API_SECRET_FILE>
          Path to file containing API secret (mutually exclusive with --api-secret and --api-secret-stdin)
      --otp <OTP>
          OTP (two-factor authentication code)
      --yes
          Skip confirmation prompts for destructive operations
  -h, --help
          Print help
  -V, --version
          Print version