import requests

# Configuración de Telegram
telegram_token = '7635259719:AAFnWapsNFwdlJqSOEIbJJYDSv5wzS9egbk'
telegram_chat_id = '1434149527'

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Lanza un error si la respuesta no es exitosa
        print("Mensaje enviado a Telegram exitosamente.")
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

# Prueba de envío
send_telegram_message("Prueba de mensaje desde el script.")