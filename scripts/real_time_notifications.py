import smtplib
from email.mime.text import MIMEText

def send_notification(subject, body, to):
    # Configuración del servidor de correo
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_user = 'tu_correo@gmail.com'
    smtp_password = 'tu_contraseña'

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to, msg.as_string())

# Ejemplo de uso
subject = 'Alerta de Trading en Tiempo Real'
body = 'Se ha generado una nueva señal de trading.'
to = 'destinatario@gmail.com'
send_notification(subject, body, to)
