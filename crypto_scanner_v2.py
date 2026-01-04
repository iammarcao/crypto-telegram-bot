import requests
import os
import json
from operator import itemgetter

# --- CONFIGURAÇÕES ---
# Lidas de variáveis de ambiente (padrão GitHub Actions)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CMC_API_KEY = os.environ.get("CMC_API_KEY")
CHAT_ID_VIP = os.environ.get("CHAT_ID_VIP")

# Moedas fixas (BTC, ETH, BNB, SOL, XRP, ADA)
FIXED_SYMBOLS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA"]

# URL base da API da CoinMarketCap
CMC_URL_QUOTES = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
CMC_URL_LISTINGS = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
# URL base da API do Telegram
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def get_crypto_data():
    """Busca dados das moedas fixas e da lista de Top Ganhadoras/Perdedoras."""
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
    }
    
    # 1. Buscar dados das moedas fixas
    fixed_params = {
        'symbol': ','.join(FIXED_SYMBOLS),
        'convert': 'USD',
    }
    
    fixed_data = {}
    try:
        response = requests.get(CMC_URL_QUOTES, headers=headers, params=fixed_params, timeout=15)
        response.raise_for_status()
        data = response.json()['data']
        for symbol in FIXED_SYMBOLS:
            if symbol in data:
                fixed_data[symbol] = data[symbol]['quote']['USD']
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados fixos: {e}")
        return None

    # 2. Buscar a lista de moedas (para encontrar Top Ganhadoras/Perdedoras)
    listing_params = {
        'start': '1',
        'limit': '100', # Limite para ter uma boa amostra
        'convert': 'USD',
    }
    
    dynamic_data = []
    try:
        response = requests.get(CMC_URL_LISTINGS, headers=headers, params=listing_params, timeout=15)
        response.raise_for_status()
        data = response.json()['data']
        
        # Filtrar moedas que já estão na lista fixa
        filtered_data = [
            item for item in data 
            if item['symbol'] not in FIXED_SYMBOLS
        ]
        
        # Ordenar por variação de 24h
        sorted_by_change = sorted(
            filtered_data, 
            key=lambda x: x['quote']['USD']['percent_change_24h'], 
            reverse=True
        )
        
        # Top 5 Ganhadoras (Top 5)
        top_gainers = sorted_by_change[:5]
        # Top 5 Perdedoras (Bottom 5)
        top_losers = sorted_by_change[-5:]
        
        # Consolidar dados dinâmicos
        for item in top_gainers + top_losers:
            dynamic_data.append({
                'symbol': item['symbol'],
                'quote': item['quote']['USD']
            })
            
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar lista dinâmica: {e}")
        # Continua com os dados fixos se a busca dinâmica falhar
        pass 

    return fixed_data, dynamic_data

def generate_observation(fixed_prices, dynamic_data):
    """Gera a observação analítica aprimorada."""
    if not fixed_prices:
        return "Não foi possível gerar a observação devido a um erro na obtenção dos dados."

    # 1. Análise de BTC e ETH (Manter a lógica de lateralidade)
    btc_change = fixed_prices['BTC']['percent_change_24h']
    eth_change = fixed_prices['ETH']['percent_change_24h']

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

    # 2. Análise de Tendência de 7 dias para Top Ganhadora/Perdedora
    
    # Encontrar a Top Ganhadora e Perdedora geral (entre as dinâmicas)
    if dynamic_data:
        top_gainer_dynamic = max(dynamic_data, key=lambda x: x['quote']['percent_change_24h'])
        top_loser_dynamic = min(dynamic_data, key=lambda x: x['quote']['percent_change_24h'])
        
        # Analisar a Top Ganhadora
        gainer_symbol = top_gainer_dynamic['symbol']
        gainer_change_7d = top_gainer_dynamic['quote']['percent_change_7d']
        gainer_change_24h = top_gainer_dynamic['quote']['percent_change_24h']
        
        if gainer_change_7d > 10:
            gainer_trend = f"em forte tendência de alta (+{gainer_change_7d:.1f}% em 7 dias)"
        elif gainer_change_7d > 0:
            gainer_trend = f"em tendência de alta (+{gainer_change_7d:.1f}% em 7 dias)"
        else:
            gainer_trend = f"em correção de 7 dias ({gainer_change_7d:.1f}%)"
            
        # Analisar a Top Perdedora
        loser_symbol = top_loser_dynamic['symbol']
        loser_change_7d = top_loser_dynamic['quote']['percent_change_7d']
        loser_change_24h = top_loser_dynamic['quote']['percent_change_24h']
        
        if loser_change_7d < -10:
            loser_trend = f"em forte tendência de baixa ({loser_change_7d:.1f}% em 7 dias)"
        elif loser_change_7d < 0:
            loser_trend = f"em tendência de baixa ({loser_change_7d:.1f}% em 7 dias)"
        else:
            loser_trend = f"em consolidação de 7 dias (+{loser_change_7d:.1f}%)"
            
        # Montar a observação
        observation = (
            f"Observação: BTC {btc_status}, ETH {eth_status}. "
            f"O destaque de alta é <b>{gainer_symbol}</b> (+{gainer_change_24h:.1f}%), que está {gainer_trend}. "
            f"A maior pressão de venda está em <b>{loser_symbol}</b> ({loser_change_24h:.1f}%), que está {loser_trend}."
        )
    else:
        observation = f"Observação: BTC {btc_status}, ETH {eth_status}. Não foi possível analisar o mercado dinâmico."
        
    return observation

def format_scanner_message(fixed_prices, dynamic_data):
    """Monta a mensagem do Scanner VIP V2."""
    if not fixed_prices:
        return "Erro ao obter dados das criptomoedas. Tente novamente mais tarde."

    message_parts = [
        "<b>Análise VIP do Mercado Crypto</b>",
        "",
        "--- Moedas Fixas (6) ---",
    ]
    
    # 1. Lista de Moedas Fixas
    for symbol in FIXED_SYMBOLS:
        if symbol in fixed_prices:
            quote = fixed_prices[symbol]
            price = quote['price']
            formatted_price = f"${price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            percent_change_24h = quote['percent_change_24h']
            change_icon = "🟢" if percent_change_24h >= 0 else "🔴"
            formatted_change = f"{percent_change_24h:+.2f}%"
            
            message_parts.append(f"<b>{symbol}</b>: {formatted_price} {change_icon} ({formatted_change})")
        else:
            message_parts.append(f"<b>{symbol}</b>: Cotação não disponível.")

    # 2. Lista de Moedas Dinâmicas
    if dynamic_data:
        message_parts.extend([
            "",
            "--- Top 5 Ganhadoras (24h) ---"
        ])
        
        # Ordenar Top 5 Ganhadoras
        top_gainers = sorted(
            [d for d in dynamic_data if d['quote']['percent_change_24h'] > 0],
            key=lambda x: x['quote']['percent_change_24h'],
            reverse=True
        )[:5]
        
        for item in top_gainers:
            symbol = item['symbol']
            quote = item['quote']
            price = quote['price']
            formatted_price = f"${price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            formatted_change = f"{quote['percent_change_24h']:+.2f}%"
            message_parts.append(f"<b>{symbol}</b>: {formatted_price} 🟢 ({formatted_change})")

        message_parts.extend([
            "",
            "--- Top 5 Perdedoras (24h) ---"
        ])
        
        # Ordenar Top 5 Perdedoras
        top_losers = sorted(
            [d for d in dynamic_data if d['quote']['percent_change_24h'] < 0],
            key=lambda x: x['quote']['percent_change_24h'],
            reverse=False
        )[:5]
        
        for item in top_losers:
            symbol = item['symbol']
            quote = item['quote']
            price = quote['price']
            formatted_price = f"${price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            formatted_change = f"{quote['percent_change_24h']:+.2f}%"
            message_parts.append(f"<b>{symbol}</b>: {formatted_price} 🔴 ({formatted_change})")

    # 3. Observação Aprimorada
    observation_text = generate_observation(fixed_prices, dynamic_data)
    message_parts.extend([
        "",
        observation_text
    ])
    
    return "\n".join(message_parts)

def send_telegram_message(text):
    """Envia a mensagem formatada para o Telegram."""
    if not BOT_TOKEN or not CHAT_ID_VIP:
        print("Erro: BOT_TOKEN ou CHAT_ID_VIP não configurados nas variáveis de ambiente.")
        return None
        
    payload = {
        'chat_id': CHAT_ID_VIP,
        'text': text,
        'parse_mode': 'HTML'
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
    print("Iniciando busca de preços para o Scanner VIP V2...")
    fixed_prices, dynamic_data = get_crypto_data()
    
    message_text = format_scanner_message(fixed_prices, dynamic_data)
    print("\n--- Mensagem Formatada ---")
    print(message_text)
    print("--------------------------\n")
    
    if "Erro" not in message_text:
        send_telegram_message(message_text)
    else:
        print("Não foi possível enviar a mensagem devido a um erro na obtenção dos dados.")

if __name__ == "__main__":
    import requests # Importar requests aqui para o teste manual
    main()
