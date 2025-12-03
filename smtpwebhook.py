import imaplib
import email
from email.header import decode_header
import time
import json
import requests
from datetime import datetime
import re

EMAIL_ADDRESS = "envio@nacionalcorretores.com.br"
EMAIL_PASSWORD = "Sucesso2025@*"
IMAP_SERVER = "imap.skymail.net.br"  
IMAP_PORT = 993

# Webhook
WEBHOOK_URL = "https://krmttlcolzufrgyfontp.supabase.co/functions/v1/email-to-whatsapp"

# Configurações
CHECK_INTERVAL = 5  # Verifica a cada 5 segundos (ajuste conforme necessário)
EMAIL_FOLDER = "INBOX"  # ou "INBOX/CRM" se tiver pasta específica

# ===== FUNÇÕES =====

def connect_to_email():
    """Conecta ao servidor IMAP"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select(EMAIL_FOLDER)
        print(f"✅ Conectado ao email: {EMAIL_ADDRESS}")
        return mail
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return None

def decode_email_subject(subject):
    """Decodifica assunto do email"""
    if subject is None:
        return ""
    decoded = decode_header(subject)
    subject_parts = []
    for content, encoding in decoded:
        if isinstance(content, bytes):
            subject_parts.append(content.decode(encoding or 'utf-8', errors='ignore'))
        else:
            subject_parts.append(content)
    return ''.join(subject_parts)

def get_email_html(msg):
    """Extrai corpo HTML do email"""
    html_body = ""
    text_body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        if content_type == "text/html":
                            html_body = payload.decode('utf-8', errors='ignore')
                        elif content_type == "text/plain" and not text_body:
                            text_body = payload.decode('utf-8', errors='ignore')
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                content_type = msg.get_content_type()
                decoded = payload.decode('utf-8', errors='ignore')
                if content_type == "text/html":
                    html_body = decoded
                else:
                    text_body = decoded
        except:
            pass
    
    # Se não tem HTML, converte texto para HTML simples
    if not html_body and text_body:
        html_body = f"<html><body><pre>{text_body}</pre></body></html>"
    
    return html_body.strip()

def parse_email_to_json(msg):
    """Converte email em JSON no formato esperado pela Edge Function"""
    subject = decode_email_subject(msg["Subject"])
    from_email = msg.get("From", "")
    html_body = get_email_html(msg)
    
    # Extrai apenas o endereço de email (remove nome se tiver)
    # Ex: "CRM Sistema <contato@imoview.com.br>" -> "contato@imoview.com.br"
    email_match = re.search(r'<(.+?)>|([^\s<>]+@[^\s<>]+)', from_email)
    clean_from = email_match.group(1) or email_match.group(2) if email_match else from_email
    
    # Monta JSON no formato exato esperado
    email_data = {
        "subject": subject,
        "html": html_body,
        "from": clean_from.strip()
    }
    
    return email_data

def send_to_webhook(email_data):
    """Envia JSON para webhook"""
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=email_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Webhook enviado com sucesso!")
            print(f"   Assunto: {email_data['subject']}")
            print(f"   De: {email_data['from']}")
            return True
        else:
            print(f"⚠️  Webhook retornou status {response.status_code}")
            print(f"   Resposta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao enviar webhook: {e}")
        return False

def monitor_emails():
    """Monitora emails continuamente"""
    print("🚀 Iniciando monitoramento de emails...")
    print(f"📧 Email: {EMAIL_ADDRESS}")
    print(f"🔗 Webhook: {WEBHOOK_URL}")
    print(f"⏱️  Verificando a cada {CHECK_INTERVAL} segundos\n")
    
    mail = connect_to_email()
    if not mail:
        return
    
    # IDs já processados
    processed_ids = set()
    
    while True:
        try:
            # Busca emails não lidos
            status, messages = mail.search(None, 'UNSEEN')
            
            if status == "OK":
                email_ids = messages[0].split()
                
                for email_id in email_ids:
                    # Converte para string se necessário
                    email_id_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                    
                    if email_id_str in processed_ids:
                        continue
                    
                    # Busca email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    
                    if status == "OK":
                        # Parse email
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Converte para JSON
                        email_data = parse_email_to_json(msg)
                        
                        print(f"\n📨 Novo email detectado!")
                        print(f"   De: {email_data['from']}")
                        print(f"   Assunto: {email_data['subject']}")
                        
                        # Envia para webhook
                        if send_to_webhook(email_data):
                            processed_ids.add(email_id_str)
                            # Opcional: marcar como lido
                            # mail.store(email_id, '+FLAGS', '\\Seen')
            
            # Aguarda antes da próxima verificação
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoramento interrompido pelo usuário")
            break
        except Exception as e:
            print(f"❌ Erro no loop: {e}")
            print("🔄 Tentando reconectar...")
            time.sleep(10)
            mail = connect_to_email()
            if not mail:
                break

if __name__ == "__main__":
    monitor_emails()