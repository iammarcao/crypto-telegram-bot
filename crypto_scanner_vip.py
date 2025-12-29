import requests
import json
import os
from datetime import datetime
import pytz # Para lidar com fuso horário de Lisboa

# --- CONFIGURAÇÕES ---
# Token do seu bot do Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Chave API da CoinMarketCap
CMC_API_KEY = os.environ.get("CMC_API_KEY")
# chat_id da SALA VIP
CHAT_ID_VIP = os.environ.get("CHAT_ID_VIP")
# Moedas que você quer no scanner
SYMBOLS = ["BTC", "ETH", "BNB", "SOL", "XRP"]

# URL base da API da CoinMarketCap
CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
# URL base da API do Telegram
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def get_prices():
    """Busca dados das moedas na CoinMarketCap."""
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
    }
    parameters = {
        'symbol': ','.join(SYMBOLS),
        'convert': 'USD',
    }

    try:
        response = requests.get(CMC_URL, headers=headers, params=parameters, timeout=15)
        response.raise_for_status()
        data = response.json()['data']

        result = {}
        for symbol in SYMBOLS:
            if symbol in data:
                quote = data[symbol]['quote']['USD']
                result[symbol] = {
                    "price": quote['price'],
                    "percent_change_24h": quote['percent_change_24h'],
                    "percent_change_7d": quote['percent_change_7d'],
                }
        return result
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar à API da CoinMarketCap: {e}")
        return None

def generate_observation(prices):
    """Gera a observação analítica baseada na variação de 24h."""
    if not prices:
        return "Não foi possível gerar a observação devido a um erro na obtenção dos dados."

    # 1. Análise de BTC e ETH
    btc_change = prices['BTC']['percent_change_24h']
    eth_change = prices['ETH']['percent_change_24h']

    # Lógica para BTC
    if -0.5 <= btc_change <= 0.5:
        btc_status = "está lateral"
    elif btc_change > 0.5:
        btc_status = "levemente positiva"
    else:
        btc_status = "levemente negativa"

    # Lógica para ETH
    if -0.5 <= eth_change <= 0.5:
        eth_status = "levemente lateral"
    elif eth_change > 0.5:
        eth_status = "levemente positiva"
    else:
        eth_status = "levemente negativa"

    # 2. Foco de Volatilidade (maior variação absoluta)
    max_abs_change = 0
    focus_symbol = ""
    for symbol in SYMBOLS:
        change = prices[symbol]['percent_change_24h']
        if abs(change) > max_abs_change:
            max_abs_change = abs(change)
            focus_symbol = symbol

    observation = (
        f"Observação: BTC {btc_status}, ETH {eth_status}, "
        f"foco de volatilidade hoje em {focus_symbol}."
    )
    return observation

def format_scanner_message(prices):
    """Monta a mensagem do Scanner VIP."""
    if not prices:
        return "Erro ao obter dados das criptomoedas. Tente novamente mais tarde."

    # Determinar maior alta e maior queda nas últimas 24h
    sorted_by_24h = sorted(
        SYMBOLS,
        key=lambda s: prices[s]["percent_change_24h"],
        reverse=True,
    )
    top_gainer = sorted_by_24h[0]
    top_loser = sorted_by_24h[-1]

    # Dados do Top Gainer
    gainer_change = prices[top_gainer]["percent_change_24h"]
    gainer_sign = "🔼"
    
    # Dados do Top Loser
    loser_change = prices[top_loser]["percent_change_24h"]
    loser_sign = "🔽"

    # Geração da Observação
    observation_text = generate_observation(prices)

    # Montagem da Mensagem
    message_parts = [
        "<b>Scanner VIP</b>",
        "",
        f"{gainer_sign} Maior alta entre as 5: <b>{top_gainer}</b> {gainer_change:+.1f}% (24h)",
        f"{loser_sign} Maior queda entre as 5: <b>{top_loser}</b> {loser_change:+.1f}% (24h)",
        "",
        observation_text,
    ]

    return "\n".join(message_parts)

def send_telegram_message(text):
    """Envia a mensagem formatada para o Telegram."""
    payload = {
        'chat_id': CHAT_ID_VIP,
        'text': text,
        'parse_mode': 'HTML' # Usando HTML para negrito e emojis
    }

    try:
        response = requests.post(TELEGRAM_URL, data=payload, timeout=15)
        response.raise_for_status()
        print("Mensagem enviada com sucesso para o Telegram.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")
        return None

def main():
    """Função principal para executar o fluxo."""
    print("Iniciando busca de preços para o Scanner VIP...")
    prices = get_prices()
    
    message_text = format_scanner_message(prices)
    print("\n--- Mensagem Formatada ---")
    print(message_text)
    print("--------------------------\n")
    
    if "Erro" not in message_text:
        send_telegram_message(message_text)
    else:
        print("Não foi possível enviar a mensagem devido a um erro na obtenção dos dados.")

if __name__ == "__main__":
    main()
