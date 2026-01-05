import requests
import os
import json
import time
from datetime import datetime, timedelta
from operator import itemgetter

# --- CONFIGURAÇÕES ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_VIP = os.environ.get("CHAT_ID_VIP")

# Moedas a serem analisadas (usando pares USDT da Binance)
TARGET_SYMBOLS_BASE = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ZEC", "SUI", "BNB", "SEI", "UNI", 
    "ONDO", "ORDI", "NEAR", "LDO", "JUP", "TIA", "TRON", "AVAX"
]
# Nota: 'river' e '1000pepe' não são símbolos padrão da Binance. Usaremos 'PEPE' e ignoraremos 'river'.
TARGET_SYMBOLS_BASE.extend(["PEPE"]) 
TARGET_SYMBOLS = [s + "USDT" for s in TARGET_SYMBOLS_BASE]

# URLs da API da Binance
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
# URL base da API do Telegram
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def get_klines_data(symbol, interval, start_time, end_time):
    """Busca dados de candlestick (klines) da Binance."""
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': 7 # Buscar as últimas 7 velas de 1h
    }
    try:
        response = requests.get(BINANCE_KLINES_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar klines para {symbol}: {e}")
        return None

def get_giro_data():
    """Busca dados de 1h para o período 00:00 a 07:00 (Lisboa/UTC)."""
    
    # O GitHub Actions roda em UTC. Lisboa no inverno é UTC.
    # O período de análise é 00:00 a 07:00 UTC (7 velas de 1h).
    
    # Não precisamos de start_time e end_time, pois usaremos 'limit=7'
    # O período de análise será as últimas 7 velas de 1h.
    pass
    
    all_data = []
    
    # 1. Buscar dados de 1h para cada moeda
    for symbol in TARGET_SYMBOLS:
        klines = get_klines_data(symbol, '1h', None, None)
        
        if klines and len(klines) >= 7: # Deve ter pelo menos 7 velas
            # Processar os dados
            closes = [float(k[4]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            
            open_price = float(klines[0][1])
            close_price = float(klines[-1][4])
            
            # Calcular a variação total do período
            price_change_percent = ((close_price - open_price) / open_price) * 100
            
            # Calcular o volume total do período
            total_volume = sum(volumes)
            
            # Encontrar a máxima e mínima do período
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            period_high = max(highs)
            period_low = min(lows)
            
            # Obter o preço atual (último fechamento)
            current_price = close_price
            
            all_data.append({
                'symbol': symbol,
                'price': current_price,
                'change_percent': price_change_percent,
                'total_volume': total_volume,
                'period_high': period_high,
                'period_low': period_low,
                'open_price': open_price,
                'close_price': close_price,
            })
            
    return all_data

def analyze_technical(data):
    """Implementa a lógica de análise técnica (rompimentos)."""
    if not data:
        return None, None, None, None
    
    # 1. Maior Volume
    top_volume = max(data, key=itemgetter('total_volume'))
    
    # 2. Maior Variação (Alta e Baixa)
    top_gainer = max(data, key=itemgetter('change_percent'))
    top_loser = min(data, key=itemgetter('change_percent'))
    
    # 3. Análise de Rompimento (Price Action)
    # Procuramos por moedas que fecharam perto da máxima ou mínima do período
    
    technical_analysis = []
    
    for item in data:
        symbol = item['symbol'].replace('USDT', '')
        price = item['price']
        high = item['period_high']
        low = item['period_low']
        change = item['change_percent']
        
        # Rompimento de Máxima (Fechamento perto da máxima do período)
        if change > 3 and (high - price) / high < 0.005: # Mais de 3% de alta e fechou a 0.5% da máxima
            analysis = f"<b>{symbol}</b>: Fechou o período de 7h na máxima, indicando um **forte rompimento de resistência** e pressão compradora. Próximo alvo em {high:.4f}."
            technical_analysis.append(analysis)
            
        # Rompimento de Mínima (Fechamento perto da mínima do período)
        elif change < -3 and (price - low) / low < 0.005: # Mais de 3% de baixa e fechou a 0.5% da mínima
            analysis = f"<b>{symbol}</b>: Fechou o período de 7h na mínima, indicando **rompimento de fundo importante** e pressão vendedora. Próximo suporte em {low:.4f}."
            technical_analysis.append(analysis)
            
        # Suporte/Resistência Testada (Variação moderada, mas tocou a máxima/mínima)
        elif 0.5 < change < 3 and (high - price) / high > 0.01 and (high - price) / high < 0.05:
            analysis = f"<b>{symbol}</b>: Testou a resistência em {high:.4f} e recuou, indicando **pressão vendedora** no topo do range."
            technical_analysis.append(analysis)
            
        elif -3 < change < -0.5 and (price - low) / low > 0.01 and (price - low) / low < 0.05:
            analysis = f"<b>{symbol}</b>: Testou o suporte em {low:.4f} e se recuperou, indicando **pressão compradora** no fundo do range."
            technical_analysis.append(analysis)
            
    return top_volume, top_gainer, top_loser, technical_analysis

def format_giro_message(top_volume, top_gainer, top_loser, technical_analysis, all_data):
    """Monta a mensagem do Giro da Madrugada VIP."""
    if not top_volume:
        return "Erro ao obter dados da Binance. A análise não pôde ser concluída."

    # Formatação de preço e volume
    def format_price(price):
        return f"${price:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    def format_volume(volume):
        if volume >= 1_000_000_000:
            return f"${volume/1_000_000_000:,.2f}B"
        elif volume >= 1_000_000:
            return f"${volume/1_000_000:,.2f}M"
        else:
            return f"${volume:,.0f}"

    # Análise de Destaques
    gainer_symbol = top_gainer['symbol'].replace('USDT', '')
    loser_symbol = top_loser['symbol'].replace('USDT', '')
    volume_symbol = top_volume['symbol'].replace('USDT', '')
    
    message_parts = [
        "<b>Giro da Madrugada VIP 🌙</b>",
        "(Análise Gráfico 1H - 00:00 às 07:00 Lisboa)",
        "",
        "--- Destaques do Período ---",
        f"🔥 Maior Volume Negociado: <b>{volume_symbol}</b> ({format_volume(top_volume['total_volume'])})",
        f"🚀 Maior Alta: <b>{gainer_symbol}</b> ({top_gainer['change_percent']:+.2f}%)",
        f"📉 Maior Baixa: <b>{loser_symbol}</b> ({top_loser['change_percent']:+.2f}%)",
        "",
        "--- Análise Técnica (Price Action) ---"
    ]
    
    # 1. Análise Técnica Detalhada
    if technical_analysis:
        message_parts.extend(technical_analysis)
    else:
        message_parts.append("O mercado se manteve em consolidação, sem rompimentos significativos de máxima ou mínima do período.")
        
    # 2. Lista de Cotações
    message_parts.extend([
        "",
        "--- Cotações Atuais ---"
    ])
    
    # Ordenar por símbolo para facilitar a leitura
    all_data_sorted = sorted(all_data, key=itemgetter('symbol'))
    
    for item in all_data_sorted:
        symbol = item['symbol'].replace('USDT', '')
        price = item['price']
        change = item['change_percent']
        change_icon = "🟢" if change >= 0 else "🔴"
        
        message_parts.append(f"<b>{symbol}</b>: {format_price(price)} {change_icon} ({change:+.2f}%)")
        
    message_parts.extend([
        "",
        "<i>Análise baseada no método Marcus Aurora</i>"
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
    print("Iniciando busca de dados para o Giro da Madrugada VIP...")
    
    # Verifica se as variáveis de ambiente estão presentes
    if not os.environ.get("BOT_TOKEN") or not os.environ.get("CHAT_ID_VIP"):
        print("ERRO: Variáveis de ambiente (BOT_TOKEN, CHAT_ID_VIP) não estão configuradas.")
        return

    all_data = get_giro_data()
    top_volume, top_gainer, top_loser, technical_analysis = analyze_technical(all_data)
    
    message_text = format_giro_message(top_volume, top_gainer, top_loser, technical_analysis, all_data)
    print("\n--- Mensagem Formatada ---")
    print(message_text)
    print("--------------------------\n")
    
    if "Erro" not in message_text:
        send_telegram_message(message_text)
    else:
        print("Não foi possível enviar a mensagem devido a um erro na obtenção dos dados.")

if __name__ == "__main__":
    main()
