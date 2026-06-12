# BTC Analysis Prompt

Analyze BTC/USD using Kraken CLI data.

Return:
1. Market bias: long / short / neutral
2. 15m trend
3. Key support levels
4. Key resistance levels
5. Long scenario
6. Short scenario
7. No-trade condition
8. Best setup if any
9. Entry, SL, TP, risk USD, position size, R:R
10. Invalidation

Rules:
- Capital: 8000 USD
- Max risk per trade: 80 USD
- Focus only on BTC/USD
- Do not force a trade
- If setup is weak, say NO TRADE
