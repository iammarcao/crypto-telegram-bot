import requests
import json
import os
from datetime import datetime, timedelta
import pytz
import time # Importar a biblioteca time

# --- CONFIGURAÇÕES ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_VIP = os.environ.get("CHAT_ID_VIP")

# Lista de moedas para análise
SYMBOLS = [
    "BTC", "ETH", "SOL", "XRP", "RIVER", "1000PEPE", "DOGE", "ZEC", "SUI",
    "BNB", "SEI", "UNI", "ONDO", "ORDI", "NEAR", "LDO", "JUP", "TIA", "TRON", "AVAX"
]

BINANCE_API_BASE = "https://api.binance.com/api/v3"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# Fuso horário de Lisboa
LISBON_TZ = pytz.timezone("Europe/Lisbon")

def get_binance_klines(symbol, interval=\'1h\', limit=7):
    url = f"{BINANCE_API_BASE}/klines"
    params = {
        \'symbol\': symbol,
        \'interval\': interval,
        \'limit\': limit
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Levanta um HTTPError para códigos de status ruins (4xx ou 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar klines para {symbol}: {e}")
        return None

def get_binance_ticker(symbol):
    url = f"{BINANCE_API_BASE}/ticker/24hr"
    params = {\'symbol\': symbol}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar ticker para {symbol}: {e}")
        return None

def get_exchange_info():
    url = f"{BINANCE_API_BASE}/exchangeInfo"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar exchangeInfo: {e}")
        return None

def format_price(price_str):
    try:
        price = float(price_str)
        if price >= 1000:
            return f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif price >= 1:
            return f"{price:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return f"{price:,.8f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return price_str

def analyze_klines(klines):
    if not klines or len(klines) < 7: # Precisamos de 7 velas para 7 horas
        return None, None, None, None

    # Klines: [open_time, open, high, low, close, volume, close_time, ...]
    
    # Última vela (mais recente)
    last_close = float(klines[-1][4])
    last_high = float(klines[-1][2])
    last_low = float(klines[-1][3])

    # Vela de 7 horas atrás (primeira da nossa janela)
    first_open = float(klines[0][1])

    # Variação no período de 7 horas
    change_7h = ((last_close - first_open) / first_open) * 100 if first_open != 0 else 0

    # Volume total no período de 7 horas
    total_volume = sum(float(k[5]) for k in klines)

    # Identificar rompimentos
    analysis = []
    # Rompimento de máxima/mínima do período
    period_high = max(float(k[2]) for k in klines)
    period_low = min(float(k[3]) for k in klines)

    # Simples análise de price action
    if last_close > period_high * 0.999 and last_close > first_open: # Quase rompeu a máxima e fechou em alta
        analysis.append(f"Fechou próximo à máxima do período, indicando **forte pressão compradora**.")
    elif last_close < period_low * 1.001 and last_close < first_open: # Quase rompeu a mínima e fechou em baixa
        analysis.append(f"Fechou próximo à mínima do período, indicando **forte pressão vendedora**.")
    elif last_close > first_open and last_close > float(klines[-2][4]): # Fechou em alta e acima do fechamento anterior
        analysis.append(f"Mostrou **impulso de alta** no final do período.")
    elif last_close < first_open and last_close < float(klines[-2][4]): # Fechou em baixa e abaixo do fechamento anterior
        analysis.append(f"Mostrou **pressão vendedora** no final do período.")
    else:
        analysis.append(f"Movimento **lateral** no período.")

    return change_7h, total_volume, analysis, last_close

def main():
    print("Iniciando busca de dados para o Giro da Madrugada VIP...")

    exchange_info = get_exchange_info()
    if not exchange_info:
        send_telegram_message("Erro: Não foi possível obter informações da exchange. Análise não concluída.")
        return

    valid_symbols = {s["symbol"] for s in exchange_info["symbols"] if s["status"] == "TRADING" and s["quoteAsset"] == "USDT"}

    analysis_results = []
    all_tickers = []

    for symbol_base in SYMBOLS:
        symbol_usdt = f"{symbol_base}USDT"
        if symbol_usdt not in valid_symbols:
            print(f"Símbolo {symbol_usdt} não encontrado ou não negociável na Binance. Pulando.")
            continue

        klines = get_binance_klines(symbol_usdt)
        ticker_data = get_binance_ticker(symbol_usdt)

        if klines and ticker_data:
            change_7h, total_volume, analysis_text, last_close = analyze_klines(klines)
            price_24h_change = float(ticker_data.get("priceChangePercent", 0))
            current_price = float(ticker_data.get("lastPrice", 0))
            
            analysis_results.append({
                "symbol": symbol_base,
                "change_7h": change_7h,
                "total_volume": total_volume,
                "analysis_text": analysis_text,
                "price_24h_change": price_24h_change,
                "current_price": current_price
            })
            all_tickers.append({
                "symbol": symbol_base,
                "price": current_price,
                "change": price_24h_change
            })
        time.sleep(0.5) # Pequeno atraso para evitar rate limit

    if not analysis_results:
        send_telegram_message("Erro: Não foi possível obter dados para nenhuma moeda. Análise não concluída.")
        return

    # Destaques
    highest_volume = max(analysis_results, key=lambda x: x["total_volume"])
    highest_gain = max(analysis_results, key=lambda x: x["change_7h"])
    lowest_gain = min(analysis_results, key=lambda x: x["change_7h"])

    message_parts = [
        "<b>Giro da Madrugada VIP 🌙</b>",
        "(Análise Gráfico 1H - 00:00 às 07:00 Lisboa)",
        "",
        "--- Destaques do Período ---",
        f"🔥 Maior Volume Negociado: <b>{highest_volume["symbol"]}</b> (${format_price(highest_volume["total_volume"])})",
        f"🚀 Maior Alta: <b>{highest_gain["symbol"]}</b> ({highest_gain["change_7h"]:+.2f}%)",
        f"📉 Maior Baixa: <b>{lowest_gain["symbol"]}</b> ({lowest_gain["change_7h"]:+.2f}%)",
        "",
        "--- Análise Técnica (Price Action) ---"
    ]

    for res in analysis_results:
        if res["analysis_text"]:
            message_parts.append(f"<b>{res["symbol"]}</b>: {\' \'.join(res["analysis_text"])})")

    message_parts.append("")
    message_parts.append("--- Cotações Atuais ---")

    # Ordenar tickers por símbolo para exibição
    all_tickers.sort(key=lambda x: x["symbol"])

    for ticker in all_tickers:
        change_icon = "🟢" if ticker["change"] >= 0 else "🔴"
        message_parts.append(f"<b>{ticker["symbol"]}</b>: ${format_price(ticker["price"])} {change_icon} ({ticker["change"]:+.2f}%)")

    message_parts.extend([
        "",
        "<i>Análise baseada no método Marcus Aurora</i>"
    ])
    
    final_message = "\n".join(message_parts)
    send_telegram_message(final_message)

def send_telegram_message(text):
    """Envia a mensagem formatada para o Telegram."""
    if not BOT_TOKEN or not CHAT_ID_VIP:
        print("Erro: BOT_TOKEN ou CHAT_ID_VIP não configurados.")
        return

    payload = {
        \'chat_id\': CHAT_ID_VIP,
        \'text\': text,
        \'parse_mode\': \'HTML\'
    }
    try:
        response = requests.post(TELEGRAM_URL, data=payload, timeout=10)
        response.raise_for_status()
        print("Mensagem enviada com sucesso para o Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")

if __name__ == "__main__":
    main()
