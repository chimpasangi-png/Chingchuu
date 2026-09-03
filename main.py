import os
import time
import random
import requests
from datetime import datetime

# ================= CONFIGURATION =================
# Replace with your actual credentials:
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# Target amounts to track
TARGET_AMOUNTS = {300.0, 1000.0, 3200.0, 5000.0}

# Cooldown between posts (in seconds) to avoid spamming the channel:
# E.g., 351 to 18000 seconds = 3 to 300 minutes between proofs
MIN_COOLDOWN_SEC = 351
MAX_COOLDOWN_SEC = 18000

# Reject any block older than this (180s = 3 minutes max age)
MAX_BLOCK_AGE_SEC = 180

# Tron FullNode parameters
FULLNODE_URL = "https://api.trongrid.io/wallet/getnowblock"
USDT_HEX_CONTRACT = "41a614f803b6fd780986a42c78ec9c7f77e6ded13c"
TRANSFER_METHOD_ID = "a9059cbb"
DECIMALS = 10**6
# =================================================

def send_telegram_proof(amount, tx_id, block_num, block_time_str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    tronscan_link = f"https://tronscan.org/#/transaction/{tx_id}"

    # Label matching your pricing tiers
    tier_name = f"${int(amount)} USDT TRC-20 Allocation"
    if amount == 300.0:
        tier_name = "Demo Allocation (300 USDT)"
    elif amount == 1000.0:
        tier_name = "Starter Allocation (1,000 USDT)"
    elif amount == 3200.0:
        tier_name = "Standard Allocation (3,200 USDT)"
    elif amount == 5000.0:
        tier_name = "Pro Allocation (5,000 USDT)"

    text = (
        f"⚡ *DISPATCH CONFIRMED (TRC-20)*\n\n"
        f"📦 *Tier:* `{tier_name}`\n"
        f"⏱️ *Delivered:* `{block_time_str}` (Block #{block_num})\n"
        f"🌐 *Network:* `Tron (TRC-20)`\n"
        f"✅ *Status:* `Confirmed On-Chain`\n\n"
        f"🔗 *Explorer Verification:*\n"
        f"[View Hash on Tronscan]({tronscan_link})\n\n"
        f"👉 *Start bot:* @Quickflashbot"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"\n[!] Failed to post to Telegram: {e}")
        return False

def main():
    seen_txids = set()
    last_block_num = 0
    next_allowed_post_time = 0  # Can post first match immediately

    print(f"🚀 Channel Proof Bot Started")
    print(f"📡 Target amounts: {TARGET_AMOUNTS} USDT")
    print(f"📢 Target channel: {TELEGRAM_CHAT_ID}\n")

    while True:
        try:
            response = requests.post(FULLNODE_URL, json={}, timeout=10)
            if response.status_code == 200:
                block_data = response.json()
                block_header = block_data.get("block_header", {}).get("raw_data", {})
                block_num = block_header.get("number", 0)
                block_ts = block_header.get("timestamp", int(time.time() * 1000))

                now_ts = int(time.time() * 1000)
                age_seconds = (now_ts - block_ts) / 1000

                # Strict real-time check: Ignore if block timestamp is older than 3 minutes
                if age_seconds > MAX_BLOCK_AGE_SEC:
                    time.sleep(3)
                    continue

                if block_num != last_block_num:
                    last_block_num = block_num
                    transactions = block_data.get("transactions", [])

                    for tx in transactions:
                        tx_id = tx.get("txID")
                        if not tx_id or tx_id in seen_txids:
                            continue
                        seen_txids.add(tx_id)

                        raw_data = tx.get("raw_data", {})
                        contracts = raw_data.get("contract", [])

                        for c in contracts:
                            if c.get("type") == "TriggerSmartContract":
                                val = c.get("parameter", {}).get("value", {})
                                if val.get("contract_address", "").lower() == USDT_HEX_CONTRACT and val.get("data", "").startswith(TRANSFER_METHOD_ID):
                                    try:
                                        raw_amount = int(val.get("data", "")[-64:], 16)
                                        usdt_amount = round(raw_amount / DECIMALS, 2)

                                        if usdt_amount in TARGET_AMOUNTS:
                                            block_dt = datetime.fromtimestamp(block_ts / 1000).strftime('%H:%M:%S UTC')
                                            current_time = time.time()

                                            print(f"\n[Chain Match] {usdt_amount} USDT | TXID: {tx_id[:16]}... | Block #{block_num}")

                                            # Only send to channel if cooldown period has expired
                                            if current_time >= next_allowed_post_time:
                                                posted = send_telegram_proof(usdt_amount, tx_id, block_num, block_dt)
                                                if posted:
                                                    wait_gap = random.randint(MIN_COOLDOWN_SEC, MAX_COOLDOWN_SEC)
                                                    next_allowed_post_time = current_time + wait_gap
                                                    mins = round(wait_gap / 60, 1)
                                                    print(f"✅ Posted to {TELEGRAM_CHAT_ID}! Next proof scheduled in {mins} minutes.\n")
                                            else:
                                                remaining = int(next_allowed_post_time - current_time)
                                                print(f"⏳ Cooldown active ({remaining}s remaining). Skipping broadcast.")
                                    except Exception:
                                        pass

            if len(seen_txids) > 20000:
                seen_txids.clear()

        except Exception as e:
            print(f"\n[!] Connection error: {e}")

        time.sleep(3)

if __name__ == "__main__":
    main()
    
